from datetime import date, timedelta
from decimal import Decimal
from uuid import uuid4
import os
import streamlit as st
from dotenv import load_dotenv
from review import load_records, budget_overview, PurchaseRequest, evaluate
from agent import review_chat
from chat_review import ChatReviewError
from purchase_chat import (
    PAYMENT_COMMAND, SpendingDetailsNeeded, apply_budget_command, budget_command, build_reply, chat_transcript,
    confirm_payment, escalation_summary, review_snapshot, session_budgets, session_ledger,
)
from submission_log import record_submission, save_review

load_dotenv()
st.set_page_config(page_title='Campus Spending Review', page_icon='🎓', layout='wide')

def setting(name, default=None):
    fallback = os.getenv(name, default)
    try:
        return st.secrets.get(name, fallback)
    except FileNotFoundError:
        return fallback


api_key = setting('OPENAI_API_KEY')
chat_requested = str(setting('OPENAI_CHAT_ENABLED', 'true')).strip().lower() == 'true'
chat_enabled = chat_requested and isinstance(api_key, str) and bool(api_key.strip())
supabase_url = setting('SUPABASE_URL')
supabase_key = setting('SUPABASE_SECRET_KEY')
logging_enabled = bool(supabase_url and supabase_key)

st.title('Campus Spending Review')
st.caption('A second look before your organization commits funds.')
st.warning('Prototype · Mock financial data · Illustrative policies, not official CMU rules. Every result is a recommendation; a human treasurer makes the final decision.')

try:
    budgets, ledger, policies = load_records()
except (OSError, ValueError, KeyError, TypeError) as exc:
    st.error(f'Data needs verification. Review is unavailable: {exc}')
    st.stop()


def display_chat_message(message):
    with st.chat_message(message['role']):
        if message['role'] == 'user' or message.get('account_notice') or message.get('payment_notice'):
            st.text(message['text'])
            return
        if 'error' in message:
            st.warning(message['text'])
            st.caption('Use Manual review to continue without the chat model.')
            return

        result = message['result']
        decision = result['decision']
        evidence = result['evidence']
        market = evidence.get('market_price')
        heading = {
            'APPROVE': 'APPROVE · Ready for treasurer review',
            'DEFER': 'DEFER · More information needed',
            'ESCALATE': 'ESCALATE · Human review required',
        }[decision]
        if decision == 'DEFER' and market and market['status'] == 'unavailable':
            heading = 'DEFER · Price check unavailable'
        elif decision == 'DEFER' and market and market['status'] == 'insufficient_sources':
            heading = 'DEFER · Price comparison incomplete'
        st.markdown(f'**{heading}**')
        if deadline := evidence.get('deadline'):
            needed_by = date.fromisoformat(deadline)
            st.text(f'Needed by {needed_by:%B} {needed_by.day}, {needed_by.year}')
        st.text(message['text'])
        st.text(message['next_action'])
        if decision == 'ESCALATE':
            with st.expander('Escalation summary to share'):
                st.code(escalation_summary(message), language='text')

        if market:
            with st.expander('Market price check', expanded=True):
                st.text(market['summary'])
                if market.get('scope'):
                    st.text(market['scope'])
                for index, option in enumerate(market.get('options', market['prices']), 1):
                    provider = option['provider']
                    if location := option.get('location'):
                        provider += f' · {location}'
                    if option.get('price_type') == 'quote_required':
                        price_label = 'Exact price requires a provider quote'
                    else:
                        price = f"${Decimal(option['total_usd']):,.2f}"
                        price_label = f'Published starting rate {price}' if option.get('price_type') == 'starting_rate' else price
                    availability = {
                        'confirmed': 'Availability confirmed for the requested dates',
                        'unverified': 'Availability unverified',
                        'unavailable': 'Unavailable for the requested dates',
                    }.get(option.get('availability'))
                    details = [provider, price_label, availability, option['terms']]
                    st.text('\n'.join(detail for detail in details if detail))
                    st.link_button(f'Open provider page {index}', option['url'])

        with st.expander('Verified checks and interpreted request'):
            if 'available' in evidence:
                st.text(f"{evidence['category']} available: ${Decimal(evidence['available']):,.2f}")
            if 'shortfall' in evidence:
                st.text(f"Shortfall: ${Decimal(evidence['shortfall']):,.2f}")
            for item in evidence['escalation_reasons'] + evidence['missing']:
                if not market or item != market['summary']:
                    st.text(item)
            st.markdown('**Policy checks**')
            for rule in evidence['rules']:
                st.text(rule)
            st.table([{'Field': field.capitalize(), 'Value': value or 'Missing'}
                      for field, value in result['request'].items()])


