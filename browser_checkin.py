"""GLaDOS 签到的真浏览器兜底通道（应对 Cloudflare Turnstile）。

背景（2026-11 逆向 /static/js/main~21b3c6c3.chunk.js 得出）：
  1. 页面先 GET /api/user/checkin/challenge -> {nonce, ttl, turnstile: sitekey}
  2. 用 sitekey 渲染 Turnstile 挂件（action="checkin", cData=nonce,
     appearance="interaction-only"），真浏览器环境通常无感通过并回调出令牌
  3. POST /api/user/checkin，body 为 {token: hostname, nonce,
     proof: SHA256(nonce + ".glados-observe-v1"), tsState, turnstile: 令牌}

纯 requests 拿不到合法令牌，因此本模块直接用真实 Chrome/Edge 打开官方签到页，
由页面自身完成 challenge -> Turnstile -> proof 全流程；我们只负责：
  注入 Cookie -> 点 "Check in" 按钮 -> 拦截 /api/user/checkin 的 JSON 响应。

设计说明：
  - 支持免 Playwright 的原生 CDP 驱动模式：优先寻找系统安装的 Edge / Chrome /
    Chromium，通过 Chrome DevTools Protocol 自动化控制，
    无需额外安装庞大的 playwright 依赖；同时兼容 Playwright（如已安装且未检测到系统浏览器时回退）。
  - 浏览器持久化目录放在系统用户数据区（STATE_DIRECTORY / LOCALAPPDATA / XDG_DATA_HOME），
    不落在仓库内，避免登录态被误提交；目录保存 cf_clearance 等状态，请勿随意删除。
  - 优先使用配置的 User-Agent 保持设备一致性；若服务端拒绝，再改用浏览器原生 UA 重试一次。
  - GitHub Actions 等机房环境由 checkin.attempt_browser_checkin 预先禁用，
    本模块不做二次判断。

安全与隐私：Cookie/UA 只注入浏览器，绝不写日志；截图仅存 logs/ 目录。
"""

import base64
import glob
import ipaddress
import json
import os
import re
import shutil
import socket
import struct
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone, timedelta
from urllib.parse import urlsplit
import urllib.request

# 浏览器通道优先级：真实 Chrome > 真实 Edge > Playwright 自带 Chromium
BROWSER_CHANNELS = ('chrome', 'msedge', None)
CHECKIN_PAGE_PATH = '/console/checkin'
# 2026-11-17 实测在线的官方域名（one 为旧域名，留作最后回退）
DOMAINS = ('https://glados.cloud', 'https://glados.rocks', 'https://glados.network', 'https://glados.space', 'https://glados.one')
# 页面自身等待 Turnstile 最长约 90s + 2.5s 最小间隔 + 网络余量
RESULT_WAIT_SECONDS = 150
BUTTON_WAIT_SECONDS = 45
# 会话 Cookie 与其他 Cookie 一律按目标站点主机绑定（url 形式，非子域通配）
SESSION_COOKIE_NAMES = ('gld:sess', 'gld:sess.sig', 'koa:sess', 'koa:sess.sig')


def _log(msg):
    # 自包含版本，与 checkin.log() 格式一致（避免循环导入）
    now = datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{now} 北京时间] {msg}", flush=True)


def profile_dir():
    """浏览器持久化目录：放在系统用户数据区，避免落入 git 仓库。"""
    base = (
        os.environ.get('STATE_DIRECTORY')
        or os.environ.get('LOCALAPPDATA')
        or os.environ.get('XDG_DATA_HOME')
        or os.path.expanduser('~/.local/share')
        or os.path.expanduser('~')
    )
    return os.path.join(base, 'glados-checkin-browser')


def log_dir():
    """日志与截图保存目录：优先使用 STATE_DIRECTORY/logs，避免在无写权限的工作目录下报错。"""
    base = os.environ.get('STATE_DIRECTORY') or '.'
    d = os.path.join(base, 'logs')
    try:
        os.makedirs(d, exist_ok=True)
        return d
    except OSError:
        d = os.path.join(tempfile.gettempdir(), 'glados-logs')
        try:
            os.makedirs(d, exist_ok=True)
        except OSError:
            pass
        return d


def parse_cookie_header(cookie_header, base_url):
    """把 'a=1; b=2' 请求头解析成绑定到目标站点的 Cookie 列表。

    用 url（而非 domain 通配）注入，Cookie 仅属于当前主机；
    会话 Cookie 附带 Secure/HttpOnly 属性，与官网真实下发行为一致。
    """
    url = base_url.rstrip('/') + '/'
    cookies = []
    for item in cookie_header.split(';'):
        name, sep, value = item.strip().partition('=')
        if sep and name:
            cookie = {
                'name': name,
                'value': value,
                'url': url,
            }
            if name.strip() in SESSION_COOKIE_NAMES:
                cookie.update({'secure': True, 'httpOnly': True, 'sameSite': 'Lax'})
            cookies.append(cookie)
    return cookies


