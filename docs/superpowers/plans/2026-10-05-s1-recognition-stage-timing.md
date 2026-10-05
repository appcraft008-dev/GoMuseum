# S1 识别分步计时 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 每次识别把总耗时和各阶段耗时写进 `recognition_events`,跑一周后用 SQL 出分位数,找出 30–60 秒的等待耗在哪一步。

**Architecture:** `recognize()` 内用一个极小的阶段计时器在各阶段结束处打点;`record_event()` 多收两个可选参数 `duration_ms`/`timings`,落到 `recognition_events` 的两个新 nullable 列。持久化进 DB 而不是只打日志:每次 CD 都会重建容器,docker 日志撑不过一周。

**Tech Stack:** FastAPI / SQLAlchemy / Alembic / pytest(sqlite 内存库)。

**Spec:** `docs/superpowers/specs/2026-10-05-recognition-failure-feedback-design.md`(S1 一节)

## Global Constraints

- 契约只做加法:响应形状不变,App 无感;新列 nullable,老行保持 NULL。
- 埋点纪律不变:计时/落库任何异常都不能打断识别(`record_event` 已吞异常)。
- 计时数据不含任何用户标识,不涉及隐私政策/删号/导出改动。
- 不预设优化手段——本计划只测量。
- Python 必须过 black + isort;提交遵循 Conventional Commits;禁止 `git add <目录>/`。
- 合并流向 feature/* → staging(我合)→ main(用户合);合 main 前查 prod 有无长跑任务。

## Review Focus

1. 缓存命中路径也要有计时(否则「重发很快」的证据缺失)→ Task 2 测试 `test_event_timing_cache_hit`。
2. GPT 兜底链是最可疑的慢点,必须能被单独归因 → Task 2 测试 `test_event_timing_attributes_slow_gpt`。
3. 没跑的阶段不能出现在 `timings` 里(否则分位数被 0 稀释)→ Task 2 测试断言 vector 命中时无 `gpt`、`canvas`、`crops` 键。
4. 老调用方不传计时参数仍能落事件 → Task 1 测试 `test_record_event_without_timing`。
5. 端点耗时不含上传时间(上传在进入同步 handler 之前完成)——用 nginx `rt=` 字段补齐,Task 4 的 SQL 报告注明这一点,不在代码里处理。

---

### Task 1: `recognition_events` 加计时列 + `record_event` 收计时参数

**Files:**
- Create: `backend/alembic/versions/f1t1_recognition_events_timing.py`
- Modify: `backend/app/models/recognition_event.py`
- Modify: `backend/app/services/recognition/events.py`(`record_event`)
- Test: `backend/tests/unit/services/recognition/test_service.py`(追加)

**Interfaces:**
- Produces: `RecognitionEvent.duration_ms: int | None`、`RecognitionEvent.timings: dict[str, int] | None`;
  `record_event(db, *, museum_slug, phash, outcome, top_qid, top_score, language, engine, user_id=None, duration_ms=None, timings=None) -> None`

- [ ] **Step 1: 写失败测试**(追加到 `test_service.py` 末尾附近的「埋点」小节)

```python
def test_record_event_stores_timing(session):
    from app.services.recognition.events import record_event

    record_event(
        session,
        museum_slug="orsay",
        phash="p1",
        outcome="match",
        top_qid="Q334138",
        top_score=0.9,
        language="en",
        engine="vector",
        duration_ms=1234,
        timings={"prep": 10, "embed": 1200},
    )
    ev = session.query(RecognitionEvent).one()
    assert ev.duration_ms == 1234
    assert ev.timings == {"prep": 10, "embed": 1200}


def test_record_event_without_timing(session):
    from app.services.recognition.events import record_event

    record_event(
        session,
        museum_slug="orsay",
        phash="p2",
        outcome="match",
        top_qid="Q334138",
        top_score=0.9,
        language="en",
        engine="vector",
    )
    ev = session.query(RecognitionEvent).one()
    assert ev.duration_ms is None and ev.timings is None
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && python -m pytest tests/unit/services/recognition/test_service.py -k "record_event_stores_timing or record_event_without_timing" -v`
Expected: FAIL(`record_event() got an unexpected keyword argument 'duration_ms'`)

- [ ] **Step 3: 模型加两列**(`recognition_event.py`)

import 行改为:
```python
from sqlalchemy import JSON, Column, DateTime, Float, Index, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
```
在 `user_id` 列之后、`created_at` 之前加:
```python
    # 识别耗时(S1,2026-10-05):总毫秒 + 各阶段毫秒 {"prep":..,"embed":..,"gpt":..}。
    # 只记**跑了的**阶段;从进入 recognize() 起算,不含上传(上传看 nginx rt=)。
    duration_ms = Column(Integer, nullable=True)
    timings = Column(JSON().with_variant(JSONB, "postgresql"), nullable=True)
```

- [ ] **Step 4: 迁移**(`f1t1_recognition_events_timing.py`)

```python
"""识别事件记耗时 —— 找出「转圈 30 秒到 1 分钟」耗在哪一步(spec 2026-10-05 S1)。

**加法**:两列 nullable,老行保持 NULL;写入侧不传也不报错。
存 DB 不只打日志:每次 CD 都会重建容器,docker 日志撑不过一周的观测期。
不含用户标识,隐私政策/删号/导出无需配套。
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "f1t1"
down_revision = "e6b7"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "recognition_events", sa.Column("duration_ms", sa.Integer(), nullable=True)
    )
    op.add_column(
        "recognition_events",
        sa.Column("timings", postgresql.JSONB(), nullable=True),
    )


def downgrade():
    op.drop_column("recognition_events", "timings")
    op.drop_column("recognition_events", "duration_ms")
```

- [ ] **Step 5: `record_event` 收两个参数**(`events.py`)

签名在 `user_id=None,` 之后加 `duration_ms=None,` 和 `timings=None,`;`RecognitionEvent(...)` 构造里在 `user_id=user_id,` 之后加:
```python
                duration_ms=duration_ms,
                timings=timings,
```

- [ ] **Step 6: 跑测试确认通过**

Run: `cd backend && python -m pytest tests/unit/services/recognition/test_service.py -v`
Expected: 全部 PASS(含原有用例)

- [ ] **Step 7: 迁移链检查**

Run: `cd backend && python -m alembic heads`
Expected: 只有一个 head:`f1t1 (head)`

- [ ] **Step 8: Commit**

```bash
git add backend/alembic/versions/f1t1_recognition_events_timing.py backend/app/models/recognition_event.py backend/app/services/recognition/events.py backend/tests/unit/services/recognition/test_service.py
git commit -m "feat(recognition): recognition_events 加耗时列,record_event 可收计时"
```

---

### Task 2: `recognize()` 各阶段打点

**Files:**
- Modify: `backend/app/services/recognition/service.py`(`recognize()`,约 251–434 行)
- Test: `backend/tests/unit/services/recognition/test_service.py`(追加)

**Interfaces:**
- Consumes: Task 1 的 `record_event(..., duration_ms=, timings=)`
- Produces: 阶段键名(报告 SQL 依赖,不得改名):`prep` `cache_get` `embed` `vq` `canvas` `crops` `vector_out` `gpt` `match` `demand`

- [ ] **Step 1: 写失败测试**

```python
def test_event_timing_vector_hit(session):
    vq = _FakeVQ([("Q334138", 0.95)])
    recognize(session, "orsay", _jpeg(), embed_fn=lambda b: "V", vector_query_fn=vq)
    ev = session.query(RecognitionEvent).one()
    assert isinstance(ev.duration_ms, int) and ev.duration_ms >= 0
    assert {"prep", "embed", "vq", "vector_out"} <= set(ev.timings)
    # 没跑的阶段不出现(否则分位数被 0 稀释)
    assert not {"gpt", "canvas", "crops", "cache_get"} & set(ev.timings)
    assert all(isinstance(v, int) and v >= 0 for v in ev.timings.values())


def test_event_timing_attributes_slow_gpt(session):
    import time

    slow = _vision([{"title": "Nope", "artist": "X"}])

    def slow_identify(*a, **k):
        time.sleep(0.05)
        return slow(*a, **k)

    recognize(
        session,
        "orsay",
        _jpeg(),
        embed_fn=lambda b: None,  # 引擎不可用 → GPT 链
        identify_fn=slow_identify,
    )
    ev = session.query(RecognitionEvent).filter_by(engine="text").one()
    assert ev.timings["gpt"] >= 40
    assert ev.duration_ms >= ev.timings["gpt"]
    assert "match" in ev.timings


def test_event_timing_cache_hit(session):
    class _FakeRedis:
        def __init__(self):
            self.store = {}

        def get(self, k):
            return self.store.get(k)

        def setex(self, k, ttl, v):
            self.store[k] = v

    r = _FakeRedis()
    vq = _FakeVQ([("Q334138", 0.95)])
    img = _jpeg()
    recognize(session, "orsay", img, embed_fn=lambda b: "V", vector_query_fn=vq, redis=r)
    recognize(session, "orsay", img, embed_fn=lambda b: "V", vector_query_fn=vq, redis=r)
    ev = session.query(RecognitionEvent).filter_by(engine="cache").one()
    assert {"prep", "cache_get"} <= set(ev.timings)
    assert "embed" not in ev.timings
    assert isinstance(ev.duration_ms, int)
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && python -m pytest tests/unit/services/recognition/test_service.py -k event_timing -v`
Expected: FAIL(`ev.duration_ms` 为 None / `ev.timings` 为 None)

- [ ] **Step 3: 加计时器**(`service.py`,放在 `_top_of` 之前;顶部 `import time`)

```python
class _StageClock:
    """识别分步计时(S1)。mark(name) 记「上一个打点到现在」的毫秒数。
    ponytail: 只记跑了的阶段,同名重复 mark 会覆盖——recognize() 里每个阶段只 mark 一次。"""

    def __init__(self):
        self._t0 = self._last = time.perf_counter()
        self.stages: dict[str, int] = {}

    def mark(self, name: str) -> None:
        now = time.perf_counter()
        self.stages[name] = round((now - self._last) * 1000)
        self._last = now

    def total_ms(self) -> int:
        return round((time.perf_counter() - self._t0) * 1000)
```

- [ ] **Step 4: 在 `recognize()` 打点**

逐处修改(行号以当前文件为准,按上下文定位):

1. 函数体第一行(`museum = None` 之前)加 `clock = _StageClock()`。
2. `phash = ImageService.generate_perceptual_hash(image_bytes)` 之后加 `clock.mark("prep")`。
3. 缓存块:`hit = redis.get(ckey)` 之后加 `clock.mark("cache_get")`;命中分支的 `record_event(...)` 调用末尾加 `duration_ms=clock.total_ms(), timings=clock.stages,`。
4. 向量块:
   - `vec = (embed_fn or _default_embed)(image_bytes)` 之后加 `clock.mark("embed")`;
   - `ranked = vquery(db, vec, museum_id)` 之后加 `clock.mark("vq")`;
   - canvas 分支 `if canvas is not None:` 块内 `ranked = _merge(ranked, canvas)` 之后加 `clock.mark("canvas")`;未进入该 `if` 时(`canvas is None`)也已花了嵌入时间,所以把 mark 放在 `canvas = ...` 这一行之后、`if canvas is not None:` 之前,改为:
     ```python
                canvas = (embed_canvas_fn or _default_embed_canvas)(image_bytes)
                if canvas is not None:
                    canvas_used = True
                    ranked = _merge(ranked, canvas)
                clock.mark("canvas")
     ```
     (位于外层 `if not ranked or ranked[0][1] < settings.RECOG_HIGH:` 块内,只有跑了才 mark)
   - crops 同理,在外层 `if not ranked or ranked[0][1] < settings.RECOG_LOW:` 块的末尾加 `clock.mark("crops")`;
   - `out = _vector_out(db, storage, ranked, language)` 之后加 `clock.mark("vector_out")`。
5. GPT 链:`vis = identify_fn(...)` 之后加 `clock.mark("gpt")`;`if not queries and not label_lines: ... else: ...` 整个分支结束后(与 `out = {...}` 同缩进层)加 `clock.mark("match")`。
6. `record_demand` 的 `try/except` 块之后(仍在 `if out["outcome"] == "unrecognized":` 内)加 `clock.mark("demand")`。
7. 结尾 `record_event(...)` 调用末尾加 `duration_ms=clock.total_ms(), timings=clock.stages,`。

- [ ] **Step 5: 跑测试确认通过**

Run: `cd backend && python -m pytest tests/unit/services/recognition/ tests/integration/test_recognize_flow.py tests/unit/api/test_recognize_global.py -v`
Expected: 全部 PASS

- [ ] **Step 6: 格式化 + 全量后端测试**

Run: `cd backend && black app tests alembic && isort app tests alembic && python -m pytest -q`
Expected: 与基线一致,无新失败

- [ ] **Step 7: Commit**

```bash
git add backend/app/services/recognition/service.py backend/tests/unit/services/recognition/test_service.py
git commit -m "feat(recognition): 识别各阶段打点并落事件,定位慢在哪一步"
```

---

### Task 3: 上 staging 实测

**Files:** 无代码改动

- [ ] **Step 1:** 推分支、`/pr` 提 PR → staging;CI 全绿后合并(`gh pr merge --squash --delete-branch`)。
- [ ] **Step 2:** 等 staging CD 完成(含 alembic 迁移),用 staging 包或 curl 发 3 张图:一张能直接认出、一张走 GPT 链、同一张重发一次(命中缓存)。
- [ ] **Step 3:** 只读查 staging 库:
```sql
select engine, outcome, duration_ms, timings
from recognition_events order by created_at desc limit 5;
```
Expected: 三行都有 `duration_ms`,`timings` 键与 Task 2 规定的阶段名一致;缓存那行只有 `prep`/`cache_get`。
- [ ] **Step 4:** 向用户报告 staging 结果,请用户合 staging→main 上 prod(合前查 prod 有无长跑任务)。

---

### Task 4: 一周后出报告(prod 只读)

**Files:** 无代码改动

- [ ] **Step 1:** 上 prod 满约 7 天后,只读执行:
```sql
-- 总耗时分位数(按决出档位)
select engine, count(*) n,
  percentile_cont(0.5) within group (order by duration_ms) p50,
  percentile_cont(0.9) within group (order by duration_ms) p90,
  percentile_cont(0.99) within group (order by duration_ms) p99,
  max(duration_ms) mx
from recognition_events where duration_ms is not null
group by engine order by n desc;

-- 各阶段分位数(只统计跑了该阶段的请求)
select k stage, count(*) n,
  percentile_cont(0.5) within group (order by v::int) p50,
  percentile_cont(0.9) within group (order by v::int) p90,
  max(v::int) mx
from recognition_events, jsonb_each_text(timings) as t(k, v)
where timings is not null
group by k order by p90 desc;
```
- [ ] **Step 2:** 结合 nginx `rt=`(若用户已加)算「上传+排队」= nginx rt − duration_ms 的分布;499 请求的 rt 是否集中在 60s。
- [ ] **Step 3:** 写结论给用户:慢在哪一阶段、长尾占比、建议的下一步(另立项)。原始计数全部保留在报告里,不只给比例。
