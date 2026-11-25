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


class BrowserDetectionTests(unittest.TestCase):
    def test_custom_and_env_path_precedence(self):
        with mock.patch('os.path.exists', return_value=True):
            self.assertEqual(
                browser_checkin.find_browser_executable(custom='/custom/bin/edge'),
                '/custom/bin/edge',
            )
            with mock.patch.dict(os.environ, {'GLADOS_BROWSER_PATH': '/env/bin/chrome'}):
                self.assertEqual(
                    browser_checkin.find_browser_executable(),
                    '/env/bin/chrome',
                )

    def test_which_detection(self):
        with mock.patch('os.path.exists', return_value=False), \
                mock.patch.dict(os.environ, {'GLADOS_BROWSER_PATH': ''}), \
                mock.patch('shutil.which', side_effect=lambda name: '/bin/microsoft-edge' if name == 'microsoft-edge' else None):
            self.assertEqual(
                browser_checkin.find_browser_executable(),
                '/bin/microsoft-edge',
            )

    def test_profile_dir_respects_state_directory(self):
        with mock.patch.dict(os.environ, {'STATE_DIRECTORY': '/var/lib/glados'}):
            self.assertEqual(
                browser_checkin.profile_dir(),
                '/var/lib/glados/glados-checkin-browser',
            )

    def test_log_dir_respects_state_directory(self):
        with mock.patch.dict(os.environ, {'STATE_DIRECTORY': '/var/lib/glados'}), \
                mock.patch('os.makedirs'):
            self.assertEqual(
                browser_checkin.log_dir(),
                '/var/lib/glados/logs',
            )


class CDPEndpointTests(unittest.TestCase):
    def test_browser_ws_url_returned_directly(self):
        ws_url = browser_checkin.resolve_cdp_url('ws://127.0.0.1:9222/devtools/browser')
        self.assertEqual(ws_url, 'ws://127.0.0.1:9222/devtools/browser')

    def test_page_ws_url_rejected_without_reusing_existing_page(self):
        with self.assertRaises(ValueError):
            browser_checkin.resolve_cdp_url('ws://127.0.0.1:9222/devtools/page/abc')

    def test_remote_non_loopback_cdp_urls_are_rejected(self):
        for bad_url in (
            'http://192.168.1.50:9222',
            'https://remote-cdp.example.com:9222',
            'ws://10.0.0.8:9222/devtools/browser',
        ):
            with self.assertRaises(ValueError) as ctx:
                browser_checkin.resolve_cdp_url(bad_url)
            self.assertNotIn('192.168', str(ctx.exception))
            self.assertNotIn('remote-cdp.example.com', str(ctx.exception))
            self.assertNotIn('10.0.0.8', str(ctx.exception))

    def test_http_url_discovers_browser_ws_via_json_version_only(self):
        seen_urls = []
        fake_response = mock.MagicMock()
        fake_response.read.return_value = b'{"webSocketDebuggerUrl": "ws://127.0.0.1:9222/devtools/browser/uuid-1"}'
        fake_response.__enter__.return_value = fake_response
        fake_response.__exit__.return_value = False

        def fake_urlopen(url, timeout=5):
            seen_urls.append(url)
            return fake_response

        with mock.patch('urllib.request.urlopen', side_effect=fake_urlopen):
            ws_url = browser_checkin.resolve_cdp_url('http://localhost:9222')
            self.assertEqual(ws_url, 'ws://127.0.0.1:9222/devtools/browser/uuid-1')
        self.assertEqual(seen_urls, ['http://localhost:9222/json/version'])

    def test_http_url_does_not_fallback_to_existing_pages(self):
        seen_urls = []
        fake_response = mock.MagicMock()
        fake_response.read.return_value = b'{"Browser": "Chrome/145.0.0.0"}'
        fake_response.__enter__.return_value = fake_response
        fake_response.__exit__.return_value = False

        def fake_urlopen(url, timeout=5):
            seen_urls.append(url)
            return fake_response

        with mock.patch('urllib.request.urlopen', side_effect=fake_urlopen):
            with self.assertRaises(RuntimeError):
                browser_checkin.resolve_cdp_url('http://127.0.0.1:9222')
        self.assertEqual(seen_urls, ['http://127.0.0.1:9222/json/version'])


