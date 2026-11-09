import os
import unittest
from unittest import mock

import checkin


COOKIE = 'gld:sess=synthetic-session; gld:sess.sig=synthetic-signature'
USER_AGENT = 'Mozilla/5.0 SyntheticBrowser/1.0'
DENIAL = {
    'code': 4,
    'reason': 'device-mismatch',
    'message': 'Automated check-in detected. Please sign in again to continue.',
}


class OfflineTestCase(unittest.TestCase):
    def setUp(self):
        network = mock.patch(
            'requests.sessions.Session.request',
            side_effect=AssertionError('Live HTTP disabled in regression tests'),
        )
        network.start()
        self.addCleanup(network.stop)


class AuthFailureTests(OfflineTestCase):
    @mock.patch('checkin.time.sleep')
    @mock.patch('checkin.requests.post')
    @mock.patch('checkin.requests.get')
    def test_http_auth_denial_stops_domain_fallback_and_checkin_retries(self, get, post, sleep):
        for status in (401, 403):
            with self.subTest(status=status), mock.patch.dict(os.environ, {}, clear=True):
                post.reset_mock()
                get.reset_mock()
                sleep.reset_mock()
                get.return_value = mock.Mock(status_code=200)
                get.return_value.json.return_value = {'code': 0, 'nonce': 'synthetic-nonce', 'ttl': 300000}
                response = mock.Mock(status_code=status)
                response.json.side_effect = ValueError('synthetic private response body')
                post.return_value = response

                result, success = checkin.checkin_with_retry(checkin.GLaDOS(COOKIE))

                self.assertFalse(success)
                self.assertEqual(result['http_status'], status)
                self.assertEqual(post.call_count, 1)
                self.assertEqual(get.call_count, 1)
                response.json.assert_not_called()
                sleep.assert_called_once_with(2.7)

    def test_explicit_auth_denial_overrides_success_code_or_message(self):
        for result in (
            dict(DENIAL, code=0),
            dict(DENIAL, message="Today's observation logged. Return tomorrow."),
            {'code': 0, 'http_status': 403},
        ):
            with self.subTest(result=result):
                self.assertFalse(checkin.is_normal_checkin_result(result))

    @mock.patch('checkin.log')
    def test_retry_auth_log_does_not_echo_response_or_untrusted_fields(self, log):
        response = dict(
            DENIAL,
            reason='untrusted-private-reason',
            message='Automated check-in detected: ' + COOKIE + ' private@example.test',
        )
        client = mock.Mock()
        client.checkin.return_value = response

        result, success = checkin.checkin_with_retry(client)

        self.assertFalse(success)
        self.assertEqual(result, response)
        self.assertEqual(client.checkin.call_count, 1)
        output = str(log.call_args_list)
        self.assertIn('code=4', output)
        for value in ('synthetic-session', 'synthetic-signature', 'private@example.test',
                      'untrusted-private-reason'):
            self.assertNotIn(value, output)

    @mock.patch('checkin.requests.get')
    def test_transient_http_error_still_falls_back_to_next_domain(self, get):
        unavailable = mock.Mock(status_code=503)
        ok = mock.Mock(status_code=200)
        ok.json.return_value = {'code': 0, 'data': {'leftDays': 123}}
        get.side_effect = [unavailable, ok]
        with mock.patch.dict(os.environ, {}, clear=True):
            client = checkin.GLaDOS(COOKIE)
            result = client.req('GET', '/api/user/status')

        self.assertEqual(result, ok.json.return_value)
        self.assertEqual(get.call_count, 2)
        self.assertEqual(client.domain, checkin.DOMAINS[1])

    @mock.patch('checkin.requests.post')
    @mock.patch('checkin.requests.get')
    @mock.patch('checkin.time.sleep')
    def test_configured_cookie_and_user_agent_reach_checkin_request(self, sleep, get, post):
        get.return_value = mock.Mock(status_code=200)
        get.return_value.json.return_value = {'code': 0, 'nonce': 'synthetic-nonce', 'ttl': 300000}
        post.return_value = mock.Mock(status_code=200)
        post.return_value.json.return_value = DENIAL
        with mock.patch.dict(os.environ, {'GLADOS_USER_AGENT': USER_AGENT}, clear=True):
            self.assertEqual(checkin.GLaDOS(COOKIE).checkin(), DENIAL)

        headers = post.call_args.kwargs['headers']
        self.assertEqual(headers['Cookie'], COOKIE)
        self.assertEqual(headers['User-Agent'], USER_AGENT)


