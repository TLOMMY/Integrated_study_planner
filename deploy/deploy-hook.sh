#!/usr/bin/env bash
# 自动部署入口，由 install.sh 安装为 /usr/local/bin/xueyeguanjia-deploy。
# GitHub Actions 通过 deploy 用户的受限 SSH 密钥调用它（见 deploy/setup-autodeploy.sh）。
# 不接受任何参数，只做一件事：拉取最新代码，按首次部署时的方式重新运行 install.sh。
set -euo pipefail

APP=/opt/xueyeguanjia/app
CONF=/etc/xueyeguanjia/deploy.conf

[ "$(id -u)" -eq 0 ] || { echo "需要 root 权限"; exit 1; }
[ -f "$CONF" ] || { echo "缺少 $CONF，请先手动运行一次 deploy/install.sh"; exit 1; }
# shellcheck disable=SC1090
. "$CONF"

# 同一时间只允许一次部署
exec 9>/run/xueyeguanjia-deploy.lock
flock -w 900 9 || { echo "另一次部署仍在进行，已放弃"; exit 1; }

echo "==> 拉取最新代码"
git -C "$APP" pull --ff-only
echo "    当前版本：$(git -C "$APP" log --oneline -1)"

# 依赖已装好时跳过 apt，避免与系统自动更新抢锁
export DOMAIN="$DEPLOY_DOMAIN" SKIP_APT=1
if [ "$DEPLOY_MODE" = ip ]; then
  bash "$APP/deploy/install.sh" --ip "$DEPLOY_IP"
else
  bash "$APP/deploy/install.sh" "$DEPLOY_EMAIL"
fi
