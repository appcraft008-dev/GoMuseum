# 弹性可扩容架构 设计

- 日期：2026-10-21
- 状态：v2，已按 Fable 独立评审修订，待用户审阅
- 来源：10-20 staging 多用户压测（backlog #1041），以及 10-20/21 的 brainstorm 逐段确认
- 评审：Fable 评审 v1，提出阻断 4 条、重要 16 条、次要 10 条，逐条处理见 §13

## 0. 目标与原则

### 0.1 原则（用户定）

> 软件架构不能成为性能瓶颈。瓶颈只允许出现在：VPS 硬件（CPU / 内存 / 硬盘）、第三方接口速率限制、成本预算。

由此推出三条可检验的要求：

1. **加资源就加容量，不改代码**：加进程、加容器、加机器都只改配置。
2. **所有容量数字都是配置项**：并发数、连接数、限流、预算都写在 `.env`，重启后生效。
3. **不上大公司架构**：不引入 Kubernetes、消息中间件、Prometheus/Grafana。能用 PostgreSQL、Redis、nginx、cron 解决的，就不加新组件。

### 0.2 性能目标（验收标准）

| 场景 | 目标 |
|---|---|
| 设计容量 | 全部馆合计 **200 人同时在用**；扩到 1000+ 人只加机器 |
| 浏览 / 搜索 / 内容接口（不含长连接接口，见 §7） | p95 ≤ 1 秒 |
| 识别 | p95 ≤ 3 秒 |
| 首屏（空作品第一次打开 → 本语言讲解出现） | 高峰时比单人多 ≤ 10 秒。单人首屏的绝对值（p50 ≤ 15 秒、p95 ≤ 25 秒）归「单人首屏提速」专题，不在本设计的验收范围内 |
| 其余 9 门语言补齐 | ≤ 5 分钟（前提：生成并发按 §9.2 的公式配置） |
| 生成过程中另一种语言的用户打开 | ≤ 60 秒（§3.3 「并进首屏」）。首屏已开跑时，等待时间 = 首屏剩余时间 + 一门语言的翻译时间，上线后实测 |
| 首次播放（现场合成） | 50 人同时首播，首包 p95 ≤ 3 秒 |
| 第二个人听正在合成的同一段 | ≤ 3 秒开始播放（用户 10-21 定：允许再合成一次，见 §6） |
| 部署 / 重启 | 不丢任务 |
| 内容生成成本 | 每天 $30、每月 $300（配置项）；达到 80% 告警，达到 100% 停止新内容生成 |
| 语音、识别兜底成本 | 各设一条告警线（配置项），只告警不停（用户 10-21 定） |

### 0.3 不在本设计范围

- **单人首屏提速**（新模型下 p50 约 22 秒，主因是接地闸重写草稿）：另开专题。
- 问答音频、作者简介音频（非流式接口，篇幅短）：不改。
- 离线 CLI 脚本（onboard / generate / translate）：不进队列，行为不变。
- VoxCPM2 定期替换懒生成音频（`audio_queue_cli` 导出 → Mac 生成 → `audio_ingest_cli` 写回）：**不受影响**。它只读写 `audio_key` / `audio_engine`，不碰本设计替换掉的锁和并发机制。
- 识别 ONNX 推理降本（int8 量化、减少裁剪、提前退出）：这是识别容量在 1000+ 人规模时的主要杠杆（§9.1），需要先用评测集验证，另开专题。
- 老版 App 拉取 5MB 全量馆包（`artworks=true`，museums.py:359-361）：新版已经不这样请求，存量会随着用户升级自然消失。§7 统计浏览 p95 时把它单独剔除。

## 1. 现状与已查实的瓶颈

| # | 瓶颈 | 证据 | 违反哪条原则 |
|---|---|---|---|
| B1 | 懒生成跑在 web 进程的后台线程里，并发数写死在代码里，且按进程计（`_SEM=2`、`_FANOUT_SEM=2`，lazy.py:24,32）；槽位满了直接放弃（lazy.py:235-245、353-355） | 压测 C：20 件同时生成，补语言只完成 10 件，8 件因槽位满被跳过 | 加机器不加生成容量；重启会丢掉正在跑的任务 |
| B2 | 数据库连接：每个进程 `pool_size=20 + max_overflow=40`（database.py:28），prod 数据库 `max_connections=100` | 2 个进程理论上可开到 120 个，已超过上限；平时实际只用 11 个 | 加进程、加容器后，高峰时整站报「连接数过多」 |
| B3 | 向量检索逐条比对，耗时随向量数线性增长；「同一作品取最高分」是 Python 循环（vector_index.py:142-146）；一次识别最多查 13 遍（全帧 1 遍 + 画框最多 4 遍 + 裁剪 8 遍）。全局识别在检索时不过滤馆（过滤在之后的 `_drop_hidden` 里做） | 本机实测，见 §5.3 | 收录越多，识别越慢 |
| B4 | 识别和浏览在同一个进程里抢 CPU；ONNX 没有设线程数（embedder.py:108） | 压测 B：40 人每 5 秒识别一次，8 核占满（779%） | 识别一忙，浏览跟着变慢 |
| B5 | 语音合成并发写死为每进程 8 路（tts_service.py:36）；段锁存在 `attributes` JSON 里，读改写会互相覆盖（lazy_audio.py:38-48）；第二个听众收到 409，要等整段合成完并落库（实测整段最长约 12 秒，另加上传时间） | 代码 | 达不到「50 人同时首播」和「第二人 3 秒」 |
| B6 | 每 IP 每天 300 的额度对登录用户也生效（lazy.py:640-644） | 压测 C 第一次跑：浏览时触发的翻译吃光了 IP 额度，20 人全部收到 daily_cap | 馆内共用 WiFi 的游客互相挤占 |
| B7 | nginx 每 IP 10 次/秒（突发 20） | nginx-api.gomuseum.app.conf:17、34 | 同上 |
| B8 | 价目表只有旧模型，新模型按 $0 计（llm_cost_report.py:9-15）；**识别兜底（recognition/vision.py:70-84）、/chat/ask（chat.py:99-115）、老接口 /content/explanation（ai_service.py）都没有记账** | 代码 | 无法做成本上限 |
| B9 | slowapi 限流的计数存在每个进程的内存里（rate_limit.py 没有配置存储后端）；游客登录限每 IP 每小时 5 次（auth.py:188-189） | 代码 | 进程越多，限流越松，各进程之间也不一致 |
| B10 | Wikidata 并发写死为每进程 2 路（wikidata_api.py:27-28） | 代码 | 多开 worker 会线性放大并发，违反 Wikimedia 调用礼仪；一次慢请求会卡住同进程里所有首屏 |
| B11 | 告警限频的记录存在进程内存里（ops_alert.py:19、31-37） | 代码 | cron 每次起新进程，限频不起作用，会反复发信 |
| B12 | 启动命令是 `alembic upgrade head && uvicorn`，并写死了 `container_name`（compose:55-57）；`init_db()` 每个进程都会执行（main.py:52） | 代码 | 多个容器会同时跑数据库迁移；`--scale` 无法使用 |
| B13 | 没有容量监控，也没有扩容提醒 | — | 不知道什么时候该加机器 |

