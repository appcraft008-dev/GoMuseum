# 容量运维手册(弹性扩容阶段 0)

设计:`docs/superpowers/specs/2026-10-21-elastic-scaling-design.md`(§7 监控、§11 分阶段)。告警邮件里的「见 docs/ops/capacity-runbook.md」指的就是本文。

## 1. 运行方式

宿主机 cron 每 5 分钟跑 `/opt/gomuseum/ops-check.sh`(仓库 `deployment/production/ops-check.sh`):在宿主机上取 CPU、内存、磁盘,把 nginx 日志从 stdin 喂给容器里的 `python -m scripts.ops_check`。ops_check 查库、写一条 `ops_sample`,满足条件时发告警邮件并记一条 `ops_alert`。

| 模式 | 参数 | 行为 |
|---|---|---|
| 正常 | 无 | 采样;到期的告警发邮件,发出后记 `ops_alert(mailed=true)` |
| 只记不发 | `--no-mail` | 采样;到期的告警只记 `ops_alert(mailed=false)` 并打到日志。上线头 7 天用这个(R13) |
| 预演 | `--dry-run` | 不写库、不发信,只打印会告警的 key |

- 手动预演(不落地文件):`ssh -i ~/.ssh/deepmeeting_deploy root@38.242.207.219 'bash -s -- --dry-run' < deployment/production/ops-check.sh`
- 退出码:0 正常;2 有告警但发不出去(`OPS_ALERT_EMAIL` 未配置或发信失败)。
- 日志 `/var/log/gomuseum-ops-check.log` 没有轮转,每天约 30KB。
- 每周的 `python scripts/ops_report.py` 末尾有「容量」段:各触发指标的现值和阈值、三笔账、最近一次采样时间(cron 停了一眼能看出来)、近 7 天每条告警发了或本该发几封。

## 2. 告警(同一 key 6 小时一封)

| key | 条件 | 处理办法 |
|---|---|---|
| `browse-p95` | 15 分钟内浏览/内容接口 ≥20 个请求且 p95 > 1.0s(不含音频、全量馆包、`/history/recent`) | 先按路径看是哪个接口慢;整体都慢就加 web 进程 |
| `browse-5xx` | ≥20 个请求、≥5 个 5xx、占比 >1%,且分布在 ≥3 个不同分钟 | `docker logs --since 20m gomuseum_prod_backend` 查异常 |
| `recog-p95-{engine}` | vector 1.0s / vector_canvas 4.0s / vector_crops 4.2s 基线;最新 30 条 n≥20 且 p95 > 1.5×基线 | 看 CPU(`docker stats`,同机其他项目也算);持续超线就按阶段 5 拆出 recognizer |
| `host-disk` / `host-mem` | > 80% | 清理备份目录、旧镜像,或者加资源 |
| `host-cpu` | 最近 3 次采样都 > 70% | 用 `docker stats` 找出占 CPU 的容器 |
| `db-conn` | 连接数 > 0.8 × `max_connections` | 按扩容总规则第 1 条调整连接池或 `max_connections` |
| `gen-fail` | 1 小时 ≥5 次失败且 >20%;或 2 小时 ≥3 次失败且一次成功都没有 | docker logs 查 `lazy generation failed`。transient 看上游状态页和额度;internal 是我们的 bug;err_kind 为空 = 请求语言一段都没出,先看 OpenAI |
| `recog-ai-daily` | AI 兜底今天的次数 > max(20, 3 × 前 30 天日均) | 按 user_id 分组看有没有人在刷识别;必要时收紧 nginx 识别限流 |
| `budget-gen-day-80` / `-100` | 今日生成账达到 80% / 100% × `BUDGET_GEN_DAILY_USD` | 阶段 0 不会自动停,只有段数日上限兜底。看是谁在大量生成,再决定调预算还是离线预生成 |
| `budget-gen-month-80` / `-100` | 本月生成账达到 80% / 100% × `BUDGET_GEN_MONTHLY_USD` | 同上 |
| `budget-tts-day` | 语音今日账 ≥ 80% × `ALERT_TTS_DAILY_USD` | 只告警。看未缓存的首播量、有没有人在刷 `/audio` |
| `budget-recog-day` | `ALERT_RECOG_DAILY_USD` > 0 且识别兜底今日账 ≥ 80% × 该值 | 只告警,同 `recog-ai-daily` |
| `price-unknown-{model}` | 今天的 `@app` 用量里有价目表没有的模型(已按最贵价计) | 到官方价目页查单价,在 `.env` 的 `LLM_PRICES` 里只加这一个模型(和代码默认表合并),重启后端 |

账只算在线服务(`@app` 通道),离线脚本是运营者主动花的钱。计日按 UTC。

## 3. 阶段提醒(同一 key 7 天一封)

收到「该进入阶段 N 了」:**照 spec §11 阶段 N 做,先写实施计划经用户批准**。

