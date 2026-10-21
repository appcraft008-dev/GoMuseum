# 弹性可扩容架构 设计

- 日期：2026-10-21
- 状态：v7。已按 Fable 六轮独立评审修订，待用户审阅
- 来源：10-20 staging 多用户压测（backlog #1041），以及 10-20/21 brainstorm 的逐段确认
- 评审处理记录：v1→v2 见 §13.1，v2→v3 见 §13.2，v3→v4 见 §13.3，v4→v5 见 §13.4，v5→v6 见 §13.5，v6→v7 见 §13.6

## 0. 目标与原则

### 0.1 原则（用户定）

> 软件架构不能成为性能瓶颈。瓶颈只能出在三处：VPS 硬件（CPU / 内存 / 硬盘）、第三方接口的速率限制、成本预算。

据此提出三条可检验的要求：

1. **加资源就加容量，不改代码。** 加进程、加容器、加机器都只改配置。
2. **所有容量数字都是配置项。** 并发数、连接数、限流、预算都写在 `.env` 里，重启后生效。
3. **不上大公司架构。** 不引入 Kubernetes、消息中间件、Prometheus/Grafana。PostgreSQL、Redis、nginx、cron 能解决的，就不加新组件。

### 0.2 性能目标（验收标准）

| 场景 | 目标 |
|---|---|
| 设计容量 | 所有馆合计 **200 人同时在用**；扩到 1000 人以上只靠加机器 |
| 浏览 / 搜索 / 内容接口（不含长连接，见 §7） | p95 ≤ 1 秒 |
| 识别 | p95 ≤ 3 秒 |
| 首屏（空作品第一次被打开 → 本语言讲解出现） | 高峰时比单人多 ≤ 10 秒。单人首屏的绝对值（p50 ≤ 15 秒、p95 ≤ 25 秒）归「单人首屏提速」专题 |
| 其余 9 门语言补齐 | 平常 ≤ 5 分钟；高峰期间允许积压，高峰过后 30 分钟内清空（用户 10-21 定 A） |
| 生成过程中，另一种语言的用户打开同一件 | ≤ 60 秒（§3.3：英文主讲解一发布，他的语言就开始翻译。上线后实测） |
| 首次播放（现场合成） | 50 人同时首播，首包 p95 ≤ 3 秒 |
| 第二个人听同一段正在合成的音频 | ≤ 3 秒开始播放（§6，同一段最多 2 路同时合成） |
| 部署或重启 | 不丢任务，不留半成品 |
| 内容生成成本 | 每天 $30、每月 $300（配置项）；到 80% 告警，到 100% 停止生成新内容 |
| 语音、识别兜底的成本 | 各设一条告警线（配置项），只告警，不停服务 |

**容量与预算的关系（用户 10-21 定 A）：** prod 已开放的 4 个馆里，**有图但还没有内容的作品共 14,242 件**，占有图作品的 93%（10-21 查询结果）。200 人高峰时，打开空作品是常态。按评审估算，每天 $30 的预算会在 1–2 小时内用完（取决于新模型单价，尚未核对）。

所以设计上的定位是：**懒生成只负责兜住长尾，热门作品靠离线提前生成**。上线后由 §7 的「当日因预算被拒的打开次数」这个指标来判断，下一步是调高预算，还是离线批量生成那些常被拒的作品。离线批量预生成属于另一个内容运营专题，可以走半价的批量接口，在夜间运行。

### 0.3 不在本设计范围

- **单人首屏提速**（新模型下 p50 约 22 秒）：另开专题。
- **离线批量预生成**（见 §0.2）：另开专题。
- 问答音频、作者简介音频（非流式接口，篇幅短）：不改。
- 离线 CLI 脚本（onboard / generate / translate）：不进队列，行为不变。
- VoxCPM2 定期替换懒生成音频：**不受影响**。`audio_ingest_cli` 直接通过 ORM 写 `audio_key` / `audio_engine`，不经过 `persist_section_audio`，也不碰本设计要替换的锁和并发机制。
- 识别 ONNX 推理降本（int8 量化、减少裁剪次数、提前退出）：这是 1000 人以上规模时识别容量的主要杠杆（§9.1），需要先跑评测集，另开专题。
- 老版 App 拉取 5MB 全量馆包（`artworks=true`）：会随版本升级自然消失。§7 统计时把它剔除。

## 1. 现状与已查实的瓶颈

| # | 瓶颈 | 证据 | 违反了什么 |
|---|---|---|---|
| B1 | 懒生成跑在 web 进程的后台线程里；并发数写死在代码里，并且按进程算（`_SEM=2`、`_FANOUT_SEM=2`，lazy.py:24,32）；槽位满了就直接放弃（lazy.py:235-245、353-355） | 压测 C：20 件同时生成时，补语言只完成了 10 件，有 8 件因槽位满被跳过 | 加机器不能增加生成容量；重启会丢掉正在跑的任务 |
| B1b | `generate_object` 只要发现作品已有任何一段已发布的英文，就整件跳过（pipeline.py:151-152）；而英文主讲解在首屏开始约 10 秒时就已经落库（content_repo.py:236） | 代码；backlog 里「只有主讲解的件」的筛查 | 中途失败后无法续跑，只能留下半成品 |
| B2 | 数据库连接：每个进程 `pool_size=20 + max_overflow=40`（database.py:28），prod 的 `max_connections=100`。另有三类占用被忽略：流式语音接口在整段合成期间一直占着 `get_db` 会话（FastAPI 0.142 的 yield 依赖要等流结束才退出）；`record_llm_usage` 每次调用都另开一个会话；`_prepare_sync`、`_persist_sync` 在默认线程池里也各占一个连接 | 代码，以及评审的实测 | 加进程或加容器后，高峰时整站会报「连接数过多」；记账因拿不到连接而静默丢失 |
| B3 | 向量检索逐条比对，耗时随向量数线性增长；「同一作品取最高分」用的是 Python 循环（vector_index.py:142-146）；一次识别最多查 13 遍 | 本机实测（§5.3） | 收录的作品越多，识别越慢 |
| B4 | 识别和浏览在同一个进程里争抢 CPU；ONNX 没有设置线程数（embedder.py:108） | 压测 B：8 核占用 779% | 识别一忙，浏览也跟着变慢 |
| B5 | TTS 并发写死为每进程 8 路（tts_service.py:36）；段锁存放在 `attributes` JSON 里，读改写时会互相覆盖（lazy_audio.py:38-48）；第二个听众收到 409，要等第一个人那段合成完（约 12 秒）并上传 | 代码 | 达不到「50 人同时首播」和「第二个人 3 秒内开始听」 |
| B6 | 每个 IP 每天 300 的额度对正式账号也生效（lazy.py:640-644） | 压测 C 第一次运行 | 同一个 WiFi 下的游客互相挤占额度 |
| B7 | nginx 限制每个 IP 每秒 10 次（突发 20） | nginx-api.gomuseum.app.conf:17、34 | 同上 |
| B8 | 价目表里只有旧模型，新模型按 $0 计算（llm_cost_report.py:9-15）；识别兜底调用 `chat(...)[0]` 时把 tokens 丢掉了，没有记账（recognition/vision.py:70-84） | 代码 | 无法设置成本上限 |
| B9 | slowapi 的计数存在每个进程的内存里；游客登录限制为每个 IP 每小时 5 次（auth.py:188-189） | 代码 | 进程越多，限流越松 |
| B10 | 启动命令是 `alembic upgrade head && uvicorn`；`container_name` 和主机端口映射 `127.0.0.1:8100:8000` 都写死了（compose:55-57）；每个进程都会执行一次 `init_db()` | 代码 | 多个容器会同时跑数据库迁移 |
| B11 | 没有容量监控，也没有扩容提醒 | — | 不知道什么时候该加机器 |

以下几处已经可以扩容，不需要改：

- 识别的「同一张图正在识别」锁在 Redis 里。
- 索引是每个进程各存一份（约 0.8G/进程）。
- `llm_usage` 由数据库原子累加。
- nginx 日志已经带 `rt=`。
- 用 `FOR UPDATE SKIP LOCKED` 领任务不会重复领取（评审实测：40 个并发领 30 个任务，0 次重复）。

prod 上已有的死代码不在本设计范围内：`/chat/ask` 开头就直接返回 503（chat.py:84-87），`/content/explanation` 返回 410。

## 2. 总体架构

同一个镜像、同一份代码，按启动命令和 nginx 路由分成三类容器：

```
             ┌── 识别类请求 ──→ recognizer 容器
用户 → nginx ┤
             └── 其他请求 ───→ web 容器（浏览、内容、语音流）
                                    │ 写任务
                                    ▼
                        PostgreSQL 任务表 generation_jobs
                                    ▲ 领任务
                                    │
                        worker 容器（生成进程）
```

| 容器 | 负责 | 启动 | 扩容 |
|---|---|---|---|
| web | 浏览、搜索、内容接口（读内容、写任务）、语音流 | `alembic upgrade head && uvicorn …`（**只有它跑迁移**） | 同一台机器上调大 `WEB_WORKERS`；跨机器在 nginx upstream 里加一台 |
| recognizer | 所有识别接口 | `uvicorn …`；不跑迁移；主机端口 `127.0.0.1:8102` | 同一台机器上调大 `RECOG_WORKERS`；跨机器在 upstream 里加一台 |
| worker | 领任务、调 AI、写回结果 | `python -m app.workers.generation`；不跑迁移；不映射端口，不写死 `container_name` | 调大线程数；也可以多开几个 worker 容器（同机或跨机都行） |

