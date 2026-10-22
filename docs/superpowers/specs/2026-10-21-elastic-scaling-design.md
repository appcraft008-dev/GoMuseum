# 弹性可扩容架构 设计

- 日期：2026-10-21
- 状态：v9（10-22）。依据第八轮评审（对照最新 staging 代码与 prod 只读数据）修订，待用户审阅
- 来源：10-20 staging 多用户压测（backlog #1041），以及 10-20/21 brainstorm 的逐段确认
- 评审历史：见 §13。共 8 轮：第 1–6 轮逐段评审，第 7 轮全新上下文全量评审，第 8 轮重点查「会不会影响已有用户」

## 0. 目标与原则

### 0.1 原则（用户定）

> 软件架构不能成为性能瓶颈。瓶颈只能出现在三个地方：VPS 硬件（CPU / 内存 / 硬盘）、第三方接口的速率限制、成本预算。

据此提出三条可以检验的要求：

1. **加资源就加容量，不改代码**：加进程、加容器、加机器都只改配置。
2. **所有容量数字都是配置项**：写在 `.env` 里，重启后生效。
3. **不上大公司架构**：不引入 Kubernetes、消息中间件、Prometheus/Grafana。

### 0.2 性能目标（验收标准）

| 场景 | 目标 |
|---|---|
| 设计容量 | 全部馆合计 **200 人同时使用**；扩到 1000 人以上只靠加机器（PostgreSQL 单点的处理见 §9.5） |
| 浏览、搜索、内容接口（不含长连接） | p95 ≤ 1 秒 |
| 识别：向量判定各路径 | 单人使用时不比今天的基线慢；200 人时各路径 p95 ≤ 基线 × 1.5（用户 10-22 定）。基线见下表 |
| 识别：AI 兜底路径 | 单独统计（要调用外部视觉模型，超时为 30 秒），在 §7 的报告里跟踪 |
| 首屏（空作品第一次打开，到本语言讲解出现） | 高峰时比单人多 ≤ 10 秒。单人首屏本身的时长归「单人首屏提速」专题 |
| 其余 9 门语言补齐 | 平常 ≤ 5 分钟；高峰时允许积压，高峰过后 30 分钟内清空（用户 10-21 定 A）。预算停止期间不计 |
| 生成中，另一种语言的用户打开同一件 | ≤ 60 秒（英文一就绪就开始翻译，§3.3；上线后实测） |
| 首次播放（现场合成） | 50 人同时首播时，首包 p95 ≤ 3 秒 |
| 第二个人听同一段正在合成的音频 | ≤ 3 秒开始播放（同一段最多 2 路合成，§6） |
| 部署 / 重启 | 不丢任务，不留半成品。后端发版时懒生成最多暂停约 3 分钟（§11）；浏览只受 web 重启本身影响，不会因为 worker 停得更久 |
| 内容生成成本 | 每天 $30、每月 $300（配置项）。到 80% 告警，到 100% 停止生成新内容 |
| 语音、识别兜底成本 | 各设一条告警线，只告警，不停服务（用户 10-21 定） |

**识别延迟基线**（prod 10-08～10-22，推理用满 8 核，几乎没有并发）：

| 路径 | 次数 | p50 | p95 |
|---|---|---|---|
| 向量直判 | 111 | 0.25 秒 | 2.0 秒 |
| 画框 | 344 | 1.6 秒 | 4.0 秒 |
| 裁剪 | 185 | 2.3 秒 | 4.1 秒 |
| AI 兜底 | 344 | 6.0 秒 | 12.2 秒 |

画框、裁剪两步各自 p50 约 1 秒，是推理最重的部分；约 77% 的识别会走到其中至少一步。v8 的「向量路径 p95 ≤ 3 秒」今天在几乎零负载下就达不到，所以改为对标基线。

**容量与预算的关系（用户 10-21 定 A）**

- 开放的 4 个馆中，有图但还没有内容的作品共 14,242 件，占有图作品的 93%（10-21 查询）。
- 近一周 prod 有 471 次打开讲解，其中打开时还没有内容的占 **15.5%**（这就是 p_stub，10-21 实测）。样本说明：共 30 个查看者，其中一个测试账号贡献了 292 次。
- 按 200 人高峰估算，每天 $30 的预算会在 1–2 小时内用完（§9.3；新模型单价尚未核对）。

因此，**懒生成只用来兜住长尾，热门作品要靠离线提前生成**。上线后看 §7 的「当日因预算被拒的作品数」，再决定是调高预算，还是离线批量生成那些常被拒的作品。离线批量生成另开专题。

### 0.3 不在本设计范围内

- 单人首屏提速、离线批量预生成：另开专题。
- 识别 ONNX 推理降本（int8、减少裁剪、提前退出）：这是 1000 人以上规模时识别容量的主要杠杆（§9.1），需要先跑评测集，另开专题。
- 离线 CLI 脚本：不进队列，行为不变。会写作者行的那几个脚本有一条运维约定，见 §3.3 W12。
- VoxCPM2 替换懒生成音频：不受影响。`audio_ingest_cli` 直接写 ORM，不经过 `persist_section_audio`。
- 缺图补图：**留在 web 进程里，不进队列**。它是幂等的小下载，也不调用大模型；放进队列只会多出一类任务和一组特例处理。
- 老版 App 拉取 5MB 全量馆包：§7 统计时剔除。

## 1. 现状与已查实的瓶颈

| # | 瓶颈 | 证据 | 违反了什么 |
|---|---|---|---|
| B1 | 懒生成跑在 web 进程的后台线程里；并发数写死在进程内（`_SEM=2`、`_FANOUT_SEM=2`）；槽位满了就直接放弃 | lazy.py；压测 C 里 20 件只补齐了 10 件 | 加机器不增加生成容量；重启会丢任务 |
| B1b | `generate_object` 只要已有任何一段已发布的英文，就整件跳过；而英文主讲解在约 10 秒时就已落库 | pipeline.py `generate_object` 开头；`persist_gated_sections` | 中途失败后无法续跑，只剩半成品 |
| B2 | 每个进程连接池为 20+40，prod 的 `max_connections=100`；流式语音在整段合成期间一直占着 `get_db` 的会话（FastAPI 0.142 实测）；记账每次都另开会话 | database.py；评审实测 | 加进程后整站会报「连接数过多」；记账会静默丢失 |
| B3 | 向量检索里的 Python 循环耗时随向量数线性增长；一次识别最多要查 13 遍 | vector_index.py；本机实测 | 收录作品越多，识别越慢 |
| B4 | 识别和浏览在同一个进程里抢 CPU；ONNX 没有设线程数 | 压测 B：CPU 779% | 识别一忙，浏览跟着变慢 |
| B5 | TTS 并发写死为 8；音频锁放在 `attributes` JSON 里读改写，会和其他写入互相覆盖；流式和非流式 `/audio` 两条路径靠这把锁互相看见 | tts_service.py、lazy_audio.py、streaming_audio.py | 达不到 50 路首播，也达不到「第二人 3 秒」 |
| B6 | 每 IP 每天 300 次的额度对正式账号也生效 | lazy.py | 同一 WiFi 下的游客互相挤占 |
| B7 | nginx 对全站限制每 IP 10r/s，这同时也是识别 AI 兜底唯一的量的上限 | nginx 配置注释 | 共用 WiFi 时会误伤正常用户 |
| B8 | 价目表只有旧模型；识别兜底把 tokens 丢了，没有记账 | llm_cost_report.py、recognition/vision.py | 无法设成本上限 |
| B9 | slowapi 的计数存在进程内 | rate_limit.py | 进程越多，限流越松 |
| B10 | 启动命令里跑迁移；容器名和端口写死；每个进程都执行 `init_db` | compose | 多容器时会同时跑迁移 |
| B11 | **CD 只同步 `backend/` 目录**，compose 和 nginx 都是手工改；每次 CD 都会在 VPS 现有的 compose 目录执行 `up -d --build` | deploy.yml:15-16、77-95 | 新增容器、改数据库参数都需要手工配合，发布顺序一错就会停摆 |
| B12 | 大模型调用没有显式超时（SDK 默认 600 秒，外加 2 次重试） | openai_models、content_enricher | 一次挂住的调用会占住一个线程几十分钟 |
| B13 | 没有容量监控 | — | 不知道什么时候该加机器 |
| B14 | 生成管线的同一个会话从第一次查库开到落库提交，中间穿插抓取和大模型调用，事务一直开着；prod `lock_timeout=0`；web 启动时先跑迁移 | pipeline.py `generate_object`；pg_settings；compose `command` | worker 常驻后，带改表迁移的发版要等它的事务全部结束，这段时间新 web 起不来，整站 502（第八轮） |
| B15 | `/audio` 是同步接口，合成期间一直占着线程池；流式接口在事件循环里同步查库 | museums.py `object_audio`、`object_audio_stream` | 问答音频一多，浏览抢不到线程；连接池一耗尽，整个进程卡 30 秒 |

已经可以扩容、不用改的部分：

- 识别锁在 Redis 里。
- 索引是每个进程各一份副本。
- `llm_usage` 是原子累加。
- nginx 日志已带 `rt=`。
- `SKIP LOCKED` 领取不会重复（已实测）。
- `Artist` 的写入点只有 §3.3 列出的这些（第七轮全仓库核实过）。

## 2. 总体架构

```
             ┌── 识别类请求 ──→ recognizer 容器
用户 → nginx ┤
             └── 其他请求 ───→ web 容器（浏览、内容、语音流、补图）
                                    │ 写任务
                                    ▼
                        PostgreSQL 任务表 generation_jobs
                                    ▲ 领任务
                                    │
                        worker 容器（生成进程）
```

