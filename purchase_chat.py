"""Decision handoffs and snapshots for one chat purchase."""
from datetime import datetime, timezone
import re
from uuid import uuid4

from review import budget_overview, money


PAYMENT_COMMAND = re.compile(r'(?:record paid|confirm payment of|(?:i|we) (?:already )?paid)\b\s*(.*)', re.IGNORECASE)
USD_NUMBER = r'(?:[0-9]{1,3}(?:,[0-9]{3})+|[0-9]+)(?:\.[0-9]{1,2})?'
USD = rf'\$?{USD_NUMBER}'
USD_AMOUNT = re.compile(USD)
BUDGET_SET = re.compile(r'(?:set|update|change) (?:the |our |my )?(.+?) (?:budget|allocation) to (.+)', re.IGNORECASE)
BUDGET_ADD = re.compile(r'add (.+?) to (?:the |our |my )?(.+?) (?:budget|allocation)', re.IGNORECASE)
SPENDING_REPORT = re.compile(
    rf'(?:(?:i|we) (?:already )?)?(?:spent|paid) (?:(another) )?(?:the |hte )?({USD}) '
    r'(on|in|from|for) (?:the )?(.+?)(?: budget| category)?',
    re.IGNORECASE,
)
BUDGET_UPDATE_SUFFIX = re.compile(
    r'(?:\s*[,;.]\s*|\s+(?:and|to)\s+)(?:please )?(?:update|adjust) (?:the |my |our )?budget$',
    re.IGNORECASE,
)
COMPLETED_EXPENSE = re.compile(
    r'\b(?:i|we) (?:already |just )?(?:spent|paid|bought|purchased|rented|picked up|got it|received it)\b'
    r'|\b(?:log|record)\b[^.!?]*\b(?:spent|spending|expense|already paid)\b',
    re.IGNORECASE,
)
EXPENSE_AMOUNTS = re.compile(
    rf'(?<![-\w])\$\s*({USD_NUMBER})(?![0-9]|[.,][0-9])|(?<![-\w.,$])({USD_NUMBER})\s+(?:usd|dollars?)\b',
    re.IGNORECASE,
)
CATEGORY_HINTS = {
    'travel': r'\b(?:zip[ -]?car|van|shuttle|bus|train|flight|car rental|transportation)\b',
    'events': r'\b(?:food|meals?|catering|venue|refreshments|pizza|snacks|groceries|party supplies)\b',
    'marketing': r'\b(?:posters?|flyers?|banner|advertising)\b',
    'equipment': r'\b(?:projector|microphone|camera|laptop)\b',
}


class SpendingDetailsNeeded(ValueError):
    """A reported expense needs an amount or category to be entered."""


def build_reply(result, escalation_authority):
    decision = result['decision']
    if decision == 'APPROVE':
        action = 'Verify the supporting details and authorize the expense through your treasurer process.'
    elif decision == 'DEFER':
        market = result['evidence'].get('market_price', {})
        if any(item.startswith('Verify category records') for item in result['evidence']['missing']):
            action = 'Reconcile the budget records before relying on this review. Reply with other missing details.'
        elif market.get('status') == 'unavailable':
            action = 'Retry when live price search is available, or ask the treasurer to compare provider quotes.'
        elif market.get('status') == 'insufficient_sources':
            action = ('See the provider pages under Market price check for exact pricing and availability.'
                      if market.get('options') else 'Retry the search or ask the treasurer to review the existing quote.')
        elif market.get('status') == 'benchmark' and result['evidence']['missing'] == [market['summary']]:
            action = 'Confirm the terms and all-in price before committing funds.'
        else:
            action = 'Reply with the requested details to continue this review.'
    else:
        action = f'Share the escalation summary with {escalation_authority} before committing funds.'
    text = result['reason']
    if result['follow_up']:
        text += f"\n\n{result['follow_up']}"
    return {'role': 'assistant', 'text': text, 'result': result, 'next_action': action}


def escalation_summary(reply):
    result = reply['result']
    request = result['request']
    evidence = result['evidence']
    lines = ['Expense review · ESCALATE', f"Purchase: {request['description'] or 'Unspecified'}"]
    for label, field in (('Requested', 'amount'), ('Available', 'available'), ('Shortfall', 'shortfall')):
        if evidence.get(field) is not None:
            lines.append(f'{label}: ${evidence[field]}')
    for label, field in (('Category', 'category'), ('Needed by', 'deadline'), ('Vendor', 'vendor')):
        if request.get(field):
            lines.append(f'{label}: {request[field]}')
    lines.append(f"Reason: {result['reason']}")
    if evidence['escalation_reasons']:
        lines.append('Verified policy triggers: ' + ' '.join(evidence['escalation_reasons']))
    if evidence['missing']:
        lines.append('Unresolved details: ' + ' '.join(evidence['missing']))
    lines.append(f"Next action: {reply['next_action']}")
    return '\n'.join(lines)


