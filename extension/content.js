// GLaDOS Check-in extension — content script（只在 #glados-auto 时工作）
// 职责：等按钮 -> 点击（页面自身完成 Turnstile）-> 捕获 /api/user/checkin 响应 -> 上报

(() => {
  if (!location.hash.includes('glados-auto')) return;
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
    return origOpen.call(this, method, url, ...rest);
  };
  XMLHttpRequest.prototype.send = function (body) {
    if (this._gladosUrl && this._gladosUrl.includes('/api/user/checkin')) {
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
    if (url.includes('/api/user/checkin')) {
      p.then(r => r.clone().json().then(j => send({ type: 'checkin-result', result: j })).catch(() => {}));
    }
    return p;
  };

  // ---- 等待并点击 Check in ----
  const findButton = () =>
    [...document.querySelectorAll('button')].find(b =>
      /check\s*in/i.test((b.textContent || '').trim()) || /check\s*in/i.test(b.getAttribute('aria-label') || ''));

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