| 容器 | 负责 | 启动 | 扩容 |
|---|---|---|---|
| web | 浏览、搜索、内容、语音流、补图 | `alembic upgrade head && uvicorn …`，**只有它跑迁移** | 同机加 `WEB_WORKERS`；跨机在 upstream 加一台 |
| recognizer | 识别接口 | `uvicorn …`，端口 `127.0.0.1:8102`，`depends_on: web: service_healthy`，`cpu_shares` 低于 web（§5.2） | 同机加 `RECOG_WORKERS`；跨机在 upstream 加一台 |
| worker | 领任务、调 AI、写回 | `python -m app.workers.generation`，不映射端口，不写死容器名，`depends_on: web: service_healthy`，`restart: always`，`stop_grace_period: 60s`，设 `mem_limit` | 加线程；或用 `--scale` / 跨机多开 |

- `init_db` 只在 web 里执行，由 `INIT_DB_ON_START` 控制。
- 部署脚本和 cron 里写死的容器名，全部改成按 compose 服务名查找。

**共享状态只放两个地方：**

- PostgreSQL：必须可靠的数据，包括任务、内容、账本。
- Redis：丢了只会降级的数据，包括防滥用计数、限流计数、识别锁、音频合成槽位、记账失败计数。

**扩容总规则**（写进运维文档，告警邮件里会引用）：

1. 所有进程的连接上限之和 ≤ 0.8 × `max_connections`（§5.1）。
2. 同时在途的大模型请求数 < 外部每分钟上限 ÷ 每路每分钟调用次数。共用同一个账户的调用方都要算进去，包括离线脚本和 staging。
3. Google TTS 两条限制：
   - prod 和 staging 所有 web 进程的 `TTS_CONCURRENCY` 之和 < 100 路并发；
   - 每分钟请求数 < **200**（Chirp3-HD 的限额，backlog 10-20 探测）。
4. 所有调用 Wikidata / Wikimedia 的进程，`WIKIDATA_CONCURRENCY` 之和 ≤ 4。
5. 这台 VPS 还跑着 deepmeeting 的 prod/staging（web + worker）和公司官网。核数、内存按扣掉它们之后的余量算。

## 3. 生成任务队列

### 3.1 表结构

新建表 `generation_jobs`（alembic 迁移，纯加法）：

| 列 | 类型 | 说明 |
|---|---|---|
| id | bigserial PK | |
| kind | varchar(16) | `first_screen` / `translate` |
| qid | varchar(32) | |
| language | varchar(16) | `translate` 填目标语言；`first_screen` 固定为空串 |
| lang_priority | varchar(16) null | 只有 first_screen 用：第一个请求者的语言 |
| priority | smallint | 10 = 有人在等；0 = 没人在等 |
| priority_at | timestamptz **default now()** | 优先级最后一次被设置或抬高的时间 |
| status | varchar(12) | `queued` / `running` / `done` / `failed` / `cancelled` |
| attempts | smallint default 0 | |
| run_after | timestamptz default now() | 失败重试时的退避时间 |
| lease_until | timestamptz null | |
| worker_id | varchar(64) null | |
| created_at / started_at / finished_at | timestamptz | |
| last_error | text null | 截断到 2000 字 |
| error_kind | varchar(12) null | 失败类别：`transient`（超时、429、5xx、连接错误）/ `internal`（其余），决定冷却时长 |

索引：

- `uq_active_job (kind, qid, language) WHERE status IN ('queued','running')`：部分唯一索引，保证同一件作品同时只有一个首屏任务。
- `ix_queued (priority DESC, created_at) WHERE status='queued'`：claim 用的部分索引。第七轮实测，优先级 10 的领取从 92 ms 降到 0.9 ms。
- `ix_running_lease (lease_until) WHERE status='running'`：清理线程用。
- `(kind, qid, language, finished_at)`：冷却用。

**有效优先级**：priority=10，且 `priority_at` 在 10 分钟以内，才算「有人在等」，由高优先级线程领取；其余任务由低优先级线程领取。降级直接在 claim 的条件里算出来，不用清理线程去改数据。

### 3.2 接口（`app/services/jobs.py`）

所有函数都接收调用方传入的 `db`，**函数内部不提交**。

**`enqueue(db, kind, qid, language, priority, lang_priority=None) -> (Job | None, inserted)`**

按下面的顺序判断：

1. **语言白名单**：`language` 必须在该馆的语言集合里，否则返回 `(None, False)`。原 `maybe_trigger` 的环境守卫保留，只在 staging/production 生效。
2. **先读**：调用 `active_job`。
   - 已有 running 的任务：不写库，直接返回。给正在跑的任务抬优先级没有意义。
   - 已有 queued 的任务，且有效优先级不低于本次请求：不写库，直接返回。
3. **不和首屏重复**：`translate` 的目标语言等于本件活跃首屏的 `lang_priority` 时，返回那个首屏任务，不入队。首屏完成时会先把自己的行置为 done，再为其余语言入队，所以那一步不会触发这条规则。
4. **没有依赖就不入队**：`translate` 任务对应的作品，既没有活跃的首屏，`content_status` 也不是 `ready`（即没有任何已发布的英文段，见 pipeline.py：`ready if pub_en > 0`），返回 `(None, False)`。
5. **预算**：只有用户触发的入队（priority 10）在内容生成预算耗尽时返回 `daily_cap`。首屏完成后补的入队照常写入，什么时候执行由 claim 决定。
6. **冷却**（用户 10-22 定：按错误类型区分），看本件同类任务最近一次结束的记录：
   - 失败且 `error_kind='transient'`：15 分钟内不再入队（`JOB_COOLDOWN_TRANSIENT_MIN`）。上游故障恢复后，用户最多等 15 分钟就能重新生成；
   - 失败且 `error_kind='internal'`：6 小时（`JOB_COOLDOWN_INTERNAL_H`）；
   - 由内容接口触发的续跑（优先级 0 的 first_screen）：**不论成败**，6 小时内结束过就不再入队（`JOB_RESUME_COOLDOWN_H`）；
   - 冷却期间返回 `(None, False)`。行为变化：现在失败后点「重试」立即重来，改后要等冷却结束。
7. **写入**：

```sql
INSERT INTO generation_jobs (kind, qid, language, lang_priority, priority, status)
VALUES (:kind, :qid, :lang, :lp, :prio, 'queued')
ON CONFLICT (kind, qid, language) WHERE status IN ('queued','running')
DO UPDATE SET
  priority    = GREATEST(generation_jobs.priority, EXCLUDED.priority),
  priority_at = CASE WHEN EXCLUDED.priority >= generation_jobs.priority THEN now()
                     ELSE generation_jobs.priority_at END
RETURNING *, (xmax = 0) AS inserted;
```

**`claim(db, worker_id, high: bool) -> Job | None`**

高、低两档用**两条独立的 SQL**。第八轮：v8 用参数化的 `:high = (…)`，规划器没法把它当成索引范围条件，高档线程在「没有高优先级任务、低优先级积压很多」时每次都要扫完全部 queued 行。预算停止时 worker 直接不调用 claim（预算状态每 10 秒算一次，缓存在进程内）。

高档：

```sql
UPDATE generation_jobs j SET status='running', attempts=j.attempts+1,
       lease_until=now()+interval '2 min', worker_id=:w, started_at=now()
WHERE j.id = (
  SELECT c.id FROM generation_jobs c
  WHERE c.status='queued' AND c.priority >= 10
    AND c.priority_at >= now() - interval '10 min'
    AND c.run_after <= now()
  ORDER BY c.priority DESC, c.created_at
  LIMIT 1 FOR UPDATE SKIP LOCKED)
RETURNING j.*;
```

低档：

```sql
UPDATE generation_jobs j SET status='running', attempts=j.attempts+1,
       lease_until=now()+interval '2 min', worker_id=:w, started_at=now()
WHERE j.id = (
  SELECT c.id FROM generation_jobs c
  WHERE c.status='queued' AND c.run_after <= now()
    AND NOT (c.priority >= 10 AND c.priority_at >= now() - interval '10 min')
    -- 优先级 0 的补齐翻译要等本件首屏整件完成
    AND NOT (c.kind='translate' AND c.priority < 10 AND EXISTS (
          SELECT 1 FROM generation_jobs f
          WHERE f.qid=c.qid AND f.kind='first_screen' AND f.status IN ('queued','running')))
  ORDER BY c.priority DESC, c.created_at
  LIMIT 1 FOR UPDATE SKIP LOCKED)
RETURNING j.*;
```

- 两条都只扫 `status='queued'`，走部分索引；高档的 `priority >= 10` 是索引范围条件。
- 依赖检查只查 `generation_jobs` 这张小表，不扫内容段表。第七轮实测，原来的写法每次都要对整张段表做一次约 74 ms 的哈希。
- 高优先级翻译**不保证英文已就绪**：enqueue 第 4 步只保证本件有活跃首屏。所以翻译任务领到后，先查本件有没有已发布的英文主讲解；没有就置回 queued，`run_after = now() + 10s`，`attempts` 减 1（不计次数）。

**清理线程**（每个 worker 进程一个，每 30 秒执行一次）：

- 租约已过期的 running 任务：`attempts < 3` 时置回 `queued`，并设 `run_after = now() + 30s × 2^attempts`；否则置为 `failed`。
- 孤儿翻译任务（queued、本件没有活跃首屏、`content_status != 'ready'`，判断条件同 enqueue 第 4 步）：置为 `cancelled`。
- 每小时删除一次 7 天前已完成的任务。

**`heartbeat`**：每 30 秒续一次租，条件为 `worker_id=:w AND status='running'`。线程挂住的问题由 §3.4 的显式超时兜底，不另设最长运行时间，因为停止续租只会让同一个任务被两个线程跑。

