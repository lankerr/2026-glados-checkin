#!/data/data/com.termux/files/usr/bin/bash
# Read the points ledger and show a local notification on Android.
set -eu
here="$(cd "$(dirname "$0")" && pwd)"
config="${GLADOS_TERMUX_ENV:-${GLADOS_TERMUX_CONFIG:-$HOME/.config/glados-termux}/env}"
if [ -n "${GLADOS_TERMUX_ENV:-}${GLADOS_TERMUX_CONFIG:-}" ] || [ -e "$config" ] || [ -L "$config" ]; then
    if [ ! -f "$config" ] || [ ! -r "$config" ]; then
        echo '无法读取指定的流水核对配置。' >&2
        exit 2
    fi
    set -a
    # shellcheck disable=SC1090
    . "$config"
    set +a
fi
exec python "$here/../update_streak.py" --termux-notify
