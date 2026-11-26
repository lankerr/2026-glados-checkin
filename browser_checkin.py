"""Conservative official-page fallback. No guarantee of verification success.

Each call uses a fresh, temporary browser profile. It never reads the old shared
profile. Only a complete configured gld session is accepted. Status identity must
match before a user can submit. An ambiguous submission blocks that account until reconciled.
"""
import hashlib
import os
import re
import tempfile
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import urlsplit

BROWSER_CHANNELS = ('chrome', 'msedge', None)
CHECKIN_PAGE_PATH = '/console/checkin'
DOMAINS = ('https://glados.cloud', 'https://glados.rocks', 'https://glados.network', 'https://glados.space', 'https://glados.one')
RESULT_WAIT_SECONDS = 150
SESSION_COOKIE_NAMES = ('gld:sess', 'gld:sess.sig', 'koa:sess', 'koa:sess.sig')


def _failure(reason):
    return {'request_failed': True, 'reason': reason}


def _log(msg):
    print(msg, flush=True)


def profile_dir():
    """Non-secret safety state only; no persistent cookies/browser profile."""
    return os.path.join(os.environ.get('LOCALAPPDATA') or os.path.expanduser('~'),
                        'glados-checkin-safety')


def parse_cookie_header(cookie_header, base_url):
    cookies = []
    for item in cookie_header.split(';'):
        name, sep, value = item.strip().partition('=')
        if sep and name:
            cookie = {'name': name, 'value': value, 'url': base_url.rstrip('/') + '/'}
            if name in SESSION_COOKIE_NAMES:
                cookie.update(secure=True, httpOnly=True, sameSite='Lax')
            cookies.append(cookie)
    return cookies


def _valid_cookie(header):
    if not isinstance(header, str) or any(c in header for c in '\r\n'):
        return False
    pairs = parse_cookie_header(header, DOMAINS[0])
    names = [c['name'] for c in pairs]
    # Duplicate or legacy sessions are ambiguous; never guess which account wins.
    return (len(names) == len(set(names))
            and not any(n.startswith('koa:') for n in names)
            and all(any(c['name'] == n and c['value'] for c in pairs)
                    for n in ('gld:sess', 'gld:sess.sig')))


@contextmanager
def _exclusive_guard(expected_email):
    root = Path(profile_dir())
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    # Atomic creation also excludes another process. A crash fails closed:
    # a human must check no run remains before removing this non-secret lock.
    lock = root / 'browser.lock'
    fd = os.open(str(lock), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    try:
        os.close(fd)
        # Older versions left a date but no account. Keep the global lock and
        # honor all such markers until the operator reconciles those submissions.
        for entry in root.iterdir():
            if re.fullmatch(r'unresolved-[0-9]{4}-[0-9]{2}-[0-9]{2}', entry.name):
                raise UnresolvedSubmission
        identity = expected_email.strip().casefold().encode('utf-8')
        account_key = hashlib.sha256(identity).hexdigest()
        marker = root / ('pending-' + account_key)
        try:
            marker.lstat()
        except FileNotFoundError:
            yield marker
        else:
            raise UnresolvedSubmission
    finally:
        lock.unlink()


class UnresolvedSubmission(Exception):
    """A prior submission still needs manual reconciliation."""


def _is_checkin(url, method, base):
    endpoint = urlsplit(url)
    return (method == 'POST' and endpoint.scheme == 'https'
            and endpoint.netloc == urlsplit(base).netloc and endpoint.path == '/api/user/checkin')


def _manual_page(context, cookie, expected_email, marker):
    """Observe the user's own foreground submission; never click or solve challenges."""
    from checkin import NORMAL_CHECKIN_MESSAGES, is_non_retryable_checkin_result, is_turnstile_checkin_result
    base = DOMAINS[0]
    official_page = base + CHECKIN_PAGE_PATH
    armed = submitted = guard_failed = False

    def guard(route):
        nonlocal submitted, guard_failed
        req = route.request
        if req.method == 'POST' and urlsplit(req.url).path == '/api/user/checkin':
            if not armed or submitted or not _is_checkin(req.url, req.method, base):
                route.abort()
                return
            if req.frame != page.main_frame or req.frame.url.split('?', 1)[0].split('#', 1)[0] != official_page:
                route.abort()
                return
            try:
                marker.touch(exist_ok=False)
            except OSError:
                guard_failed = True
                route.abort()
                return
            submitted = True
        route.continue_()

    try:
        page = context.new_page()
        context.route('**/*', guard)
        context.add_cookies(parse_cookie_header(cookie, base))
        resp = context.request.get(base + '/api/user/status', timeout=15000, max_redirects=0)
        if resp.status != 200:
            return _failure('browser-identity-unverified')
        data = resp.json().get('data')
        if not isinstance(data, dict) or data.get('email') != expected_email:
            return _failure('browser-identity-unverified')
        page.goto(official_page, wait_until='domcontentloaded', timeout=45000)
        if page.url.split('?', 1)[0].split('#', 1)[0] != official_page:
            return _failure('browser-identity-unverified')
        _log(f'请在打开的官网窗口确认账号并亲自签到。等待 {RESULT_WAIT_SECONDS} 秒；关闭窗口可退出。')
        with page.expect_response(lambda r: submitted and _is_checkin(r.url, r.request.method, base),
                                  timeout=RESULT_WAIT_SECONDS * 1000) as observed:
            armed = True
        resp = observed.value
        if not 200 <= resp.status < 300:
            return _failure('submission-unknown')
        result = resp.json()
        if not isinstance(result, dict) or result.get('request_failed'):
            return _failure('submission-unknown')
        if is_turnstile_checkin_result(result) or is_non_retryable_checkin_result(result):
            return result  # Keep the marker; do not launch another browser or retry.
        code = result.get('code')
        message = str(result.get('message', '')).strip().lower()
        if (type(code) not in (str, int) or str(code) not in ('0', '1')
                or not (message == 'checkin!' or message.startswith(NORMAL_CHECKIN_MESSAGES))):
            return _failure('submission-unknown')
        marker.unlink()
        return result
    except Exception:
        if guard_failed:
            return _failure('browser-state-unavailable')
        return _failure('submission-unknown' if submitted else 'browser-manual-incomplete')


def browser_checkin(cookie_header, expected_email):
    if not _valid_cookie(cookie_header):
        return _failure('browser-cookie-ambiguous')
    if not isinstance(expected_email, str) or '@' not in expected_email:
        return _failure('browser-identity-unverified')
    try:
        with _exclusive_guard(expected_email) as marker:
            from playwright.sync_api import sync_playwright
            with tempfile.TemporaryDirectory(prefix='glados-isolated-') as directory, sync_playwright() as pw:
                for channel in BROWSER_CHANNELS:
                    try:
                        context = pw.chromium.launch_persistent_context(
                            user_data_dir=directory, channel=channel, headless=False, service_workers='block')
                    except Exception:
                        continue
                    try:
                        return _manual_page(context, cookie_header, expected_email, marker)
                    finally:
                        try:
                            context.close()
                        except Exception:
                            pass
                return _failure('browser-checkin-unavailable')
    except UnresolvedSubmission:
        return _failure('browser-outcome-unresolved')
    except FileExistsError:
        return _failure('browser-busy')
    except Exception:
        return _failure('browser-checkin-unavailable')
