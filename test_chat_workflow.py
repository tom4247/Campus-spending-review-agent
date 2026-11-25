import os
import unittest
from datetime import timedelta
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

from review import PurchaseRequest, review_evidence


class ChatWorkflowTests(unittest.TestCase):
    def test_openai_key_alone_enables_chat_in_streamlit_secrets(self):
        from chat_review import ChatReviewError

        with patch('agent.review_chat', side_effect=ChatReviewError('Test OpenAI response')) as model, patch.dict(
            os.environ, {'SUPABASE_URL': '', 'SUPABASE_SECRET_KEY': ''}
        ):
            os.environ.pop('OPENAI_CHAT_ENABLED', None)
            app = AppTest.from_file('app.py')
            app.secrets['OPENAI_API_KEY'] = 'mock-key'
            app.run()
            self.assertFalse(app.chat_input[0].disabled)
            app.chat_input[0].set_value('A test van request').run()
            self.assertFalse(app.exception)
            self.assertEqual(model.call_args.args[0], [{'role': 'user', 'text': 'A test van request'}])
            self.assertTrue(any('Test OpenAI response' in item.value for item in app.warning))

    def test_missing_openai_key_keeps_chat_disabled(self):
        with patch.dict(os.environ, {'OPENAI_API_KEY': '', 'OPENAI_CHAT_ENABLED': 'true'}):
            app = AppTest.from_file('app.py').run()
            self.assertFalse(app.exception)
            self.assertTrue(app.chat_input[0].disabled)

    def test_follow_up_updates_the_same_review_and_exposes_a_handoff(self):
        settings = {'OPENAI_CHAT_ENABLED': 'true', 'OPENAI_API_KEY': 'mock-key',
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

        with patch.dict(os.environ, settings), patch('agent.review_chat', side_effect=[first, second]) as model, patch(
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
        with patch.dict(os.environ, {'OPENAI_CHAT_ENABLED': 'false', 'OPENAI_API_KEY': 'mock-key',
                                     'SUPABASE_URL': '', 'SUPABASE_SECRET_KEY': ''}):
            app = AppTest.from_file('app.py').run()
            self.assertFalse(app.exception)
            self.assertTrue(app.chat_input[0].disabled)
            self.assertFalse(any(item.label == 'Draft with AI' for item in app.expander))
            next(button for button in app.button if button.label == 'Try a sample request').click().run()
            next(button for button in app.button if button.label == 'Review purchase').click().run()
            self.assertFalse(app.exception)
            self.assertEqual(app.session_state['review']['decision'], 'ESCALATE')

    def test_reported_payment_uses_actual_amount_and_reduces_session_budget_once(self):
        settings = {'OPENAI_CHAT_ENABLED': 'true', 'OPENAI_API_KEY': 'mock-key',
                    'SUPABASE_URL': 'https://example.supabase.co', 'SUPABASE_SECRET_KEY': 'sb_secret_mock'}
        first = 'Campus Shuttle quoted $100 for our competition trip.'
        second = 'City Bus quoted $200 for our conference trip.'

        def review(messages, api_key, budgets, ledger, policies, today):
            amount = '100' if messages[0]['text'] == first else '200'
            request = PurchaseRequest('Bus trip', 'Club travel', amount, 'Travel',
                                      today + timedelta(days=7), 'Example Bus', f'${amount}')
            evidence = review_evidence(request, budgets, ledger, policies, today)
            decision = 'ESCALATE' if evidence['escalation_reasons'] else 'DEFER' if evidence['missing'] else 'APPROVE'
            return {'decision': decision, 'request': {'description': request.description, 'amount': amount,
                                                      'category': request.category},
                    'evidence': evidence, 'reason': f"Available funds: ${evidence['available']}.",
                    'follow_up': 'Have the budget records been verified?' if decision == 'DEFER' else ''}

        with patch.dict(os.environ, settings), patch('agent.review_chat', side_effect=review) as model, patch(
            'submission_log.save_review', side_effect=[True, True, False, True, True, True]
        ) as write:
            app = AppTest.from_file('app.py').run()

            def send(prompt, expected):
                app.chat_input[0].set_value(prompt).run()
                self.assertFalse(app.exception)
                self.assertTrue(any(expected in item.value for item in app.text))

            send('I paid $125.50', 'Review a purchase with a spending category')
            send(first, 'Available funds: $300.00.')
            send('Record paid $0', 'Enter a payment amount greater than zero.')
            send('I paid $125.50', 'Available in this session: $174.50.')
            self.assertTrue(any('could not be confirmed in Supabase' in item.value for item in app.warning))
            send('I paid $125.50', 'already has a $125.50 payment recorded.')
            self.assertFalse(any('could not be confirmed in Supabase' in item.value for item in app.warning))
            send('I paid $126', 'already has a $125.50 payment recorded.')
            self.assertEqual(write.call_count, 4)
            saved, retried = [call.args[-1] for call in write.call_args_list[2:4]]
            self.assertEqual(saved, retried)
            self.assertEqual(saved['id'], write.call_args_list[1].args[-1]['id'])
            self.assertEqual(saved['review']['payment']['amount'], '125.50')
            self.assertEqual(saved['review']['result']['request']['amount'], '100')
            self.assertEqual(app.dataframe[0].value.iloc[0]['Paid in this session'], '$125.50')

            next(button for button in app.button if button.label == 'Start a new chat request').click().run()
            send(second, 'Shortfall: $25.50')
            self.assertEqual(model.call_args_list[0].args[0], [{'role': 'user', 'text': first}])
            self.assertEqual(model.call_args.args[0], [{'role': 'user', 'text': second}])
            self.assertEqual(model.call_count, 2)
            overview = app.dataframe[1].value.set_index('Category')
            self.assertEqual(overview.loc['Travel', 'Paid expenses'], '$925.50')
            self.assertEqual(overview.loc['Travel', 'Available'], '$174.50')

            other = AppTest.from_file('app.py').run()
            self.assertEqual(other.dataframe[0].value.set_index('Category').loc['Travel', 'Available'], '$300.00')

    def test_budget_updates_and_named_payment_work_in_the_same_chat(self):
        settings = {'OPENAI_CHAT_ENABLED': 'true', 'OPENAI_API_KEY': 'mock-key',
                    'SUPABASE_URL': 'https://example.supabase.co', 'SUPABASE_SECRET_KEY': 'sb_secret_mock'}
        request_text = 'Example Van Rentals quoted $300 for a van rental. Use Travel.'

        def review(messages, api_key, budgets, ledger, policies, today):
            request = PurchaseRequest('Van rental', 'Club travel', '300', 'Travel',
                                      today + timedelta(days=7), 'Example Van Rentals', '$300')
            evidence = review_evidence(request, budgets, ledger, policies, today)
            decision = 'DEFER' if evidence['missing'] else 'APPROVE'
            return {'decision': decision, 'request': {'description': request.description, 'amount': '300',
                                                      'category': request.category},
                    'evidence': evidence, 'reason': f"Available funds: ${evidence['available']}.",
                    'follow_up': 'Have the budget records been verified?' if decision == 'DEFER' else ''}

        with patch.dict(os.environ, settings), patch('agent.review_chat', side_effect=review) as model, patch(
            'submission_log.save_review', return_value=True
        ) as save_review, patch('submission_log.record_submission', return_value=True) as log_update:
            app = AppTest.from_file('app.py').run()
            for prompt, expected in (
                ('Can you update our budget?', 'Which category and total allocation'),
                ('Travel to $2,200', 'Available in this session: $500.00.'),
                (request_text, 'Available funds: $500.00.'),
                ('I paid for the $300 projector', 'The current review is “Van rental”'),
                ('I paid for the $300 van rental', 'Available in this session: $200.00.'),
                ('Please add $50 to the Travel budget.', 'Available in this session: $250.00.'),
                ("What's my budget?", 'Travel: $250.00 available'),
            ):
                app.chat_input[0].set_value(prompt).run()
                self.assertFalse(app.exception)
                self.assertTrue(any(expected in item.value for item in app.text), expected)

            model.assert_called_once()
            self.assertEqual(model.call_args.args[0], [{'role': 'user', 'text': request_text}])
            self.assertEqual(save_review.call_args.args[-1]['review']['payment']['amount'], '300.00')
            events = [call.args[-1] for call in log_update.call_args_list]
            self.assertEqual([event['allocation'] for event in events], ['2200.00', '2250.00'])
            self.assertEqual([event['available_after'] for event in events], ['500.00', '250.00'])
            self.assertEqual(events[0]['session_id'], events[1]['session_id'])

    def test_spending_report_in_fresh_chat_updates_budget_without_model_or_review(self):
        settings = {'OPENAI_CHAT_ENABLED': 'true', 'OPENAI_API_KEY': 'mock-key',
                    'SUPABASE_URL': 'https://example.supabase.co', 'SUPABASE_SECRET_KEY': 'sb_secret_mock'}
        with patch.dict(os.environ, settings), patch('agent.review_chat') as model, patch(
            'submission_log.save_review'
        ) as save_review, patch('submission_log.record_submission', return_value=True) as log_expense:
            app = AppTest.from_file('app.py').run()
            for prompt, available, expected in (
                ('We spent $300 on travel', '$0.00', 'Recorded $300.00 spent on Travel.'),
                ('We spent $300 on Travel.', '$0.00', 'already recorded as spent on Travel'),
                ('We spent $0 on Travel', '$0.00', 'Enter an expense amount greater than zero.'),
                ('We spent $40 on a mystery category', '$0.00', 'Choose a budget category'),
                ('We spent another $300 on Travel', '$-300.00', 'Available in this session: $-300.00'),
            ):
                app.chat_input[0].set_value(prompt).run()
                self.assertFalse(app.exception)
                self.assertTrue(any(expected in item.value for item in app.text), expected)
                self.assertEqual(app.dataframe[0].value.set_index('Category').loc['Travel', 'Available'], available)

            next(button for button in app.button if button.label == 'Start a new chat request').click().run()
            self.assertEqual(app.dataframe[0].value.set_index('Category').loc['Travel', 'Paid expenses'], '$1,400.00')
            model.assert_not_called()
            save_review.assert_not_called()
            events = [call.args[-1] for call in log_expense.call_args_list]
            self.assertEqual([event['kind'] for event in events], ['spending_reported', 'spending_reported'])
            self.assertEqual([event['available_after'] for event in events], ['0.00', '-300.00'])
            self.assertTrue(all(event['review_id'] is None for event in events))
            self.assertNotEqual(events[0]['expense_id'], events[1]['expense_id'])

    def test_completed_zipcar_expense_bypasses_pending_review(self):
        settings = {'OPENAI_CHAT_ENABLED': 'true', 'OPENAI_API_KEY': 'mock-key',
                    'SUPABASE_URL': 'https://example.supabase.co', 'SUPABASE_SECRET_KEY': 'sb_secret_mock'}
        proposed = 'We are considering a $300 Zipcar rental. We got the quote two days ago.'
        completed = ('requested amount $300, zip car is vendor, the quote is $300 and '
                     'date we got it was two days ago')
        deferred = {
            'decision': 'DEFER', 'reason': 'Provide the date needed.', 'follow_up': 'When do you need it?',
            'request': {'description': 'Zipcar rental', 'category': 'Travel', 'amount': '300'},
            'evidence': {'escalation_reasons': [], 'missing': ['Provide the date needed.'], 'rules': []},
        }
        with patch.dict(os.environ, settings), patch('agent.review_chat', return_value=deferred) as model, patch(
            'submission_log.save_review', return_value=True
        ) as save_review, patch('submission_log.record_submission', return_value=True) as log_expense:
            app = AppTest.from_file('app.py').run()
            app.chat_input[0].set_value(proposed).run()
            self.assertFalse(app.exception)
            model.assert_called_once()
            log_expense.assert_not_called()

            app.chat_input[0].set_value(completed).run()
            self.assertFalse(app.exception)
            reply = app.session_state['expense_review_chat'][-1]
            self.assertEqual(reply['text'], 'Recorded $300.00 spent on Travel. Available in this session: $0.00.')
            self.assertTrue(reply['account_notice'])
            model.assert_called_once()
            self.assertEqual(save_review.call_count, 2)
            log_expense.assert_called_once()
            self.assertEqual(log_expense.call_args.args[-1]['category'], 'Travel')
            budget = next(item.value for item in app.dataframe if 'Allocation' in item.value.columns)
            travel = budget.set_index('Category').loc['Travel']
            self.assertEqual((travel['Paid expenses'], travel['Available']), ('$1,100.00', '$0.00'))

    def test_food_spending_and_category_clarification_keep_accounting_intent(self):
        settings = {'OPENAI_CHAT_ENABLED': 'true', 'OPENAI_API_KEY': 'mock-key',
                    'SUPABASE_URL': 'https://example.supabase.co', 'SUPABASE_SECRET_KEY': 'sb_secret_mock'}
        with patch.dict(os.environ, settings), patch('agent.review_chat') as model, patch(
            'submission_log.save_review'
        ) as save_review, patch('submission_log.record_submission', return_value=True) as log_expense:
            app = AppTest.from_file('app.py').run()
            for prompt, expected, available in (
                ('we spent hte $100 for food, update the budget', 'Recorded $100.00 spent on Events.', '$1,800.00'),
                ('We paid $60 for food', 'Recorded $60.00 spent on Events.', '$1,740.00'),
                ('We spent $20 on assorted items', 'Choose a budget category', '$1,740.00'),
                ('food', 'Recorded $20.00 spent on Events.', '$1,720.00'),
                ('We spent money for food', 'What was the total amount you paid?', '$1,720.00'),
                ('It was $15', 'Recorded $15.00 spent on Events.', '$1,705.00'),
            ):
                app.chat_input[0].set_value(prompt).run()
                self.assertFalse(app.exception)
                reply = app.session_state['expense_review_chat'][-1]
                self.assertIn(expected, reply['text'])
                row = app.dataframe[0].value.set_index('Category').loc['Events']
                self.assertEqual(row['Available'], available)

            model.assert_not_called()
            save_review.assert_not_called()
            self.assertEqual([call.args[-1]['amount'] for call in log_expense.call_args_list],
                             ['100.00', '60.00', '20.00', '15.00'])

    def test_chat_displays_price_check_with_source_links(self):
        settings = {'OPENAI_CHAT_ENABLED': 'true', 'OPENAI_API_KEY': 'mock-key',
                    'SUPABASE_URL': '', 'SUPABASE_SECRET_KEY': ''}
        market = {'status': 'above_range', 'summary': 'The $300 quote is above the observed range.',
                  'scope': 'Pittsburgh cargo vans for one day.',
                  'prices': [{'provider': 'Comparable Vans', 'total_usd': '250.00',
                              'terms': 'Same class, date, and mileage.',
                              'url': 'https://comparable.example/cargo-van'}]}
        result = {'decision': 'DEFER', 'reason': 'Check the quoted price.', 'follow_up': 'What is included?',
                  'request': {'description': 'Van rental'},
                  'evidence': {'escalation_reasons': [], 'missing': [market['summary']], 'rules': [],
                               'market_price': market}}

        with patch.dict(os.environ, settings), patch('agent.review_chat', return_value=result):
            app = AppTest.from_file('app.py').run()
            app.chat_input[0].set_value('A $300 van rental').run()
            self.assertFalse(app.exception)
            self.assertTrue(any(item.label == 'Market price check' for item in app.expander))
            self.assertTrue(any(market['summary'] in item.value for item in app.text))
            self.assertEqual(app.get('link_button')[0].proto.url, 'https://comparable.example/cargo-van')

    def test_date_stays_visible_when_price_check_is_unavailable(self):
        from market_prices import market_unavailable

        settings = {'OPENAI_CHAT_ENABLED': 'true', 'OPENAI_API_KEY': 'mock-key',
                    'SUPABASE_URL': '', 'SUPABASE_SECRET_KEY': ''}
        market = market_unavailable()
        result = {'decision': 'DEFER', 'reason': 'The budget and policy checks are complete.', 'follow_up': '',
                  'request': {'description': 'Van rental', 'deadline': '2026-11-27'},
                  'evidence': {'deadline': '2026-11-27', 'escalation_reasons': [], 'missing': [market['summary']],
                               'rules': [], 'market_price': market}}

        with patch.dict(os.environ, settings), patch('agent.review_chat', return_value=result):
            app = AppTest.from_file('app.py').run()
            app.chat_input[0].set_value('I need the rental two days from now').run()
            self.assertFalse(app.exception)
            self.assertTrue(any('Price check unavailable' in item.value for item in app.markdown))
            self.assertTrue(any(item.value == 'Needed by November 27, 2026' for item in app.text))
            self.assertTrue(any('Retry when live price search is available' in item.value for item in app.text))
