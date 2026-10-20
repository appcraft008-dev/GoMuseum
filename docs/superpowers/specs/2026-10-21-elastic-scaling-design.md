# 弹性可扩容架构 设计

- 日期：2026-10-21
- 状态：待评审
- 来源：10-20 staging 多用户压测（backlog #1041）+ 10-20/21 brainstorm 逐段确认

## 0. 目标与原则

### 0.1 原则（用户定）

> 软件架构不能成为性能瓶颈。瓶颈只允许在：VPS 硬件（CPU / 内存 / 硬盘）、第三方接口速率限制、成本预算。

由此推出三条可检验的要求：

1. **加资源就加容量，不改代码**：加进程、加容器、加机器只改配置。
2. **所有容量数字都是配置项**：并发数、连接数、限流、预算都写在 `.env`，重启生效。
3. **不上大公司架构**：不引入 Kubernetes、消息中间件、Prometheus/Grafana。能用 PostgreSQL、Redis、nginx、cron 解决的，就不加新组件。

### 0.2 性能目标（验收标准）

| 场景 | 目标 |
|---|---|
| 设计容量 | 全部馆合计 **200 人同时在用**；扩到 1000+ 人只加机器 |
| 浏览 / 搜索 / 内容接口 | p95 ≤ 1 秒 |
| 识别 | p95 ≤ 3 秒 |
| 单人首屏（空作品第一次打开 → 本语言讲解出现） | p50 ≤ 15 秒，p95 ≤ 25 秒（属于「单人首屏提速」专题，本设计只保证高峰时不额外变慢） |
| 高峰排队额外等待 | 比单人时多 ≤ 10 秒 |
| 其余 9 门语言补齐 | ≤ 5 分钟 |
| 生成过程中另一种语言的用户打开 | ≤ 60 秒 |
| 首次播放（现场合成） | 50 人同时首播，首包 p95 ≤ 3 秒 |
| 第二个人听正在合成的同一段 | ≤ 3 秒开始播放，共用同一次合成 |
| 部署 / 重启 | 不丢任务 |
| 成本 | 每天 $30、每月 $300（配置项）；80% 告警，100% 停新内容生成 |

### 0.3 不在本设计范围

- **单人首屏提速**（新模型下 p50 约 22 秒，主因是接地闸重写草稿）：另开专题。
- 问答音频、作者简介音频（非流式接口，篇幅短）：不改。
- 离线 CLI 脚本（onboard / generate / translate）：不进队列，行为不变。

## 1. 现状与已查实的瓶颈

| # | 瓶颈 | 证据 | 违反哪条原则 |
|---|---|---|---|
| B1 | 懒生成跑在网页进程的后台线程里，并发数写死在代码里（`_SEM=2`、`_FANOUT_SEM=2`，`lazy.py:24,32`），按进程计 | 压测 C：20 件同时打开时，补语言 10/20 完成，8 件因槽位满被跳过 | 加机器不加生成容量；部署重启时正在跑的任务丢失 |
| B2 | 数据库连接：每个进程 `pool_size=20 + max_overflow=40`（`database.py:28`），prod 数据库 `max_connections=100` | 2 个进程理论上限已达 120 > 100；平时只用 11 个 | 加进程或容器 → 高峰时整站报「连接数过多」 |
| B3 | 向量检索逐条比对，耗时随作品数线性增长，一半耗时在 Python 循环（`vector_index.py:128-147`）；一次识别最多查约 12 遍（全帧 + 画框 + 8 个裁剪） | 本机实测，见 §4.3 | 收录越多越慢，加机器也救不了单次识别 |
| B4 | 识别和浏览在同一进程里抢 CPU | 压测 B：40 人每 5 秒识别一次，8 核 779% 占满 | 识别一忙，浏览跟着变慢 |
| B5 | 第二个听众收到 409，要等第一个人那段全部合成并存好（15–30 秒）；段锁存在 `attributes` JSON 里，和 `lazy_lock_at` 共用一格，读改写会互相覆盖（`lazy_audio.py:38`） | 代码 | 达不到 3 秒目标 |
| B6 | 每 IP 每天 300 额度对登录用户也生效 | 压测 C 第一次跑：浏览触发的翻译吃光同一 IP 额度，20 人全部收到 daily_cap | 馆内共用 WiFi 的游客互相挤占 |
| B7 | nginx 每 IP 10 次/秒（突发 20） | 配置 | 同上 |
| B8 | 价目表（`scripts/llm_cost_report.py:9`）只有旧模型，新模型 `gpt-6-luna`、`claude-haiku-5-5`、`claude-sonnet-5-5` 会按 $0 计 | 代码 | 不修就无法做成本上限 |
| B9 | 没有容量监控，没有扩容提醒 | — | 不知道什么时候该加机器 |

