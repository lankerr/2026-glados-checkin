"""Offline tests. No service, credentials or installed browser needed."""
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, Mock, patch

import browser_checkin as b

EMAIL = 'alice@example.invalid'
COOKIE = 'gld:sess=fixture; gld:sess.sig=fixture'


class ManualHandoffTests(unittest.TestCase):
    def test_profile_not_reused_and_private_data_cleaned_on_error(self):
        class Module:
            sync_playwright = MagicMock()
        chromium = Module.sync_playwright.return_value.__enter__.return_value.chromium
        paths = []
        def launch(**opts):
            self.assertFalse(opts['headless'])
            profile = Path(opts['user_data_dir'])
            self.assertFalse((profile / 'session').exists())
            (profile / 'session').write_text('fixture')
            paths.append(profile)
            return Mock()
        chromium.launch_persistent_context.side_effect = launch
        with tempfile.TemporaryDirectory() as root, patch.object(b, 'profile_dir', return_value=root), \
                patch.dict(sys.modules, {'playwright.sync_api': Module}), \
                patch.object(b, '_manual_page', side_effect=RuntimeError()):
            for email in (EMAIL, 'bob@example.invalid'):
                b.browser_checkin(COOKIE, email)
            self.assertEqual(len(set(paths)), 2)
            self.assertFalse(any(p.exists() for p in paths))

    def simulate(self, email=EMAIL, response_lost=False):
        ctx = Mock()
        resp = ctx.request.get.return_value
        resp.status = 200
        resp.json.return_value = {'data': {'email': email}}
        page = ctx.new_page.return_value
        page.url = page.main_frame.url = b.DOMAINS[0] + b.CHECKIN_PAGE_PATH
        ctx.route.side_effect = lambda pattern, guard: setattr(ctx, 'guard', guard)
        routes = []
        def user_submit(*args):
            route = Mock()
            route.request = SimpleNamespace(method='POST', url=b.DOMAINS[0] + '/api/user/checkin', frame=page.main_frame)
            ctx.guard(route)
            routes.append(route)
        listener = MagicMock()
        listener.__exit__.side_effect = lambda *a: (user_submit(), user_submit(), False)[-1]
        page.expect_response.return_value = listener
        result = listener.__enter__.return_value.value
        result.status = 200
        if response_lost:
            result.json.side_effect = ValueError()
        else:
            result.json.return_value = {'code':'0', 'message':'Checkin!'}
        with b._exclusive_guard(EMAIL) as marker:
            reply = b._manual_page(ctx, COOKIE, EMAIL, marker)
        return reply, routes

    def test_verified_user_can_submit_once_and_success_unlocks(self):
        with tempfile.TemporaryDirectory() as root, patch.object(b, 'profile_dir', return_value=root):
            mismatch, routes = self.simulate(email='other@example.invalid')
            self.assertEqual(mismatch['reason'], 'browser-identity-unverified')
            self.assertFalse(routes)
            result, routes = self.simulate()
            self.assertEqual(result['code'], '0')
            routes[0].continue_.assert_called_once()
            routes[1].abort.assert_called_once()
            self.assertEqual(list(Path(root).iterdir()), [])

    def test_ambiguous_response_blocks_only_that_account_across_runs(self):
        with tempfile.TemporaryDirectory() as root, patch.object(b, 'profile_dir', return_value=root):
            result, _ = self.simulate(response_lost=True)
            self.assertEqual(result['reason'], 'submission-unknown')
            self.assertEqual(b.browser_checkin(COOKIE, EMAIL.upper())['reason'], 'browser-outcome-unresolved')
            with b._exclusive_guard('bob@example.invalid'):
                self.assertEqual(b.browser_checkin(COOKIE, EMAIL)['reason'], 'browser-busy')
            (Path(root) / 'unresolved-2026-01-01').touch()
            self.assertEqual(b.browser_checkin(COOKIE, 'bob@example.invalid')['reason'], 'browser-outcome-unresolved')
