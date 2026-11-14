"""Synthetic safety tests: no HTTP or real browser."""
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch
import browser_checkin as b
import checkin

COOKIE = 'gld:sess=synthetic; gld:sess.sig=synthetic-signature'
EMAIL = 'test@example.invalid'

class FakePage:
    def __init__(self, ctx, outcome):
        self.ctx, self.outcome = ctx, outcome
        self.url = b.DOMAINS[0] + b.CHECKIN_PAGE_PATH
        self.first = self
        self.posts = 0
    def goto(self, *args, **kw): pass
    def get_by_role(self, *args, **kw): return self
    def wait_for(self, **kw): pass
    def is_disabled(self): return False
    def close(self): pass
    def click(self):
        for _ in range(2):  # Simulate the webpage itself retrying.
            route = Mock()
            route.request = SimpleNamespace(method='POST', url=b.DOMAINS[0]+'/api/user/checkin')
            self.ctx.guard(route)
            self.posts += route.continue_.call_count
    def expect_response(self, *args, **kw): return self
    def __enter__(self): return SimpleNamespace(value=SimpleNamespace(json=lambda: self.outcome))
    def __exit__(self, *args):
        if self.outcome == 'timeout': raise TimeoutError()

class FakeContext:
    def __init__(self, outcome, email=EMAIL):
        self.request = SimpleNamespace(get=lambda *a, **k: SimpleNamespace(status=200,json=lambda:{'data':{'email':email}}))
        self.page = FakePage(self, outcome)
        self.cleared = False
    def route(self, pattern, guard): self.guard = guard
    def clear_cookies(self): self.cleared = True
    def add_cookies(self, cookies): assert self.cleared
    def new_page(self): return self.page

class SafetyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.marker = Path(self.tmp.name)/'unresolved'
        p = patch('requests.sessions.Session.request',side_effect=AssertionError('NO LIVE HTTP'))
        p.start();self.addCleanup(p.stop)
    def test_lost_response_no_second_post_and_marker(self):
        c = FakeContext('timeout')
        r = b._try_domains(c,COOKIE,EMAIL,self.marker)
        self.assertEqual(r['reason'],'browser-outcome-unknown')
        self.assertEqual(c.page.posts,1)
        self.assertTrue(self.marker.exists())
    def test_invalid_json_keeps_marker(self):
        for result in ([], None, {}, {'code':True}):
            if self.marker.exists(): self.marker.unlink()
            c=FakeContext(result)
            self.assertEqual(b._try_domains(c,COOKIE,EMAIL,self.marker)['reason'],'browser-outcome-unknown')
            self.assertTrue(self.marker.exists())
            self.assertEqual(c.page.posts,1)
    def test_known_response_and_page_retry_guard(self):
        c=FakeContext({'code':0,'message':'Checkin!'})
        self.assertEqual(b._try_domains(c,COOKIE,EMAIL,self.marker)['code'],0)
        self.assertEqual(c.page.posts,1)
        self.assertFalse(self.marker.exists())
    def test_mismatched_identity_no_click(self):
        c=FakeContext({'code':0},'other@example.invalid')
        self.assertEqual(b._try_domains(c,COOKIE,EMAIL,self.marker)['reason'],'browser-identity-unverified')
        self.assertEqual(c.page.posts,0)
    def test_incomplete_duplicate_legacy_cookie_rejected(self):
        for cookie in ('','gld:sess=x',COOKIE+'; gld:sess=other',COOKIE+'; koa:sess=old'):
            self.assertFalse(b._valid_cookie(cookie))
        self.assertTrue(b._valid_cookie(COOKIE))
    def test_exact_endpoint(self):
        for url in ('https://glados.cloud.evil.invalid/api/user/checkin','https://glados.cloud/api/user/checkin/challenge'):
            self.assertFalse(b._is_checkin(url,'POST',b.DOMAINS[0]))
    def test_concurrent_lock_fails_closed_and_releases(self):
        with patch.object(b,'profile_dir',return_value=self.tmp.name):
            with b._exclusive_guard():
                with self.assertRaises(FileExistsError):
                    with b._exclusive_guard(): pass
            with b._exclusive_guard(): pass
    def test_unresolved_blocks_before_launch(self):
        with patch.object(b,'profile_dir',return_value=self.tmp.name):
            with b._exclusive_guard() as marker: marker.touch()
            with patch.object(b,'_pick_context',side_effect=AssertionError('NO BROWSER')):
                self.assertEqual(b.browser_checkin(COOKIE,'synthetic',expected_email=EMAIL)['reason'],'browser-outcome-unresolved')
    def test_outer_layer_never_retries_ambiguous(self):
        client=checkin.GLaDOS(COOKIE)
        client.req=Mock(return_value={'data':{'email':EMAIL}})
        with patch.dict('os.environ',{'GLADOS_BROWSER_CHECKIN':'1','GLADOS_USER_AGENT':'Synthetic/1.0'}),patch.object(b,'browser_checkin',return_value={'request_failed':True,'reason':'browser-outcome-unknown'}) as call:
            checkin.attempt_browser_checkin(client,max_attempts=10)
            call.assert_called_once()
    def test_unknown_expected_identity_does_not_launch(self):
        self.assertEqual(b.browser_checkin(COOKIE,'synthetic')['reason'],'browser-identity-unverified')
    def test_launch_has_no_stealth_and_explicit_isolated_directory(self):
        pw=Mock()
        b._pick_context(pw,False,'Synthetic/1.0',self.tmp.name)
        args=pw.chromium.launch_persistent_context.call_args.kwargs
        self.assertEqual(args['user_data_dir'],self.tmp.name)
        self.assertNotIn('--disable-blink-features=AutomationControlled',args['args'])

if __name__=='__main__': unittest.main()
