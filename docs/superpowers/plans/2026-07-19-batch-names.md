# Batch names Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** names 显示名翻译走 OpenAI Batch(半价+免长时盯守),质量零变化,失败零新机制。

**Architecture:** 新模块 `batch_names.py` 四函数(collect/submit/poll/apply)+ `run` 编排,全注入可测;collect 阶段同步抓权威标签**直接落库**(部分进度不怕 batch 失败),只把仍缺的翻译任务发 Batch;apply 复用剥号清洗、只补缺不覆盖。onboard `--use-batch/--batch-job` wiring。

**Tech Stack:** OpenAI Batch API(同步 OpenAI client,独立于生成 seam)/ JSONL / pytest fake client。

## Global Constraints

- spec: `docs/superpowers/specs/2026-07-19-batch-names-design.md`
- 同 prompt(`build_name_translation_prompt`)同模型(gpt-4o);custom_id=`"<title|artist>|<key>|<lang>"`
- 失败行=仍缺→幂等重跑;job 状态落盘 `/tmp/<slug>_names_batch.json`
- 记账 `record_llm_usage("names", "gpt-4o@batch", ...)`;PRICES 加 `"gpt-4o@batch": (1.25, 5.00)`
- staging 护栏兼容(`--use-batch` 同受 staging_limit);懒生成路径⛔不 Batch
- black;测试照 sqlite StaticPool fixture 模式

---

### Task 1: strip_name 共享助手(微重构)

**Files:**
- Modify: `backend/app/services/enrichment/translator.py`
- Test: `backend/tests/integration/test_generate_pipeline.py`(已有 translate 测试隐式覆盖;新增 1 条直测)

**Interfaces:**
- Produces: `strip_name(text: str) -> str`(模块级;剥书名号/引号)

- [ ] **Step 1: 失败测试**(追加 test_generate_pipeline.py)

```python
def test_strip_name_shared_helper(session):
    from app.services.enrichment.translator import strip_name

    assert strip_name("《睡莲》") == "睡莲"
    assert strip_name('"Water Lilies"') == "Water Lilies"
```

- [ ] **Step 2: 红** → **Step 3: 实现**(translator.py,translate_name 上方加模块函数,translate_name 改用它)

```python
_NAME_QUOTES = "《》\"'“”‘’«»"


def strip_name(text: str) -> str:
    """剥模型套上的书名号/引号(translate_name 与 batch 回填共用)。"""
    return (text or "").strip().strip(_NAME_QUOTES)
```

`translate_name` 末行改:`return strip_name(out)`(out 不再预 strip)。

- [ ] **Step 4: 绿**(该文件全量)→ **Step 5: Commit** `git commit -m "refactor(i18n): strip_name 共享助手(batch回填复用)"`

### Task 2: batch_names.collect_missing(TDD)

**Files:**
- Create: `backend/app/services/enrichment/batch_names.py`
- Test: `backend/tests/integration/test_batch_names.py`

**Interfaces:**
- Produces: `BatchTask`(dataclass: `custom_id: str, name: str, lang: str`);
  `collect_missing(db, slug, langs, *, fetch_labels=None, limit=None) -> list[BatchTask]`
  ——扫馆内对象 title_i18n + 关联 Artist name_i18n;权威标签**当场落库**;仅缺的出任务

- [ ] **Step 1: 失败测试**