已经可以扩容、不用改的部分：识别「同图正在识别」锁在 Redis；搜索索引和向量索引是每个进程各自的内存副本（约 0.8G/进程，prod 容器 2 进程共 1.7G）；用量账本 `llm_usage` 已按「天 × 用途 × 模型」原子累加；告警邮件 `ops_alert.alert_throttled` 已有；nginx 访问日志已带 `rt=`（请求耗时）。

## 2. 总体架构

同一个镜像、同一份代码，按启动命令和 nginx 路由分成三类容器：

```
             ┌── /recognize 类 ──→ recognizer 容器（N 个进程，可多容器、可跨机器）
用户 → nginx ┤
             └── 其他请求 ──────→ web 容器（浏览、内容、语音流）
                                     │ 写任务
                                     ▼
                         PostgreSQL 任务表 generation_jobs
                                     ▲ 领任务
                                     │
                         worker 容器（生成进程，线程数可配，可多容器、可跨机器）
```

| 容器 | 负责 | 扩容方式 |
|---|---|---|
| web | 浏览、搜索、内容接口（只读内容、写任务）、语音流式播放 | 增加 `WEB_WORKERS`；或 nginx upstream 加一台 |
| recognizer | 所有识别接口 | 增加 `RECOG_WORKERS`；或 upstream 加一台 |
| worker | 从任务表领任务、调用 AI、写回结果 | 增加线程数配置；或多起几个 worker 容器（同机或异机） |

跨进程、跨机器共享的状态只放两个地方：**PostgreSQL**（必须可靠的：任务、内容、账本）和 **Redis**（丢了只降级的：防滥用计数、识别锁、语音直播缓冲）。

**扩容总规则**（写进运维文档，告警邮件里引用）：

- Σ(所有进程的数据库连接上限) ≤ 0.8 × `max_connections`
- Σ(所有 worker 的 AI 并发) × 每路每分钟调用数 < 外部每分钟上限
- Σ(所有 web 进程的同时 TTS 合成数) < Google 同时流式会话上限（100）

## 3. 生成任务队列（PostgreSQL 任务表）

### 3.1 表结构

`generation_jobs`（alembic 迁移新建，纯加法）：

| 列 | 类型 | 说明 |
|---|---|---|
| id | bigserial PK | |
| kind | varchar(16) | `first_screen` / `translate` / `image` |
| qid | varchar(32) | 作品 |
| language | varchar(16) | `image` 类为空串 |
| priority | smallint | 10 = 有人在等；0 = 没人在等 |
| status | varchar(12) | `queued` / `running` / `done` / `failed` |
| attempts | smallint, default 0 | |
| lease_until | timestamptz null | running 时有效 |
| worker_id | varchar(64) null | 主机名:pid:线程 |
| created_at / started_at / finished_at | timestamptz | |
| last_error | text null | 截断到 2000 字符 |

索引：

- 部分唯一索引 `(kind, qid, language) WHERE status IN ('queued','running')`：同一组合同时只有一个活跃任务。
- `(status, priority DESC, created_at)`：领任务用。

### 3.2 接口（只有这几个函数，以后换专用队列只改这一个模块）

`app/services/jobs.py`：

- `enqueue(db, kind, qid, language, priority) -> Job`
  `INSERT … ON CONFLICT (部分唯一索引) DO UPDATE SET priority = GREATEST(priority, EXCLUDED.priority) RETURNING *`。已有活跃任务时只抬高优先级，不新建。