**`still_mine`**：只用于翻译任务，在每段之间检查。首屏任务中途不中止，由续跑来处理。

**`finish(db, job_id, worker_id, ok, error=None, retry=True)`**：只在 `worker_id=:w AND status='running'` 时生效。

- 翻译任务：
  - 开始时记下本件**已发布**英文段的段名集合 `seen`。
  - 有任何一段翻译报错（逐段 try/except 跳过）：整个任务按**失败**处理，走下面的重试和冷却；已经翻好的段照常保留。
  - 全部成功时，再算一次「现在已发布、不在 `seen` 里、本语言还没有行」的英文段。有就置回 `queued`（`attempts` 不清零）；没有就置为 `done`。这样首屏期间陆续发布的深度段也会被翻译。
  - 每次回队列都必须有新发布的英文段，所以回队列次数受英文段数封顶，不会循环。第八轮：v8 写的「任何英文段（不论状态）」会把被闸挡下的英文段也算成缺口，而翻译只读已发布段，prod 上 1,269 条被挡英文段只有 30 条有法语行，翻译任务会永远回队列；「`attempts` 清零」会让一段每次都报错的翻译变成热循环，直到烧光当天预算。
- 首屏任务成功：置为 `done`，同一事务里为其余语言入队（§3.3）。
- 失败：记 `error_kind`。`retry=True` 且 `attempts < 3` 时，置回 `queued`，`run_after` 按指数退避；否则置为 `failed`，进入冷却（enqueue 第 6 步）。

**`release`**：部署停机时调用，执行 `status='queued', attempts=attempts-1, worker_id=NULL`。

### 3.3 哪些工作进队列

| 工作 | 原来 | 现在 | 优先级 |
|---|---|---|---|
| 首屏生成 | BackgroundTasks → `maybe_trigger` | `enqueue(first_screen, qid, '', 10, lang_priority=请求语言)` | 10 |
| **续跑**：作品已 ready，但有缺行（不论状态，§3.4） | 不会被触发 | 内容接口发现缺行时，执行 `enqueue(first_screen, …, 0)`；续跑任务不论成败，结束后 6 小时内不再入队（enqueue 第 6 步） | 0 |
| 首屏期间，另一种语言的用户打开 | 等首屏完成后插队 | `enqueue(translate, qid, 他的语言, 10)`，英文一就绪就能执行 | 10 |
| 已有作品缺请求语言 | BackgroundTasks | `enqueue(translate, qid, lang, 10)` | 10 |
| 首屏完成后补齐其余语言 | 首屏线程里接着跑 fanout | jobs 层单独开一个事务：**先把首屏行置为 done**，再对**仍有缺口的语言**执行 `enqueue(translate, qid, lang, 0)`。缺口判定同 `_fanout_langs`，也包括 `lang_priority` 那门（它可能在首屏里被闸挡下或失败）。**`lang_priority` 那门用优先级 10**：请求者多半还在页面上，排在优先级 0 后面会让他一直看到转圈 | 0（`lang_priority` 那门为 10） |
| 补图 | web 后台线程 | **不变** | — |
| 语音流、索引重建 | web 进程 | **不变** | — |

**作者行等共享实体（纪律 37）**

新增 **`locked_artist(db, qid) -> Artist`**，放在 `app/services/artist_write.py`：

- 新建作者用 `insert(Artist).on_conflict_do_nothing()`，按数据库方言分支处理，写法同 `llm_usage.py`。
- 加锁重读用 `db.query(Artist).filter_by(qid=qid).with_for_update().populate_existing().one()`。`populate_existing` 会用库里的最新值覆盖会话缓存。第六轮已实测：这样处理后，音频损失闸比对的「旧值」就是锁定后库里的最新值。
- 这个函数不提交。调用方的约定是：
  - 拿锁时 `db.dirty` 必须为空（用断言检查）；
  - 拿锁之后不发起任何网络调用；
  - 补缺写完后立即提交。
- 持锁时间是毫秒级。

**调用方固定三步：**

1. 不加锁，先读出快照（包括 `bio_en`）。
2. 在锁外算出所有候选值 `{字段: {语言: 值}}`。原来的作者块是「读、判断、联网、赋值」交替进行的，要整体改成这个形状：**只加一次锁、只提交一次**。
3. 加锁，对重读出来的值只补缺，然后提交。**前置条件**：凡是从 `bio_en` 翻译出来的值，只有当 `art.bio["en"] == 快照 bio_en` 时才写入，否则整批丢弃。

判断「缺失」时沿用现有的真值语义：

- 字符串：空串或 None 算缺失。
- 列表：空列表或 None 算缺失。
- dict 类字段：先确认是 dict；JSON null 按空 dict 处理。

`fill_artist_i18n_facts` 拆成两个入口：

- 补缺用纯函数 `compute_artist_i18n_facts(snapshot, langs, translator) -> {字段: {语言: 值}}`；
- `--refresh-langs` 显式刷新仍保留原来的 ORM 入口，行为不变，受音频损失闸管控。

**写入点清单**（第七轮已在全仓库核实，没有其他写 `artists` 的地方）：

| # | 位置 | 处理 |
|---|---|---|
| W1 | pipeline 中新建作者 | 改用 `locked_artist`；删除 `db.add(Artist(...))` |
| W2–W5 | `name_en`、`name_zh`、`birth`、`death`、`nationality`、`notable_works`（JSONB 列表：SQL NULL、JSON null、`[]` 都算缺失） | 加锁后补缺 |
| W4 | `name_i18n = _fill_i18n(...)` | 锁外算出候选，加锁后只合并缺失的语言 |
| W6/W7 | 作者简介英文是坏值时，重写并覆盖 target_langs 各语言，同时清掉对应音频 | **沿用现有行为**。在锁外生成新内容。加锁后，如果英文仍是那条坏值（compare-and-set），就用 ORM 覆盖，并清掉 `bio_audio`/`bio_audio_engine`，这一步会经过音频损失闸：脚本进程没有额度时会被拦下；web/worker 只记录，写进 `audio_invalidations`，孤儿 GC 会保留这些文件。已知并接受：这一步搬进 worker 后，一次首屏可能清掉多门语言的作者音频 |
| W6′ | 作者简介英文缺失（不是坏值） | 走补缺 |
| W8 | `nationality_i18n`、`notable_works_i18n` | `compute_…` 计算后补缺；refresh 模式保持不变 |
| W9 | pipeline 补写作者简介的其他语言 | 在锁外翻译，加锁后补缺，带 `bio_en` 前置条件 |
| W10 | `backfill.fill_artist_bio` | 同 W9。三个调用方（`_backfill_bios`、lazy fanout、`translate_object_language` 的调用方）都是调用后立即 commit，第六轮已核实 |
| W11 | `lazy_audio` 写作者简介音频 | 合成完成后用 `locked_artist` 重读，依次判断：① 合成用的文本 ≠ 重读出的 `art.bio[lang]`：丢弃本次结果，返回 `(None, "busy")`；② 已有别人写入的 key：返回那个已有的 key；③ 以上都不是：只合并这门语言的 key。这样不会把一个没人引用的 URL 交给用户 |
| W12 | 离线脚本整块写入：`backfill_display_names`、`batch_names.py`、`scripts/fix_hant_script.py`、`scripts/fix_title_i18n.py` | 不在本设计范围内（走 ORM，音频损失闸能看见）。**残余风险**：和在线任务并发时会丢更新。**运维约定**：跑这些脚本之前先 `docker compose stop worker`，写进脚本 docstring 和运维文档 |
| W13 | `audio_ingest_cli`、`rescan_language` 写 `bio_audio` | 同 W12 |

**提交边界**：作者块排在 guide 落库之后（`persist_gated_sections` 内部会提交一次）。作者块提交时会带上之前已 flush 的改动，这没有问题，但不能有 dirty 对象。

### 3.4 worker 进程

**启动时：**

- `llm_usage.ORIGIN_SUFFIX="@app"`；
- 调用 `audio_guard.set_record_only()`；
- 显式设置线程池大小（§5.1）。

**线程：**

- `WORKER_HIGH_THREADS=24`：领有效优先级为 10 的任务。
- `WORKER_LOW_THREADS=60`：领其余任务。
- 这两个默认值由 §9.2 按实测的 p_stub 算出。
- 空闲时每次 sleep 1 秒。

**大模型调用的显式超时与 429：**

- `chat()` 给生成类通道设 `LLM_TIMEOUT_S=90`（每次尝试），配合 SDK 的 `max_retries=2`。
- 429 按 `Retry-After` 等待，在 `chat()` 里统一处理，每次记一条 `event_log`。
- 管线内部有 `except Exception`，不能让它吞掉 429 后把薄内容落库。429 在 `chat()` 层重试完仍然失败时，抛一个专门的异常；管线遇到这个异常不落库，任务直接失败，等重试。

**领到首屏任务时：**

1. 先以数据库为准计算缺口，**不看 `content_status`**。缺口一律按「**缺行**」判断，被闸挡下（needs_review）的行也算有。用户 10-22 定：needs_review 是最终结果，懒生成不自动重试，与 lazy.py `_has_missing_section` 的现有规则一致。以下任一项成立就算有缺口：
   - 英文 guide 没有行；
   - 本类别的基础段缺行；
   - 英文问答一行都没有；
   - `lang_priority` 那门有英文已发布段还没有行。
2. 没有缺口：直接 `finish(done)`。
3. 有缺口：调用 `generate_object(…, resume=True)`。

**续跑模式（resume）：**

