const $ = (id) => document.getElementById(id);
async function refresh() {
  const s = await chrome.runtime.sendMessage({ type: 'get-state' });
  if (s) {
    $('streak').textContent = s.streak && s.streak.count ? `${s.streak.count} 天（${s.streak.lastDate}）` : '暂无';
    const today = new Date(Date.now() + (8 * 60 + new Date().getTimezoneOffset()) * 60000).toISOString().slice(0, 10);
    $('today').textContent = s.lastDoneDate === today ? '已完成 ✅' : '待签到';
  }
  try {
    const r = await fetch('https://glados.cloud/api/user/points', { credentials: 'include' });
    if (r.ok) { const d = await r.json(); $('points').textContent = String(d.points ?? '?'); }
    else $('points').textContent = '请先登录 glados.cloud';
  } catch (e) { $('points').textContent = '-'; }
}
document.getElementById('run').addEventListener('click', async (e) => {
  e.target.disabled = true; e.target.textContent = '已触发，签完自动关页…';
  await chrome.runtime.sendMessage({ type: 'manual-run' });
  setTimeout(() => { e.target.disabled = false; e.target.textContent = '立即签到'; refresh(); }, 4000);
});
refresh();
