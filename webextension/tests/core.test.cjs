const { test } = require('node:test');
const assert = require('node:assert/strict');
const { parse, day, nextReminder } = require('../core.js');
const now = Date.parse('2026-11-18T16:00:00Z');
const row = (business, change = 2, time = now) => ({ business, change, time });
function read(history) { return parse({ points: '10.50', history }, now); }
test('UTC+8 midnight is independent of host timezone', () => {
  assert.equal(day(now - 1), '2026-11-18');
  assert.equal(day(now), '2026-11-19');
  assert.equal(read([row('checkin', 4, now - 1)]).confirmed, false);
});
test('only a positive, explicitly labelled check-in dated today confirms a credit', () => {
  for (const entry of [row('refund'),row('compensation'),row('system:compensation'),row('promotion'),row('checkin refund'),row(''),row('checkin',0),row('checkin',-2), row('checkin', 2, now + 5000)]) {
    assert.equal(read([entry]).confirmed, false);
  }
  assert.equal(read([row('CHECK-IN', '0.5', now / 1000)]).confirmed, true);
  assert.equal(read([row('system:checkin', 11)]).confirmed, true);
});
test('retain evidence beyond the ten displayed entries; skip malformed amounts and times', () => {
  const entries = Array.from({ length: 12 }, () => row('promotion'));
  const result = read([null, row('checkin',''), row('checkin',3,'!'), ...entries, row('checkin')]);
  assert.equal(result.confirmed, true);
  assert.equal(result.rows.length, 10);
  assert.equal(result.points, 10.5);
});
test('unreadable server balances and application errors cannot look successful', () => {
  for (const value of [null,'',[],true,Infinity]) assert.equal(parse({ points:value },now), null);
  assert.equal(parse({ code:1, points:50 },now), null);
  assert.equal(parse({ points:0 },now).historyAvailable, false);
  assert.equal(parse({ points:0, list:[] },now).historyAvailable, true);
});
test('one-shot reminders target the next Beijing 09:30, including after sleep', () => {
  const slot = Date.parse('2026-11-18T01:30:00Z');
  assert.equal(nextReminder(slot - 1), slot);
  assert.equal(nextReminder(slot), slot + 86400000);
  assert.equal(nextReminder(slot + 6 * 3600000), slot + 86400000);
});