def review_snapshot(review_id, chat):
    latest = chat[-1]
    result = latest.get('result')
    snapshot = None
    if result:
        snapshot = {'result': result, 'next_action': latest['next_action']}
        if result['decision'] == 'ESCALATE':
            snapshot['handoff'] = escalation_summary(latest)
    return {
        'id': review_id,
        'updated_at': datetime.now(timezone.utc).isoformat(),
        'status': result['decision'] if result else 'UNAVAILABLE' if 'error' in latest else 'PENDING',
        'transcript': chat_transcript(chat),
        'review': snapshot,
    }


def chat_transcript(chat):
    return [{'role': message['role'], 'text': message['text']} for message in chat]


def session_ledger(ledger, snapshots, spending):
    payments = []
    for snapshot in snapshots:
        payment = (snapshot['review'] or {}).get('payment')
        if payment:
            payments.append({
                'id': f"payment-{snapshot['id']}", 'category': payment['category'],
                'description': payment['description'], 'amount': money(payment['amount']), 'status': 'paid',
            })
    return [*ledger, *payments, *spending]


def session_budgets(budgets, allocations):
    return [{**row, 'allocation': allocations.get(row['category'], row['allocation'])} for row in budgets]


def expense_category(text, categories, *, short_reply=False):
    match = re.fullmatch if short_reply else re.search
    exact = [name for name in categories if match(rf'(?<!\w){re.escape(name)}(?!\w)', text, re.IGNORECASE)]
    if exact:
        return exact[0] if len(exact) == 1 else ''
    inferred = [
        name for name in categories
        if (hint := CATEGORY_HINTS.get(name.casefold())) and match(hint, text, re.IGNORECASE)
    ]
    return inferred[0] if len(inferred) == 1 else ''


def spending_command(text, categories, reviewed_payment):
    bookkeeping_request = BUDGET_UPDATE_SUFFIX.search(text)
    report = text[:bookkeeping_request.start()].rstrip() if bookkeeping_request else text
    if match := SPENDING_REPORT.fullmatch(report):
        another, amount, preposition, category = match.groups()
        category_reply = expense_category(category, categories, short_reply=True)
        if not reviewed_payment or preposition.casefold() != 'for' or bookkeeping_request or category_reply:
            category = expense_category(category, categories) or category
            return 'spend_another' if another else 'spend', category, amount

    if (reviewed_payment and not bookkeeping_request) or re.search(
        r'\b(?:if (?:i|we)|hypothetically|planning to|considering|should (?:i|we))\b', text, re.IGNORECASE,
    ):
        return None
    if not COMPLETED_EXPENSE.search(text):
        return None

    category = expense_category(text, categories)
    if not category and PAYMENT_COMMAND.fullmatch(text):
        return None
    try:
        amounts = {money((prefixed or suffixed).replace(',', ''))
                   for prefixed, suffixed in EXPENSE_AMOUNTS.findall(text)}
    except ValueError:
        amounts = set()
    amount = f'{amounts.pop():f}' if len(amounts) == 1 else ''
    return 'spend', category, amount


def spending_follow_up(text, categories, pending):
    action, category, amount = pending
    reply = re.sub(r'^(?:use |charge (?:it )?to |(?:it was )?for |category is )(?:the )?', '', text, flags=re.IGNORECASE)
    if updated_category := expense_category(reply, categories, short_reply=True):
        return action, updated_category, amount
    if match := re.fullmatch(rf'(?:(?:it was|the total was) )?({USD})(?: dollars| usd)?', text, re.IGNORECASE):
        return action, category, match[1]
    return None


def budget_command(prompt, categories, awaiting_details=False, *, reviewed_payment=False, pending_spending=None):
    text = re.sub(r'^(?:can you |could you |please )+', '', prompt.rstrip(' .!?'), flags=re.IGNORECASE)
    if action := spending_command(text, categories, reviewed_payment):
        return action
    if match := BUDGET_SET.fullmatch(text):
        return 'set', *match.groups()
    if match := BUDGET_ADD.fullmatch(text):
        amount, category = match.groups()
        return 'add', category, amount
    if re.fullmatch(
        r'(?:show (?:me )?|what is |what[’\x27]s )?(?:the |our |my )?(?:session )?budget(?: balance)?',
        text, re.IGNORECASE,
    ):
        return 'show', '', ''
    if re.fullmatch(
        r'(?:update|change|set) (?:the |our |my )?(?:.+? )?(?:budget|allocation)(?: to .+)?', text, re.IGNORECASE,
    ):
        return 'clarify', '', ''
    if awaiting_details and (match := re.fullmatch(rf'(.+?) (?:to )?({USD})', text, re.IGNORECASE)):
        return 'set', *match.groups()
    if pending_spending:
        return spending_follow_up(text, categories, pending_spending)
    return None


