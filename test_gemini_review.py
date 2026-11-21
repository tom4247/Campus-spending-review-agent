import json
import os
import unittest
from datetime import date
from unittest.mock import patch

import httpx

from gemini_review import GeminiReviewError, review_chat
from review import load_records


class GeminiReviewTests(unittest.TestCase):
    def setUp(self):
        self.records = load_records()
        self.today = date(2026, 11, 17)
        self.messages = ['Can we rent a van for a club competition?', 'It is $80 from Example Vans.']
        self.fields = {
            'description': 'Van rental', 'purpose': 'Club competition', 'amount': '80.00',
            'category': 'Travel', 'deadline': '2026-11-24', 'vendor': 'Example Vans',
            'quote': 'Example Vans quote: $80',
        }

    def mock_review(self, decision, expected_outcomes, expected_shortfall='0.00'):
        requests = []
        replies = iter([self.fields, {'decision': decision, 'reason': 'The reason returned by Gemini.'}])
        client_type = httpx.Client

        def respond(request):
            self.assertEqual(request.url.host, 'generativelanguage.googleapis.com')
            self.assertEqual(request.headers['x-goog-api-key'], 'test-key')
            self.assertNotIn('test-key', request.content.decode())
            requests.append(json.loads(request.content))
            return httpx.Response(200, json={'candidates': [{
                'finishReason': 'STOP',
                'content': {'parts': [{'text': json.dumps(next(replies))}]},
            }]})

        def make_client(**kwargs):
            return client_type(transport=httpx.MockTransport(respond), **kwargs)

        with patch.dict(os.environ, {'GEMINI_MODEL': ''}), patch('gemini_review.httpx.Client', side_effect=make_client):
            try:
                return review_chat(self.messages, 'test-key', *self.records, self.today)
            finally:
                self.assertEqual(len(requests), 2)
                review_payload = json.loads(requests[-1]['contents'][0]['parts'][0]['text'])
                self.assertEqual(review_payload['user_messages'], self.messages)
                evidence = review_payload['verified_evidence']
                self.assertEqual(evidence.get('shortfall'), expected_shortfall)
                self.assertNotIn('decision', evidence)
                self.assertEqual(review_payload['allowed_outcomes'], expected_outcomes)

    def test_gemini_can_escalate_an_affordable_request(self):
        result = self.mock_review('ESCALATE', ['APPROVE', 'DEFER', 'ESCALATE'])
        self.assertEqual(result['decision'], 'ESCALATE')

    def test_gemini_approval_is_accepted_for_a_complete_request(self):
        result = self.mock_review('APPROVE', ['APPROVE', 'DEFER', 'ESCALATE'])
        self.assertEqual(result['decision'], 'APPROVE')

    def test_model_cannot_approve_a_verified_shortfall(self):
        self.fields['amount'] = '450.00'
        with self.assertRaisesRegex(GeminiReviewError, 'conflicted'):
            self.mock_review('APPROVE', ['ESCALATE'], '150.00')

    def test_partial_request_can_defer_without_budget_calculation(self):
        self.fields['category'] = None
        self.fields['amount'] = None
        result = self.mock_review('DEFER', ['DEFER', 'ESCALATE'], None)
        self.assertEqual(result['decision'], 'DEFER')
        self.assertIn('Confirm the spending category.', result['evidence']['missing'])