- 同一台机器上，web 和 recognizer 扩容靠增加进程数，不靠 `--scale`，所以端口映射不用改。只有 worker 没有端口，可以用 `--scale`。
- `init_db()` 由 `INIT_DB_ON_START` 控制，只有 web 打开。
- 部署脚本和 cron 里写死的容器名要一并清点，改为按 compose 服务名查找。

跨进程共享的状态只放在两个地方：

- **PostgreSQL**：必须可靠的数据，包括任务、内容、账本。
- **Redis**：丢了只会降级的数据，包括防滥用计数、限流计数、识别锁、语音合成槽位。

**扩容总规则**（写进运维文档，告警邮件里会引用）：

1. 所有进程的数据库连接上限之和 ≤ 0.8 × `max_connections`（核算见 §5.1）。
2. 同时在途的 AI 请求 < 外部每分钟上限 ÷ 每路每分钟的调用次数。共用同一个 API 账户的所有调用方都要算进去：worker、识别兜底、离线批量脚本（backfill 默认 8 线程）、staging。
3. prod 和 staging 所有 web 进程的 `TTS_CONCURRENCY` 之和 < Google 允许的同时流式会话数（100）。两边共用同一个 key。
4. 所有会调用 Wikidata 的进程，其 `WIKIDATA_CONCURRENCY` 之和 ≤ 4（遵守 Wikimedia 的调用礼仪；§4.3）。

## 3. 生成任务队列（PostgreSQL 任务表）

### 3.1 表结构

`generation_jobs`，用 alembic 迁移新建，只做加法：

| 列 | 类型 | 说明 |
|---|---|---|
| id | bigserial PK | |
| kind | varchar(16) | `first_screen` / `translate` / `image` |
| qid | varchar(32) | |
| language | varchar(16) | `translate` 任务填目标语言；`first_screen` 和 `image` **固定为空串** |
| lang_priority | varchar(16) null | 只有 `first_screen` 用：第一个请求者的语言，传给 `generate_object(lang_priority=…)` 走快速路径 |
| priority | smallint | 10 = 有人在等；0 = 没人在等 |
| status | varchar(12) | `queued` / `running` / `done` / `failed` / `cancelled` |
| rerun | boolean default false | 只在显式传入 `mark_rerun=True` 并且命中 running 行时置为 true，见 §3.2 |
| priority_at | timestamptz | 优先级最后一次被抬高的时间，用于降级判断 |
| attempts | smallint default 0 | |
| lease_until | timestamptz null | |
| worker_id | varchar(64) null | |
| created_at / started_at / finished_at | timestamptz | |
| last_error | text null | 截断到 2000 字符 |

索引：

- 部分唯一索引 `uq_active_job (kind, qid, language) WHERE status IN ('queued','running')`。首屏任务的 language 固定为空串，所以**同一件作品同一时间最多只有一个首屏任务**。
- `(status, priority DESC, created_at)`
- `(kind, qid, language, finished_at)`，用于失败冷却。

### 3.2 接口（`app/services/jobs.py`，以后换专用队列只改这个模块）

所有函数都接收调用方传入的 `db`，**内部不提交事务**，由调用方决定事务边界（§3.6 的「无空窗」依赖这一点）。

**`enqueue(db, kind, qid, language, priority, lang_priority=None, mark_rerun=False, from_fanout=False) -> (Job | None, inserted: bool)`**

`mark_rerun` 只在首屏 finish 时为补齐任务传 true，轮询路径一律传 false。

1. **先读**：`active_job(db, kind, qid, language)`。
   - 已有 `running` 的任务：抬高正在跑的任务的优先级没有意义。没有传 `mark_rerun=True` 时，不写库，直接返回 `(job, False)`。
   - 已有 `queued` 的任务，并且优先级不低于本次请求：不写，直接返回。
   - 这一步是为了避免每 4 秒一次的轮询都写库。
2. **不和首屏重复**（只针对轮询路径；首屏 finish 时的补齐入队传 `from_fanout=True`，跳过这一步）：`kind=translate`，并且目标语言等于本件活跃首屏任务的 `lang_priority` 时，直接返回 `(首屏任务, False)`，不入队。这门语言由首屏自己翻译（pipeline.py:507）。
3. **没有依赖就不入队**：`kind=translate`，本件既没有活跃的首屏任务，也没有任何已发布的英文段时，返回 `(None, False)`。判断条件和清理线程取消孤儿任务时用的是同一个，避免出现「入队→被取消→再入队」的反复。
4. **预算**：只有轮询路径（优先级 10）在预算耗尽时返回 `daily_cap`。补齐入队和 `mark_rerun` 不受预算影响，照常入队，什么时候执行由 claim 的预算条件决定。这样预算恢复后，之前排队的工作不会丢。
5. **失败冷却**：同一个 (kind, qid, language) 在 `JOB_FAIL_COOLDOWN_H`（默认 6）小时内有过 `failed`，就返回 `(None, False)`，调用方按「暂不可用」处理（§3.6）。
   - 这是一处行为变化：冷却期内，App 上的「重试」也不会触发生成。
6. **写入**：
   ```sql
   INSERT INTO generation_jobs (kind, qid, language, lang_priority, priority, status)
   VALUES (:kind, :qid, :lang, :lp, :prio, 'queued')
   ON CONFLICT (kind, qid, language) WHERE status IN ('queued','running')
   DO UPDATE SET
     priority    = GREATEST(generation_jobs.priority, EXCLUDED.priority),
     priority_at = CASE WHEN EXCLUDED.priority > generation_jobs.priority THEN now() ELSE generation_jobs.priority_at END,
     rerun       = generation_jobs.rerun OR (generation_jobs.status = 'running' AND :mark_rerun)
   RETURNING *, (xmax = 0) AS inserted;
   ```
   首屏任务只记第一个请求者的 `lang_priority`。后来的其他语言不会并进首屏，而是各自建一条高优先级的翻译任务（§3.3）。v2 里的 `want_langs` 合并方案已删除。

**`claim(db, worker_id, lo, hi) -> Job | None`**

```sql
UPDATE generation_jobs j SET status='running', attempts=j.attempts+1, rerun=false,
       lease_until=now()+interval '2 min', worker_id=:w, started_at=now()
WHERE j.id = (
  SELECT c.id FROM generation_jobs c
  WHERE c.priority BETWEEN :lo AND :hi
    AND c.attempts < 3
    AND (c.status='queued' OR (c.status='running' AND c.lease_until < now()))
    AND NOT (c.kind='translate' AND NOT EXISTS (   -- 翻译的依赖：有任何已发布的英文段（与现有 _has_published 一致；老作品可能没有 guide 段）
          SELECT 1 FROM object_content_sections s JOIN museum_objects o ON o.id=s.object_id
          WHERE o.qid=c.qid AND s.language='en' AND s.status='published'))
    AND NOT (c.kind='translate' AND c.priority < 10 AND EXISTS (   -- 后台补齐：等首屏整件做完
          SELECT 1 FROM generation_jobs f
          WHERE f.qid=c.qid AND f.kind='first_screen' AND f.status IN ('queued','running')))
    AND (c.kind='image' OR NOT :budget_exhausted)   -- 补图不调用大模型，不受预算限制
  ORDER BY c.priority DESC, c.created_at
  LIMIT 1 FOR UPDATE SKIP LOCKED)
RETURNING j.*;
```

- 有人在等的翻译（优先级 10）**只要英文主讲解已发布就能开跑**，不用等首屏整件做完。这是「另一种语言 ≤ 60 秒」的实现方式。
- 第三轮评审已核实：正常生成路径下，英文 guide 发布后不会再被改动（`sections_for` 的各类别都不包含 guide），所以这条依赖成立。
- 执行计划显示，依赖子查询会被物化成一次全表哈希。实测单次领取约 10 ms，并发 24 路时约 27 ms。现阶段可以接受；P2 上线后如果量到问题，再加 `ready_at` 列。

**清理线程**（每个 worker 进程一个，每 30 秒运行一次，不放在每次领任务的路径上）：

- 租约已过期且已试满 3 次的任务 → `failed`。
- `priority_at` 早于 10 分钟前的优先级 10 queued 任务 → 降为 0。依据是最后一次被抬高的时间，不是创建时间，所以用户重新打开时会再被抬回 10，不会被马上降回去。
- 孤儿翻译任务：queued 状态、本件没有活跃的首屏任务、也没有任何已发布的英文段 → 置为 `cancelled`。比如首屏过闸失败的件，否则 App 会一直显示「生成中」。
- 每小时删除一次已完成超过 7 天的 `done` / `failed` / `cancelled` 任务。

**`heartbeat(db, job_id, worker_id) -> bool`**

- 每 30 秒续租一次，条件为 `worker_id=:w AND status='running'`。
- 不设最长运行时间：停止续租不会释放卡住的线程，只会让同一个任务被两个线程同时跑。卡住的请求交给 SDK 的超时处理。

**`still_mine(db, job_id, worker_id) -> bool`**

- **只用于翻译任务**，在每门语言、每段内容之间检查一次。
- 首屏任务**中途不检查、不中止**：中止会制造半成品，首屏的失败交给续跑来处理（§3.4）。
- 已知代价：租约过期被别人接手后，原线程不会停，会和新线程一起跑完同一个首屏。正常情况下首屏只要 1–2 分钟，远小于 2 分钟一次、每 30 秒续一次的租约，只有进程卡死时才会发生。新线程走续跑模式，两边都是只补缺，最坏结果是多花一份钱，数据不会错。

**`finish(db, job_id, worker_id, ok, error=None, retry=True)`**