def find_browser_executable(custom=None):
    """在系统中寻找可用的 Edge、Chrome 或 Chromium 可执行文件路径。

    探测策略：
    1. 自定义路径参数或环境变量 GLADOS_BROWSER_PATH
    2. PATH 环境变量中的常用浏览器名称
    3. Linux / NixOS / macOS / Windows 常见安装路径及包管理器路径
    """
    if custom and os.path.exists(custom):
        return custom
    env_path = os.environ.get('GLADOS_BROWSER_PATH')
    if env_path and os.path.exists(env_path):
        return env_path

    candidates = [
        'microsoft-edge',
        'microsoft-edge-stable',
        'microsoft-edge-beta',
        'microsoft-edge-dev',
        'msedge',
        'google-chrome',
        'google-chrome-stable',
        'google-chrome-beta',
        'chrome',
        'chromium',
        'chromium-browser',
        'brave-browser',
        'brave',
    ]
    for name in candidates:
        found = shutil.which(name)
        if found:
            return found

    # Unix / Linux 常见固定路径（包括 NixOS 系统 profile 和 per-user profile）
    unix_paths = [
        '/run/current-system/sw/bin/microsoft-edge',
        '/run/current-system/sw/bin/microsoft-edge-stable',
        '/run/current-system/sw/bin/google-chrome',
        '/run/current-system/sw/bin/google-chrome-stable',
        '/run/current-system/sw/bin/chromium',
        '/usr/bin/microsoft-edge',
        '/usr/bin/microsoft-edge-stable',
        '/usr/bin/google-chrome',
        '/usr/bin/google-chrome-stable',
        '/usr/bin/chromium',
        '/usr/bin/chromium-browser',
        '/var/lib/flatpak/exports/bin/com.microsoft.Edge',
        '/var/lib/flatpak/exports/bin/com.google.Chrome',
        '/snap/bin/chromium',
    ]
    for p in unix_paths:
        if os.path.exists(p):
            return p

    # NixOS per-user profile 与用户级路径通配
    for pattern in (
        '/etc/profiles/per-user/*/bin/microsoft-edge',
        '/etc/profiles/per-user/*/bin/google-chrome',
        '/etc/profiles/per-user/*/bin/chromium',
        os.path.expanduser('~/.nix-profile/bin/microsoft-edge'),
        os.path.expanduser('~/.nix-profile/bin/google-chrome'),
        os.path.expanduser('~/.nix-profile/bin/chromium'),
    ):
        matches = glob.glob(pattern)
        if matches and os.path.exists(matches[0]):
            return matches[0]

    # Windows 常见路径
    if sys.platform == 'win32':
        prog_files = os.environ.get('ProgramFiles', r'C:\Program Files')
        prog_files_x86 = os.environ.get('ProgramFiles(x86)', r'C:\Program Files (x86)')
        local_app = os.environ.get('LOCALAPPDATA', r'C:\Users\Default\AppData\Local')
        win_candidates = [
            os.path.join(prog_files_x86, r'Microsoft\Edge\Application\msedge.exe'),
            os.path.join(prog_files, r'Microsoft\Edge\Application\msedge.exe'),
            os.path.join(local_app, r'Microsoft\Edge\Application\msedge.exe'),
            os.path.join(prog_files, r'Google\Chrome\Application\chrome.exe'),
            os.path.join(prog_files_x86, r'Google\Chrome\Application\chrome.exe'),
            os.path.join(local_app, r'Google\Chrome\Application\chrome.exe'),
        ]
        for p in win_candidates:
            if os.path.exists(p):
                return p

    # macOS 常见路径
    if sys.platform == 'darwin':
        mac_paths = [
            '/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge',
            '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
            '/Applications/Chromium.app/Contents/MacOS/Chromium',
        ]
        for p in mac_paths:
            if os.path.exists(p):
                return p

    return None


class SimpleWebSocket:
    """极简标准库 RFC 6455 WebSocket 客户端，无需安装 websocket/websockets 依赖。"""

    def __init__(self, ws_url):
        parsed = urlsplit(ws_url)
        self.host = parsed.hostname
        self.port = parsed.port or (443 if parsed.scheme == 'wss' else 80)
        self.path = parsed.path
        if parsed.query:
            self.path += '?' + parsed.query
        self.sock = socket.create_connection((self.host, self.port), timeout=10)

        # 握手协议
        key = base64.b64encode(os.urandom(16)).decode('ascii')
        req = (
            f"GET {self.path} HTTP/1.1\r\n"
            f"Host: {self.host}:{self.port}\r\n"
            f"Upgrade: websocket\r\n"
            f"Connection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {key}\r\n"
            f"Sec-WebSocket-Version: 13\r\n\r\n"
        )
        self.sock.sendall(req.encode('ascii'))
        resp = b""
        while b"\r\n\r\n" not in resp:
            chunk = self.sock.recv(4096)
            if not chunk:
                raise ConnectionError("WebSocket 握手提前关闭")
            resp += chunk
        if b" 101 " not in resp:
            status_line = resp.split(b"\r\n")[0]
            raise ConnectionError(f"WebSocket 握手失败: {status_line}")

    def send(self, data_str):
        data = data_str.encode('utf-8')
        length = len(data)
        mask = os.urandom(4)
        if length < 126:
            header = bytes([0x81, 0x80 | length]) + mask
        elif length < 65536:
            header = bytes([0x81, 0x80 | 126]) + struct.pack('>H', length) + mask
        else:
            header = bytes([0x81, 0x80 | 127]) + struct.pack('>Q', length) + mask
        payload = bytes(b ^ mask[i % 4] for i, b in enumerate(data))
        self.sock.sendall(header + payload)

    def recv(self, timeout=None):
        if timeout is not None:
            self.sock.settimeout(timeout)
        try:
            header = self._recv_exact(2)
            if not header:
                return None
            b1, b2 = header[0], header[1]
            opcode = b1 & 0x0F
            is_masked = bool(b2 & 0x80)
            payload_len = b2 & 0x7F
            if payload_len == 126:
                payload_len = struct.unpack('>H', self._recv_exact(2))[0]
            elif payload_len == 127:
                payload_len = struct.unpack('>Q', self._recv_exact(8))[0]
            mask_key = self._recv_exact(4) if is_masked else None
            data = self._recv_exact(payload_len)
            if is_masked and mask_key:
                data = bytes(b ^ mask_key[i % 4] for i, b in enumerate(data))

            if opcode == 0x8:  # Close
                self.close()
                return None
            if opcode == 0x9:  # Ping -> 发送 Pong 响应
                mask = os.urandom(4)
                pong_header = bytes([0x8A, 0x80 | len(data)]) + mask
                payload = bytes(b ^ mask[i % 4] for i, b in enumerate(data))
                self.sock.sendall(pong_header + payload)
                return self.recv(timeout)
            if opcode == 0x1:  # Text frame
                return data.decode('utf-8', errors='replace')
            return None
        except (socket.timeout, TimeoutError):
            return None
        finally:
            if timeout is not None:
                self.sock.settimeout(None)

    def _recv_exact(self, n):
        buf = bytearray()
        while len(buf) < n:
            chunk = self.sock.recv(n - len(buf))
            if not chunk:
                break
            buf.extend(chunk)
        return bytes(buf)

    def close(self):
        try:
            self.sock.close()
        except Exception:
            pass


