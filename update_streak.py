#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Report the latest consecutive check-in dates visible in the points ledger."""

import argparse
import os
import shutil
import subprocess
import sys
from datetime import date, timedelta
from pathlib import Path

import checkin


def visible_streak(entries, today):
    credited_dates = set()
    for entry in entries:
        if not checkin.is_credited_checkin(entry):
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
    return format_streak(*visible_streak(entries, today), today)


def format_streak(count, last_date, today):
    if last_date is None:
        return '前 10 条可见流水中无明确签到入账，签到状态待确认。'
    report = f'最近可见签到为 {last_date}，截至该日可见流水连续 {count} 天。'
    if last_date < today:
        report += '今日签到入账仍待确认。'
    return report


def notify_termux(confirmed, total, failed):
    title = 'GLaDOS 流水读取异常' if failed else 'GLaDOS 流水核对完成'
    body = (f'今日已确认签到入账 {confirmed}/{total} 个账号。' if total else '请检查本机配置。')
    if total and confirmed < total:
        body += '其余账号请打开官网核对。'
    binary = shutil.which('termux-notification')
    if binary:
        try:
            result = subprocess.run([binary, '--title', title, '--content', body],
                                    timeout=15, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if result.returncode == 0:
                return
        except (OSError, subprocess.TimeoutExpired):
            pass
    print(f'本地通知命令未成功。{title}。{body}')


def main(*, termux_notify=False):
    cookies = checkin.get_cookies()
    details = []
    failed = False
    confirmed = 0
    if not cookies:
        details.append('❌ GLADOS_COOKIE 为空或格式无法解析，请检查当前环境的配置。')
        failed = True
    elif not checkin.log_user_agent_configuration():
        details.append('❌ GLADOS_USER_AGENT 配置格式无效，请查看运行日志中的配置提示。')
        failed = True
    else:
        today = checkin.beijing_now().date()
        for index, cookie in enumerate(cookies, start=1):
            client = checkin.GLaDOS(cookie)
            if client.get_points():
                count, last_date = visible_streak(client.recent_entries, today)
                line = format_streak(count, last_date, today)
                confirmed += int(last_date == today)
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
    if termux_notify:
        notify_termux(confirmed, len(cookies), failed)
    return int(failed)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--termux-notify', action='store_true', help='在安卓 Termux 通知栏显示入账账号数')
    sys.exit(main(termux_notify=parser.parse_args().termux_notify))