- `claim(db, worker_id, min_priority, max_priority) -> Job | None`
  ```sql
  UPDATE generation_jobs SET status='running', attempts=attempts+1,
         lease_until=now()+interval '2 min', worker_id=:w, started_at=now()
  WHERE id = (
    SELECT id FROM generation_jobs
    WHERE priority BETWEEN :lo AND :hi
      AND (status='queued' OR (status='running' AND lease_until < now()))
      AND attempts < 3
    ORDER BY priority DESC, created_at
    LIMIT 1 FOR UPDATE SKIP LOCKED)
  RETURNING *;
  ```
- `heartbeat(db, job_id, worker_id)`：每 30 秒把 `lease_until` 延到 now()+2 分钟；如果 `worker_id` 已不是自己（被别人接走），返回 False，本线程放弃写回。
- `finish(db, job_id, worker_id, ok, error=None)`：置 `done` / `failed`；`attempts` 达到 3 且失败 → `failed`。
- `active_job(db, qid, language) -> Job | None`、`queue_position(db, job) -> int`：给内容接口用。

### 3.3 哪些工作进队列

| 工作 | 原来 | 现在 | 优先级 |
|---|---|---|---|
| 首屏生成（空作品第一次打开） | web 进程 BackgroundTasks → `maybe_trigger` | `enqueue(first_screen, qid, 请求语言, 10)` | 10 |
| 请求语言缺失的懒翻译 | 同上 | `enqueue(translate, qid, lang, 10)` | 10 |
| 首屏完成后其余语言补齐 | 首屏线程里接着跑 fanout | 首屏任务完成时，为每门缺失语言 `enqueue(translate, qid, lang, 0)`；已有人标记「在等」的语言用 10 | 0 / 10 |
| 缺图补图 | 后台线程 | `enqueue(image, qid, '', 0)` | 0 |
| 语音流式合成 | web 进程 | **不动**（必须直接流给用户） | — |
| 搜索 / 向量索引重建 | 进程内 | **不动** | — |

另一种语言的用户在生成过程中打开：`enqueue(translate, qid, 他的语言, 10)`。如果已有该语言 priority=0 的任务，只抬到 10。翻译任务开始前若首屏任务还没完成，`claim` 后检测到依赖未就绪，就放回队列（`status='queued'`，撤销本次 `attempts` 计数），本线程 sleep 5 秒再领。

### 3.4 worker 进程

- 启动命令：`python -m app.workers.generation`（同一镜像）。
- 两组线程，避免后台补齐挤占有人在等的任务：
  - `WORKER_HIGH_THREADS`（默认 8）：只领 priority ≥ 10 的任务。
  - `WORKER_LOW_THREADS`（默认 16）：只领 priority < 10 的任务。
- 没有任务时每个线程 sleep 1 秒再领（不用 LISTEN/NOTIFY；1 秒延迟在 15 秒的首屏目标里可以忽略）。
- 领任务前查预算（§4.1），用完就不领，任务留在队列里，第二天或调高上限后自动继续。生成一次、永久落库，晚一天生成成本相同，所以不设过期。
- 收到 SIGTERM：停止领新任务，等手头任务最多 5 分钟（compose `stop_grace_period: 5m`）；没做完的任务靠租约到期被别的 worker 接走。
- 生成逻辑本身（`generate_and_persist`、fanout 里的单语言翻译、补图）原样复用，只是换了调用方。纪律 37（共享实体只补缺）的约束不变。

### 3.5 被替换的旧机制

| 旧 | 新 |
|---|---|
| `attributes.lazy_lock_at`（10 分钟 TTL） | 部分唯一索引 + 租约 |
| fanout 5 分钟标记 | 部分唯一索引 |
| `_SEM` / `_FANOUT_SEM` / `_FANOUT_WORKERS` | worker 线程数配置 |
| 槽位满就放弃、清锁 | 排队 |
| FastAPI BackgroundTasks 触发 | `enqueue` |
| 段数上限 `_LAZY_DAILY_SECTION_CAP=1000` / `_FANOUT_DAILY_SECTION_CAP=3000` | 美元预算（§4.1） |