- 只在 `worker_id=:w AND status='running'` 时生效。
- 成功：
  - `rerun=true` → 置回 `queued`，`attempts` 清零，再跑一遍，把运行期间新发布的英文段落也补上；
  - 否则置为 `done`。
- 失败：
  - `retry=True` 且 `attempts < 3` → 置回 `queued`；
  - 其余情况置为 `failed`。

**`release(db, job_id, worker_id)`**：部署停机时使用（§3.4）。执行 `status='queued', attempts=attempts-1, worker_id=NULL`。

### 3.3 哪些工作进队列

| 工作 | 原来 | 现在 | 优先级 |
|---|---|---|---|
| 首屏生成 | web 的 BackgroundTasks 调用 `maybe_trigger` | `enqueue(first_screen, qid, '', 10, lang_priority=请求语言)` | 10 |
| 首屏进行中，另一种语言的用户打开 | 首屏完成后再插队 | `enqueue(translate, qid, 他的语言, 10)`，英文主讲解一发布就开跑 | 10 |
| 已有内容的作品缺少请求语言（懒翻译） | BackgroundTasks | `enqueue(translate, qid, lang, 10)` | 10 |
| 首屏完成后补齐其余语言（**包括 `lang_priority` 这门**：首屏里它的翻译可能被闸挡下或失败，所以照样入队兜底；已经翻完的话，翻译任务会按缺口直接完成） | 首屏线程接着跑 fanout | 每门缺失的语言 `enqueue(translate, qid, lang, 0, mark_rerun=True, from_fanout=True)`，与首屏的 `finish(done)` 放在 **jobs 层单独开的同一个事务**里提交。事务内顺序：先把首屏行改成 done，再入队（`persist_gated_sections` 内部会自己 commit，不能和它混用）。如果某门语言已有 running 的翻译任务，就把它的 rerun 置为 true，确保之后发布的深度段也会被翻译 | 0 |
| 用户浏览时缺图补图 | 后台线程，立即执行 | `enqueue(image, qid, '', 10)`，由独立的 `WORKER_IMAGE_THREADS`（默认 2）领取，不占首屏线程 | 10 |
| 语音流式合成 | web 进程 | **不变** | — |
| 搜索和向量索引重建 | 进程内 | **不变** | — |

**作者行等共享实体（纪律 37）：**

`artists` 行由所有引用这位作者的作品共用，会被多个任务并发写入。v6 的做法：**所有在线写入都走同一个小函数，用行锁、ORM 赋值、只补缺**。这样不写原生 SQL 合并语句，音频损失闸也能照常看见每一次写入。v5 的原生 SQL 方案已作废：闸只挂在 ORM 的 `before_flush` 上，原生 SQL 会绕过它，既不拦截也不记损失账（database.py:62-74，audio_guard 的 docstring 里也写明「管不到批量语句」）。

**`locked_artist(db, qid) -> Artist`**（新增，放在 `app/services/artist_write.py`）

- 新建作者行：`postgresql.insert(Artist).values(qid=…).on_conflict_do_nothing()`（SQLite 按方言分支处理，写法同 `llm_usage.py`）。
- 重读并加锁：`db.query(Artist).filter_by(qid=qid).with_for_update().populate_existing().one()`。
  - `populate_existing` 让会话里缓存的旧对象被数据库的最新值覆盖，不会拿到旧快照。
  - 拿到的是行锁，同一行的其他写入者会排队。不再用 advisory lock：行锁已经够用，也少一个可能死锁的地方。
- 函数本身**不提交**。调用方的规则是：拿到锁之后不能再发起任何网络调用；在 Python 里只补缺地赋值完，**立即提交**，提交时释放锁。持锁时间是毫秒级，远低于 `statement_timeout=30s`。

**调用方的固定三步**（作者块、`fill_artist_bio`、`lazy_audio` 都按这三步写）：

1. **无锁读快照**：读出作者行当前各字段的值，其中包括 `bio_en` 快照。
2. **锁外全部算完**：根据快照判断缺什么，联网把所有候选值算好，得到 `{字段: {语言: 值}}`。作者块原来是「读一点、判断一点、联网一次、赋值一次」交替进行，现在要整体改成这个形状，所以**一次加锁、一次提交**，不按字段分多次拿锁。
3. **加锁只补缺，然后提交**：调用 `locked_artist`，对重读出来的值逐项补缺。**前置条件**：凡是从 `bio_en` 翻译出来的值（W6/W7 的各语言简介、W9 补写的语言、W10 补写的语言），只有在 `art.bio["en"] == 快照 bio_en` 时才写入，否则这一批全部丢弃。这样不会出现「英文是 A，法文却是从旧英文 B 翻出来的」这种混搭。

`fill_artist_i18n_facts` 拆成两个入口：
- 补缺用的新纯函数：`compute_artist_i18n_facts(snapshot: dict, langs, translator) -> dict[str, dict[str, Any]]`。它不接收 ORM 对象，只返回新增的键。
- `--refresh-langs` 继续使用原来的 ORM 入口，行为不变，由闸管控。

**规则：先把网络上的事做完，再加锁写入。** 所有要写的内容（作者简介、多语言名字、国籍、代表作、各语言翻译）都先在锁外算好，放在内存里。加锁后，对**刚刚重读出来的值**判断缺失，只补缺失的部分：
  - 字符串：空串和 None 都算缺失。
  - 列表：空列表和 None 都算缺失。
  - dict 字段：先确认是 dict，JSON null 按空 dict 处理。
  - 判断「缺失」用的是现有代码的真值判断方式，保持一致。

**写入点清单**（第五轮评审逐一列出，W1–W13）：

| # | 位置 | v6 的处理 |
|---|---|---|
| W1 | pipeline `_enrich_artist_and_titles` 新建作者 | 用 `locked_artist` 新建；删除原来的 `db.add(Artist(...))` |
| W2–W5 | 同上：`name_en`、`name_zh`、`birth`、`death`、`nationality`、`notable_works` | 加锁后对重读值补缺。`notable_works` 是 JSONB 列表，SQL NULL、JSON null、`[]` 都算缺失 |
| W4 | 同上：`name_i18n = _fill_i18n(...)` | `_fill_i18n` 在锁外算出候选值，加锁后只合并缺失的语言 |
| W6、W7 | 同上：作者简介英文是坏值时重新生成，并覆盖 `target_langs` 各语言、清掉这些语言的作者音频 | **沿用现有行为，已知接受**：移到 worker 之后，一次首屏仍可能清掉多门语言的作者音频，由闸记账。新的简介文本在锁外生成好；加锁重读后，如果英文仍然是那条坏值（compare-and-set），就用 ORM 覆盖各语言简介，并清掉对应语言的 `bio_audio`/`bio_audio_engine`。走 ORM 写入，**音频损失闸能看见**：脚本进程里没有额度就拦下（`AudioLossBlocked`）；web/worker 是 record-only，写入并记 `audio_invalidations`，孤儿 GC 会保留这些 key。重读后如果英文已经被别人修好，本次不写 |
| W6' | 作者简介英文缺失（不是坏值） | 走补缺，不走 compare-and-set |
| W8 | `fill_artist_i18n_facts`：`nationality_i18n`、`notable_works_i18n` | 补缺模式：锁外算好，加锁后只合并缺失的语言。**`--refresh-langs` 显式刷新模式保持不变**，仍然直接用 ORM 替换已有值，由闸管控 |
| W9 | pipeline 里补写作者简介的各语言 | 锁外翻译好，加锁后只补缺 |
| W10 | `backfill.fill_artist_bio` | 改为「锁外翻译，再调用 `locked_artist` 补缺」（带 `bio_en` 前置条件）。第六轮评审已核实三个调用方都满足「调用后立即提交、此前没有未写入的改动」：`_backfill_bios`、lazy fanout 和 `translate_object_language`；后者的调用方 lazy `_translate` 和 rescan 脚本都紧接着 `db.commit()` |
| W11 | `lazy_audio.get_or_make_artist_bio_audio_url` 写 `bio_audio`/`bio_audio_engine` | 合成完成后用 `locked_artist` 重读，按顺序判断三条：① 合成时用的文本 `text` 与重读出来的 `art.bio[language]` 不相等（字符串比较）→ 丢弃，返回 `(None, "busy")`，前端稍后重试时会用新文本重新合成；② `bio_audio[language]` 已经被别人写入（同一作者的两件作品并发点播放）→ 丢弃自己的，返回已有的 key；③ 否则写入，只合并这门语言的 key。被丢弃的文件交给孤儿 GC，**不会把无人引用的 URL 交给用户**。两门语言并发合成时，两个 key 都会保留 |
| W12 | 离线整块写入：`backfill_display_names`、`batch_names.py`（onboard names，新建 Artist 并整块写 `name_i18n`）、`scripts/fix_hant_script.py`（`name_i18n`、`bio`）、`scripts/fix_title_i18n.py`（`name_i18n`） | 不在本设计范围：走 ORM，闸能看见。**残余风险**：和在线任务并发时仍可能丢更新。**运维约定**：运行这些脚本之前先停 worker 容器（`docker compose stop worker`），跑完再启动。这条写进脚本的 docstring 和运维文档 |
| W13 | `audio_ingest_cli`、`rescan_language` 写 `bio_audio` | 不在本设计范围：离线脚本，走 ORM，闸能看见。并发风险和运维约定同 W12 |

**提交边界**：