class CDPClient:
    """通过 Chrome DevTools Protocol 控制浏览器的同步封装。"""

    def __init__(self, ws_url, session_id=None):
        self.ws = SimpleWebSocket(ws_url)
        self._msg_id = 0
        self.session_id = session_id
        self.checkin_request_id = None
        self.checkin_loading_finished = False

    def _handle_event(self, data):
        if not isinstance(data, dict):
            return
        if self.session_id and data.get('sessionId') not in (None, self.session_id):
            return
        method = data.get('method', '')
        params = data.get('params', {})
        if method == 'Network.requestWillBeSent':
            req = params.get('request', {})
            req_method = req.get('method', '').upper()
            url = req.get('url', '')
            path = urlsplit(url).path.rstrip('/')
            if path == '/api/user/checkin' and req_method == 'POST':
                self.checkin_request_id = params.get('requestId')
        elif method == 'Network.responseReceived':
            resp = params.get('response', {})
            url = resp.get('url', '')
            path = urlsplit(url).path.rstrip('/')
            if path == '/api/user/checkin':
                if not self.checkin_request_id:
                    self.checkin_request_id = params.get('requestId')
        elif method == 'Network.loadingFinished':
            if params.get('requestId') == self.checkin_request_id:
                self.checkin_loading_finished = True

    def poll_events(self, timeout=0.2):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            remaining = max(0.01, deadline - time.monotonic())
            msg = self.ws.recv(timeout=remaining)
            if not msg:
                break
            try:
                data = json.loads(msg)
                self._handle_event(data)
            except ValueError:
                pass

    def call(self, method, params=None, timeout=15, use_session=True):
        self._msg_id += 1
        call_id = self._msg_id
        payload = {'id': call_id, 'method': method}
        if params is not None:
            payload['params'] = params
        if self.session_id and use_session:
            payload['sessionId'] = self.session_id
        self.ws.send(json.dumps(payload))

        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            remaining = max(0.05, deadline - time.monotonic())
            msg = self.ws.recv(timeout=remaining)
            if not msg:
                continue
            try:
                data = json.loads(msg)
                if data.get('id') == call_id:
                    return data
                self._handle_event(data)
            except ValueError:
                pass
        return None

    def evaluate(self, expr, timeout=5):
        res = self.call('Runtime.evaluate', {
            'expression': expr,
            'returnByValue': True,
            'awaitPromise': True,
        }, timeout=timeout)
        if res and 'result' in res and 'result' in res['result']:
            return res['result']['result'].get('value')
        return None

    def close(self):
        self.ws.close()


def _is_loopback_host(host):
    """仅允许本机回环主机名或回环 IP，防止会话凭据发往外部远端。"""
    if not host:
        return False
    normalized = host.strip().strip('[]').lower()
    if normalized == 'localhost':
        return True
    try:
        return ipaddress.ip_address(normalized).is_loopback
    except ValueError:
        return False


def _validate_cdp_url(cdp_url):
    """校验自定义 CDP 地址格式与本机边界，报错绝不回显原始 URL 或凭据。"""
    raw = (cdp_url or '').strip()
    if not raw:
        raise ValueError('自定义 CDP 地址为空')
    parsed = urlsplit(raw)
    scheme = parsed.scheme.lower()
    if scheme not in ('http', 'https', 'ws', 'wss'):
        raise ValueError('自定义 CDP 地址协议无效')
    if not _is_loopback_host(parsed.hostname):
        raise ValueError('自定义 CDP 地址仅支持本机回环地址')
    return parsed


def _build_http_version_url(parsed):
    """构造不含用户认证信息与查询参数的 /json/version 发现地址。"""
    host = parsed.hostname or ''
    if ':' in host and not host.startswith('['):
        host = f'[{host}]'
    port_part = f':{parsed.port}' if parsed.port else ''
    base_path = parsed.path.rstrip('/')
    return f'{parsed.scheme.lower()}://{host}{port_part}{base_path}/json/version'


def resolve_cdp_url(cdp_url):
    """从给定的本机 CDP 地址解析出浏览器级 WebSocket 地址（禁止复用已有页面）。"""
    parsed = _validate_cdp_url(cdp_url)
    scheme = parsed.scheme.lower()

    if scheme in ('ws', 'wss'):
        if '/devtools/page/' in parsed.path:
            raise ValueError('不允许直接复用已有页面调试地址，请提供浏览器级 CDP 地址')
        return cdp_url.strip()

    version_url = _build_http_version_url(parsed)
    try:
        with urllib.request.urlopen(version_url, timeout=5) as r:
            info = json.loads(r.read().decode())
    except Exception as e:
        raise RuntimeError(f'连接本机 CDP 服务失败 ({type(e).__name__})') from None

    ws_url = info.get('webSocketDebuggerUrl') if isinstance(info, dict) else None
    if not ws_url or not isinstance(ws_url, str):
        raise RuntimeError('CDP 服务未提供浏览器级调试端点')

    ws_parsed = _validate_cdp_url(ws_url)
    if ws_parsed.scheme.lower() not in ('ws', 'wss') or '/devtools/page/' in ws_parsed.path:
        raise RuntimeError('CDP 服务返回的调试端点无效')
    return ws_url.strip()


