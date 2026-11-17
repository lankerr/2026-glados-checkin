#!/usr/bin/env bash
# GLaDOS 自动签到 一键安装（macOS / Linux）
# 流程：Python 检查 -> 依赖 -> Cookie/UA 模板 -> cron(09:30/12:30/20:30) -> 自检
# 重复运行安全：配置与 cron 条目会更新而非重复添加。

set -euo pipefail
cd "$(dirname "$0")"
echo "===================================="
echo " GLaDOS 自动签到 一键安装 (macOS/Linux)"
echo "===================================="

# ---- 1. Python ----
PY=""
for c in python3 python; do
  if command -v "$c" >/dev/null 2>&1; then PY="$c"; break; fi
done
if [ -z "$PY" ]; then
  echo "[X] 未检测到 Python，请先安装 Python 3.10+（macOS: brew install python3 / Ubuntu: sudo apt install python3 python3-pip）"
  exit 1
fi
"$PY" --version

# ---- 2. 依赖 ----
echo "[1/5] 安装依赖（requests + playwright）..."
"$PY" -m pip install --quiet --disable-pip-version-check -r requirements.txt

# 浏览器：有 Chrome/Chromium/Edge 之一即可，否则下载 playwright chromium
if ! command -v google-chrome >/dev/null 2>&1 \
   && ! command -v chromium >/dev/null 2>&1 \
   && ! command -v chromium-browser >/dev/null 2>&1 \
   && ! command -v microsoft-edge >/dev/null 2>&1 \
   && [ ! -x "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" ]; then
  echo "     未检测到 Chrome/Chromium/Edge，下载 Playwright chromium（约 120MB）..."
  "$PY" -m playwright install chromium
fi

# ---- 3. Cookie / UA 模板 ----
echo "[2/5] 检查 Cookie 配置..."
if [ ! -s cookie.txt ]; then
  cat > cookie.txt <<'TMPL'
把下面一行替换成你的 GLaDOS Cookie（登录 glados.cloud -> F12 -> Network -> 刷新 -> 点第一个请求 -> Request Headers 里 cookie: 后面的整串）
必须同时包含 gld:sess 与 gld:sess.sig
gld:sess=粘贴到这里; gld:sess.sig=粘贴到这里
TMPL
  echo "     已生成 cookie.txt 模板——请用编辑器打开并粘贴你的 Cookie！"
fi
if [ ! -s user-agent.txt ]; then
  echo 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36' > user-agent.txt
  echo "     已生成 user-agent.txt 默认值（建议换成你登录所用浏览器的 UA）"
fi

# ---- 4. 启动脚本 ----
RUNSH="run-checkin.sh"
if [ ! -f "$RUNSH" ]; then
  cat > "$RUNSH" <<RUNEOF
#!/usr/bin/env bash
set -euo pipefail
cd "\$(dirname "\$0")"
export PYTHONIOENCODING=utf-8
if [ ! -s cookie.txt ]; then echo '[错误] cookie.txt 为空'; exit 1; fi
export GLADOS_COOKIE="\$(cat cookie.txt)"
export GLADOS_USER_AGENT="\$(cat user-agent.txt 2>/dev/null || true)"
export EXCHANGE_PLAN=plan500
export PUSH_LEVEL=fail_only
mkdir -p logs
LOG="logs/checkin_\$(date +%F).log"
"$PY" checkin.py 2>&1 | tee -a "\$LOG"
exit "\${PIPESTATUS[0]}"
RUNEOF
  chmod +x "$RUNSH"
fi

# ---- 5. cron（幂等：先删旧条目再加新）----
echo "[3/5] 注册 cron（每天 09:30 / 12:30 / 20:30）..."
if [ "${GLADOS_INSTALL_NO_TASK:-}" = "1" ]; then
  echo "     (测试模式：跳过 cron 注册)"
else
  ABS_RUN="$(cd "$(dirname "$RUNSH")" && pwd)/$RUNSH"
  ( crontab -l 2>/dev/null | grep -v "GLADOS-CHECKIN $ABS_RUN" || true ) | { cat; \
    echo "30 9 * * * GLADOS-CHECKIN $ABS_RUN #GLADOS-CHECKIN"; \
    echo "30 12 * * * GLADOS-CHECKIN $ABS_RUN #GLADOS-CHECKIN"; \
    echo "30 20 * * * GLADOS-CHECKIN $ABS_RUN #GLADOS-CHECKIN"; } | crontab -
  echo "     已写入 crontab（crontab -l 可查看）"
fi

# ---- 6. 自检 ----
echo "[4/5] 运行离线自检（单元测试）..."
set +e
"$PY" -m unittest discover -s tests 2>&1 | tail -n 3
set -e

echo "[5/5] 完成！"
echo ""
echo "下一步（唯一要你做的事）："
echo "  1. 编辑 cookie.txt 粘贴你的 GLaDOS Cookie（含 gld:sess 与 gld:sess.sig）"
echo "  2. 运行 ./run-checkin.sh 立即试跑一次（会短暂弹出浏览器窗口，属正常）"
echo "  3. 之后每天 09:30 / 12:30 / 20:30 自动签到；结果看 logs/ 目录"
echo "  （可选）要收推送：编辑 run-checkin.sh 设置 PUSHPLUS_TOKEN / SERVERCHAN_SENDKEY"