def apply_budget_command(command, current_budgets, ledger, allocations, spending):
    action, category_name, amount_text = command
    overview = budget_overview(current_budgets, ledger)
    if action == 'show':
        return '\n'.join(f"{row['category']}: ${row['available']:,.2f} available" for row in overview), None
    if action == 'clarify':
        raise ValueError('Which category and total allocation should I use? For example, “Update the Travel budget to $2,300”.')
    is_spending = action in ('spend', 'spend_another')
    if is_spending and not amount_text:
        raise SpendingDetailsNeeded('What was the total amount you paid?')
    details_error = SpendingDetailsNeeded if is_spending else ValueError
    row = next((item for item in overview if item['category'].casefold() == category_name.casefold()), None)
    if row is None:
        categories = ', '.join(item['category'] for item in overview)
        raise details_error(f'Choose a budget category: {categories}.')
    if not USD_AMOUNT.fullmatch(amount_text):
        raise details_error('Enter the amount in USD, for example $300.00.')
    amount = money(amount_text.removeprefix('$').replace(',', ''))
    if is_spending:
        return record_spending(row, amount, spending, another=action == 'spend_another')

    previous = row['allocation']
    allocation = money(previous + amount) if action == 'add' else amount
    category = row['category']
    available = row['available'] + allocation - previous
    response = f'{category} allocation is ${allocation:,.2f}. Available in this session: ${available:,.2f}.'
    if allocation == previous:
        return response, None

    allocations[category] = allocation
    return response, {
        'kind': 'budget_allocation_updated', 'category': category, 'previous_allocation': f'{previous:.2f}',
        'allocation': f'{allocation:.2f}', 'available_after': f'{available:.2f}',
    }


def record_spending(row, amount, spending, *, another):
    if amount <= 0:
        raise SpendingDetailsNeeded('Enter an expense amount greater than zero.')

    category = row['category']
    if not another and any(entry['category'] == category and entry['amount'] == amount for entry in spending):
        return (f'${amount:,.2f} is already recorded as spent on {category}. '
                f'For a separate expense, type “We spent another ${amount:,.2f} on {category}”.'), None

    expense_id = f'expense-{uuid4()}'
    available = row['available'] - amount
    spending.append({
        'id': expense_id, 'category': category, 'description': 'Expense reported in chat',
        'amount': amount, 'status': 'paid',
    })
    event = {'kind': 'spending_reported', 'expense_id': expense_id, 'category': category,
             'amount': f'{amount:.2f}', 'available_after': f'{available:.2f}'}
    return f'Recorded ${amount:,.2f} spent on {category}. Available in this session: ${available:,.2f}.', event


def confirm_payment(snapshot, amount_text, budgets, ledger):
    """Record the reported amount once against the current purchase review."""
    amount_text = amount_text.strip().rstrip('.!')
    reference = None
    if match := re.fullmatch(rf'({USD}) for (?:the |a |an )?(.+)', amount_text, re.IGNORECASE):
        amount_text, reference = match.groups()
    elif match := re.fullmatch(rf'for (?:the |a |an )?({USD}) (.+)', amount_text, re.IGNORECASE):
        amount_text, reference = match.groups()
    if not USD_AMOUNT.fullmatch(amount_text):
        raise ValueError('Enter the total you paid in USD, for example “I paid $125.50”.')
    amount = money(amount_text.removeprefix('$').replace(',', ''))
    if amount <= 0:
        raise ValueError('Enter a payment amount greater than zero.')
    if not snapshot or not snapshot['review']:
        raise ValueError('Review a purchase with a spending category before recording payment.')

    review = snapshot['review']
    request = review['result']['request']
    description = request.get('description') or 'Chat purchase'
    if reference:
        named_words = set(re.findall(r'\w+', reference.casefold())) - {'this', 'that', 'the', 'purchase', 'request', 'it'}
        description_words = set(re.findall(r'\w+', description.casefold()))
        if not named_words <= description_words:
            raise ValueError(f'The current review is “{description}”. Open the matching request, or type “I paid ${amount:,.2f}” if you mean this purchase.')
    previous = review.get('payment')
    if previous:
        if amount == money(previous['amount']):
            return snapshot, f'This purchase already has a ${amount:,.2f} payment recorded.'
        raise ValueError(f"This purchase already has a ${money(previous['amount']):,.2f} payment recorded.")

    category = request.get('category')
    row = next((item for item in budget_overview(budgets, ledger) if item['category'] == category), None)
    if row is None:
        raise ValueError('Confirm the spending category in the purchase review before recording payment.')

    available = row['available'] - amount
    recorded_at = datetime.now(timezone.utc).isoformat()
    payment = {
        'amount': f'{amount:.2f}', 'category': category,
        'description': description,
        'reported_at': recorded_at, 'available_after': f'{available:.2f}',
    }
    updated = {**snapshot, 'updated_at': recorded_at, 'review': {**review, 'payment': payment}}
    return updated, f'Recorded ${amount:,.2f} paid from {category}. Available in this session: ${available:,.2f}.'