def _clear_cdp_session_cookies(cdp, cookie_names, bases):
    """清理本轮涉及域名的会话 Cookie，避免多账号或失败重试残留会话状态。"""
    for base in bases:
        url = base.rstrip('/') + '/'
        for name in cookie_names:
            try:
                cdp.call('Network.deleteCookies', {'name': name, 'url': url}, timeout=3)
            except Exception:
                pass


def _run_cdp_session_with_client(cdp, cookie_header, user_agent=None):
    """通过已建立的 CDP 会话（支持独立的 Target session_id）执行签到。"""
    last_error = None
    attempted_bases = []
    injected_names = set(SESSION_COOKIE_NAMES)
    try:
        # 开启网络与页面事件
        cdp.call('Page.enable')
        cdp.call('Network.enable')
        cdp.call('Runtime.enable')

        if user_agent:
            cdp.call('Network.setUserAgentOverride', {'userAgent': user_agent})

        # 注入 fetch/XHR 拦截脚本，保证 100% 捕获 /api/user/checkin 响应体
        preload_js = r"""
        try {
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined,
                configurable: true,
            });
        } catch(e) {}
        window._glados_checkin_result = null;

        function _isCheckinPost(url, method) {
            if (!url) return false;
            if (method && String(method).toUpperCase() !== 'POST') return false;
            try {
                const u = new URL(url, window.location.href);
                return u.pathname.replace(/\/$/, '') === '/api/user/checkin';
            } catch(e) {
                const s = String(url);
                return s.includes('/api/user/checkin') && !s.includes('/challenge');
            }
        }

        if (window.fetch) {
            const _f = window.fetch;
            window.fetch = async function(...args) {
                const resp = await _f.apply(this, args);
                try {
                    const url = (args[0] && args[0].url) || args[0] || '';
                    const opts = args[1] || (typeof args[0] === 'object' ? args[0] : {});
                    const method = opts.method || 'GET';
                    if (_isCheckinPost(url, method)) {
                        const clone = resp.clone();
                        clone.text().then(text => {
                            try {
                                const parsed = JSON.parse(text);
                                if (!parsed.nonce) {
                                    window._glados_checkin_result = parsed;
                                }
                            } catch(e) {
                                window._glados_checkin_result = { code: 0, message: text };
                            }
                        }).catch(() => {});
                    }
                } catch(e) {}
                return resp;
            };
        }
        if (window.XMLHttpRequest) {
            const _XHR = window.XMLHttpRequest;
            const _origOpen = _XHR.prototype.open;
            const _origSend = _XHR.prototype.send;
            _XHR.prototype.open = function(method, url) {
                this._glados_method = method;
                this._glados_url = url;
                return _origOpen.apply(this, arguments);
            };
            _XHR.prototype.send = function() {
                this.addEventListener('load', function() {
                    try {
                        if (_isCheckinPost(this._glados_url, this._glados_method)) {
                            try {
                                const parsed = JSON.parse(this.responseText);
                                if (!parsed.nonce) {
                                    window._glados_checkin_result = parsed;
                                }
                            } catch(e) {
                                window._glados_checkin_result = { code: 0, message: this.responseText };
                            }
                        }
                    } catch(e) {}
                });
                return _origSend.apply(this, arguments);
            };
        }
        """
        cdp.call('Page.addScriptToEvaluateOnNewDocument', {'source': preload_js})

        for base in DOMAINS:
            captured = {'json': None}
            cdp.checkin_request_id = None
            cdp.checkin_loading_finished = False
            last_turnstile_click = 0
            _log(f"📄 正在通过 {base} 打开官方签到页…")

            # 注入该域名的安全会话 Cookie（先清理该域名残留的旧会话 Cookie）
            attempted_bases.append(base)
            cookies = parse_cookie_header(cookie_header, base)
            injected_names.update(c['name'] for c in cookies)
            _clear_cdp_session_cookies(cdp, injected_names, (base,))
            cdp.call('Network.setCookies', {'cookies': cookies})

            # 导航到签到页面
            cdp.call('Page.navigate', {'url': base + CHECKIN_PAGE_PATH})

            # 循环等待按钮可点击并点击
            btn_deadline = time.monotonic() + BUTTON_WAIT_SECONDS
            clicked = False
            while time.monotonic() < btn_deadline:
                # 优先检查是否已有页面自动请求的响应
                res = cdp.evaluate(r"""
                (() => {
                    if (window._glados_checkin_result) {
                        return { status: 'captured', json: window._glados_checkin_result };
                    }
                    const btns = Array.from(document.querySelectorAll('button, a, div[role="button"]'));
                    const btn = btns.find(b => {
                        const t = (b.textContent || '').trim();
                        return /check\s*in/i.test(t) || /签到/i.test(t);
                    });
                    if (btn) {
                        if (btn.disabled || btn.getAttribute('aria-disabled') === 'true') {
                            return { status: 'disabled' };
                        }
                        btn.click();
                        return { status: 'clicked' };
                    }
                    return { status: 'waiting' };
                })()
                """)
                if isinstance(res, dict):
                    if res.get('status') == 'captured' and res.get('json'):
                        captured['json'] = res['json']
                        break
                    if res.get('status') == 'clicked':
                        clicked = True
                        _log("🖱️ 点击 Check in，页面将自行完成 Turnstile 验证…")
                        break
                time.sleep(0.5)

            if not clicked and not captured['json']:
                last_error = f'{base}: 未找到可点击的 Check in 按钮'
                _log(f"⚠️ {last_error}，尝试下一个域名")
                continue

            # 等待签到接口响应及 Turnstile 验证完成
            result_deadline = time.monotonic() + RESULT_WAIT_SECONDS
            while time.monotonic() < result_deadline and not captured['json']:
                cdp.poll_events(timeout=0.3)

                # 1. 优先通过 CDP Network.responseReceived 获取响应体
                if cdp.checkin_request_id:
                    body_res = cdp.call('Network.getResponseBody', {'requestId': cdp.checkin_request_id})
                    if body_res and 'result' in body_res and 'body' in body_res['result']:
                        raw_body = body_res['result']['body']
                        try:
                            parsed = json.loads(raw_body)
                            # 排除 /api/user/checkin/challenge 响应 (包含 nonce/ttl 且无 message)
                            if isinstance(parsed, dict) and ('nonce' in parsed and 'ttl' in parsed and 'message' not in parsed):
                                cdp.checkin_request_id = None
                            else:
                                captured['json'] = parsed
                                _log("✅ 通过 CDP 网络事件成功捕获签到接口响应！")
                                break
                        except Exception:
                            pass

                # 2. 检查 JavaScript hook (fetch & XHR)
                hook_res = cdp.evaluate("window._glados_checkin_result || null")
                if isinstance(hook_res, dict) and hook_res:
                    if 'nonce' in hook_res and 'ttl' in hook_res and 'message' not in hook_res:
                        pass
                    else:
                        captured['json'] = hook_res
                        _log("✅ 通过页面 JS Hook 成功捕获签到结果！")
                        break

                # 3. 检查页面临时弹出的 Toast 浮窗提示（仅限真正包含签到关键词的消息提示）
                toast_res = cdp.evaluate(r"""
                (() => {
                    const notices = Array.from(document.querySelectorAll('.ant-message-notice, .ant-message, [role="alert"]'));
                    for (const n of notices) {
                        const text = (n.textContent || '').trim();
                        if (/checkin!\s*got/i.test(text)) {
                            return { code: 0, message: text };
                        }
                        if (/observation logged/i.test(text) || /repeats/i.test(text)) {
                            return { code: 1, message: text };
                        }
                    }
                    return null;
                })()
                """)
                if isinstance(toast_res, dict) and toast_res:
                    captured['json'] = toast_res
                    _log(f"✅ 从页面 Toast 提示捕获签到结果: {toast_res.get('message')}")
                    break

                # 4. 检查是否出现需要交互的 Turnstile 验证框并自动点击复选框
                turnstile_box = cdp.evaluate(r"""
                (() => {
                    const iframe = document.querySelector('iframe[src*="challenges.cloudflare.com"]')
                        || document.querySelector('iframe[title*="Cloudflare"]')
                        || document.querySelector('iframe[src*="turnstile"]');
                    if (iframe) {
                        const rect = iframe.getBoundingClientRect();
                        if (rect.width > 50 && rect.height > 30) {
                            return {
                                x: Math.round(rect.left + 30),
                                y: Math.round(rect.top + rect.height / 2)
                            };
                        }
                    }
                    return null;
                })()
                """)
                if isinstance(turnstile_box, dict) and 'x' in turnstile_box and 'y' in turnstile_box:
                    now = time.monotonic()
                    if now - last_turnstile_click > 5.0:
                        last_turnstile_click = now
                        _log("🖱️ 检测到 Cloudflare Turnstile 验证框，尝试模拟点击复选框…")
                        tx, ty = turnstile_box['x'], turnstile_box['y']
                        cdp.call('Input.dispatchMouseEvent', {'type': 'mouseMoved', 'x': tx, 'y': ty})
                        cdp.call('Input.dispatchMouseEvent', {'type': 'mousePressed', 'x': tx, 'y': ty, 'button': 'left', 'clickCount': 1})
                        cdp.call('Input.dispatchMouseEvent', {'type': 'mouseReleased', 'x': tx, 'y': ty, 'button': 'left', 'clickCount': 1})

                time.sleep(0.5)

            result = captured['json']
            if not result:
                try:
                    snap = cdp.call('Page.captureScreenshot', {'format': 'png'})
                    if snap and 'result' in snap and 'data' in snap['result']:
                        netloc = urlsplit(base).netloc.replace(':', '_')
                        snap_path = os.path.join(log_dir(), f'browser_checkin_timeout_{netloc}.png')
                        with open(snap_path, 'wb') as f:
                            f.write(base64.b64decode(snap['result']['data']))
                        _log(f"⚠️ 等待验证超时（截图已存 {snap_path}）")
                except Exception:
                    pass
                last_error = f'{base}: 等待 Turnstile 验证或签到响应超时 ({RESULT_WAIT_SECONDS}s)'
                _log(f"⚠️ {last_error}，尝试下一个域名")
                continue

            if result:
                if isinstance(result, dict) and result.get('reason') == 'turnstile':
                    try:
                        snap = cdp.call('Page.captureScreenshot', {'format': 'png'})
                        if snap and 'result' in snap and 'data' in snap['result']:
                            snap_path = os.path.join(log_dir(), 'browser_checkin_turnstile.png')
                            with open(snap_path, 'wb') as f:
                                f.write(base64.b64decode(snap['result']['data']))
                            _log(f"⚠️ 服务端仍要求 Turnstile（截图已存 {snap_path}）")
                    except Exception:
                        pass
                return result

        return {'request_failed': True, 'reason': 'browser-checkin-failed',
                'detail': str(last_error or '所有域名均未完成签到')}
    finally:
        _clear_cdp_session_cookies(cdp, injected_names, attempted_bases)