```python
# backend/tests/integration/test_batch_names.py
"""Batch names:collect 只收缺的(权威已落库不进JSONL);apply 合并+剥号+坏行跳过。"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.models.artist import Artist
from app.models.museum import Museum
from app.models.museum_object import MuseumObject, ObjectImage
from app.services.enrichment.batch_names import collect_missing
from app.services.object_importer import upsert_museum, upsert_object


@pytest.fixture()
def session():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(
        bind=engine,
        tables=[
            Museum.__table__,
            MuseumObject.__table__,
            ObjectImage.__table__,
            Artist.__table__,
        ],
    )
    s = sessionmaker(bind=engine)()
    m = upsert_museum(s, {"slug": "louvre", "name_en": "Louvre"})
    o = upsert_object(
        s,
        m.id,
        {
            "qid": "Q1",
            "title_en": "Mona Lisa",
            "artist_en": "Leonardo",
            "category": "painting",
            "attributes": {"artist_qid": "QA1"},
        },
    )
    s.add(Artist(qid="QA1", name_en="Leonardo", name_i18n={"en": "Leonardo"}))
    s.commit()
    yield s


def test_collect_authoritative_lands_and_only_missing_emitted(session):
    # fr 有权威标签→当场落库不出任务;zh 无→出任务(pivot=title_en)
    tasks = collect_missing(
        session,
        "louvre",
        ["en", "fr", "zh"],
        fetch_labels=lambda qid, langs: (
            {"fr": "La Joconde"} if qid == "Q1" else {}
        ),
    )
    o = session.query(MuseumObject).filter_by(qid="Q1").one()
    assert o.attributes["title_i18n"]["fr"] == "La Joconde"  # 权威直接落库
    ids = {t.custom_id for t in tasks}
    assert "title|Q1|zh" in ids and "title|Q1|fr" not in ids
    assert "artist|QA1|zh" in ids  # 作者名 zh 缺
    t = next(t for t in tasks if t.custom_id == "title|Q1|zh")
    assert t.name == "Mona Lisa" and t.lang == "zh"


def test_collect_limit_and_idempotent(session):
    o = session.query(MuseumObject).filter_by(qid="Q1").one()
    o.attributes = {
        **o.attributes,
        "title_i18n": {"en": "Mona Lisa", "zh": "蒙娜丽莎", "fr": "La Joconde"},
    }
    a = session.query(Artist).one()
    a.name_i18n = {"en": "Leonardo", "zh": "达芬奇", "fr": "Léonard"}
    session.commit()
    tasks = collect_missing(
        session, "louvre", ["en", "fr", "zh"], fetch_labels=lambda q, l: {}
    )
    assert tasks == []  # 全齐→零任务(按语言维度幂等)
```

- [ ] **Step 2: 红**(ModuleNotFoundError)

- [ ] **Step 3: 实现**

```python
# backend/app/services/enrichment/batch_names.py
"""names 的 Batch 模式(成本工程②,spec 2026-07-19-batch-names)。
collect 同步抓权威标签当场落库(部分进度不怕 batch 失败),仅缺的出翻译任务;
submit/poll/apply 走 OpenAI Batch(半价);apply 剥号+只补缺+分批 commit。
失败行=仍缺→幂等重跑,零新机制。"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass

logger = logging.getLogger(__name__)

MODEL = "gpt-4o"
USAGE_MODEL = "gpt-4o@batch"


@dataclass
class BatchTask:
    custom_id: str  # "<title|artist>|<key>|<lang>"
    name: str  # 待翻译的轴心名
    lang: str


def collect_missing(db, slug, langs, *, fetch_labels=None, limit=None):
    from app.models.artist import Artist
    from app.models.museum import Museum
    from app.models.museum_object import MuseumObject
    from app.services.enrichment.backfill import _clean_i18n
    from app.services.enrichment.material import fetch_wikidata_labels

    fetch_labels = fetch_labels or fetch_wikidata_labels
    m = db.query(Museum).filter_by(slug=slug).one_or_none()
    if not m:
        return []
    objs = db.query(MuseumObject).filter_by(museum_id=m.id).all()
    if limit:
        objs = objs[:limit]
    tasks: list[BatchTask] = []
    artist_qids: set = set()
    for i, o in enumerate(objs):
        attrs = dict(o.attributes or {})
        ti = _clean_i18n(attrs.get("title_i18n"))
        if aq := attrs.get("artist_qid"):
            artist_qids.add(aq)
        missing = [lg for lg in langs if not ti.get(lg)]
        if missing:
            try:
                labels = fetch_labels(o.qid, langs)
            except Exception:  # 单件网络失败跳过(纪律①),重跑再补
                continue
            for lg in langs:
                if not ti.get(lg) and labels.get(lg):
                    ti[lg] = labels[lg]  # 权威当场落库
            if o.title_en and not ti.get("en"):
                ti["en"] = o.title_en
            o.attributes = {**attrs, "title_i18n": ti}
            pivot = ti.get("en") or next((ti[x] for x in langs if ti.get(x)), None)
            if pivot:
                for lg in langs:
                    if not ti.get(lg):
                        tasks.append(BatchTask(f"title|{o.qid}|{lg}", pivot, lg))
        if (i + 1) % 200 == 0:
            db.commit()  # 分批落盘(纪律②)
    for aq in sorted(artist_qids):
        art = db.query(Artist).filter_by(qid=aq).first()
        if not art:
            continue
        ni = _clean_i18n(art.name_i18n)
        pivot = ni.get("en") or art.name_en
        if not pivot:
            continue
        if art.name_en and not ni.get("en"):
            ni["en"] = art.name_en
            art.name_i18n = ni
        for lg in langs:
            if lg != "en" and not ni.get(lg):
                tasks.append(BatchTask(f"artist|{aq}|{lg}", pivot, lg))
    db.commit()
    return tasks
```