| 步骤 | 判断「已完成」的依据 | resume 时怎么做 |
|---|---|---|
| 入口 | — | 跳过开头「已有已发布英文 → skipped」的早退 |
| 装载状态 | — | `en_published` 从库里装载**全部**已发布的英文段 |
| 取数 | `attributes` 里已有对应键 | `f_lab`、`f_amat` 只在缺 `title_i18n` 或作者材料键时才抓取（现在是无条件抓取） |
| 英文 guide | `en/guide` 有行 | 已发布就从库里读出 `guide_text` 作为去重锚；needs_review 不重写 |
| 请求语言 guide | 有行 | 已有就跳过 |
| 作者块 | — | 按 §3.3 的三步执行 |
| canonical 深度段 | 各段已有行（不论状态） | 只把缺的段名作为 `sections` 传给 `generate_canonical`（不用改接口）；已有的段不经过 `_upsert_section`。已知代价：缺的段看不到已有段的内容，去重效果会弱一些 |
| 翻译 | 该语言该段已发布 | 调用 `translate_object_language(include_bio=False)`。**在函数内部的 `for code in ordered` 循环里逐段 try/except**（在外层包一层做不到逐段容错） |
| 问答 | 该语言有问答行（不论状态） | 英文问答一行都没有时才生成；再跑翻译（翻译时会顺带产出请求语言的问答）。只为没有问答行的语言生成，因为 `persist_suggested_questions` 会整组删掉再插入 |

- 翻译这一步沿用 `translate_object_language`：目标语言里被闸挡下的段会再翻一次（#1036「被挡的段重试一次」）。续跑结束后 6 小时内不会再触发，所以有上限。
- 存量里真正缺行的半成品，在内容接口发现缺口时会以优先级 0 自动入队（§3.3），也可以用运维脚本批量入队。prod 10-22：1,096 件已有内容的作品中，英文段少于 5 行的有 108 件（其中一部分是类别本来就段少）；英文问答全被挡的 103 件、英文主讲解被挡的 3 件**不会**触发续跑。

**异常处理**：捕获 BaseException，把任务置为 `failed(retry=False)` 并告警，线程继续运行。失败时按异常类型记 `error_kind`：超时、429 重试用尽、5xx、连接错误为 `transient`，其余为 `internal`。

**收到 SIGTERM**（第八轮改，配合 CD，见 §11）：

1. 停止领新任务。
2. 翻译任务在段与段之间检查到停止信号，就 release。
3. 首屏任务**不等它跑完**。compose 设 `stop_grace_period: 60s`，到时进程被杀；租约最迟 2 分钟后过期，由新 worker 续跑接手，已落库的段不会重做。

v8 的「首屏跑完再退（5 分钟宽限）」和「先扩到 2 个再缩回」都删掉：CD 每次只执行一条 `up`，做不到滚动；5 分钟宽限会让每次发版多等最多 5 分钟，期间没人领任务。

**回滚开关 `LAZY_EXECUTOR=queue|inprocess`：**

- **代码里的默认值是 `inprocess`**（第七轮 A1：代码合入就会自动部署，而 worker 需要手工上线）。prod 手工上线 worker 之后，再把 `.env` 改成 `queue`。`.env` 在 `backend/` 之外，CD 不会覆盖它。
- inprocess 模式下：内容接口走原来的 `maybe_trigger`；worker 不领任务；queued 状态的任务都置为 `cancelled`（不计入冷却）。
- 已知小代价：切换那一刻，已在 running 的队列任务可能和 web 内重新触发的同一件重复生成一次。
- 两种模式都要测。观察两周后删除 inprocess 路径。
- **开关只切换执行方式，不回滚管线改动。** 管线改动（续跑、作者行加锁、超时与 429、翻译逐段容错）在 P2a 单独上线、单独观察（用户 10-22 定拆分，§11）；它们出问题时回滚代码。

### 3.5 被替换的旧机制

| 旧 | 新 |
|---|---|
| `lazy_lock_at` | 部分唯一索引 + 租约 |
| fanout 标记、`_SEM`、`_FANOUT_SEM` | 任务表 + 线程数配置 |
| 槽位满就放弃 | 排队 |
| 按段数计的上限 | 按美元计的预算 |
| `attributes.audio_locks`（所有音频路径） | Redis 合成槽位（§6） |

本节吸收了 backlog 待定项 (a)。

### 3.6 内容接口契约（只做加法）

**`generating`：语义不变。** 只要存在与「本作品 + 本语言」相关的 queued 或 running 任务（本作品的 first_screen，或本语言的 translate），它就是 true。

- 必须等这门语言整门翻完，才变成 false。
- 首屏完成和补齐入队在同一个事务里，中间不会出现空窗。
- 补齐只给有缺口的语言入队，所以内容已经完整的语言，不会因为一个排在后面的优先级 0 任务而一直显示 true（第七轮 B4）。
- 续跑只由「缺行」触发（§3.4），所以 `generating=true` 时一定有新内容要出现。已有内容、只是部分段被闸挡下的作品不会入队，打开时不转圈。第八轮：v8 按「未发布」判断，prod 上 106 件这类作品每次打开都会转圈，并重新生成一次。

预算停止期间：排队中、还没开跑的任务返回 `generating=false`，并带 `unavailable_reason="daily_cap"`。失败或冷却期间返回 `generating=false`，App 显示「待完善」。

**新增字段 `queue_position`、`eta_seconds`**：放在 P2c，和前端的排队提示一起排期。

- `queue_position`：排在我前面的同档 queued 任务数。
- `eta_seconds = ceil((位置+1) × 近 1 小时同类任务平均耗时 ÷ max(1, 同档 running 任务数))`。没有历史数据时，平均耗时按 20 秒算。

## 4. 成本上限与限流

### 4.1 三笔账

**补记账**：recognition/vision.py 要保留 `chat()` 返回的用量，记到 `recognition` / `label` 通道下。这两个通道名不能改，因为 `LLM_CHANNEL_MODELS` 靠它们选模型。

**价目表**：`LLM_PRICES` 作为配置项（JSON）。

- 新模型的单价在实施时到官方价目页核对，不凭记忆填。
- 遇到价目表里没有的模型，按表里最贵的价格计算，并告警。

| 账 | 计入的通道（只计 `@app`） | 到 100% 时 | 配置 |
|---|---|---|---|
| 内容生成 | generate、gate、translate、qa、vision | 停止：claim 不再领生成任务，用户触发的 enqueue 返回 `daily_cap` | `BUDGET_GEN_DAILY_USD=30`、`BUDGET_GEN_MONTHLY_USD=300` |
| 语音 | tts | 只告警 | `ALERT_TTS_DAILY_USD` |
| 识别兜底 | recognition、label | 只告警 | `ALERT_RECOG_DAILY_USD` |

- 三笔账都在 `BUDGET_ALERT_RATIO=0.8` 时告警。
- 统一按 UTC 计日。容器时区本来就是 UTC，`llm_usage` 的 `date.today()` 就是 UTC 日期，不用改（第八轮核实）。
- 不做缓存。
- 已知文案偏差：月度预算耗尽时，App 仍提示「明天再来」（`guideDailyCap`）。前端下次发版时区分月度和日度。

**记账不能丢：**

- `record_llm_usage` 改用一个独立的小连接池（每进程 4+4）。
- 记账失败时 `INCR ops:usage_record_fail`，写进 Redis 供 cron 读取；Redis 也不可用时只写日志。

**超支上限**：预算越线的那一刻，已经在跑的任务最多还会花约 24 × 首屏成本 + 60/9 × 单件全部翻译成本（§9.3）。

### 4.2 防滥用（Redis，fail-open）

| 身份 | 额度层 |
|---|---|
| 正式账号 | 账号层 `CAP_PER_USER=160`，加一个**宽松的 IP 层** `CAP_PER_IP_REGISTERED=3000`。这是 backlog (b) 原来的建议：既不卡住共用 WiFi 的用户，又能挡住有人用一批账号刷光全局预算 |
| 游客账号（`is_guest`） | 账号层，加 IP 层 `CAP_PER_IP=300` |

- 匿名用户不会触发生成。
- **扣额度的顺序**：enqueue 但不提交 → `inserted=True` 时扣 Redis 额度 → 超额就 ROLLBACK，否则 COMMIT。
  - 合并到已有任务的请求不扣额度。
  - 与 #1037 的 paid key 兼容：COMMIT 失败时会多扣一次，但同一件作品同一天不会再扣，可以自愈。
- slowapi：`storage_uri` 指向 Redis，打开 `in_memory_fallback_enabled=True`，并设 socket 超时（第七轮实测，Redis 挂掉时不会报错）。
  - 改用 Redis 后，计数从「每个进程一份」变成「全站一份」，实际限额会减半。所以现有各条限额的数字**乘以当前 web 进程数（2）**，保持今天的实际限额：注册 5/分 → 10/分，登录 10/分 → 20/分，申请重设密码 5/时 → 10/时，确认重设密码 10/时 → 20/时，邮件验证 5/时 → 10/时，反馈与照片反馈 60/时 → 120/时，支付 120/分 → 240/分。
- 游客登录限速 `GUEST_LOGIN_RATE=30/hour`。

### 4.3 外部接口速率

- **大模型**：并发数就是上限（§9.2）。显式超时和 429 的处理见 §3.4。
- **Wikidata / Wikimedia**：
  - 保留进程内的 `_GATE`，大小改为配置项 `WIKIDATA_CONCURRENCY`（默认 2）。
  - `material.py` 里直接调 `requests.get` 的几处（wbsearchentities、SPARQL）**也要经过 `_GATE`**。
  - queue 模式下只有 worker 调用。
- **Google TTS**：
  - `TTS_CONCURRENCY` 每进程默认 32。
  - 遇到 `ResourceExhausted`（429）时**先退避再重试**。现在 `_is_transient` 会立即重试一次，每次重试都要再消耗一次额度。退避加重试的总时长封顶 25 秒，保证 `/audio` 在 App 35 秒的接收超时之前返回。
  - 每次 429 记 `event_log`，纳入 §7。