def _run_cdp_session(ws_url, cookie_header, user_agent=None):
    """通过已建立的 CDP WebSocket 会话执行签到。"""
    cdp = CDPClient(ws_url)
    try:
        return _run_cdp_session_with_client(cdp, cookie_header, user_agent=user_agent)
    finally:
        cdp.close()


def _pick_page_target_ws(targets):
    """从自启浏览器 /json 列表中选择 type=page 的空白页调试地址，跳过扩展后台页。"""
    if not isinstance(targets, list):
        return None
    for target in targets:
        if (isinstance(target, dict)
                and target.get('type') == 'page'
                and target.get('webSocketDebuggerUrl')
                and not str(target.get('url', '')).startswith('chrome-extension://')):
            return target['webSocketDebuggerUrl']
    for target in targets:
        if (isinstance(target, dict)
                and target.get('type') == 'page'
                and target.get('webSocketDebuggerUrl')):
            return target['webSocketDebuggerUrl']
    return None


def _try_domains_cdp(browser_path, cookie_header, headless, user_agent=None):
    """使用本地 Chrome/Edge 浏览器进程（通过 CDP 自动化协议）执行签到。"""
    # 动态分配空闲调试端口
    s = socket.socket()
    s.bind(('127.0.0.1', 0))
    port = s.getsockname()[1]
    s.close()

    p_dir = profile_dir()
    try:
        os.makedirs(p_dir, exist_ok=True)
    except OSError as e:
        _log(f"⚠️ 创建浏览器配置目录失败 ({p_dir}): {e}")
    log_dir()

    args = [
        browser_path,
        f'--remote-debugging-port={port}',
        f'--user-data-dir={p_dir}',
        '--no-first-run',
        '--no-default-browser-check',
        '--disable-blink-features=AutomationControlled',
        '--disable-features=TranslateUI',
        '--window-size=1920,1080',
        '--lang=zh-CN',
    ]
    # 在 root 环境、systemd 守护进程或 Linux 无头环境下添加安全/沙箱兼容参数
    if hasattr(os, 'geteuid') and (os.geteuid() == 0 or os.environ.get('INVOCATION_ID') or sys.platform.startswith('linux')):
        args.append('--no-sandbox')
    if headless:
        args.append('--headless=new')
        args.append('--disable-gpu')
        args.append('--disable-dev-shm-usage')
    if user_agent:
        args.append(f'--user-agent={user_agent}')
    args.append('about:blank')

    _log(f"🚀 启动系统浏览器: {os.path.basename(browser_path)} (headless={headless})")
    proc = subprocess.Popen(
        args,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        cwd=p_dir if os.path.isdir(p_dir) else None,
    )

    try:
        # 轮询等待 CDP 服务端口就绪
        ws_url = None
        for _ in range(50):
            if proc.poll() is not None:
                break
            try:
                with urllib.request.urlopen(f'http://127.0.0.1:{port}/json', timeout=1) as req:
                    pages = json.loads(req.read().decode())
                ws_url = _pick_page_target_ws(pages)
                if ws_url:
                    break
            except Exception:
                pass
            time.sleep(0.1)

        if not ws_url:
            err = ''
            if proc.poll() is not None and proc.stderr:
                try:
                    err = proc.stderr.read().decode('utf-8', errors='replace').strip()
                except Exception:
                    pass
            detail = f'未能连接到浏览器 CDP 调试端口 (exit code: {proc.returncode})'
            if err:
                detail += f': {err[:300]}'
            _log(f"⚠️ {detail}")
            return {'request_failed': True, 'reason': 'browser-checkin-failed',
                    'detail': detail}

        return _run_cdp_session(ws_url, cookie_header, user_agent=user_agent)
    except Exception as e:
        _log(f"⚠️ 浏览器签到异常 ({type(e).__name__})")
        return {'request_failed': True, 'reason': 'browser-checkin-failed',
                'detail': f'浏览器签到异常 ({type(e).__name__})'}
    finally:
        try:
            proc.terminate()
            proc.wait(timeout=3)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass


