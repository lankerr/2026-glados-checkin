const $ = (id) => document.getElementById(id);
// 读取 _locales 文案；substitutions 对应 messages.json 中的 $1/$2 占位符
const t = (key, substitutions) => chrome.i18n.getMessage(key, substitutions);

// Chrome 不会替换弹窗 HTML 里的 __MSG_*__，需用 data-i18n 在脚本里填入
function applyI18n() {
  const lang = t('htmlLang');
  if (lang) document.documentElement.lang = lang;
  document.querySelectorAll('[data-i18n]').forEach((el) => {
    const msg = t(el.dataset.i18n);
    if (msg) el.textContent = msg;
  });
}

// 扩展无法探测或代开「关闭后继续运行后台应用」开关，只能按浏览器给出设置地址
function isEdge() {
  return /\bEdg\//.test(navigator.userAgent);
}
function settingsUrl() {
  return isEdge() ? 'edge://settings/system/manageSystem' : 'chrome://settings/system';
}
function applyBackgroundHint() {
  const url = settingsUrl();
  const toggle = t(isEdge() ? 'toggleNameEdge' : 'toggleNameChrome');
  $('bgHint').innerHTML = '';
  const text = t('bgHint', [url, toggle]);
  // 把设置地址单独标成 code，方便对照复制；其余说明保持纯文本
  const idx = text.indexOf(url);
  if (idx < 0) {
    $('bgHint').textContent = text;
  } else {
    $('bgHint').appendChild(document.createTextNode(text.slice(0, idx)));
    const code = document.createElement('code');
    code.textContent = url;
    $('bgHint').appendChild(code);
    $('bgHint').appendChild(document.createTextNode(text.slice(idx + url.length)));
  }
  $('copySettings').textContent = t('btnCopySettings');
}

async function copySettingsUrl() {
  const url = settingsUrl();
  try {
    await navigator.clipboard.writeText(url);
  } catch (e) {
    const ta = document.createElement('textarea');
    ta.value = url;
    document.body.appendChild(ta);
    ta.select();
    document.execCommand('copy');
    ta.remove();
  }
  const btn = $('copySettings');
  btn.textContent = t('btnCopied');
  setTimeout(() => { btn.textContent = t('btnCopySettings'); }, 1500);
}

// 接口可能返回 "257.00000000000000" 这类字符串，展示时去掉无意义小数
function formatPoints(value) {
  const n = Number(value);
  if (!Number.isFinite(n)) return String(value ?? '?');
  return Number.isInteger(n) ? String(n) : String(parseFloat(n.toFixed(4)));
}

async function refresh() {
  const s = await chrome.runtime.sendMessage({ type: 'get-state' });
  if (s) {
    $('streak').textContent = s.streak && s.streak.count
      ? t('streakDays', [String(s.streak.count), s.streak.lastDate])
      : t('streakNone');
    const today = new Date(Date.now() + (8 * 60 + new Date().getTimezoneOffset()) * 60000).toISOString().slice(0, 10);
    $('today').textContent = s.lastDoneDate === today ? t('todayDone') : t('todayPending');
  }
  try {
    const r = await fetch('https://glados.cloud/api/user/points', { credentials: 'include' });
    if (r.ok) { const d = await r.json(); $('points').textContent = formatPoints(d.points ?? '?'); }
    else $('points').textContent = t('loginRequired');
  } catch (e) { $('points').textContent = '-'; }
}
document.getElementById('run').addEventListener('click', async (e) => {
  e.target.disabled = true; e.target.textContent = t('btnRunning');
  await chrome.runtime.sendMessage({ type: 'manual-run' });
  setTimeout(() => { e.target.disabled = false; e.target.textContent = t('btnCheckin'); refresh(); }, 4000);
});
$('copySettings').addEventListener('click', copySettingsUrl);
applyI18n();
applyBackgroundHint();
refresh();