### 4.4 nginx

- 识别路径**单独用一个 `limit_req_zone`**：每 IP `2r/s burst=20`。它是识别 AI 兜底唯一的量的上限。共用 WiFi 时，50 人每 3.5 分钟识别一次，约 0.24 次/秒，足够用。
- 其他路径：`50r/s burst=100`。
- 本节吸收了 backlog 待定项 (c)。

## 5. 识别与网页服务扩容

### 5.1 数据库连接

**先消除隐藏的连接占用：**

- 流式语音接口在 `_require_audio_access` 和 `_hidden` 之后**立即 `db.close()`**。`_prepare_sync` 自己另开会话。
- 流式接口是 async，这两次检查改为 `await run_in_threadpool(...)` 执行，不在事件循环里同步查库。否则连接池一旦耗尽，`pool_timeout=30s` 会把整个进程（包括健康检查）卡住 30 秒（B15）。
- `/audio` 是同步接口，合成期间一直占着线程池的一个线程。设每进程同时合成上限 `AUDIO_SYNC_MAX=16`，超出直接返回 409（App 已会按 2→16 秒退避重试）。这样线程池 40 个里至少 24 个留给浏览。
- 记账用独立连接池。
- 启动时显式设置线程池大小，不依赖宿主机核数：
  - anyio limiter：web 40，recognizer `RECOG_THREADPOOL=16`；
  - 事件循环的默认 executor：12。

| 进程 | 业务池 | 记账池 | 每进程 | 个数 | 小计 |
|---|---|---|---|---|---|
| web | 40+12（`DB_POOL_SIZE=40`、`DB_MAX_OVERFLOW=12`） | 8 | 60 | 2 | 120 |
| recognizer | 16+4 | 8 | 28 | 2 | 56 |
| worker | HIGH+LOW+4 = 88（代码自动计算，overflow 为 0） | 8 | 96 | 1 | 96 |
| 脚本 / cron / 迁移 | | | | | ~15 |
| **合计** | | | | | **~287** |

- `max_connections` 设为 400，0.8 × 400 = 320，放得下 287。staging 的 PostgreSQL 是独立容器，不占用这个额度。多机部署时再加 PgBouncer。
- **P1 阶段不缩小连接池**，因为那时懒生成还跑在 web 里。
- **改 `max_connections` 需要重启 PostgreSQL**，P1 要安排维护窗口（§11），并且排在 P1 代码上线**之前**：记账连接池上线后每进程最多 68 个连接，2 个进程是 136，超过现在的 100（第八轮）。
- `shared_buffers`、`effective_cache_size` 不改：整个库只有 274 MB（10-22），调大没有收益，只会让维护窗口多一处改动（第八轮）。

### 5.2 recognizer 容器

- nginx 用两条 location 把识别请求转给 recognizer：`= /api/v1/recognize` 和 `~ ^/api/v1/museums/[^/]+/recognize$`。
  - 使用识别专用的限流区（§4.4），保留 `proxy_read_timeout 120s`。
  - web 设为 backup，配合 `proxy_next_upstream error timeout`：只有连接失败才回落到 web；POST 请求已经发出就不会重发。
- confirm、reject、已返回 410 的旧接口、照片反馈，这几个接口留在 web。
- 配置：`RECOG_WORKERS=2`、`RECOG_ONNX_THREADS=4`（P3 按路径实测后定）、`RECOG_THREADPOOL=16`；web 上设 `RECOG_PRELOAD=false`。
- **用 CPU 权重隔离识别和浏览**（用户 10-22 定）：recognizer `cpu_shares: 512`，web `cpu_shares: 1024`。两边争 CPU 时浏览优先；没人争时识别能用满空闲的核，单人识别速度不比今天慢。v8 的「每请求 2 线程」在今天的低负载下，预计会让画框、裁剪两步慢 2–3 倍（§0.2 基线）。

### 5.3 向量检索

**现状（prod 10-22）**：41,365 条向量，对应 15,406 件作品（每件约 2.7 条），每条 384 维 float32（1.5 KB），合计约 62 MB。近 30 天 2,201 次识别里有 2,200 次是不限馆的全局识别，每次都扫全部向量。现在慢在 Python 循环（逐条建馆过滤掩码、逐条取每件作品的最高分），不在矩阵乘法本身。

**收录到几十万、上百万件时的路线**（按触发条件逐级上，不提前做）：

| 档 | 做法 | 触发 |
|---|---|---|
| ① | 去掉 Python 循环：`np.maximum.at` 加预存的 qid 下标；`np.isin` 做馆过滤；13 个查询向量合成一次矩阵乘法 | P1。第七轮实测：10 万向量、13 个查询约 6 ms（旧实现 329 ms）；30 万向量约 16 ms。按线性外推，100 万件作品（约 270 万条向量）约 150 ms，VPS 上可能再慢 2–3 倍 |
| ② | 向量矩阵只常驻在 recognizer 里 | P3 |
| ③ | 省内存：换成 FAISS 的半精度（或 8 位）暴力检索；索引存成文件，用内存映射加载，同机所有进程共用一份，秒级启动 | 每进程向量矩阵超过 1 GB（约 70 万条向量、25 万件作品）。到 100 万件时 float32 每进程约 4 GB，2 个进程就是 8 GB，从数据库重新加载要几分钟——这才是百万级的真正瓶颈 |
| ④ | 缩小范围：识别接口加可选参数 `city`，先只搜该城市的馆，没有把握再退回全局。加法契约，老 App 照旧走全局 | 全局识别 p95 超过基线 × 1.5，或开到多个城市之后。要前端发版配合；参数从哪来（城市选择还是定位）届时再定 |
| ⑤ | 近似检索（FAISS 的 HNSW 或 IVF），百万级单次查询在毫秒级；召回率略低于 100% | ①–④ 之后暴力检索仍超基线（约 200 万条向量以上）。上线前必须用 `scripts/recognition_photo_eval.py` 和它的标注集对比，Top-1 准确率不降才切 |

- 第 ① 档不解决 CPU 占满的问题（B4），那要靠拆出 recognizer。
- 验收标准：10 万向量时 ≤ 30 ms，结果与旧实现逐条对拍一致。
- v8 把近似检索的门槛定在 30 万条向量。第八轮按实测数改为最后一档：30 万条暴力检索只要约 16 ms，那时换近似检索收益很小，还要承担召回率下降的风险。

## 6. 语音：合成槽位（所有音频路径统一）

**同一段音频最多同时合成 2 路。** 流式接口、非流式 `/audio`、问答音频、作者简介音频**都用同一套 Redis 槽位**，`attributes.audio_locks` 全部删除。

**为什么要统一：**

- 老 App 的流式请求收到 409 后，会立即回退到非流式的 `/audio`（guide_audio_player.dart 的 `_loadLegacy`）。如果只给流式路径加槽位，这条回退路径就能绕过上限。
- `attributes` 是整体读改写的，会覆盖 worker 写进去的 `title_i18n` 等字段。

**槽位：**

- 槽位 key：`audio:synth:{qid}:{lang}:{section}:{1|2}`，用 `SET <token> NX EX 180` 抢占；释放时用 Lua 比对 token 后再删除。
- 抢到槽位后，**先再查一次缓存**：别人可能刚落库，有就直接返回。
- 两个槽位都被占时，**流式和 `/audio` 都返回 409**，老 App 会按 2、4、8、16 秒退避重试，最多 60 秒（guide_audio_player.dart 已核实）。`/audio` 另有进程内同时合成上限（§5.1），超出也返回 409。
- Redis 不可用时放行。这时仍受每进程 `TTS_CONCURRENCY` 限制，数据正确性由条件落库保证。

**条件落库：**

- `persist_section_audio` 改为：

  ```sql
  UPDATE … SET audio_key=:k, audio_engine=:e
  WHERE … AND audio_key IS NULL AND body = :合成所用正文
  RETURNING audio_key
  ```

  没有更新到任何行时，再 SELECT 出胜出的 key。如果正文已经变了，返回 busy。
- 问答和作者简介的音频用同样的条件写法（作者简介见 W11）。
- 落败的那份已上传文件，交给孤儿 GC 清理。
- 不影响 VoxCPM2 替换。音频从无到有不算损失，不会触发音频损失闸。

**代价与契约：**

- 代价：每段最多多合成一次。
- 契约不变，老 App 不需要发版。
- 测试要覆盖：流式收到 409 后回退到 `/audio`，不会产生第 3 份合成。

## 7. 监控与扩容提醒

**运行方式：**

- 宿主机 cron 每 5 分钟执行一次 `/opt/gomuseum/ops-check.sh`。
- 宿主机指标直接在 shell 里取，其余的通过 `docker exec <按服务名> python scripts/ops_check.py` 获取。
- 告警限频用文件时间戳 `/opt/gomuseum/alerts/{key}.last`，同类告警 6 小时只发一封。
- 每封告警都写明处理办法。

**邮件告警只保留 7 项**（第七轮建议收敛，其余放进报告）：

| 检查项 | 数据来源 | 阈值 | 处理办法 |
|---|---|---|---|
| **worker 存活** | 任务表 | 有 queued 的生成任务，**且当前不在预算停止期间**，且 5 分钟内没有任何任务被领取（发版时会停 worker 1–3 分钟，设 2 分钟会误报） | 最紧急：懒生成已经停了 |
| 「有人在等」的最老任务 | 任务表：有效优先级 10 的 queued 任务中最老的那条已等待的时长（实时值，不是事后统计） | > 30 秒，且不在预算停止期间 | 加 `WORKER_HIGH_THREADS` |
| 内容生成预算 | `llm_usage` × `LLM_PRICES` | 80% / 100% | 调高预算，或离线预生成 |
| 浏览 / 内容接口 p95 与 5xx | nginx `urt=`，剔除长连接 | p95 > 1 秒，或 5xx > 1% | 加 web 进程；查日志 |
| 识别（向量各路径）p95 | `recognition_event`，按 engine 分路径 | > 基线 × 1.5（§0.2） | 加 recognizer |
| 磁盘 / 内存 / CPU | 宿主机 | > 80%；CPU 连续 15 分钟 > 70% | 加资源 |
| 数据库连接 | `pg_stat_activity` | > 80% `max_connections` | 调整配置 |

