#!/usr/bin/env bash
# 学业管家一键部署（Ubuntu 22.04 / 24.04，root 运行）。可重复执行：已存在的配置会保留，代码会更新。
#
# 两种模式：
#   sudo bash deploy/install.sh --ip [公网IP]        备案前：公网 IP + 纯 HTTP，不申请证书（IP 不填则自动检测）
#   sudo bash deploy/install.sh you@example.com     备案后：域名 + HTTPS（邮箱用于证书到期提醒）
#
# 可选环境变量（只在需要时设置）：
#   DOMAIN=xueyeguanjia.com      主域名（www 与 app 子域名都要有 A 记录指向本机）
#   ICP_NUMBER="京ICP备xxxxxxxx号-1"   POLICE_BEIAN="京公网安备xxxxxxxxxxxxxx号"   写入后端配置并显示在介绍页、登录页
#   CONTACT_EMAIL=you@example.com     隐私政策里的联系邮箱
#   DOWNLOAD_URL=https://github.com/<you>/<repo>/releases/latest    介绍页的下载按钮
#   REPO=https://github.com/<you>/<repo>.git   代码仓库
#
# 从 IP 模式切换到域名 + HTTPS：备案通过、域名解析到本机后，直接再运行一次（不带 --ip）：
#   sudo DOMAIN=你的域名 ICP_NUMBER="…" bash deploy/install.sh you@example.com
# 脚本会申请证书、换成 HTTPS 的 Nginx 配置，并把 APP_PUBLIC_URL / CORS_ORIGINS 更新为新域名（数据与密钥不变）。
# 之后安卓 / Windows 客户端在登录页「服务器」里改成 https://app.你的域名。
#
# 本脚本不包含任何密钥：JWT 密钥在服务器上随机生成；DeepSeek Key、邮件密码等请在
# /etc/xueyeguanjia/backend.env 中自行填写后执行 systemctl restart xueyeguanjia。
set -euo pipefail

MODE=domain
EMAIL=""
PUBLIC_IP=""
case "${1:-}" in
  --ip)
    MODE=ip
    PUBLIC_IP=${2:-}
    ;;
  -h|--help|"")
    sed -n '2,21p' "$0" | sed 's/^# \{0,1\}//'
    [ -n "${1:-}" ] && exit 0
    echo
    echo "错误：请指定 --ip 或证书提醒邮箱"
    exit 1
    ;;
  *)
    EMAIL=$1
    ;;
esac

DOMAIN=${DOMAIN:-xueyeguanjia.com}
APP_DOMAIN=app.$DOMAIN
REPO=${REPO:-https://github.com/TLOMMY/Integrated_study_planner.git}
DOWNLOAD_URL=${DOWNLOAD_URL:-$(echo "${REPO%.git}" | sed 's|$|/releases/latest|')}
ROOT=/opt/xueyeguanjia
APP=$ROOT/app
SITE=$ROOT/site
DATA=/var/lib/xueyeguanjia
ENV_FILE=/etc/xueyeguanjia/backend.env
CONF_DIR=/etc/nginx/sites-available
STEPS=8

[ "$(id -u)" -eq 0 ] || { echo "请用 sudo 运行"; exit 1; }

# backend.env 里写入 / 更新一项（值里的 | & \ 会被转义）
set_env() {
  local key=$1 value=$2 escaped
  escaped=$(printf '%s' "$value" | sed -e 's/[\\|&]/\\&/g')
  if grep -q "^${key}=" "$ENV_FILE"; then
    sed -i "s|^${key}=.*|${key}=${escaped}|" "$ENV_FILE"
  else
    printf '%s=%s\n' "$key" "$value" >> "$ENV_FILE"
  fi
}
get_env() { grep "^$1=" "$ENV_FILE" 2>/dev/null | tail -1 | cut -d= -f2- || true; }
add_cors() {
  local origin=$1 current
  current=$(get_env CORS_ORIGINS)
  case ",$current," in *",$origin,"*) return ;; esac
  set_env CORS_ORIGINS "${current:+$current,}$origin"
}

