const $ = (id) => document.getElementById(id);
// 读取 _locales 文案；substitutions 对应 messages.json 中的 $1/$2 占位符
const t = (key, substitutions) => chrome.i18n.getMessage(key, substitutions);

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
    if (r.ok) { const d = await r.json(); $('points').textContent = String(d.points ?? '?'); }
    else $('points').textContent = t('loginRequired');
  } catch (e) { $('points').textContent = '-'; }
}
document.getElementById('run').addEventListener('click', async (e) => {
  e.target.disabled = true; e.target.textContent = t('btnRunning');
  await chrome.runtime.sendMessage({ type: 'manual-run' });
  setTimeout(() => { e.target.disabled = false; e.target.textContent = t('btnCheckin'); refresh(); }, 4000);
});
refresh();
