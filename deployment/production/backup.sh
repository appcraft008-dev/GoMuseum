#!/bin/bash
# GoMuseum 数据库每日备份（保留 7 天），由 cron 调用
set -euo pipefail
BACKUP_DIR=/opt/gomuseum/backups
mkdir -p "$BACKUP_DIR"
STAMP=$(date +%Y%m%d_%H%M%S)
docker exec gomuseum_prod_postgres pg_dump -U gomuseum gomuseum | gzip > "$BACKUP_DIR/gomuseum_$STAMP.sql.gz"
find "$BACKUP_DIR" -name "gomuseum_*.sql.gz" -mtime +7 -delete
echo "backup done: gomuseum_$STAMP.sql.gz"