- 首屏里的作者块位于 guide 落库之后。guide 的 `persist_gated_sections` 内部已经提交过一次。作者块提交时，会带上本事务里已经 flush 的改动（例如 `o.attributes`），这是无害的；但不能有 dirty 对象。
- 提交后 `o` 会过期（`expire_on_commit` 是默认值），之后再访问时会多一次重新加载，不影响正确性。
- 调用 `locked_artist` 的代码，从拿到锁到提交之间，不能有其他 ORM 对象的未提交改动。测试里用断言检查这一点：拿锁时 `db.dirty` 必须为空。

### 3.4 worker 进程

**启动：**

- 命令：`python -m app.workers.generation`。
- 启动时设置 `llm_usage.ORIGIN_SUFFIX = "@app"`，并调用 `audio_guard.set_record_only()`，与 web 进程保持一致。

**线程：**

- `WORKER_HIGH_THREADS` 只领优先级 ≥ 10 的任务；`WORKER_LOW_THREADS` 只领优先级 < 10 的任务。
- 默认值分别为 **16 / 40**，按 §9.2 的公式确定。另有 `WORKER_IMAGE_THREADS`（默认 2），只领补图任务。
- 没有任务时，sleep 1 秒再领。

**领到首屏任务时：**

- 先算出缺口，以数据库为准，**不看 `content_status`**。英文 guide 一过闸，`content_status` 就会变成 ready（pipeline.py:497-501），而首屏中途失败的件正好都是 ready。
- 缺口有下面四类，满足任意一条就要跑：
  - 英文 guide 还没发布；
  - 本类别的基础段有缺行；
  - 问答缺失；
  - `lang_priority` 这门语言还没有已发布的段。
- 一条都不缺 → 直接 `finish(done)`。

**续跑模式 `generate_object(…, resume=True)`：** 只补缺口，不重写已有内容。各步骤的做法如下：

| 步骤 | 已做的判据 | resume 时的做法 |
|---|---|---|
| 入口 | — | 跳过开头「已有已发布英文就返回 `skipped: exists`」的早退 |
| 装载状态 | — | `en_published` 从数据库装载**全部**已发布的英文段（guide 加上已有的深度段），而不只是本次生成的。下游的问答 `covered`、逐语言翻译都依赖它 |
| 取数（材料、看图、标题、作者解析） | `attributes` 里已有对应的键 | 现在 `f_lab`（多语标题）和 `f_amat`（作者材料）是无条件抓取的。resume 时改为：`attributes` 里缺 `title_i18n` 或作者材料对应的键时才抓。数据本身是幂等的，这样改只是不再白付调用费用 |
| 英文 guide | `en/guide` 已发布 | 已有：从数据库读出 `guide_text`，不重新生成（后面的 canonical 要用它去重） |
| 请求语言 guide | 该语言的 guide 已发布 | 已有就跳过 |
| 作者块 | 字段是否缺失 | 本身已经是只补缺（见 §3.3） |
| canonical（深度段） | 各段是否已有行（任何状态都算） | **把缺的段名作为 `sections` 传给 `generate_canonical`**（content_enricher.py:103 本来就按传入的段生成，`gate.gate` 也只处理传入的段，不用改接口）。去重锚 `guide_text` 用库里已过闸的 guide body。已有的段不经过 `_upsert_section`，不会清音频，也不会让译文降级。已知代价：新补的段看不到已有深度段的内容，段与段之间的去重会弱一些 |
| 翻译 | 该语言该段已发布 | **改为调用 `translate_object_language(include_bio=False)`**。在外面包一层逐段容错：它内部一段出错会中断整门语言，而首屏原来的做法是跳过这一段、继续下一段（backfill.py:200-236）。它本身是幂等的，只翻缺的段。首屏里原来 591-621 行那段无条件 upsert 的循环，在 resume 模式下不再使用 |
| 问答 | 该语言已有已发布的问答 | 顺序：**先补齐英文问答，再跑翻译**；翻译会顺带把请求语言的问答也翻出来，所以请求语言的问答来自翻译，不再用 `suggest()` 直接生成。这个来源差异可以接受。**只为没有问答的语言生成**。`persist_suggested_questions` 会先整组删除再插入，删除时会带走已有的问答音频，所以已有问答的语言绝不能再调用它 |

- `have` 只统计已发布的段。所以续跑或 rerun 时，needs_review 的段会被再翻一次。按「宁缺毋滥」的原则，这样做是有界的：每次续跑最多重试一次。
- 续跑模式也用来修复存量的「只有主讲解」的半成品（backlog 筛查项）。
- 首屏完成后，finish 和补齐任务的入队放在同一个事务里提交（§3.3）。

**异常处理：**

- 任务循环捕获 BaseException，覆盖 `CancelledError`、`SystemExit` 等。
- 把任务置为 `failed(retry=False)` 并发告警，然后线程继续工作。
- 在 record-only 模式下不会抛出 `AudioLossBlocked`，这里捕获只是兜底。

**收到 SIGTERM 时：**

1. 停止领新任务。
2. 首屏任务**等它自然跑完**：整件 1–2 分钟，远小于 5 分钟的宽限期。
3. 翻译任务最多等 4 分钟，到时还没完成就 `release`。
4. 退出。compose 设置 `stop_grace_period: 5m`。

**预算停止时：** 不领生成任务；补图任务照常领（不调用大模型）。

**429：** 不在生成管线里重试。管线内部有很多 `except Exception` 会吞掉错误，结果是一份很薄的内容被永久落库。改为在 `chat()` 里统一处理：配置 SDK 的 `max_retries`，并按 `Retry-After` 等待；每次遇到 429 记一条 `event_log`。

**回滚开关 `LAZY_EXECUTOR=queue|inprocess`（默认 queue）：**

- `inprocess` 时，内容接口走原来的 `maybe_trigger`，`generating` 用原来的判定方式。worker 启动和每次清理时都读这个开关，读到 `inprocess` 就不领任务，并把所有 `queued` 任务置为 `cancelled`。`cancelled` 不计入失败冷却。
- 切回 `queue` 后，内容接口只看任务表，被取消的任务不会复活。
- web 和 worker 读同一个 `.env`，切换时两个容器一起重启。
- 两种模式都要测（跨配置维度测试）。
- P2 上线观察两周后，删除 `inprocess` 路径。

### 3.5 被替换的旧机制

| 旧 | 新 |
|---|---|
| `attributes.lazy_lock_at` | 部分唯一索引加租约 |
| fanout 标记 | 部分唯一索引 |
| `_SEM` / `_FANOUT_SEM` / `_FANOUT_WORKERS` | worker 线程数配置 |
| 槽位满就放弃 | 排队等待 |
| BackgroundTasks | `enqueue` |
| 按段数计的上限（1000 / 3000） | 美元预算（§4.1，与 P2 同时上线） |

backlog 里的待定项 (a) 由这一节吸收。

### 3.6 内容接口契约（只加字段）

**`generating` 的语义不变。** 只要存在与「这件作品 + 本语言」相关的 queued 或 running 任务，它就是 true。相关任务指本作品的 first_screen，或本语言的 translate。

- 这门语言必须整门翻译完，`generating` 才会变成 false。App 的 keepAlive 依赖这一点（catalog_providers.dart:50）。
- **不会出现空窗**：首屏的 `finish(done)` 和各语言的 `enqueue` 在同一个事务里提交。
- 和现在的唯一区别：翻译 X 语言时，Y 语言的 `generating` 会是 false。这比现在更准确，评审确认不会破坏老 App。

**预算停止期间：** 只在排队、还没开始跑的任务，`generating` 返回 false，同时 `unavailable_reason="daily_cap"`。前端的 `dailyCapReached` 已经能处理这种情况。

**失败或处于冷却期：** `generating=false`，表现和现在空作品的「待完善」一样。

**新增 `queue_position`、`eta_seconds`：** 放在 P2b，和前端的排队提示一起排期。

- `queue_position` = 排在前面、同一优先级档、状态为 queued 的任务数。
- `eta_seconds = ceil((queue_position + 1) × 最近 1 小时同类任务的平均耗时 ÷ max(1, 同档正在运行的任务数))`。没有历史数据时，平均耗时按 20 秒计。

## 4. 成本上限与限流

### 4.1 成本上限

**补记账：** recognition/vision.py:70-84 改为保留 `chat()` 返回的用量，调用 `record_llm_usage`。channel 沿用现有的 `recognition` / `label`，因为 `LLM_CHANNEL_MODELS` 靠这个名字选择模型，**不能改名**。

**价目表：** 配置项 `LLM_PRICES`（JSON：`{"模型": [每百万输入美元, 每百万输出美元]}`；TTS 按每百万字符计入输入价）。

- **新模型的单价在实施时从官方价目页核对后填写。**
- 遇到价目表里没有的模型，按表中最贵的价格计算，同时告警。

**三笔账**（用户 10-21 定；只统计带 `@app` 后缀的，也就是线上服务进程的调用）：

| 账 | channel | 到 100% 时 | 配置 |
|---|---|---|---|
| 内容生成 | generate、gate、translate、qa、vision | **停止**：worker 不领生成任务；用户触发的 `enqueue` 返回 `daily_cap`（补齐入队不受影响，见 §3.2） | `BUDGET_GEN_DAILY_USD=30`、`BUDGET_GEN_MONTHLY_USD=300` |
| 语音 | tts | 只告警 | `ALERT_TTS_DAILY_USD` |
| 识别兜底 | recognition、label | 只告警 | `ALERT_RECOG_DAILY_USD` |

- 三笔账到 `BUDGET_ALERT_RATIO=0.8` 时都会告警。
- 离线脚本（channel 不带后缀，如 names、intro）不计入，单独出报表。
- 「当天」统一按 **UTC** 计算：`llm_usage` 改用 UTC 日期。
- 不做缓存：每天只有几十行，直接求和。
- **记账不能丢**：
  - `record_llm_usage` 改用独立的小连接池（每个进程 4+4），不和业务会话抢连接。
  - 记账失败时，除了现有的日志，还要计数，并纳入 §7 的告警。
