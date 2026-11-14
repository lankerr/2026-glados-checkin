#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
2026 GLaDOS 自动签到 (积分增强版)

功能：
- 全自动签到
- 精准获取当前积分 (Points)
- 积分达标自动兑换会员天数（默认 500 分兑换 100 天，可配置/关闭）
- PushPlus / Server酱 微信推送（包含积分、剩余天数、签到结果、兑换结果）
- 智能多域名切换 (优先 glados.cloud)
- 支持 Cookie-Editor 导出格式
"""

import html
import hashlib
import json
import math
import os
import re
import sys
import time
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit

import requests

# Fix Windows Unicode Output
if sys.platform.startswith('win'):
    sys.stdout.reconfigure(encoding='utf-8')

# ================= 配置 =================

# 域名优先级：Cloud 第一
DOMAINS = [
    "https://glados.cloud",
    "https://glados.rocks", 
    "https://glados.network",
]

DEFAULT_USER_AGENT = (
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
    'AppleWebKit/537.36 (KHTML, like Gecko) '
    'Chrome/120.0.0.0 Safari/537.36'
)

HEADERS = {
    'Content-Type': 'application/json;charset=UTF-8',
    'Accept': 'application/json, text/plain, */*',
    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
    'Sec-Fetch-Dest': 'empty',
    'Sec-Fetch-Mode': 'cors',
    'Sec-Fetch-Site': 'same-origin',
}

NORMAL_CHECKIN_MESSAGES = (
    "checkin! got",
    "checkin repeats! please try tomorrow",
    "today's observation logged",
)

# The current official console obtains a fresh challenge, waits at least 2.5 s,
# and sends SHA-256(nonce + ".glados-observe-v1") with the check-in request.
# Allow a small margin beyond that minimum, as in the reference script in #28.
CHECKIN_CHALLENGE_DELAY = 2.7

# 积分兑换计划 (#11)：消耗 points 积分兑换 days 天会员。
# 通过环境变量 EXCHANGE_PLAN 选择，默认 plan500（500 分兑换 100 天），
# 设为 off 关闭自动兑换。
EXCHANGE_PLANS = {
    "plan100": {"points": 100, "days": 10},
    "plan200": {"points": 200, "days": 30},
    "plan500": {"points": 500, "days": 100},
}

EXCHANGE_DISABLED_VALUES = ("", "off", "no", "none", "false", "0", "disabled")

CURRENT_SESSION_COOKIES = ('gld:sess', 'gld:sess.sig')
LEGACY_SESSION_COOKIES = ('koa:sess', 'koa:sess.sig')

# ================= 工具函数 =================

def beijing_now():
    return datetime.now(timezone(timedelta(hours=8)))


def beijing_time():
    return beijing_now().strftime("%Y-%m-%d %H:%M:%S")


def parse_finite_number(raw):
    """Parse finite int/float or numeric string; reject booleans and non-finite values."""
    if isinstance(raw, bool) or raw is None:
        return None
    if isinstance(raw, (int, float)):
        return float(raw) if math.isfinite(raw) else None
    if isinstance(raw, str):
        text = raw.strip()
        if not text:
            return None
        try:
            num = float(text)
        except ValueError:
            return None
        return num if math.isfinite(num) else None
    return None


def format_points_number(raw, signed=False):
    """Format point amounts without truncating non-zero decimals (e.g. 14.0 -> 14, 1.5 -> 1.5)."""
    num = parse_finite_number(raw)
    if num is None:
        return None
    if abs(num - round(num)) < 1e-9:
        integer = int(round(num))
        if signed:
            return f"+{integer}" if integer >= 0 else str(integer)
        return str(integer)
    formatted = f"{num:.4f}".rstrip('0').rstrip('.')
    if signed and num >= 0 and not formatted.startswith('+'):
        return '+' + formatted
    return formatted


def format_beijing_timestamp_ms(timestamp):
    """Return (formatted_datetime, YYYY-MM-DD) in Beijing time for a ms epoch timestamp."""
    if isinstance(timestamp, bool) or not isinstance(timestamp, (int, float)) or not math.isfinite(timestamp):
        return None, None
    try:
        dt = datetime.fromtimestamp(timestamp / 1000, timezone(timedelta(hours=8)))
    except (ValueError, OverflowError, OSError):
        return None, None
    return dt.strftime('%Y-%m-%d %H:%M:%S 北京时间'), dt.strftime('%Y-%m-%d')


def log(msg):
    print(f"[{beijing_time()} 北京时间] {msg}", flush=True)

def extract_cookie(raw: str):
    """提取 Cookie，支持请求头及 Cookie-Editor JSON 导出格式。"""
    if not raw:
        return None
    raw = raw.strip()
    raw = re.sub(r'^cookie\s*:\s*', '', raw, flags=re.IGNORECASE)
    
    # GLaDOS 2026 新会话与旧 Koa 会话的 Cookie 请求头格式。
    if any(f'{name}=' in raw for name in CURRENT_SESSION_COOKIES + LEGACY_SESSION_COOKIES):
        return raw
        
    # Cookie-Editor 的 JSON 数组导出，或旧版 {"token": "..."} 格式。
    if raw.startswith(('{', '[')):
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, list):
                pairs = []
                for item in parsed:
                    if not isinstance(item, dict):
                        continue
                    name = item.get('name')
                    value = item.get('value')
                    if name and value is not None:
                        pairs.append(f'{name}={value}')
                cookie = '; '.join(pairs)
                return cookie if cookie and get_session_cookie_kind(cookie) else None

            token = parsed.get('token') if isinstance(parsed, dict) else None
            return f'koa:sess={token}' if token else None
        except (json.JSONDecodeError, AttributeError, TypeError):
            return None
        
    # JWT Token
    if raw.count('.') == 2 and '=' not in raw and len(raw) > 50:
        return 'koa:sess=' + raw
        
    # Standard
    return raw


def get_cookie_names(cookie_header):
    """Return Cookie names only; values are deliberately never logged."""
    names = set()
    for item in cookie_header.split(';'):
        name, separator, _ = item.strip().partition('=')
        if separator and name:
            names.add(name)
    return names


def get_session_cookie_kind(cookie_header):
    """Identify a complete current or legacy signed session Cookie pair."""
    names = get_cookie_names(cookie_header)
    if set(CURRENT_SESSION_COOKIES).issubset(names):
        return 'gld'
    if set(LEGACY_SESSION_COOKIES).issubset(names):
        return 'koa'
    return None

def get_cookies():
    raw = os.environ.get("GLADOS_COOKIE", "")
    if not raw:
        log("❌ 未配置 GLADOS_COOKIE")
        return []

    # A Cookie-Editor export is one JSON document. Its formatting newlines
    # and ampersands inside values are not account separators.
    if raw.lstrip().startswith(('{', '[')):
        cookie = extract_cookie(raw)
        return [cookie] if cookie else []
    
    # Split by enter or &
    sep = '\n' if '\n' in raw else '&'
    return [cookie for item in raw.split(sep) if (cookie := extract_cookie(item))]


class UserAgentConfigurationError(ValueError):
    """Invalid local User-Agent input; messages never contain the supplied value."""


def normalize_user_agent(raw):
    """Remove common copy/paste wrappers without altering the browser value."""
    if any((ord(char) < 32 and char not in '\t\r\n') or ord(char) == 127 for char in raw):
        raise UserAgentConfigurationError('含有无效控制字符，请重新复制浏览器的 User-Agent')
    value = raw.strip()
    if not value:
        return '', False
    if '\r' in value or '\n' in value:
        raise UserAgentConfigurationError('含有换行，请粘贴完整单行 User-Agent')
    try:
        value.encode('latin-1')
    except UnicodeEncodeError:
        raise UserAgentConfigurationError(
            '含有不支持的字符，请重新复制浏览器的 User-Agent，不要加入说明文字或中文引号'
        ) from None

    original = value
    prefix_removed = False
    if value.lower().startswith('user-agent:'):
        value = value[len('user-agent:'):].strip()
        prefix_removed = True
    if len(value) >= 2 and value[0] == value[-1]:
        inner = value[1:-1]
        # Apostrophes can be legal product-token characters. Preserve a quoted
        # single token; only unwrap full, space-containing browser strings or
        # an explicitly copied header name. Double quotes are not token chars.
        single_quote_wrapper = value[0] == "'" and (
            not inner or any(char in ' \t' for char in inner)
            or inner.lower().startswith('user-agent:')
        )
        if value[0] == '"' or single_quote_wrapper:
            value = inner.strip()
    if not prefix_removed and value.lower().startswith('user-agent:'):
        value = value[len('user-agent:'):].strip()
    if not value:
        raise UserAgentConfigurationError('只有请求头名称或引号，没有 User-Agent 值')
    if value[0] == '"' or value[-1] == '"':
        raise UserAgentConfigurationError('外层双引号不成对或重复，请只保留 User-Agent 值')
    if len(value) >= 2 and value[0] == value[-1] == "'" and any(char in ' \t' for char in value):
        raise UserAgentConfigurationError('包裹 User-Agent 的单引号重复，请只保留 User-Agent 值')
    if value.lower().startswith('user-agent:'):
        raise UserAgentConfigurationError('请求头名称重复，请只保留 User-Agent 值')
    return value, value != original


def get_browser_headers():
    """Build headers matching the browser that created the login session."""
    user_agent, _ = normalize_user_agent(os.environ.get("GLADOS_USER_AGENT", ""))
    user_agent = user_agent or DEFAULT_USER_AGENT
    headers = {'User-Agent': user_agent}

    chrome = re.search(r'(?:Chrome|Chromium)/(\d+)', user_agent)
    if chrome:
        major = chrome.group(1)
        if 'Macintosh' in user_agent:
            platform = 'macOS'
        elif 'Windows' in user_agent:
            platform = 'Windows'
        elif 'Android' in user_agent:
            platform = 'Android'
        elif 'Linux' in user_agent:
            platform = 'Linux'
        else:
            platform = 'Unknown'

        headers.update({
            'Sec-CH-UA': (
                f'"Chromium";v="{major}", '
                f'"Google Chrome";v="{major}", '
                '"Not_A Brand";v="99"'
            ),
            'Sec-CH-UA-Mobile': '?1' if 'Mobile' in user_agent else '?0',
            'Sec-CH-UA-Platform': f'"{platform}"',
        })

    return headers


def is_turnstile_checkin_result(result):
    """Return True when the server blocks automated check-in with Cloudflare Turnstile."""
    if not isinstance(result, dict):
        return False
    reason = str(result.get('reason', '')).strip().lower()
    message = str(result.get('message', '')).strip().lower()
    return reason == 'turnstile' or 'cloudflare verification failed' in message


def is_non_retryable_checkin_result(result):
    """Return True for authentication/device failures that waiting cannot fix."""
    if not isinstance(result, dict):
        return False
    code = result.get('code')
    reason = str(result.get('reason', '')).strip().lower()
    message = str(result.get('message', '')).strip().lower()
    return (
        code == -2
        or result.get('http_status') in (401, 403)
        or reason == 'device-mismatch'
        or '没有权限' in message
        or 'permission' in message
        or 'unauthorized' in message
        or 'automated check-in detected' in message
    )


def is_missing_api_response(result):
    return not isinstance(result, dict) or result.get('request_failed') is True


def summarize_checkin_failure(result):
    """Describe failures using fixed labels and allowlisted, non-secret metadata."""
    if not isinstance(result, dict):
        return '未收到有效 API 响应；本次请求失败，今日签到状态未知'

    reason = str(result.get('reason', '')).strip().lower()
    message = str(result.get('message', '')).strip().lower()
    if reason == 'checkin-challenge-unavailable':
        label = '未获取有效签到验证，本次未提交签到，请稍后重试'
    elif reason == 'checkin-challenge-expired':
        label = '签到验证已过期，本次未提交签到，请稍后重试'
    elif result.get('request_failed') is True:
        if result.get('invalid_headers') is True:
            label = '请求头格式无效，请检查 Cookie 和 User-Agent 格式'
        elif result.get('invalid_response') is True:
            label = '服务响应格式异常，未收到有效 API 响应'
        else:
            label = '网络或服务暂时异常，未收到有效 API 响应'
        label += '；本次请求失败，今日签到状态未知'
    elif is_turnstile_checkin_result(result):
        label = '服务端要求 Cloudflare Turnstile 人机验证，本次未入账；请通过官网浏览器手动签到'
    elif reason == 'device-mismatch':
        label = '服务端拒绝设备校验；请核对会话和 User-Agent 配置'
    elif 'automated check-in detected' in message:
        label = '服务端拒绝自动签到；请核对会话配置，仍失败时联系服务方'
    elif is_non_retryable_checkin_result(result):
        label = '服务端拒绝会话认证或访问'
    else:
        label = '签到失败'

    details = []
    code = result.get('code')
    if type(code) is int and -999 <= code <= 999:
        details.append(f'code={code}')
    status = result.get('http_status')
    if type(status) is int and 100 <= status <= 599:
        details.append(f'http_status={status}')
    if result.get('request_failed') is True and result.get('timed_out') is True:
        details.append('timeout=true')
    if reason in ('device-mismatch', 'http-auth-rejected', 'turnstile'):
        details.append(f'reason={reason}')
    return label + (f" [{', '.join(details)}]" if details else '')


def log_user_agent_configuration():
    try:
        user_agent, normalized = normalize_user_agent(os.environ.get('GLADOS_USER_AGENT', ''))
    except UserAgentConfigurationError as error:
        log(f'❌ User-Agent 配置错误: {error}')
        return False
    status = '已配置' if user_agent else '未配置，使用默认值'
    if normalized:
        status += '（已自动去除外层引号或请求头名称）'
    log('浏览器 User-Agent: ' + status)
    return True


def is_normal_checkin_result(result):
    """Return True for a new check-in or a harmless already-checked-in response."""
    if is_missing_api_response(result):
        return False
    if is_non_retryable_checkin_result(result) or is_turnstile_checkin_result(result):
        return False

    message = str(result.get('message', '')).strip().lower()
    if any(marker in message for marker in NORMAL_CHECKIN_MESSAGES):
        return True

    # GLaDOS has historically used code=0 for successful check-ins. Newer
    # duplicate/observation responses can use code=1 and are handled above.
    return result.get('code') == 0


REPEAT_CHECKIN_MESSAGES = (
    "checkin repeats! please try tomorrow",
    "today's observation logged",
)

BREAKDOWN_KEYS = ('base', 'level', 'streak', 'cable', 'lucky', 'site', 'exitIp')


def is_repeat_checkin_result(result):
    if not isinstance(result, dict):
        return False
    message = str(result.get('message', '')).strip().lower()
    return result.get('code') == 1 or any(marker in message for marker in REPEAT_CHECKIN_MESSAGES)


def extract_declared_checkin_points(result):
    """Extract server-declared gained points and optional raw breakdown sum from /api/user/checkin."""
    if not isinstance(result, dict):
        return None, None
    declared = parse_finite_number(result.get('points')) if 'points' in result else None
    if declared is None:
        message = str(result.get('message', ''))
        match = re.search(r'checkin!\s*got\s*([+-]?\d+(?:\.\d+)?)\s*point', message, flags=re.IGNORECASE)
        if match:
            declared = parse_finite_number(match.group(1))

    breakdown = result.get('breakdown') or result.get('settlement')
    breakdown_sum = None
    if isinstance(breakdown, dict):
        values = [parse_finite_number(breakdown.get(key)) for key in BREAKDOWN_KEYS]
        present = [v for v in values if v is not None]
        if present:
            breakdown_sum = sum(present)
    return declared, breakdown_sum


def summarize_current_run_gain(result, is_success, client):
    """Keep API claims and ledger observations separate: no transaction linkage exists.

    A same-day credit, even for the same amount, can be an earlier/manual or
    unrelated credit. A final refusal/repeat response cannot exclude a credit
    from an earlier request whose response was lost during this run.
    """
    if not is_success:
        return '未确认（最终请求未成功；本轮是否入账未知，请核对完整流水）'

    if is_repeat_checkin_result(result):
        claim = '接口返回今日已签到（不能据此确定本轮新增积分）'
    else:
        declared_num, breakdown_sum = extract_declared_checkin_points(result)
        if declared_num is None:
            claim = '接口返回成功（本次入账归属未确认）'
        else:
            amount = format_points_number(declared_num, signed=True)
            claim = f'接口声称 {amount} 分（本次入账归属未确认）'
        if breakdown_sum is not None:
            parts = format_points_number(breakdown_sum, signed=True)
            claim += f'；接口分项合计 {parts} 分（不据此推断封顶规则）'

    today_gain = getattr(client, 'today_positive_change', None)
    if isinstance(today_gain, str):
        return claim + f'；今日已读取流水中一笔正变动 {today_gain} 分（未关联本次请求，非今日合计）'
    return claim + '；已读取流水中未识别到今日正变动（不等于没有入账，记录可能缺失或延迟）'


def attempt_browser_checkin(client, max_attempts=2):
    """Turnstile 兜底：真浏览器打开官方签到页完成验证并签到。

    返回浏览器签到结果 dict；返回 None 表示兜底被禁用或环境不可用。
    任何异常都不应中断主流程，最终失败按 turnstile 原语义处理。
    """
    if os.environ.get('GLADOS_BROWSER_CHECKIN', '1').strip().lower() in ('0', 'false', 'no', 'off'):
        return None
    # GitHub Actions 是数据中心 IP + 无头临时容器，Turnstile 基本不可能放行，
    # 默认禁用以免浪费 runner 分钟数；确要尝试可显式设 GLADOS_BROWSER_CHECKIN=1。
    if (os.environ.get('GITHUB_ACTIONS', '').strip().lower() in ('1', 'true', 'yes')
            and os.environ.get('GLADOS_BROWSER_CHECKIN', '').strip().lower() not in ('1', 'true', 'yes', 'on')):
        log("⏭️ 检测到 GitHub Actions 环境：浏览器兜底默认禁用（数据中心 IP 无法可靠通过 Turnstile，请转本地运行）")
        return None
    try:
        from browser_checkin import browser_checkin
    except ImportError:
        log("⚠️ playwright 未安装（pip install playwright && playwright install chromium），无法使用浏览器兜底")
        return None
    try:
        ua = get_browser_headers().get('User-Agent')
    except UserAgentConfigurationError:
        ua = None
    if not ua:
        log("⚠️ 缺少浏览器 User-Agent，跳过浏览器兜底")
        return None
    result = None
    for i in range(1, max(1, max_attempts) + 1):
        log(f"🔄 浏览器签到兜底第 {i}/{max_attempts} 次（真页面自行完成 Turnstile）…")
        try:
            result = browser_checkin(client.cookie, ua)
        except Exception as e:  # noqa: BLE001 - 兜底通道绝不冒泡异常
            result = {'request_failed': True, 'reason': 'browser-checkin-error',
                      'detail': type(e).__name__}
        if is_normal_checkin_result(result) or is_non_retryable_checkin_result(result):
            return result
        if i < max_attempts:
            time.sleep(8)
    return result


def checkin_with_retry(client, attempts=3, delay_seconds=60):
    """Retry transient/unknown check-in failures without sending duplicate alerts."""
    attempts = max(1, attempts)
    last_result = None

    for attempt in range(1, attempts + 1):
        last_result = client.checkin()
        if is_normal_checkin_result(last_result):
            return last_result, True

        if is_non_retryable_checkin_result(last_result):
            log(f"❌ 签到认证失败，不再重试: {summarize_checkin_failure(last_result)}")
            return last_result, False

        if is_turnstile_checkin_result(last_result):
            # 2026-11 起官方签到接口要求 Cloudflare Turnstile 令牌，纯 API 无法取得；
            # 改用真浏览器打开官方签到页，由页面自身完成验证（见 browser_checkin.py）。
            browser_result = attempt_browser_checkin(client)
            if browser_result is None:
                log(f"❌ 签到需要人机验证，停止自动重试: {summarize_checkin_failure(last_result)}")
                return last_result, False
            if is_normal_checkin_result(browser_result):
                return browser_result, True
            if is_non_retryable_checkin_result(browser_result):
                log(f"❌ 浏览器签到被拒绝，不再重试: {summarize_checkin_failure(browser_result)}")
                return browser_result, False
            log(f"❌ 浏览器兜底未通过人机验证: {summarize_checkin_failure(browser_result)}")
            return browser_result, False

        if attempt < attempts:
            log(f"⚠️ 签到第 {attempt}/{attempts} 次失败，{delay_seconds} 秒后重试")
            time.sleep(max(0, delay_seconds))

    return last_result, False

# ================= 核心逻辑 =================

class GLaDOS:
    def __init__(self, cookie):
        self.cookie = cookie
        self.domain = DOMAINS[0]
        self.email = "?"
        self.left_days = "?"
        self.points = "?"
        self.points_change = "?"
        self.points_change_time = "未知"
        self.today_positive_change = None
        self.has_dated_history = False
        self.exchange_info = ""
        self.exchange_result = ""
        self.plan = "?"
        self.session_cookie_kind = get_session_cookie_kind(cookie)
        if self.session_cookie_kind != 'gld':
            log(
                "⚠️ Cookie 未包含完整的 gld:sess 与 gld:sess.sig；"
                "2026-09 新版接口可能返回“没有权限”"
            )

    def req(self, method, path, data=None, form=False, domains=None):
        """带自动域名切换的请求；form=True 时以表单提交（兑换接口要求）"""
        # Validate local configuration before the retry loop or any network request.
        browser_headers = get_browser_headers()
        # Keep only fixed, non-secret failure metadata after all domains fail.
        failure = {'request_failed': True, 'reason': 'request-failed'}
        for d in DOMAINS if domains is None else domains:
            try:
                url = f"{d}{path}"
                h = HEADERS.copy()
                h.update(browser_headers)
                h['Cookie'] = self.cookie
                h['Origin'] = d
                h['Referer'] = f"{d}/console/checkin"

                if form:
                    # 表单提交交给 requests 自动设置 Content-Type，
                    # 手动预设 JSON 头会被兑换接口拒绝。
                    h.pop('Content-Type', None)
                    resp = requests.post(url, headers=h, data=data, timeout=10)
                elif method == 'GET':
                    resp = requests.get(url, headers=h, timeout=10)
                else:
                    resp = requests.post(url, headers=h, json=data, timeout=10)

                if resp.status_code == 200:
                    payload = resp.json()
                    if isinstance(payload, dict):
                        self.domain = d # Remember working domain
                        return payload
                    failure['invalid_response'] = True
                    log(f"⚠️ {d} 响应格式异常")
                    continue
                if resp.status_code in (401, 403):
                    # A rejected request must not be replayed on alternate domains.
                    # The response can be HTML or contain private details; do not echo it.
                    return {
                        'http_status': resp.status_code,
                        'reason': 'http-auth-rejected',
                    }
                failure['http_status'] = resp.status_code
                log(f"⚠️ {d} 返回 HTTP {resp.status_code}")
            except (requests.RequestException, ValueError) as e:
                # InvalidHeader and other request errors may embed Cookie values.
                if isinstance(e, requests.Timeout):
                    failure['timed_out'] = True
                elif isinstance(e, requests.exceptions.InvalidHeader):
                    failure['invalid_headers'] = True
                elif isinstance(e, ValueError):
                    failure['invalid_response'] = True
                log(f"⚠️ {d} 请求失败: {type(e).__name__}")
                continue
        return failure

    def get_status(self):
        """获取状态：天数、邮箱"""
        res = self.req('GET', '/api/user/status')
        if res and 'data' in res:
            d = res['data']
            self.email = d.get('email', 'Unknown')
            self.left_days = str(d.get('leftDays', '?')).split('.')[0]
            return True
        return False

    def get_points(self):
        """获取积分、变化历史、兑换计划"""
        res = self.req('GET', '/api/user/points')
        if res and 'points' in res:
            # 当前积分（保留非零小数，不因 split('.') 截断小数奖励）
            formatted_pts = format_points_number(res.get('points', '0'), signed=False)
            self.points = formatted_pts if formatted_pts is not None else '0'

            # This is the latest ledger entry, not a change caused by this run.
            self.points_change = '?'
            self.points_change_time = '未知'
            self.today_positive_change = None
            self.has_dated_history = False
            today_bj = beijing_now().strftime('%Y-%m-%d')

            history = res.get('history')
            if not isinstance(history, list):
                history = res.get('list') if isinstance(res.get('list'), list) else []

            if history:
                last = history[0] if isinstance(history[0], dict) else {}
                formatted_change = format_points_number(last.get('change', '0'), signed=True)
                self.points_change = formatted_change if formatted_change is not None else '+0'
                formatted_dt, _ = format_beijing_timestamp_ms(last.get('time'))
                if formatted_dt:
                    self.points_change_time = formatted_dt

                # Observation only: date/amount/business do not link a credit to this run.
                for item in history[:10]:
                    if not isinstance(item, dict):
                        continue
                    _, entry_date = format_beijing_timestamp_ms(item.get('time'))
                    if entry_date:
                        self.has_dated_history = True
                    entry_num = parse_finite_number(item.get('change'))
                    business = str(item.get('business', '')).strip().lower()
                    if (
                        self.today_positive_change is None
                        and entry_date == today_bj
                        and entry_num is not None
                        and entry_num > 0
                        and 'exchange' not in business
                        and 'refund' not in business
                    ):
                        self.today_positive_change = format_points_number(entry_num, signed=True)

            # 兑换计划
            plans = res.get('plans', {})
            pts = parse_finite_number(self.points)
            if pts is None:
                pts = 0.0
            exchange_lines = []
            if isinstance(plans, dict):
                for plan_data in plans.values():
                    if not isinstance(plan_data, dict):
                        continue
                    need = int(plan_data.get('points', 0))
                    days = plan_data.get('days', '?')
                    if pts >= need:
                        exchange_lines.append(f"✅ {need}分→{days}天 (可兑换)")
                    else:
                        diff_label = format_points_number(need - pts, signed=False) or str(need)
                        exchange_lines.append(f"❌ {need}分→{days}天 (差{diff_label}分)")
            self.exchange_info = "<br>".join(exchange_lines)
            return True
        return False

    def checkin(self):
        """执行签到"""
        challenge = self.req('GET', '/api/user/checkin/challenge')
        if is_non_retryable_checkin_result(challenge) or is_missing_api_response(challenge):
            return challenge
        nonce = challenge.get('nonce')
        ttl = challenge.get('ttl', 300000)
        if (
            challenge.get('code') != 0
            or not isinstance(nonce, str) or not 0 < len(nonce) <= 4096
            or type(ttl) not in (int, float)
            or (type(ttl) is float and not math.isfinite(ttl))
            or ttl <= CHECKIN_CHALLENGE_DELAY * 1000
        ):
            return {'request_failed': True, 'reason': 'checkin-challenge-unavailable'}

        # A nonce belongs to the origin which issued it. Do not replay the POST
        # on another domain; the outer retry obtains a fresh challenge instead.
        domain = self.domain
        received_at = time.monotonic()
        proof = hashlib.sha256((nonce + '.glados-observe-v1').encode('utf-8')).hexdigest()
        time.sleep(CHECKIN_CHALLENGE_DELAY)
        if (time.monotonic() - received_at) * 1000 >= ttl:
            return {'request_failed': True, 'reason': 'checkin-challenge-expired'}
        return self.req('POST', '/api/user/checkin', {
            'token': urlsplit(domain).hostname,
            'nonce': nonce,
            'proof': proof,
        }, domains=(domain,))

    def exchange(self, plan):
        """兑换会员天数：表单提交 planType (plan100/plan200/plan500)"""
        return self.req('POST', '/api/user/exchange', {'planType': plan}, form=True)

# ================= 自动兑换 (#11) =================

def get_exchange_plan():
    """读取自动兑换配置，返回计划 ID；关闭或无效时返回 None"""
    raw = os.environ.get("EXCHANGE_PLAN", "plan500").strip().lower()
    if raw in EXCHANGE_DISABLED_VALUES:
        return None
    if raw in EXCHANGE_PLANS:
        return raw
    log(f"⚠️ EXCHANGE_PLAN 值 '{raw}' 无效 (可选: {'/'.join(EXCHANGE_PLANS)}/off)，本次跳过兑换")
    return None


def auto_exchange(g, plan_id):
    """积分达标时自动兑换会员天数，返回用于推送的兑换说明"""
    info = EXCHANGE_PLANS[plan_id]
    need, days = info["points"], info["days"]

    pts = parse_finite_number(getattr(g, 'points', None))
    if pts is None:
        log("⚠️ 积分查询失败，跳过兑换")
        return "⚠️ 兑换跳过(积分查询失败)"

    pts_label = format_points_number(pts, signed=False)
    if pts < need:
        return f"⏭️ 积分不足({pts_label}/{need})，攒够自动兑换{days}天"

    res = g.exchange(plan_id)
    if res and res.get('code') == 0:
        log(f"🎁 自动兑换成功: {need}分 → +{days}天")
        # 兑换消耗积分、增加天数，刷新后推送里才是最新数据
        g.get_status()
        g.get_points()
        return f"🎁 兑换成功 +{days}天 (消耗{need}分)"

    err = res.get('message', 'Failure') if res else "Network Error"
    log(f"⚠️ 自动兑换失败: {err}")
    return f"⚠️ 兑换失败({err})"

# ================= 主程序 =================

def pushplus(token, title, content):
    if not token:
        return False
    try:
        url = "https://www.pushplus.plus/send"
        response = requests.post(
            url,
            json={'token': token, 'title': title, 'content': content, 'template': 'html'},
            timeout=10,
        )
        response.raise_for_status()
        payload = response.json()
        if payload.get('code') not in (None, 0, 200):
            raise RuntimeError(payload.get('msg', f"PushPlus code={payload.get('code')}"))
        log("✅ PushPlus 推送成功")
        return True
    except (requests.RequestException, ValueError, RuntimeError) as e:
        log(f"❌ PushPlus 推送失败: {e}")
        return False

def serverchan_push(sendkey, title, content):
    """发送 Server酱通知，兼容 Turbo 与 Server酱³ SendKey。"""
    sendkey = (sendkey or "").strip()
    if not sendkey:
        return False

    # 与官方 SDK 保持相同的 SendKey 路由，无需增加依赖。
    # https://sct.ftqq.com/docs/integrations/python/
    if sendkey.startswith("sctp"):
        match = re.match(r"sctp([0-9]+)t", sendkey)
        if not match:
            log("❌ Server酱 推送失败: Server酱³ SendKey 格式无效")
            return False
        url = f"https://{match.group(1)}.push.ft07.com/send/{sendkey}.send"
    else:
        url = f"https://sctapi.ftqq.com/{sendkey}.send"

    # 复用完整的多账号报告；先去标签再解码，保留正文里的 HTML 转义字符。
    text = re.sub(r"<br\s*/?>", "\n", content, flags=re.IGNORECASE)
    text = re.sub(r"</(?:h[1-6]|p|div)\s*>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    lines = [line.strip() for line in html.unescape(text).splitlines()]
    desp = "  \n".join(line for line in lines if line)

    try:
        response = requests.post(url, json={'title': title, 'desp': desp}, timeout=10)
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict) or payload.get('code') != 0:
            code = payload.get('code') if isinstance(payload, dict) else None
            detail = f"code={code}" if type(code) is int else "接口返回无效响应"
            log(f"❌ Server酱 推送失败: {detail}")
            return False
        log("✅ Server酱 推送成功")
        return True
    except (requests.RequestException, ValueError) as e:
        # HTTP 异常可能包含带 SendKey 的请求 URL，不输出原始异常或响应正文。
        log(f"❌ Server酱 推送失败: {type(e).__name__}")
        return False


def telegram_push(token, chat_id, title, content):
    if not token or not chat_id: return
    try:
        import re
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        # Convert HTML to be Telegram-compatible
        text = f"<b>{title}</b>\n\n{content}"
        
        # 1. Block elements replacements (handle tags with attributes)
        text = text.replace("<br>", "\n")
        # Handle H3 tags
        text = re.sub(r"<h3[^>]*>", "<b>", text)
        text = text.replace("</h3>", "</b>\n")
        
        # 2. Paragraph and Div tags
        text = re.sub(r"<(div|p)[^>]*>", "", text)
        text = re.sub(r"</(div|p)>", "\n", text)
        
        # 3. Span and small tags
        text = re.sub(r"<(span|small)[^>]*>", "", text)
        text = re.sub(r"</(span|small)>", "", text)
        
        # 4. Final cleaning: Strip all HTML tags EXCEPT the ones supported by Telegram: b, i, u, s, a, code, pre
        text = re.sub(r"<(?!\/?(b|i|u|s|a|code|pre)\b)[^>]+>", "", text)
        
        # 5. Dedent each line to fix alignment issues caused by HTML template indentation
        lines = [line.strip() for line in text.split('\n')]
        text = "\n".join(lines)
        
        # 6. Collapse multiple newlines
        text = re.sub(r"\n\s*\n", "\n\n", text).strip()
        
        data = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML"
        }
        resp = requests.post(url, json=data, timeout=10)
        if resp.status_code != 200:
            log(f"❌ Telegram 推送失败: HTTP {resp.status_code}")
            return False
        log("✅ Telegram 推送成功")
        return True
    except (requests.RequestException, ValueError) as e:
        log(f"❌ Telegram 推送失败: {e}")
        return False

def summarize_readonly_ledger(client, status_ok, points_ok):
    """Describe ledger observations in read-only mode without sending a check-in."""
    if not status_ok:
        return '未获取（登录状态读取未成功，本次未发起签到请求）'
    if not points_ok:
        return '未获取（积分流水读取未成功，本次未发起签到请求）'
    today_gain = getattr(client, 'today_positive_change', None)
    if isinstance(today_gain, str):
        return (
            f'本次为只读核对（未发起签到请求）；今日已读取流水中一笔正变动 {today_gain} 分'
            '（非今日合计，可能来自网页手动签到或其他变动）'
        )
    return '本次为只读核对（未发起签到请求）；已读取流水中未识别到今日正变动（不等于没有入账，今日可能尚未签到或记录延迟）'


def render_account_card(
    index,
    client,
    gain_summary,
    status_message,
    exchange_line="",
    gain_heading="签到响应与流水观察",
    result_heading="签到结果",
):
    """Render per-account HTML card for PushPlus/ServerChan/Telegram notifications."""
    account_label = str(client.email) if client.email != '?' else f'账号 {index}'
    points_label = str(client.points) if client.points != '?' else '未获取'
    change_time = (
        client.points_change_time
        if isinstance(getattr(client, 'points_change_time', None), str) else '未知'
    )
    history_label = (
        f'{client.points_change}（{change_time}；历史记录，不代表本次新增）'
        if client.points_change != '?' else '未获取'
    )
    days_label = f'{client.left_days} 天' if client.left_days != '?' else '未获取'
    return f"""
