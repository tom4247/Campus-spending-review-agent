import json
import os
import unittest
from datetime import date
from types import SimpleNamespace
from unittest.mock import patch

from agent import review_chat
from chat_review import ChatReviewError
from review import load_records


class OpenAIChatTests(unittest.TestCase):
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
