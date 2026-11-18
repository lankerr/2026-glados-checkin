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


async function request(type, consent) {
  const r = await chrome.runtime.sendMessage({type, consent});
  if (!r?.ok) throw new Error('request_failed');
  return r.data;
}
async function refresh() {
  const s = await request('get-state');
  $('account').textContent = s.binding?.label || t('notConnected');
  $('automation').textContent = t(s.enabled ? 'enabled' : 'disabled');
  $('task').textContent = s.task ? (t(s.task.state) || s.task.state) : t('noTask');
  $('points').textContent = s.observation ? formatPoints(s.observation.points) : '—';
}
function action(id, type, confirmation) {
  $(id).addEventListener('click', async () => {
    if (confirmation && !confirm(t(confirmation))) return;
    $(id).disabled = true; $('error').textContent = '';
    try { await request(type, confirmation ? true : undefined); await refresh(); }
    catch { $('error').textContent = t('errorSafe'); }
    finally { $(id).disabled = false; }
  });
}
action('connect','connect');
action('enable','enable','consentEnable');
action('run','manual-run','consentRun');
action('pause','pause');
action('openSite','open-site');
action('reviewTask','review-task','consentReview');
action('forget','forget','consentForget');
$('copySettings').addEventListener('click', copySettingsUrl);
applyI18n();
applyBackgroundHint();
refresh().catch(() => { $('error').textContent = t('errorSafe'); });
