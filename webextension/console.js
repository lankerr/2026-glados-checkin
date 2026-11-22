const api = globalThis.browser || chrome;
const el = id => document.getElementById(id);
const t = key => api.i18n.getMessage(key);
const send = (type, extra = {}) => api.runtime.sendMessage({ type, ...extra });
document.documentElement.lang = t('lang');
document.title = t('name');
for (const node of document.querySelectorAll('[data-i]')) node.textContent = t(node.dataset.i);
const dateFormat = opts => new Intl.DateTimeFormat(t('lang'), { timeZone: 'Asia/Shanghai', ...opts });
const clock = dateFormat({ month:'2-digit', day:'2-digit', hour:'2-digit', minute:'2-digit', hourCycle:'h23' });
const date = dateFormat({ year:'numeric', month:'long', day:'numeric', weekday:'short' });
const format = new Intl.NumberFormat(t('lang'), { maximumFractionDigits: 8 });
let snapshot;
function cell(tag, value, parent) {
  const node = document.createElement(tag);
  node.textContent = value;
  parent.append(node);
  return node;
}
function renderLedger(result) {
  snapshot = result?.snapshot ? result : null;
  const data = snapshot?.snapshot;
  el('date').textContent = date.format(Date.now()) + ' · UTC+8';
  const current = data && Ledger.day(Date.now()) === Ledger.day(data.at);
  el('open').textContent = t(current && data.confirmed ? 'viewSite' : 'open');
  el('status').textContent = t(current ? (data.confirmed ? 'confirmed' : 'unknown') : 'notRead');
  el('hint').textContent = t(current && data.confirmed ? 'confirmedHint' : 'actionHint');
  el('points').textContent = data ? format.format(data.points) : '—';
  el('account').textContent = data ? result.account + ' · ' + clock.format(data.at) : t('accountHint');
  const rows = el('rows');
  rows.replaceChildren();
  for (const row of data?.rows || []) {
    const tr = rows.insertRow();
    cell('td', clock.format(row.at), tr);
    cell('td', t(row.type), tr);
    const td = cell('td', (row.change > 0 ? '+' : '') + format.format(row.change), tr);
    td.className = row.change > 0 ? 'amount gain' : 'amount';
  }
  el('table').hidden = !rows.children.length;
  el('empty').hidden = !el('table').hidden;
  el('empty').textContent = t(!data ? 'unreadLedger' : data.historyAvailable ? 'emptyLedger' : 'missingLedger');
}
let local;
async function renderState() {
  const s = await send('state');
  if (!s?.hosts) throw new Error('state');
  if (local?.host && local.host !== s.host) renderLedger(null);
  local = s;
  const select = el('host');
  if (!select.options.length) s.hosts.forEach(host => select.add(new Option(host, host)));
  select.value = s.host;
  el('reminder').checked = s.reminder;
  const activity = el('activity');
  activity.replaceChildren();
  for (const entry of s.activity) {
    const li = document.createElement('li');
    const box = cell('span', t(entry.kind), li);
    cell('small', entry.host, box);
    cell('time', clock.format(entry.at), li);
    activity.append(li);
  }
  el('noActivity').hidden = s.activity.length > 0;
}
function lock(value) {
  for (const id of ['host', 'open', 'refresh', 'reminder', 'clear']) el(id).disabled = value;
  if (!value) el('clear').disabled = !local?.activity?.length;
}
async function act(type, extra) {
  lock(true);
  el('feedback').textContent = t('working');
  if (type === 'host' || type === 'refresh') renderLedger(null);
  try {
    const result = await send(type, { host: local.host, ...extra });
    if (type === 'refresh') renderLedger(result);
    el('feedback').textContent = t(result.error || ({ open:'afterOpen', refresh:'read', host:'saved', clear:'cleared', reminder:'saved' })[type]);
  } catch { el('feedback').textContent = t('unavailable'); }
  finally {
    try { await renderState(); } catch { el('feedback').textContent = t('unavailable'); }
    lock(false);
  }
}
for (const id of ['open','refresh','clear']) el(id).addEventListener('click', () => act(id));
el('host').addEventListener('change', () => act('host', { value:el('host').value }));
el('reminder').addEventListener('change', () => act('reminder', { value:el('reminder').checked }));
document.addEventListener('visibilitychange', () => {
  if (!document.hidden) {
    // Login cookies or the active container can change while the desk is away.
    renderLedger(null);
    renderState().catch(() => { el('feedback').textContent = t('unavailable'); });
  }
});
setInterval(() => {
  if (!document.hidden && (!snapshot || Ledger.day(snapshot.snapshot.at) !== Ledger.day(Date.now()))) renderLedger(snapshot);
}, 60000);
renderLedger(null);
renderState().then(() => lock(false), () => { el('feedback').textContent = t('unavailable'); });
