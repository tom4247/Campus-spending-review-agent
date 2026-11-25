import json
import os
import unittest
from datetime import date
from types import SimpleNamespace
from unittest.mock import patch

from openai import RateLimitError

from agent import review_chat
from chat_review import ChatReviewError
from review import load_records


def price_response(totals, scope, *, missing_details='', unusable_last=False):
    prices = [
        {'provider': provider, 'total_usd': total, 'url': f'https://{provider}.example/price',
         'terms': scope, 'price_type': 'total', 'location': 'Pittsburgh', 'availability': 'confirmed'}
        for provider, total in zip(('first', 'second', 'third'), totals)
    ]
    sourced = prices[:-1] if unusable_last else prices
    web_search = SimpleNamespace(type='web_search_call', action=SimpleNamespace(
        sources=[SimpleNamespace(url=price['url']) for price in sourced],
    ))
    return SimpleNamespace(
        status='completed', output=[web_search],
        output_text=json.dumps({'scope': scope, 'missing_details': missing_details, 'prices': prices}),
    )


class OpenAIChatTests(unittest.TestCase):
    def test_billing_and_spend_limits_are_identified_without_retry(self):
        for code, kind, expected in (
            ('credit_balance_exhausted', 'insufficient_quota', 'no prepaid credits left'),
            ('project_spend_limit_exceeded', 'insufficient_quota', 'project reached its spending limit'),
            (None, 'insufficient_quota', 'no available API credits'),
        ):
            with self.subTest(code=code), patch('openai.OpenAI') as client, patch('agent.sleep') as sleep:
                create = client.return_value.__enter__.return_value.responses.create
                response = SimpleNamespace(status_code=429, request=object(), headers={'retry-after': '1'})
                create.side_effect = RateLimitError('private provider details', response=response,
                                                    body={'code': code, 'type': kind})
                with self.assertRaisesRegex(ChatReviewError, expected) as error:
                    review_chat([], 'mock-key', *load_records(), date(2026, 11, 17))
                self.assertNotIn('private provider details', str(error.exception))
                if code:
                    self.assertIn(code, str(error.exception))
                create.assert_called_once()
                sleep.assert_not_called()

    def test_temporary_rate_limit_retries_once_when_the_wait_is_short(self):
        with patch('openai.OpenAI') as client, patch('agent.sleep') as sleep:
            create = client.return_value.__enter__.return_value.responses.create
            response = SimpleNamespace(status_code=429, request=object(), headers={'retry-after': '2'})
            create.side_effect = RateLimitError('temporary limit', response=response,
                                                body={'code': 'slow_down', 'type': 'rate_limit_error'})
            with self.assertRaisesRegex(ChatReviewError, 'temporarily limited the request rate'):
                review_chat([], 'mock-key', *load_records(), date(2026, 11, 17))
            self.assertEqual(create.call_count, 2)
            sleep.assert_called_once_with(2)

    def test_luna_uses_verified_evidence_and_can_escalate(self):
        fields = {
            'description': 'Van rental', 'purpose': 'Competition', 'amount': '450.00',
            'category': 'Travel', 'deadline': '2026-11-24', 'vendor': 'Example Vans', 'quote': '$450',
        }
        decision = {'decision': 'ESCALATE', 'reason': 'Travel is $150 short.', 'follow_up': ''}
        messages = [{'role': 'user', 'text': 'Example Vans quoted $450 for competition travel November 24.'}]

        with patch.dict(os.environ, {'OPENAI_CHAT_MODEL': ''}), patch('openai.OpenAI') as client:
            create = client.return_value.__enter__.return_value.responses.create
            create.side_effect = [
                SimpleNamespace(status='completed', output_text=json.dumps(reply))
                for reply in (fields, decision)
            ]
            result = review_chat(messages, 'mock-key', *load_records(), date(2026, 11, 17))
            self.assertEqual(result['decision'], 'ESCALATE')
            self.assertEqual(result['evidence']['shortfall'], '150.00')
            self.assertEqual(create.call_count, 2)
            for call in create.call_args_list:
                self.assertEqual(call.kwargs['model'], 'gpt-6-luna')
                self.assertEqual(call.kwargs['reasoning'], {'effort': 'none'})
                self.assertLessEqual(call.kwargs['max_output_tokens'], 512)
                self.assertTrue(call.kwargs['text']['format']['strict'])
                self.assertFalse(call.kwargs['store'])
            payload = json.loads(create.call_args.kwargs['input'])
            self.assertEqual(payload['allowed_outcomes'], ['ESCALATE'])
            self.assertEqual(payload['verified_evidence']['available'], '300.00')

    def test_incomplete_openai_response_stops_before_decision(self):
        with patch('openai.OpenAI') as client:
            create = client.return_value.__enter__.return_value.responses.create
            create.return_value = SimpleNamespace(status='incomplete', output_text='')
            with self.assertRaisesRegex(ChatReviewError, 'incomplete review'):
                review_chat([], 'mock-key', *load_records(), date(2026, 11, 17))
            create.assert_called_once()

    def test_openai_cannot_approve_a_verified_shortfall(self):
        fields = {
            'description': 'Van rental', 'purpose': 'Competition', 'amount': '450.00',
            'category': 'Travel', 'deadline': '2026-11-24', 'vendor': 'Example Vans', 'quote': '$450',
        }
        with patch('openai.OpenAI') as client:
            create = client.return_value.__enter__.return_value.responses.create
            create.side_effect = [
                SimpleNamespace(status='completed', output_text=json.dumps(fields)),
                SimpleNamespace(status='completed', output_text='{"decision":"APPROVE","reason":"Approved","follow_up":""}'),
            ]
            with self.assertRaisesRegex(ChatReviewError, 'conflicted'):
                review_chat([], 'mock-key', *load_records(), date(2026, 11, 17))

    def test_openai_defers_when_details_are_missing(self):
        fields = {
            'description': 'Van rental', 'purpose': 'Competition', 'amount': '',
            'category': 'Travel', 'deadline': '2026-11-24', 'vendor': '', 'quote': '',
        }
        decision = {'decision': 'DEFER', 'reason': 'We need a quote.', 'follow_up': 'What did the vendor quote?'}
        with patch('openai.OpenAI') as client:
            create = client.return_value.__enter__.return_value.responses.create
            create.side_effect = [
                SimpleNamespace(status='completed', output_text=json.dumps(reply))
                for reply in (fields, decision)
            ]
            result = review_chat([], 'mock-key', *load_records(), date(2026, 11, 17))
            self.assertEqual(result['decision'], 'DEFER')
            self.assertEqual(result['follow_up'], decision['follow_up'])
            self.assertIn('Provide vendor.', result['evidence']['missing'])

    def test_chat_follow_up_resolves_relative_and_us_deadline(self):
        fields = {
            'description': 'Posters', 'purpose': 'Club showcase', 'amount': '70.00',
            'category': 'Marketing', 'deadline': '', 'vendor': 'Campus Print', 'quote': '$70',
        }
        proposed = {'role': 'user', 'text': 'Campus Print quoted $70 for showcase posters. Use Marketing.'}
        question = {'role': 'assistant', 'text': 'When do you need them?'}
        for reply, expected_date in (
            ('tomorrow', '2026-11-26'),
            ('Tomorrow, please.', '2026-11-26'),
            ('in two days', '2026-11-27'),
            ('two days from now', '2026-11-27'),
            ('11/27/26', '2026-11-27'),
            ('I need them by 11/27/2026.', '2026-11-27'),
            ('The quote was issued on 11/27/26.', None),
            ('2/30/26', None),
        ):
            with self.subTest(reply=reply), patch('openai.OpenAI') as client:
                outcome = {'decision': 'APPROVE', 'reason': 'The expense fits the verified budget.', 'follow_up': ''}
                extraction = SimpleNamespace(status='completed', output_text=json.dumps(fields))
                if expected_date is None:
                    outcome = {'decision': 'DEFER', 'reason': 'The deadline is missing.', 'follow_up': 'When is it needed?'}
                create = client.return_value.__enter__.return_value.responses.create
                responses = [extraction]
                if expected_date:
                    responses.append(price_response(('60', '80'), 'The same poster sizes and print quantity.'))
                responses.append(SimpleNamespace(status='completed', output_text=json.dumps(outcome)))
                create.side_effect = responses
                messages = [proposed, question, {'role': 'user', 'text': reply}]
                result = review_chat(messages, 'mock-key', *load_records(), date(2026, 11, 25))
                evidence = json.loads(create.call_args.kwargs['input'])['verified_evidence']
                self.assertEqual(evidence['deadline'], expected_date)
                self.assertEqual(result['request']['deadline'], expected_date or '')
                self.assertEqual('Provide the date needed.' in evidence['missing'], expected_date is None)

    def test_price_evidence_gates_approval_after_budget_checks_pass(self):
        fields = {
            'description': 'Cargo van rental', 'purpose': 'Club travel', 'amount': '300.00', 'category': 'Travel',
            'deadline': '2026-11-27', 'vendor': 'Local Vans', 'quote': '$300 including taxes and fees',
        }
        text = ('Local Vans quoted $300 all-in for a cargo van in Pittsburgh for one day, including 100 miles. '
                'We need it on 11/27/26. Use Travel.')
        scope = 'One-day Pittsburgh cargo van rental with 100 miles and applicable taxes and fees.'
        for totals, status, excluded_last in (
            (('260', '325'), 'supported', False),
            (('220', '260', '500'), 'above_range', True),
            (('260', '325'), 'insufficient_sources', True),
        ):
            with self.subTest(status=status), patch('openai.OpenAI') as client:
                response = price_response(totals, scope, unusable_last=excluded_last)
                decision = 'APPROVE' if status == 'supported' else 'DEFER'
                outcome = {'decision': decision, 'reason': 'Reviewed market pricing.',
                           'follow_up': '' if decision == 'APPROVE' else 'Can you share a comparable quote?'}
                create = client.return_value.__enter__.return_value.responses.create
                create.side_effect = [
                    SimpleNamespace(status='completed', output_text=json.dumps(fields)),
                    response,
                    SimpleNamespace(status='completed', output_text=json.dumps(outcome)),
                ]
                result = review_chat([{'role': 'user', 'text': text}], 'mock-key', *load_records(), date(2026, 11, 25))
                search = create.call_args_list[1].kwargs
                self.assertEqual(search['tools'][0]['type'], 'web_search')
                self.assertEqual(search['include'], ['web_search_call.action.sources'])
                self.assertEqual(create.call_count, 3)
                self.assertEqual(result['decision'], decision)
                market = result['evidence']['market_price']
                self.assertEqual(market['status'], status)
                self.assertEqual(len(market['prices']), len(totals) - int(excluded_last))
                allowed = json.loads(create.call_args.kwargs['input'])['allowed_outcomes']
                self.assertEqual('APPROVE' in allowed, status == 'supported')

    def test_starting_rate_and_missing_rental_terms_cannot_support_price(self):
        from market_prices import compare_prices

        response = price_response(('19.95', '280'), 'One-day Pittsburgh van rental.')
        research = json.loads(response.output_text)
        research['prices'][0]['price_type'] = 'starting_rate'
        cited = {price['url'] for price in research['prices']}
        result = compare_prices('300', research, cited)
        self.assertEqual(result['status'], 'insufficient_sources')
        self.assertEqual([price['total_usd'] for price in result['prices']], ['280.00'])
        self.assertEqual(len(result['options']), 2)

        research['missing_details'] = 'How many days and miles do you need?'
        result = compare_prices('300', research, cited)
        self.assertEqual(result['status'], 'needs_details')
        self.assertEqual(result['summary'], research['missing_details'])

    def test_rental_search_returns_nearby_options_without_asking_user_to_find_quotes(self):
        fields = {
            'description': 'Cargo van rental', 'purpose': 'Club trip', 'amount': '300.00', 'category': 'Travel',
            'deadline': '2026-11-27', 'vendor': 'Local Vans', 'quote': '$300 including taxes and fees',
        }
        scope = 'One-day Pittsburgh cargo van rental.'
        response = price_response(('240', '260', ''), scope)
        research = json.loads(response.output_text)
        research['prices'][0]['availability'] = 'unverified'
        research['prices'][1]['price_type'] = 'starting_rate'
        research['prices'][2]['price_type'] = 'quote_required'
        research['prices'][2]['availability'] = 'unverified'
        response.output_text = json.dumps(research)
        outcome = {'decision': 'DEFER', 'reason': 'These providers need availability checks.',
                   'follow_up': 'Can you find other comparable quotes yourself?'}
        with patch('openai.OpenAI') as client:
            create = client.return_value.__enter__.return_value.responses.create
            create.side_effect = [
                SimpleNamespace(status='completed', output_text=json.dumps(fields)), response,
                SimpleNamespace(status='completed', output_text=json.dumps(outcome)),
            ]
            messages = [{'role': 'user', 'text': 'We need a one-day Pittsburgh cargo van rental in two days.'}]
            result = review_chat(messages, 'mock-key', *load_records(), date(2026, 11, 25))

        market = result['evidence']['market_price']
        self.assertEqual(market['status'], 'insufficient_sources')
        self.assertEqual(market['prices'], [])
        self.assertEqual([option['price_type'] for option in market['options']],
                         ['total', 'starting_rate', 'quote_required'])
        self.assertEqual(market['options'][-1]['total_usd'], '')
        self.assertEqual(result['follow_up'], '')
