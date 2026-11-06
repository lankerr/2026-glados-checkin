import os
import unittest
from pathlib import Path
from unittest import mock

import checkin


USER_AGENT = (
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
    'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/154.0.0.0 Safari/537.36'
)
COOKIE = 'gld:sess=synthetic-private-session; gld:sess.sig=synthetic-private-signature'


class UserAgentNormalizationTests(unittest.TestCase):
    def test_valid_browser_values_and_comments_are_preserved(self):
        for value in (
            USER_AGENT,
            'Mozilla/5.0 (X11; Linux x86_64; rv:144.0) Gecko/20100101 Firefox/144.0',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) Version/26.0 Safari/605.1.15',
            USER_AGENT + ' Edg/154.0.0.0',
            'Synthetic/1.0 (a "quoted" comment)',
            'Synthetic/1.0\tOther/2.0',
            "Synthetic/1.0 'Brand'",
            "Synthetic/1.0'",
            "'Synthetic/1.0",
            "'Synthetic/1.0'",
            "'Brand'",
        ):
            with self.subTest(value=value):
                self.assertEqual(checkin.normalize_user_agent(value), (value, False))

    def test_empty_and_outer_whitespace_keep_existing_behavior(self):
        for value in ('', ' \t\r\n '):
            self.assertEqual(checkin.normalize_user_agent(value), ('', False))
        self.assertEqual(checkin.normalize_user_agent(' \t' + USER_AGENT + '\n '), (USER_AGENT, False))

    def test_single_pair_of_ascii_quotes_and_header_prefix_are_removed(self):
        for value in (
            '"' + USER_AGENT + '"',
            "'" + USER_AGENT + "'",
            'User-Agent: ' + USER_AGENT,
            'user-agent:\t' + USER_AGENT,
            'USER-AGENT: "' + USER_AGENT + '"',
            'User-Agent: ' + "'" + USER_AGENT + "'",
            '"User-Agent: ' + USER_AGENT + '"',
            "'user-agent: " + USER_AGENT + "'",
        ):
            with self.subTest(value=value):
                self.assertEqual(checkin.normalize_user_agent(value), (USER_AGENT, True))

    def test_invalid_values_raise_without_echoing_input(self):
        private = 'SyntheticPrivateBrowser/1.0'
        for value in (
            private + '\nHeader: injected',
            private + '\rHeader: injected',
            private + '\x00',
            private + '\x01',
            private + '\x0b',
            '\x0c' + private,
            private + '\x7f',
            '“' + private + '”',
            private + ' 中文说明',
            '"' + private,
            '"' + private + "'",
            '""' + private + '""',
            'User-Agent: User-Agent: ' + private,
            'User-Agent:',
            '""',
            "''",
            'User-Agent: ""',
        ):
            with self.subTest(value=value):
                with self.assertRaises(checkin.UserAgentConfigurationError) as error:
                    checkin.normalize_user_agent(value)
                self.assertNotIn(private, str(error.exception))

    def test_configured_headers_use_normalized_value_and_matching_hints(self):
        with mock.patch.dict(os.environ, {'GLADOS_USER_AGENT': 'User-Agent: "' + USER_AGENT + '"'}, clear=True):
            headers = checkin.get_browser_headers()
        self.assertEqual(headers['User-Agent'], USER_AGENT)
        self.assertIn('v="154"', headers['Sec-CH-UA'])
        self.assertEqual(headers['Sec-CH-UA-Platform'], '"macOS"')

    def test_empty_value_still_uses_default(self):
        for environment in ({}, {'GLADOS_USER_AGENT': ''}, {'GLADOS_USER_AGENT': ' \t\n '}):
            with mock.patch.dict(os.environ, environment, clear=True):
                self.assertEqual(checkin.get_browser_headers()['User-Agent'], checkin.DEFAULT_USER_AGENT)

    def test_normalized_value_survives_requests_preparation(self):
        for raw in (USER_AGENT, '"' + USER_AGENT + '"', 'User-Agent: "' + USER_AGENT + '"'):
            with self.subTest(raw=raw), mock.patch.dict(os.environ, {'GLADOS_USER_AGENT': raw}, clear=True):
                # Preparing an HTTP request does not send it or open a connection.
                request = checkin.requests.Request(
                    'GET', 'https://example.test/', headers=checkin.get_browser_headers(),
                ).prepare()
                self.assertEqual(request.headers['User-Agent'], USER_AGENT)


