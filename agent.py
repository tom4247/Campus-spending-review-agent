"""OpenAI purchase chat and legacy draft and explanation helpers."""
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


def draft_request(description, categories, today):
    from openai import OpenAI

    fields = ('description', 'purpose', 'amount', 'category', 'deadline', 'vendor', 'quote')
    properties = {field: {'type': ['string', 'null']} for field in fields}
    properties['category']['enum'] = [*categories, None]
    response = OpenAI(timeout=25, max_retries=0).responses.create(
        model=os.getenv('OPENAI_MODEL', 'gpt-4.1-mini'),
        instructions=(
            f'Today is {today}. Extract purchase request details for the user to confirm. '
            'Use null for missing or ambiguous details. Never invent a vendor or quote. '
            'Suggest a category only if clearly supported, and use only allowed categories. '
            'Use a decimal string without currency symbols for amount and YYYY-MM-DD for deadline. '
            'Resolve relative dates only when unambiguous.'
        ),
        input=description,
        text={'format': {'type': 'json_schema', 'name': 'purchase_request', 'strict': True,
                         'schema': {'type': 'object', 'properties': properties,
                                    'required': list(fields), 'additionalProperties': False}}},
        max_output_tokens=500,
        store=False,
    )
    return json.loads(response.output_text)


def review_chat(messages, api_key, budgets, ledger, policies, today):
    """Run the chat review using OpenAI's low-cost structured output model."""
    from openai import APIConnectionError, APIStatusError, OpenAI
    from chat_review import ChatReviewError, review_with_model

    default_model = 'gpt-6-luna'
    model = os.getenv('OPENAI_CHAT_MODEL') or default_model
    reasoning = {'reasoning': {'effort': 'none'}} if model == default_model else {}

    with OpenAI(api_key=api_key.strip(), timeout=20, max_retries=0) as client:
        def generate(instruction, data, properties):
            try:
                response = client.responses.create(
                    model=model, instructions=instruction, input=json.dumps(data),
                    text={'format': {
                        'type': 'json_schema', 'name': 'purchase_review', 'strict': True,
                        'schema': {'type': 'object', 'properties': properties,
                                   'required': list(properties), 'additionalProperties': False},
                    }},
                    max_output_tokens=512, store=False, **reasoning,
                )
            except APIConnectionError as exc:
                raise ChatReviewError('OpenAI could not be reached. Try again or use Manual review.') from exc
            except APIStatusError as exc:
                status = exc.status_code
                if exc.code in ('insufficient_quota', 'billing_hard_limit_reached') or status == 402:
                    message = 'OpenAI has no available API credits or has reached its spending limit. Check API billing.'
                elif status in (401, 403):
                    message = 'OpenAI denied access. Check the API key and project permissions in Streamlit Secrets.'
                elif status == 404:
                    message = 'The OpenAI model is unavailable to this project. Check OPENAI_CHAT_MODEL.'
                elif status == 429:
                    message = 'OpenAI is at its usage limit. Try again later or use Manual review.'
                else:
                    message = 'OpenAI could not complete the review. Try again or use Manual review.'
                raise ChatReviewError(f'{message} (HTTP {status})') from exc

            try:
                if response.status != 'completed':
                    raise ValueError('Incomplete OpenAI response.')
                decoded = json.loads(response.output_text)
                if not isinstance(decoded, dict) or decoded.keys() != properties.keys():
                    raise ValueError('Unexpected OpenAI response fields.')
                return decoded
            except (TypeError, ValueError) as exc:
                raise ChatReviewError('OpenAI returned an incomplete review. Try again or use Manual review.') from exc

        return review_with_model(messages, budgets, ledger, policies, today, generate)
