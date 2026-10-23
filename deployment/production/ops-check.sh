#!/bin/bash
# GoMuseum 容量监控(每 5 分钟),由 cron 调用。spec 2026-10-21-elastic-scaling-design §7;
# 告警含义与处理办法见 docs/ops/capacity-runbook.md。
#
# ⚠️ 安装要手工拷到 VPS(CD 只 rsync backend/),位置沿用 /opt/gomuseum/:
#   scp -i ~/.ssh/deepmeeting_deploy deployment/production/ops-check.sh \
#       root@<VPS>:/opt/gomuseum/ops-check.sh
#   ssh ... 'chmod +x /opt/gomuseum/ops-check.sh'
#   crontab -e   # 与 backup.sh 同一个 crontab;上线头 7 天带 --no-mail(只记不发)
#   */5 * * * * /opt/gomuseum/ops-check.sh --no-mail >> /var/log/gomuseum-ops-check.log 2>&1
# 装完先用 cron 的短 PATH 实跑一次:env -i PATH=/usr/bin:/bin /opt/gomuseum/ops-check.sh --dry-run
# 不落地文件也能预演:ssh ... 'bash -s -- --dry-run' < deployment/production/ops-check.sh
# ⚠️ 改了这个文件之后要重新 scp。
#
# 宿主机指标在这里取(容器看不到宿主机),nginx 日志从 stdin 喂给容器里的 ops_check,
# 告警邮件由容器里的 ops_alert 发。额外参数(--dry-run / --no-mail)原样转给 ops_check。
# 退出码同 ops_check:0 正常 | 2 有告警但发不出去(OPS_ALERT_EMAIL 未配置或发信失败)
set -uo pipefail

case " $* " in *" --dry-run "*) dry=1 ;; *) dry=0 ;; esac
STATE=/opt/gomuseum/ops-check.cpu  # 上次的 /proc/stat 累计值,算这 5 分钟的 CPU
read -r _ u n s i w q sq st _ < /proc/stat
busy=$((u + n + s + q + sq + st))
total=$((busy + i + w))
cpu=""
if read -r pb pt < "$STATE" 2>/dev/null && [ "$total" -gt "$pt" ]; then
    cpu=$((100 * (busy - pb) / (total - pt)))
fi
# 预演不动状态文件:否则下一次 cron 算的是一个更短的区间
[ "$dry" = 1 ] || echo "$busy $total" > "$STATE"
mem=$(free | awk '/^Mem:/ {printf "%d", 100 * ($2 - $7) / $2}')
disk=$(df -P / | awk 'NR == 2 {sub("%", "", $5); print $5}')

# 只取带 urt= 的行(只有 api.gomuseum.app 用 main_rt 格式);grep 没匹配时别让 pipefail 误报
{ tail -n 100000 /var/log/nginx/access.log 2>/dev/null | grep -F ' urt=' || true; } |
    docker exec -i gomuseum_prod_backend python -m scripts.ops_check \
        --cpu "$cpu" --mem "$mem" --disk "$disk" "$@"
code=$?
echo "[$(date -Is)] ops_check exit=$code cpu=$cpu mem=$mem disk=$disk $*"
exit $code
