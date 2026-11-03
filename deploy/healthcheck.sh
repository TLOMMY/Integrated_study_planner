#!/usr/bin/env bash
# 后端健康检查：由 systemd timer（xueyeguanjia-health.timer）每分钟运行一次，install.sh 安装到
# /usr/local/bin/xueyeguanjia-healthcheck。
#
#   - 连续 FAILS_BEFORE_ALERT 次（默认 2，约 2 分钟）请求 /health 失败：通过已有的反馈通知渠道
#     （管理后台「设置」或 backend.env 里的群机器人 / 邮箱）告警；仍未恢复时每 REALERT_MINUTES 分钟提醒一次；
#   - 连续 RESTART_AFTER 次（默认 3）失败：自动 systemctl restart 一次；
#   - 恢复后再发一条"已恢复"。
# 状态记在 STATE_DIR；所有路径都可用环境变量覆盖（本地演练用）。脚本里没有任何密钥。
set -uo pipefail

URL=${HEALTH_URL:-http://127.0.0.1:8000/health}
SERVICE=${SERVICE-xueyeguanjia}
STATE_DIR=${STATE_DIR:-/var/lib/xueyeguanjia/health}
APP_DIR=${APP_DIR:-/opt/xueyeguanjia/app/Backend+AI-interface}
PYTHON=${PYTHON:-/opt/xueyeguanjia/venv/bin/python}
ENV_FILE=${ENV_FILE:-/etc/xueyeguanjia/backend.env}
RUN_AS=${RUN_AS:-xueyeguanjia}
FAILS_BEFORE_ALERT=${FAILS_BEFORE_ALERT:-2}
RESTART_AFTER=${RESTART_AFTER:-3}
REALERT_MINUTES=${REALERT_MINUTES:-60}

mkdir -p "$STATE_DIR"
FAILS_FILE="$STATE_DIR/fails"
ALERT_FILE="$STATE_DIR/last_alert"
DOWN_FILE="$STATE_DIR/down_since"

log() { echo "[healthcheck] $*"; command -v logger >/dev/null && logger -t xueyeguanjia-health "$*"; return 0; }

# 用后端自己的通知模块发送（读取后台设置的机器人 / 邮箱；数据库读不了时退回 backend.env）
notify() {
  local title=$1 text=$2
  local cmd=("$PYTHON" -c 'import sys
from dotenv import load_dotenv
if sys.argv[1]:
    load_dotenv(sys.argv[1], override=False)
from app.services.alerts import main
sys.exit(main(sys.argv[2:]))' "$( [ -r "$ENV_FILE" ] && echo "$ENV_FILE" )" notify "$title" "$text")
  if [ "$(id -u)" -eq 0 ] && id "$RUN_AS" >/dev/null 2>&1 && command -v runuser >/dev/null; then
    # 以服务用户身份运行，避免 root 在数据库目录留下 root 所有的临时文件
    (cd "$APP_DIR" && runuser -u "$RUN_AS" -- "${cmd[@]}") || log "告警发送失败：$title"
  else
    (cd "$APP_DIR" && "${cmd[@]}") || log "告警发送失败：$title"
  fi
}

now=$(date +%s)
fails=$(cat "$FAILS_FILE" 2>/dev/null || echo 0)
host=$(hostname 2>/dev/null || echo server)

if curl -fsS -m 10 -o /dev/null "$URL"; then
  if [ -f "$DOWN_FILE" ]; then
    since=$(cat "$DOWN_FILE")
    minutes=$(( (now - since) / 60 ))
    log "后端已恢复（中断约 ${minutes} 分钟）"
    [ -f "$ALERT_FILE" ] && notify "【学业管家】后端已恢复" "服务器 ${host} 的后端已恢复正常，中断约 ${minutes} 分钟。
时间：$(date '+%Y-%m-%d %H:%M:%S')"
    rm -f "$DOWN_FILE" "$ALERT_FILE"
  fi
  echo 0 > "$FAILS_FILE"
  exit 0
fi

fails=$((fails + 1))
echo "$fails" > "$FAILS_FILE"
[ -f "$DOWN_FILE" ] || echo "$now" > "$DOWN_FILE"
log "健康检查失败（连续第 ${fails} 次）：$URL"

if [ "$fails" -eq "$RESTART_AFTER" ] && command -v systemctl >/dev/null && [ -n "$SERVICE" ]; then
  log "尝试自动重启 $SERVICE"
  systemctl restart "$SERVICE" || log "重启失败"
fi

if [ "$fails" -ge "$FAILS_BEFORE_ALERT" ]; then
  last=$(cat "$ALERT_FILE" 2>/dev/null || echo 0)
  if [ $((now - last)) -ge $((REALERT_MINUTES * 60)) ]; then
    echo "$now" > "$ALERT_FILE"
    restarted=""
    [ "$fails" -ge "$RESTART_AFTER" ] && restarted="已自动重启过一次服务，仍未恢复。"
    notify "【学业管家】后端不可用" "服务器 ${host} 的健康检查连续 ${fails} 次失败（${URL}）。${restarted}
请登录服务器查看：journalctl -u ${SERVICE} -n 100
时间：$(date '+%Y-%m-%d %H:%M:%S')（未恢复前每 ${REALERT_MINUTES} 分钟提醒一次）"
  fi
fi
exit 1
