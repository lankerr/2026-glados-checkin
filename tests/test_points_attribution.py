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


class TodayRewardsTotalTests(unittest.TestCase):
    def test_sums_eligible_today_entries_in_returned_window(self):
        client = checkin.GLaDOS('gld:sess=fake; gld:sess.sig=fake')
        client.req = mock.Mock(return_value={'points': 44, 'history': [
            {'change': '19', 'time': MS},
            {'change': '10', 'time': MS},
            {'change': '14', 'time': MS - 86400000},          # 昨天：不计
            {'change': '-500', 'time': MS, 'business': 'exchange'},  # 兑换：不计
            {'change': '1.5', 'time': MS},                    # 小数：计入
        ], 'plans': {}})
        with mock.patch('checkin.beijing_now', return_value=NOW):
            client.get_points()
        self.assertEqual(client.today_rewards_total, '+30.5')
        self.assertEqual(client.today_rewards_count, 3)
        summary = checkin.today_rewards_summary(client)
        self.assertIn('今日符合条件的正变动小计 +30.5 分（已返回前10条流水中 3 笔', summary)

    def test_no_today_entries_yields_empty_summary(self):
        client = checkin.GLaDOS('gld:sess=fake; gld:sess.sig=fake')
        client.req = mock.Mock(return_value={'points': 5, 'history': [
            {'change': '14', 'time': MS - 86400000}], 'plans': {}})
        with mock.patch('checkin.beijing_now', return_value=NOW):
            client.get_points()
        self.assertIsNone(client.today_rewards_total)
        self.assertEqual(checkin.today_rewards_summary(client), '')

    def test_push_card_shows_today_gain_line(self):
        client = checkin.GLaDOS('gld:sess=fake; gld:sess.sig=fake')
        client.req = mock.Mock(return_value={'points': 44, 'history': [
            {'change': '19', 'time': MS}, {'change': '10', 'time': MS},
        ], 'plans': {}})
        with mock.patch('checkin.beijing_now', return_value=NOW):
            client.get_points()
        card = checkin.render_account_card(1, client, '观察', 'OK')
        self.assertIn('今日符合条件的正变动小计', card)
        self.assertIn('+29', card)
        self.assertIn('已返回前10条流水中 2 笔', card)



class RecentEntriesTests(unittest.TestCase):
    def test_recent_entries_collected_and_card_renders_mini_ledger(self):
        client = checkin.GLaDOS('gld:sess=fake; gld:sess.sig=fake')
        client.req = mock.Mock(return_value={'points': 56, 'history': [
            {'change': '12', 'time': MS},
            {'change': '19', 'time': MS - 86400000},
            {'change': '-500', 'time': MS - 86400000, 'business': 'exchange'},
        ], 'plans': {}})
        with mock.patch('checkin.beijing_now', return_value=NOW):
            client.get_points()
        self.assertEqual(len(client.recent_entries), 3)
        self.assertEqual(client.recent_entries[0]['change'], '+12')
        card = checkin.render_account_card(1, client, '观察', 'OK')
        self.assertIn('近期积分流水', card)
        self.assertIn('+12', card)
        self.assertIn('-500', card)


class StreakStateTests(unittest.TestCase):
    def test_continuation_and_first_run_and_gap(self):
        from datetime import date
        from update_streak import next_state, parse_block, render_block
        today = date(2026, 11, 17)
        # ① 连续推进：昨天有记录
        c, d, ch = next_state(3, '2026-11-16', {'2026-11-17', '2026-11-16'}, today)
        self.assertEqual((c, d, ch), (4, '2026-11-17', True))
        # ② 今日未入账：原样保持
        c, d, ch = next_state(4, '2026-11-17', set(), today)
        self.assertEqual((c, d, ch), (4, '2026-11-17', False))
        # ③ 断档后从窗口重算
        c, d, ch = next_state(30, '2026-11-01', {'2026-11-17', '2026-11-16'}, today)
        self.assertEqual((c, d, ch), (2, '2026-11-17', True))
        # ④ 标记块解析与渲染往返
        block = render_block(4, '2026-11-17', '+12')
        self.assertEqual(parse_block(block), (4, '2026-11-17'))
