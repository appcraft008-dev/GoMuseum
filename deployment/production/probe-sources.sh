#!/bin/bash
# GoMuseum 外部富化源探活（每 3 天），由 cron 调用。
#
# 为什么是 3 天而不是每天:要防的是"源死了两个月没人知道",不是"晚一天知道"。
# 3 天把最坏发现延迟从 60 天压到 3 天,收益的 95% 已经拿到,
# 而对上游的礼貌请求量只有每天的三分之一。
#
# 为什么需要:单源容错(纪律①)把源的死讯降级成一条 warning —— 对的设计,
# 但代价是源死掉不会报错,只会让内容悄悄变薄。2026 年 Joconde 老 API 7-22 断供,
# **两个月没人发现**。详见 backend/scripts/probe_sources.py。
#
# ⚠️ 安装要**手工拷到 VPS**,CD 不会带它过去 —— deploy.yml 只 rsync `backend/`,
# 仓库里的 deployment/ 目录在 VPS 上并不存在。位置沿用 backup.sh 的约定:/opt/gomuseum/。
#
#   scp -i ~/.ssh/deepmeeting_deploy deployment/production/probe-sources.sh \
#       root@<VPS>:/opt/gomuseum/probe-sources.sh
#   ssh ... 'chmod +x /opt/gomuseum/probe-sources.sh'
#   crontab -e   # 与 backup.sh / reconcile-refunds.sh 同一个 crontab
#   41 5 */3 * * /opt/gomuseum/probe-sources.sh >> /var/log/gomuseum-probe.log 2>&1
#
# ✅ 已于 2026-09-12 装上 prod(VPS 38.242.207.219),并用
#    `env -i PATH=/usr/bin:/bin` 剥空环境实跑验证过 —— "手动能跑≠cron 能跑",
#    典型死法是 docker 装在 /usr/local/bin 而 cron 的 PATH 够不着(本机在 /usr/bin,没踩到)。
#
# ⚠️ 改了这个文件之后要**重新 scp** —— 它不随部署更新。
#
# ⚠️ 非零退出**必须有人看见**。退出码:
#   0 = 全活   1 = 有源探不通   2 = 探针自检没过(探活结果不可信)
# 先跑自检再探活:一个没有判断力的探针每天都会说"一切正常",
# 那比没有探活更糟 —— 它会让人以为这件事已经有人看着了。
set -uo pipefail

docker exec gomuseum_prod_backend python scripts/probe_sources.py --self-test || {
    echo "[$(date -Is)] probe_sources 自检失败,跳过探活"
    exit 2
}
docker exec gomuseum_prod_backend python scripts/probe_sources.py
code=$?
echo "[$(date -Is)] probe_sources exit=$code"
exit $code
