#!/usr/bin/env bash
# 学业管家一键部署（Ubuntu 22.04 / 24.04，root 运行）。可重复执行：已存在的配置会保留，代码会更新。
#
#   sudo bash deploy/install.sh you@example.com
#
# 前提：域名 xueyeguanjia.com、www、app 三条 A 记录已指向本机，且已完成 ICP 备案（国内服务器）。
set -euo pipefail

EMAIL=${1:-}
DOMAIN=xueyeguanjia.com
APP_DOMAIN=app.$DOMAIN
REPO=https://github.com/TLOMMY/Integrated_study_planner.git
ROOT=/opt/xueyeguanjia
APP=$ROOT/app
DATA=/var/lib/xueyeguanjia
ENV_FILE=/etc/xueyeguanjia/backend.env

[ "$(id -u)" -eq 0 ] || { echo "请用 sudo 运行"; exit 1; }
[ -n "$EMAIL" ] || { echo "用法：sudo bash deploy/install.sh 你的邮箱（用于 HTTPS 证书到期提醒）"; exit 1; }

echo "==> 1/7 安装系统依赖"
apt-get update -y
apt-get install -y git nginx python3 python3-venv python3-pip sqlite3 certbot python3-certbot-nginx curl ca-certificates
if ! command -v node >/dev/null || [ "$(node -v | cut -c2- | cut -d. -f1)" -lt 20 ]; then
  curl -fsSL https://deb.nodesource.com/setup_22.x | bash -
  apt-get install -y nodejs
fi

echo "==> 2/7 创建运行用户与目录"
id xueyeguanjia >/dev/null 2>&1 || useradd --system --home "$ROOT" --shell /usr/sbin/nologin xueyeguanjia
mkdir -p "$ROOT/site" "$DATA/feedback" /etc/xueyeguanjia /var/www/certbot /var/backups/xueyeguanjia

echo "==> 3/7 拉取代码"
if [ -d "$APP/.git" ]; then git -C "$APP" pull --ff-only; else git clone --depth 1 "$REPO" "$APP"; fi

echo "==> 4/7 后端：虚拟环境与依赖"
[ -d "$ROOT/venv" ] || python3 -m venv "$ROOT/venv"
"$ROOT/venv/bin/pip" install --upgrade pip -q
"$ROOT/venv/bin/pip" install -r "$APP/Backend+AI-interface/requirements.txt" -q
if [ ! -f "$ENV_FILE" ]; then
  cp "$APP/deploy/backend.env.example" "$ENV_FILE"
  sed -i "s|^JWT_SECRET_KEY=.*|JWT_SECRET_KEY=$(openssl rand -base64 48 | tr -d '\n')|" "$ENV_FILE"
  echo "    已生成 $ENV_FILE（含随机 JWT 密钥），如需 AI 请填写 DEEPSEEK_API_KEY"
fi
chmod 600 "$ENV_FILE"

echo "==> 5/7 前端：打包网页版"
(cd "$APP/Frontend" && npm ci --no-audit --no-fund && npm run build)

chown -R xueyeguanjia:xueyeguanjia "$ROOT" "$DATA"
chown root:xueyeguanjia "$ENV_FILE"; chmod 640 "$ENV_FILE"

echo "==> 6/7 后端服务与每日备份"
cp "$APP/deploy/xueyeguanjia.service" /etc/systemd/system/xueyeguanjia.service
systemctl daemon-reload
systemctl enable --now xueyeguanjia
systemctl restart xueyeguanjia
install -m 755 "$APP/deploy/backup.sh" /usr/local/bin/xueyeguanjia-backup
echo "30 3 * * * root /usr/local/bin/xueyeguanjia-backup >> /var/log/xueyeguanjia-backup.log 2>&1" > /etc/cron.d/xueyeguanjia-backup

echo "==> 7/7 Nginx 与 HTTPS 证书"
CONF=/etc/nginx/sites-available/xueyeguanjia.conf
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
  rm -f /etc/nginx/sites-enabled/default
  nginx -t && systemctl reload nginx
  certbot certonly --webroot -w /var/www/certbot -d "$DOMAIN" -d "www.$DOMAIN" -d "$APP_DOMAIN" \
    --email "$EMAIL" --agree-tos --non-interactive
fi
cp "$APP/deploy/nginx/xueyeguanjia.conf" "$CONF"
ln -sf "$CONF" /etc/nginx/sites-enabled/xueyeguanjia.conf
nginx -t && systemctl reload nginx

sleep 2
if curl -fsS "https://$APP_DOMAIN/api/health" >/dev/null; then
  echo "部署完成：https://$APP_DOMAIN"
else
  echo "后端未响应，请查看：journalctl -u xueyeguanjia -n 50"
fi
