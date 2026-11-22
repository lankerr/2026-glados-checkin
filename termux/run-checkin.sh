#!/data/data/com.termux/files/usr/bin/bash
# GLaDOS Termux 签到入口：加载配置 → 跑引擎 → 发本地通知
# 手动试跑：bash termux/run-checkin.sh
set -uo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
ENGINE="$HERE/../checkin.py"
ENV_FILE="${GLADOS_TERMUX_ENV:-$HOME/.config/glados-termux/env}"

if [ ! -f "$ENV_FILE" ]; then
    echo "未找到配置 $ENV_FILE，请先运行 termux/bootstrap.sh" >&2
    exit 2
fi
if [ ! -f "$ENGINE" ]; then
    echo "未找到签到引擎 $ENGINE（请在仓库根目录结构不变的情况下运行）" >&2
    exit 2
fi
# shellcheck disable=SC1090
. "$ENV_FILE"

# Termux 装不了 playwright：显式关闭浏览器兜底，只走 requests 通道
export GLADOS_BROWSER_CHECKIN=0

OUTPUT="$(python "$ENGINE" 2>&1)"
CODE=$?
printf '%s\n' "$OUTPUT"
python "$HERE/notify.py" --code "$CODE" "$OUTPUT" || true
exit "$CODE"