**外部探活**：推荐用免费的外部 HTTP 探活服务（如 UptimeRobot）探测 `/health`，覆盖 cron 或 docker 本身故障的情况。账号**由用户注册**（§11 P4）。

**`scripts/ops_report.py`（按需运行）包含：**

- 补语言积压，以及「高峰后 30 分钟清空」的达成情况；
- 失败率；
- 外部 429（大模型、Google TTS）；
- 语音和识别兜底的两笔账；
- 识别 AI 兜底路径的 p95；
- **当日因预算被拒的作品数（按 qid 去重）**，以及被拒次数最多的作品；
- 记账失败计数（从 Redis 读）；
- 向量数；
- 各项指标距离上限还有多少余量。

## 8. staging 与 prod 隔离

- staging 的容器加 `cpus` 和 `mem_limit`，合计 2 核 4G。
- prod 的 worker 设 `mem_limit`，防止它挤占 web 的资源。
- 测真实容量时，按小时租一台同规格机器，跑 `lt.py` 的 200 人场景。

## 9. 规模与成本估算

### 9.1 识别

`核数 = k × U / T_recog × c_recog ÷ u`

| 变量 | 取值 | 来源 |
|---|---|---|
| U | 200 / 1000 | 设计容量 |
| T_recog | 3–4 分钟 | **假设**（用户判断） |
| k | 2–3 | **假设**；有真实流量后，用 `recognition_events` 的每分钟最大值 ÷ 平均值实测 |
| c_recog | 0.97 核·秒（**待按路径实测**） | 压测 B 的值，没有分路径。prod 近 14 天约 77% 的识别会走画框或裁剪这两步重推理；压测样本如果多走了快路径，这个数会偏低而不是偏高（第八轮） |
| u | 0.6 | 留出的余量 |

- 200 人：需要 2.7–5.4 核，c_recog 实测后可能更高；这台 8 核机器还要分给 web、worker、PG 和同机其他项目（§2 第 5 条）。
- 1000 人：需要 13–27 核，约 2–3 台机器；或者先做推理降本。

**延迟要单独算**：最慢的路径要做 13 次推理。今天推理用满 8 核时，画框、裁剪两条路径的 p95 已经约 4 秒（§0.2 基线）。P3 要按路径（快路径、画框、裁剪、AI 兜底）分别实测单人和 200 人两种负载下的 p95，再定 `RECOG_ONNX_THREADS` 取多少。

### 9.2 生成

**10-19 prod 实测（51 件，`@app`）：**

| channel | 模型 | 调用 | 输入 | 输出 | 每次输入 | 每次输出 |
|---|---|---|---|---|---|---|
| gate | haiku | 333 | 1,582,553 | 6,355 | 4,752 | 19 |
| generate | haiku | 127 | 682,677 | 63,548 | 5,375 | 500 |
| qa | haiku | 51 | 290,127 | 21,467 | 5,689 | 421 |
| translate | luna | 5,610 | 3,424,283 | 509,706 | 610 | 91 |
| vision | sonnet | 50 | 117,080 | 13,372 | 2,342 | 267 |

- 平均每件约 121 次调用，输入 119.5k tokens，输出 12.0k tokens。
- 「翻译每门语言约 12 次」这个数，是假设这 51 件都补齐了 9 门语言推出来的，**没有核实**。实施时在 staging 上跑 N 件，取 `llm_usage` 的增量，分别统计首屏和每门翻译。

**需求侧**

- 每分钟需要首屏的件数：`λ = U × p_stub / T_open`
  - p_stub = **0.155**（10-21 实测，样本有偏）
  - T_open = 3.5 分钟（**假设**）
  - 200 人时，λ ≈ 8.9 件/分钟
- 高优先级线程数 ≈ `λ × T_occ_first / 60 × k`
  - T_occ_first 是首屏占用线程的时长，估计 45–90 秒，**未实测**，取 60 秒
  - k = 3
  - 结果约 27 个
- 低优先级线程：平均负载 ≈ `λ × 9 × T_lang / 60`
  - T_lang ≈ 44 秒，**未实测**
  - 结果约 59。按 §0.2，高峰时允许积压，按 LOW ≥ 平均负载 / 0.7 算，约 84 个
- **预算的约束**：$30 ÷ C_item ≈ 每天 300–600 件。持续高峰时，预算 1–2 小时就会用完，之后停止生成，积压留到第二天。所以线程数只影响预算用完之前的响应速度，不影响每天能生成多少件。
- **默认取 HIGH=24、LOW=60**：
  - 这样连接数能放进 §5.1 的核算。
  - 在预算约束下，日均 λ ≤ 2.5 件/分钟，此时低优先级的平均负载约 17，60 个线程绰绰有余。
  - 只有预算用完之前那段持续高峰，补语言会积压。
  - 等 T_occ_first、T_lang 实测之后，按公式重新调整。

**供给侧**

- **Haiku**：每个首屏约 75 秒，24 线程每分钟约处理 19 件；每件 Haiku 输入 50.1k tokens，合计约 0.96M TPM，约占上限 10M（10-20 探测）的 10%。
- **OpenAI**：低优先级 60 线程，每线程 1 路调用，每次 ≥ 1 秒，所以 ≤ 3,600 次/分钟、≤ 2.5M TPM。加上离线脚本和 staging，仍低于 10k RPM、10M TPM。
- **Wikidata**：
  - 每件首屏约 10 次调用（未实测）。24 线程满载约 240 次/分钟；而 2 个令牌、p50 为 0.5 秒时，吞吐也约 240 次/分钟，**已经到了单进程的上限**。
  - 解法二选一：再开一个 worker 容器，令牌按总规则第 4 条平分；或者先把 HIGH 降到 16。
  - P2b 上线后，看「最老等待时长」和首屏耗时的实测再定。
- **Google TTS**：
  - 200 人、每人每 3.5 分钟听一段：平均约 57 次/分钟，高峰（×3）约 171 次/分钟，**接近 200 的上限**。
  - 随着音频落库和 VoxCPM2 替换推进，未缓存比例会下降。
  - 429 的退避和告警见 §4.3。

### 9.3 成本

**每件成本：**

`C_item = 50.1k×P_haiku_in + 1.79k×P_haiku_out + 2.30k×P_sonnet_in + 0.26k×P_sonnet_out + 67.1k×P_luna_in + 9.99k×P_luna_out`

单价在实施时核对。

**每日花费** ≤ 当天被打开过的不同空作品数 × C_item，另加三项：按请求翻译、首屏失败的部分成本、被闸挡下后的重译。

**$30 能撑多久** = 30 ÷ (λ × 60 × C_item) 小时。λ = 8.9 时：

- C_item 为 $0.05：约 1.1 小时；
- C_item 为 $0.10：约 34 分钟。

**语音** = 未缓存的首播段数 × 字数 × $30/百万字，另加每段最多多合成一次的成本。

### 9.4 语音

- 每段音频 0.91–1.97 MB。
- 并发：32 × 2 进程 = 64 路，满足 ≥ 50 的目标，也低于 100 的上限（staging 也要计入）。
- 每分钟请求数见 §9.2。

### 9.5 PostgreSQL 单点

1000 人以上时，PostgreSQL 仍然只有一台。首要的两个杠杆：

- 把 PG 搬到独立机器；
- 已 ready 的作品内容不再变化，可以在 nginx 或 web 层缓存响应。

这两项都不在本设计范围内，等 §7 的数据库连接或 CPU 告警触发后再做。

## 10. 配置项清单

| 配置 | 默认 | 位置 |
|---|---|---|
| `WEB_WORKERS` / `RECOG_WORKERS` | 2 / 2 | compose |
| `RECOG_ONNX_THREADS` / `RECOG_THREADPOOL` | 4（P3 实测后定）/ 16 | `.env` |
| `cpu_shares` | web 1024 / recognizer 512 | compose |
| `RECOG_PRELOAD` | true（web 设为 false） | compose |
| `INIT_DB_ON_START` | true（recognizer、worker 设为 false） | compose |
| `LAZY_EXECUTOR` | **inprocess**（prod 上线 worker 后改为 queue） | `.env` |
| `WORKER_HIGH_THREADS` / `WORKER_LOW_THREADS` | 24 / 60 | `.env` |
| worker 的 `restart` / `stop_grace_period` | always / 60s | compose |
| `JOB_COOLDOWN_TRANSIENT_MIN` / `JOB_COOLDOWN_INTERNAL_H` / `JOB_RESUME_COOLDOWN_H` | 15 / 6 / 6 | `.env` |
| `LLM_TIMEOUT_S` | 90 | `.env` |
| `DB_POOL_SIZE` / `DB_MAX_OVERFLOW` | P1 保持 20/40；P2 起 web 40/12、recognizer 16/4，worker 自动计算 | `.env` |
| `max_connections` | 400（`shared_buffers` 等不改） | postgres 容器启动命令 |
| `LLM_PRICES` | 实施时核对 | `.env` |
| `BUDGET_GEN_DAILY_USD` / `BUDGET_GEN_MONTHLY_USD` / `BUDGET_ALERT_RATIO` | 30 / 300 / 0.8 | `.env` |
| `ALERT_TTS_DAILY_USD` / `ALERT_RECOG_DAILY_USD` | 按实测基线定 | `.env` |
| `CAP_PER_USER` / `CAP_PER_IP` / `CAP_PER_IP_REGISTERED` | 160 / 300 / 3000 | `.env` |
| `WEIGHT_GENERATION` / `WEIGHT_TRANSLATION` | 8 / 3 | `.env` |
| `GUEST_LOGIN_RATE` | 30/hour | `.env` |
| `WIKIDATA_CONCURRENCY` | 2（每进程） | `.env` |
| `TTS_CONCURRENCY` | 32（每进程） | `.env` |
| `AUDIO_SYNTH_SLOTS` | 2 | `.env` |
| `AUDIO_SYNC_MAX` | 16（每进程） | `.env` |
| nginx | 识别 2r/s burst 20；其他 50r/s burst 100 | nginx |