- [ ] **Step 4: 绿** → **Step 5: Commit** `git commit -m "feat(cost): batch_names.collect_missing(权威落库/仅缺出任务/幂等)"`

### Task 3: submit / poll / apply + 状态落盘(TDD,fake client)

**Files:**
- Modify: `backend/app/services/enrichment/batch_names.py`(追加)
- Test: `backend/tests/integration/test_batch_names.py`(追加)

**Interfaces:**
- Produces: `submit(tasks, client) -> str`(job_id);`poll(job_id, client, interval=60) -> list[dict]`
  (output 行 dict);`apply(db, lines) -> dict`(`{"applied","skipped"}`);
  `save_state(path, job_id, n)` / `load_state(path) -> dict|None`

- [ ] **Step 1: 失败测试**(追加)

```python
class _FakeClient:
    """OpenAI Batch 三接口 fake:files.create/batches.create+retrieve/files.content。"""

    def __init__(self, results):
        self._results = results  # list[dict] 输出行
        outer = self

        class _Files:
            def create(self, file, purpose):
                outer.uploaded = file.read().decode()
                class R: id = "file-in"
                return R()

            def content(self, fid):
                class R:
                    text = "\n".join(json.dumps(r) for r in outer._results)
                return R()

        class _Batches:
            def create(self, **kw):
                outer.batch_kwargs = kw
                class R: id = "batch-1"
                return R()

            def retrieve(self, bid):
                class R:
                    status = "completed"
                    output_file_id = "file-out"
                return R()

        self.files, self.batches = _Files(), _Batches()


import json

from app.services.enrichment.batch_names import (
    BatchTask,
    apply,
    load_state,
    poll,
    save_state,
    submit,
)


def _ok_line(cid, text, tin=100, tout=10):
    return {
        "custom_id": cid,
        "response": {
            "status_code": 200,
            "body": {
                "choices": [{"message": {"content": text}}],
                "usage": {"prompt_tokens": tin, "completion_tokens": tout},
            },
        },
        "error": None,
    }


def test_submit_builds_jsonl_and_poll_returns_lines(session):
    fake = _FakeClient([_ok_line("title|Q1|zh", "《蒙娜丽莎》")])
    job = submit([BatchTask("title|Q1|zh", "Mona Lisa", "zh")], fake)
    assert job == "batch-1"
    line = json.loads(fake.uploaded.splitlines()[0])
    assert line["custom_id"] == "title|Q1|zh" and line["body"]["model"] == "gpt-4o"
    assert "Mona Lisa" in line["body"]["messages"][1]["content"]
    lines = poll(job, fake, interval=0)
    assert lines[0]["custom_id"] == "title|Q1|zh"


def test_apply_merges_strips_and_skips_bad(session, monkeypatch):
    import app.services.enrichment.batch_names as bn

    recorded = []
    monkeypatch.setattr(
        bn, "record_llm_usage", lambda ch, model, tin, tout, db=None: recorded.append(model)
    )
    lines = [
        _ok_line("title|Q1|zh", "《蒙娜丽莎》"),  # 剥号后写入
        _ok_line("artist|QA1|zh", "达·芬奇"),
        {"custom_id": "title|Q1|ja", "response": None, "error": {"message": "boom"}},  # 坏行跳过
        _ok_line("title|Q404|zh", "无主"),  # 实体不存在跳过
    ]
    out = apply(session, lines)
    o = session.query(MuseumObject).filter_by(qid="Q1").one()
    assert o.attributes["title_i18n"]["zh"] == "蒙娜丽莎"  # 已剥号
    assert session.query(Artist).one().name_i18n["zh"] == "达·芬奇"
    assert out["applied"] == 2 and out["skipped"] == 2
    assert recorded == ["gpt-4o@batch", "gpt-4o@batch"]  # 记账半价价目


def test_apply_does_not_overwrite_existing(session):
    o = session.query(MuseumObject).filter_by(qid="Q1").one()
    o.attributes = {**o.attributes, "title_i18n": {"zh": "既有译名"}}
    session.commit()
    apply(session, [_ok_line("title|Q1|zh", "新译名")])
    assert (
        session.query(MuseumObject).filter_by(qid="Q1").one().attributes["title_i18n"]["zh"]
        == "既有译名"
    )  # 只补缺不覆盖


def test_state_roundtrip(tmp_path):
    p = str(tmp_path / "s.json")
    save_state(p, "batch-9", 42)
    st = load_state(p)
    assert st["job_id"] == "batch-9" and st["task_count"] == 42
```