已经可以扩容、不需要改动的部分：

- 识别「同图正在识别」的锁存在 Redis 里（service.py:174-191）。
- 搜索和向量索引是每个进程各存一份的内存副本，每进程约 0.8G。
- 用量账本 `llm_usage` 已经按「天 × 用途 × 模型」做原子累加（llm_usage.py:29-50）。
- nginx 日志已经带 `rt=`（请求耗时）。
- 领取任务用的 `UPDATE … WHERE id = (SELECT … FOR UPDATE SKIP LOCKED)`，在 READ COMMITTED 隔离级别下不会让两个进程领到同一条（评审已核实）。

## 2. 总体架构

同一个镜像、同一份代码，按启动命令和 nginx 路由分成三类容器：

```
             ┌── 识别类请求 ──→ recognizer 容器（N 个进程，可多容器、可跨机器）
用户 → nginx ┤
             └── 其他请求 ───→ web 容器（浏览、内容、语音流）
                                    │ 写任务
                                    ▼
                        PostgreSQL 任务表 generation_jobs
                                    ▲ 领任务
                                    │
                        worker 容器（生成进程，线程数可配，可多容器、可跨机器）
```

| 容器 | 负责 | 启动 | 扩容方式 |
|---|---|---|---|
| web | 浏览、搜索、内容接口（读内容、写任务）、语音流 | `alembic upgrade head && uvicorn …`（**只有它跑迁移**） | 增加 `WEB_WORKERS`，或在 nginx upstream 里加一台 |
| recognizer | 所有识别接口 | `uvicorn …`，不跑迁移，不设 `container_name` | 增加 `RECOG_WORKERS`，或在 upstream 里加一台 |
| worker | 领任务、调用 AI、写回结果 | `python -m app.workers.generation`，不跑迁移，不设 `container_name` | 增加线程数，或多开 worker 容器 |

`init_db()` 里的 `create_all` 只在 web 进程执行：加一个环境变量开关，默认开；recognizer 和 worker 关闭。

跨进程、跨机器共享的状态只放两个地方：

- **PostgreSQL**：必须可靠的数据，包括任务、内容、账本。
- **Redis**：丢了只会降级的数据，包括防滥用计数、限流计数、识别锁、Wikidata 令牌、告警限频。

**扩容总规则**（写进运维文档，告警邮件中会引用）：

1. 所有进程的数据库连接上限之和 ≤ 0.8 × `max_connections`。
2. 所有同时在途的 AI 请求之和 < 外部每分钟上限 ÷ 每路每分钟调用数。**必须把共用同一 API 账户的所有调用方都算进去**：线上 worker、web 里的问答和识别兜底、离线批量脚本（backfill 默认 8 线程）、staging。
3. 所有 web 进程的 `TTS_CONCURRENCY` 之和 < Google 同时流式会话上限（100）。
4. Wikidata 全局同时在途请求数 ≤ `WIKIDATA_CONCURRENCY`（跨进程计数，见 §4.3）。

## 3. 生成任务队列（PostgreSQL 任务表）

### 3.1 表结构

`generation_jobs`：通过 alembic 迁移新建，纯加法。

| 列 | 类型 | 说明 |
|---|---|---|
| id | bigserial PK | |
| kind | varchar(16) | `first_screen` / `translate` / `image` |
| qid | varchar(32) | 作品 |
| language | varchar(16) | `translate` 填目标语言；`first_screen` 和 `image` **固定为空串** |
| want_langs | text[] | 只有 `first_screen` 用：首屏要直接产出的语言（请求语言，加上开跑前陆续并进来的语言） |
| priority | smallint | 10 = 有人在等；0 = 没人在等 |
| status | varchar(12) | `queued` / `running` / `done` / `failed` |
| attempts | smallint, default 0 | |
| lease_until | timestamptz null | running 时有效 |
| worker_id | varchar(64) null | 主机名:pid:线程 |
| created_at / started_at / finished_at | timestamptz | |
| last_error | text null | 截断到 2000 字符 |

索引：

- 部分唯一索引 `uq_active_job (kind, qid, language) WHERE status IN ('queued','running')`。首屏任务的 language 固定为空串，所以**同一件作品同时只会有一个首屏任务**。
- `(status, priority DESC, created_at)`：领任务用。
- `(qid, kind, finished_at)`：失败冷却查询用（§3.2）。

### 3.2 接口

全部放在 `app/services/jobs.py`，以后换成专用队列只改这一个模块。

**`enqueue(db, kind, qid, language, priority, want_lang=None) -> (Job, inserted: bool)`**

1. **先读**：调用 `active_job(db, kind, qid, language)`。如果已有活跃任务，优先级不低于本次请求，且 want_lang 已包含在内，就直接返回 `(job, False)`，不写库。App 每 4 秒轮询一次，这一步避免每次轮询都写一条新的行版本。
2. **失败冷却**：同一 (kind, qid, language) 在 6 小时内有过 `failed`，就不再入队，返回 None，调用方按「暂不可用」处理（§3.6）。冷却时长由 `JOB_FAIL_COOLDOWN_H` 配置。
3. **写入**：
   ```sql
   INSERT INTO generation_jobs (kind, qid, language, want_langs, priority, status)
   VALUES (:kind, :qid, :lang, :want, :prio, 'queued')
   ON CONFLICT (kind, qid, language) WHERE status IN ('queued','running')
   DO UPDATE SET
     priority   = GREATEST(generation_jobs.priority, EXCLUDED.priority),
     want_langs = CASE WHEN generation_jobs.status = 'queued'
                       THEN ARRAY(SELECT DISTINCT unnest(generation_jobs.want_langs || EXCLUDED.want_langs))
                       ELSE generation_jobs.want_langs END
   RETURNING *, (xmax = 0) AS inserted;
   ```
   返回的 `inserted` 给 §4.2 用：只有新建任务时才扣防滥用额度。