st.subheader('Review a purchase in chat')
st.caption('Describe a planned purchase or report money already spent.')
if chat_enabled:
    disclosure = 'Chat sends fictional purchase details to OpenAI for review.'
    if logging_enabled:
        disclosure += ' Reviews, payments, and budget updates are saved in the project database.'
    st.caption(disclosure)
    st.caption('To record past spending, tell the chat what you paid, such as “We spent $100 for food”.')
elif chat_requested:
    st.info('OpenAI chat needs an API key. Use Manual review below.')
else:
    st.info('Purchase chat is paused. Use Manual review below.')

with st.container():
    chat = st.session_state.setdefault('expense_review_chat', [])
    saved_reviews = st.session_state.setdefault('chat_review_history', {})
    allocations = st.session_state.setdefault('chat_budget_allocations', {})
    spending = st.session_state.setdefault('chat_spending', [])
    unsaved_payments = st.session_state.setdefault('unsaved_payments', set())
    if chat and st.button('Start a new chat request'):
        chat.clear()
        st.session_state.pop('purchase_review_id', None)
        st.session_state.pop('chat_save_failed', None)
        st.session_state.pop('budget_update_pending', None)
        st.session_state.pop('spending_pending', None)

    history = st.container()
    with history:
        for message in chat:
            display_chat_message(message)

    prompt = st.chat_input('Describe a purchase, update a budget, or report a payment', max_chars=2000,
                           key='purchase_chat_input', disabled=not chat_enabled)
    if prompt and prompt.strip():
        prompt = prompt.strip()
        review_id = st.session_state.get('purchase_review_id')
        snapshot = saved_reviews.get(review_id)
        payment_command = PAYMENT_COMMAND.fullmatch(prompt)
        review = (snapshot or {}).get('review') or {}
        budget_action = budget_command(
            prompt, [row['category'] for row in budgets], st.session_state.get('budget_update_pending', False),
            reviewed_payment=bool(payment_command and review), pending_spending=st.session_state.get('spending_pending'),
        )
        if not budget_action or budget_action[0] in ('spend', 'spend_another'):
            st.session_state.pop('spending_pending', None)
        st.session_state['budget_update_pending'] = bool(budget_action and budget_action[0] == 'clarify')
        recorded_payment = review.get('payment')
        account_notice = bool(budget_action or payment_command or recorded_payment)
        message = {'role': 'user', 'text': prompt, 'account_notice': account_notice}
        chat.append(message)
        with history:
            display_chat_message(message)
            current_ledger = session_ledger(ledger, saved_reviews.values(), spending)
            current_budgets = session_budgets(budgets, allocations)
            if budget_action:
                try:
                    text, event = apply_budget_command(budget_action, current_budgets, current_ledger, allocations, spending)
                    if event and logging_enabled:
                        if 'budget_session_id' not in st.session_state:
                            st.session_state['budget_session_id'] = str(uuid4())
                        related_review_id = review_id if event['kind'] == 'budget_allocation_updated' else None
                        entry = {**event, 'session_id': st.session_state['budget_session_id'], 'review_id': related_review_id}
                        if not record_submission(supabase_url, supabase_key, entry):
                            st.session_state['budget_save_failed'] = True
                except SpendingDetailsNeeded as exc:
                    st.session_state['spending_pending'] = budget_action
                    text = str(exc)
                except ValueError as exc:
                    text = str(exc)
                reply = {'role': 'assistant', 'text': text, 'account_notice': True}
                chat.append(reply)
            elif account_notice:
                updated = None
                text = 'This purchase has a payment recorded. Use Start a new chat request for another purchase.'
                if payment_command:
                    try:
                        updated, text = confirm_payment(snapshot, payment_command[1], current_budgets, current_ledger)
                    except ValueError as exc:
                        text = str(exc)
                reply = {'role': 'assistant', 'text': text, 'account_notice': True}
                chat.append(reply)
                if updated is not None:
                    changed = updated is not snapshot
                    if changed:
                        updated['transcript'] = chat_transcript(chat)
                        saved_reviews[review_id] = updated
                    if logging_enabled and (changed or review_id in unsaved_payments):
                        if save_review(supabase_url, supabase_key, updated):
                            unsaved_payments.discard(review_id)
                        else:
                            unsaved_payments.add(review_id)
            else:
                if review_id is None:
                    review_id = st.session_state['purchase_review_id'] = str(uuid4())
                messages = [item for item in chat if not (item.get('account_notice') or item.get('payment_notice'))]
                if logging_enabled:
                    save_review(supabase_url, supabase_key, review_snapshot(review_id, messages))
                try:
                    with st.spinner('OpenAI is reviewing the request…'):
                        conversation = chat_transcript(item for item in messages if 'error' not in item)
                        result = review_chat(conversation, api_key, current_budgets, current_ledger, policies, date.today())
                    reply = build_reply(result, policies['escalation_authority'])
                except ChatReviewError as exc:
                    reply = {'role': 'assistant', 'text': str(exc), 'error': True}
                chat.append(reply)
                snapshot = review_snapshot(review_id, [*messages, reply])
                saved_reviews[review_id] = snapshot
                if logging_enabled:
                    st.session_state['chat_save_failed'] = not save_review(supabase_url, supabase_key, snapshot)
            display_chat_message(reply)

    if st.session_state.get('chat_save_failed'):
        st.warning('Could not confirm that the latest review was saved to Supabase.')
    if unsaved_payments:
        st.warning('A payment is recorded in this session but could not be confirmed in Supabase. '
                   'Repeat the same payment message in that request to retry the save.')
    if st.session_state.get('budget_save_failed'):
        st.warning('A budget change is recorded in this session. Its save to Supabase could not be confirmed.')