def _try_remote_cdp(cdp_url, cookie_header, user_agent=None):
    """连接到本机配置的 CDP 服务端点（如 http://127.0.0.1:9222），在隔离上下文中执行签到。"""
    _log("🌐 正在连接本机 CDP 服务…")
    try:
        browser_ws_url = resolve_cdp_url(cdp_url)
    except ValueError:
        detail = '自定义 CDP 地址无效，请检查本机调试端点配置'
        _log(f'⚠️ {detail}')
        return {'request_failed': True, 'reason': 'browser-checkin-failed', 'detail': detail}
    except Exception as e:
        _log(f"⚠️ 连接自定义 CDP 服务失败 ({type(e).__name__})")
        return {'request_failed': True, 'reason': 'browser-checkin-failed',
                'detail': f'连接自定义 CDP 服务失败 ({type(e).__name__})'}

    cdp = None
    browser_context_id = None
    target_id = None
    try:
        cdp = CDPClient(browser_ws_url)
        ctx_res = cdp.call(
            'Target.createBrowserContext',
            {'disposeOnDetach': True},
            timeout=10,
            use_session=False,
        )
        browser_context_id = (ctx_res or {}).get('result', {}).get('browserContextId')
        if not browser_context_id:
            raise RuntimeError('createBrowserContext-failed')

        target_res = cdp.call(
            'Target.createTarget',
            {'url': 'about:blank', 'browserContextId': browser_context_id},
            timeout=10,
            use_session=False,
        )
        target_id = (target_res or {}).get('result', {}).get('targetId')
        if not target_id:
            raise RuntimeError('createTarget-failed')

        attach_res = cdp.call(
            'Target.attachToTarget',
            {'targetId': target_id, 'flatten': True},
            timeout=10,
            use_session=False,
        )
        session_id = (attach_res or {}).get('result', {}).get('sessionId')
        if not session_id:
            raise RuntimeError('attachToTarget-failed')

        cdp.session_id = session_id
        return _run_cdp_session_with_client(cdp, cookie_header, user_agent=user_agent)
    except Exception as e:
        _log(f"⚠️ 自定义 CDP 服务签到异常 ({type(e).__name__})")
        return {'request_failed': True, 'reason': 'browser-checkin-failed',
                'detail': f'自定义 CDP 服务签到异常 ({type(e).__name__})'}
    finally:
        if cdp is not None:
            if target_id:
                try:
                    cdp.call('Target.closeTarget', {'targetId': target_id}, timeout=3, use_session=False)
                except Exception:
                    pass
            if browser_context_id:
                try:
                    cdp.call(
                        'Target.disposeBrowserContext',
                        {'browserContextId': browser_context_id},
                        timeout=3,
                        use_session=False,
                    )
                except Exception:
                    pass
            cdp.close()


