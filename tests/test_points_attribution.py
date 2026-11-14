import os
import unittest
from datetime import datetime, timezone, timedelta
from unittest import mock
import checkin

NOW = datetime(2026, 11, 14, 17, 0, tzinfo=timezone(timedelta(hours=8)))
MS = int(NOW.timestamp() * 1000)


class AttributionTests(unittest.TestCase):
    def observe(self, history):
        client = checkin.GLaDOS('gld:sess=fake; gld:sess.sig=fake')
        client.req = mock.Mock(return_value={'points': 50, 'history': history})
        with mock.patch('checkin.beijing_now', return_value=NOW):
            client.get_points()
        return client

    def test_same_amount_unrelated_credit_does_not_verify_attribution(self):
        client = self.observe([{'time': MS, 'change': 5, 'business': 'promotion'}])
        result = checkin.summarize_current_run_gain({'code': 0, 'points': 5}, True, client)
        self.assertIn('本次入账归属未确认', result)
        self.assertIn('未关联本次请求', result)
        self.assertNotIn('核对一致', result)

    def test_multiple_same_day_credits_are_not_total_or_current_gain(self):
        client = self.observe([
            {'time': MS, 'change': 5, 'business': 'promotion'},
            {'time': MS-1000, 'change': 12, 'business': 'checkin'},
        ])
        result = checkin.summarize_current_run_gain({'code': 0, 'points': 5}, True, client)
        self.assertIn('一笔正变动 +5', result)
        self.assertIn('非今日合计', result)
        self.assertNotIn('实际入账', result)

    def test_missing_delayed_or_undated_history_does_not_imply_zero(self):
        for history in ([], [{'change': 5}], [{'time': MS-86400000, 'change': 5}]):
            with self.subTest(history=history):
                result = checkin.summarize_current_run_gain(
                    {'code': 0, 'points': 5}, True, self.observe(history))
                self.assertIn('本次入账归属未确认', result)
                self.assertIn('不等于没有入账', result)

    @mock.patch('checkin.time.sleep')
    def test_timeout_then_refusal_does_not_assert_entire_run_added_zero(self, sleep):
        client = self.observe([{'time': MS, 'change': 5}])
        client.checkin = mock.Mock(side_effect=[
            {'request_failed': True, 'reason': 'network'},
            {'code': 5, 'reason': 'turnstile', 'message': 'Nothing was recorded'},
        ])
        with mock.patch.dict(os.environ, {'GLADOS_BROWSER_CHECKIN': '0'}), \
                mock.patch('checkin.log'):
            result, success = checkin.checkin_with_retry(client, 3, 0)
        self.assertFalse(success)
        self.assertEqual(client.checkin.call_count, 2)
        summary = checkin.summarize_current_run_gain(result, success, client)
        self.assertIn('本轮是否入账未知', summary)
        self.assertNotIn('0 分', summary)

    def test_repeat_after_unknown_attempt_does_not_assert_entire_run_zero(self):
        summary = checkin.summarize_current_run_gain(
            {'code': 1, 'message': "Today's observation logged"}, True,
            self.observe([{'time': MS, 'change': 5}]))
        self.assertIn('不能据此确定本轮新增积分', summary)
        self.assertNotIn('0 分', summary)

    def test_breakdown_difference_does_not_infer_cap(self):
        summary = checkin.summarize_current_run_gain(
            {'code': 0, 'points': 2, 'breakdown': {'base': 2.7}}, True,
            self.observe([{'time': MS, 'change': 2}]))
        self.assertIn('不据此推断封顶规则', summary)
        self.assertNotIn('受上限', summary)
