#!/bin/bash
# GoMuseum 数据库每日备份 + 每日音频盘点,由 cron 调用(每天 04:20)。
#
# 保留策略(契约纪律 37 第④层,2026-09-26 起):
#   - 每日备份保留 14 天
#   - 每周日另存一份周备份,保留 8 周
# 原来只留 7 天:2026-09-14 的跨馆作者音频事故 12 天后才被发现,那时原文已被轮转掉,
# 只能重录。「发现得慢」是常态 —— 保留期要按「最慢多久能发现」来定,不是按磁盘。
set -euo pipefail
BACKUP_DIR=/opt/gomuseum/backups
WEEKLY_DIR="$BACKUP_DIR/weekly"
mkdir -p "$BACKUP_DIR" "$WEEKLY_DIR"
STAMP=$(date +%Y%m%d_%H%M%S)
FILE="$BACKUP_DIR/gomuseum_$STAMP.sql.gz"
docker exec gomuseum_prod_postgres pg_dump -U gomuseum gomuseum | gzip > "$FILE"
if [ "$(date +%u)" = "7" ]; then
  cp "$FILE" "$WEEKLY_DIR/"
fi
find "$BACKUP_DIR" -maxdepth 1 -name "gomuseum_*.sql.gz" -mtime +14 -delete
find "$WEEKLY_DIR" -name "gomuseum_*.sql.gz" -mtime +56 -delete
echo "backup done: gomuseum_$STAMP.sql.gz"

# 每日音频盘点(纪律 37 第③层):已挂音频只该涨不该无声地掉,掉了发邮件。
# 放在备份之后:告警里说「用 pg_dump 恢复」时,当天的 dump 已经在了。
# 盘点失败不影响备份本身(set -e 之外单独判退出码):1=有损失已告警,2=告警没发出去。
set +e
docker exec gomuseum_prod_backend python -m scripts.audio_inventory
rc=$?
set -e
echo "audio inventory exit=$rc"