<div style="border:2px solid #333; padding:15px; margin-bottom:15px; border-radius:10px; background:#fff;">
    <h3 style="margin:0 0 15px 0; color:#333; border-bottom:2px solid #333; padding-bottom:8px;">👤 {html.escape(account_label)}</h3>
    <p style="margin:8px 0; color:#000; font-size:16px;"><b>当前积分:</b> <span style="color:#e74c3c; font-size:22px; font-weight:bold;">{html.escape(points_label)}</span></p>
    <p style="margin:8px 0; color:#000; font-size:15px;"><b>{html.escape(gain_heading)}:</b> {html.escape(gain_summary)}</p>
    <p style="margin:8px 0; color:#666; font-size:14px;"><b>最近一笔积分变动:</b> {html.escape(history_label)}</p>
    <p style="margin:8px 0; color:#000; font-size:16px;"><b>剩余天数:</b> <span style="font-weight:bold;">{html.escape(days_label)}</span></p>
    <p style="margin:8px 0; color:#000; font-size:16px;"><b>{html.escape(result_heading)}:</b> {html.escape(str(status_message))}</p>{exchange_line}
    <div style="margin-top:15px; padding:12px; background:#f0f0f0; border-radius:8px; border:1px solid #ccc;">
        <p style="margin:0 0 8px 0; color:#333; font-weight:bold; font-size:15px;">🎁 兑换选项:</p>
        <p style="margin:0; color:#000; font-size:14px; line-height:1.8;">
{client.exchange_info}</p>
    </div>
