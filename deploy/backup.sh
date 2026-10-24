#!/usr/bin/env bash
# 每天备份数据库，保留最近 30 天。由 install.sh 写入 /etc/cron.d/xueyeguanjia-backup。
# 使用 sqlite3 的 .backup：服务运行中也能得到一致的副本。
set -euo pipefail

DB=/var/lib/xueyeguanjia/study_planner.db
DEST=/var/backups/xueyeguanjia
KEEP_DAYS=30

mkdir -p "$DEST"
[ -f "$DB" ] || { echo "数据库不存在：$DB"; exit 0; }
STAMP=$(date +%Y%m%d-%H%M%S)
sqlite3 "$DB" ".backup '$DEST/study_planner-$STAMP.db'"
gzip -f "$DEST/study_planner-$STAMP.db"
find "$DEST" -name 'study_planner-*.db.gz' -mtime +"$KEEP_DAYS" -delete
echo "已备份到 $DEST/study_planner-$STAMP.db.gz"
