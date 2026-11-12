from datetime import date, timedelta
from decimal import Decimal
import os
import streamlit as st
from dotenv import load_dotenv
from review import load_records, budget_overview, PurchaseRequest, evaluate
from agent import explain

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

st.subheader('Purchase Request')
st.caption('The prefilled van rental demonstrates the $150 Travel shortfall. Replace the fields to review another request.')
with st.form('request'):
    left, right = st.columns(2)
    with left:
        description = st.text_input('Purchase description', 'Van rental')
        purpose = st.text_input('Purpose', 'Transportation to a student organization event')
        amount = st.text_input('Requested amount (USD)', '450.00')
        category = st.selectbox('Spending category', [r['category'] for r in budgets])
    with right:
        deadline = st.date_input('Date needed', date.today() + timedelta(days=1))
        vendor = st.text_input('Vendor', 'Example Van Rentals')
        quote = st.text_input('Vendor quote or estimated cost', 'Estimated rental cost: $450')
        comments = st.text_area('Additional comments or justification')
    submitted = st.form_submit_button('Review purchase', type='primary')

if submitted:
    # Clear a previous result before validating the new request.
    st.session_state.pop('review', None)
    st.session_state.pop('ai_text', None)
    st.session_state.pop('ai_error', None)
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
        st.error(str(exc))

st.subheader('AI Recommendation')
if 'review' not in st.session_state:
    st.info('Submit a purchase request to see the recommendation and supporting checks.')
else:
    r = st.session_state['review']
    st.caption('Snapshot of the last submitted request. Submit again after changing fields or source records.')
    display = {'APPROVE': st.success, 'DEFER': st.warning, 'ESCALATE': st.error}[r['decision']]
    display(f"Recommended decision: {r['decision']} — human decision required")
    st.write(f"**{r['category']} available:** ${r['allocation']} allocation − ${r['paid']} paid − ${r['committed']} committed = **${r['available']}**")
    st.write(f"**Request:** ${r['amount']} · **After purchase:** ${r['after_purchase']} · **Shortfall:** ${r['shortfall']}")
    for label, items in [('Explanation', r['reasons']), ('Policy rules applied', r['rules']), ('Missing information / verification', r['missing']), ('Next steps', r['next_steps'])]:
        st.markdown(f'**{label}**')
        for item in items or ['None identified by configured checks.']:
            st.write('• ' + item)
    st.caption('Free-text purpose, quote accuracy, and comments are not semantically verified in this MVP. Confirm the category and supporting documents manually.')
    if st.session_state.get('ai_error'):
        st.info(st.session_state['ai_error'])
    if st.session_state.get('ai_text'):
        st.markdown('**OpenAI explanation · generated commentary; verify against the calculations above**')
        st.write(st.session_state['ai_text'])
    else:
        st.caption('Rule-based explanation shown. No AI call was made or the AI call was unavailable.')