backlog 待定项 (a)「`_SEM` 2→4」由此吸收，不单独做。

### 3.6 内容接口契约（只加字段）

`GET /museums/{slug}/objects/{qid}/content` 响应：

- `generating`：语义不变，存在该 (qid, 本语言) 相关的 queued/running 任务（含本作品的 first_screen）即为 true。仍然要等这门语言整门翻完才变 false（App keepAlive 依赖它）。
- **新增** `queue_position: int | null`：排在我前面、同优先级档、`status='queued'` 的任务数；running 或无任务时为 null。
- **新增** `eta_seconds: int | null`：`(queue_position + 1) × 最近 1 小时同类任务平均耗时 ÷ max(1, 当前同档 running 任务数)`，向上取整；没有历史数据时平均耗时按 20 秒算。web 进程不需要知道 worker 配了多少线程。
- 老 App 不认识新字段，照旧看 `generating` 轮询；新 App 显示「前面还有 N 件，预计 X 秒」（需发版，另立前端任务）。
- `daily_cap` / `no_image` 等 `unavailable_reason` 语义不变。

### 3.7 清理

`done` / `failed` 保留 7 天后删除：worker 每小时执行一次 `DELETE … WHERE finished_at < now() - interval '7 days'`。

## 4. 成本上限与限流

### 4.1 成本上限（全站，存在 PostgreSQL）

- 价目表改为配置 `LLM_PRICES`（JSON：`{"模型名": [每百万输入美元, 每百万输出美元]}`；TTS 按每百万字符计入输入价）。**新模型单价在实施时从官方价目页核对后填写，不凭记忆。**
- 遇到价目表里没有的模型：按表里最贵的价格计，并发一封告警（`alert_throttled`），宁可多算不少算。
- 当日花费 = Σ 当天 `llm_usage` 中 `channel` 以 `@app` 结尾的行（tokens × 单价）。当月同理。**只计在线服务进程（用户触发）的花费**；离线脚本是人工有意执行的，单独出报表，不占预算。worker 进程同样置 `ORIGIN_SUFFIX="@app"`。
- 配置：`BUDGET_DAILY_USD=30`、`BUDGET_MONTHLY_USD=300`、`BUDGET_ALERT_RATIO=0.8`。
- 达到 80%：告警邮件。达到 100%：
  - **停**：新内容生成（worker 不领任务；`enqueue` 时直接返回 `daily_cap`，用户立刻看到提示）。
  - **不停**（用户决定 A）：识别中的 AI 兜底、语音合成。它们照常计入账本、触发告警；它们各自有每用户额度（识别次数、付费通行证），总量有上限。
- 花费查询结果在进程内缓存 30 秒，避免每次领任务都扫账本。

### 4.2 防滥用（单人，存在 Redis，fail-open 不变）

- 登录用户只按账号限额（`CAP_PER_USER`）；匿名请求按 IP 限额（`CAP_PER_IP`）。登录用户不再计入 IP 额度。
- `CAP_PER_USER`、`CAP_PER_IP`、`WEIGHT_GENERATION`、`WEIGHT_TRANSLATION` 改为配置项，默认值保持当前值。
- #1037 的「同一件同一天只扣一次」保留。
- 扣额度的时机：`enqueue` 时（和现在「拿到锁后扣」等价：已有活跃任务时不扣）。
- 吸收 backlog 待定项 (b)。

### 4.3 外部接口速率

- 不另做限速器。worker 的并发数就是调用速率的上限。
- 遇到 429：按 `Retry-After` 或指数退避（1/2/4/8 秒，最多 4 次）重试，不算任务失败；每次 429 记一条 `event_log`（§7 用）。
- 规模校核见 §9。

### 4.4 nginx 入口

`api.gomuseum.app`：`limit_req rate=10r/s burst=20` → `rate=50r/s burst=100`。吸收 backlog 待定项 (c)。

## 5. 识别与网页服务扩容

### 5.1 数据库连接

