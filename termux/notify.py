#!/usr/bin/env python
"""Termux 本地通知 glue：把 checkin.py 的输出摘成本地通知标题与正文。

纯函数 summarize() 不依赖设备与网络，可用离线单测覆盖；
main() 仅在真机上执行，termux-notification 不存在时静默降级为打印摘要。
"""
import argparse
import re
import shutil
import subprocess
import sys

ACCOUNT_RESULT = re.compile(
    r"^\[\d{4}-\d\d-\d\d \d\d:\d\d:\d\d 北京时间\] (✅|❌) 账号 [1-9]\d* "
    r"\| 积分: [^|]* \| 入账核验: .*? \| 天数: [^|]* \| 结果: "
)
TITLE_SUCCESS = "GLaDOS 签到接口返回成功"
TITLE_FAILURE = "GLaDOS 有账号签到失败"
TITLE_ERROR = "GLaDOS 运行异常（结果待核对）"
TITLE_UNKNOWN = "GLaDOS 签到结束（结果待核对）"


def summarize(output_text, exit_code):
    """只汇总引擎的账号结果行；锁屏通知仅显示计数。"""
    success = failure = 0
    for line in (output_text or "").splitlines():
        match = ACCOUNT_RESULT.match(line)
        if match:
            if match[1] == "✅":
                success += 1
            else:
                failure += 1
    if failure:
        title = TITLE_FAILURE
    elif exit_code != 0:
        title = TITLE_ERROR
    elif success:
        title = TITLE_SUCCESS
    else:
        title = TITLE_UNKNOWN
    body = (f"账号结果：成功 {success}，失败 {failure}。积分入账请核对官网流水。"
            if success or failure else "未读到账号签到结果，请查看本机日志。")
    return {"title": title, "body": body}


def send_local_notification(summary):
    """在 Termux 里发本地通知；不在 Termux（或未装 termux-api）时返回 False。"""
    binary = shutil.which("termux-notification")
    if not binary:
        return False
    try:
        proc = subprocess.run(
            [binary, "--title", summary["title"], "--content", summary["body"]],
            timeout=15, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return proc.returncode == 0


def main(argv=None):
    parser = argparse.ArgumentParser(description="Summarize checkin output into a local Termux notification")
    parser.add_argument("--code", type=int, default=0, help="checkin.py 的退出码")
    parser.add_argument("text", nargs="?", default="", help="引擎输出；缺省时读 stdin")
    args = parser.parse_args(argv)
    text = args.text if args.text else sys.stdin.read()
    summary = summarize(text, args.code)
    delivered = send_local_notification(summary)
    print(summary["title"])
    print(summary["body"])
    if not delivered:
        print("（本地通知命令未成功，仅打印摘要）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
