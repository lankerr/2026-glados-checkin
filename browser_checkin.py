"""Conservative official-page fallback. No guarantee of verification success.

Each call uses a fresh, temporary browser profile. It never reads the old shared
profile. Only a complete configured gld session is accepted. Status identity must
match before a click. One POST maximum; ambiguous outcomes block later calls for
this local Beijing date until manually reconciled. No CAPTCHA bypass is provided.
"""
import json
import os
import re
import tempfile
from contextlib import contextmanager
from datetime import datetime, timezone, timedelta
from pathlib import Path
from urllib.parse import urlsplit

BROWSER_CHANNELS = ('chrome', 'msedge', None)
CHECKIN_PAGE_PATH = '/console/checkin'
DOMAINS = ('https://glados.cloud', 'https://glados.rocks')
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
def _exclusive_guard():
    root = Path(profile_dir())
    root.mkdir(parents=True, exist_ok=True)
    # Atomic creation also excludes another process. A crash fails closed:
    # a human must check no run remains before removing this non-secret lock.
    lock = root / 'browser.lock'
    fd = os.open(str(lock), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    try:
        os.close(fd)
        day = datetime.now(timezone(timedelta(hours=8))).strftime('%Y-%m-%d')
        yield root / ('unresolved-' + day)
    finally:
        lock.unlink()


def _pick_context(pw, headless, user_agent=None, directory=None):
    errors = []
    for channel in BROWSER_CHANNELS:
        kwargs = {'user_data_dir': directory, 'headless': headless,
                  'args': ['--no-first-run', '--no-default-browser-check'],
                  'service_workers': 'block'}
        if channel:
            kwargs['channel'] = channel
        if user_agent:
            kwargs['user_agent'] = user_agent
        try:
            return pw.chromium.launch_persistent_context(**kwargs), channel
        except Exception as exc:
            errors.append(type(exc).__name__)
    raise RuntimeError('browser-unavailable: ' + ','.join(errors))


def _is_checkin(url, method, base):
    parsed, origin = urlsplit(url), urlsplit(base)
    return (method == 'POST' and parsed.scheme == origin.scheme
            and parsed.netloc == origin.netloc and parsed.path == '/api/user/checkin')


def _try_domains(context, cookie_header, expected_email, marker, domains=None):
    # Only one selected official origin per call: no cross-domain replay.
    base = tuple(domains or DOMAINS)[0]
    state = {'allowed': False, 'submitted': False}

    def guard(route):
        req = route.request
        if req.method == 'POST':
            if (not state['allowed'] or state['submitted']
                    or not _is_checkin(req.url, req.method, base)):
                route.abort()
                return
            # Durable marker precedes submission, including automatic page POSTs.
            marker.touch(exist_ok=False)
            state['submitted'] = True
        route.continue_()

    context.route('**/*', guard)
    page = None
    try:
        context.clear_cookies()
        context.add_cookies(parse_cookie_header(cookie_header, base))
        response = context.request.get(base + '/api/user/status', timeout=15000)
        body = response.json()
        data = body.get('data') if isinstance(body, dict) else None
        actual = data.get('email') if isinstance(data, dict) else None
        if response.status != 200 or actual != expected_email:
            return _failure('browser-identity-unverified')
        page = context.new_page()
        page.goto(base + CHECKIN_PAGE_PATH, wait_until='domcontentloaded', timeout=45000)
        # Redirects to login or a different origin must never be clicked.
        if urlsplit(page.url).netloc != urlsplit(base).netloc or urlsplit(page.url).path != CHECKIN_PAGE_PATH:
            return _failure('browser-identity-unverified')
        btn = page.get_by_role('button', name=re.compile(r'^check\s*in$', re.I)).first
        btn.wait_for(state='visible', timeout=45000)
        if btn.is_disabled():
            return _failure('browser-checkin-unavailable')
        state['allowed'] = True
        with page.expect_response(lambda r: _is_checkin(r.url, r.request.method, base),
                                  timeout=RESULT_WAIT_SECONDS * 1000) as info:
            btn.click()
        result = info.value.json()
        if not isinstance(result, dict) or type(result.get('code')) is not int:
            return _failure('browser-outcome-unknown')
        # Received a structured server decision. No repeat in this call anyway.
        if state['submitted']:
            marker.unlink()
        return result
    except Exception:
        # Even a click exception may occur after submission. Do not retry.
        if state['allowed']:
            marker.touch(exist_ok=True)
            return _failure('browser-outcome-unknown')
        return _failure('browser-checkin-unavailable')
    finally:
        if page:
            try:
                page.close()
            except Exception:
                pass


def browser_checkin(cookie_header, user_agent, domains=None, expected_email=None):
    if not _valid_cookie(cookie_header):
        return _failure('browser-cookie-ambiguous')
    if not isinstance(expected_email, str) or not expected_email.strip():
        return _failure('browser-identity-unverified')
    selected = tuple(domains or DOMAINS)
    if not selected or any(base not in DOMAINS for base in selected):
        return _failure('browser-origin-invalid')
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return _failure('browser-checkin-unavailable')
    headless = os.environ.get('GLADOS_BROWSER_HEADLESS', '').lower() in ('1', 'true', 'yes')
    try:
        with _exclusive_guard() as marker:
            if marker.exists():
                return _failure('browser-outcome-unresolved')
            # Temporary per-call storage: no prior-account cookies, localStorage,
            # service workers or persistent login state are imported/reused.
            with tempfile.TemporaryDirectory(prefix='glados-isolated-') as directory:
                with sync_playwright() as pw:
                    context, channel = _pick_context(pw, headless, user_agent, directory)
                    try:
                        return _try_domains(context, cookie_header, expected_email, marker, selected)
                    finally:
                        context.close()
    except FileExistsError:
        return _failure('browser-busy')
    except Exception:
        return _failure('browser-checkin-error')
