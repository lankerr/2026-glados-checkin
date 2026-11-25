import unittest
from datetime import datetime, timedelta, timezone
from unittest import mock

import checkin

NOW = datetime(2026, 11, 15, 12, tzinfo=timezone(timedelta(hours=8)))
STAMP = int(NOW.timestamp() * 1000)


class PointsSubtotalScopeTests(unittest.TestCase):
    def observe(self, history):
        client = checkin.GLaDOS('gld:sess=fake; gld:sess.sig=fake')
        client.req = mock.Mock(return_value={'points': '44', 'history': history, 'plans': {}})
        with mock.patch('checkin.beijing_now', return_value=NOW):
            self.assertTrue(client.get_points())
        client.req.assert_called_once_with('GET', '/api/user/points')
        return client

    def assert_scope(self, client):
        summary = checkin.today_rewards_summary(client)
        card = checkin.render_account_card(1, client, '', '')
        for text in (summary, card):
            for qualifier in ('小计', '已返回前10条', '排除 exchange/refund', '完整性未确认', '非全天合计', '未关联本次请求'):
                self.assertIn(qualifier, text)
            self.assertNotIn('含所有来源', text)
            self.assertNotIn('今日加分合计', text)

    def test_eleven_today_entries_are_labelled_as_partial_not_daily_total(self):
        client = self.observe([{'time': STAMP, 'change': 1, 'business': 'checkin'} for _ in range(11)])
        self.assertEqual(client.today_rewards_total, '+10')
        self.assertEqual(client.today_rewards_count, 10)
        self.assert_scope(client)

    def test_excluded_positive_entries_and_malformed_rows_are_disclosed(self):
        client = self.observe([
            {'time': STAMP, 'change': 2, 'business': 'checkin'},
            {'time': STAMP, 'change': 5, 'business': 'refund'},
            {'time': STAMP, 'change': 7, 'business': 'exchange'},
            {'time': 'bad', 'change': 9},
            {'time': STAMP, 'change': 'bad'},
            None,
        ])
        self.assertEqual(client.today_rewards_total, '+2')
        self.assertEqual(client.today_rewards_count, 1)
        self.assert_scope(client)

    def test_empty_or_no_eligible_records_do_not_claim_zero_daily_gain(self):
        for history in ([], [{'time': STAMP, 'change': 5, 'business': 'refund'}]):
            with self.subTest(history=history):
                client = self.observe(history)
                self.assertIsNone(client.today_rewards_total)
                self.assertEqual(checkin.today_rewards_summary(client), '')
                self.assertNotIn('今日符合条件的正变动小计:', checkin.render_account_card(1, client, '', ''))


if __name__ == '__main__':
    unittest.main()