- `DB_POOL_SIZE`（默认 10）、`DB_MAX_OVERFLOW`（默认 10）改为配置项。
- prod 数据库 `max_connections` 100 → 300（PostgreSQL 容器命令参数；内存充足）。
- 按 §2 的总规则核算各容器配置；多机部署时在数据库前加 PgBouncer（届时再做）。

### 5.2 recognizer 容器

- compose 新增服务 `recognizer`：同一镜像，`uvicorn app.main:app --workers ${RECOG_WORKERS:-2}`，可选 `cpus` 上限。
- nginx 按路径分流：匹配 `/api/v1/recognize`（含 `/confirm`、`/reject`）和 `/api/v1/museums/{slug}/recognize` 的请求转给 recognizer upstream，其余转给 web。
- `RECOG_ONNX_THREADS`：单次推理的 ONNX 线程数（`intra_op_num_threads`），防止一张图吃满所有核。
- `RECOG_PRELOAD`（web 容器设 false）：web 容器启动时不预热向量索引和 ONNX 模型，省内存；万一有识别请求落到 web 容器，仍按需加载。

### 5.3 向量检索

| 档 | 做法 | 触发条件 |
|---|---|---|
| ① 本次做 | 去掉 Python 循环：馆过滤改用预存的 `museum_ids` numpy 数组 + `np.isin`；「同作品取最高分」改用预存的 qid 下标数组 + `np.maximum.at`；一次识别的全帧、画框、裁剪向量合成一个矩阵，一次 `mat @ V.T` | — |
| ② 写进设计、暂不做 | 近似检索索引（FAISS HNSW 一类） | 向量数 > 30 万（§7 监控）；上线前必须用 `recognition_photo_eval` 评测集验证不掉准 |
| ③ | 向量矩阵只在 recognizer 容器常驻 | §5.2 |

本机基准（复刻 `query_index` 的计算路径，384 维，馆过滤 = 全局识别的可见馆过滤）：

| 向量数 | 单次查询（现状） | 其中矩阵点积 |
|---|---|---|
| 2.7 万（prod 当前 26,678） | 8.3 ms | 3.4 ms |
| 10 万 | 37 ms | 15.7 ms |
| 30 万 | 91 ms | 22.3 ms |
| 100 万 | 529 ms | 254 ms |

第 ① 档验收：10 万向量、12 个查询向量，一次识别的检索总耗时 ≤ 30 ms（本机），结果与现实现逐条一致（单元测试对拍）。

## 6. 语音：第二个听众共用同一次合成

### 6.1 机制

- 「谁来合成」：Redis `SET audio:lock:{qid}:{lang}:{section} <id> NX EX 120`。抢到的人是生产者。
- 生产者在 `start_and_stream` 的 producer 里，每个片段除了放进本地 queue，也 `XADD audio:live:{qid}:{lang}:{section}`；结束时追加结束标记（成功 / 失败）；流的 TTL 为 10 分钟。
- 没抢到锁的人：从流的开头 `XRANGE` 读出已有片段，再 `XREAD BLOCK` 跟读新片段，直到结束标记；收到失败标记时抛错（与生产者的客户端行为一致，不把截断音频当完整讲解）。锁存在但流里 3 秒内没有任何片段 → 退回 409（与现在相同）。
- 落库仍由生产者的 detached task 完成，逻辑不变。

### 6.2 降级与兼容

- Redis 连不上：退回现在的数据库段锁 + 409，只是失去共享功能。
- 契约不变：第二个人原来收到 409，现在收到正常的 `audio/mpeg` 流，老 App 首播时就是这么处理的，**不用发版**。
- 数据库 `attributes.audio_locks` 只在降级路径使用。

### 6.3 资源

- prod 抽样 5 段 Google 合成的中文讲解（212–417 字）：0.91–1.97 MB。50 段同时直播 ≤ 100 MB Redis 内存，10 分钟过期。
- 同时合成数：Google 上限 100 路流式会话，按 §2 总规则核算。

## 7. 监控与扩容提醒

服务器 cron 每 5 分钟跑一次 `/opt/gomuseum/ops-check.sh`（沿用 `probe-sources.sh` 的模式）：宿主机指标在 shell 里取，其余调用 `docker exec … python scripts/ops_check.py`。超阈值就用 `ops_alert` 发邮件（同类 6 小时一封），**每封都写明处理办法**。

