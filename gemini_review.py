"""Gemini interprets chat requests and chooses a recommendation from verified evidence."""
import json
import logging
import os
import re

import httpx

from chat_review import ChatReviewError as GeminiReviewError, review_with_model

DEFAULT_MODEL = 'gemini-3.8-flash'


def _gemini_error(response, model, phase):
    try:
        error = response.json()['error']
        codes = [error.get('status', '')]
        codes.extend(detail.get('reason', '') for detail in error.get('details', []))
        provider_message = error.get('message', '').lower()
    except (KeyError, AttributeError, TypeError, ValueError):
        codes, provider_message = [], ''

    status = response.status_code
    diagnostic = f'HTTP {status}'
    safe_codes = [code for code in codes if isinstance(code, str) and re.fullmatch(r'[A-Z_]{3,64}', code)]
    if safe_codes:
        diagnostic += ' · ' + ', '.join(safe_codes)
    logging.warning('Gemini %s failed for %s (%s).', phase, model, diagnostic)

    if 'API_KEY_INVALID' in codes or 'API_KEY_EXPIRED' in codes or 'api key not valid' in provider_message:
        message = 'Google rejected the Gemini API key. Replace GEMINI_API_KEY in Streamlit Secrets with a valid Google AI Studio key.'
    elif status == 402 or 'FAILED_PRECONDITION' in codes:
        message = 'Google requires a project setup step. Check the Gemini project’s status and billing in Google AI Studio.'
    elif status in (401, 403):
        message = 'Google denied access. Check the Gemini API key’s restrictions and project status in Google AI Studio.'
    elif status == 404:
        message = 'This Gemini model is unavailable to the app. Check GEMINI_MODEL in Streamlit Secrets.'
    elif status == 429:
        message = 'Gemini reached its usage limit. Try again later or check your project quota.'
    elif status == 400:
        message = 'Gemini rejected the request format. Share this diagnostic so the app owner can investigate.'
    else:
        message = 'Gemini could not run this review. Try again or contact the treasurer.'
    return GeminiReviewError(f'{message} ({phase}, {diagnostic})')


def _structured_response(client, model, instruction, data, properties):
    try:
        response = client.post(
            f'https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent',
            json={
                'systemInstruction': {'parts': [{'text': instruction}]},
                'contents': [{'role': 'user', 'parts': [{'text': json.dumps(data)}]}],
                'generationConfig': {
                    'responseMimeType': 'application/json',
                    'responseJsonSchema': {
                        'type': 'object', 'properties': properties, 'required': list(properties),
                        'additionalProperties': False,
                    },
                    'maxOutputTokens': 2048,
                },
            },
        )
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        phase = 'request extraction' if 'description' in properties else 'review decision'
        raise _gemini_error(exc.response, model, phase) from exc
    except httpx.RequestError as exc:
        raise GeminiReviewError('Gemini could not be reached. Try again or contact the treasurer.') from exc

    try:
        candidate = response.json()['candidates'][0]
        if candidate.get('finishReason') != 'STOP':
            raise ValueError('Gemini did not finish the structured response.')
        parts = candidate['content']['parts']
        data = json.loads(''.join(part.get('text', '') for part in parts if not part.get('thought')))
        if not isinstance(data, dict) or data.keys() != properties.keys():
            raise ValueError('Unexpected Gemini response fields.')
        return data
    except (KeyError, IndexError, TypeError, AttributeError, ValueError) as exc:
        raise GeminiReviewError('Gemini returned an incomplete review. Try again or contact the treasurer.') from exc


def review_chat(messages, api_key, budgets, ledger, policies, today):
    model = os.getenv('GEMINI_MODEL') or DEFAULT_MODEL
    if not re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9_.-]*', model):
        raise GeminiReviewError('The configured GEMINI_MODEL is invalid.')

    with httpx.Client(headers={'x-goog-api-key': api_key.strip()}, timeout=20) as client:
        def generate(instruction, data, properties):
            return _structured_response(client, model, instruction, data, properties)

        return review_with_model(messages, budgets, ledger, policies, today, generate)