- [ ] **Step 2: 红** → **Step 3: 实现**(batch_names.py 追加)

```python
def _jsonl(tasks):
    from app.services.enrichment.prompts import build_name_translation_prompt

    lines = []
    for t in tasks:
        system, user = build_name_translation_prompt(t.name, t.lang)
        lines.append(
            json.dumps(
                {
                    "custom_id": t.custom_id,
                    "method": "POST",
                    "url": "/v1/chat/completions",
                    "body": {
                        "model": MODEL,
                        "messages": [
                            {"role": "system", "content": system},
                            {"role": "user", "content": user},
                        ],
                        "temperature": 0.3,
                    },
                },
                ensure_ascii=False,
            )
        )
    return "\n".join(lines)


def submit(tasks, client) -> str:
    import io

    f = client.files.create(
        file=io.BytesIO(_jsonl(tasks).encode()), purpose="batch"
    )
    b = client.batches.create(
        input_file_id=f.id,
        endpoint="/v1/chat/completions",
        completion_window="24h",
    )
    return b.id


def poll(job_id, client, interval=60):
    while True:
        b = client.batches.retrieve(job_id)
        if b.status == "completed":
            text = client.files.content(b.output_file_id).text
            return [json.loads(x) for x in text.splitlines() if x.strip()]
        if b.status in ("failed", "expired", "cancelled"):
            raise RuntimeError(f"batch {job_id} 终态 {b.status}")
        logger.info("batch %s status=%s,继续等待", job_id, b.status)
        time.sleep(interval)


def apply(db, lines) -> dict:
    from app.models.artist import Artist
    from app.models.museum_object import MuseumObject
    from app.services.enrichment.translator import strip_name
    from app.services.llm_usage import record_llm_usage

    applied = skipped = 0
    for i, ln in enumerate(lines):
        try:
            cid = ln["custom_id"]
            body = (ln.get("response") or {}).get("body") or {}
            text = strip_name(body["choices"][0]["message"]["content"])
            if not text:
                raise ValueError("empty")
            etype, key, lang = cid.split("|", 2)
            u = body.get("usage") or {}
            record_llm_usage(
                "names", USAGE_MODEL,
                u.get("prompt_tokens", 0), u.get("completion_tokens", 0),
            )
            if etype == "title":
                o = db.query(MuseumObject).filter_by(qid=key).one_or_none()
                if o is None:
                    raise ValueError("no object")
                ti = dict((o.attributes or {}).get("title_i18n") or {})
                if not ti.get(lang):  # 只补缺不覆盖
                    ti[lang] = text
                    o.attributes = {**(o.attributes or {}), "title_i18n": ti}
            else:
                a = db.query(Artist).filter_by(qid=key).one_or_none()
                if a is None:
                    raise ValueError("no artist")
                ni = dict(a.name_i18n or {})
                if not ni.get(lang):
                    ni[lang] = text
                    a.name_i18n = ni
            applied += 1
        except Exception:
            skipped += 1  # 坏行=仍缺→幂等重跑再补(纪律①)
        if (i + 1) % 200 == 0:
            db.commit()
    db.commit()
    return {"applied": applied, "skipped": skipped}


def save_state(path, job_id, task_count):
    with open(path, "w") as f:
        json.dump({"job_id": job_id, "task_count": task_count, "at": time.time()}, f)


def load_state(path):
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return None
```

(注意:apply 里 `record_llm_usage` 直接 import 到模块级供 monkeypatch——按测试写法,把 import 放模块顶部:`from app.services.llm_usage import record_llm_usage`,apply 内直接用。)

- [ ] **Step 4: 绿** → **Step 5: Commit** `git commit -m "feat(cost): batch_names submit/poll/apply+状态落盘(fake client TDD)"`

### Task 4: run 编排 + onboard wiring + 价目

**Files:**
- Modify: `backend/app/services/enrichment/batch_names.py`(追加 run)
- Modify: `backend/scripts/onboard.py`(na 加 `--use-batch/--batch-job`;cmd_names 分流)
- Modify: `backend/scripts/llm_cost_report.py`(PRICES 加行)

**Interfaces:**
- Produces: `run(db, slug, langs, *, client=None, limit=None, job_id=None, state_path=None, poll_interval=60) -> dict`

- [ ] **Step 1: run 实现**(batch_names.py 追加;client=None 时建同步 OpenAI)