**`claim(db, worker_id, lo, hi) -> Job | None`**

```sql
-- 先清理：租约已过期、尝试次数已满的任务置为 failed。
-- 否则它会永远卡在 running，并一直占着唯一索引。
UPDATE generation_jobs SET status='failed', finished_at=now(), last_error='lease expired after max attempts'
WHERE status='running' AND lease_until < now() AND attempts >= 3;

UPDATE generation_jobs j SET status='running', attempts=j.attempts+1,
       lease_until=now()+interval '2 min', worker_id=:w, started_at=now()
WHERE j.id = (
  SELECT c.id FROM generation_jobs c
  WHERE c.priority BETWEEN :lo AND :hi
    AND c.attempts < 3
    AND (c.status='queued' OR (c.status='running' AND c.lease_until < now()))
    -- 依赖：翻译任务要等本件首屏完成。直接在 SQL 里排除，而不是领到后再放回
    AND NOT (c.kind='translate' AND EXISTS (
          SELECT 1 FROM generation_jobs f
          WHERE f.qid=c.qid AND f.kind='first_screen' AND f.status IN ('queued','running')))
  ORDER BY c.priority DESC, c.created_at
  LIMIT 1 FOR UPDATE SKIP LOCKED)
RETURNING j.*;
```

领到翻译任务后，如果这件作品没有已发布的英文（首屏失败或内容为空），直接 `finish(failed)`，不放回队列。

**`still_mine(db, job_id, worker_id) -> bool`**

- 每生成完一段就调用一次。
- 生成过程是边做边写库、每段单独提交的，所以没法等全部做完再决定「不写回」。
- 租约被别的进程接管后，旧线程在段与段之间发现自己已不再持有任务，就中止。**接管后最多会重复生成一段**。这是已知代价，写明在此，不再进一步处理。

**`heartbeat(db, job_id, worker_id) -> bool`**

- 每 30 秒把 `lease_until` 延长到 now()+2 分钟。
- 更新条件是 `worker_id=:w AND status='running'`。返回 False 表示任务已被接管。

**`finish(db, job_id, worker_id, ok, error=None)`**

- 只在 `worker_id=:w AND status='running'` 时生效。
- 成功 → 置 `done`。
- 失败且 attempts < 3 → 放回 `queued`，等下次再领。
- 失败且 attempts ≥ 3 → 置 `failed`。

**`release(db, job_id, worker_id)`**：部署停机时用，见 §3.4。

**`active_job` / `queue_position`**：给内容接口用。

### 3.3 哪些工作进队列

| 工作 | 原来 | 现在 | 优先级 |
|---|---|---|---|
| 首屏生成（空作品第一次被打开） | web 进程 BackgroundTasks → `maybe_trigger` | `enqueue(first_screen, qid, '', 10, want_lang=请求语言)` | 10 |
| 首屏期间另一种语言的用户打开 | 等首屏完成后在补语言阶段插队 | 首屏还在 `queued`：把他的语言并进 `want_langs`，首屏直接一起产出。首屏已在 `running`：`enqueue(translate, qid, 他的语言, 10)`，首屏一完成就会被领走 | 10 |
| 请求语言缺失的懒翻译（已有内容的作品） | BackgroundTasks | `enqueue(translate, qid, lang, 10)` | 10 |
| 首屏完成后补齐其余语言 | 首屏线程里接着跑 fanout | 每门缺失的语言各 `enqueue(translate, qid, lang, 0)`；已有人在等的语言用 10。**这一步和首屏的 `finish(done)` 在同一个事务里提交**（§3.6） | 0 / 10 |
| 缺图补图 | 后台线程 | `enqueue(image, qid, '', 0)` | 0 |
| 语音流式合成 | web 进程 | **不动**（声音必须直接流给用户） | — |
| 搜索 / 向量索引重建 | 进程内 | **不动** | — |

**共享作者行（纪律 37）：**

- 翻译任务调用 `translate_object_language(include_bio=False)`，不再顺带写作者简介。
- 作者简介改用单条原子 SQL 补写，只补缺、不覆盖（`bio` 是 JSONB，见 models/artist.py:23）：
  ```sql
  UPDATE artists SET bio = COALESCE(bio,'{}'::jsonb) || jsonb_build_object(:lang, :txt)
  WHERE qid = :q AND NOT (COALESCE(bio,'{}'::jsonb) ? :lang);
  ```
- 作者简介的翻译放在首屏任务里做（保留现在的并行写法），或者作为独立的 translate 子步骤，但都必须走这条 SQL。
- 现在的 `fill_artist_bio` 是「读出 → 修改 → 写回」（backfill.py:164-168），worker 并发时会丢掉别人刚写的语言，这次一并改掉。离线脚本也会因此受益。

### 3.4 worker 进程

- 启动命令：`python -m app.workers.generation`。
- 启动时设置 `llm_usage.ORIGIN_SUFFIX = "@app"`，并调用 `audio_guard.set_record_only()`。这两项与 web 进程一致，因为生成逻辑原本就在 web 进程里跑，行为要保持不变。
- 线程分两组，避免后台补齐挤占有人在等的任务：
  - `WORKER_HIGH_THREADS`：只领 priority ≥ 10 的任务。
  - `WORKER_LOW_THREADS`：只领 priority < 10 的任务。
  - 默认值按 §9.2 的公式定，初始为 8 / 32。
- 没有任务时每个线程 sleep 1 秒再领。不用 LISTEN/NOTIFY，1 秒的延迟在首屏时长里可以忽略。
- 领任务前先查内容生成预算（§4.1）。预算用完就不领，任务留在队列里，等第二天或调高上限后自动继续。生成结果一次落库、永久保存，晚一天生成成本相同，所以任务不设过期。
- 任务循环捕获 **BaseException**。`AudioLossBlocked` 继承的是 BaseException，`except Exception` 接不住，线程会静默退出。捕获后把任务置为 `failed`（不重试）并发告警，线程继续领下一个任务。
- 收到 SIGTERM 时：
  1. 停止领新任务。
  2. 等手头任务做完，最多 4 分钟。
  3. 到时仍未做完的，主动 `release`（`status='queued', attempts=attempts-1, worker_id=NULL`），不必让别人干等 2 分钟的租约到期。
  4. 退出。compose 设置 `stop_grace_period: 5m`。
