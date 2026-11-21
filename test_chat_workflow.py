import os
import unittest
from unittest.mock import patch

from streamlit.testing.v1 import AppTest


class ChatWorkflowTests(unittest.TestCase):
    def test_streamlit_boolean_secret_enables_chat(self):
        with patch.dict(os.environ, {'GEMINI_CHAT_ENABLED': 'false', 'GEMINI_API_KEY': ''}):
            app = AppTest.from_file('app.py')
            app.secrets['GEMINI_API_KEY'] = 'mock-key'
            app.secrets['GEMINI_CHAT_ENABLED'] = True
            app.run()
            self.assertFalse(app.exception)
            self.assertFalse(app.chat_input[0].disabled)

    def test_openai_can_be_enabled_in_streamlit_secrets(self):
        from chat_review import ChatReviewError

        with patch('agent.review_chat', side_effect=ChatReviewError('Test OpenAI response')) as openai, patch(
            'gemini_review.review_chat'
        ) as gemini, patch.dict(os.environ, {'SUPABASE_URL': '', 'SUPABASE_SECRET_KEY': ''}):
            app = AppTest.from_file('app.py')
            app.secrets['OPENAI_API_KEY'] = 'mock-key'
            app.secrets['OPENAI_CHAT_ENABLED'] = True
            app.secrets['GEMINI_API_KEY'] = 'mock-gemini-key'
            app.secrets['GEMINI_CHAT_ENABLED'] = True
            app.run()
            self.assertFalse(app.chat_input[0].disabled)
            app.chat_input[0].set_value('A test van request').run()
            self.assertFalse(app.exception)
            self.assertEqual(openai.call_args.args[0], [{'role': 'user', 'text': 'A test van request'}])
            gemini.assert_not_called()
            self.assertTrue(any('Test OpenAI response' in item.value for item in app.warning))

    def test_follow_up_updates_the_same_review_and_exposes_a_handoff(self):
        settings = {'GEMINI_CHAT_ENABLED': 'true', 'GEMINI_API_KEY': 'mock-key',
                    'SUPABASE_URL': 'https://example.supabase.co', 'SUPABASE_SECRET_KEY': 'sb_secret_mock'}
        request = {'description': 'Van rental', 'category': 'Travel', 'amount': '450.00', 'deadline': '2026-11-24'}
        evidence = {'category': 'Travel', 'amount': '450.00', 'available': '300.00', 'shortfall': '150.00',
                    'escalation_reasons': ['Insufficient funds: $150.00.'], 'missing': [],
                    'rules': ['Spending must fit available category funds.']}
        follow_up = 'What is the total quoted by your vendor?'
        first = {'decision': 'DEFER', 'reason': 'The total is missing.', 'follow_up': follow_up, 'request': request,
                 'evidence': {'escalation_reasons': [], 'missing': ['Provide the requested amount.'], 'rules': []}}
        second = {'decision': 'ESCALATE', 'reason': 'Travel is $150 short.', 'follow_up': '',
                  'request': request, 'evidence': evidence}

        with patch.dict(os.environ, settings), patch('gemini_review.review_chat', side_effect=[first, second]) as model, patch(
            'submission_log.save_review', return_value=True
        ) as save:
            app = AppTest.from_file('app.py').run()
            self.assertFalse(app.exception)
            self.assertFalse(app.text_input)
            app.chat_input[0].set_value('I need a van for our club trip.').run()
            self.assertFalse(app.exception)
            self.assertTrue(any(follow_up in item.value for item in app.text))
            app.chat_input[0].set_value('The quote is $450.').run()
            self.assertFalse(app.exception)

            snapshots = [call.args[-1] for call in save.call_args_list]
            self.assertEqual([row['status'] for row in snapshots], ['PENDING', 'DEFER', 'PENDING', 'ESCALATE'])
            self.assertEqual(len({row['id'] for row in snapshots}), 1)
            self.assertIn(follow_up, model.call_args.args[0][1]['text'])
            self.assertEqual(snapshots[-1]['transcript'][-2]['text'], 'The quote is $450.')
            self.assertIn('Shortfall: $150.00', snapshots[-1]['review']['handoff'])
            self.assertIn('Shortfall: $150.00', app.code[0].value)

            next(button for button in app.button if button.label == 'Start a new chat request').click().run()
            self.assertFalse(app.chat_message)
            self.assertTrue(any(item.label == 'Review history for this session' for item in app.expander))
            self.assertEqual(save.call_count, 4)

    def test_paused_chat_keeps_manual_review_available(self):
        with patch.dict(os.environ, {'GEMINI_CHAT_ENABLED': 'false', 'GEMINI_API_KEY': 'mock-key',
                                     'SUPABASE_URL': '', 'SUPABASE_SECRET_KEY': ''}):
            app = AppTest.from_file('app.py').run()
            self.assertFalse(app.exception)
            self.assertTrue(app.chat_input[0].disabled)
            self.assertFalse(any(item.label == 'Draft with AI' for item in app.expander))
            next(button for button in app.button if button.label == 'Try a sample request').click().run()
            next(button for button in app.button if button.label == 'Review purchase').click().run()
            self.assertFalse(app.exception)
            self.assertEqual(app.session_state['review']['decision'], 'ESCALATE')