class CDPIsolationAndRedactionTests(unittest.TestCase):
    def test_logs_and_errors_never_leak_cdp_credentials_or_query_tokens(self):
        markers = ('synthuser', 'SYNTHETIC_CDP_SECRET_999', 'SYNTHETIC_QUERY_TOKEN_XYZ')
        urls_and_modes = (
            (
                'http://synthuser:SYNTHETIC_CDP_SECRET_999@127.0.0.1:9222/cdp?token=SYNTHETIC_QUERY_TOKEN_XYZ',
                mock.patch('urllib.request.urlopen', side_effect=OSError('http://synthuser:SYNTHETIC_CDP_SECRET_999@127.0.0.1:9222?token=SYNTHETIC_QUERY_TOKEN_XYZ unreachable')),
            ),
            (
                'ws://synthuser:SYNTHETIC_CDP_SECRET_999@127.0.0.1:9222/devtools/browser?token=SYNTHETIC_QUERY_TOKEN_XYZ',
                mock.patch('browser_checkin.CDPClient', side_effect=RuntimeError('ws://synthuser:SYNTHETIC_CDP_SECRET_999@127.0.0.1:9222/devtools/browser?token=SYNTHETIC_QUERY_TOKEN_XYZ failed')),
            ),
            (
                'http://synthuser:SYNTHETIC_CDP_SECRET_999@192.168.1.99:9222?token=SYNTHETIC_QUERY_TOKEN_XYZ',
                mock.patch('urllib.request.urlopen'),
            ),
        )
        for bad_url, patcher in urls_and_modes:
            logs = []
            with patcher, mock.patch('browser_checkin._log', side_effect=logs.append):
                result = browser_checkin._try_remote_cdp(bad_url, COOKIE, user_agent='Mozilla/5.0')
            self.assertTrue(result.get('request_failed'))
            combined = '\n'.join(logs) + '\n' + str(result.get('detail', ''))
            for marker in markers:
                self.assertNotIn(marker, combined)

    def test_remote_cdp_uses_isolated_browser_context_and_disposes_on_failure(self):
        calls = []

        class FakeCDPClient:
            def __init__(self, ws_url, session_id=None):
                self.ws_url = ws_url
                self.session_id = session_id

            def call(self, method, params=None, timeout=15, use_session=True):
                calls.append((method, params, self.session_id if use_session else None))
                if method == 'Target.createBrowserContext':
                    return {'id': 1, 'result': {'browserContextId': 'ctx-synthetic-1'}}
                if method == 'Target.createTarget':
                    return {'id': 2, 'result': {'targetId': 'target-synthetic-1'}}
                if method == 'Target.attachToTarget':
                    return {'id': 3, 'result': {'sessionId': 'session-synthetic-1'}}
                return {'id': 4, 'result': {}}

            def close(self):
                calls.append(('close', None, None))

        with mock.patch('browser_checkin.CDPClient', FakeCDPClient), \
                mock.patch('browser_checkin._run_cdp_session_with_client', side_effect=RuntimeError('boom')), \
                mock.patch('browser_checkin._log'):
            result = browser_checkin._try_remote_cdp(
                'ws://127.0.0.1:9222/devtools/browser', COOKIE, user_agent='Mozilla/5.0'
            )

        self.assertTrue(result.get('request_failed'))
        methods = [c[0] for c in calls]
        self.assertEqual(methods, [
            'Target.createBrowserContext',
            'Target.createTarget',
            'Target.attachToTarget',
            'Target.closeTarget',
            'Target.disposeBrowserContext',
            'close',
        ])
        self.assertEqual(calls[1][1].get('browserContextId'), 'ctx-synthetic-1')
        self.assertEqual(calls[4][1].get('browserContextId'), 'ctx-synthetic-1')

    def test_cross_account_cdp_sessions_isolate_and_clean_up_cookies(self):
        class AccountFakeCDP:
            def __init__(self):
                self.session_id = 'session-1'
                self.checkin_request_id = None
                self.checkin_loading_finished = False
                self.cookie_jar = {}
                self.deleted = []

            def call(self, method, params=None, timeout=15, use_session=True):
                if method == 'Network.deleteCookies':
                    self.deleted.append((params['name'], params['url']))
                    self.cookie_jar.pop((params['name'], params['url']), None)
                elif method == 'Network.setCookies':
                    for c in params['cookies']:
                        self.cookie_jar[(c['name'], c['url'])] = c['value']
                return {'result': {}}

            def evaluate(self, expr, timeout=5):
                if 'window._glados_checkin_result' in expr:
                    return {'status': 'captured', 'json': dict(OK)}
                return None

        acc1_cookie = 'gld:sess=synthetic-acc1; gld:sess.sig=synthetic-sig1'
        acc2_cookie = 'gld:sess=synthetic-acc2; gld:sess.sig=synthetic-sig2'
        fake_cdp = AccountFakeCDP()

        with mock.patch.object(browser_checkin, 'DOMAINS', ('https://glados.cloud',)), \
                mock.patch('browser_checkin._log'):
            r1 = browser_checkin._run_cdp_session_with_client(fake_cdp, acc1_cookie)
            self.assertEqual(r1, OK)
            # 账号 1 结束后，会话 Cookie 必须已清空
            self.assertEqual(fake_cdp.cookie_jar, {})

            r2 = browser_checkin._run_cdp_session_with_client(fake_cdp, acc2_cookie)
            self.assertEqual(r2, OK)
            self.assertEqual(fake_cdp.cookie_jar, {})

        self.assertIn(('gld:sess', 'https://glados.cloud/'), fake_cdp.deleted)
        self.assertIn(('gld:sess.sig', 'https://glados.cloud/'), fake_cdp.deleted)

    def test_headless_env_overrides_auto_detection(self):
        with mock.patch.dict(os.environ, {'GLADOS_BROWSER_HEADLESS': '0', 'DISPLAY': '', 'WAYLAND_DISPLAY': '', 'GLADOS_BROWSER_ENGINE': 'cdp'}), \
                mock.patch('browser_checkin._run_cdp', return_value={'ok': True}) as mock_cdp:
            browser_checkin.browser_checkin(COOKIE, 'synthetic-ua')
            self.assertFalse(mock_cdp.call_args.args[2])

        with mock.patch.dict(os.environ, {'GLADOS_BROWSER_HEADLESS': '1', 'DISPLAY': ':0', 'GLADOS_BROWSER_ENGINE': 'cdp'}), \
                mock.patch('browser_checkin._run_cdp', return_value={'ok': True}) as mock_cdp:
            browser_checkin.browser_checkin(COOKIE, 'synthetic-ua')
            self.assertTrue(mock_cdp.call_args.args[2])

    def test_pick_page_target_ws_skips_extension_background_pages(self):
        targets = [
            {'type': 'background_page', 'url': 'chrome-extension://abc/_generated_background_page.html', 'webSocketDebuggerUrl': 'ws://127.0.0.1:9222/devtools/page/ext'},
            {'type': 'service_worker', 'url': 'chrome-extension://def/sw.js', 'webSocketDebuggerUrl': 'ws://127.0.0.1:9222/devtools/page/sw'},
            {'type': 'page', 'url': 'about:blank', 'webSocketDebuggerUrl': 'ws://127.0.0.1:9222/devtools/page/real'},
        ]
        self.assertEqual(
            browser_checkin._pick_page_target_ws(targets),
            'ws://127.0.0.1:9222/devtools/page/real',
        )