- **超支上限：** 越线那一刻，已经在跑的任务还会继续花钱，最多 ≈ 16 × 首屏成本 + 40/9 × 单件全部翻译成本，约等于 **5–17 件全流程的费用**，取决于首屏和翻译的成本比例（§9.3）。

### 4.2 防滥用（单人维度，存在 Redis；Redis 不可用时放行）

| 身份 | 计入哪几层额度 |
|---|---|
| 正式账号 | 只按账号计（`CAP_PER_USER`） |
| 游客账号（`is_guest`；`_caller` 返回的 User 对象可以直接拿到这个字段） | 账号 + IP 两层（`CAP_PER_IP`） |

匿名用户本来就不会触发生成（museums.py:150），所以不设这一档。

**扣额度的事务顺序：**

1. 在同一个事务里执行 `enqueue`（尚未提交）。
2. 如果 `inserted=True`，扣 Redis 额度。
3. 超额就 ROLLBACK，返回 `daily_cap`；否则 COMMIT。
4. 合并进已有任务的请求不扣额度。

**其他：**

- `CAP_*` 和 `WEIGHT_*` 都改为配置项，默认值保持不变。保留 #1037「同一件作品同一天只扣一次」。
- **slowapi 改为存 Redis**：`storage_uri` 指向 Redis，`in_memory_fallback_enabled=True`，并设置 socket 超时。这样 Redis 挂了时登录和支付接口不会报 500。
- 游客登录的频率限制改为配置项 `GUEST_LOGIN_RATE`，默认每 IP 每小时 30 次。
- 本节吸收 backlog 待定项 (b)。

### 4.3 外部接口速率

- **大模型**：不另做限速器，worker 的并发数就是上限（§9.2）。429 的处理见 §3.4。
- **Wikidata**：保留进程内的 `_GATE`，把大小改成配置项 `WIKIDATA_CONCURRENCY`（默认 2）。queue 模式下只有 worker 会调用 Wikidata（翻译和识别都不调用）。多开 worker 容器时，按扩容总规则第 4 条平分。v2 设计的 Redis 跨进程令牌（INCR 加 TTL）有 bug，而且目前用不上，已删除。
- **TTS**：配置项 `TTS_CONCURRENCY`，每进程默认 32，取代写死的 8（tts_service.py:36）。prod 2 个进程加 staging 的总和，受扩容总规则第 3 条约束。

### 4.4 nginx

`limit_req` 从 `10r/s burst=20` 改为 `50r/s burst=100`。本节吸收 backlog 待定项 (c)。

## 5. 识别与网页服务扩容

### 5.1 数据库连接

**先消除隐藏占用：**

- 流式语音接口在返回 `StreamingResponse` 之前先执行 `db.close()`。只改一行，之后合成期间就不再占着连接。
- 记账使用独立的小连接池（§4.1）。
- 启动时**显式设置** anyio 的线程 limiter（web 40，recognizer 用 `RECOG_THREADPOOL`，默认 16），并显式设置事件循环的默认 executor（12）。不依赖隐式默认值：`asyncio.to_thread` 的默认大小取的是宿主机核数，而不是容器的 cpus 限制。

**按进程算每个进程需要的连接数：**

| 进程 | 业务连接池 | 记账连接池 | 每进程合计 | 默认进程数 | 小计 |
|---|---|---|---|---|---|
| web | 40（同步线程池）+ 12（to_thread）= `DB_POOL_SIZE=40`、`DB_MAX_OVERFLOW=12` | 8 | 60 | 2 | 120 |
| recognizer | 16 + 4 = 20 | 8 | 28 | 2 | 56 |
| worker | HIGH + LOW + IMAGE + 4 = 62（代码自动计算，overflow 为 0）；首屏任务里的看图等子线程使用调用方的会话，不另开连接 | 8 | 70 | 1 | 70 |
| 脚本 / cron / 迁移 | | | | | ~15 |
| **合计** | | | | | **~261** |

- prod 的 `max_connections` 从 100 调到 **400**。0.8 × 400 = 320，合计约 261，在上限之内。每个空闲连接占几 MB 内存，24G 内存足够。
- 多机部署时再加 PgBouncer。
- **P1 阶段不缩小连接池**：那时懒生成还在 web 进程里跑。P1 只把连接池大小改成配置项（默认值不变），同时调高 `max_connections`，并先修掉流式语音占连接的问题。**`max_connections` 只有重启 PostgreSQL 才能生效，相当于 prod 数据库停机一次**：P1 计划里要写明维护窗口，并先确认 prod 上没有长任务在跑。

### 5.2 recognizer 容器

compose 新增 `recognizer` 服务，nginx 按路径分流：

- `location = /api/v1/recognize`
- `location ~ ^/api/v1/museums/[^/]+/recognize$`
- 两条 location 都复制原有的 `limit_req` 和 `proxy_read_timeout 120s`。
- upstream 里把 web 设为 backup，并配置 `proxy_next_upstream error timeout`。只有连接失败时才回落到 web；POST 请求已经发出后不会重发，所以不会重复识别。

`confirm`、`reject`、已经返回 410 的旧接口、照片反馈这几类请求很轻，继续留在 web。

| 配置 | 默认 | 作用 |
|---|---|---|
| `RECOG_WORKERS` | 2 | 进程数 |
| `RECOG_ONNX_THREADS` | 2 | 推理线程数 |
| `RECOG_THREADPOOL` | 16 | 同步线程池上限 |
| `RECOG_PRELOAD` | web 设为 false | web 不预热识别模型和索引；请求回落时再按需加载 |

### 5.3 向量检索

| 档 | 做法 | 时机 |
|---|---|---|
| ① | 「同一作品取最高分」改用 `np.maximum.at` 加预存的 qid 下标数组；馆过滤改用 `np.isin`；一次识别的多个查询向量合成一个矩阵，一次 `mat @ V.T` 算完 | P1 |
| ② | 近似检索（FAISS HNSW 一类） | 向量数超过 30 万时；上线前必须跑 `recognition_photo_eval` 评测集，确认准确率不降 |
| ③ | 向量矩阵只在 recognizer 里常驻 | P3 |

本机基准（384 维）。全局识别只走「无过滤」这一列：

| 向量数 | 无过滤 | 有过滤 | 其中矩阵点积 |
|---|---|---|---|
| 2.7 万（prod 当前 dinov3-vits16 共 26,678 条） | 8.3 ms | 1.6 ms | 3.4 ms |
| 10 万 | 37 ms | 6.4 ms | 15.7 ms |
| 30 万 | 91 ms | 19 ms | 22.3 ms |
| 100 万 | 529 ms | 77 ms | 254 ms |

- 第 ① 档解决的是「作品越多识别越慢」，**不解决 CPU 占满（B4）**。B4 靠 §5.2 的拆分。
- 第 ① 档验收：10 万向量、13 个查询向量时，检索总耗时 ≤ 30 ms；新旧两种实现的结果对拍完全一致。

## 6. 语音：第二个听众（用户 10-21 定：同一段最多 2 路同时合成）

**合成槽位：**

- 每一段音频有两个合成槽位：`audio:synth:{qid}:{lang}:{section}:1` 和 `:2`。
- 抢槽位用 `SET … <token> NX EX 180`。单次 TTS 合成最长 2×45 秒，加上上传，120 秒太紧。
- 抢到槽位后，先**再查一次缓存**：别人可能刚刚落库完，有缓存就直接返回链接，不再合成。
- 合成结束后，用 Lua 脚本比对 token，确认是自己的才删除，不会误删别人的槽位。

**谁来合成：**

- 抢到任意一个槽位的人，自己发起流式合成，约 2 秒出声（压测 D 实测首包 1.6–1.9 秒）。
- 两个槽位都被占时返回 409。老 App 会按 2、4、8、16 秒退避重试，等第一份合成完就直接播放。
- Redis 不可用时一律放行，不加限制。

**落库只补缺：**

- `persist_section_audio` 改为条件写入：`UPDATE … SET audio_key=:k, audio_engine=:e WHERE … AND audio_key IS NULL`，然后**返回库里实际胜出的那个 key**。
- 非流式的 `/audio`（lazy_audio.py:85-88）改为使用返回的这个 key，避免把会被 GC 清掉的孤儿 URL 返回给用户。
- 落败那一份上传的对象由孤儿 GC 清理。
- 不影响 VoxCPM2 替换（它不走这个函数），也不影响音频损失闸（从无到有不算损失）。

**去掉段锁：** 流式接口不再读写 `attributes.audio_locks`。非流式的问答和作者简介接口保持原样。

**代价：** 每段最多多合成一次，约 $0.03，计入语音账。

**契约不变：** 老 App 不用发版。

## 7. 监控与扩容提醒

宿主机上的 cron 每 5 分钟运行一次 `/opt/gomuseum/ops-check.sh`。

- 宿主机指标直接在 shell 里取。
- 其余指标通过 `docker exec <按 compose 服务名查找> python scripts/ops_check.py` 获取。
- **告警限频用文件时间戳**：`/opt/gomuseum/alerts/{key}.last`，同一类告警 6 小时只发一封。cron 只在这一台机器上运行，所以不需要 Redis。
- 应用进程内现有的 `alert_throttled` 保持不变。
- 每封告警邮件都写明处理办法。

