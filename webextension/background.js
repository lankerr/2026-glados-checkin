if (typeof importScripts === 'function') importScripts('core.js', 'reader.js');
const api = globalThis.browser || chrome;
const hosts = api.runtime.getManifest().host_permissions.map(pattern => new URL(pattern).host);
const dashboard = api.runtime.getURL('console.html');
const reminderName = 'daily-reminder';
const t = key => api.i18n.getMessage(key);
let queue = Promise.resolve();
function serial(task) {
  const next = queue.then(task);
  queue = next.catch(() => {});
  return next;
}
async function state() {
  const data = await api.storage.local.get(['host', 'activity', 'reminder']);
  return { host: hosts.includes(data.host) ? data.host : hosts[0], activity: data.activity || [], reminder: data.reminder === true };
}
async function log(kind, host) {
  const { activity } = await state();
  await api.storage.local.set({ activity: [{ kind, host, at: Date.now() }, ...activity].slice(0, 30) });
}
async function schedule() {
  const { reminder } = await state();
  if (!reminder) return api.alarms.clear(reminderName);
  const alarm = await api.alarms.get(reminderName);
  if (!alarm) await api.alarms.create(reminderName, { when: Ledger.nextReminder() });
}
api.runtime.onStartup.addListener(() => serial(schedule));
api.runtime.onInstalled.addListener(() => serial(schedule));
api.alarms.onAlarm.addListener(alarm => {
  if (alarm.name !== reminderName) return;
  return serial(async () => {
    if (!(await state()).reminder) return;
    await api.alarms.create(reminderName, { when: Ledger.nextReminder() });
    await api.notifications.create(reminderName, {
      type: 'basic', iconUrl: api.runtime.getURL('icons/icon128.png'), title: t('name'), message: t('reminderText')
    });
  });
});
api.action.onClicked.addListener(() => api.runtime.openOptionsPage());
api.notifications.onClicked.addListener(id => {
  if (id === reminderName) return api.runtime.openOptionsPage();
});
async function command(message, windowId) {
  const current = await state();
  if (message.type === 'state') return { ...current, hosts };
  if (message.type === 'host' && hosts.includes(message.value)) {
    await api.storage.local.set({ host: message.value });
    return {};
  }
  if (message.type === 'reminder' && typeof message.value === 'boolean') {
    await api.storage.local.set({ reminder: message.value });
    await schedule();
    return {};
  }
  if (message.type === 'clear') {
    await api.storage.local.remove('activity');
    return {};
  }
  if (!['open', 'refresh'].includes(message.type) || !Number.isInteger(windowId)) return { error: 'unavailable' };
  if (message.host !== current.host) return { error: 'switched' };
  const origin = 'https://' + current.host;
  if (!await api.permissions.contains({ origins: [origin + '/*'] })) return { error: 'permission' };
  const url = origin + '/console/checkin';
  // URL-filtered queries can miss a newly created, still-navigating tab.
  // Host permissions expose only addresses that this extension can access.
  const tabs = (await api.tabs.query({ windowId })).filter(tab => {
    const address = tab.pendingUrl || tab.url;
    if (!address?.startsWith(origin + '/')) return false;
    const target = new URL(address);
    return target.pathname.replace(/\/$/, '') === '/console/checkin' && !target.hash.includes('glados-auto');
  });
  if (tabs.length > 1) return { error: 'multiple' };
  if (message.type === 'open') {
    if (tabs.length) await api.tabs.update(tabs[0].id, { active: true });
    else await api.tabs.create({ windowId, url, active: true });
    await log('opened', current.host);
    return {};
  }
  if (!tabs.length) return { error: 'noTab' };
  let result;
  try {
    const [frame] = await api.scripting.executeScript({
      target: { tabId: tabs[0].id, frameIds: [0] }, func: readOfficialLedger, args: [origin],
    });
    const read = frame?.result;
    result = read?.ledger ? { snapshot: Ledger.parse(read.ledger), account: read.account } : read;
  }
  catch { result = { error: 'reload' }; }
  if (!result?.snapshot && !result?.error) result = { error: 'unavailable' };
  await log(result.error ? 'readFailed' : 'read', current.host);
  return result;
}
api.runtime.onMessage.addListener((message, sender, reply) => {
  if (sender.id !== api.runtime.id || sender.url !== dashboard) return false;
  serial(() => command(message, sender.tab?.windowId))
    .then(reply, () => reply({ error: 'unavailable' }));
  return true;
});
