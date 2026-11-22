#!/usr/bin/env python
"""Termux 本地通知 glue：把 checkin.py 的输出摘成本地通知标题与正文。

纯函数 summarize() 不依赖设备与网络，可用离线单测覆盖；
main() 仅在真机上执行，termux-notification 不存在时静默降级为打印摘要。
"""
import argparse
import shutil
import subprocess
import sys

# 通知正文最多保留的行数与单行长度（termux-notification 抽屉里过长的正文会被截断）
MAX_BODY_LINES = 12
MAX_LINE_CHARS = 120
TITLE_SUCCESS = "GLaDOS 签到完成"
TITLE_FAILURE = "GLaDOS 签到失败"
TITLE_UNKNOWN = "GLaDOS 签到结束（结果待核对）"


def _clip(line):
    line = line.rstrip()
    return line if len(line) <= MAX_LINE_CHARS else line[: MAX_LINE_CHARS - 1] + "…"


def summarize(output_text, exit_code):
    """从引擎输出提炼 (title, body)。

    规则：出现 ❌ 按失败处理；只有 ✅/⏭️ 按完成处理；引擎以非零退出码
    结束且没有明确标记时按待核对处理（非零退出也可能只是推送渠道问题）。
    """
    lines = [_clip(line) for line in (output_text or "").splitlines() if line.strip()]
    body_lines = lines[-MAX_BODY_LINES:]
    has_fail = any("❌" in line for line in lines)
    has_done = any("✅" in line or "⏭️" in line for line in lines)
    if has_fail:
        title = TITLE_FAILURE
    elif has_done:
        title = TITLE_SUCCESS
    else:
        title = TITLE_UNKNOWN if exit_code == 0 else TITLE_FAILURE
    return {"title": title, "body": "\n".join(body_lines)}


def send_local_notification(summary):
    """在 Termux 里发本地通知；不在 Termux（或未装 termux-api）时返回 False。"""
    binary = shutil.which("termux-notification")
    if not binary:
        return False
    subprocess.run(
        [binary, "--title", summary["title"], "--content", summary["body"]],
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return True


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
        print("（未检测到 termux-notification，仅打印摘要）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
