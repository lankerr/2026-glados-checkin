#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Report the latest consecutive check-in dates visible in the points ledger."""

import os
import sys
from datetime import date, timedelta
from pathlib import Path

import checkin

CHECKIN_LABELS = {'system:checkin', 'checkin', 'check-in', 'check_in'}


def visible_streak(entries, today):
    credited_dates = set()
    for entry in entries:
        if entry.get('business') not in CHECKIN_LABELS:
            continue
        amount = checkin.parse_finite_number(entry.get('change'))
        if amount is None or amount <= 0:
            continue
        try:
            entry_date = date.fromisoformat(entry.get('date') or '')
        except ValueError:
            continue
        if entry_date <= today:
            credited_dates.add(entry_date)

    if not credited_dates:
        return 0, None
    last_date = max(credited_dates)
    count = 0
    cursor = last_date
    while cursor in credited_dates:
        count += 1
        cursor -= timedelta(days=1)
    return count, last_date


def describe_streak(entries, today):
    count, last_date = visible_streak(entries, today)
    if last_date is None:
        return '前 10 条可见流水中无明确签到入账，签到状态待确认。'
    report = f'最近可见签到为 {last_date}，截至该日可见流水连续 {count} 天。'
    if last_date < today:
        report += '今日签到入账仍待确认。'
    return report


def main():
    cookies = checkin.get_cookies()
    details = []
    failed = False
    if not cookies:
        details.append('❌ GLADOS_COOKIE 为空或格式无法解析，请检查 Actions Secret。')
        failed = True
    elif not checkin.log_user_agent_configuration():
        details.append('❌ GLADOS_USER_AGENT 配置格式无效，请查看运行日志中的配置提示。')
        failed = True
    else:
        today = checkin.beijing_now().date()
        for index, cookie in enumerate(cookies, start=1):
            client = checkin.GLaDOS(cookie)
            if client.get_points():
                line = describe_streak(client.recent_entries, today)
            else:
                line = f'❌ 积分流水读取失败：{client.points_error}。今日入账待核对。'
                failed = True
            details.append(f'账号 {index}：{line}' if len(cookies) > 1 else line)

    report = '\n\n'.join(details)
    print(report)
    summary = os.environ.get('GITHUB_STEP_SUMMARY')
    if summary:
        with Path(summary).open('a', encoding='utf-8') as output:
            output.write(
                f'## 签到流水只读核对\n\n{report}\n\n'
                '只计入返回的前 10 条流水中明确标为签到的正变动。'
                '日期按北京时间，同一天只统计一次，流水来源无法归属到某个脚本。\n'
            )
    return int(failed)


if __name__ == '__main__':
    sys.exit(main())