class AuthMainTests(OfflineTestCase):
    def run_main(self, client, environment=None):
        config = {
            'GLADOS_COOKIE': COOKIE,
            'GLADOS_USER_AGENT': USER_AGENT,
            'EXCHANGE_PLAN': 'plan500',
        }
        config.update(environment or {})
        with mock.patch.dict(os.environ, config, clear=True), \
                mock.patch('checkin.GLaDOS', return_value=client), \
                mock.patch('checkin.log') as log, \
                mock.patch('checkin.pushplus') as pushplus, \
                mock.patch('checkin.telegram_push') as telegram:
            exit_code = checkin.main()
        return exit_code, log, pushplus, telegram

    def test_auth_denial_stops_followup_reads_and_exchange(self):
        client = mock.Mock()
        client.checkin.return_value = dict(DENIAL, message=DENIAL['message'] + COOKIE)
        client.points = '600'
        client.email = 'private@example.test'
        exit_code, log, pushplus, telegram = self.run_main(client)

        self.assertEqual(exit_code, 1)
        client.checkin.assert_called_once_with()
        client.get_status.assert_not_called()
        client.get_points.assert_not_called()
        client.exchange.assert_not_called()
        pushplus.assert_not_called()
        telegram.assert_not_called()
        output = str(log.call_args_list)
        self.assertIn('reason=device-mismatch', output)
        for value in ('synthetic-session', 'synthetic-signature', 'private@example.test'):
            self.assertNotIn(value, output)

    def test_normal_success_still_reads_account_and_exchanges(self):
        client = checkin.GLaDOS(COOKIE)
        client.points = '500'
        client.checkin = mock.Mock(return_value={'code': 0, 'message': 'Checkin! Got 1 Point'})
        client.get_status = mock.Mock()
        client.get_points = mock.Mock()
        client.exchange = mock.Mock(return_value={'code': 0, 'message': 'ok'})

        exit_code, _, _, _ = self.run_main(client)

        self.assertEqual(exit_code, 0)
        client.exchange.assert_called_once_with('plan500')
        self.assertEqual(client.get_status.call_count, 2)
        self.assertEqual(client.get_points.call_count, 2)

    def test_denied_account_does_not_prevent_next_account_checkin(self):
        denied = checkin.GLaDOS(COOKIE)
        allowed = checkin.GLaDOS(COOKIE)
        denied.checkin = mock.Mock(return_value=DENIAL)
        allowed.checkin = mock.Mock(return_value={'code': 0, 'message': 'Checkin! Got 1 Point'})
        for client in (denied, allowed):
            client.get_status = mock.Mock()
            client.get_points = mock.Mock()
            client.exchange = mock.Mock()
        with mock.patch.dict(os.environ, {
            'GLADOS_COOKIE': COOKIE + '\n' + COOKIE,
            'EXCHANGE_PLAN': 'off',
        }, clear=True), mock.patch('checkin.GLaDOS', side_effect=[denied, allowed]), \
                mock.patch('checkin.log'):
            self.assertEqual(checkin.main(), 1)

        denied.get_status.assert_not_called()
        denied.get_points.assert_not_called()
        denied.exchange.assert_not_called()
        allowed.checkin.assert_called_once_with()
        allowed.get_status.assert_called_once_with()
        allowed.get_points.assert_called_once_with()

    def test_normal_run_reports_only_user_agent_configuration_presence(self):
        for agent, expected in ((USER_AGENT, '已配置'), ('', '未配置')):
            with self.subTest(configured=bool(agent)):
                client = checkin.GLaDOS(COOKIE)
                client.checkin = mock.Mock(return_value=DENIAL)
                client.get_status = mock.Mock(return_value=False)
                client.get_points = mock.Mock(return_value=False)
                exit_code, log, _, _ = self.run_main(client, {'GLADOS_USER_AGENT': agent})

                self.assertEqual(exit_code, 1)
                output = str(log.call_args_list)
                self.assertIn('User-Agent', output)
                self.assertIn(expected, output)
                self.assertNotIn(USER_AGENT, output)

    @mock.patch('checkin.log')
    @mock.patch('checkin.requests.get')
    def test_read_only_diagnostic_reports_http_denial_without_writes(self, get, log):
        get.return_value = mock.Mock(status_code=403)
        with mock.patch.dict(os.environ, {}, clear=True), \
                mock.patch('checkin.requests.post') as post:
            result = checkin.diagnose_accounts([COOKIE])

        self.assertEqual(result, 1)
        self.assertEqual(get.call_count, 1)
        post.assert_not_called()
        output = str(log.call_args_list)
        self.assertIn('http_status=403', output)
        self.assertNotIn('synthetic-session', output)


if __name__ == '__main__':
    unittest.main()