if [ "$MODE" = ip ]; then
  if [ -z "$PUBLIC_IP" ]; then
    # 云服务器网卡上通常是内网地址，先问外部服务；都失败再用本机第一个地址
    PUBLIC_IP=$(curl -fsS -m 5 https://api.ipify.org 2>/dev/null || curl -fsS -m 5 https://ifconfig.me 2>/dev/null || hostname -I | awk '{print $1}')
  fi
  [[ "$PUBLIC_IP" =~ ^[0-9]{1,3}(\.[0-9]{1,3}){3}$ ]] || { echo "无法识别公网 IP（$PUBLIC_IP），请写成：--ip 1.2.3.4"; exit 1; }
  APP_URL="http://$PUBLIC_IP"
  echo "部署模式：公网 IP + HTTP（$APP_URL）。请确认云服务器安全组已放行 80 端口。"
else
  [[ "$EMAIL" == *@* ]] || { echo "用法：sudo bash deploy/install.sh 你的邮箱（用于 HTTPS 证书到期提醒），或 --ip"; exit 1; }
  APP_URL="https://$APP_DOMAIN"
  echo "部署模式：域名 + HTTPS（$APP_URL，主页 https://$DOMAIN）"
fi

echo "==> 1/$STEPS 安装系统依赖"
apt-get update -y
PKGS="git nginx python3 python3-venv python3-pip sqlite3 curl ca-certificates"
[ "$MODE" = domain ] && PKGS="$PKGS certbot python3-certbot-nginx"
# shellcheck disable=SC2086
apt-get install -y $PKGS
if ! command -v node >/dev/null || [ "$(node -v | cut -c2- | cut -d. -f1)" -lt 20 ]; then
  curl -fsSL https://deb.nodesource.com/setup_22.x | bash -
  apt-get install -y nodejs
fi

echo "==> 2/$STEPS 创建运行用户与目录"
id xueyeguanjia >/dev/null 2>&1 || useradd --system --home "$ROOT" --shell /usr/sbin/nologin xueyeguanjia
mkdir -p "$SITE" "$DATA/feedback" "$DATA/health" /etc/xueyeguanjia /var/www/certbot /var/backups/xueyeguanjia

echo "==> 3/$STEPS 拉取代码"
if [ -d "$APP/.git" ]; then git -C "$APP" pull --ff-only; else git clone --depth 1 "$REPO" "$APP"; fi

echo "==> 4/$STEPS 后端：虚拟环境、依赖与配置"
[ -d "$ROOT/venv" ] || python3 -m venv "$ROOT/venv"
"$ROOT/venv/bin/pip" install --upgrade pip -q
"$ROOT/venv/bin/pip" install -r "$APP/Backend+AI-interface/requirements.txt" -q
if [ ! -f "$ENV_FILE" ]; then
  cp "$APP/deploy/backend.env.example" "$ENV_FILE"
  set_env JWT_SECRET_KEY "$(openssl rand -base64 48 | tr -d '\n')"
  echo "    已生成 $ENV_FILE（含随机 JWT 密钥），如需 AI 请填写 DEEPSEEK_API_KEY"
fi
add_cors "$APP_URL"
# 通知里的后台链接：没设过、或从 IP 模式切到域名时更新
current_url=$(get_env APP_PUBLIC_URL)
if [ -z "$current_url" ] || { [ "$MODE" = domain ] && [[ "$current_url" == http://* ]]; }; then
  set_env APP_PUBLIC_URL "$APP_URL"
fi
[ -n "${ICP_NUMBER:-}" ] && set_env ICP_NUMBER "$ICP_NUMBER"
[ -n "${POLICE_BEIAN:-}" ] && set_env POLICE_BEIAN "$POLICE_BEIAN"
[ -n "${CONTACT_EMAIL:-}" ] && set_env CONTACT_EMAIL "$CONTACT_EMAIL"

echo "==> 5/$STEPS 前端：打包网页版；介绍与下载页"
(cd "$APP/Frontend" && npm ci --no-audit --no-fund && npm run build)
ICP=$(get_env ICP_NUMBER)
POLICE=$(get_env POLICE_BEIAN)
POLICE_CODE=$(printf '%s' "$POLICE" | tr -cd '0-9')
html_escape() { printf '%s' "$1" | sed -e 's/&/\&amp;/g' -e 's/</\&lt;/g' -e 's/>/\&gt;/g' -e 's/"/\&quot;/g'; }
sed_value() { printf '%s' "$1" | sed -e 's/[\\|&]/\\&/g'; }
mkdir -p "$SITE/screenshots"
cp "$APP"/docs/screenshots/*.png "$SITE/screenshots/" 2>/dev/null || true
sed -e "s|__APP_URL__|$(sed_value "$APP_URL")|g" \
    -e "s|__DOWNLOAD_URL__|$(sed_value "$DOWNLOAD_URL")|g" \
    -e "s|__ICP_NUMBER__|$(sed_value "$(html_escape "$ICP")")|g" \
    -e "s|__POLICE_BEIAN__|$(sed_value "$(html_escape "$POLICE")")|g" \
    -e "s|__POLICE_CODE__|$POLICE_CODE|g" \
    "$APP/deploy/landing/index.html" > "$SITE/index.html"

chown -R xueyeguanjia:xueyeguanjia "$ROOT" "$DATA"
chown root:xueyeguanjia "$ENV_FILE"; chmod 640 "$ENV_FILE"

echo "==> 6/$STEPS 后端服务"
cp "$APP/deploy/xueyeguanjia.service" /etc/systemd/system/xueyeguanjia.service
systemctl daemon-reload
systemctl enable --now xueyeguanjia
systemctl restart xueyeguanjia

echo "==> 7/$STEPS 运维：每日备份、恢复脚本、健康检查（每分钟，失败时通过反馈通知渠道告警）"
install -m 755 "$APP/deploy/backup.sh" /usr/local/bin/xueyeguanjia-backup
install -m 755 "$APP/deploy/restore.sh" /usr/local/bin/xueyeguanjia-restore
install -m 755 "$APP/deploy/healthcheck.sh" /usr/local/bin/xueyeguanjia-healthcheck
echo "30 3 * * * root /usr/local/bin/xueyeguanjia-backup >> /var/log/xueyeguanjia-backup.log 2>&1" > /etc/cron.d/xueyeguanjia-backup
cp "$APP/deploy/xueyeguanjia-health.service" "$APP/deploy/xueyeguanjia-health.timer" /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now xueyeguanjia-health.timer

echo "==> 8/$STEPS Nginx"
rm -f /etc/nginx/sites-enabled/default
if [ "$MODE" = ip ]; then
  rm -f /etc/nginx/sites-enabled/xueyeguanjia.conf
  cp "$APP/deploy/nginx/xueyeguanjia-ip.conf" "$CONF_DIR/xueyeguanjia-ip.conf"
  ln -sf "$CONF_DIR/xueyeguanjia-ip.conf" /etc/nginx/sites-enabled/xueyeguanjia-ip.conf
  nginx -t && systemctl reload nginx
  HEALTH="$APP_URL/api/health"
else
  # 从 IP 模式切过来：先停用 IP 配置（它是 default_server，会抢走证书验证请求）
  rm -f /etc/nginx/sites-enabled/xueyeguanjia-ip.conf
  CONF=$CONF_DIR/xueyeguanjia.conf
  if [ ! -d "/etc/letsencrypt/live/$DOMAIN" ]; then
    # 先用纯 HTTP 配置申请证书
    cat > "$CONF" <<NGINX
server {
    listen 80;
    server_name $DOMAIN www.$DOMAIN $APP_DOMAIN;
    location /.well-known/acme-challenge/ { root /var/www/certbot; }
    location / { return 200 'ok'; }
}
NGINX
    ln -sf "$CONF" /etc/nginx/sites-enabled/xueyeguanjia.conf
    nginx -t && systemctl reload nginx
    certbot certonly --webroot -w /var/www/certbot -d "$DOMAIN" -d "www.$DOMAIN" -d "$APP_DOMAIN" \
      --email "$EMAIL" --agree-tos --non-interactive
  fi
  sed "s/xueyeguanjia\.com/$DOMAIN/g" "$APP/deploy/nginx/xueyeguanjia.conf" > "$CONF"
  ln -sf "$CONF" /etc/nginx/sites-enabled/xueyeguanjia.conf
  nginx -t && systemctl reload nginx
  HEALTH="$APP_URL/api/health"
fi

sleep 2
if curl -fsS -m 10 "$HEALTH" >/dev/null; then
  echo
  echo "部署完成：网页版 $APP_URL"
  if [ "$MODE" = ip ]; then
    echo "  介绍与下载页：$APP_URL/intro/"
    echo "  注意：纯 HTTP 下浏览器不支持「断网可看」与「安装到桌面」，密码以明文传输，仅用于备案前测试。"
    echo "  备案通过后切换到域名 + HTTPS：sudo DOMAIN=你的域名 bash deploy/install.sh 你的邮箱"
  else
    echo "  介绍与下载页：https://$DOMAIN"
  fi
  echo "  配置文件：$ENV_FILE（改完执行 systemctl restart xueyeguanjia）"
  echo "  恢复备份：sudo xueyeguanjia-restore latest    健康检查日志：journalctl -t xueyeguanjia-health"
else
  echo "后端未响应，请查看：journalctl -u xueyeguanjia -n 50"
fi
