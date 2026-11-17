#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""每日自动战报：读取积分流水，更新 README 中"连续自动入账"标记块。

由 .github/workflows/streak.yml 每天上午（北京时间）调用：
  1. 用仓库 Secrets 里的 Cookie 只读查询 /api/user/points；
  2. 根据"奖励性正变动"日期与已持久化的状态，推进或重置连续天数；
  3. 重写 README 中 <!--STREAK:START--> ... <!--STREAK:END--> 之间的内容。

口径：与推送卡片一致——排除 exchange/refund 的正变动才计入；今日尚未入账时
保持原状态不动（不报中断），断档后从可见流水窗口重算。
"""

import os
import re
import sys
from datetime import date, timedelta

import checkin

MARK_START = '<!--STREAK:START-->'
MARK_END = '<!--STREAK:END-->'
README_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'README.md')


def next_state(prev_count, prev_date_str, credited_dates, today):
    """推进连续入账状态。credited_dates 为 ISO 日期字符串集合。

    返回 (count, last_date_str, updated_today)。今日未入账时原样返回。
    """
    today_s = today.isoformat()
    yesterday_s = (today - timedelta(days=1)).isoformat()
    if today_s not in credited_dates:
        return prev_count, prev_date_str, False
    if prev_date_str == today_s:
        return prev_count, prev_date_str, False
    if prev_date_str == yesterday_s and prev_count and prev_count > 0:
        return prev_count + 1, today_s, True
    # 断档或首次运行：从可见流水窗口向前数
    count = 0
    cursor = today
    while cursor.isoformat() in credited_dates:
        count += 1
        cursor -= timedelta(days=1)
    return max(count, 1), today_s, True


def parse_block(text):
    """读取现有标记块中的 (count, last_date_str)。"""
    m = re.search(re.escape(MARK_START) + r'(.*?)' + re.escape(MARK_END), text, re.S)
    if not m:
        return 0, None
    body = m.group(1)
    count_m = re.search(r'(\d+)\s*天', body)
    date_m = re.search(r'(\d{4}-\d{2}-\d{2})', body)
    return (int(count_m.group(1)) if count_m else 0), (date_m.group(1) if date_m else None)


def render_block(count, last_date_str, last_gain):
    gain = f'，{last_gain} 分' if last_gain else ''
    return (
        f'{MARK_START}\n'
        f'> 🔥 **连续自动入账 {count} 天**（最近 {last_date_str}{gain}）'
        '——每日云端只读核对自动更新，官网流水可查\n'
        f'{MARK_END}'
    )


def main():
    cookie = os.environ.get('GLADOS_COOKIE', '').strip()
    if not cookie:
        print('❌ 未配置 GLADOS_COOKIE')
        return 1
    client = checkin.GLaDOS(cookie)
    if not client.get_points():
        print('❌ 积分流水读取失败，本次不更新战报')
        return 1

    credited = {
        e['date'] for e in client.recent_entries
        if e.get('date') and str(e.get('change', '')).startswith('+')
        and 'exchange' not in (e.get('business') or '')
        and 'refund' not in (e.get('business') or '')
    }
    today = checkin.beijing_now().date()
    text = open(README_PATH, encoding='utf-8').read()
    prev_count, prev_date = parse_block(text)
    count, last_date, changed = next_state(prev_count, prev_date, credited, today)

    if not changed:
        print(f'ℹ️ 今日尚未入账或已更新过，保持：{prev_count} 天 @ {prev_date}')
        return 0
    if MARK_START not in text:
        print('❌ README 中未找到 STREAK 标记块')
        return 1
    block = render_block(count, last_date, client.today_rewards_total)
    new_text = re.sub(re.escape(MARK_START) + r'.*?' + re.escape(MARK_END), block, text, flags=re.S)
    open(README_PATH, 'w', encoding='utf-8', newline='').write(new_text)
    print(f'✅ 战报已更新：连续自动入账 {count} 天 @ {last_date}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
