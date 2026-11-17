from datetime import date, timedelta
from decimal import Decimal
import os
import streamlit as st
from dotenv import load_dotenv
from review import load_records, budget_overview, PurchaseRequest, evaluate
from agent import draft_request, explain

load_dotenv()
st.set_page_config(page_title='Campus Spending Review', page_icon='🎓', layout='wide')
st.title('Campus Spending Review')
st.caption('A second look before your organization commits funds.')
st.warning('Prototype · Mock financial data · Illustrative policies, not official CMU rules. Every result is a recommendation; a human treasurer makes the final decision.')
with st.sidebar:
    st.header('Review settings')
    use_ai = st.toggle('Add OpenAI explanation', value=False)
    st.caption('When enabled, verified financial summaries and policy results are sent to OpenAI. Purchase free text and API keys are not included in that summary.')
    st.caption('Read-only: this app cannot change budgets, approve purchases, or make payments.')

try:
    budgets, ledger, policies = load_records()
except (OSError, ValueError, KeyError, TypeError) as exc:
    st.error(f'Data needs verification. Review is unavailable: {exc}')
    st.stop()

st.subheader('Budget Overview')
overview = budget_overview(budgets, ledger)
cols = st.columns(3)
for col, key, label in zip(cols, ['allocation', 'committed', 'available'], ['Total allocated', 'Outstanding commitments', 'Available across categories']):
    col.metric(label, f"${sum(r[key] for r in overview):,.2f}")
st.caption('Category restrictions apply; totals do not imply funds can be transferred between categories.')
st.dataframe([{'Category': r['category'], 'Allocation': f"${r['allocation']:,.2f}",
    'Paid expenses': f"${r['paid']:,.2f}", 'Commitments': f"${r['committed']:,.2f}",
    'Available': f"${r['available']:,.2f}", 'Verified on': str(r['verified_on'])} for r in overview], hide_index=True, width='stretch')
if any((date.today() - r['verified_on']).days not in range(policies['max_record_age_days'] + 1) for r in overview):
    st.warning('Some records are stale or future-dated. Requests in those categories require verification.')
with st.expander('Illustrative policies and source records'):
    st.json({k: str(v) if isinstance(v, Decimal) else v for k, v in policies.items()})
    st.dataframe([{**r, 'amount': str(r['amount'])} for r in ledger], hide_index=True)
    st.caption('Edit local files in data/ to configure the prototype. Verification dates mean the entire category ledger has been reconciled, including outstanding commitments.')

st.subheader('Purchase request')
categories = [row['category'] for row in budgets]
today = date.today()
date_min, date_max = date(1900, 1, 1), date(2100, 12, 31)
fields = ('description', 'purpose', 'amount', 'category', 'deadline', 'vendor', 'quote', 'comments')


def fill_request(values, *, from_ai=False):
    for field in fields:
        st.session_state[field] = values.get(field) or (None if field in ('deadline', 'category') else '')
    st.session_state['confirm_draft'] = False
    st.session_state['from_ai'] = from_ai
    for key in ('review', 'ai_text', 'ai_error'):
        st.session_state.pop(key, None)


sample = dict(description='Van rental', purpose='Transportation to a student organization event',
              amount='450.00', category='Travel' if 'Travel' in categories else None,
              deadline=today + timedelta(days=1), vendor='Example Van Rentals',
              quote='Estimated rental cost: $450')
st.button('Try a sample request', on_click=fill_request, args=(sample,))

with st.expander('Draft with AI'):
    st.caption('Drafting sends the text you enter here to OpenAI.')
    description_text = st.text_area('Describe your purchase', placeholder='We need a $450 van for Saturday.')
    if st.button('Draft request'):
        if not description_text.strip():
            st.info('Enter a purchase description to create a draft.')
        elif not os.getenv('OPENAI_API_KEY'):
            st.info('AI drafting requires an OpenAI API key. You can fill in the form below.')
        else:
            try:
                with st.spinner('Drafting request…'):
                    draft = draft_request(description_text.strip(), categories, today)
                try:
                    deadline = date.fromisoformat(draft.get('deadline') or '')
                    draft['deadline'] = deadline if date_min <= deadline <= date_max else None
                except ValueError:
                    draft['deadline'] = None
                if draft.get('category') not in categories:
                    draft['category'] = None
                fill_request(draft, from_ai=True)
            except Exception:
                st.warning('AI drafting is unavailable. You can fill in the form below.')