</div>
"""


def notify_status_accounts(cookies):
    """Read account status and points ledger, then push a read-only summary card."""
    log('📬 只读状态与积分核对推送：仅读取登录状态与积分流水并发送通知，不发起签到请求、不自动兑换')
    if not log_user_agent_configuration():
        return 1
    exchange_plan = get_exchange_plan()
    results = []
    success_cnt = 0

    for i, cookie in enumerate(cookies, 1):
        g = GLaDOS(cookie)
        status_ok = g.get_status()
        points_ok = g.get_points() if status_ok else False
        query_ok = bool(status_ok and points_ok)
        if query_ok:
            success_cnt += 1
            msg = '只读状态与积分核对（未发起签到请求，不触发人机验证）'
        elif status_ok:
            msg = '登录状态正常，但积分流水读取未成功（未发起签到请求）'
        else:
            msg = '登录状态读取未成功，请检查会话配置或网络（未发起签到请求）'

        gain_summary = summarize_readonly_ledger(g, status_ok, points_ok)
        log(
            f"{'✅' if query_ok else '❌'} 账号 {i} | 积分: {g.points} | 流水观察: {gain_summary} | "
            f"天数: {g.left_days} | 模式: {msg}"
        )
        exchange_line = ""
        if exchange_plan:
            g.exchange_result = '⏭️ 只读核对模式，本次跳过自动兑换'
            exchange_line = f"""
    <p style="margin:8px 0; color:#000; font-size:16px;"><b>自动兑换:</b> {html.escape(g.exchange_result)}</p>"""
        results.append(render_account_card(
            i,
            g,
            gain_summary,
            msg,
            exchange_line=exchange_line,
            gain_heading="流水观察",
            result_heading="运行模式",
        ))

    ptoken = os.environ.get("PUSHPLUS_TOKEN")
    serverchan_sendkey = os.environ.get("SERVERCHAN_SENDKEY", "").strip()
    tg_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    tg_chat_id = os.environ.get("TELEGRAM_CHAT_ID")

    if not (ptoken or serverchan_sendkey or (tg_token and tg_chat_id)):
        log("⚠️ 未配置任何通知渠道（PUSHPLUS_TOKEN / SERVERCHAN_SENDKEY / TELEGRAM），无法发送状态推送")
        return 1

    outcome = '只读核对完成' if success_cnt == len(cookies) else '只读核对异常'
    title = f"GLaDOS状态核对: {outcome} {success_cnt}/{len(cookies)}"
    content = "".join(results)
    content += '<p>说明：本次为只读状态与积分流水核对推送，未调用签到或兑换接口，不会触发 Turnstile 验证。</p>'
    content += f"<br><small>时间（北京时间 UTC+8）: {beijing_time()}</small>"

    push_ok = True
    if ptoken:
        push_ok = pushplus(ptoken, title, content) and push_ok
    if serverchan_sendkey:
        push_ok = serverchan_push(serverchan_sendkey, title, content) and push_ok
    if tg_token and tg_chat_id:
        push_ok = bool(telegram_push(tg_token, tg_chat_id, title, content)) and push_ok

    return 0 if (success_cnt == len(cookies) and push_ok) else 1


def diagnose_accounts(cookies):
    """Read authentication status without check-in, redemption or notifications."""
    success_cnt = 0
    log('🔎 只读诊断：仅查询登录状态，不签到、不兑换、不推送')
    if not log_user_agent_configuration():
        return 1
    for i, cookie in enumerate(cookies, 1):
        client = GLaDOS(cookie)
        result = client.req('GET', '/api/user/status')
        authenticated = (
            isinstance(result, dict)
            and result.get('code') == 0
            and isinstance(result.get('data'), dict)
            and bool(result['data'])
        )
        # Never print response bodies: they may contain email or account data.
        if authenticated:
            success_cnt += 1
            log(f'✅ 账号 {i}: 登录状态查询成功')
        elif is_non_retryable_checkin_result(result):
            log(f'❌ 账号 {i}: 会话认证被拒绝；{summarize_checkin_failure(result)}')
        elif is_missing_api_response(result):
            log(f'❌ 账号 {i}: 登录状态查询失败；{summarize_checkin_failure(result)}')
        else:
            log(f'❌ 账号 {i}: 登录状态查询失败，请检查 API 返回分类和会话配置')
    log('只读查询通过不代表签到设备校验通过；实际签到仍需匹配浏览器 User-Agent')
    return 0 if success_cnt == len(cookies) else 1


def main():
    log("🚀 2026 GLaDOS Checkin Starting...")
    cookies = get_cookies()
    if not cookies:
        return 1

    if os.environ.get('CHECKIN_DIAGNOSTIC_ONLY', '').strip().lower() in ('1', 'true', 'yes'):
        return diagnose_accounts(cookies)

    if os.environ.get('CHECKIN_NOTIFY_STATUS_ONLY', '').strip().lower() in ('1', 'true', 'yes'):
        return notify_status_accounts(cookies)

    if not log_user_agent_configuration():
        return 1
    exchange_plan = get_exchange_plan()
    if exchange_plan:
        plan = EXCHANGE_PLANS[exchange_plan]
        log(f"🎁 自动兑换已启用: {plan['points']}分 → {plan['days']}天 (EXCHANGE_PLAN={exchange_plan})")
    else:
        log("⏭️ 自动兑换未启用")

    results = []
    success_cnt = 0
    exchange_events = 0

    for i, cookie in enumerate(cookies, 1):
        g = GLaDOS(cookie)

        # 1. Checkin
        attempts = int(os.environ.get("CHECKIN_MAX_ATTEMPTS", "3"))
        delay_seconds = int(os.environ.get("CHECKIN_RETRY_DELAY_SECONDS", "60"))
        res, is_success = checkin_with_retry(g, attempts, delay_seconds)
        msg = res.get('message', 'Success') if is_success else summarize_checkin_failure(res)

        gain_summary = '未确认（最终请求未成功；本轮是否入账未知，请核对完整流水）'
        if is_non_retryable_checkin_result(res):
            # Stop all follow-up requests for this account after an explicit denial.
            g.exchange_result = '⏭️ 认证被拒绝，跳过兑换'
        elif is_missing_api_response(res):
            # Do not add more reads or attempt redemption during a transport outage.
            g.exchange_result = '⏭️ 本次请求失败，跳过积分查询和兑换'
            gain_summary = '未获取（本次请求失败，今日签到状态未知）'
        else:
            # 2. Get Info (Refresh data)
            g.get_status()
            g.get_points()
            gain_summary = summarize_current_run_gain(res, is_success, g)

            # 2.5 Auto exchange (issue #11): runs only after a normal check-in
            # so failed check-ins do not trigger unexpected redemptions.
            if exchange_plan:
                if is_success:
                    g.exchange_result = auto_exchange(g, exchange_plan)
                    if not g.exchange_result.startswith("⏭️"):
                        exchange_events += 1
                else:
                    g.exchange_result = '⏭️ 本次签到未成功，跳过兑换'

        # 3. Log
        status_icon = "✅" if is_success else "❌"
        # Actions logs are public in a public repository. Keep account details
        # inside the private notification instead of exposing the email here.
        log(
            f"{status_icon} 账号 {i} | 积分: {g.points} | 入账核验: {gain_summary} | "
            f"天数: {g.left_days} | 结果: {msg}"
        )

        if is_success:
            success_cnt += 1

        # 4. Result Formatting
        exchange_line = ""
        if exchange_plan:
            exchange_line = f"""
    <p style="margin:8px 0; color:#000; font-size:16px;"><b>自动兑换:</b> {html.escape(g.exchange_result)}</p>"""
        results.append(render_account_card(i, g, gain_summary, msg, exchange_line=exchange_line))

    # Push
    push_level = os.environ.get("PUSH_LEVEL", "fail_only").lower()

    # Exchange outcomes (success or failure) are worth notifying even when
    # PUSH_LEVEL=fail_only, otherwise an always-failing exchange stays silent.
    if push_level == "fail_only" and success_cnt == len(cookies) and exchange_events == 0:
        log("⏭️ 根据 PUSH_LEVEL=fail_only 设置，所有账号签到成功，跳过推送")
        return 0

    ptoken = os.environ.get("PUSHPLUS_TOKEN")
    serverchan_sendkey = os.environ.get("SERVERCHAN_SENDKEY", "").strip()
    tg_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    tg_chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    
    if ptoken or serverchan_sendkey or (tg_token and tg_chat_id):
        outcome = '本次运行成功' if success_cnt == len(cookies) else '本次运行失败'
        title = f"GLaDOS签到: {outcome} {success_cnt}/{len(cookies)}"
        content = "".join(results)
        if success_cnt < len(cookies):
            content += '<p>以上仅反映本次运行。失败账号的今日签到状态未知，请结合当天其他成功运行或官网签到日历核对。</p>'
        content += f"<br><small>时间（北京时间 UTC+8）: {beijing_time()}</small>"
        
        if ptoken:
            pushplus(ptoken, title, content)
        if serverchan_sendkey:
            serverchan_push(serverchan_sendkey, title, content)
        if tg_token and tg_chat_id:
            telegram_push(tg_token, tg_chat_id, title, content)

    return 0 if success_cnt == len(cookies) else 1

if __name__ == '__main__':
    sys.exit(main())
