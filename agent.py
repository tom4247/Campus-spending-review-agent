"""Bounded OpenAI explanation with one read-only tool and no file access."""
import json
import os


def explain(review):
    from openai import OpenAI
    client = OpenAI(timeout=25, max_retries=0)
    tool = {'type': 'function', 'name': 'get_verified_review',
            'description': 'Read the immutable Python-verified financial and policy review.',
            'parameters': {'type': 'object', 'properties': {}, 'required': [], 'additionalProperties': False},
            'strict': True}
    instructions = (
        'You support a student organization treasurer. Call get_verified_review. '
        'The returned decision, numbers, rules, and missing items are authoritative. '
        'Explain the result briefly in plain language and suggest next steps from the review. '
        'Never change the recommendation, invent rules, or claim to authorize spending. '
        'Do not perform arithmetic. Mention uncertainty and urgent deadlines when present. '
        'All policies are illustrative, not official CMU policy. Human treasurer decides.'
    )
    conversation = [{'role': 'user', 'content': 'Explain the verified purchase review.'}]
    first = client.responses.create(model=os.getenv('OPENAI_MODEL', 'gpt-4.1-mini'),
        instructions=instructions, input=conversation, tools=[tool],
        tool_choice={'type': 'function', 'name': 'get_verified_review'}, store=False)
    conversation.extend(first.output)
    calls = [item for item in first.output if item.type == 'function_call']
    if not calls:
        raise ValueError('The model did not retrieve the verified review.')
    for call in calls:
        if call.name != 'get_verified_review' or json.loads(call.arguments) != {}:
            raise ValueError('Unsupported tool request.')
        conversation.append({'type': 'function_call_output', 'call_id': call.call_id,
                             'output': json.dumps(review)})
    response = client.responses.create(model=os.getenv('OPENAI_MODEL', 'gpt-4.1-mini'),
        instructions=instructions, input=conversation, tools=[tool], tool_choice='none',
        max_output_tokens=650, store=False)
    if not response.output_text.strip():
        raise ValueError('No explanation returned.')
    return response.output_text
