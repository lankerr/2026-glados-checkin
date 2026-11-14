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
  - 浏览器持久化目录放在系统用户数据区（LOCALAPPDATA），不落在仓库内，
    避免登录态被误提交；目录保存 cf_clearance 等状态，请勿随意删除。
  - 默认使用浏览器原生 UA（与 Sec-CH-UA 一致，Turnstile 通过率最高）；
    若服务端返回 device-mismatch，再用 cookie.txt 配套 UA 重试一次。
  - GitHub Actions 等机房环境由 checkin.attempt_browser_checkin 预先禁用，
    本模块不做二次判断。

安全与隐私：Cookie/UA 只注入浏览器，绝不写日志；截图仅存 logs/ 目录。
"""

import json
import os
import re
import time
from datetime import datetime, timezone, timedelta
from urllib.parse import urlsplit

# 浏览器通道优先级：真实 Chrome > 真实 Edge > Playwright 自带 Chromium
BROWSER_CHANNELS = ('chrome', 'msedge', None)
CHECKIN_PAGE_PATH = '/console/checkin'
# glados.network 当前 DNS 不稳定，暂不参与浏览器回退
DOMAINS = ('https://glados.cloud', 'https://glados.rocks')
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
    base = os.environ.get('LOCALAPPDATA') or os.path.expanduser('~')
    return os.path.join(base, 'glados-checkin-browser')


def parse_cookie_header(cookie_header, base_url):
    """把 'a=1; b=2' 请求头解析成绑定到目标站点的 Playwright Cookie 列表。

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


def _pick_context(pw, headless, user_agent=None):
    """按优先级启动浏览器，返回 (context, channel_name)。

    持久化目录 + 真实 Chrome/Edge + 关闭 AutomationControlled，让 Turnstile
    在常规浏览器环境中正常发放令牌；user_agent 仅在 device-mismatch 重试时传入。
    """
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
        except Exception as e:  # noqa: BLE001 - 逐通道回退需捕获所有启动错误
            errors.append(f'{channel or "chromium"}: {type(e).__name__}')
    raise RuntimeError('无可用浏览器通道（' + '; '.join(errors) + '）')


def _try_domains(context, cookie_header):
    """逐域名打开签到页并点击，返回 /api/user/checkin 的 JSON 或失败 dict。

    每个域名使用独立的响应捕获状态，避免上一域名的旧响应污染下一域名。
    """
    last_error = None
    checkin_name = re.compile(r'check\s*in', re.IGNORECASE)

    for base in DOMAINS:
        captured = {'json': None}
        page = None

        def on_response(resp, _base=base):
            try:
                if (resp.url.startswith(_base) and '/api/user/checkin' in resp.url
                        and resp.request.method == 'POST'):
                    body = resp.text()
                    try:
                        captured['json'] = json.loads(body)
                    except ValueError:
                        captured['json'] = {'request_failed': True,
                                            'reason': 'browser-checkin-invalid-json'}
            except Exception:  # noqa: BLE001 - 拦截失败不影响页面流程
                pass

        try:
            context.add_cookies(parse_cookie_header(cookie_header, base))
            page = context.new_page()
            page.on('response', on_response)
            page.goto(base + CHECKIN_PAGE_PATH, wait_until='domcontentloaded', timeout=45000)
            _log(f"📄 已打开官方签到页，等待 Check in 按钮就绪…")

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
                except Exception:  # noqa: BLE001 - 元素未出现属正常轮询
                    btn = None
                page.wait_for_timeout(500)

            if captured['json']:
                return captured['json']  # 页面自动重试已成功
            if btn is None:
                try:
                    page.screenshot(path=os.path.join('logs', 'browser_checkin_button_timeout.png'))
                except Exception:  # noqa: BLE001 - 截图失败不影响回退
                    pass
                last_error = f'{base}: 未找到可点击的 Check in 按钮'
                _log(f"⚠️ {last_error}，尝试下一个域名")
                continue

            _log("🖱️ 点击 Check in，页面将自行完成 Turnstile 验证…")
            with page.expect_response(lambda r: r.url.startswith(base)
                                      and '/api/user/checkin' in r.url
                                      and r.request.method == 'POST',
                                      timeout=RESULT_WAIT_SECONDS * 1000) as resp_info:
                btn.click()
            resp = resp_info.value
            # 注：resp.json()/resp.text() 的正文读取不受 expect_response 超时保护；
            # 极端情况下由外层计划任务的执行时限兜底强杀，此处不做无限阻塞防护。
            try:
                captured['json'] = resp.json()
            except ValueError:
                captured['json'] = {'request_failed': True,
                                    'reason': 'browser-checkin-invalid-json'}
            result = captured['json']
            if isinstance(result, dict) and result.get('reason') == 'turnstile':
                try:
                    page.screenshot(path=os.path.join('logs', 'browser_checkin_turnstile.png'))
                except Exception:  # noqa: BLE001
                    pass
                _log("⚠️ 服务端仍要求 Turnstile（截图已存 logs/browser_checkin_turnstile.png）")
            return result
        except Exception as e:  # noqa: BLE001 - 换域名重试
            last_error = f'{base}: {type(e).__name__}'
            _log(f"⚠️ 浏览器签到异常 {last_error}，尝试下一个域名")
        finally:
            if page:
                try:
                    page.close()
                except Exception:  # noqa: BLE001
                    pass

    return {'request_failed': True, 'reason': 'browser-checkin-failed',
            'detail': str(last_error or '所有域名均未完成签到')}


def browser_checkin(cookie_header, user_agent, domains=None):
    """用真浏览器完成一次签到，返回 /api/user/checkin 的 JSON（或失败原因 dict）。

    第一轮使用浏览器原生 UA（Turnstile 通过率最高）；若服务端判定设备不一致
    （device-mismatch / http-auth-rejected），改用 cookie.txt 配套 UA 再试一轮。
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return {'request_failed': True, 'reason': 'browser-checkin-unavailable',
                'detail': 'playwright 未安装'}

    headless = os.environ.get('GLADOS_BROWSER_HEADLESS', '').strip().lower() in ('1', 'true', 'yes')
    if domains:
        globals()['DOMAINS'] = tuple(domains)

    with sync_playwright() as pw:
        try:
            context, channel = _pick_context(pw, headless)
        except RuntimeError as e:
            if headless:
                return {'request_failed': True, 'reason': 'browser-checkin-unavailable',
                        'detail': str(e)}
            # 有头模式启动失败（如计划任务无桌面会话）时退回无头再试一次
            context, channel = _pick_context(pw, True)
        _log(f"🌐 浏览器兜底已启动（channel={channel or 'chromium'}）")
        try:
            result = _try_domains(context, cookie_header)
            # 设备一致性被拒：换 cookie.txt 配套 UA 重试一轮
            if (isinstance(result, dict) and user_agent
                    and result.get('reason') in ('device-mismatch', 'http-auth-rejected')):
                _log("🔄 服务端判定设备不一致，改用 cookie.txt 配套 User-Agent 重试…")
                try:
                    context.close()
                except Exception:  # noqa: BLE001
                    pass
                context, channel = _pick_context(pw, headless, user_agent=user_agent)
                result = _try_domains(context, cookie_header)
            return result
        finally:
            try:
                context.close()
            except Exception:  # noqa: BLE001
                pass