| 检查项 | 数据来源 | 阈值 | 处理办法 |
|---|---|---|---|
| CPU | 宿主机 | 连续 15 分钟 > 70% | 用 `docker stats` 看是哪类容器：识别占用高就加 recognizer，生成占用高就加 worker |
| 内存 / 硬盘 | 宿主机 | > 80% | 加内存；清理日志 |
| 浏览 / 内容接口 p95 | nginx `rt=`，**剔除** `/audio/stream`、识别接口、`artworks=true` | 15 分钟窗口 > 1 秒 | 加 web 进程 |
| 识别 p95 | `recognition_event.duration_ms` | 15 分钟窗口 > 3 秒 | 加 recognizer；向量数超过 30 万时启用 §5.3 第 ② 档 |
| 首屏排队 | 任务表，优先级 10 的 `started_at − created_at` | p95 > 10 秒 | 调大 `WORKER_HIGH_THREADS` |
| 补语言积压 | 任务表 | 低优先级积压持续 30 分钟没有下降（目标：高峰后 30 分钟内清空，§0.2） | 调大 `WORKER_LOW_THREADS`，或加 worker 容器 |
| **worker 存活** | 任务表 | 有 queued 的生成任务、**当前不在预算停止状态**，且 2 分钟内没有任何任务被领走或续租 | **最紧急**：懒生成已经停了 |
| 失败率 | 任务表 | 1 小时内 failed 占比 > 10% | 查看 `last_error` |
| 三笔账 | `llm_usage` × `LLM_PRICES` | 内容生成到 80% / 100%；语音、识别超过各自的告警线 | 决定是否调高预算或告警线 |
| **因预算被拒的作品数** | `event_log`（`enqueue` 返回 `daily_cap` 时记一条，带 qid），**按 qid 去重统计**，避免被轮询和重试次数放大 | 写进 ops_report，不发邮件 | 依据它决定调高预算，还是离线预生成（§0.2） |
| 记账失败 | 记账失败计数 | 15 分钟内 > 0 | 检查记账连接池 |
| 外部 429 | `event_log` | 15 分钟内 > 20 次 | 降低并发或申请提高配额 |
| 数据库连接 | `pg_stat_activity` | > 80% `max_connections` | 调整连接配置 |
| 向量数 | `object_embeddings` | > 30 万 | 启用 §5.3 第 ② 档 |

「worker 存活」告警和 P2 一起上线。

`scripts/ops_report.py`：一次列出以下内容，按需运行。

- 各接口的 p50 / p95；
- 排队情况；
- 三笔账；
- 因预算被拒最多的作品（离线预生成的候选）；
- 各项指标距离上限的余量。

## 8. staging 与 prod 隔离

- staging 的 backend、worker、postgres 容器加上 `cpus` 和 `mem_limit` 限制，合计 2 核 4G。
- 测真实容量时，按小时租一台与 prod 同规格的机器，跑 `lt.py` 的 200 人场景。

## 9. 规模与成本估算（变量来源都列出）

### 9.1 识别

计算公式：`所需核数 = k × U / T_recog × c_recog ÷ u`

| 变量 | 取值 | 来源 |
|---|---|---|
| U | 200 / 1000 | 设计容量 |
| T_recog | 3–4 分钟 | **假设**（用户判断：一段讲解约 1.5 分钟，加上走路和看画的时间） |
| k（高峰与平均的比值） | 2–3 | **假设**；有真实流量后，用 `recognition_events` 每分钟的最大值除以平均值来测 |
| c_recog（每次识别耗费的核·秒） | ≤ 0.97 | 压测 B 的上限值。测试时 CPU 饱和、ONNX 线程超订、prod 也在同一台机器上，实际可能高估约 2 倍。没有按识别路径分开统计：最快的路径推理 1 次，最慢 13 次 |
| u（目标利用率） | 0.6 | 留出余量，保证 p95 达标 |

结果：

- 200 人：满载需要 1.6–3.2 核，按 u=0.6 留余量后需要 **2.7–5.4 核**。
- 1000 人：满载需要 8–16 核，留余量后需要 13–27 核，也就是 **2–3 台同规格机器**。另一个办法是先做推理降本（§0.3）。

### 9.2 生成

**10-19 的 prod 实测数据**（`llm_usage` 中带 `@app` 的记录，共 51 件）：

| channel | 模型 | 调用次数 | 输入 tokens | 输出 tokens | 每次输入 | 每次输出 |
|---|---|---|---|---|---|---|
| gate | haiku | 333 | 1,582,553 | 6,355 | 4,752 | 19 |
| generate | haiku | 127 | 682,677 | 63,548 | 5,375 | 500 |
| qa | haiku | 51 | 290,127 | 21,467 | 5,689 | 421 |
| translate | luna | 5,610 | 3,424,283 | 509,706 | 610 | 91 |
| vision | sonnet | 50 | 117,080 | 13,372 | 2,342 | 267 |

- 平均每件约 121 次调用，输入约 119.5k tokens，输出约 12.0k tokens。
- 「翻译每门语言约 12 次」是用 110 ÷ 9 算出来的，**前提是这 51 件都补齐了 9 门语言，这一点没有核实**。`llm_usage` 无法按件、按语言拆开统计。
- 实施时补测：在 staging 上单独跑 N 件，取 `llm_usage` 的增量，分别得到首屏和每门翻译的调用次数和耗时，保留分项计数。

**需求侧：**

- 每分钟需要生成的件数：`λ = U × p_stub / T_open`。
  - 线程数按需求速率配置。日预算是封顶，不是限速：预算花完就全部停止生成，不会把生成速度平摊到全天。
- 高优先级线程数 ≈ `λ × T_occ_first / 60 × k + λ_req_tr × T_lang / 60 × k`。
  - `T_occ_first` 是首屏线程被占用的时长，不是用户看到第一屏的时间。整件生成都在这个线程里跑，包括作者块、canonical、闸、所有段落、问答（问答一块就要 24.9 秒）。按代码路径估计 45–90 秒，**未实测**。
  - `λ_req_tr` 是有人在等的懒翻译速率，**未测**。
- 低优先级线程数：平均负载 ≈ `λ × 9 × T_lang / 60`。`T_lang` 约 44 秒，是评审推算的，**未实测**。高峰时要乘 k，但 §0.2 已定允许高峰积压，所以按平均负载留余量配置，高峰积压由「高峰后 30 分钟清空」来约束：需要 LOW ≥ 平均负载 / 0.7。
- 例子：p_stub=0.1，U=200，T_open=3.5 分钟，k=3，T_occ_first=60 秒，得到：
  - λ ≈ 5.7 件/分钟；
  - 高优先级约 17 个线程（还没算懒翻译）；
  - 低优先级约 38 个线程。
- **默认值取 HIGH=16、LOW=40。** 等 staging 补测拿到 T_occ_first、T_lang，上线后拿到 p_stub，再按公式调整。

**供给侧：**

- 高优先级每个线程同时最多 2 路大模型调用在途（主线程 + 问答，或主线程 + 看图）；低优先级每个线程 1 路。
- 调用次数上界：16×2×60 + 40×1×60 = 4,320 次/分钟。
  - 这个上界假设每个槽位都在不停地调用 Haiku，实际达不到。首屏是串行的，Haiku 只占其中一部分。按第三轮评审的估算：每个首屏占用一个线程约 75 秒，16 个线程每分钟约处理 12.8 件；每件 Haiku 输入 50.1k tokens，合计约 0.64M TPM，只占上限 10M 的 6%，不会先成为瓶颈。
- OpenAI 约 4,320 × 0.7k ≈ 3.0M tokens/分钟，加上离线脚本和 staging，仍然低于 10M。
- **Wikidata：**
  - 吞吐量够用：2 个令牌，按 p50 0.5 秒算，约每秒 4 次；每件首屏约 8–12 次调用（次数未实测），所以每分钟能撑约 20–30 件首屏。
  - 但**延迟**是个问题：16 个线程满载时约 160 次/分钟，对应令牌容量 240 次/分钟，利用率约 67%。16 件首屏同时开跑，取数阶段要排队约 20–48 秒。Wikidata 慢的时候更长，会吃掉「比单人多 ≤ 10 秒」的余量。
  - 解法属于运维层面：多开 worker 容器，并按扩容总规则第 4 条平分令牌。也就是说，Wikidata 是**单个 worker 进程内的延迟瓶颈**。
  - P2 上线后，从任务表的首屏排队和耗时指标里实测验证。

### 9.3 成本

**每件内容生成的成本：**

`C_item = 50.1k × P_haiku_in + 1.79k × P_haiku_out + 2.30k × P_sonnet_in + 0.26k × P_sonnet_out + 67.1k × P_luna_in + 9.99k × P_luna_out`

- 系数来自 §9.2 表格除以 51；单价在实施时核对。

**每日花费：**

- 每日花费 ≤ 当天被打开过的不同空作品数 × C_item。
- 还要加上：已有作品的懒翻译、首屏失败重试时已经花掉的部分、被闸挡下后重新翻译的部分。
- 到预算后停止；超支上限见 §4.1。

**$30 能撑多久：**

- 30 ÷ (λ × 60 × C_item) 小时。
- 例：λ=5.7 时，C_item 为 $0.05 约撑 1.75 小时，为 $0.10 约撑 53 分钟（评审的估算）。
- 这正是 §0.2 定位 A 的依据。

**语音：**

- 每日花费 = 未缓存的首播段数 × 平均字数 × $30/百万字。
- 加上同一段最多 2 路合成，每段最多多花一次。
- 10-19 单用户实测：33 次合成，共 16,752 字。

brainstorm 时提过的「$30 一两个小时用完」，与上面评审的估算方向一致，但单价仍未核对。设计不依赖这个估算。