- 每小时清理一次：`DELETE … WHERE status IN ('done','failed') AND finished_at < now() - interval '7 days'`。
- **回滚开关** `LAZY_EXECUTOR=queue|inprocess`，默认 `queue`。设为 `inprocess` 时，内容接口回到原来的 `maybe_trigger` 路径。P2 上线后观察两周，没有问题再删除旧路径。
- 生成逻辑本身（`generate_and_persist`、单语言翻译、补图）原样复用，只是换了调用方。纪律 37 不变。

### 3.5 被替换的旧机制

| 旧 | 新 |
|---|---|
| `attributes.lazy_lock_at`（10 分钟 TTL） | 部分唯一索引 + 租约 |
| fanout 的 5 分钟标记 | 部分唯一索引 |
| `_SEM` / `_FANOUT_SEM` / `_FANOUT_WORKERS` | worker 线程数配置 |
| 槽位满就放弃并清锁 | 排队 |
| FastAPI BackgroundTasks 触发 | `enqueue` |
| 按段数计的上限 `_LAZY_DAILY_SECTION_CAP=1000` / `_FANOUT_DAILY_SECTION_CAP=3000` | 美元预算（§4.1，与 P2 同时上线，见 §11） |

backlog 待定项 (a)「`_SEM` 2→4」被这一节吸收，不再单独做。

### 3.6 内容接口契约（只加字段）

`GET /museums/{slug}/objects/{qid}/content`

**`generating`：语义不变。**

- 存在与 (qid, 本语言) 相关的 queued 或 running 任务时为 true。相关任务包括本作品的 first_screen 和本语言的 translate。
- 仍然要等这门语言整门翻译完，才变成 false（App 的 keepAlive 依赖这一点，lazy.py:89-93）。
- **不能出现空窗**：首屏的 `finish(done)` 和各语言 translate 的 `enqueue` 在同一个事务里提交，所以中间任何时刻其他语言的 `generating` 都不会提前变成 false。由契约测试守住（§12）。

**几种特殊状态：**

- **预算停止期间**：只在排队、还没开跑的任务，`generating` 返回 false，同时返回 `unavailable_reason="daily_cap"`。否则老 App 每 4 秒轮询、最多 225 次，会空转 15 分钟，却始终看不到提示（guide_page.dart:140-144、184-189）。
- **失败**：任务 `failed` 后 `generating=false`，表现与现在 stub 的「待完善」一致。6 小时冷却期内不会再次入队（§3.2）。

**新增 `queue_position: int | null` 和 `eta_seconds: int | null`**（用户 10-20 定「排队位置 A」）：

- `queue_position`：排在我前面的、同优先级档、`status='queued'` 的任务数。
- `eta_seconds = (queue_position + 1) × 最近 1 小时同类任务的平均耗时 ÷ max(1, 当前同档 running 任务数)`，向上取整。没有历史数据时，平均耗时按 20 秒算。
- 这两个字段只有新版 App 用得上。**放在 P2b，和前端的排队提示一起排期**，避免现在就多一次没人用的计数查询。
- 老 App 不认识这两个字段，照旧看 `generating` 轮询。

`daily_cap`、`no_image` 等 `unavailable_reason` 的语义都不变。

## 4. 成本上限与限流

### 4.1 成本上限

**补记账**：识别兜底（recognition/vision.py:70-84）、/chat/ask（chat.py:99-115）、老接口 /content/explanation（ai_service.py）都补上 `record_llm_usage`。

**价目表**：改成配置项 `LLM_PRICES`，格式为 JSON：`{"模型名": [每百万输入美元, 每百万输出美元]}`。TTS 按每百万字符的价格计入「输入价」。

- **新模型单价在实施时从官方价目页核对后填写，不凭记忆。**
- 遇到价目表里没有的模型：按表里最贵的价格计算并发告警，宁可多算，不少算。

**三笔账分开**（用户 10-21 定）：

| 账 | 计入的 channel（只计 `@app` 后缀，即线上服务进程） | 到 100% 时 | 配置 |
|---|---|---|---|
| 内容生成 | generate、gate、translate、qa、names、intro、vision（富化看图） | **停**：worker 不领任务；`enqueue` 直接返回 `daily_cap`，用户立刻看到提示 | `BUDGET_GEN_DAILY_USD=30`、`BUDGET_GEN_MONTHLY_USD=300` |
| 语音 | tts | 只告警 | `ALERT_TTS_DAILY_USD` |
| 识别兜底 + 问答对话 | recog、chat | 只告警 | `ALERT_RECOG_DAILY_USD` |

- 三笔账都在花费达到 `BUDGET_ALERT_RATIO=0.8` 时告警。
- 识别兜底补记账时，channel 用 `recog`，与富化用的 `vision` 区分开。
- 离线脚本由人工执行，不计入预算，单独出报表。
- 「当天」统一按 **UTC** 计算。`llm_usage` 现在用的是 `date.today()`，即容器本地时区，要改成 UTC 日期，与 lazy.py 的日上限保持一致。
- 不做缓存：`llm_usage` 每天只有几十行，直接求和即可。
- **超支上限（如实写明）**：越线那一刻还在运行的任务会继续花钱。最多 ≈ 高优先级线程数 × 首屏成本 + 低优先级线程数 × 单语言成本，按默认配置约相当于 5–8 件全流程的费用。

### 4.2 防滥用（单人，存 Redis，fail-open 不变）

| 身份 | 计哪几层额度 |
|---|---|
| 正式账号（非游客） | 只按账号计，`CAP_PER_USER` |
| 游客账号（`is_guest`） | 账号和 IP 两层都计（游客可以换 device_id 批量注册，如果去掉 IP 这层，就成了刷量入口） |
| 匿名 | 按 IP 计，`CAP_PER_IP` |