with st.form('request'):
    left, right = st.columns(2)
    with left:
        description = st.text_input('Purchase description', key='description')
        description_feedback = st.empty()
        purpose = st.text_input('Purpose', key='purpose')
        purpose_feedback = st.empty()
        amount = st.text_input('Requested amount (USD)', key='amount')
        amount_feedback = st.empty()
        category = st.selectbox('Spending category', categories, index=None, key='category')
        category_feedback = st.empty()
    with right:
        deadline = st.date_input('Date needed', value=None, min_value=date_min, max_value=date_max, key='deadline')
        deadline_feedback = st.empty()
        vendor = st.text_input('Vendor', key='vendor')
        vendor_feedback = st.empty()
        quote = st.text_input('Vendor quote or estimated cost', key='quote')
        quote_feedback = st.empty()
        comments = st.text_area('Additional comments or justification', key='comments')
    from_ai = st.session_state.get('from_ai', False)
    confirmed = not from_ai or st.checkbox('I verified the spending category and date needed', key='confirm_draft')
    submitted = st.form_submit_button('Review purchase', type='primary')

if submitted:
    if not description.strip():
        description_feedback.caption('Enter a purchase description.')
    if not purpose.strip():
        purpose_feedback.caption('Explain what the purchase is for.')
    if not vendor.strip():
        vendor_feedback.caption('Enter the vendor name.')
    if not quote.strip() and policies['quote_required']:
        quote_feedback.caption('Enter a vendor quote or cost estimate.')
    if deadline is None:
        deadline_feedback.caption('Choose the date you need the purchase.')
    elif deadline < today:
        deadline_feedback.caption('Choose a new date. The date entered has passed.')

    # Clear a previous result before validating the new request.
    st.session_state.pop('review', None)
    st.session_state.pop('ai_text', None)
    st.session_state.pop('ai_error', None)
    if not category:
        category_feedback.error('Select a spending category.')
    if not amount.strip():
        amount_feedback.error('Enter the requested amount.')
    if not confirmed:
        st.warning('Verify the spending category and date needed before reviewing the draft.')
    if not category or not amount.strip() or not confirmed or (from_ai and deadline is None):
        st.stop()
    try:
        result = evaluate(PurchaseRequest(description, purpose, amount, category, deadline, vendor, quote, comments), budgets, ledger, policies)
        st.session_state['review'] = result
        if use_ai:
            if not os.getenv('OPENAI_API_KEY'):
                st.session_state['ai_error'] = 'No API key configured. Showing the verified rule-based review.'
            else:
                try:
                    with st.spinner('Explaining the verified review…'):
                        st.session_state['ai_text'] = explain(result)
                except Exception:
                    st.session_state['ai_error'] = 'OpenAI explanation unavailable. Showing the verified rule-based review; check API access and model settings.'
    except ValueError as exc:
        amount_feedback.error(str(exc))

st.subheader('Purchase review')
if 'review' not in st.session_state:
    st.info('Submit a purchase request to see the recommendation and supporting checks.')
else:
    r = st.session_state['review']
    st.caption('Snapshot of the last submitted request. Submit again after changing fields or source records.')
    decision = r['decision']
    display, title = {
        'APPROVE': (st.success, 'APPROVE · Ready for treasurer review'),
        'DEFER': (st.warning, 'DEFER · More information needed'),
        'ESCALATE': (st.error, 'ESCALATE · Ask your treasurer'),
    }[decision]
    display(title)
    reason = r['reasons'][0]
    if Decimal(r['shortfall']) > 0:
        reason = f"The request is ${Decimal(r['shortfall']):,.2f} over the available {r['category']} budget."
    st.write(reason)
    next_step = r['next_steps'][0]
    if decision == 'DEFER':
        missing = r['missing'][0]
        next_step = ('Ask your treasurer to verify the category records, then review again.'
                     if missing.startswith('Verify category records')
                     else f'{missing} Then review the request again.')
    st.write(f'**Next step** · {next_step}')

    with st.expander('Why this decision?'):
        st.markdown(
            rf"**{r['category']} budget available** · "
            rf"\${Decimal(r['allocation']):,.2f} allocated − \${Decimal(r['paid']):,.2f} paid "
            rf"− \${Decimal(r['committed']):,.2f} committed = **\${Decimal(r['available']):,.2f}**"
        )
        st.markdown(
            rf"**Request** \${Decimal(r['amount']):,.2f} · "
            rf"**After purchase** \${Decimal(r['after_purchase']):,.2f} · "
            rf"**Shortfall** \${Decimal(r['shortfall']):,.2f}"
        )
        for label, items in [('Reasons', r['reasons']), ('Policy checks', r['rules']),
                             ('Missing information', r['missing']), ('Next steps', r['next_steps'])]:
            st.markdown(f'**{label}**')
            for item in items or ['None identified by configured checks.']:
                st.write('• ' + item)
        st.caption('Confirm category and supporting documents manually.')
        if st.session_state.get('ai_error'):
            st.info(st.session_state['ai_error'])
        if st.session_state.get('ai_text'):
            st.markdown('**OpenAI explanation**')
            st.write(st.session_state['ai_text'])