def _pick_context(pw, headless, user_agent=None):
    """Playwright 兼容回退：按优先级启动浏览器，返回 (context, channel_name)。"""
    errors = []
    for channel in BROWSER_CHANNELS:
        kwargs = {
            'user_data_dir': profile_dir(),
            'headless': headless,
            'args': [
                '--disable-blink-features=AutomationControlled',
                '--no-first-run',
                '--no-default-browser-check',
            ],
        }
        if channel:
            kwargs['channel'] = channel
        if user_agent:
            kwargs['user_agent'] = user_agent
        try:
            context = pw.chromium.launch_persistent_context(**kwargs)
            return context, channel
        except Exception as e:
            errors.append(f'{channel or "chromium"}: {type(e).__name__}')
    raise RuntimeError('无可用浏览器通道（' + '; '.join(errors) + '）')


def _clear_playwright_session_cookies(context, cookie_names):
    """清理 Playwright 上下文中的会话 Cookie，防止多账号互相污染。"""
    for name in cookie_names:
        try:
            context.clear_cookies(name=name)
        except TypeError:
            try:
                context.clear_cookies()
            except Exception:
                pass
            break
        except Exception:
            pass


def _try_domains_playwright(context, cookie_header):
    """Playwright 兼容回退：逐域名打开签到页并点击。"""
    last_error = None
    checkin_name = re.compile(r'check\s*in', re.IGNORECASE)
    injected_names = set(SESSION_COOKIE_NAMES)

    try:
        for base in DOMAINS:
            captured = {'json': None}
            page = None

            def on_response(resp, _base=base):
                try:
                    path = urlsplit(resp.url).path.rstrip('/')
                    if (resp.url.startswith(_base) and path == '/api/user/checkin'
                            and resp.request.method == 'POST'):
                        body = resp.text()
                        try:
                            parsed = json.loads(body)
                            if not ('nonce' in parsed and 'ttl' in parsed and 'message' not in parsed):
                                captured['json'] = parsed
                        except ValueError:
                            captured['json'] = {'request_failed': True,
                                                'reason': 'browser-checkin-invalid-json'}
                except Exception:
                    pass

            try:
                cookies = parse_cookie_header(cookie_header, base)
                injected_names.update(c['name'] for c in cookies)
                _clear_playwright_session_cookies(context, injected_names)
                context.add_cookies(cookies)
                page = context.new_page()
                page.on('response', on_response)
                page.goto(base + CHECKIN_PAGE_PATH, wait_until='domcontentloaded', timeout=45000)
                _log("📄 已打开官方签到页，等待 Check in 按钮就绪…")

                btn = None
                deadline = time.monotonic() + BUTTON_WAIT_SECONDS
                while time.monotonic() < deadline and not captured['json']:
                    try:
                        btn = page.get_by_role('button', name=checkin_name).first
                        if btn.count() == 0:
                            btn = None
                        elif btn.is_disabled():
                            btn = None
                        else:
                            break
                    except Exception:
                        btn = None
                    page.wait_for_timeout(500)

                if captured['json']:
                    return captured['json']
                if btn is None:
                    last_error = f'{base}: 未找到可点击的 Check in 按钮'
                    _log(f"⚠️ {last_error}，尝试下一个域名")
                    continue

                _log("🖱️ 点击 Check in，页面将自行完成 Turnstile 验证…")
                with page.expect_response(lambda r: r.url.startswith(base)
                                          and urlsplit(r.url).path.rstrip('/') == '/api/user/checkin'
                                          and r.request.method == 'POST',
                                          timeout=RESULT_WAIT_SECONDS * 1000) as resp_info:
                    btn.click()
                resp = resp_info.value
                try:
                    captured['json'] = resp.json()
                except ValueError:
                    captured['json'] = {'request_failed': True,
                                        'reason': 'browser-checkin-invalid-json'}
                result = captured['json']
                if isinstance(result, dict) and result.get('reason') == 'turnstile':
                    _log("⚠️ 服务端仍要求 Turnstile")
                return result
            except Exception as e:
                last_error = f'{base}: {type(e).__name__}'
                _log(f"⚠️ 浏览器签到异常 {last_error}，尝试下一个域名")
            finally:
                if page:
                    try:
                        page.close()
                    except Exception:
                        pass

        return {'request_failed': True, 'reason': 'browser-checkin-failed',
                'detail': str(last_error or '所有域名均未完成签到')}
    finally:
        _clear_playwright_session_cookies(context, injected_names)