- `CAP_PER_USER`、`CAP_PER_IP`、`WEIGHT_GENERATION`、`WEIGHT_TRANSLATION` 改为配置项，默认值保持当前数值。
- 保留 #1037 的「同一件作品同一天只扣一次」。
- 扣额度的时机：`enqueue` 返回 `inserted=True` 时才扣。合并进已有任务的请求不扣。
- **slowapi 的计数改存 Redis**（`storage_uri`），进程数变化不再影响限流的松紧。
- 游客登录限额改为配置项 `GUEST_LOGIN_RATE`，默认调高到每 IP 每小时 30 次。馆内 WiFi 和运营商共享 IP 下，5 次不够用。
- 这一节吸收 backlog 待定项 (b)。

### 4.3 外部接口速率

**大模型**：不另做限速器，worker 并发数就是调用上限。§9.2 校核过，离外部上限还差一个数量级。

- 遇到 429：按 `Retry-After` 等待，或按 1/2/4/8 秒退避，最多 4 次。
- 429 不算任务失败；每次记一条 `event_log`。

**Wikidata**：

- 把进程内的 `_GATE = BoundedSemaphore(2)` 换成跨进程令牌：Redis `INCR wikidata:inflight`，加 TTL 兜底。
- 上限 `WIKIDATA_CONCURRENCY`，默认 4，等于现在 prod 的 2 进程 × 2。
- Redis 连不上时退回进程内信号量。

**语音**：用配置项 `TTS_CONCURRENCY`（每进程，默认 16）替换写死的 `_EXECUTOR = ThreadPoolExecutor(max_workers=8)`（tts_service.py:36）。

### 4.4 nginx 入口

`api.gomuseum.app`：`limit_req rate=10r/s burst=20` 改为 `rate=50r/s burst=100`。这一节吸收 backlog 待定项 (c)。

## 5. 识别与网页服务扩容

### 5.1 数据库连接

- `DB_POOL_SIZE` / `DB_MAX_OVERFLOW` 改为配置项。
  - web 和 recognizer 默认 20 / 10。依据：线程池有 40 个线程，等识别锁时最长要占用连接 90 秒。
  - worker 由代码**自动计算**为 `HIGH + LOW + 2`（心跳另需连接），overflow 为 0，不用手动填写。
- prod `max_connections` 从 100 调到 300，在 PostgreSQL 容器的启动参数里改。
- 默认配置下的连接总数：web 2×30 + recognizer 2×30 + worker (40+2) + 脚本和 cron 约 5，合计约 167，低于 0.8 × 300 = 240。多机部署时再加 PgBouncer。

### 5.2 recognizer 容器

**容器**：compose 新增 `recognizer` 服务。镜像相同，启动命令为 `uvicorn app.main:app --workers ${RECOG_WORKERS:-2}`，可选设置 `cpus` 上限。

**nginx 路由**：

- 精确匹配以下两条：
  - `location = /api/v1/recognize`
  - `location ~ ^/api/v1/museums/[^/]+/recognize$`
- 新的 location 要复制 `limit_req` 和 `proxy_read_timeout 120s`。
- 配置 `proxy_next_upstream error timeout`，并把 web 设为 backup：recognizer 挂了就回落到 web。
- 以下几个接口很轻，留在 web：`/recognize/confirm`、`/reject`，已下线返回 410 的 `/recognition/recognize`，以及 `/feedback/recognition-photo`。

**配置项**：

- `RECOG_ONNX_THREADS`：单次推理用的 ONNX 线程数（`intra_op_num_threads`），防止一张图吃满所有核。
- `RECOG_PRELOAD`：web 容器设为 false，启动时不预热向量索引和 ONNX 模型，省内存。识别请求万一回落到 web，仍会按需加载。

### 5.3 向量检索

| 档 | 做法 | 什么时候做 |
|---|---|---|
| ① | 「同一作品取最高分」改用预存的 qid 下标数组 + `np.maximum.at`；按馆过滤改用 numpy 数组 + `np.isin`；一次识别的全帧、画框、裁剪向量合成一个矩阵，一次 `mat @ V.T` 算完 | P1 |
| ② | 近似检索索引（FAISS HNSW 一类） | 向量数超过 30 万时（§7 监控）。上线前必须用 `recognition_photo_eval` 评测集验证准确率不下降 |
| ③ | 向量矩阵只在 recognizer 容器里常驻 | P3 |

本机基准（复刻 `query_index`，384 维）。「有过滤」对应单馆识别；全局识别只走「无过滤」这一列。

| 向量数 | 单次查询（无过滤） | 单次查询（有过滤） | 其中矩阵点积 |
|---|---|---|---|
| 2.7 万（prod 当前 dinov3-vits16 为 26,678 条；代码注释里的「4 万」是两个模型的向量加在一起） | 8.3 ms | 1.6 ms | 3.4 ms |
| 10 万 | 37 ms | 6.4 ms | 15.7 ms |
| 30 万 | 91 ms | 19 ms | 22.3 ms |
| 100 万 | 529 ms | 77 ms | 254 ms |

当前规模下，一次识别的检索最多约 13 × 8 ms ≈ 0.1 秒，CPU 的大头在最多 13 次 ONNX 推理上。所以第 ① 档解决的是「作品越多越慢」，**不解决 CPU 占满（B4）**。B4 靠 §5.2 的拆分来解决，长期靠 §0.3 的推理降本。

第 ① 档的验收标准：10 万向量、13 个查询向量时，一次识别的检索总耗时 ≤ 30 ms（本机）；新旧实现在同一输入上的排序结果逐条一致（单元测试对拍）。

## 6. 语音：第二个听众（用户 10-21 定：允许再合成一次）

- **做法**：不共享合成流。第二个人进来时，如果这一段还没有 `audio_key`，就**自己再发起一次流式合成**。首包时间与首播相同（压测 D 实测 1.6–1.9 秒）。
- **落库只补缺**：`persist_section_audio` 改为条件写入，`UPDATE … SET audio_key=:k, audio_engine=:e WHERE … AND audio_key IS NULL`。
  - 后完成的那份不会覆盖先完成的。它上传到 R2 的对象成了孤儿，由现有的孤儿 GC 清理。
  - 顺带堵住了一个小空隙：VoxCPM2 写回的音频，可能被同时在进行的现场合成覆盖。
