// GLaDOS Check-in extension — background service worker (MV3)
//
// 架构：
//  - 零配置：使用浏览器自身登录态（host_permissions 下 fetch 带 credentials）
//  - 三时段幂等调度（北京时间 09:30 / 12:30 / 20:30），浏览器启动时当日补跑
//  - 已在别处签到（本地脚本/手动）会先被流水识别，扩展不再开页
//  - 徽章 = 连续自动入账天数（与仓库 README 战报同口径）
//  - 签到由官方页面自身完成验证，扩展只负责开页、点击与读取结果
//  - 关窗口仍可签：依赖浏览器「关闭后继续运行后台应用」；彻底退出/睡眠/关机不会跑

const ORIGIN = 'https://glados.cloud';
const FALLBACK_ORIGINS = ['https://glados.rocks'];
const SLOTS = ['09:30', '12:30', '20:30'];
const STATE_KEY = 'gladosState';
// 读取 _locales 文案；substitutions 对应 messages.json 中的 $1/$2 占位符
const t = (key, substitutions) => chrome.i18n.getMessage(key, substitutions);

function bjNow() {
  // 北京时间（UTC+8）的 Date 值
  return new Date(Date.now() + (8 * 60 + new Date().getTimezoneOffset()) * 60000);
}
function bjToday() { return bjNow().toISOString().slice(0, 10); }
function bjHHMM() { return bjNow().toTimeString().slice(0, 5); }

async function getState() {
  const { [STATE_KEY]: s } = await chrome.storage.local.get(STATE_KEY);
  return s || { lastDoneDate: '', streak: { count: 0, lastDate: '' }, lastResult: null, lastRunAt: '' };
}
async function setState(patch) {
  const s = await getState();
  const next = { ...s, ...patch };
  await chrome.storage.local.set({ [STATE_KEY]: next });
  return next;
}

// ---------- 流水读取（与推送卡片同口径：排除 exchange/refund 的正变动） ----------
async function readLedger(origin = ORIGIN) {
  try {
    const r = await fetch(origin + '/api/user/points', { credentials: 'include' });
    if (!r.ok) return null;
    const data = await r.json();
    const history = Array.isArray(data.history) ? data.history : (data.list || []);
    const today = bjToday();
    let todayGain = 0, todayCount = 0;
    const creditedDates = new Set();
    for (const e of history.slice(0, 10)) {
      const d = new Date(Number(e.time));
      const bj = new Date(d.getTime() + (8 * 60 + d.getTimezoneOffset()) * 60000);
      const day = bj.toISOString().slice(0, 10);
      const num = Number(e.change);
      const biz = String(e.business || '').toLowerCase();
      if (!Number.isFinite(num) || num <= 0) continue;
      if (biz.includes('exchange') || biz.includes('refund')) continue;
      creditedDates.add(day);
      if (day === today) { todayGain += num; todayCount += 1; }
    }
    return { ok: true, points: data.points, todayGain, todayCount, creditedDates: [...creditedDates] };
  } catch (err) {
    return null;
  }
}

// ---------- 连续天数（与 update_streak.py 同一状态机） ----------
async function advanceStreak(ledger) {
  const s = await getState();
  const today = bjToday();
  const yesterday = new Date(Date.now() - 86400000 + (8 * 60 + new Date().getTimezoneOffset()) * 60000).toISOString().slice(0, 10);
  const credited = new Set(ledger.creditedDates);
  if (!credited.has(today)) return s.streak;
  if (s.streak.lastDate === today) return s.streak;
  let streak;
  if (s.streak.lastDate === yesterday && s.streak.count > 0) {
    streak = { count: s.streak.count + 1, lastDate: today };
  } else {
    let count = 0;
    let cursor = new Date(bjNow());
    for (;;) {
      const day = cursor.toISOString().slice(0, 10);
      if (!credited.has(day)) break;
      count += 1;
      cursor = new Date(cursor.getTime() - 86400000);
    }
    streak = { count: Math.max(count, 1), lastDate: today };
  }
  await setState({ streak });
  return streak;
}