### 9.4 语音

- 抽样大小：5 段中文讲解，0.91–1.97 MB。
- 并发：`TTS_CONCURRENCY=32` × 2 个进程 = 64 路，≥ 50 路首播的目标，低于 100 路的上限（staging 也计在内）。

## 10. 配置项清单

| 配置 | 默认 | 位置 |
|---|---|---|
| `WEB_WORKERS` / `RECOG_WORKERS` | 2 / 2 | compose |
| `RECOG_ONNX_THREADS` / `RECOG_THREADPOOL` | 2 / 16 | `.env` |
| `RECOG_PRELOAD` | true（web 设为 false） | compose |
| `INIT_DB_ON_START` | true（recognizer、worker 设为 false） | compose |
| `WORKER_HIGH_THREADS` / `WORKER_LOW_THREADS` | 16 / 40 | `.env` |
| `WORKER_IMAGE_THREADS` | 2 | `.env` |
| `JOB_FAIL_COOLDOWN_H` | 6 | `.env` |
| `LAZY_EXECUTOR` | queue | `.env` |
| `DB_POOL_SIZE` / `DB_MAX_OVERFLOW` | P1 保持 20/40；P2 起 web 40/12、recognizer 16/4，worker 自动计算 | `.env` |
| `max_connections` | 400 | postgres 容器启动命令 |
| `LLM_PRICES` | 实施时核对 | `.env` |
| `BUDGET_GEN_DAILY_USD` / `BUDGET_GEN_MONTHLY_USD` / `BUDGET_ALERT_RATIO` | 30 / 300 / 0.8 | `.env` |
| `ALERT_TTS_DAILY_USD` / `ALERT_RECOG_DAILY_USD` | 实施时按实测基线确定 | `.env` |
| `CAP_PER_USER` / `CAP_PER_IP` / `WEIGHT_GENERATION` / `WEIGHT_TRANSLATION` | 160 / 300 / 8 / 3 | `.env` |
| `GUEST_LOGIN_RATE` | 30/hour | `.env` |
| `WIKIDATA_CONCURRENCY` | 2（每个进程） | `.env` |
| `TTS_CONCURRENCY` | 32（每个进程） | `.env` |
| `AUDIO_SYNTH_SLOTS` | 2 | `.env` |
| nginx `limit_req` | 50r/s burst 100 | nginx |

## 11. 分阶段实施（每个阶段单独写计划、单独提 PR）

| 阶段 | 内容 | 依赖 |
|---|---|---|
| P1 | 连接池改为配置项（默认值不变）、`max_connections` 调到 400；流式语音接口提前释放会话；记账改用独立连接池；向量检索第 ① 档；防滥用的身份分档；slowapi 改存 Redis（含降级）；nginx 限流；`TTS_CONCURRENCY`；语音合成槽位和条件落库（§6） | 无 |
| P2 | 补记账、价目表、三笔账；任务表和 worker；**`generate_object` 续跑模式**；作者行写入统一走 `locked_artist`（行锁 + ORM 只补缺，§3.3）；`chat()` 统一处理 429；回滚开关；**worker 存活告警**；被拒打开次数的记录 | P1 |
| P2b | `queue_position` / `eta_seconds` | P2；与前端一起排期 |
| P3 | recognizer 容器、nginx 分流、recognizer 线程池和连接池、staging 资源上限 | P1 |
| P4 | 其余 ops-check 项、ops_report | P2 |

每个阶段上 prod 前，先确认 prod 上没有正在运行的长任务。

## 12. 测试与验收

任务表、预算、作者行相关的测试都用真实的 PostgreSQL。

**任务表**

- `enqueue`：
  - 重复请求会合并，并抬高优先级；
  - 任务在 running 时再收到同样的请求，会置 rerun；
  - 只读命中时不写库；
  - 冷却期内不入队；
  - 不同语言的首屏请求只产生一条任务。
- `claim`：
  - SKIP LOCKED 下不会重复领取；
  - 租约过期后可以被接管；
  - 优先级 10 的翻译只依赖英文主讲解；优先级 0 的翻译要等首屏完成；
  - 预算停止时仍然领取补图任务。
- 清理线程：
  - 试满 3 次的任务被置为 failed；
  - `priority_at` 超过 10 分钟的任务被降级；降级后用户重新打开会抬回 10，下一轮清理不会再把它降回去；
  - 首屏过闸失败后，孤儿翻译任务被置为 cancelled，`generating` 变为 false。
- 和首屏请求语言相同的翻译不入队；只有补齐路径会置 rerun，轮询路径不会。
- 首屏里请求语言的翻译失败后，finish 之后仍有这门语言的翻译任务。
- 预算耗尽时，补齐入队和 rerun 照常写入，claim 不领；预算恢复后照常执行。
- 没有已发布的英文段、也没有活跃首屏时，轮询不入队，`generating` 稳定为 false，不在 true 和 false 之间来回跳。
- `finish`：
  - rerun 为 true 时重新排队；
  - `retry=False` 时直接置为 failed。
- 首屏完成后再收到入队请求时（作品已经不是空作品），直接置为 done。
- SIGTERM：首屏任务跑完才退出；翻译任务被 release。
- 回滚开关：两种模式下 `generating` 的值都正确；切到 inprocess 后 worker 不领任务，queued 任务被置为 cancelled。

**续跑模式**

- 首屏领取：作品 `content_status=ready` 但缺深度段时，仍然会续跑，不会被直接置为 done。
- 人为制造几种半成品：
  - 只有英文主讲解；
  - 缺深度段；
  - 缺问答；
  - 缺请求语言。
- 对每种半成品，`resume=True` 都能补齐缺失的部分，并且不重写已有内容：已有段落的 body、`audio_key` 不变，已有问答行（包括其音频）不被删除。

**纪律 37**

- **测试环境说明**：SQLite 会忽略 `FOR UPDATE`，并发用例在上面会假通过。凡是并发类用例（下面标「PG」的），都打上 PG 专用标记；CI 缺 PG 时报**失败**，不是跳过。另加一条不依赖 PG 的断言：用 PG 方言编译 `locked_artist` 的查询，断言其中包含 `FOR UPDATE`。非并发用例留在 SQLite 上跑。
- `bio_en` 快照前置条件：快照之后英文已被别人改掉时，这一批从快照翻译出来的其他语言全部不写。
- （PG）两个首屏同时遇到同一位新作者：不出现主键冲突，作者行不丢更新。
- （PG）首屏的作者块和 9 个翻译任务同时写同一位作者：最后各字段的所有语言都在。
- （PG）持锁期间不发起网络调用：用会阻塞的假网络测试，锁等待 < 1 秒；拿锁时 `db.dirty` 为空。
- 先把 `art` 加载进会话，再由另一个会话修改 bio，然后跑作者块：断言另一个会话的修改没有被回滚。
- `bio`、`bio_audio`、`bio_audio_engine` 各自为 SQL NULL、JSON null、`{}` 时，补缺和修坏值都不报错。
- `notable_works` 为 SQL NULL、JSON null、`[]` 时会被补上；非空时不会被覆盖。`notable_works_i18n` 的空列表视为缺失。
- 修坏值：
  - 脚本进程里，额度为 0 时抛 `AudioLossBlocked`，数据库无任何改动。
  - web 或 worker 的 record-only 模式下，写入成功，并且清掉几门语言，`audio_invalidations` 就有几条记录。
  - （PG）两个进程并发修同一条坏值时，只有一方写入。
  - 作者简介英文是缺失而不是坏值时，走补缺。
- `lazy_audio`：
  - 合成期间这门语言的简介被改写了：返回 `(None, "busy")`，不挂上用旧文本合成的音频。
  - 同一门语言已被别人写入：返回已有的 key。
  - （PG）两门语言并发合成：两个 key 都在。
- `names --refresh-langs` 仍能替换已有值，并且由闸管控。
- resume：绕过 exists 早退；已有的深度段不传给 canonical；已有英文问答时，请求语言的问答来自翻译。
- 9 个翻译任务并发补写简介时，最后 9 门语言都在。
- 简介值为 `""` 或 `null` 时会被视为缺失并补写。

**预算**（配置两侧都测）

- 内容生成在 80% 和 100% 两种状态下的行为；
- 语音和识别只告警；
- 未知模型按最贵价计算；
- 按 UTC 切日；
- 记账连接池耗尽时，不丢失记账、不阻塞业务。

**扣额度**：超额时 ROLLBACK，不会出现任务。

**语音**

- 3 个人同时首播同一段时：前两个人拿到音频流，第三个人收到 409；
- 只有一份落库，并且返回的是胜出的那个 key；
- Redis 不可用时放行。

**向量检索**：新旧实现对拍。

**连接数**：50 路流式语音同时进行时，数据库连接数不会随之增长。

**契约测试**

- 用状态机走一遍：首屏 → 有人在等的翻译（与首屏并行）→ 首屏完成并入队补齐任务 → 补齐完成。
- 每一步检查各语言的 `generating`，**任何一步都不能提前变成 false**。
- 预算停止时，返回 `generating=false` 加 `daily_cap`。

**容量验收**：在按小时租的同规格机器上跑 200 人场景，逐行对照 §0.2。

## 13. 评审处理记录

### 13.1 v1 → v2（第一轮，30 条）

阻断 A1–A4、重要 B1–B16、次要 C1–C10 全部按评审修改，只有 C6 部分采纳（`queue_position` 推迟到 P2b）。第二轮评审逐条核实的结果见 13.2 的最后一行。

### 13.2 v2 → v3（第二轮）