- **去掉段锁**：流式接口不再返回 409，也不再读写 `attributes.audio_locks`。非流式的 `/audio`（问答、作者简介）保持原样。
- **代价**：两个人在约 12 秒内播放同一段还没缓存的音频时，会多合成一次，约 $0.03。这笔钱计入语音账，只告警。
- **契约不变**：第二个人原来收到 409，现在收到正常的 `audio/mpeg` 流。老 App 首播时就是这样处理流的，**不用发新版**。
- **并发**：受 `TTS_CONCURRENCY`（§4.3）和扩容总规则第 3 条约束。

## 7. 监控与扩容提醒

服务器上用 cron 每 5 分钟跑一次 `/opt/gomuseum/ops-check.sh`，写法沿用 `probe-sources.sh`：宿主机指标在 shell 里直接取，其余指标通过 `docker exec … python scripts/ops_check.py` 获取。

- **告警限频改存 Redis**：`SET alert:{key} 1 NX EX 21600`，即全站同一类告警 6 小时只发一封。Redis 连不上时退回进程内限频。
- 每封告警邮件都写明处理办法。
- cron 脚本按 compose 服务名找容器，不写死容器名。

| 检查项 | 数据来源 | 阈值 | 处理办法（写在邮件里） |
|---|---|---|---|
| CPU | 宿主机 | 连续 15 分钟 > 70% | 用 `docker stats` 看是哪类容器：识别占用高 → 加 recognizer；生成占用高 → 加 worker |
| 内存 / 硬盘 | 宿主机 | > 80% | 加内存；清理日志和备份 |
| 浏览 / 内容接口 p95 | nginx `rt=`，**剔除** `/audio/stream`、识别接口、`artworks=true` | 15 分钟窗口 > 1 秒 | 加 web 进程 |
| 识别 p95 | `recognition_event.duration_ms` | 15 分钟窗口 > 3 秒 | 加 recognizer；向量数超过 30 万时上 §5.3 第 ② 档 |
| 首屏排队 | 任务表 `started_at − created_at`（priority 10） | p95 > 10 秒 | 加 `WORKER_HIGH_THREADS`；如果 429 同时在增加，先提外部配额 |
| 补语言积压 | 任务表 | 最老的低优先级 queued 任务等了 > 5 分钟 | 加 `WORKER_LOW_THREADS`，或多开 worker 容器 |
| **worker 存活** | 任务表 | 有 queued 任务，但 2 分钟内没有任何任务被领走或续租 | **最紧急**：懒生成已经停了，立即查 worker 容器 |
| 失败率 | 任务表 | 1 小时内 failed > 10% | 查看 `last_error` |
| 三笔账 | `llm_usage` × `LLM_PRICES` | 内容生成 80% / 100%；语音、识别达到各自的告警线 | 决定是否调高预算或告警线 |
| 外部 429 | `event_log` | 15 分钟内 > 20 次 | 降低并发，或申请提高配额 |
| 数据库连接 | `pg_stat_activity` | > 80% `max_connections` | 调整连接配置；多机部署时加 PgBouncer |
| 向量数 | `object_embeddings`（当前模型） | > 30 万 | 上 §5.3 第 ② 档 |
| Redis 不可用 | 现有告警 | — | — |

**「worker 存活」这项告警和 P2 一起上线**，不等 P4。

另提供报告命令 `scripts/ops_report.py`：一次列出各类接口的 p50/p95、排队情况、三笔账的当日和当月花费，以及每项离上限还有多少余量。按需运行，不发日报。

## 8. staging 与 prod 隔离

- staging 的 backend、worker、postgres 容器加 `cpus` 和 `mem_limit` 限制，合计 2 核 4G。staging 只用来做功能验证。
- 真实容量测试：按小时租一台与 prod 同规格的机器，部署同一个镜像，跑压测脚本（复用 10-20 的 `lt.py` 场景 A–E，扩到 200 人），测完退掉。

## 9. 规模与成本估算（列出每个变量的来源）

### 9.1 识别

`R_peak = k × U / T_recog`

| 变量 | 取值 | 来源 |
|---|---|---|
| U | 200 / 1000 | 设计容量 |
| T_recog | 3–4 分钟 | **假设**（用户判断：一段标准讲解约 1.5 分钟，再加上走路和看画的时间） |
| k（高峰 / 平均） | 2–3 | **假设**（旅行团集体进馆、开门时段）。有真实流量后，从 `recognition_events` 按每分钟的最大值除以平均值实测 |
| 单次识别成本 | ≤ 0.97 核·秒 | 压测 B：7.79 核 ÷ 每秒 8 次。这是上限，因为同机还在跑 prod。没有分路径统计：快路径只推理 1 次，画框加裁剪最多推理 13 次；AI 兜底 CPU 占用少，但每次占住一个线程 3–10 秒 |

结果：

- **200 人**：平均每秒 0.8–1.1 次，高峰每秒 1.7–3.3 次，需要**约 4–6 核专门跑识别**。这台机器上还有 web、worker、两套数据库和 staging，余量偏紧。P3 拆出 recognizer 后先给它设 `cpus` 配额，再观察实际负载。
- **1000 人**：高峰每秒 8–17 次，需要 **2–4 台同规格机器专门跑识别**，或者先做 §0.3 的推理降本。

### 9.2 生成：需要多少线程、会不会撞到外部上限

10-19 的 prod 实测数据：取 `llm_usage` 中 `@app` 后缀的记录，即你那天测试的 51 件作品。

| channel | 模型 | 调用次数 | 输入 tokens | 输出 tokens |
|---|---|---|---|---|
| gate | claude-haiku-5-5 | 333 | 1,582,553 | 6,355 |
| generate | claude-haiku-5-5 | 127 | 682,677 | 63,548 |
| qa | claude-haiku-5-5 | 51 | 290,127 | 21,467 |
| translate | gpt-6-luna | 5,610 | 3,424,283 | 509,706 |
| vision | claude-sonnet-5-5 | 50 | 117,080 | 13,372 |
| 合计 | | 6,171 | 6.10M | 0.61M |

按 51 件平均，每件约：

- 121 次调用。其中**首屏约 11 次**；**翻译约 110 次**，平均每门语言约 12 次。
- 输入约 120k tokens，输出约 12k tokens。

**需求侧（线程数由此推出）**

计算公式：

