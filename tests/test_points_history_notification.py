import os
import unittest
from datetime import datetime, timedelta, timezone
from unittest import mock
import checkin

COOKIE = 'gld:sess=fake; gld:sess.sig=fake'
FIXED_NOW = datetime(2026, 11, 14, 16, 0, 0, tzinfo=timezone(timedelta(hours=8)))
TODAY_MS = int(datetime(2026, 11, 14, 9, 30, 0, tzinfo=timezone(timedelta(hours=8))).timestamp() * 1000)


class PointsHistoryTests(unittest.TestCase):
    def test_history_timestamp_is_explicit_and_resets_when_history_empty(self):
        client = checkin.GLaDOS(COOKIE)
        client.req = mock.Mock(return_value={'points': '15', 'history': [
            {'change': '14.0', 'time': 1794499249195}], 'plans': {}})
        self.assertTrue(client.get_points())
        self.assertEqual(client.points_change, '+14')
        self.assertIn('2026-11-13 00:00:49', client.points_change_time)
        client.req.return_value['history'] = []
        client.get_points()
        self.assertEqual(client.points_change, '?')

    def test_decimal_points_and_changes_are_not_truncated(self):
        client = checkin.GLaDOS(COOKIE)
        client.req = mock.Mock(return_value={
            'points': '15.5',
            'history': [{'change': '1.5', 'time': TODAY_MS}],
            'plans': {'plan100': {'points': 100, 'days': 10}},
        })
        with mock.patch('checkin.beijing_now', return_value=FIXED_NOW):
            self.assertTrue(client.get_points())
        self.assertEqual(client.points, '15.5')
        self.assertEqual(client.points_change, '+1.5')
        self.assertIn('差84.5分', client.exchange_info)

    def test_invalid_time_is_not_echoed(self):
        for value in ['secret', float('inf'), True, 10**18, None]:
            client = checkin.GLaDOS(COOKIE)
            client.req = mock.Mock(return_value={'points': '15', 'history': [
                {'change': '14', 'time': value}], 'plans': {}})
            client.get_points()
            self.assertEqual(client.points_change_time, '未知')

    def test_failure_and_repeat_notification_do_not_present_old_gain_as_current(self):
        for result, expected_exit in [
            ({'code': 5, 'reason': 'turnstile'}, 1),
            ({'code': 1, 'message': "Today's observation logged."}, 0),
            ({'code': 0, 'message': 'Checkin! Got 14 Points'}, 0),
        ]:
            client = checkin.GLaDOS(COOKIE)
            client.checkin = mock.Mock(return_value=result)
            client.get_status = mock.Mock(return_value=True)
            client.req = mock.Mock(return_value={'points': '15', 'history': [
                {'change': '14', 'time': 1794499249195}], 'plans': {}})
            with mock.patch('checkin.beijing_now', return_value=FIXED_NOW), \
                    mock.patch.dict(os.environ, {'GLADOS_COOKIE': COOKIE,
                    'EXCHANGE_PLAN': 'off', 'CHECKIN_MAX_ATTEMPTS': '1',
                    'GLADOS_BROWSER_CHECKIN': '0',
                    'PUSHPLUS_TOKEN': 'fake-token', 'PUSH_LEVEL': 'always'}, clear=True), \
                    mock.patch('checkin.GLaDOS', return_value=client), \
                    mock.patch('checkin.pushplus') as push, \
                    mock.patch('checkin.log'), \
                    mock.patch('requests.sessions.Session.request', side_effect=AssertionError('No network')):
                self.assertEqual(checkin.main(), expected_exit)
                content = push.call_args.args[2]
                self.assertIn('历史记录，不代表本次新增', content)
                self.assertIn('2026-11-13 00:00:49', content)
                self.assertNotIn('(+14)', content)
                self.assertNotIn('fake-token', content)

    @mock.patch('checkin.time.sleep')
    def test_turnstile_stops_retries_immediately_and_skips_auto_exchange(self, sleep):
        client = checkin.GLaDOS(COOKIE)
        client.checkin = mock.Mock(return_value={
            'code': 5,
            'reason': 'turnstile',
            'message': 'Cloudflare verification failed. Nothing was recorded — please retry.',
        })
        client.get_status = mock.Mock(return_value=True)
        client.req = mock.Mock(return_value={
            'points': '520',
            'history': [{'change': '14', 'time': 1794499249195}],
            'plans': {},
        })
        client.exchange = mock.Mock()
        with mock.patch('checkin.beijing_now', return_value=FIXED_NOW), \
                mock.patch.dict(os.environ, {
                    'GLADOS_COOKIE': COOKIE,
                    'EXCHANGE_PLAN': 'plan500',
                    'CHECKIN_MAX_ATTEMPTS': '3',
                    'GLADOS_BROWSER_CHECKIN': '0',
                    'PUSHPLUS_TOKEN': 'fake-token',
                    'PUSH_LEVEL': 'fail_only',
                }, clear=True), \
                mock.patch('checkin.GLaDOS', return_value=client), \
                mock.patch('checkin.pushplus') as push, \
                mock.patch('checkin.log'):
            self.assertEqual(checkin.main(), 1)

        client.checkin.assert_called_once()
        sleep.assert_not_called()
        client.exchange.assert_not_called()
        content = push.call_args.args[2]
        self.assertIn('reason=turnstile', content)
        self.assertIn('未确认（最终请求未成功；本轮是否入账未知，请核对完整流水）', content)
        self.assertIn('本次签到未成功，跳过兑换', content)

    def test_cross_check_distinguishes_matched_capped_mismatched_and_repeat_gains(self):
        with mock.patch('checkin.beijing_now', return_value=FIXED_NOW):
            # 1. Exact match between checkin response and today's ledger
            client = checkin.GLaDOS(COOKIE)
            client.req = mock.Mock(return_value={
                'points': '15',
                'history': [{'change': '14.0', 'time': TODAY_MS}],
                'plans': {},
            })
            client.get_points()
            summary = checkin.summarize_current_run_gain(
                {'code': 0, 'message': 'Checkin! Got 14 Points', 'points': 14}, True, client,
            )
            self.assertIn('接口声称 +14 分（本次入账归属未确认）', summary)
            self.assertIn('未关联本次请求', summary)

            # 2. Breakdown sum (+2.7) capped at +2 (Free cap max 2)
            client.req.return_value = {
                'points': '2',
                'history': [{'change': '2', 'time': TODAY_MS}],
                'plans': {},
            }
            client.get_points()
            summary = checkin.summarize_current_run_gain(
                {'code': 0, 'message': 'Checkin! Got 2 Points', 'points': 2, 'breakdown': {'base': 2.7}},
                True, client,
            )
            self.assertIn('+2 分', summary)
            self.assertIn('分项合计 +2.7 分', summary)

            # 3. Declared points mismatch actual ledger entry
            summary = checkin.summarize_current_run_gain(
                {'code': 0, 'message': 'Checkin! Got 7 Points', 'points': 7}, True, client,
            )
            self.assertIn('一笔正变动 +2 分', summary)
            self.assertIn('接口声称 +7 分', summary)
            self.assertIn('本次入账归属未确认', summary)

            # 4. Repeat check-in after manual browser check-in earlier today
            client.req.return_value = {
                'points': '155',
                'history': [{'change': '12', 'time': TODAY_MS}],
                'plans': {},
            }
            client.get_points()
            summary = checkin.summarize_current_run_gain(
                {'code': 1, 'message': "Today's observation logged. Return tomorrow for more points."},
                True, client,
            )
            self.assertIn('不能据此确定本轮新增积分', summary)
            self.assertIn('一笔正变动 +12 分', summary)

    def test_pre_exchange_checkin_gain_is_preserved_after_auto_exchange_deduction(self):
        client = checkin.GLaDOS(COOKIE)
        client.checkin = mock.Mock(return_value={'code': 0, 'message': 'Checkin! Got 11 Points'})
        client.get_status = mock.Mock(return_value=True)
        client.exchange = mock.Mock(return_value={'code': 0, 'message': 'ok'})
        client.req = mock.Mock(side_effect=[
            {'points': '501', 'history': [{'change': '11', 'time': TODAY_MS}], 'plans': {}},
            {'points': '1', 'history': [
                {'change': '-500', 'time': TODAY_MS + 1000, 'business': 'exchange'},
                {'change': '11', 'time': TODAY_MS, 'business': 'checkin'},
            ], 'plans': {}},
        ])
        with mock.patch('checkin.beijing_now', return_value=FIXED_NOW), \
                mock.patch.dict(os.environ, {
                    'GLADOS_COOKIE': COOKIE,
                    'EXCHANGE_PLAN': 'plan500',
                    'CHECKIN_MAX_ATTEMPTS': '1',
                    'PUSHPLUS_TOKEN': 'fake-token',
                    'PUSH_LEVEL': 'fail_only',
                }, clear=True), \
                mock.patch('checkin.GLaDOS', return_value=client), \
                mock.patch('checkin.pushplus') as push, \
                mock.patch('checkin.log'):
            self.assertEqual(checkin.main(), 0)

        content = push.call_args.args[2]
        self.assertIn('接口声称 +11 分（本次入账归属未确认）', content)
        self.assertIn('兑换成功 +100天 (消耗500分)', content)
        self.assertIn('-500（', content)

    def test_notify_status_only_pushes_readonly_card_without_checkin_or_exchange(self):
        client = checkin.GLaDOS(COOKIE)
        client.checkin = mock.Mock(side_effect=AssertionError('checkin must not be called in notify_status_only'))
        client.exchange = mock.Mock(side_effect=AssertionError('exchange must not be called in notify_status_only'))
        client.req = mock.Mock(side_effect=[
            {'code': 0, 'data': {'email': 'readonly@example.test', 'leftDays': '688.0'}},
            {
                'points': '15',
                'history': [{'change': '14.0', 'time': 1794499249195}],
                'plans': {'plan100': {'points': 100, 'days': 10}},
            },
        ])
        with mock.patch('checkin.beijing_now', return_value=FIXED_NOW), \
                mock.patch.dict(os.environ, {
                    'GLADOS_COOKIE': COOKIE,
                    'CHECKIN_NOTIFY_STATUS_ONLY': 'true',
                    'EXCHANGE_PLAN': 'plan500',
                    'PUSH_LEVEL': 'fail_only',
                    'PUSHPLUS_TOKEN': 'fake-token',
                }, clear=True), \
                mock.patch('checkin.GLaDOS', return_value=client), \
                mock.patch('checkin.pushplus', return_value=True) as push, \
                mock.patch('checkin.log') as log_mock, \
                mock.patch('requests.sessions.Session.request', side_effect=AssertionError('No network')):
            self.assertEqual(checkin.main(), 0)

        client.checkin.assert_not_called()
        client.exchange.assert_not_called()
        self.assertEqual(client.req.call_count, 2)
        push.assert_called_once()
        title = push.call_args.args[1]
        content = push.call_args.args[2]
        self.assertIn('GLaDOS状态核对: 只读核对完成 1/1', title)
        self.assertIn('readonly@example.test', content)
        self.assertIn('15', content)
        self.assertNotIn('(+14)', content)
        self.assertIn('本次为只读核对（未发起签到请求）', content)
        self.assertIn('历史记录，不代表本次新增', content)
        self.assertIn('只读核对模式，本次跳过自动兑换', content)
        self.assertNotIn('readonly@example.test', str(log_mock.call_args_list))

    def test_notify_status_only_returns_nonzero_when_no_push_channel_configured(self):
        client = checkin.GLaDOS(COOKIE)
        client.checkin = mock.Mock(side_effect=AssertionError('checkin must not be called'))
        client.req = mock.Mock(side_effect=[
            {'code': 0, 'data': {'email': 'readonly@example.test', 'leftDays': '688.0'}},
            {'points': '15', 'history': [], 'plans': {}},
        ])
        with mock.patch('checkin.beijing_now', return_value=FIXED_NOW), \
                mock.patch.dict(os.environ, {
                    'GLADOS_COOKIE': COOKIE,
                    'CHECKIN_NOTIFY_STATUS_ONLY': 'true',
                }, clear=True), \
                mock.patch('checkin.GLaDOS', return_value=client), \
                mock.patch('checkin.log'):
            self.assertEqual(checkin.main(), 1)


