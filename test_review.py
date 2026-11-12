import shutil
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch
from types import SimpleNamespace
from review import DATA, load_records, evaluate, PurchaseRequest
from agent import explain


class ReviewTests(unittest.TestCase):
    def setUp(self):
        self.b, self.l, self.p = load_records()
        self.today = date(2026, 11, 11)
        self.r = PurchaseRequest('Van rental', 'Club event travel', '450', 'Travel',
                                 self.today + timedelta(days=1), 'Example vendor', '$450 estimate')

    def review(self):
        return evaluate(self.r, self.b, self.l, self.p, self.today)

    def test_van_shortfall(self):
        r = self.review()
        self.assertEqual((r['decision'], r['available'], r['shortfall']), ('ESCALATE', '300.00', '150.00'))
        self.assertTrue(r['urgent'])

    def test_affordable_request(self):
        self.r.amount = '300.00'
        self.assertEqual(self.review()['decision'], 'APPROVE')

    def test_missing_information_and_urgent_priority(self):
        self.r.amount = '100'
        self.r.vendor = ''
        self.r.deadline = self.today + timedelta(days=7)
        self.assertEqual(self.review()['decision'], 'DEFER')
        self.r.deadline = self.today
        self.assertEqual(self.review()['decision'], 'ESCALATE')

    def test_invalid_currency(self):
        for amount in ['-1', '0', 'NaN', 'Infinity', '4.001', 'abc', '1e100000']:
            with self.subTest(amount=amount), self.assertRaises(ValueError):
                self.r.amount = amount
                self.review()

    def test_stale_and_future_records(self):
        self.r.amount = '100'
        self.r.deadline = self.today + timedelta(days=7)
        for verified in [self.today - timedelta(days=15), self.today + timedelta(days=1)]:
            self.b[0]['verified_on'] = verified
            self.assertEqual(self.review()['decision'], 'DEFER')

    def test_threshold_and_restriction(self):
        self.r.category = 'Events'
        self.r.amount = '1000'
        self.assertEqual(self.review()['decision'], 'ESCALATE')
        self.r.category = 'Equipment'
        self.r.amount = '100'
        self.assertEqual(self.review()['decision'], 'ESCALATE')

    def test_duplicate_records_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            directory = Path(d)
            for source in DATA.iterdir():
                shutil.copy(source, directory)
            with (directory / 'ledger.csv').open('a') as f:
                f.write('TR002,Travel,Duplicate hotel,900.00,paid\n')
            with self.assertRaises(ValueError):
                load_records(directory)

    def test_missing_deadline_and_past_deadline(self):
        self.r.amount = '100'
        for deadline in [None, self.today - timedelta(days=1)]:
            self.r.deadline = deadline
            self.assertEqual(self.review()['decision'], 'DEFER')

    def test_read_only_tool_protocol(self):
        review = self.review()
        call = SimpleNamespace(type='function_call', name='get_verified_review', arguments='{}', call_id='test')
        first = SimpleNamespace(output=[call])
        last = SimpleNamespace(output_text='Ask the financial reviewer to review the shortfall.')
        with patch('openai.OpenAI') as client:
            client.return_value.responses.create.side_effect = [first, last]
            self.assertEqual(explain(review), last.output_text)
            second = client.return_value.responses.create.call_args_list[1].kwargs
            self.assertEqual(second['tool_choice'], 'none')
            self.assertIn('150.00', second['input'][-1]['output'])


if __name__ == '__main__':
    unittest.main()