| 检查项 | 数据来源 | 阈值 | 处理办法（写在邮件里） |
|---|---|---|---|
| CPU | 宿主机 | 连续 15 分钟 > 70% | 看 `docker stats` 是哪类容器：识别 → 加 recognizer；生成 → 加 worker |
| 内存 / 硬盘 | 宿主机 | > 80% | 加内存；清理日志和备份 |
| 浏览 / 内容 p95 | nginx 访问日志 `rt=` | 15 分钟窗口 > 1 秒 | 加 web 进程 |
| 识别 p95 | `recognition_event.duration_ms` | 15 分钟窗口 > 3 秒 | 加 recognizer；向量数 > 30 万 → §5.3 第 ② 档 |
| 首屏等待 | 任务表（started_at − created_at，finished_at − started_at） | p95 > 25 秒，或排队 p95 > 10 秒 | 加 worker 高优先级线程；若 429 也在增加，先提外部配额 |
| 补语言积压 | 任务表 | 最老的 queued 低优先级任务 > 5 分钟 | 加 worker 低优先级线程 |
| **worker 存活** | 任务表 | 有 queued 任务，但 2 分钟内没有任何任务被领走或续租 | **最紧急**：懒生成停了，查 worker 容器 |
| 钱 | `llm_usage` × `LLM_PRICES` | 80% / 100% | 是否调高 `BUDGET_*` |
| 外部 429 | `event_log` | 15 分钟 > 20 次 | 降并发或申请配额 |
| 数据库连接 | `pg_stat_activity` | > 80% `max_connections` | 调连接配置；多机加 PgBouncer |
| 向量数 | `object_embeddings` | > 30 万 | §5.3 第 ② 档 |
| Redis 不可用 | 现有告警 | — | — |

报告命令 `scripts/ops_report.py`：各类接口 p50/p95、排队情况、当日和当月花费、各项离上限的余量。按需跑，不发日报。

## 8. staging 与 prod 隔离

- staging 的 backend / worker / postgres 容器加 `cpus` 和 `mem_limit`（合计 2 核 4G）。staging 只做功能验证。
- 真实容量测试：按小时租一台与 prod 同规格的机器，部署同一镜像跑压测脚本（复用 10-20 的 `lt.py` 场景 A–E，扩到 200 人），测完退掉。

## 9. 规模与成本估算（变量来源都列出，供独立复核）

### 9.1 识别请求率

`R_recog = U / T_recog`

- U：同时在用人数，取 200（设计容量）/ 1000（扩展目标）。
- T_recog：每人两次识别的间隔，**假设** 3–4 分钟（用户判断：一段标准讲解约 1.5 分钟，加上走路和看画）。
- 单机容量：压测 B（staging，与 prod 同一台 8 核机器，2 个 uvicorn 进程）每秒 4 次时 p95 2.1 秒，每秒 8 次时 p95 4.2 秒、CPU 满 → 达标容量约每秒 4–6 次。注意压测时 prod 和 staging 在同一台机器上。

结果：200 人约每秒 0.8–1.1 次；1000 人约每秒 4.2–5.6 次 → 需要第二台机器分担。

### 9.2 生成调用速率（对照外部上限）

`calls/min ≤ (WORKER_HIGH_THREADS + WORKER_LOW_THREADS) × c`

- c：一个线程每分钟发出的 AI 调用数。来源：10-19 实测 51 件，每件约 120 次调用、约 2 分钟（含首屏 + 9 门翻译）→ 一件全流程约 60 次/分钟。一个翻译线程只做一门语言，c 应小于 60；**取 60 作上界**。
- 上界：24 × 60 = 1440 次/分钟。外部上限：OpenAI 10,000 RPM、Anthropic 每模型 10,000 RPM、Google Chirp3-HD 200 次/分钟（只用于语音，不在此式内）。
- 120 次调用里首屏与翻译各占多少没有分项计数；实施时从任务表的耗时和 `llm_usage` 按 channel 分项补齐。

### 9.3 成本