async function updateBadge(streak) {
  const s = streak || (await getState()).streak;
  const text = s.count > 0 ? String(s.count) : '';
  await chrome.action.setBadgeText({ text });
  await chrome.action.setBadgeBackgroundColor({ color: '#e377c2' });
  await chrome.action.setTitle({ title: t('badgeTitle', [String(s.count)]) });
}

function notify(id, title, message) {
  chrome.notifications.create(id, {
    type: 'basic',
    iconUrl: chrome.runtime.getURL('icons/icon128.png'),
    title, message,
  });
}

// ---------- 调度 ----------
async function runSlot(reason) {
  const s = await getState();
  const today = bjToday();
  const ledger = await readLedger();
  if (!ledger) {
    notify('net', t('notifyNetTitle'), t('notifyNetMessage'));
    return;
  }
  await advanceStreak(ledger);
  await updateBadge();
  if (s.lastDoneDate === today || ledger.todayCount > 0) {
    await setState({ lastDoneDate: today });
    return; // 今日已在别处入账（本地脚本/手动），扩展不开页
  }
  chrome.tabs.create({ url: ORIGIN + '/console/checkin#glados-auto', active: false });
}

chrome.runtime.onInstalled.addListener((details) => {
  for (const slot of SLOTS) {
    const [h, m] = slot.split(':').map(Number);
    const when = new Date(AlarmsUtc(h, m)).getTime();
    chrome.alarms.create('slot-' + slot, { when, periodInMinutes: 24 * 60 });
  }
  runSlot('installed');
  // 扩展无法代开系统开关；仅首次安装提醒开启「关窗口后继续运行后台应用」
  if (details.reason === 'install') {
    notify('bg-hint', t('notifyBgTitle'), t('notifyBgMessage'));
  }
});
function AlarmsUtc(h, m) {
  // 把北京时间 h:m 换算成 UTC 的下一个触发时刻
  const now = new Date();
  const utc = new Date(now.getTime() + (8 * 60 + now.getTimezoneOffset()) * 60000);
  utc.setHours(h, m, 0, 0);
  if (utc <= bjNow()) utc.setDate(utc.getDate() + 1);
  return new Date(utc.getTime() - (8 * 60 + now.getTimezoneOffset()) * 60000).getTime();
}
chrome.runtime.onStartup.addListener(() => runSlot('startup'));
chrome.alarms.onAlarm.addListener(a => { if (a.name.startsWith('slot-')) runSlot('alarm'); });

// ---------- 来自 content script 的结果 ----------
chrome.runtime.onMessage.addListener((msg, sender, respond) => {
  (async () => {
    if (msg.type === 'checkin-result') {
      const r = msg.result || {};
      const ok = r.code === 0 || r.code === 1 || /repeats|observation logged/i.test(String(r.message || ''));
      if (ok) {
        await setState({ lastDoneDate: bjToday(), lastResult: r, lastRunAt: new Date().toISOString() });
        const ledger = await readLedger();
        if (ledger) { await advanceStreak(ledger); }
        await updateBadge();
        notify('done', t('notifyDoneTitle'), String(r.message || t('notifyDoneFallback')));
      } else {
        notify('fail', t('notifyFailTitle'), String(r.message || t('notifyFailFallback')));
      }
      if (sender.tab) chrome.tabs.remove(sender.tab.id).catch(() => {});
      respond({ ok: true });
    } else if (msg.type === 'need-login') {
      notify('login', t('notifyLoginTitle'), t('notifyLoginMessage'));
      if (sender.tab) chrome.tabs.remove(sender.tab.id).catch(() => {});
      respond({ ok: true });
    } else if (msg.type === 'manual-run') {
      await runSlot('manual');
      respond({ ok: true });
    } else if (msg.type === 'get-state') {
      respond(await getState());
    }
  })();
  return true; // async respond
});

updateBadge();
