// Shared by the background, dashboard and offline tests.
const Ledger = (() => {
  const day = ms => new Date(ms + 8 * 3600000).toISOString().slice(0, 10);
  function number(value) {
    if (typeof value !== 'number' && (typeof value !== 'string' || !/^[+-]?(?:\d+\.?\d*|\.\d+)$/.test(value.trim()))) return null;
    const n = Number(value);
    return Number.isFinite(n) ? n : null;
  }
  function timestamp(value) {
    const n = number(value);
    if (n === null) return null;
    const ms = n < 1e11 ? n * 1000 : n;
    return ms >= Date.UTC(2000, 0) && ms < Date.UTC(2100, 0) ? ms : null;
  }
  function parse(payload, now = Date.now()) {
    const points = number(payload?.points);
    if (points === null || ![undefined, 0, '0'].includes(payload.code)) return null;
    const history = Array.isArray(payload.history) ? payload.history : payload.list;
    const rows = [];
    for (const item of Array.isArray(history) ? history : []) {
      const at = timestamp(item?.time);
      const change = number(item?.change);
      if (at === null || change === null) continue;
      const type = String(item.business || '').trim().toLowerCase();
      rows.push({ at, change, type: ['system:checkin', 'checkin', 'check-in', 'check_in'].includes(type) ? 'checkin'
        : ['refund','exchange','promotion','compensation'].includes(type) ? type : 'other' });
    }
    rows.sort((a, b) => b.at - a.at);
    const today = day(now);
    const confirmed = rows.some(row => row.type === 'checkin' && row.change > 0 && row.at <= now && day(row.at) === today);
    return { points, rows: rows.slice(0, 10), confirmed, historyAvailable: Array.isArray(history), at: now };
  }
  function nextReminder(now = Date.now()) {
    const slot = Date.parse(day(now) + 'T09:30:00+08:00');
    return slot > now ? slot : slot + 86400000;
  }
  return { parse, day, nextReminder };
})();
if (typeof module !== 'undefined') module.exports = Ledger;
