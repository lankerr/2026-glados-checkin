import io
import json
import os
import unittest
from unittest import mock

import checkin


class FakeClient:
    def __init__(self, results):
        self.results = iter(results)
        self.calls = 0

    def checkin(self):
        self.calls += 1
        return next(self.results)


class CheckinLoggingTests(unittest.TestCase):
    def test_log_reaches_buffered_output_before_returning(self):
        with io.TextIOWrapper(io.BytesIO(), encoding='utf-8', newline='\n') as stream, \
                mock.patch('checkin.sys.stdout', stream), \
                mock.patch('checkin.beijing_time', return_value='2026-11-06 12:00:00'):
            checkin.log('offline check')
            self.assertEqual(
                stream.buffer.getvalue().decode('utf-8'),
                '[2026-11-06 12:00:00 北京时间] offline check\n',
            )


class CheckinResultTests(unittest.TestCase):
    def test_current_observation_message_is_normal(self):
        result = {
            'code': 1,
            'message': "Today's observation logged. Return tomorrow for more points.",
        }
        self.assertTrue(checkin.is_normal_checkin_result(result))

    def test_historic_success_message_is_normal(self):
        self.assertTrue(
            checkin.is_normal_checkin_result({'code': 0, 'message': 'Checkin! Got 15 Points'})
        )

    def test_unknown_error_is_failure(self):
        self.assertFalse(checkin.is_normal_checkin_result({'code': 2, 'message': 'Cookie expired'}))

    def test_permission_failure_is_not_retryable(self):
        self.assertTrue(
            checkin.is_non_retryable_checkin_result({'code': -2, 'message': '没有权限'})
        )

    def test_device_mismatch_is_not_retryable(self):
        self.assertTrue(
            checkin.is_non_retryable_checkin_result(
                {'code': 4, 'reason': 'device-mismatch', 'message': 'denied'}
            )
        )

    @mock.patch('checkin.time.sleep')
    def test_retry_stops_after_success(self, sleep):
        client = FakeClient([
            None,
            {'code': 0, 'message': 'Checkin! Got 15 Points'},
        ])

        result, success = checkin.checkin_with_retry(client, attempts=3, delay_seconds=1)

        self.assertTrue(success)
        self.assertEqual(result['code'], 0)
        self.assertEqual(client.calls, 2)
        sleep.assert_called_once_with(1)

    @mock.patch('checkin.time.sleep')
    def test_retry_stops_immediately_for_auth_failure(self, sleep):
        client = FakeClient([
            {'code': -2, 'message': '没有权限'},
            {'code': 0, 'message': 'Checkin! Got 15 Points'},
        ])

        result, success = checkin.checkin_with_retry(client, attempts=3, delay_seconds=1)

        self.assertFalse(success)
        self.assertEqual(result['code'], -2)
        self.assertEqual(client.calls, 1)
        sleep.assert_not_called()

    @mock.patch('checkin.time.sleep')
    def test_automated_detection_without_reason_does_not_retry(self, sleep):
        failure = {
            'code': 4,
            'message': 'Automated check-in detected. Please sign in again to continue.',
        }
        client = FakeClient([failure])

        result, success = checkin.checkin_with_retry(client, attempts=3)

        self.assertFalse(success)
        self.assertEqual(result, failure)
        self.assertEqual(client.calls, 1)
        sleep.assert_not_called()


class BrowserHeaderTests(unittest.TestCase):
    def test_custom_chrome_user_agent_builds_matching_client_hints(self):
        user_agent = (
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
            'AppleWebKit/537.36 (KHTML, like Gecko) '
            'Chrome/154.0.0.0 Safari/537.36'
        )
        with mock.patch.dict(os.environ, {'GLADOS_USER_AGENT': user_agent}):
            headers = checkin.get_browser_headers()

        self.assertEqual(headers['User-Agent'], user_agent)
        self.assertIn('v="154"', headers['Sec-CH-UA'])
        self.assertEqual(headers['Sec-CH-UA-Mobile'], '?0')
        self.assertEqual(headers['Sec-CH-UA-Platform'], '"macOS"')

    def test_empty_user_agent_uses_compatible_default(self):
        with mock.patch.dict(os.environ, {'GLADOS_USER_AGENT': ''}):
            headers = checkin.get_browser_headers()

        self.assertEqual(headers['User-Agent'], checkin.DEFAULT_USER_AGENT)