## 11. 分阶段实施

**发布机制的约束（第七轮 A1）：**

- CD 只同步 `backend/`，并在 VPS 现有的 compose 目录执行 `up -d --build`。compose、nginx、`.env` 都要手工改。
- 所以每个阶段都分三步：**代码合入 → 手工改 compose / nginx / .env → 切开关**。
- compose 的改动必须在同一个维护窗口里**立即生效**（`up -d <服务>`）。否则下一次 CD 会把这些改动带上，在不受控的时间点重建容器（比如重启数据库）。

**CD 要先停 worker 再迁移**（第八轮，P2b 起生效）：

- 生成管线的事务会跨越抓取和大模型调用（B14），prod `lock_timeout=0`。迁移时如果旧 worker 还在跑，`ALTER TABLE`、建索引要等它的事务全部结束，这段时间新 web 起不来，整站 502。改热表的迁移大约每月一次（09-07 讲解段表加列，10-19 作品表建唯一约束）。现在没事，是因为懒生成线程跟着旧 web 容器一起停掉了。
- deploy.yml 的部署步骤改为：

  ```sh
  docker compose build
  # 有 worker 服务时才停（P2b 之前没有这个服务）
  if docker compose config --services | grep -qx worker; then docker compose stop -t 60 worker; fi
  docker compose up -d --remove-orphans --wait
  ```

  先构建，停 worker 的这段时间就不包含构建耗时。worker 停下后，库里没有它的事务，迁移不用等锁。
- alembic 每次迁移先 `SET lock_timeout = '10s'`。拿不到锁就失败退出，容器按 `restart` 策略重试，不会无限期挡住其他查询。
- 代价：每次后端发版，懒生成暂停 1–3 分钟；在跑的首屏由续跑接手，不丢任务。现在发版时正在生成的作品要等 10 分钟锁过期，新方案仍然更好。
- deploy.yml 的改动和 P2b 的代码放在同一个 PR 里合入，必须早于手工在 compose 里加 worker。

| 阶段 | 内容 | 上线步骤 |
|---|---|---|
| P1 | 连接池改为配置项（默认值不变）；流式语音提前 `db.close()`，两次检查放进线程池；`/audio` 同时合成上限；记账用独立连接池；向量检索 ①；防滥用按身份分档（含宽松 IP 层）；slowapi 改用 Redis（限额数字翻倍）；`TTS_CONCURRENCY` 和 TTS 429 退避；**所有音频路径统一用 Redis 槽位**，并加条件落库；Wikimedia 直连请求经过 `_GATE` | ① **维护窗口（先做）**：确认 prod 没有长任务 → 备份 → 手工改 compose 里 postgres 的 `max_connections=400` → `up -d postgres` → 核实连接数。趁正式版用户还少时做，影响最小。② 代码合入，CD 自动部署（这些改动都不涉及 compose）。③ 手工改 nginx（识别单独限流，其他 50r/s）→ `nginx -t` → reload |
| P2a | 只改管线，仍在 web 里跑（用户 10-22 定拆分）：`locked_artist` 和作者块重构；`chat()` 显式超时和 429 专门异常；翻译逐段容错；`generate_object` 的续跑模式（inprocess 下 `_generate` 一律传 `resume=True`，对 stub 等同全新生成，让新代码路径先跑起来）；补记账、价目表、三笔账（此阶段只告警） | ① 代码合入，CD 自动部署。② 观察 7 天：作者行变更（纪律 37 写入面）、生成失败率、`audio_invalidations`、成本。出问题回滚代码 |
| P2b | 任务表和 worker；按美元预算停止；内容接口的续跑触发与冷却；语言白名单；回滚开关；**deploy.yml 先停 worker**；**worker 存活告警**；记录被拒作品 | ① 代码合入（`LAZY_EXECUTOR` 默认 inprocess；开关只切执行方式，管线已在 P2a 跑过）。② 手工在 compose 里加 worker 服务（`depends_on: web: service_healthy`、`restart: always`、`stop_grace_period: 60s`、`mem_limit`）→ `up -d worker` → 看日志确认它在空转等待。③ `.env` 改为 `LAZY_EXECUTOR=queue` → 依次重启 web 和 worker。④ 观察 24 小时，出问题就把 `.env` 改回 inprocess 再重启。⑤ 两周后删除 inprocess 路径 |
| P2c | `queue_position` / `eta_seconds` | 与前端一起排期 |
| P3 | recognizer 容器（`cpu_shares` 低于 web）、nginx 分流、显式设置线程池、staging 资源上限、prod worker 的 `mem_limit`；按路径实测识别 p95，与 §0.2 基线对比 | ① 代码合入。② 手工在 compose 里加 recognizer → `up -d recognizer` → 本机请求验证。③ 改 nginx upstream（web 作为 backup）→ reload |
| P4 | 其余 ops-check 检查项、ops_report、cron | ① 代码合入。② 在宿主机装 cron。③ **用户**注册外部探活服务 |

每个阶段上 prod 前，都要先确认 prod 上没有长任务在跑。

## 12. 测试与验收

**测试环境：**

- 任务表、预算、作者行的测试都用真实 PostgreSQL。
- **并发类用例打 PG 专用标记，CI 里没有 PG 时报失败，而不是跳过。**
- 另加一条用 PG 方言编译、断言 SQL 里有 `FOR UPDATE` 的检查。
- 非并发用例可以留在 SQLite 上跑。

**任务表**

- enqueue：
  - 重复请求会合并；抬高优先级时刷新 `priority_at`；
  - 插入时 `priority_at=now()`，测试从 enqueue 开始走真实路径；
  - 只读命中时不写库；running 中再次入队不写库；
  - 冷却按 `error_kind` 区分（transient 15 分钟、internal 6 小时），续跑不论成败冷却 6 小时；语言白名单、环境守卫都生效；
  - 不同语言的首屏只生成一条任务；
  - 与首屏 `lang_priority` 相同的翻译不入队；
  - 没有依赖时不入队，`generating` 稳定为 false，不会在 true/false 之间抖动。
- claim：
  - SKIP LOCKED 不会重复领取；
  - 有效优先级：等待超过 10 分钟后改由低优先级线程领取，用户重新打开后回到高优先级；
  - 优先级 0 的翻译会等首屏完成；
  - 预算停止时不领取；
  - `run_after` 退避生效；
  - 用 EXPLAIN 断言两条 SQL 都走部分索引；在 3 万件作品、10 万条 queued 任务的规模下，单次 claim < 5 ms，**包括高档在「0 条高优先级、10 万条低优先级」时的最坏情况**；
  - 高优先级翻译在英文还没就绪时被领到：置回 queued，不计次数。
- 清理线程：租约过期后，按退避置回 queued，或置为 failed；孤儿翻译任务被置为 cancelled。
- finish：
  - 翻译完成时只因「开始后新发布的英文段」回队列；首屏期间新发布的深度段最终会被翻译；
  - 英文有 needs_review 段时，翻译任务照常 done，不回队列；
  - 某一段每次翻译都报错：任务按失败处理、进入冷却，不循环；已翻好的段保留；
  - `retry=False` 时直接置为 failed。
- 首屏完成后，只为有缺口的语言入队；如果 `lang_priority` 那门在首屏里翻译失败，也会入队兜底。
- SIGTERM：翻译任务被 release；首屏任务被杀后，租约过期由续跑接手，已落库的段不重做。
- 部署（staging 演练）：worker 有在跑的任务时，执行一次带改表迁移的 CD。断言迁移不等锁、worker 60 秒内退出、新 worker 续跑接手；期间浏览接口只受 web 重启影响。
- 回滚开关：两种模式都要测；inprocess 模式下 worker 不领任务。
- 显式超时：模拟大模型调用挂住，90 秒后报错并释放线程。
- 429 重试用尽：抛出专门的异常，不落库薄内容。

**续跑**

- 人为构造几种半成品：只有主讲解、缺深度段、缺问答、缺请求语言。
- 对每种半成品断言：
  - resume 只补缺，已有段的 body 和 `audio_key` 不变，已有问答行不被删除；
  - 能绕过 exists 早退；
  - 已有的深度段不会传给 canonical；
  - 某一段翻译出错时跳过它，继续翻译后面的段；
  - `content_status=ready` 但有缺行时，内容接口会以优先级 0 入队续跑；
  - 英文问答全是 needs_review、英文主讲解是 needs_review 时，内容接口不入队，`generating` 保持 false；
  - 续跑正常结束后 6 小时内再打开，不再入队。

**纪律 37（作者行）**

