#!/data/data/com.termux/files/usr/bin/bash
# GLaDOS Termux 一键引导：装依赖 → 生成配置模板 → 注册每日定时任务
# 用法：bash termux/bootstrap.sh
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
DEFAULT_ENV="$HOME/.config/glados-termux/env"
ENV_FILE="${GLADOS_TERMUX_ENV:-${GLADOS_TERMUX_CONFIG:-$HOME/.config/glados-termux}/env}"
CONFIG_DIR="$(dirname "$ENV_FILE")"
JOB_ID="${GLADOS_TERMUX_JOB_ID:-101}"
# 默认每 24 小时跑一次（从注册时刻起算）。要贴近“北京时间上午”，
# 可在上午手动重新执行本脚本的 register 步骤刷新起点。
PERIOD_MS="${GLADOS_TERMUX_PERIOD_MS:-86400000}"

echo "==> 安装依赖（python、termux-api 命令行）"
pkg install -y python termux-api

echo "==> 安装引擎依赖（仅 requests；Termux 不支持 playwright，已自动禁用浏览器兜底）"
pip install --upgrade requests

echo "==> 生成配置模板（已存在则不覆盖）：$ENV_FILE"
umask 077
mkdir -p "$CONFIG_DIR"
if [ ! -f "$ENV_FILE" ]; then
    # Refuse to truncate a file created by another installer.
    set -C
    cat > "$ENV_FILE" <<'EOF'
# GLaDOS Termux 配置。此文件含凭据，权限已设为 600，不要提交到任何仓库。
# GLADOS_COOKIE 必填；其余按需参考仓库 docs/usage.md。
export GLADOS_COOKIE='粘贴你的 Cookie（与 Python 本地版同一格式）'
# export GLADOS_USER_AGENT='Mozilla/5.0 (Linux; Android 15) ...'
# 远程推送（可选，与仓库其他部署共用同一套环境变量）
# export PUSHPLUS_TOKEN=''
# export SERVERCHAN_SENDKEY=''
# export TELEGRAM_BOT_TOKEN=''
# export TELEGRAM_CHAT_ID=''
# export EXCHANGE_PLAN='plan500'
EOF
    set +C
    chmod 600 "$ENV_FILE"
    echo "    请编辑 $ENV_FILE 填入 GLADOS_COOKIE 后再试跑。"
else
    echo "    配置已存在，保持不变。"
fi

# Android starts the scheduled script without this Termux shell's overrides.
if [ "$ENV_FILE" != "$DEFAULT_ENV" ]; then
    echo "自定义配置已准备好。请在同一配置环境中手动运行；未注册定时任务。"
    exit 0
fi

echo "==> 获取唤醒锁（允许 Termux 在后台按计划唤醒）"
termux-wake-lock

echo "==> 注册每日定时任务（JobScheduler，重启后仍生效）"
termux-job-scheduler \
    --job-id "$JOB_ID" \
    --script "$HERE/run-checkin.sh" \
    --period-ms "$PERIOD_MS" \
    --persisted true \
    --network any \
    --battery-not-low true \
    --charging false

echo "==> 完成。接下来："
echo "    1. 编辑 $ENV_FILE 填入 GLADOS_COOKIE"
echo "    2. 手动试跑一次：bash $HERE/run-checkin.sh"
echo "    3. 查看已注册任务：termux-job-scheduler --list-job"
echo "       取消任务：termux-job-scheduler --cancel-job $JOB_ID"
echo "提醒：本机通知需要同时安装 Termux:API 应用（F-Droid 版），命令行包已装。"