| key | 条件 | 对应 |
|---|---|---|
| `trigger-t1` | 近 7 天 ≥3 天出现名额满(不含运营预览账号) | 阶段 1:`.env` 两个并发数改 4,重启 web,观察一天日志和连接数 |
| `trigger-t2-conn` | 在用连接峰值 > 40 | 阶段 2 |
| `trigger-t2-tts` | 近 7 天 ≥3 天 TTS 同时合成 ≥4 路 | 阶段 2 |
| `trigger-t2-vq` | 向量检索 n≥50 且 p95 > 0.5s | 阶段 2 |
| `trigger-t2-vectors` | 当前模型向量 > 100,000 | 阶段 2(§5.3 档①) |
| `trigger-vectors-700k` | 当前模型向量 > 700,000 | §5.3 档③ |
| `trigger-t3-concurrency` | `LAZY_CONCURRENCY` ≥4 后,近 7 天 ≥3 天全站同时生成 ≥4 件 | 阶段 3 |
| `trigger-t3-failures` | 近 7 天失败或中断 > 5 次 | 阶段 3 |
| `trigger-t5-cpu` | 最近 3 次采样 CPU 均值 > 50% | 阶段 5 |
| `trigger-t5-recog` | 5 分钟识别 ≥20 次,同时浏览 p95 > 1.0s | 阶段 5 |
| `trigger-ip-cap-{tier}` | 近 7 天这一档 IP 额度被用满过 | §4.2:评估要不要放宽 |
| `trigger-search-engine` | 作品 > 150,000 | §5.4:换外部搜索引擎 |

## 4. 扩容总规则(spec §2)

1. 所有进程的连接上限之和 ≤ 0.8 × `max_connections`(§5.1)。
2. 同时在途的大模型请求数 < 外部每分钟上限 ÷ 每路每分钟调用次数。共用同一个账户的调用方都要算进去,包括离线脚本和 staging。
3. Google TTS 两条限制:prod 和 staging 所有 web 进程的 `TTS_CONCURRENCY` 之和 < 100 路并发;每分钟请求数 < **200**(Chirp3-HD 的限额,backlog 10-20 探测)。
4. 所有调用 Wikidata / Wikimedia 的进程,`WIKIDATA_CONCURRENCY` 之和 ≤ 4。
5. 这台 VPS 还跑着 deepmeeting 的 prod/staging(web + worker)和公司官网。核数、内存按扣掉它们之后的余量算。

## 5. 手工配置的现状

| 项 | 在哪改 | 回滚 |
|---|---|---|
| nginx 两个限流区(总区 50r/s burst 100;识别区 2r/s burst 50) | 宿主机上 api.gomuseum.app 的站点文件(改前用 `nginx -T 2>/dev/null \| grep -n 'configuration file\|gomuseum_api'` 定位),模板 `deployment/production/nginx-api.gomuseum.app.conf` | 改前 `cp` 一份 `.bak`;回滚 = 拷回、`nginx -t`、`systemctl reload nginx` |
| staging 资源上限(合计 2 核 4G) | VPS `/opt/gomuseum/staging/docker-compose.yml`,仓库 `deployment/staging/docker-compose.yml` | 删掉 `cpus` / `mem_limit` 几行,`up -d <服务>`。⚠️ CPU 受限后 staging 的识别延迟和 prod 不可比:ORT 按宿主机 8 核开线程 |
| prod `max_connections=400` | `deployment/production/docker-compose.yml` 里 postgres 的 `command` | 只能在维护窗口里 `up -d gomuseum_postgres`;回滚 = 删掉 `command`、同样在窗口里 `up -d` |
| 外部探活 | UptimeRobot 关键词监控(用户注册) | 在 UptimeRobot 里暂停 |
| `deployment/production/deploy.sh` | **不要用**:它把仓库 compose 同步到 VPS 并对全部服务 `up -d`,会在窗口外重建 postgres | 日常部署走 CD;compose 改了服务参数,只在维护窗口里单独 `up -d <服务>` |

## 6. 两条要重标的线(R7)

- `ALERT_TTS_DAILY_USD=2`:今天的量约 $0.5/天,能当异常线用;到 200 人规模几乎天天响。**阶段 2 之前按实际量重标。**
- `ALERT_RECOG_DAILY_USD=0`(关闭):上 prod 7 天后,用真实记账重定。在那之前靠次数告警 `recog-ai-daily` 守。

## 7. 提前解除某条告警的限频

限频看 `app_events` 里的 `ops_alert` 行。问题修好后想让同一 key 立刻能再报,删掉它最近的记录。**这是 prod 写操作,先请用户批准:**

```sql
DELETE FROM app_events
WHERE name = 'ops_alert' AND props->>'key' = 'host-disk'
  AND created_at > now() - interval '7 days';
```