`每日花费 = U × (60 / T_open) × p_stub × H × C_item`

- T_open：每人打开一件作品详情的间隔（分钟），**假设** 3–4 分钟（同识别；从列表点进也算打开，实际可能更频繁）。
- p_stub：打开的作品里还没有内容的比例。**未测量**。实施前从 prod 日志统计「内容请求中触发首屏生成的比例」。
- H：每天高峰等效小时数。**未测量**。
- C_item：每件全流程成本 = 120k 输入 tokens × 输入单价 + 12k 输出 tokens × 输出单价（tokens 来自 10-19 实测 51 件的平均）。单价见 §4.1，实施时核对。

brainstorm 时我粗估「200 人高峰时每天 $30 可能一两个小时就用完」，用的是旧模型单价（每件 $0.03–0.08）和 p_stub≈20–30% 的猜测，**未经验证，不作为设计依据**。设计上不依赖这个数：预算闸按实际账本工作，无论估算偏多少，都不会超支。

## 10. 配置项清单

| 配置 | 默认 | 位置 |
|---|---|---|
| `WEB_WORKERS` | 2 | compose |
| `RECOG_WORKERS` | 2 | compose |
| `RECOG_ONNX_THREADS` | 2 | `.env` |
| `RECOG_PRELOAD` | true（web 容器设 false） | `.env` / compose |
| `WORKER_HIGH_THREADS` | 8 | `.env` |
| `WORKER_LOW_THREADS` | 16 | `.env` |
| `DB_POOL_SIZE` / `DB_MAX_OVERFLOW` | 10 / 10（现为写死的 20 / 40） | `.env` |
| `max_connections` | 300 | postgres 容器命令 |
| `LLM_PRICES` | 实施时核对 | `.env` |
| `BUDGET_DAILY_USD` / `BUDGET_MONTHLY_USD` / `BUDGET_ALERT_RATIO` | 30 / 300 / 0.8 | `.env` |
| `CAP_PER_USER` / `CAP_PER_IP` / `WEIGHT_GENERATION` / `WEIGHT_TRANSLATION` | 160 / 300 / 8 / 3 | `.env` |
| nginx `limit_req` | 50r/s burst 100 | nginx 配置 |

## 11. 分阶段实施（每阶段单独写计划、单独 PR）

| 阶段 | 内容 | 依赖 | 理由 |
|---|---|---|---|
| P1 | 数据库连接配置 + `max_connections`；向量检索第 ① 档；防滥用按账号 / IP 拆分；nginx 限流 | 无 | 改动小、互相独立，先消除 B2/B3/B6/B7 |
| P2 | 任务表 + worker 容器 + 内容接口新字段 | P1（连接数） | 主体；消除 B1 |
| P3 | 价目表配置 + 美元预算 | P2（在 claim 处检查） | 消除 B8 |
| P4 | recognizer 容器 + nginx 分流 + staging 资源上限 | P1 | 消除 B4 |
| P5 | 语音直播共享 | 无 | 消除 B5 |
| P6 | ops-check / ops_report | P2、P3 | 消除 B9 |

每个阶段上 prod 前都确认 prod 上没有长任务在跑。

## 12. 测试与验收

- 单元测试：
  - `enqueue` 合并重复请求、抬高优先级；
  - `claim` 的 SKIP LOCKED 与租约过期接管；
  - 第 3 次失败后不再领取；
  - 被接管后旧 worker 的 heartbeat 返回 False、不写回；
  - 预算 80% / 100% 两侧行为（按「跨配置维度测试」：配置两侧都测）；
  - 未知模型按最贵价计并告警；
  - 向量检索新旧实现对拍；
  - 语音跟读：生产者成功 / 失败 / Redis 不可用三种情况。
- 集成测试（真 PostgreSQL，SQLite 不支持 SKIP LOCKED 和部分唯一索引语义）：两个 worker 线程并发领同一批任务，不重复执行。
- 契约测试：老 App 关心的 `generating` 在新旧实现下对同一状态给出相同值；新字段可缺省。
- 容量验收：在按小时租的同规格机器上跑 200 人混合场景，对照 §0.2 每一行。