def _with_native_ua_retry(runner, user_agent):
    """优先使用配置 UA 执行签到；若服务端判定设备不一致，再改用原生 UA 重试一次。"""
    result = runner(user_agent)
    if (isinstance(result, dict) and user_agent
            and result.get('reason') in ('device-mismatch', 'http-auth-rejected')):
        _log("🔄 配置的 User-Agent 未通过服务端设备校验，尝试改用浏览器原生 User-Agent 重试…")
        result = runner(None)
    return result


def _run_cdp(cookie_header, user_agent, headless):
    """尝试使用 CDP 模式（本机回环 CDP 端点或本地已安装浏览器）执行签到。

    若未配置 CDP 端点且未找到本地浏览器，返回 None。
    """
    cdp_url = os.environ.get('GLADOS_CDP_URL', '').strip()
    if cdp_url:
        return _with_native_ua_retry(
            lambda ua: _try_remote_cdp(cdp_url, cookie_header, user_agent=ua),
            user_agent,
        )

    browser_path = find_browser_executable()
    if browser_path:
        _log(f"🌐 优先使用系统已安装浏览器: {browser_path}")
        return _with_native_ua_retry(
            lambda ua: _try_domains_cdp(browser_path, cookie_header, headless, user_agent=ua),
            user_agent,
        )

    return None


def _run_playwright(cookie_header, user_agent, headless):
    """使用 Playwright 引擎执行签到。"""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return {
            'request_failed': True,
            'reason': 'browser-checkin-unavailable',
            'detail': 'Playwright 未安装。可通过 pip install playwright && playwright install 安装，或切换至 CDP 引擎（GLADOS_BROWSER_ENGINE=cdp）。',
        }

    with sync_playwright() as pw:
        try:
            context, channel = _pick_context(pw, headless, user_agent=user_agent)
        except RuntimeError as e:
            if headless:
                return {'request_failed': True, 'reason': 'browser-checkin-unavailable',
                        'detail': str(e)}
            context, channel = _pick_context(pw, True, user_agent=user_agent)
        _log(f"🌐 Playwright 通道已启动（channel={channel or 'chromium'}）")
        try:
            result = _try_domains_playwright(context, cookie_header)
            if (isinstance(result, dict) and user_agent
                    and result.get('reason') in ('device-mismatch', 'http-auth-rejected')):
                _log("🔄 配置的 User-Agent 未通过服务端设备校验，尝试改用浏览器原生 User-Agent 重试…")
                try:
                    context.close()
                except Exception:
                    pass
                context, channel = _pick_context(pw, headless, user_agent=None)
                result = _try_domains_playwright(context, cookie_header)
            return result
        finally:
            try:
                context.close()
            except Exception:
                pass


def browser_checkin(cookie_header, user_agent, domains=None):
    """用真浏览器完成一次签到，返回 /api/user/checkin 的 JSON（或失败原因 dict）。

    支持通过 GLADOS_BROWSER_ENGINE 环境变量显式指定驱动引擎：
      - 'auto'（默认）：优先使用系统已安装的 Edge/Chrome（原生 CDP），未检测到时自动回退到 Playwright；
      - 'cdp'：强制仅使用原生 CDP 驱动模式（系统浏览器或 GLADOS_CDP_URL）；
      - 'playwright'：强制仅使用 Playwright 驱动模式。
    """
    if domains:
        globals()['DOMAINS'] = tuple(domains)

    headless_env = os.environ.get('GLADOS_BROWSER_HEADLESS', '').strip().lower()
    if headless_env in ('1', 'true', 'yes'):
        headless = True
    elif headless_env in ('0', 'false', 'no'):
        headless = False
    else:
        # 自动判定：如果检测不到 DISPLAY 或 WAYLAND_DISPLAY（如后台 systemd 服务），自动转为无头模式
        has_display = bool(
            os.environ.get('DISPLAY')
            or os.environ.get('WAYLAND_DISPLAY')
            or sys.platform in ('win32', 'darwin')
        )
        headless = not has_display
        if headless:
            _log("⚠️ 未检测到图形桌面（DISPLAY/WAYLAND_DISPLAY），自动切换至无头模式（headless）")

    engine = os.environ.get('GLADOS_BROWSER_ENGINE', 'auto').strip().lower()

    if engine == 'playwright':
        return _run_playwright(cookie_header, user_agent, headless)

    if engine == 'cdp':
        result = _run_cdp(cookie_header, user_agent, headless)
        if result is not None:
            return result
        return {
            'request_failed': True,
            'reason': 'browser-checkin-unavailable',
            'detail': '已指定使用 CDP 引擎 (GLADOS_BROWSER_ENGINE=cdp)，但未在系统中找到 Edge/Chrome/Chromium 浏览器，且未配置 GLADOS_CDP_URL。',
        }

    # 默认 auto 模式：先尝试 CDP，若无可用浏览器再回退到 Playwright
    result = _run_cdp(cookie_header, user_agent, headless)
    if result is not None:
        return result

    pw_result = _run_playwright(cookie_header, user_agent, headless)
    if (isinstance(pw_result, dict)
            and pw_result.get('reason') == 'browser-checkin-unavailable'
            and 'Playwright 未安装' in pw_result.get('detail', '')):
        return {
            'request_failed': True,
            'reason': 'browser-checkin-unavailable',
            'detail': '未在系统中找到 Edge/Chrome/Chromium 浏览器，且未安装 Playwright。可通过环境变量 GLADOS_BROWSER_PATH 指定浏览器路径。',
        }
    return pw_result
