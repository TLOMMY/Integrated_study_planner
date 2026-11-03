#!/usr/bin/env bash
# 每天备份数据库，保留最近 30 天。由 install.sh 写入 /etc/cron.d/xueyeguanjia-backup。
# 使用 sqlite3 的 .backup：服务运行中也能得到一致的副本（没有 sqlite3 命令时用 Python 的 sqlite3 模块，效果相同）。
# 恢复见 deploy/restore.sh。路径可用环境变量覆盖（本地演练用）：DB、DEST、KEEP_DAYS、PYTHON。
set -euo pipefail

DB=${DB:-/var/lib/xueyeguanjia/study_planner.db}
DEST=${DEST:-/var/backups/xueyeguanjia}
KEEP_DAYS=${KEEP_DAYS:-30}
PYTHON=${PYTHON:-python3}

sqlite_backup() {
  # $1 源库  $2 目标文件
  if command -v sqlite3 >/dev/null; then
    sqlite3 "$1" ".backup '$2'"
  else
    "$PYTHON" -c 'import sqlite3, sys
src = sqlite3.connect(sys.argv[1]); dst = sqlite3.connect(sys.argv[2])
src.backup(dst); dst.close(); src.close()' "$1" "$2"
  fi
}

mkdir -p "$DEST"
[ -f "$DB" ] || { echo "数据库不存在：$DB"; exit 0; }
STAMP=$(date +%Y%m%d-%H%M%S)
sqlite_backup "$DB" "$DEST/study_planner-$STAMP.db"
gzip -f "$DEST/study_planner-$STAMP.db"
find "$DEST" -name 'study_planner-*.db.gz' -mtime +"$KEEP_DAYS" -delete
echo "已备份到 $DEST/study_planner-$STAMP.db.gz"