```python
def run(db, slug, langs, *, client=None, limit=None, job_id=None,
        state_path=None, poll_interval=60) -> dict:
    if client is None:
        from openai import OpenAI

        from app.core.config import settings

        client = OpenAI(api_key=settings.OPENAI_API_KEY)
    state_path = state_path or f"/tmp/{slug}_names_batch.json"
    if job_id is None:
        tasks = collect_missing(db, slug, langs, limit=limit)
        if not tasks:
            return {"tasks": 0, "applied": 0, "skipped": 0}
        job_id = submit(tasks, client)
        save_state(state_path, job_id, len(tasks))
        logger.info("batch %s 已提交 %d 任务(状态: %s)", job_id, len(tasks), state_path)
    lines = poll(job_id, client, interval=poll_interval)
    out = apply(db, lines)
    out["tasks"] = len(lines)
    out["job_id"] = job_id
    return out
```

- [ ] **Step 2: onboard wiring**:argparse `na.add_argument("--use-batch", action="store_true")`、`na.add_argument("--batch-job", default=None)`;`cmd_names` 签名加 `use_batch=False, batch_job=None`,在 `staging_limit` 之后分流:

```python
    if use_batch or batch_job:
        from app.services.enrichment.backfill import _ENSURE  # 不存在则删此行
        from app.services.enrichment.batch_names import run as batch_run
        from app.services.enrichment.lang_config import resolve_languages

        cfg = _catalog().get(slug)
        target_langs = resolve_languages(
            [s.strip() for s in langs.split(",")] if langs else cfg.languages
        )
        db = SessionLocal()
        try:
            out = batch_run(db, slug, target_langs, limit=limit, job_id=batch_job)
        finally:
            db.close()
        print(f"✓ names(batch): {out}")
        return
```

(`_ENSURE` 行是防呆示例文字,实际不写;main 分发补传 `ns.use_batch, ns.batch_job`。)

- [ ] **Step 3: PRICES 加行**(llm_cost_report.py):`"gpt-4o@batch": (1.25, 5.00),`

- [ ] **Step 4: 全量测试 + 冒烟**

```bash
cd backend && python -m pytest tests/integration/test_batch_names.py tests/integration/test_backfill_names.py tests/unit/services/test_llm_usage.py -q --no-cov -p no:cacheprovider
python scripts/onboard.py louvre names --target prod --use-batch 2>&1 | tail -1
# 预期: ❌ ENVIRONMENT 守卫拦截(wiring 通)
```

- [ ] **Step 5: Commit + PR→staging 合并**

```bash
git add backend/app/services/enrichment/batch_names.py backend/scripts/onboard.py backend/scripts/llm_cost_report.py backend/tests/integration/test_batch_names.py
git commit -m "feat(cost): names Batch 模式(collect/submit/poll/apply/run+onboard wiring+半价价目)"
gh pr create --base staging --head feature/batch-names --title "feat(cost): names Batch 模式(成本工程②,半价+免盯守)" --body "spec: docs/superpowers/specs/2026-07-19-batch-names-design.md"
```

### Task 5: staging 真钱全链验证

**Files:** 无(运维)

- [ ] **Step 1**: 合并部署后,staging 容器跑(护栏自动小样本;先造缺口:staging 金样本 names 已齐→用 `--limit 5` 配合一个缺语言的对象,或直接对 orangerie staging 数据跑——其 names 只做过 50 件,仍有缺口):

```bash
docker exec -d gomuseum_staging_backend sh -c "cd /app && setsid python scripts/onboard.py orangerie names --target staging --use-batch > /tmp/batch_names_verify.log 2>&1"
# 观察 log: 提交任务数→job id→轮询→"✓ names(batch): {...applied...}"
```

- [ ] **Step 2**: 验收:`llm_cost_report --days 1` 出现 `names gpt-4o@batch` 行;抽查 3 个新译名质量(剥号/无残片);kill 重跑 `--batch-job <id>` 断点续传实测
- [ ] **Step 3**: 记忆更新(product-backlog:成本工程②完成)——B(卢浮宫 spec)就绪可开

---

## Self-Review

1. **Spec coverage**:§1 CLI 四阶段+状态落盘→T3/T4;只 Batch 化 translate_name→T2 collect 范围;§2 记账→T3 apply+T4 PRICES;§3 模块落点→T2-T4;§4 验证→各 TDD+T5 真钱 ✓
2. **Placeholder**:T4 Step2 有一行防呆示例文字已标明"实际不写";其余代码完整 ✓
3. **一致性**:`BatchTask/collect_missing/submit/poll/apply/run/save_state/load_state` 签名各任务一致;custom_id 三段式与测试一致;`record_llm_usage` 模块顶导入供 monkeypatch ✓
