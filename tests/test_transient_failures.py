import os
import unittest
from unittest import mock

import checkin


COOKIE = 'gld:sess=private-session; gld:sess.sig=private-signature'
FAILURE = {'request_failed': True, 'reason': 'request-failed', 'http_status': 500}


class TransientFailureTests(unittest.TestCase):
    def setUp(self):
        for patch in (
            mock.patch.dict(os.environ, {
                'GLADOS_COOKIE': COOKIE,
                'EXCHANGE_PLAN': 'plan500',
                'CHECKIN_MAX_ATTEMPTS': '2',
                'PUSHPLUS_TOKEN': 'private-push-token',
            }, clear=True),
            mock.patch('requests.sessions.Session.request',
                       side_effect=AssertionError('Live HTTP disabled')),
        ):
            patch.start()
            self.addCleanup(patch.stop)

    @mock.patch('checkin.log')
    @mock.patch('checkin.requests.post')
    def test_server_error_and_timeouts_preserve_only_safe_metadata(self, post, log):
        response = mock.Mock(status_code=500)
        response.json.return_value = {'message': COOKIE}
        post.side_effect = [response] + [
            checkin.requests.ReadTimeout(COOKIE) for _ in checkin.DOMAINS[1:]
        ]

        result = checkin.GLaDOS(COOKIE).req('POST', '/api/user/checkin')

        self.assertEqual(post.call_count, len(checkin.DOMAINS))
        response.json.assert_not_called()
        self.assertEqual(result['http_status'], 500)
        self.assertTrue(result['timed_out'])
        self.assertFalse(checkin.is_non_retryable_checkin_result(result))
        self.assertFalse(checkin.is_normal_checkin_result(result))
        summary = checkin.summarize_checkin_failure(result)
        self.assertIn('网络或服务暂时异常', summary)
        self.assertIn('http_status=500', summary)
        self.assertIn('timeout=true', summary)
        for private in ('private-session', 'private-signature'):
            self.assertNotIn(private, str(result) + str(log.call_args_list) + summary)

    @mock.patch('checkin.requests.post')
    def test_fallback_success_discards_previous_failure_metadata(self, post):
        unavailable = mock.Mock(status_code=503)
        ok = mock.Mock(status_code=200)
        ok.json.return_value = {'code': 0, 'message': 'Checkin! Got 11 Points'}
        post.side_effect = [unavailable, ok]

        result = checkin.GLaDOS(COOKIE).req('POST', '/api/user/checkin')

        self.assertEqual(result, ok.json.return_value)
        self.assertNotIn('request_failed', result)
        self.assertTrue(checkin.is_normal_checkin_result(result))

    @mock.patch('checkin.log')
    @mock.patch('checkin.requests.post')
    def test_invalid_json_or_non_object_response_is_classified_without_body(self, post, log):
        for body in (ValueError(COOKIE), [COOKIE]):
            with self.subTest(body_type=type(body).__name__):
                response = mock.Mock(status_code=200)
                if isinstance(body, ValueError):
                    response.json.side_effect = body
                else:
                    response.json.return_value = body
                post.return_value = response

                result = checkin.GLaDOS(COOKIE).req('POST', '/api/user/checkin')

                self.assertTrue(result['invalid_response'])
                self.assertIn('响应格式异常', checkin.summarize_checkin_failure(result))
                self.assertNotIn('private-session', str(result) + str(log.call_args_list))

    def test_transport_failure_overrides_contradictory_success_fields(self):
        result = dict(FAILURE, code=0, message="Today's observation logged.")
        self.assertFalse(checkin.is_normal_checkin_result(result))

    def client(self, result):
        client = checkin.GLaDOS(COOKIE)
        client.checkin = mock.Mock(return_value=result)
        client.get_status = mock.Mock()
        client.get_points = mock.Mock()
        client.exchange = mock.Mock()
        return client

    @mock.patch('checkin.time.sleep')
    @mock.patch('checkin.log')
    @mock.patch('checkin.pushplus')
    def test_exhausted_failure_stops_followups_and_still_sends_accurate_alert(self, push, log, sleep):
        for result in (FAILURE, None):
            client = self.client(result)
            push.reset_mock()
            sleep.reset_mock()
            with self.subTest(result=result), mock.patch('checkin.GLaDOS', return_value=client):

                self.assertEqual(checkin.main(), 1)

                self.assertEqual(client.checkin.call_count, 2)
                client.get_status.assert_not_called()
                client.get_points.assert_not_called()
                client.exchange.assert_not_called()
                push.assert_called_once()
                title, content = push.call_args.args[1:]
                self.assertIn('本次运行失败 0/1', title)
                self.assertIn('今日签到状态未知', content)
                self.assertIn('未获取', content)
                self.assertIn('跳过积分查询和兑换', content)
                self.assertIn('北京时间 UTC+8', content)
                self.assertNotIn('private-session', content + str(log.call_args_list))
                self.assertNotIn('private-push-token', content)
                sleep.assert_called_once_with(60)

    @mock.patch('checkin.time.sleep')
    @mock.patch('checkin.log')
    @mock.patch('checkin.pushplus')
    def test_one_unavailable_account_does_not_hide_failure_or_block_other_accounts(self, push, log, sleep):
        denied = self.client(FAILURE)
        allowed = self.client({'code': 0, 'message': 'Checkin! Got 12 Points'})
        with mock.patch.dict(os.environ, {
            'GLADOS_COOKIE': COOKIE + '\n' + COOKIE,
            'EXCHANGE_PLAN': 'off',
        }), mock.patch('checkin.GLaDOS', side_effect=[denied, allowed]):
            self.assertEqual(checkin.main(), 1)

        denied.get_status.assert_not_called()
        allowed.checkin.assert_called_once_with()
        allowed.get_status.assert_called_once_with()
        allowed.get_points.assert_called_once_with()
        self.assertIn('本次运行失败 1/2', push.call_args.args[1])

    @mock.patch('checkin.log')
    @mock.patch('checkin.pushplus')
    def test_success_remains_quiet_with_fail_only(self, push, log):
        client = self.client({'code': 1, 'message': "Today's observation logged."})
        with mock.patch.dict(os.environ, {'EXCHANGE_PLAN': 'off'}), \
                mock.patch('checkin.GLaDOS', return_value=client):
            self.assertEqual(checkin.main(), 0)
        push.assert_not_called()

    @mock.patch('checkin.log')
    @mock.patch('checkin.requests.get')
    def test_read_only_timeout_does_not_advise_refreshing_credentials(self, get, log):
        get.side_effect = checkin.requests.ReadTimeout(COOKIE)

        self.assertEqual(checkin.diagnose_accounts([COOKIE]), 1)

        output = str(log.call_args_list)
        self.assertIn('timeout=true', output)
        self.assertNotIn('重新登录', output)
        self.assertNotIn('private-session', output)

if __name__ == '__main__':
    unittest.main()
