#!/bin/bash
# GoMuseum 识别照片生命周期清理(每日),由 cron 调用。
#
# 为什么需要:用户主动发送的识别照片只当信号、不当资产(spec 2026-10-05 S5):
# 超过 90 天或处理完(status=done)必须删;桶里没有行引用、超过 90 天的孤儿也删。
# 隐私政策写了「最长 90 天」——这个脚本不跑,承诺就是假的。
#
# ⚠️ 安装要**手工拷到 VPS**(同 reconcile-refunds.sh,CD 只 rsync backend/):
#   scp -i ~/.ssh/deepmeeting_deploy deployment/production/purge-recognition-photos.sh \
#       root@<VPS>:/opt/gomuseum/purge-recognition-photos.sh
#   ssh ... 'chmod +x /opt/gomuseum/purge-recognition-photos.sh'
#   crontab -e   # 与 backup.sh 同一个 crontab
#   37 4 * * * /opt/gomuseum/purge-recognition-photos.sh >> /var/log/gomuseum-photo-purge.log 2>&1
#
# ⚠️ 改了这个文件之后要**重新 scp**。私有桶未配置时脚本打印后正常退出 0。
set -uo pipefail

docker exec gomuseum_prod_backend python scripts/purge_recognition_photos.py
code=$?
echo "[$(date -Is)] purge_recognition_photos exit=$code"
exit $code
