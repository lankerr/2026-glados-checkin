// Executed on explicit user request in the top frame's isolated world. Keep
// this function self-contained because scripting.executeScript serializes it.
async function readOfficialLedger(expectedOrigin) {
  if (location.origin !== expectedOrigin || location.pathname.replace(/\/$/, '') !== '/console/checkin') {
    return { error: 'noTab' };
  }
  async function json(path) {
    const response = await fetch(new URL(path, location.origin).href, {
      credentials: 'same-origin', cache: 'no-store', redirect: 'error',
      signal: AbortSignal.timeout(7000),
    });
    if (response.status === 401) throw new Error('login');
    if (response.status === 403) throw new Error('access');
    if (!response.ok) throw new Error('unavailable');
    return response.json();
  }
  async function identity() {
    const result = await json('/api/user/status');
    const email = result?.data?.email;
    if ([1, '1', 403, '403'].includes(result?.code)) throw new Error('login');
    if (![undefined, 0, '0'].includes(result?.code) || typeof email !== 'string' || !email.includes('@')) throw new Error('identity');
    return email.trim().toLowerCase();
  }
  try {
    const before = await identity();
    const data = await json('/api/user/points');
    if (before !== await identity()) return { error: 'switched' };
    const history = Array.isArray(data.history) ? data.history : data.list;
    const ledger = { points: data.points, code: data.code };
    if (Array.isArray(history)) ledger.history = history.map(row => ({
      time: row?.time, change: row?.change, business: row?.business,
    }));
    return { ledger, account: before.slice(0, 1) + '•••@' + before.split('@').pop() };
  } catch (err) {
    return { error: ['access','login','identity'].includes(err.message) ? err.message : 'unavailable' };
  }
}