if saved_reviews:
    with st.expander('Review history for this session'):
        rows = []
        for snapshot in reversed(saved_reviews.values()):
            review = snapshot['review']
            request = review['result']['request'] if review else {}
            payment = (review or {}).get('payment')
            rows.append({
                'Purchase': request.get('description') or snapshot['transcript'][0]['text'],
                'Decision': snapshot['status'],
                'Paid in this session': f"${Decimal(payment['amount']):,.2f}" if payment else '',
                'Next action': ('Payment recorded.' if payment else
                                review['next_action'] if review else 'Retry chat or use Manual review.'),
            })
        st.dataframe(rows, hide_index=True, width='stretch')

budgets = session_budgets(budgets, allocations)
ledger = session_ledger(ledger, saved_reviews.values(), spending)
with st.expander('Budget records and spending rules'):
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
    st.caption(policies['label'])
    st.markdown(rf"- **Additional authorization** · Required for requests of \${policies['approval_threshold']:,.2f} or more.")
    st.markdown(f"- **Record verification** · Category records must have been verified within {policies['max_record_age_days']} days.")
    st.markdown(f"- **Urgent requests** · Requests due within {policies['urgent_within_days']} day(s) need prompt human review if information is missing or unresolved.")
    quote_requirement = 'Required' if policies['quote_required'] else 'Optional'
    st.markdown(f'- **Vendor quote or cost estimate** · {quote_requirement}.')
    st.markdown(f"- **Escalation contact** · {policies['escalation_authority']}")
    if policies['restricted_categories']:
        st.markdown('**Category restrictions**')
        for category, restriction in policies['restricted_categories'].items():
            st.markdown(f'- **{category}** · {restriction}')
    st.markdown('**Ledger including payments reported in this session**')
    st.dataframe([{**r, 'amount': str(r['amount'])} for r in ledger], hide_index=True)
    st.caption('Edit local files in data/ to configure the prototype. Verification dates mean the entire category ledger has been reconciled, including outstanding commitments.')

if not st.toggle('Manual review', value=not chat_enabled):
    st.stop()

st.subheader('Purchase request')
categories = [row['category'] for row in budgets]
today = date.today()
date_min, date_max = date(1900, 1, 1), date(2100, 12, 31)
fields = ('description', 'purpose', 'amount', 'category', 'deadline', 'vendor', 'quote', 'comments')


def fill_request(values):
    for field in fields:
        st.session_state[field] = values.get(field) or (None if field in ('deadline', 'category') else '')
    st.session_state.pop('review', None)


sample = dict(description='Van rental', purpose='Transportation to a student organization event',
              amount='450.00', category='Travel' if 'Travel' in categories else None,
              deadline=today + timedelta(days=1), vendor='Example Van Rentals',
              quote='Estimated rental cost: $450')
st.button('Try a sample request', on_click=fill_request, args=(sample,))

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
    if logging_enabled:
        st.caption('Submitting saves your form entries in the project database. Use fictional details only.')
    submitted = st.form_submit_button('Review purchase', type='primary')

if submitted:
    if logging_enabled:
        inputs = {field: st.session_state[field] for field in fields}
        inputs['deadline'] = deadline.isoformat() if deadline else None
        if record_submission(supabase_url, supabase_key, inputs):
            st.caption('Submission saved.')
        else:
            st.warning('Could not confirm that this submission was saved. The review can still run.')

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
    if not category:
        category_feedback.error('Select a spending category.')
    if not amount.strip():
        amount_feedback.error('Enter the requested amount.')
    if not category or not amount.strip():
        st.stop()
    try:
        result = evaluate(PurchaseRequest(description, purpose, amount, category, deadline, vendor, quote, comments), budgets, ledger, policies)
        st.session_state['review'] = result
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