class UserAgentFlowTests(unittest.TestCase):
    def setUp(self):
        for patch in (
            mock.patch.dict(os.environ, {}, clear=True),
            mock.patch('requests.sessions.Session.request', side_effect=AssertionError('Live HTTP disabled')),
        ):
            patch.start()
            self.addCleanup(patch.stop)

    def test_normalized_value_reaches_get_json_post_and_form_post(self):
        for raw in (USER_AGENT, '"' + USER_AGENT + '"', 'User-Agent: ' + USER_AGENT):
            with self.subTest(raw=raw), mock.patch.dict(os.environ, {'GLADOS_USER_AGENT': raw}), \
                    mock.patch('checkin.requests.get') as get, \
                    mock.patch('checkin.requests.post') as post:
                for call in (get, post):
                    call.return_value = mock.Mock(status_code=200)
                    call.return_value.json.return_value = {'code': 0, 'data': {'leftDays': 1}}
                get.side_effect = [
                    get.return_value,
                    mock.Mock(status_code=200, **{'json.return_value': {
                        'code': 0, 'nonce': 'synthetic-nonce', 'ttl': 300000,
                    }}),
                ]
                client = checkin.GLaDOS(COOKIE)
                client.req('GET', '/api/user/status')
                with mock.patch('checkin.time.sleep'):
                    client.checkin()
                client.exchange('plan500')
                for call in get.call_args_list + post.call_args_list:
                    self.assertEqual(call.kwargs['headers']['User-Agent'], USER_AGENT)
                    self.assertEqual(call.kwargs['headers']['Cookie'], COOKIE)
                self.assertEqual(get.call_count, 2)
                self.assertEqual(post.call_count, 2)
                self.assertNotIn('Content-Type', post.call_args.kwargs['headers'])

    def test_invalid_configuration_stops_direct_request_before_http(self):
        with mock.patch.dict(os.environ, {'GLADOS_USER_AGENT': USER_AGENT + '\nBroken'}), \
                mock.patch('checkin.requests.get') as get, \
                mock.patch('checkin.requests.post') as post, \
                mock.patch('checkin.time.sleep') as sleep:
            with self.assertRaises(checkin.UserAgentConfigurationError):
                checkin.checkin_with_retry(checkin.GLaDOS(COOKIE))
        get.assert_not_called()
        post.assert_not_called()
        sleep.assert_not_called()

    def test_normal_and_diagnostic_main_fail_before_client_or_notifications(self):
        for mode in ('false', 'true'):
            for raw in (USER_AGENT + '\nBroken', '"' + USER_AGENT, 'User-Agent:'):
                with self.subTest(mode=mode, raw=raw), mock.patch.dict(os.environ, {
                    'GLADOS_COOKIE': COOKIE,
                    'GLADOS_USER_AGENT': raw,
                    'CHECKIN_DIAGNOSTIC_ONLY': mode,
                    'SERVERCHAN_SENDKEY': 'SCTsynthetic-private-key',
                    'PUSHPLUS_TOKEN': 'synthetic-private-token',
                    'TELEGRAM_BOT_TOKEN': 'synthetic-private-token',
                    'TELEGRAM_CHAT_ID': 'synthetic-private-chat',
                }), mock.patch('checkin.GLaDOS') as client, \
                        mock.patch('checkin.log') as log, \
                        mock.patch('checkin.pushplus') as pushplus, \
                        mock.patch('checkin.serverchan_push') as serverchan, \
                        mock.patch('checkin.telegram_push') as telegram:
                    self.assertEqual(checkin.main(), 1)
                    client.assert_not_called()
                    pushplus.assert_not_called()
                    serverchan.assert_not_called()
                    telegram.assert_not_called()
                    output = str(log.call_args_list)
                    self.assertIn('User-Agent 配置错误', output)
                    for private in (USER_AGENT, COOKIE, 'synthetic-private'):
                        self.assertNotIn(private, output)

    def test_normalization_notice_is_sanitized_and_does_not_mutate_environment(self):
        raw = 'User-Agent: "' + USER_AGENT + '"'
        with mock.patch.dict(os.environ, {'GLADOS_USER_AGENT': raw}), mock.patch('checkin.log') as log:
            self.assertTrue(checkin.log_user_agent_configuration())
            self.assertEqual(os.environ['GLADOS_USER_AGENT'], raw)
        output = str(log.call_args_list)
        self.assertIn('已配置', output)
        self.assertIn('已自动去除', output)
        self.assertNotIn(USER_AGENT, output)


class UserAgentWorkflowTests(unittest.TestCase):
    def test_workflow_falls_back_to_secret_without_changing_variable_precedence(self):
        workflow = (Path(__file__).resolve().parents[1] / '.github/workflows/checkin.yml').read_text(encoding='utf-8')
        lines = [line.strip() for line in workflow.splitlines() if 'GLADOS_USER_AGENT:' in line]
        self.assertEqual(lines, [
            'GLADOS_USER_AGENT: ${{ vars.GLADOS_USER_AGENT || secrets.GLADOS_USER_AGENT }}'
        ])

    def test_resolved_variable_secret_combinations_are_accepted(self):
        # Model the documented GitHub || resolution after checking its exact expression
        # above. This is an offline contract test, not a GitHub Actions engine run.
        for variable, secret, expected in (
            (USER_AGENT, '', USER_AGENT),
            ('', USER_AGENT, USER_AGENT),
            (USER_AGENT, 'OtherBrowser/1.0', USER_AGENT),
            ('', '', checkin.DEFAULT_USER_AGENT),
            ('   ', USER_AGENT, checkin.DEFAULT_USER_AGENT),
        ):
            with self.subTest(variable=bool(variable), secret=bool(secret)), \
                    mock.patch.dict(os.environ, {'GLADOS_USER_AGENT': variable or secret}, clear=True):
                self.assertEqual(checkin.get_browser_headers()['User-Agent'], expected)


if __name__ == '__main__':
    unittest.main()
