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

    def test_verification_waits_for_person_and_never_retries(self):
        for env in ({}, {'GLADOS_BROWSER_CHECKIN': '1'},
                    {'GLADOS_MANUAL_BROWSER': '1', 'GITHUB_ACTIONS': 'true'}):
            with self.subTest(env=env), mock.patch.dict(os.environ, env, clear=True), \
                    mock.patch('browser_checkin.browser_checkin') as browser:
                client = self.make_client(TURNSTILE)
                result, ok = checkin.checkin_with_retry(client, 3, 0)
                self.assertFalse(ok)
                self.assertEqual(result, TURNSTILE)
                client.checkin.assert_called_once()
                browser.assert_not_called()

    @mock.patch.dict(os.environ, {'GLADOS_MANUAL_BROWSER':'1'}, clear=True)
    def test_explicit_foreground_handoff_only_once(self):
        for status, reason in ((False, 'browser-identity-unverified'), (True, 'submission-unknown')):
            with self.subTest(status=status), mock.patch('browser_checkin.browser_checkin',
                    return_value={'request_failed':True, 'reason':'submission-unknown'}) as browser:
                client = self.make_client(TURNSTILE)
                client.get_status = mock.Mock(return_value=status)
                client.email = 'alice@example.invalid'
                result, ok = checkin.checkin_with_retry(client, 3, 0)
                self.assertFalse(ok)
                self.assertEqual(result['reason'], reason)
                self.assertEqual(browser.call_count, int(status))
                client.checkin.assert_called_once()


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
