// GLaDOS Check-in extension — content script（只在 #glados-auto 时工作）
// 职责：等按钮 -> 点击（页面自身完成 Turnstile）-> 捕获 /api/user/checkin 响应 -> 上报

// 只认当前官网源上的真正签到接口：POST 且路径恰为 /api/user/checkin。
// 排除 GET、/api/user/checkin/challenge、跨源同名路径与同源其他前缀，
// 避免把人机验证准备阶段的 200 响应记成签到结果。
const isCheckinPost = (url, origin) => {
  try {
    const u = new URL(String(url), origin);
    return u.origin === origin && u.pathname === '/api/user/checkin';
  } catch (e) { return false; }
};

// 签到按钮识别：页面结构之外的文案兜底，覆盖英文与中文界面
const isCheckinButtonText = (text, ariaLabel) =>
  /check\s*-?\s*in|签到/i.test(((text || '') + ' ' + (ariaLabel || '')).trim());

// 供离线单测使用（node --test extension/tests/）；浏览器内容脚本环境不受影响
if (typeof module !== 'undefined' && module.exports) {
  module.exports = { isCheckinPost, isCheckinButtonText };
}

(() => {
  if (typeof location === 'undefined' || !location.hash.includes('glados-auto')) return;
  // 读取 _locales 文案，供签到失败时的上报信息使用
  const t = (key) => chrome.i18n.getMessage(key);

  const send = (payload) => {
    try { chrome.runtime.sendMessage(payload); } catch (e) { /* 扩展重载中 */ }
  };

  // 未登录被重定向到认证页
  if (location.pathname.startsWith('/authenticate')) {
    send({ type: 'need-login' });
    return;
  }

  // ---- 捕获 axios(XHR) / fetch 的签到响应 ----
  const origOpen = XMLHttpRequest.prototype.open;
  const origSend = XMLHttpRequest.prototype.send;
  XMLHttpRequest.prototype.open = function (method, url, ...rest) {
    this._gladosUrl = String(url);
    this._gladosMethod = String(method || '').toUpperCase();
    return origOpen.call(this, method, url, ...rest);
  };
  XMLHttpRequest.prototype.send = function (body) {
    if (this._gladosMethod === 'POST' && isCheckinPost(this._gladosUrl, location.origin)) {
      this.addEventListener('load', () => {
        try { send({ type: 'checkin-result', result: JSON.parse(this.responseText) }); }
        catch (e) { send({ type: 'checkin-result', result: { code: -1, message: t('parseError') } }); }
      });
    }
    return origSend.call(this, body);
  };
  const origFetch = window.fetch;
  window.fetch = function (input, init) {
    const p = origFetch.apply(this, arguments);
    const url = typeof input === 'string' ? input : (input && input.url) || '';
    const method = String((init && init.method) || (input && input.method) || 'GET').toUpperCase();
    if (method === 'POST' && isCheckinPost(url, location.origin)) {
      p.then(r => r.clone().json().then(j => send({ type: 'checkin-result', result: j })).catch(() => {}));
    }
    return p;
  };

  // ---- 等待并点击签到按钮（页面结构 button.ckb 优先，文案中英文兜底） ----
  const findButton = () =>
    document.querySelector('button.ckb') ||
    [...document.querySelectorAll('button')].find(b =>
      isCheckinButtonText(b.textContent, b.getAttribute('aria-label')));

  const deadline = Date.now() + 60000; // 页面自身等 Turnstile 最多 ~90s，按钮先出现的等点击
  const timer = setInterval(() => {
    if (Date.now() > deadline + 90000) {
      clearInterval(timer);
      send({ type: 'checkin-result', result: { code: -1, message: t('timeoutNoButton') } });
      return;
    }
    const btn = findButton();
    if (btn && !btn.disabled) {
      clearInterval(timer);
      btn.click();
    }
  }, 500);
})();