- （PG）两个首屏同时遇到同一位新作者：不冲突，不丢更新。
- （PG）作者块和 9 个翻译任务并发写同一行：所有语言都在。
- （PG）持锁期间没有网络调用，等锁 < 1 秒；拿锁时 `db.dirty` 为空。
- 先把作者行加载进会话，再由另一个会话修改它，之后跑作者块：不会把另一个会话的修改回滚掉。
- `bio`、`bio_audio`、`bio_audio_engine` 是 SQL NULL、JSON null 或 `{}` 时都不报错。
- `notable_works` 的三种空值都会被补上；`notable_works_i18n` 里的空列表视为缺失。
- `bio_en` 快照前置条件：英文已被改过时，整批其他语言都不写。
- 修坏值：
  - 脚本进程额度为 0 时抛 `AudioLossBlocked`，数据库不变；
  - 只记录模式下，清了几门语言就记几条；
  - （PG）并发修复时只有一方成功；
  - 英文缺失（而不是坏值）时走补缺。
- `lazy_audio`：
  - 文本变了时返回 busy；
  - 已有 key 时返回已有 key；
  - （PG）两门语言并发时，两个 key 都在。
- `--refresh-langs` 仍能替换内容，并受音频损失闸管控。

**预算**（配置的两侧都要测）

- 内容生成到 80% 和 100% 时的行为。
- 语音、识别只告警。
- 未知模型按最贵价计算。
- UTC 日界。
- 记账连接池耗尽时不丢账，失败计数写进 Redis。

**扣额度**

- 超额时 ROLLBACK，不留下任务。
- 正式账号在同一 IP 下超过 3000 时被拒。
- slowapi 改 Redis 后两个进程共用计数，各限额是原来数字的 2 倍。

**语音**

- 3 人同时首播：前两人拿到流，第三人收到 409。
- **流式收到 409 后回退到 `/audio`，不会产生第 3 份合成。**
- 只落库一份，返回胜出的 key。
- 合成期间正文被改，返回 busy。
- Redis 不可用时放行。
- 问答和作者简介的音频也走槽位。
- `/audio` 同一进程第 17 路同时合成返回 409。
- 流式接口的权限检查不阻塞事件循环：数据库变慢时，同一进程的其他请求不受影响。

**连接**：50 路流式同时进行时，数据库连接数不会随之增长。

**契约**

- 用状态机走完整流程：首屏 → 有人在等的翻译 → 首屏完成后补齐 → 补齐完成。每一步都断言各语言的 `generating` **不会提前变成 false，也不会永远是 true**。
- 预算停止时返回 `daily_cap`。
- 新字段可以缺省。

**容量验收**：在同规格机器上跑 200 人场景，逐行对照 §0.2。识别要分别测单人（不比基线慢）和 200 人（p95 ≤ 基线 × 1.5）。

## 13. 评审历史

| 轮次 | 范围 | 阻断 | 关键发现 | 处理 |
|---|---|---|---|---|
| 1 | 全文 v1 | 4 | 入队 SQL 跑不起来；任务会永久卡死；同一件出现两个首屏；TTS 并发写死 | v2 |
| 2 | 全文 v2 | 1 | 首屏无法续跑，会留下半成品 | v3（用户定：续跑） |
| 3 | 全文 v3 | 3 | 续跑在现有代码结构上做不到幂等；作者锁把网络调用也包进去了 | v4（用户定：补语言目标改为 A） |
| 4 | P2 v4 | 2 | 修坏值和「只补缺」冲突；代表作字段是列表 | v5 |
| 5 | §3.3 v5 | 2 | 原生 SQL 绕过了音频损失闸 | v6 |
| 6 | §3.3 v6 | 1 | 修坏值失败后，其他语言的译文来源不一致 | v7 |
| 7 | **全文 v7，全新上下文** | 1 | 见 13.1 | v8（全文重写） |
| 8 | **全文 v8，对照最新代码与 prod 只读数据**，重点查「会不会影响已有用户」 | 4 | 见 13.2 | v9（用户 10-22 定 4 项） |

### 13.1 第七轮（v7 → v8）

| 条目 | 处理 |
|---|---|
| A1 发布顺序：代码合入就自动部署，但 worker 需要手工上线，懒生成会停摆（阻断） | 改：开关默认 inprocess；§11 每个阶段分三步写；compose 改动在维护窗口内立即生效；加 depends_on |
| B1 老 App 收到 409 后回退到 `/audio`，绕过 2 路上限；`attributes` 被覆盖 | 改：所有音频路径统一用 Redis 槽位，删除 audio_locks，见 §6 |
| B2 `priority_at` 插入时为 NULL | 改：默认 now()；降级改由 claim 按有效优先级计算，见 §3.1、§3.2 |
| B3 claim 的耗时随规模增长 | 改：只扫 queued 的部分索引；租约接管移到清理线程；依赖检查不再扫段表，见 §3.1、§3.2 |
| B4 为 lang_priority 兜底入队，让 generating 长时间为 true | 改：只给有缺口的语言入队，见 §3.3、§3.6 |
| B5 放宽到 50r/s 会放大识别兜底的成本 | 改：识别单独限流 2r/s，见 §4.4 |
| B6 漏了 Google 200 次/分钟的限额；429 立即重试 | 改：总规则第 3 条加上 RPM；429 先退避；加告警，见 §2、§4.3、§9.2 |
| B7 大模型调用没有显式超时 | 改：`LLM_TIMEOUT_S=90`；429 重试用尽后抛专门的异常，见 §3.4 |
| B8 逐段容错只能放在函数内部；续跑没有触发入口 | 改：§3.4 的翻译行；§3.3 的续跑入口 |
| B9 监控有误报、漏报和盲区 | 改：收敛为 7 项；排除预算停止期间；改看最老等待时长；记账失败计数写 Redis；加外部探活，见 §7 |
| B10 p_stub、LOW 线程数、识别延迟、Haiku TPM 来源 | 改：p_stub 实测 15.5%；线程数重算为 24/60，并说明受预算约束；识别按路径分目标；TPM 注明来源为 10-20 探测，见 §0.2、§9 |
| B11 取消正式账号的 IP 层后没有兜底 | 改：保留宽松的 IP 层（3000），见 §4.2 |
| B12 language 没有白名单 | 改：见 §3.2 |
| 次要项：claim 的 kind、重试退避、环境守卫、条件落库比对正文、`db.close` 的位置、prod 隔离、PG 调优、worker 滚动部署、月度预算文案、Wikimedia 直连、回滚时的重复生成、PG 单点 | 都已写进对应章节。补图不进队列后，kind 的问题自然消失 |
| 简化建议 1：删除 rerun / mark_rerun / from_fanout | 采纳：改为翻译完成时重新检查缺口 |
| 简化建议 2：降级放进 claim 计算 | 采纳 |
| 简化建议 3：补图不进队列 | 采纳 |
| 简化建议 4：音频统一用 Redis 槽位 | 采纳 |
| 简化建议 5：监控收敛到 7 项 | 采纳 |

### 13.2 第八轮（v8 → v9）

核对方式：读 v8 全文，逐条对照最新 staging 代码（da8ca949）；在 prod 上只读查了数据库参数、存量内容和识别耗时。

| 条目 | 证据 | 处理 |
|---|---|---|
| A1 发版时迁移被 worker 的长事务卡住，整站 502（阻断） | 管线事务跨越网络调用；prod `lock_timeout=0`；CD 先重建 web 跑迁移，这时旧 worker 还在跑 | CD 先构建、再停 worker、再 up；SIGTERM 不等首屏；迁移设 `lock_timeout`。见 §11、§3.4 |
| A2 翻译完成后「重查缺口」会无限循环（阻断） | 翻译只读已发布英文段；prod 1,269 条被挡英文段只有 30 条有法语行；`attempts` 清零会热循环 | 只因「开始后新发布的英文段」回队列；有段报错按失败处理。见 §3.2 |
| A3 续跑让已有内容的作品反复转圈、反复花钱（阻断） | v8 按「未发布」判缺口；prod 103 件英文问答全被挡、3 件主讲解被挡；冷却只管失败 | 用户定：needs_review 是最终结果；缺口一律按缺行；续跑不论成败冷却 6 小时。见 §3.2–§3.4、§3.6 |
| A4 失败冷却 6 小时，上游故障恢复后仍打不开（阻断） | 现在失败后可以立即重试 | 用户定：transient 15 分钟，internal 6 小时。见 §3.1、§3.2 |
| B1 识别每请求 2 线程会让今天的用户变慢；v8 的 3 秒目标今天就达不到 | prod 基线：画框 p95 4.0 秒、裁剪 4.1 秒；约 77% 走重路径 | 用户定：按 CPU 权重隔离，推理约 4 线程；目标对标基线。见 §0.2、§5.2、§9.1 |
| B2 回滚开关不回滚管线改动 | inprocess 仍跑新管线 | 用户定：拆成 P2a（管线）和 P2b（队列）。见 §11 |
| B3 `/audio` 占线程；流式接口在事件循环里同步查库 | museums.py | `/audio` 同时合成上限 16，超出返回 409；两次检查放进线程池。见 §5.1 |
| B4 worker 没写重启策略 | compose 默认不重启 | `restart: always`。见 §2 |
| C1（用户追问）收录到几十万、上百万件时，向量识别会不会越来越慢 | prod 41,365 条向量；近 30 天 99.95% 是全局识别；百万级的瓶颈是每进程内存和加载时间，不是检索速度 | §5.3 改为五档路线，按触发条件上；近似检索从「30 万条」挪到最后一档 |
| 次要项 | — | slowapi 限额翻倍（§4.2）；维护窗口提前、不改 `shared_buffers`（§5.1、§11）；UTC 不用改（§4.1）；claim 拆成两条 SQL（§3.2）；英文未就绪的翻译不计次数回队列（§3.2）；`lang_priority` 兜底重译用优先级 10（§3.3）；存活告警改为 5 分钟（§7）；TTS 429 退避封顶 25 秒（§4.3）；同机其他项目计入容量（§2、§9.1） |
