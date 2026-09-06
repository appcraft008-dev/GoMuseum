#!/bin/bash
# GoMuseum 退款对账（每日），由 cron 调用。
#
# 为什么需要:RTDN 推送会丢(Pub/Sub 放弃重试、订阅配错、IAM 被改、部署重启),
# 丢一条 = 用户退了钱通票照用满 7 天,而且**没有任何地方会报错**。
# 推送做及时,这个脚本做兜底。详见 backend/scripts/reconcile_refunds.py。
#
# 安装(在 VPS 上,与 backup.sh 同一个 crontab):
#   crontab -e
#   17 4 * * * /opt/gomuseum/deployment/production/reconcile-refunds.sh >> /var/log/gomuseum-refunds.log 2>&1
#
# ⚠️ 非零退出**必须有人看见**。退出码:
#   0 = 干净   1 = 有订单查不到(对账有盲区)   2 = 根本没跑起来(没凭证)   3 = 撤销闸拦下
# cron 默认会把非零退出的输出邮件给本机用户;没配 MTA 的话,靠上面那个日志文件
# 加一条 ops 巡检 —— **别让它只写进 /dev/null**,那和没有对账是一回事。
set -uo pipefail

docker exec gomuseum_prod_backend python scripts/reconcile_refunds.py --apply
code=$?
echo "[$(date -Is)] reconcile_refunds exit=$code"
exit $code
