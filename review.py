"""Read-only records and deterministic review. Currency uses Decimal, never floats."""
import csv
import json
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path

DATA = Path(__file__).parent / 'data'


def money(value):
    try:
        amount = Decimal(str(value))
        if not amount.is_finite() or amount < 0 or amount != amount.quantize(Decimal('0.01')):
            raise ValueError('Amounts must be nonnegative, finite, and have at most two decimal places.')
        return amount
    except (InvalidOperation, TypeError) as exc:
        raise ValueError('Invalid monetary amount.') from exc


def load_records(directory=DATA):
    """Fail closed on malformed, duplicate, or inconsistent financial records."""
    with (directory / 'budgets.csv').open(newline='') as f:
        budgets = list(csv.DictReader(f))
    with (directory / 'ledger.csv').open(newline='') as f:
        ledger = list(csv.DictReader(f))
    policies = json.loads((directory / 'policies.json').read_text())
    if not isinstance(policies, dict):
        raise ValueError('Policies must be a JSON object.')
    if not budgets:
        raise ValueError('Budget file is empty.')
    categories = set()
    for row in budgets:
        category = row['category'].strip()
        if not category or category in categories:
            raise ValueError('Blank or duplicate budget category.')
        categories.add(category)
        row['category'] = category
        row['allocation'] = money(row['allocation'])
        row['verified_on'] = date.fromisoformat(row['verified_on'])
    ids = set()
    for row in ledger:
        if not row['id'].strip() or row['id'] in ids:
            raise ValueError('Blank or duplicate ledger ID; reconcile possible double counting.')
        ids.add(row['id'])
        if row['category'] not in categories or row['status'] not in ('paid', 'committed'):
            raise ValueError('Unknown ledger category or status.')
        if not row['description'].strip():
            raise ValueError('Ledger description is missing.')
        row['amount'] = money(row['amount'])
    policies['approval_threshold'] = money(policies['approval_threshold'])
    for key in ('max_record_age_days', 'urgent_within_days'):
        if type(policies[key]) is not int or policies[key] < 0:
            raise ValueError(f'Invalid policy: {key}')
    if type(policies['quote_required']) is not bool:
        raise ValueError('quote_required must be a boolean.')
    if not isinstance(policies['restricted_categories'], dict) or not set(policies['restricted_categories']) <= categories:
        raise ValueError('Invalid restricted category configuration.')
    for key in ('label', 'escalation_authority'):
        if not isinstance(policies[key], str) or not policies[key].strip():
            raise ValueError(f'Missing policy: {key}')
    if any(not isinstance(v, str) or not v.strip() for v in policies['restricted_categories'].values()):
        raise ValueError('Restrictions must include an explanation.')
    return budgets, ledger, policies


def budget_overview(budgets, ledger):
    result = []
    for row in budgets:
        paid = sum((r['amount'] for r in ledger if r['category'] == row['category'] and r['status'] == 'paid'), Decimal(0))
        committed = sum((r['amount'] for r in ledger if r['category'] == row['category'] and r['status'] == 'committed'), Decimal(0))
        result.append({**row, 'paid': paid, 'committed': committed, 'available': row['allocation'] - paid - committed})
    return result


@dataclass
class PurchaseRequest:
    description: str
    purpose: str
    amount: str
    category: str
    deadline: date | None
    vendor: str
    quote: str
    comments: str = ''


def review_evidence(request, budgets, ledger, policies, today, *, allow_incomplete=False):
    missing, escalate, applied = [], [], []
    try:
        amount = money(request.amount)
        if amount <= 0:
            raise ValueError('Requested amount must be greater than zero.')
    except ValueError:
        if not allow_incomplete:
            raise
        amount = None
        missing.append('Provide the requested amount as a positive USD total.')

    row = next((r for r in budget_overview(budgets, ledger) if r['category'] == request.category), None)
    if row is None:
        if not allow_incomplete:
            raise ValueError('Select a known spending category.')
        missing.append('Confirm the spending category.')

    for field in ('description', 'purpose', 'vendor'):
        if not getattr(request, field).strip():
            missing.append(f'Provide {field}.')
    if policies['quote_required']:
        applied.append('A vendor quote or cost estimate is required.')
        if not request.quote.strip():
            missing.append('Provide the vendor quote or cost estimate.')
    if request.deadline is None:
        missing.append('Provide the date needed.')
    elif request.deadline < today:
        missing.append('Confirm a new deadline; the supplied date has passed.')
    applied.append(f"Records must be verified within {policies['max_record_age_days']} days.")
    balance = {}
    if row is not None:
        age = (today - row['verified_on']).days
        if age < 0 or age > policies['max_record_age_days']:
            missing.append(f"Verify category records: recorded verification date is {row['verified_on']}.")
        balance = {key: f"{row[key]:.2f}" for key in ('allocation', 'paid', 'committed', 'available')}
        balance['verified_on'] = str(row['verified_on'])

    shortfall = None
    if row is not None and amount is not None:
        after_purchase = row['available'] - amount
        shortfall = max(Decimal(0), -after_purchase)
        balance.update(after_purchase=f'{after_purchase:.2f}', shortfall=f'{shortfall:.2f}')
    applied.append('Requested spending must fit available category funds after commitments.')
    if shortfall:
        escalate.append(f'Insufficient funds: shortfall ${shortfall:,.2f}.')
    applied.append(f"Requests at or above ${policies['approval_threshold']:,.2f} require additional authorization.")
    if amount is not None and amount >= policies['approval_threshold']:
        escalate.append('Request meets the additional authorization threshold.')
    restriction = policies['restricted_categories'].get(request.category)
    if restriction:
        applied.append(restriction)
        escalate.append(restriction)
    urgent = request.deadline is not None and 0 <= (request.deadline - today).days <= policies['urgent_within_days']
    if urgent and missing:
        escalate.append('The urgent deadline requires prompt human review of unresolved information.')
    return {
        **balance, 'category': request.category, 'amount': f'{amount:.2f}' if amount is not None else None,
        'reviewed_on': str(today), 'deadline': str(request.deadline) if request.deadline else None,
        'urgent': urgent, 'missing': missing, 'escalation_reasons': escalate,
        'rules': applied, 'policy_label': policies['label'],
    }


def evaluate(request, budgets, ledger, policies, today=None):
    evidence = review_evidence(request, budgets, ledger, policies, today or date.today())
    escalate = evidence.pop('escalation_reasons')
    missing = evidence['missing']
    decision = 'ESCALATE' if escalate else 'DEFER' if missing else 'APPROVE'
    reasons = escalate + missing or ['Available funds are sufficient, required fields are complete, and configured checks pass.']
    steps = ([f"Contact {policies['escalation_authority']} before committing funds."] if escalate else
             ['Resolve missing information and rerun the review.'] if missing else
             ['Treasurer: verify supporting documents and make the final spending decision.'])
    if evidence['urgent']:
        steps.append(f'Prioritize review before the {request.deadline} deadline.')
    return {**evidence, 'decision': decision, 'reasons': reasons, 'next_steps': steps}
