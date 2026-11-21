"""Decision handoffs and snapshots for one chat purchase."""
from datetime import datetime, timezone


def build_reply(result, escalation_authority):
    decision = result['decision']
    if decision == 'APPROVE':
        action = 'Verify the supporting details and authorize the expense through your treasurer process.'
    elif decision == 'DEFER':
        if any(item.startswith('Verify category records') for item in result['evidence']['missing']):
            action = 'Reconcile the budget records before relying on this review. Reply with other missing details.'
        else:
            action = 'Reply with the details Gemini asked for to continue this review.'
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
        'transcript': [{'role': message['role'], 'text': message['text']} for message in chat],
        'review': snapshot,
    }