class CookieTests(unittest.TestCase):
    def test_json_token_uses_real_cookie_name(self):
        self.assertEqual(checkin.extract_cookie('{"token":"abc"}'), 'koa:sess=abc')

    def test_missing_configuration_returns_no_accounts(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertEqual(checkin.get_cookies(), [])

    def test_current_signed_session_is_detected(self):
        cookie = 'koa:sess=old; gld:sess=current; gld:sess.sig=signature'

        self.assertEqual(checkin.get_session_cookie_kind(cookie), 'gld')

    def test_legacy_signed_session_is_detected(self):
        cookie = 'koa:sess=old; koa:sess.sig=signature'

        self.assertEqual(checkin.get_session_cookie_kind(cookie), 'koa')

    def test_incomplete_current_session_is_not_accepted(self):
        self.assertIsNone(checkin.get_session_cookie_kind('gld:sess=current'))

    def test_cookie_editor_json_export_preserves_current_session(self):
        raw = json.dumps([
            {'name': 'koa:sess', 'value': 'old'},
            {'name': 'gld:sess', 'value': 'current'},
            {'name': 'gld:sess.sig', 'value': 'signature'},
        ])

        cookie = checkin.extract_cookie(raw)

        self.assertIn('gld:sess=current', cookie)
        self.assertEqual(checkin.get_session_cookie_kind(cookie), 'gld')

    def test_get_cookies_preserves_formatted_json_as_one_account(self):
        raw = json.dumps([
            {'name': 'gld:sess', 'value': 'current'},
            {'name': 'gld:sess.sig', 'value': 'signature'},
        ], indent=2)

        with mock.patch.dict(os.environ, {'GLADOS_COOKIE': raw}):
            self.assertEqual(
                checkin.get_cookies(),
                ['gld:sess=current; gld:sess.sig=signature'],
            )

    def test_get_cookies_preserves_ampersands_in_json_values(self):
        raw = json.dumps([
            {'name': 'gld:sess', 'value': 'current'},
            {'name': 'gld:sess.sig', 'value': 'signature'},
            {'name': 'preferences', 'value': 'a&b'},
        ])

        with mock.patch.dict(os.environ, {'GLADOS_COOKIE': raw}):
            self.assertEqual(
                checkin.get_cookies(),
                ['gld:sess=current; gld:sess.sig=signature; preferences=a&b'],
            )

    def test_get_cookies_parses_formatted_legacy_token_json(self):
        raw = json.dumps({'token': 'legacy'}, indent=2)
        with mock.patch.dict(os.environ, {'GLADOS_COOKIE': raw}):
            self.assertEqual(checkin.get_cookies(), ['koa:sess=legacy'])

    def test_get_cookies_rejects_malformed_json(self):
        with mock.patch.dict(os.environ, {'GLADOS_COOKIE': '[\n{\n'}):
            self.assertEqual(checkin.get_cookies(), [])

    def test_get_cookies_preserves_multiple_cookie_headers(self):
        cookies = [
            'gld:sess=first; gld:sess.sig=first-signature',
            'gld:sess=second; gld:sess.sig=second-signature',
        ]
        for separator in ('\n', '&'):
            with self.subTest(separator=separator):
                with mock.patch.dict(os.environ, {'GLADOS_COOKIE': separator.join(cookies)}):
                    self.assertEqual(checkin.get_cookies(), cookies)

    def test_cookie_header_prefix_is_removed(self):
        raw = 'Cookie: gld:sess=current; gld:sess.sig=signature'

        self.assertEqual(
            checkin.extract_cookie(raw),
            'gld:sess=current; gld:sess.sig=signature',
        )

    @mock.patch('checkin.requests.get')
    def test_full_cookie_header_is_forwarded_to_api(self, request_get):
        response = mock.Mock(status_code=200)
        response.json.return_value = {'code': 0, 'data': {}}
        request_get.return_value = response
        cookie = (
            'koa:sess=legacy; koa:sess.sig=legacy-signature; '
            'gld:sess=current; gld:sess.sig=current-signature; tracking=optional'
        )

        result = checkin.GLaDOS(cookie).req('GET', '/api/user/status')

        self.assertEqual(result['code'], 0)
        self.assertEqual(request_get.call_args.kwargs['headers']['Cookie'], cookie)


class FakeGLaDOS:
    def __init__(self, points, exchange_response):
        self.points = points
        self.exchange_response = exchange_response
        self.refresh_calls = 0

    def exchange(self, plan):
        self.plan_sent = plan
        return self.exchange_response

    def get_status(self):
        self.refresh_calls += 1

    def get_points(self):
        self.refresh_calls += 1


class ExchangePlanTests(unittest.TestCase):
    def test_defaults_to_plan500(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertEqual(checkin.get_exchange_plan(), 'plan500')

    def test_off_disables_exchange(self):
        with mock.patch.dict(os.environ, {'EXCHANGE_PLAN': 'off'}):
            self.assertIsNone(checkin.get_exchange_plan())

    def test_invalid_value_disables_exchange(self):
        with mock.patch.dict(os.environ, {'EXCHANGE_PLAN': 'plan999'}):
            self.assertIsNone(checkin.get_exchange_plan())


class AutoExchangeTests(unittest.TestCase):
    def test_exchanges_and_refreshes_when_points_reach_threshold(self):
        client = FakeGLaDOS('500', {'code': 0, 'message': 'ok'})

        result = checkin.auto_exchange(client, 'plan500')

        self.assertEqual(client.plan_sent, 'plan500')
        self.assertIn('兑换成功', result)
        self.assertIn('+100天', result)
        self.assertEqual(client.refresh_calls, 2)

    def test_skips_when_points_below_threshold(self):
        client = FakeGLaDOS('499', {'code': 0, 'message': 'ok'})

        result = checkin.auto_exchange(client, 'plan500')

        self.assertFalse(hasattr(client, 'plan_sent'))
        self.assertIn('积分不足', result)

    def test_reports_failure_without_refresh(self):
        client = FakeGLaDOS('600', {'code': 1, 'message': 'denied'})

        result = checkin.auto_exchange(client, 'plan500')

        self.assertIn('兑换失败', result)
        self.assertIn('denied', result)
        self.assertEqual(client.refresh_calls, 0)

    def test_unreadable_points_is_reported(self):
        client = FakeGLaDOS('?', {'code': 0, 'message': 'ok'})

        result = checkin.auto_exchange(client, 'plan500')

        self.assertIn('积分查询失败', result)
        self.assertFalse(hasattr(client, 'plan_sent'))


class DiagnosticTests(unittest.TestCase):
    @mock.patch('checkin.log')
    @mock.patch('checkin.requests.get')
    def test_request_error_does_not_expose_cookie(self, request_get, log):
        cookie = 'gld:sess=private-cookie; gld:sess.sig=private-signature'
        request_get.side_effect = checkin.requests.exceptions.InvalidHeader(cookie)

        result = checkin.GLaDOS(cookie).req('GET', '/api/user/status')
        self.assertTrue(result['request_failed'])
        self.assertTrue(result['invalid_headers'])
        self.assertNotIn('private-cookie', str(result))
        self.assertNotIn('private-signature', str(result))

        printed = str(log.call_args_list)
        self.assertIn('InvalidHeader', printed)
        self.assertNotIn('private-cookie', printed)
        self.assertNotIn('private-signature', printed)

    @mock.patch('checkin.log')
    @mock.patch('checkin.telegram_push')
    @mock.patch('checkin.pushplus')
    @mock.patch('checkin.GLaDOS')
    def test_diagnostic_queries_status_without_writes_or_private_logs(
        self, client_class, pushplus, telegram, log,
    ):
        cookie = 'gld:sess=private-cookie; gld:sess.sig=private-signature'
        client = client_class.return_value
        client.req.return_value = {
            'code': 0,
            'data': {'email': 'private@example.test', 'leftDays': '123'},
        }
        with mock.patch.dict(os.environ, {
            'GLADOS_COOKIE': cookie,
            'CHECKIN_DIAGNOSTIC_ONLY': 'true',
            'PUSHPLUS_TOKEN': 'private-token',
            'EXCHANGE_PLAN': 'plan500',
        }):
            self.assertEqual(checkin.main(), 0)

        client.req.assert_called_once_with('GET', '/api/user/status')
        client.checkin.assert_not_called()
        client.exchange.assert_not_called()
        pushplus.assert_not_called()
        telegram.assert_not_called()
        printed = str(log.call_args_list)
        for private in ('private-cookie', 'private-signature', 'private@example.test', 'private-token'):
            self.assertNotIn(private, printed)

    @mock.patch('checkin.GLaDOS')
    def test_diagnostic_auth_and_malformed_responses_fail(self, client_class):
        for response in (
            None, [], {'code': -2, 'message': '没有权限'},
            {'code': 0, 'data': None}, {'code': 0, 'data': {}},
            {'code': -2, 'data': {'email': 'private@example.test'}},
        ):
            with self.subTest(response=response):
                client_class.return_value.req.return_value = response
                self.assertEqual(checkin.diagnose_accounts(['synthetic-cookie']), 1)

    @mock.patch('checkin.GLaDOS')
    def test_diagnostic_reports_failure_if_any_account_fails(self, client_class):
        client_class.return_value.req.side_effect = [
            {'code': 0, 'data': {'leftDays': 123}},
            {'code': -2, 'message': '没有权限'},
        ]
        self.assertEqual(checkin.diagnose_accounts(['synthetic-first', 'synthetic-second']), 1)
        self.assertEqual(client_class.return_value.req.call_count, 2)


if __name__ == '__main__':
    unittest.main()
