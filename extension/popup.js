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
applyI18n();
refresh();