| 评审条目 | 处理 |
|---|---|
| 1 首屏无法续跑（阻断） | 改：新增续跑模式（用户定），首屏中途不中止，SIGTERM 时等首屏完成，§3.2、§3.4 |
| 2 线程数用错了时长；预算是封顶而不是速率 | 改：区分「线程被占用的时长」和「用户看到首屏的时间」，按需求计算线程数，默认值调为 16/40，并写明预算与容量的关系（用户定 A），§0.2、§9.2 |
| 3 连接核算漏了三类占用 | 改：流式接口提前释放会话、记账用独立连接池、限制 recognizer 线程池，重新核算并把上限调到 400，P1 期间不缩小连接池，§5.1 |
| 4 want_langs 合并后顺序被打乱 | 改：删除 want_langs，首屏只记第一个请求者的语言，其他语言改用高优先级翻译任务，§3.1、§3.2 |
| 5 语音「各合成一次」、返回的 key 不对、并发默认值 | 改：2 个合成槽位（用户定）、返回胜出的 key、`TTS_CONCURRENCY` 调为 32、规则 3 把 staging 计入，§6、§4.3 |
| 6 隔天积压插队；补图被预算拦住 | 改：清理线程把超过 10 分钟的积压降级，补图不受预算限制，§3.2 |
| 7 另一种语言 ≤ 60 秒 | 改：有人在等的翻译只依赖英文主讲解，并在 P2 第一个任务里核实英文主讲解发布后是否还会被改写，§3.2 |
| 8 作者行的其他字段并发写入、新建作者冲突、`?` 运算符的语义 | 改：作者块加 advisory lock 串行、新建作者用 `ON CONFLICT DO NOTHING`、简介用 NULLIF 判断缺失，§3.3 |
| 9 扣额度的事务顺序 | 改，§4.2 |
| 10 回滚开关缺互斥 | 改：新增 cancelled 状态，worker 读开关，两种模式都测，§3.4 |
| 11 slowapi 缺降级 | 改：开启 `in_memory_fallback_enabled`，§4.2 |
| 12 Wikidata 令牌有 bug，也用不上 | 改：删除，改为进程内令牌数可配置，§4.3 |
| 13 两处补记账的位置是死代码，channel 名写错 | 改：只补识别兜底，沿用 recognition/label，§4.1 |
| 14 预算停止时存活告警误报；限频在 Redis 挂掉时刷屏 | 改：存活告警排除预算停止状态，限频改用文件时间戳，§7 |
| 15 次要项：空首屏、finish 的语义、running 时轮询写库、清理太频繁、函数名、429 叠加重试和被吞、匿名档、端口映射、补图优先级、卡死任务一直续租、BaseException 的理由、P1 缩小连接池 | 全部照改，见 §3.2、§3.3、§3.4、§2、§4.2、§5.1 |
| §9 重算 | 改：按调用拆分 tokens、统一识别的利用率口径、Wikidata 改为延迟问题、供给侧上界重算，并标出未核实的变量 |
| 第一轮修订的核实结论（成立 / 部分成立 / 不成立） | 「不成立」和「部分成立」的条目都已经在本表的对应行里处理 |

### 13.3 v3 → v4（第三轮）

| 评审条目 | 处理 |
|---|---|
| 1 领取规则让续跑永远不会触发（阻断） | 改：按缺口判断，不看 content_status，§3.4 |
| 2 续跑在现有结构上做不到幂等（阻断） | 改：给出各步骤的判据和做法；canonical 只补缺段，翻译复用 `translate_object_language`，问答只补缺的语言，§3.4 |
| 3 作者锁包住了网络调用，并且会超时（阻断） | 改：网络调用放在锁外，锁内只补缺并立即提交，§3.3 |
| 4 rerun 不会被置位 | 改：新增 `mark_rerun` 参数，轮询路径不写 running 行，§3.2 |
| 5 翻译和首屏的请求语言重复 | 改：与首屏 `lang_priority` 相同的语言不入队，§3.2 |
| 6 降级后会被反复抬回再降回 | 改：新增 `priority_at`，§3.1、§3.2 |
| 7 两种情况下 generating 永远为 true | 改：依赖条件放宽为「有任何已发布英文段」，孤儿任务置为 cancelled，§3.2 |
| 8 首屏和翻译互相覆盖作者行 | 改：所有作者多语言字段统一用原子合并 SQL，§3.3 |
| 9 JSON null 被拼成数组 | 改：用 jsonb_typeof 判断，§3.3 |
| 10 JOB_MAX_RUNTIME_S 导致双跑 | 改：删除，写明已知代价，§3.2 |
| 11 claim 的执行计划 | 记录实测数据，P2 上线后量到问题再优化，§3.2 |
| 12 补图占用首屏线程 | 改：独立的 IMAGE 线程，§3.3、§3.4 |
| 13 线程池依赖隐式默认值 | 改：启动时显式设置，§5.1 |
| 14 max_connections 需要重启数据库 | 改：P1 写明维护窗口，§5.1 |
| 15 合成槽位的 TTL | 改：TTL 调为 180 秒，抢到后再查一次缓存，§6 |
| 16 被拒次数会被重试放大 | 改：按 qid 去重统计，§7 |
| §9.2 低优先级公式漏了 k | 用户定 A：目标改为「平常 ≤5 分钟，高峰后 30 分钟清空」，§0.2、§7、§9.2 |
| §9.2 Haiku TPM | 改：采用评审的估算（约占上限的 6%），§9.2 |

### 13.4 v4 → v5（第四轮，只审 P2）

| 评审条目 | 处理 |
|---|---|
| 1 「只补缺」和修复坏值互相冲突（阻断） | 改：保留修复坏值的行为，改用 compare-and-set，同一条语句清掉作者音频，走音频损失闸，§3.3 |
| 2 notable_works_i18n 是列表（阻断） | 改：按字段结构分别写缺失条件，值统一用 jsonb；fill_artist_i18n_facts 改为只返回新增键；标量列单独补缺，§3.3 |
| 3 续跑漏了入口早退和状态装载 | 改：补上这两行，§3.4 |
| 4 canonical 的写法 | 改：只保留「传入缺的段名」，写明去重变弱的代价，§3.4 |
| 5 「取数已有就跳过」写得不准 | 改：如实写明现状和 resume 时的条件，§3.4 |
| 6 同一事务内补齐被「不与首屏重复」吞掉 | 改：新增 from_fanout，先置 done 再入队，lang_priority 这门也入队兜底，§3.2、§3.3 |
| 7 预算耗尽时补齐入队和 rerun 丢失 | 改：只在用户触发的路径返回 daily_cap，§3.2、§4.1 |
| 8 孤儿任务反复入队、取消 | 改：enqueue 和清理用同一个判断条件，§3.2 |
| 9 translate_object_language 遇异常中断整门 | 改：外面包逐段容错，§3.4 |
| 10 问答和翻译的先后顺序 | 改：先补英文问答，再跑翻译；接受请求语言问答来自翻译，§3.4 |
| 11 行号引用有偏差 | 实施计划里改按函数名引用 |

### 13.5 v5 → v6（第五轮，§3.3）

| 评审条目 | 处理 |
|---|---|
| 1 修坏值用原生 SQL 绕过了音频损失闸（阻断） | 改：放弃原生 SQL 合并方案，统一改为「行锁 + `populate_existing` + ORM 只补缺」，闸照常生效 |
| 2 JSONB 标量列写成 `= ''` 会报错（阻断） | 改：缺失判断移到 Python 里做，`notable_works` 的三种空值都算缺失 |
| 3 修坏值时其他语言怎么处理没写 | 改：保留现有行为（覆盖 target_langs，清掉对应音频，走闸），并区分「缺失」和「坏值」 |
| 4 漏掉了 lazy_audio 的写入 | 改：纳入 W11，写入前检查文本一致 |
| 5 重读和 expire 的时机 | 改：重读用 `populate_existing`，拿锁时 `db.dirty` 必须为空 |
| 6 `--refresh-langs` 和 `backfill_display_names` | 改：refresh 模式保持 ORM 不变；离线写入点声明为不在本设计范围 |
| 7 fill_artist_bio 的提交边界 | 改：W10 写明，实施时逐个核实三个调用方 |
| 8 advisory lock 多余 | 改：删除，只用行锁 |
| 测试清单 | 补充评审给出的 7 条 |

### 13.6 v6 → v7（第六轮，§3.3）

| 评审条目 | 处理 |
|---|---|
| 1–5 五个核实点 | 第 1 点核实成立：重读之后闸比较的是锁后的最新库值（PG 和 SQLite 都实测过）。第 2–5 点按下表修改 |
| H1 修坏值失败后，其他语言来源不一致（阻断） | 改：所有从 `bio_en` 翻译出来的写入，都加「英文仍等于快照」这个前置条件，不满足就整批丢弃 |
| H2 作者块要拆成三步 | 改：写明固定三步、一次加锁；`compute_artist_i18n_facts` 改为纯函数并给出签名；refresh 入口保留 |
| H3 离线写入点漏列 | 改：补上 batch_names、fix_hant_script、fix_title_i18n；写明残余风险，以及「跑脚本前先停 worker」的运维约定 |
| M1 SQLite 测试会假通过 | 改：并发用例打 PG 标记，缺 PG 时报失败；另加 `FOR UPDATE` 编译断言 |
| M2 W11 丢弃时的返回值 | 改：三条判断写清楚，丢弃时返回 busy 或已有的 key |
| M3 W6/W7 搬到 worker 后的副作用 | 改：写明「沿用现有行为，已知接受」，并补一条计数测试 |
| L1、L2 | 改：修正提交边界的措辞；把三个调用方写进 W10 |