class EngineSelectionTests(unittest.TestCase):
    def test_engine_playwright_forced_bypasses_cdp(self):
        with mock.patch.dict(os.environ, {'GLADOS_BROWSER_ENGINE': 'playwright'}), \
                mock.patch('browser_checkin._run_cdp') as mock_cdp, \
                mock.patch('browser_checkin._run_playwright', return_value={'ok': True}) as mock_pw:
            result = browser_checkin.browser_checkin(COOKIE, 'synthetic-ua')
            self.assertEqual(result, {'ok': True})
            mock_cdp.assert_not_called()
            mock_pw.assert_called_once()

    def test_engine_cdp_forced_fails_if_no_browser_without_calling_playwright(self):
        with mock.patch.dict(os.environ, {'GLADOS_BROWSER_ENGINE': 'cdp'}), \
                mock.patch('browser_checkin._run_cdp', return_value=None) as mock_cdp, \
                mock.patch('browser_checkin._run_playwright') as mock_pw:
            result = browser_checkin.browser_checkin(COOKIE, 'synthetic-ua')
            self.assertEqual(result.get('reason'), 'browser-checkin-unavailable')
            self.assertIn('GLADOS_BROWSER_ENGINE=cdp', result.get('detail', ''))
            mock_cdp.assert_called_once()
            mock_pw.assert_not_called()

    def test_engine_auto_prefers_cdp_when_available(self):
        with mock.patch.dict(os.environ, {'GLADOS_BROWSER_ENGINE': 'auto'}), \
                mock.patch('browser_checkin._run_cdp', return_value={'ok': 'cdp'}) as mock_cdp, \
                mock.patch('browser_checkin._run_playwright') as mock_pw:
            result = browser_checkin.browser_checkin(COOKIE, 'synthetic-ua')
            self.assertEqual(result, {'ok': 'cdp'})
            mock_cdp.assert_called_once()
            mock_pw.assert_not_called()

    def test_engine_auto_falls_back_to_playwright_when_no_browser(self):
        with mock.patch.dict(os.environ, {'GLADOS_BROWSER_ENGINE': 'auto'}), \
                mock.patch('browser_checkin._run_cdp', return_value=None) as mock_cdp, \
                mock.patch('browser_checkin._run_playwright', return_value={'ok': 'pw'}) as mock_pw:
            result = browser_checkin.browser_checkin(COOKIE, 'synthetic-ua')
            self.assertEqual(result, {'ok': 'pw'})
            mock_cdp.assert_called_once()
            mock_pw.assert_called_once()


if __name__ == '__main__':
    unittest.main()