- 每分钟要生成的件数：`λ = min(U × p_stub / T_open, 预算允许的速率)`
- 预算允许的速率 = `BUDGET_GEN_DAILY_USD ÷ C_item ÷ (H × 60)`
- 需要的高优先级线程数 ≈ `λ × T_first / 60 × k`
- 需要的低优先级线程数 ≈ `λ × 9 × T_lang / 60`

其中：

- T_first ≈ 20 秒（prod 实测 p50 为 15–22 秒）。
- T_lang **未实测**。评审按「补语言 4 线程跑满」推算约 44 秒，P2 上线后用任务表的实测值替换。

两个例子：

- **例 1**（p_stub=0.1、U=200、T_open=3.5 分钟）：λ≈5.7 件/分钟，需要高优先级约 6 个线程、低优先级约 38 个线程。
- **例 2**（预算先卡住，C_item 为 $0.05–0.3，H=4）：λ≈0.4–2.5 件/分钟，需要低优先级 3–17 个线程。

**默认值取 HIGH=8、LOW=32**。等 p_stub 和 C_item 有了实测值，再按公式调整。

**供给侧（会不会撞到外部上限）**

- 一个线程同时最多有 2–3 路 AI 调用在途：首屏内部还有 5 线程的取数池和 1 线程的问答池（pipeline.py:164、576）。
- 总上界：40 线程 × 3 路 × 每路每分钟最多 60 次（单次调用至少 1 秒）= 7,200 次/分钟，分摊到 OpenAI 和 Anthropic 两家。
- 翻译只调 OpenAI：32 × 60 = 1,920 次/分钟，低于 10,000 次/分钟的上限。
- tokens 用量：按每次约 1k 输入、100 输出估算，远低于每分钟 10M 输入、2M 输出的上限。
- **结论：大模型的速率上限不是瓶颈，Wikidata 会先成为瓶颈（§4.3）。**

### 9.3 成本

`内容生成每日花费 = Σ_模型 (每件在该模型上的输入 tokens × 输入单价 + 输出 tokens × 输出单价) × 每日生成件数`

- 每件在各模型上的 tokens：取 §9.2 的表格除以 51。单价在实施时核对（§4.1）。
- 每日生成件数 ≤ 当天被打开过的**不同** stub 作品数。p_stub 会随内容补齐而下降：上新馆的头几天偏高，之后越来越低。
- 另外两项要计入：已有作品的按请求翻译，以及失败重试（最多 3 次，每次只花部分成本）。

`语音每日花费 = 每日未缓存的首播段数 × 平均字数 × $30/百万字`

- 评审给的粗估：如果 200 人全是付费用户、30% 的播放没有缓存，约 $70/小时。这是**假设，未经验证**。实际要乘以付费用户比例；而且随着音频落库和 VoxCPM2 替换，未缓存的比例会下降。
- 10-19 实测（只有你一个用户）：33 次合成，共 16,752 字。

brainstorm 时我粗估过「$30 在高峰时一两个小时就会用完」，当时用的是旧模型单价和一个没有依据的 p_stub。**这个估算未经验证，不作为设计依据。** 设计本身不依赖任何估算：三笔账都按实际账本运转，最多超支多少见 §4.1。

### 9.4 语音

- 抽样大小：prod 上 5 段 Google 合成的中文讲解（212–417 字），音频大小 0.91–1.97 MB。
- 配额：50 路同时会话 < 上限 100 路；每分钟 50 次 < 上限 200 次。
- 1000 人时，未缓存的比例要 ≤ 30%，否则每分钟请求会超过 200 次。这个比例会随着音频落库和 VoxCPM2 替换自然下降；靠 §7 的 429 告警盯住。

### 9.5 数据库连接

- 现状：2 个进程 × (20 + 40) = 120，已超过上限 100。
- 按新的默认配置约 167 个，低于 240（见 §5.1）。

## 10. 配置项清单

| 配置 | 默认 | 位置 |
|---|---|---|
| `WEB_WORKERS` / `RECOG_WORKERS` | 2 / 2 | compose |
| `RECOG_ONNX_THREADS` | 2 | `.env` |
| `RECOG_PRELOAD` | true（web 容器设 false） | `.env` / compose |
| `INIT_DB_ON_START` | true（recognizer / worker 设 false） | compose |
| `WORKER_HIGH_THREADS` / `WORKER_LOW_THREADS` | 8 / 32 | `.env` |
| `LAZY_EXECUTOR` | queue | `.env` |
| `JOB_FAIL_COOLDOWN_H` | 6 | `.env` |
| `DB_POOL_SIZE` / `DB_MAX_OVERFLOW` | 20 / 10（worker 自动计算） | `.env` |
| `max_connections` | 300 | postgres 容器命令 |
| `LLM_PRICES` | 实施时核对 | `.env` |
| `BUDGET_GEN_DAILY_USD` / `BUDGET_GEN_MONTHLY_USD` | 30 / 300 | `.env` |
| `ALERT_TTS_DAILY_USD` / `ALERT_RECOG_DAILY_USD` | 实施时按实测基线定 | `.env` |
| `BUDGET_ALERT_RATIO` | 0.8 | `.env` |
| `CAP_PER_USER` / `CAP_PER_IP` / `WEIGHT_GENERATION` / `WEIGHT_TRANSLATION` | 160 / 300 / 8 / 3 | `.env` |
| `GUEST_LOGIN_RATE` | 30/hour | `.env` |
| `WIKIDATA_CONCURRENCY` | 4 | `.env` |
| `TTS_CONCURRENCY` | 16 | `.env` |
| nginx `limit_req` | 50r/s burst 100 | nginx 配置 |

## 11. 分阶段实施（每个阶段单独写计划、单独提 PR）

| 阶段 | 内容 | 依赖 |
|---|---|---|
| P1 | 数据库连接配置和 `max_connections`；向量检索第 ① 档；防滥用按三档身份拆分；slowapi 改存 Redis；nginx 限流放宽；`TTS_CONCURRENCY` 配置化；语音第二听众允许重新合成，落库改为条件写入（§6） | 无 |
| P2 | 补记账、价目表配置、三笔账；任务表和 worker 容器；作者简介原子补写；Wikidata 跨进程令牌；回滚开关；**worker 存活告警**；告警限频改存 Redis | P1 |
| P2b | `queue_position` / `eta_seconds` | P2；与前端排队提示一起排期 |
| P3 | recognizer 容器、nginx 分流、staging 资源上限 | P1 |
| P4 | 其余 ops-check 检查项，以及 ops_report | P2 |

