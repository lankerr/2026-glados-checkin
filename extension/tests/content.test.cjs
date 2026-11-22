// 合成用例：验证 content.js 的签到接口与按钮识别（node --test extension/tests/）
const { test } = require('node:test');
const assert = require('node:assert/strict');
const { isCheckinPost, isCheckinButtonText } = require('../content.js');

const origin = 'https://glados.cloud';

test('same-origin POST to the exact check-in path counts', () => {
  assert.equal(isCheckinPost(origin + '/api/user/checkin', origin), true);
  // 相对地址按当前源解析
  assert.equal(isCheckinPost('/api/user/checkin', origin), true);
  assert.equal(isCheckinPost('/api/user/checkin?ref=console', origin), true);
});

test('challenge preparation responses are excluded', () => {
  assert.equal(isCheckinPost(origin + '/api/user/checkin/challenge', origin), false);
  assert.equal(isCheckinPost(origin + '/api/user/checkin/challenge?x=1', origin), false);
});

test('other origins and other prefixes with the same path are excluded', () => {
  assert.equal(isCheckinPost('https://evil.example/api/user/checkin', origin), false);
  assert.equal(isCheckinPost('https://glados.cloud.evil.example/api/user/checkin', origin), false);
  assert.equal(isCheckinPost(origin + '/x/api/user/checkin', origin), false);
});

test('malformed or empty inputs never look like a check-in response', () => {
  for (const url of ['', null, undefined, 'not a url', origin + '/', origin + '/api/user']) {
    assert.equal(isCheckinPost(url, origin), false);
  }
});

test('button text matches English and Chinese check-in labels', () => {
  assert.equal(isCheckinButtonText('Check in', ''), true);
  assert.equal(isCheckinButtonText(' CHECK - IN ', ''), true);
  assert.equal(isCheckinButtonText('', 'Check in'), true);
  assert.equal(isCheckinButtonText('签到', ''), true);
  assert.equal(isCheckinButtonText('', '每日签到'), true);
});

test('unrelated buttons are not matched', () => {
  for (const [text, aria] of [['Sign out', ''], ['Checked history', ''], ['', ''], ['退出登录', '']]) {
    assert.equal(isCheckinButtonText(text, aria), false);
  }
});
