"""浏览器兜底通道（Turnstile）的回归测试：全部离线，不起真浏览器。"""

import os
import unittest
from unittest import mock

import checkin
import browser_checkin

COOKIE = 'gld:sess=synthetic-session; gld:sess.sig=synthetic-signature'
TURNSTILE = {
    'code': 5,
    'reason': 'turnstile',
    'message': 'Cloudflare verification failed. Nothing was recorded — please retry.',
}
OK = {'code': 0, 'points': 5, 'message': 'Check in! Got 5 points today.'}
# 显式压掉 CI 标志：测试自身可能跑在 GitHub Actions 里，必须与被测守卫解耦
PLAIN_ENV = {
    'GITHUB_ACTIONS': 'false',
    'GLADOS_USER_AGENT': 'Mozilla/5.0 SyntheticBrowser/1.0',
}


class OfflineTestCase(unittest.TestCase):
    def setUp(self):
        network = mock.patch(
            'requests.sessions.Session.request',
            side_effect=AssertionError('Live HTTP disabled in regression tests'),
        )
        network.start()
        self.addCleanup(network.stop)


class BrowserFallbackTests(OfflineTestCase):
    def make_client(self, api_result):
        client = checkin.GLaDOS(COOKIE)
        client.checkin = mock.Mock(return_value=api_result)
        return client

    def test_turnstile_triggers_browser_fallback_success(self):
        client = self.make_client(TURNSTILE)
        with mock.patch.dict(os.environ, dict(PLAIN_ENV)), \
                mock.patch('browser_checkin.browser_checkin', return_value=dict(OK)) as bc, \
                mock.patch('checkin.log'):
            result, success = checkin.checkin_with_retry(client, 3, 0)
        self.assertTrue(success)
        self.assertEqual(result, OK)
        bc.assert_called_once()
        # Cookie 与 UA 一并传入浏览器，保证设备一致性校验通过
        self.assertEqual(bc.call_args.args[0], COOKIE)
        self.assertIn('SyntheticBrowser', bc.call_args.args[1])

    def test_turnstile_browser_fallback_still_turnstile_reports_failure(self):
        client = self.make_client(TURNSTILE)
        with mock.patch.dict(os.environ, dict(PLAIN_ENV)), \
                mock.patch('browser_checkin.browser_checkin', return_value=dict(TURNSTILE)), \
                mock.patch('checkin.time.sleep'), \
                mock.patch('checkin.log'):
            result, success = checkin.checkin_with_retry(client, 3, 0)
        self.assertFalse(success)
        self.assertEqual(result.get('reason'), 'turnstile')

    def test_browser_exception_is_contained_as_failure(self):
        client = self.make_client(TURNSTILE)
        with mock.patch.dict(os.environ, dict(PLAIN_ENV)), \
                mock.patch('browser_checkin.browser_checkin',
                           side_effect=RuntimeError('boom')), \
                mock.patch('checkin.time.sleep'), \
                mock.patch('checkin.log'):
            result, success = checkin.checkin_with_retry(client, 3, 0)
        self.assertFalse(success)
        self.assertTrue(result.get('request_failed'))

    def test_env_disable_keeps_legacy_stop_behavior(self):
        client = self.make_client(TURNSTILE)
        with mock.patch.dict(os.environ, dict(PLAIN_ENV, GLADOS_BROWSER_CHECKIN='0')), \
                mock.patch('browser_checkin.browser_checkin') as bc, \
                mock.patch('checkin.log'):
            result, success = checkin.checkin_with_retry(client, 3, 0)
        self.assertFalse(success)
        self.assertEqual(result, TURNSTILE)
        bc.assert_not_called()
        client.checkin.assert_called_once()

    def test_normal_api_checkin_never_touches_browser(self):
        client = self.make_client(dict(OK))
        with mock.patch.dict(os.environ, dict(PLAIN_ENV)), \
                mock.patch('browser_checkin.browser_checkin') as bc, \
                mock.patch('checkin.log'):
            result, success = checkin.checkin_with_retry(client, 3, 0)
        self.assertTrue(success)
        bc.assert_not_called()

    def test_github_actions_disables_browser_fallback_by_default(self):
        client = self.make_client(TURNSTILE)
        with mock.patch.dict(os.environ, dict(PLAIN_ENV, GITHUB_ACTIONS='true', GLADOS_BROWSER_CHECKIN='')), \
                mock.patch('browser_checkin.browser_checkin') as bc, \
                mock.patch('checkin.log'):
            result, success = checkin.checkin_with_retry(client, 3, 0)
        self.assertFalse(success)
        self.assertEqual(result, TURNSTILE)
        bc.assert_not_called()

    def test_github_actions_explicit_opt_in_still_uses_browser(self):
        client = self.make_client(TURNSTILE)
        with mock.patch.dict(os.environ, dict(
            PLAIN_ENV, GITHUB_ACTIONS='true', GLADOS_BROWSER_CHECKIN='1')), \
                mock.patch('browser_checkin.browser_checkin', return_value=dict(OK)) as bc, \
                mock.patch('checkin.log'):
            result, success = checkin.checkin_with_retry(client, 3, 0)
        self.assertTrue(success)
        bc.assert_called_once()


class CookieInjectionTests(unittest.TestCase):
    def test_cookies_bind_to_requested_site_only(self):
        for base in ('https://glados.cloud', 'https://glados.rocks'):
            cookies = browser_checkin.parse_cookie_header(COOKIE, base)
            self.assertEqual(len(cookies), 2)
            for c in cookies:
                # url 形式：仅属于目标主机，不做子域通配
                self.assertEqual(c['url'], base + '/')
                self.assertNotIn('domain', c)

    def test_session_cookies_get_protective_attributes(self):
        cookies = browser_checkin.parse_cookie_header(
            COOKIE + '; _ga=GA1.2.x', 'https://glados.cloud')
        by_name = {c['name']: c for c in cookies}
        for name in ('gld:sess', 'gld:sess.sig'):
            self.assertTrue(by_name[name].get('secure'))
            self.assertTrue(by_name[name].get('httpOnly'))
        # 非会话 Cookie 不强加属性
        self.assertNotIn('httpOnly', by_name['_ga'])


if __name__ == '__main__':
    unittest.main()
