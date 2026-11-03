#!/usr/bin/env bash
# 从 backup.sh 生成的备份恢复数据库（install.sh 安装到 /usr/local/bin/xueyeguanjia-restore）。
#
#   sudo xueyeguanjia-restore                     列出可用备份
#   sudo xueyeguanjia-restore latest              恢复最新的备份
#   sudo xueyeguanjia-restore /var/backups/xueyeguanjia/study_planner-20261026-033000.db.gz
#
# 步骤：校验备份完整性 → 停止后端 → 先把当前数据库备份为 pre-restore-*.db.gz（可再恢复回来）
#       → 替换数据库并清理 -wal/-shm → 修正属主 → 启动后端并检查 /health。
# 环境变量（本地演练用）：DB、DEST、SERVICE（留空则不启停服务）、OWNER（留空则不 chown）、PYTHON、
#   HEALTH_URL（留空则不检查）、YES=1 跳过确认。
set -euo pipefail

DB=${DB:-/var/lib/xueyeguanjia/study_planner.db}
DEST=${DEST:-/var/backups/xueyeguanjia}
SERVICE=${SERVICE-xueyeguanjia}
OWNER=${OWNER-xueyeguanjia:xueyeguanjia}
PYTHON=${PYTHON:-python3}
HEALTH_URL=${HEALTH_URL-http://127.0.0.1:8000/health}
YES=${YES:-0}

die() { echo "错误：$*" >&2; exit 1; }

sqlite_backup() {
  if command -v sqlite3 >/dev/null; then
    sqlite3 "$1" ".backup '$2'"
  else
    "$PYTHON" -c 'import sqlite3, sys
src = sqlite3.connect(sys.argv[1]); dst = sqlite3.connect(sys.argv[2])
src.backup(dst); dst.close(); src.close()' "$1" "$2"
  fi
}

# 输出 "ok" 表示完整；同时要求存在 users 表（确认是本应用的库）
sqlite_check() {
  if command -v sqlite3 >/dev/null; then
    local result
    result=$(sqlite3 "$1" "PRAGMA integrity_check;" 2>&1 | head -1)
    [ "$result" = "ok" ] || { echo "$result"; return; }
    [ "$(sqlite3 "$1" "SELECT count(*) FROM sqlite_master WHERE type='table' AND name='users';")" = "1" ] && echo ok || echo "缺少 users 表"
  else
    "$PYTHON" -c 'import sqlite3, sys
try:
    con = sqlite3.connect(sys.argv[1])
    result = con.execute("PRAGMA integrity_check").fetchone()[0]
    if result == "ok" and not con.execute("SELECT 1 FROM sqlite_master WHERE type=\"table\" AND name=\"users\"").fetchone():
        result = "缺少 users 表"
    print(result)
except sqlite3.DatabaseError as exc:
    print(exc)' "$1"
  fi
}

list_backups() {
  ls -1t "$DEST"/study_planner-*.db.gz "$DEST"/pre-restore-*.db.gz 2>/dev/null || true
}

TARGET=${1:-}
if [ -z "$TARGET" ]; then
  echo "可用备份（新的在前）："
  list_backups | head -20 | sed 's/^/  /'
  echo
  echo "用法：$0 latest | <备份文件路径>"
  exit 0
fi
if [ "$TARGET" = "latest" ]; then
  TARGET=$(ls -1t "$DEST"/study_planner-*.db.gz 2>/dev/null | head -1 || true)
  [ -n "$TARGET" ] || die "$DEST 下没有备份"
fi
[ -f "$TARGET" ] || die "备份文件不存在：$TARGET"

WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT
CANDIDATE="$WORK/restore.db"
case "$TARGET" in
  *.gz) gunzip -c "$TARGET" > "$CANDIDATE" ;;
  *) cp "$TARGET" "$CANDIDATE" ;;
esac
CHECK=$(sqlite_check "$CANDIDATE")
[ "$CHECK" = "ok" ] || die "备份文件校验失败（$CHECK），未做任何修改"

echo "将用 $TARGET 恢复 $DB"
if [ "$YES" != "1" ]; then
  read -r -p "当前数据库会先备份，再被替换。确认恢复？输入 yes 继续：" answer
  [ "$answer" = "yes" ] || die "已取消"
fi

if [ -n "$SERVICE" ] && command -v systemctl >/dev/null; then
  echo "==> 停止 $SERVICE"
  systemctl stop "$SERVICE"
fi

mkdir -p "$DEST" "$(dirname "$DB")"
STAMP=$(date +%Y%m%d-%H%M%S)
if [ -f "$DB" ]; then
  SAFETY="$DEST/pre-restore-$STAMP.db"
  sqlite_backup "$DB" "$SAFETY"
  gzip -f "$SAFETY"
  echo "==> 当前数据库已备份到 $SAFETY.gz（恢复错了可以用它再恢复回来）"
fi

# 同目录下先写临时文件再改名，避免中途失败留下半个数据库
cp "$CANDIDATE" "$DB.restoring"
mv -f "$DB.restoring" "$DB"
rm -f "$DB-wal" "$DB-shm" "$DB-journal"
if [ -n "$OWNER" ] && [ "$(id -u)" -eq 0 ]; then
  chown "$OWNER" "$DB"
fi
chmod 640 "$DB" 2>/dev/null || true
echo "==> 已恢复：$DB"

if [ -n "$SERVICE" ] && command -v systemctl >/dev/null; then
  echo "==> 启动 $SERVICE"
  systemctl start "$SERVICE"
  if [ -n "$HEALTH_URL" ]; then
    for _ in 1 2 3 4 5 6 7 8 9 10; do
      sleep 1
      if curl -fsS -m 5 -o /dev/null "$HEALTH_URL"; then
        echo "后端运行正常"
        exit 0
      fi
    done
    die "后端未响应，请查看：journalctl -u $SERVICE -n 50"
  fi
fi
