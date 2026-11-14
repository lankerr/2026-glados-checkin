import os
import unittest
from unittest import mock
import checkin

COOKIE = 'gld:sess=fake; gld:sess.sig=fake'

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
            with mock.patch.dict(os.environ, {'GLADOS_COOKIE': COOKIE,
                    'EXCHANGE_PLAN': 'off', 'CHECKIN_MAX_ATTEMPTS': '1',
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