v1 原本把美元预算单独放在 P3，现在并入 P2。原因是 P2 拿掉按段数计的上限时，新的全站上限必须同时生效，而 worker 的生成能力会比现在高得多。语音简化后工作量很小，并入 P1。

每个阶段上 prod 之前，先确认 prod 上没有长任务在跑。

## 12. 测试与验收

单元测试和集成测试都用真实的 PostgreSQL。SQLite 不支持 SKIP LOCKED、部分唯一索引的 ON CONFLICT 推断，也不支持 JSONB 运算。

**任务表**

- `enqueue`：
  - 重复请求会合并，并抬高优先级、合并 want_langs；
  - 只读命中时不写库；
  - 失败冷却期内不再入队。
- 两个不同语言的首屏请求只产生一条任务。
- `claim`：
  - 在 SKIP LOCKED 下，两个线程不会领到同一条任务；
  - 租约过期后，任务可以被别的线程接管；
  - 已试满 3 次且租约过期的任务被置为 failed，不会卡住。
- 依赖：
  - 首屏未完成时，翻译任务不会被领走，也不占线程；
  - 首屏失败后，翻译任务直接置为 failed。
- 任务被接管后，旧线程调用 `still_mine`、`heartbeat`、`finish`，都返回 False 或不生效。
- 收到 SIGTERM 时，`release` 退还本次 attempts。
- worker 线程遇到 BaseException（`AudioLossBlocked`）不会退出。

**纪律 37**

- 9 个翻译任务并发给同一作者补 bio，最终 9 门语言都在，原有语言没有被覆盖。

**预算**（按「跨配置维度测试」原则，配置的两侧都要测）

- 内容生成到 80% 和到 100% 时的行为。
- 语音、识别超过告警线时只告警、不停。
- 价目表里没有的模型按最贵价计算并告警。
- 按 UTC 切分日期。

**其他**

- 向量检索：新旧实现对拍。
- 语音：两个人并发首播，都能拿到音频流；只有一份落库，后完成的不覆盖先完成的。

**契约测试**

- 用状态机走一遍完整流程：首屏 queued → running → done（同时插入翻译任务）→ 翻译 running → done。每一步都检查各语言的 `generating`，**任何一步都不能提前变成 false**。
- 预算停止时，排队中的任务返回 `generating=false` 加 `daily_cap`。
- 新增字段可以缺省。

**容量验收**

- 在按小时租的同规格机器上跑 200 人混合场景，逐行对照 §0.2。

## 13. 评审处理记录（v1 → v2）

| 评审条目 | 处理 |
|---|---|
| A1 ON CONFLICT 推断失败、列名歧义 | 改，§3.2 |
| A2 试满 3 次的任务卡在 running | 改，claim 前先清理，并新增 release，§3.2、§3.4 |
| A3 同一件作品出现两个首屏任务 | 改，首屏的 language 固定为空串，新增 want_langs，§3.1、§3.3 |
| A4 TTS 并发写死 | 改，新增 `TTS_CONCURRENCY`，§4.3 |
| B1 依赖未就绪时反复放回、死循环 | 改，在 SQL 里直接排除，§3.2 |
| B2 首屏完成到翻译入队之间有空窗 | 改，同一事务提交，并加契约测试，§3.6、§12 |
| B3 漏记账、三笔账、超支上限 | 改，补记账；三笔账分开（用户定）；去掉缓存；如实写明超支上限，§4.1 |
| B4 worker 进程的音频损失闸和 BaseException | 改，调用 set_record_only，并捕获 BaseException，§3.4 |
| B5 作者 bio 丢更新 | 改，include_bio=False，改用原子 SQL，§3.3 |
| B6 预算停止后 App 空转 | 改，§3.6 |
| B7 每次轮询都写库 | 改，先读后写，§3.2 |
| B8 游客账号刷量、slowapi 计数在进程内 | 改，按三档身份计额度，slowapi 改存 Redis，§4.2 |
| B9 Wikidata 并发写死 | 改，换成跨进程令牌，§4.3 |
| B10 告警限频在进程内 | 改，限频改存 Redis，§7 |
| B11 语音 Redis Stream 方案的 6 个问题 | 改方案：允许重新合成，落库改为条件写入（用户定），§6 |
| B12 连接池偏小 | 改，§5.1 |
| B13 分阶段顺序 | 改，预算和存活告警并入 P2，新增回滚开关，§11 |
| B14 多容器同时迁移、container_name 写死 | 改，§2 |
| B15 被接管后旧线程停不下来 | 改，每段之间检查 still_mine，并写明最多重复一段，§3.2 |
| B16 漏算共用账户的调用方；线程数 ≠ 并发数 | 改，扩容总规则第 2 条，§9.2 |
| C1 §0.2 与 §0.3 矛盾 | 改，首屏目标改为相对单人的增量，§0.2 |
| C2 另一种语言 ≤60 秒难以保证 | 改，并进首屏的 want_langs，§3.3 |
| C3 B3 的证据有偏差 | 改，次数改为 13 遍；注明全局识别不过滤；注明 4 万是两个模型之和；说明第 ① 档不解决 CPU 问题，§1、§5.3 |
| C4 浏览 p95 应排除长连接 | 改，§7 |
| C5 失败后怎么办 | 改，新增 6 小时冷却；attempts < 3 时放回队列，§3.2 |
| C6 queue_position 暂时没人用 | 部分采纳：用户已定要做，挪到 P2b 和前端一起排期，§3.6 |
| C7 nginx 路由写法和回落 | 改，§5.2 |
| C8 「15–30 秒」与代码注释不符 | 改，按「约 12 秒 + 上传时间」，§1 |
| C9 时区不一致 | 改，统一用 UTC，§4.1 |
| C10 老 App 拉取全量馆包 | 记入「不在本设计范围」，§7 统计时剔除，§0.3 |
| §9.1 高峰系数；1000 人需 2–4 台 | 改，§9.1 |
| §9.2 线程数应从需求推出 | 改，用 10-19 的实测分项推出公式，§9.2 |
| §9.3 成本按模型拆分、补上语音 | 改，§9.3 |
