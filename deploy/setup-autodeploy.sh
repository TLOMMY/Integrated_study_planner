#!/usr/bin/env bash
# 配置 GitHub Actions 自动部署（在服务器上用 root 运行一次；再运行一次即更换密钥，旧密钥立即失效）：
#   sudo bash deploy/setup-autodeploy.sh [服务器地址]
#
# 做的事：
#   1. 创建 deploy 用户（不能用密码登录）
#   2. 生成一把专用 SSH 密钥；这把密钥登录后只能执行 xueyeguanjia-deploy，不能开终端、不能转发端口
#   3. sudo 规则只放行 xueyeguanjia-deploy 这一条命令，且不能带参数
#   4. 打印需要填进 GitHub 仓库 Settings → Secrets and variables → Actions 的三项
set -euo pipefail

CONF=/etc/xueyeguanjia/deploy.conf
HOOK=/usr/local/bin/xueyeguanjia-deploy
DEPLOY_USER=deploy

[ "$(id -u)" -eq 0 ] || { echo "请用 sudo 运行"; exit 1; }
if [ ! -x "$HOOK" ] || [ ! -f "$CONF" ]; then
  echo "请先运行一次 deploy/install.sh（会安装部署命令并记录部署方式）"
  exit 1
fi

HOST=${1:-}
if [ -z "$HOST" ]; then
  # shellcheck disable=SC1090
  . "$CONF"
  if [ "$DEPLOY_MODE" = ip ]; then HOST=$DEPLOY_IP; else HOST=app.$DEPLOY_DOMAIN; fi
fi

id "$DEPLOY_USER" >/dev/null 2>&1 || useradd --create-home --shell /bin/bash "$DEPLOY_USER"
passwd -l "$DEPLOY_USER" >/dev/null
HOME_DIR=$(getent passwd "$DEPLOY_USER" | cut -d: -f6)

TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
ssh-keygen -q -t ed25519 -N "" -C "github-actions-deploy" -f "$TMP/key"

install -d -m 700 -o "$DEPLOY_USER" -g "$DEPLOY_USER" "$HOME_DIR/.ssh"
printf 'command="sudo -n %s",restrict %s\n' "$HOOK" "$(cat "$TMP/key.pub")" > "$HOME_DIR/.ssh/authorized_keys"
chown "$DEPLOY_USER:$DEPLOY_USER" "$HOME_DIR/.ssh/authorized_keys"
chmod 600 "$HOME_DIR/.ssh/authorized_keys"

printf '%s ALL=(root) NOPASSWD: %s ""\n' "$DEPLOY_USER" "$HOOK" > "$TMP/sudoers"
visudo -cf "$TMP/sudoers" >/dev/null
install -m 440 "$TMP/sudoers" /etc/sudoers.d/xueyeguanjia-deploy

echo
echo "配置完成。打开 GitHub 仓库 Settings → Secrets and variables → Actions → New repository secret，依次添加："
echo
echo "━━━━ 名称：DEPLOY_HOST ━━━━"
echo "$HOST"
echo
echo "━━━━ 名称：DEPLOY_SSH_KEY（从 BEGIN 到 END 整段复制，包括这两行）━━━━"
cat "$TMP/key"
echo
echo "━━━━ 名称：DEPLOY_KNOWN_HOSTS（整段复制）━━━━"
for f in /etc/ssh/ssh_host_*_key.pub; do
  printf '%s %s\n' "$HOST" "$(cut -d' ' -f1,2 "$f")"
done
echo
echo "私钥只显示这一次，服务器上不保留。复制完成后建议执行 clear 清屏。"
