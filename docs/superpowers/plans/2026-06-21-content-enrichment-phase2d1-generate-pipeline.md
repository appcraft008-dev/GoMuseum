# 内容富化 Phase 2d-1 generate 编排管线 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把前三期原语（2a 生成 / 2b 质量闸 / 2c 翻译）接成一条可批量运行的 generate 编排：从 DB 读已 load 的对象 → 组材料 → 生成英语草稿 → 过质量闸 → 落英语 → 翻译铺语言 → 按语言落库，并配 `onboard.py generate` CLI（三触发之一）。

**Architecture:** 新增 `enrichment/pipeline.py`（纯编排，注入 enricher/gate/translator，整体离线可测）；`onboard.py` 加 `cmd_generate` + `generate` 子命令（构造真实组件 = `default_complete`，带 `--target` 环境守卫，与 `cmd_load` 同款）。落库复用 2b 的 `persist_gated_sections`。

**Tech Stack:** Python 3.11 · FastAPI · SQLAlchemy · pytest · OpenAI（gpt-4o-mini，经 `default_complete`）。

**本期范围（2d 拆三：本计划是 2d-1 编排脊柱）:** 仅 generate 编排 + CLI。**建议问答（§12b，需新 DB 模型+迁移）= 2d-2；canary 质量报告（§8B）= 2d-3**，各自独立计划，不在本期。幂等：已发布英语段默认跳过（`--force` 强制重生成），honoring "生成一次永久落库、不重复付费"（spec §7）。

**前置事实（已验证，勿重查）:**
- `build_material(obj)` 在 `content_enricher.py`，读 `obj["title_en"/"artist_en"/"year"/"category"/"attributes"]`（attributes 含 `extract_*`/Joconde，来自 fetch→load）。
- `sections_for(category)` 在 `category_config.py`。
- `ContentEnricher(complete).generate_canonical(obj, sections) -> {code: body|None}`（2a）。
- `QualityGate(complete).gate(material, facts, sections) -> {code: SectionQuality}`（2b）；`SectionQuality(body,status,grounding_ratio,conflicts,score)`。
- `ContentTranslator(complete).translate_object(en_sections, target_langs) -> {lang: {code: SectionQuality}}`，跳过 "en"（2c）。
- `persist_gated_sections(db, qid, language, results, model) -> (pub, nr)`（2b，按段写 published/needs_review）。
- `resolve_languages(override)` 在 `lang_config.py`；`MuseumConfig.languages`（2c）。
- `default_complete` 在 `content_enricher.py`（gpt-4o-mini）。
- `Museum`（`models/museum.py`，`slug` 唯一）、`MuseumObject`（`models/museum_object.py`，`museum_id`/`popularity`/`qid`/`category`/`attributes`）、`ObjectContentSection`（`models/content.py`，`object_id`/`language`/`section_code`/`status`）。
- CLI 守卫范式：`cmd_load` 用 `settings.ENVIRONMENT` 对 `--target` 守卫（`_ENV_BY_TARGET={"prod":"production","staging":"staging"}`）；测试见 `tests/unit/services/enrichment/test_onboard_cli.py`（`from scripts import onboard` / `from scripts.onboard import build_parser`）。
- 集成测试 `session` fixture（`tests/integration/test_content_persist.py`）已 seed museum `orsay`(slug) + object `qid="Q1"`(category=painting，title_en="A")。

---

## 文件结构

| 文件 | 职责 | 动作 |
|---|---|---|
| `backend/app/services/enrichment/pipeline.py` | `_row_to_obj`/`_facts_text`/`generate_object`/`generate_museum` 编排 | **新建** |
| `backend/scripts/onboard.py` | 加 `generate` 子命令 + `cmd_generate`（环境守卫 + 构造真实组件） | 修改 |
| `backend/tests/unit/services/enrichment/test_pipeline.py` | 编排 helper 单测 | **新建** |
| `backend/tests/integration/test_generate_pipeline.py` | `generate_object`/`generate_museum` 集成测试 | **新建** |
| `backend/tests/unit/services/enrichment/test_onboard_cli.py` | 追加 generate 的 parser + 环境守卫测试 | 修改 |

**关键接口（先定死）:**

```python
# pipeline.py
def generate_object(db, qid, *, enricher, gate, translator,
                    target_langs, model, force=False) -> dict: ...
def generate_museum(db, slug, *, enricher, gate, translator,
                    target_langs, model, force=False, limit=None) -> dict: ...
```

---

## Task 1: 编排 helper `_row_to_obj` + `_facts_text`

**Files:**
- Create: `backend/app/services/enrichment/pipeline.py`
- Test: `backend/tests/unit/services/enrichment/test_pipeline.py`

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/unit/services/enrichment/test_pipeline.py
from types import SimpleNamespace

from app.services.enrichment.pipeline import _facts_text, _row_to_obj


def test_row_to_obj_maps_columns_and_attributes():
    o = SimpleNamespace(
        title_en="Olympia", artist_en="Manet", year="1863",
        category="painting", attributes={"extract_en": "lead text"},
    )
    obj = _row_to_obj(o)
    assert obj["title_en"] == "Olympia"
    assert obj["category"] == "painting"
    assert obj["attributes"]["extract_en"] == "lead text"


def test_row_to_obj_handles_none_attributes():
    o = SimpleNamespace(
        title_en="X", artist_en=None, year=None, category="painting", attributes=None
    )
    assert _row_to_obj(o)["attributes"] == {}


def test_facts_text_lists_present_hard_facts_only():
    obj = {"title_en": "Olympia", "artist_en": "Manet", "year": "1863"}
    facts = _facts_text(obj)
    assert "- Title: Olympia" in facts
    assert "- Artist: Manet" in facts
    assert "- Year: 1863" in facts


def test_facts_text_skips_missing():
    facts = _facts_text({"title_en": "Olympia", "artist_en": None, "year": None})
    assert facts == "- Title: Olympia"
```

- [ ] **Step 2: 跑确认失败**

Run: `cd backend && poetry run pytest tests/unit/services/enrichment/test_pipeline.py -v`
Expected: FAIL（`ModuleNotFoundError: pipeline`）

- [ ] **Step 3: 创建 `backend/app/services/enrichment/pipeline.py`**

```python
"""generate 编排：DB 对象 → 生成(2a) → 质量闸(2b) → 落英语 → 翻译(2c) → 按语言落库。
组件注入（enricher/gate/translator），整体离线可测。spec §7 / §17 三触发之一。"""

from __future__ import annotations

from app.services.content_repo import persist_gated_sections
from app.services.enrichment.category_config import sections_for
from app.services.enrichment.content_enricher import build_material

_FACT_KEYS = [("Title", "title_en"), ("Artist", "artist_en"), ("Year", "year")]


def _row_to_obj(o) -> dict:
    """MuseumObject 行 → build_material/生成器吃的 obj dict。"""
    return {
        "title_en": o.title_en,
        "artist_en": o.artist_en,
        "year": o.year,
        "category": o.category,
        "attributes": o.attributes or {},
    }


def _facts_text(obj: dict) -> str:
    """结构化硬事实文本（供质量闸事实对账）；缺字段跳过。"""
    lines = []
    for label, key in _FACT_KEYS:
        v = obj.get(key)
        if v:
            lines.append(f"- {label}: {v}")
    return "\n".join(lines)
```

- [ ] **Step 4: 跑确认通过**

Run: `cd backend && poetry run pytest tests/unit/services/enrichment/test_pipeline.py -v`
Expected: PASS（4 passed）（单文件触发仓库覆盖率门时加 `--no-cov`）

- [ ] **Step 5: 提交**

```bash
cd backend && poetry run black app/services/enrichment/pipeline.py tests/unit/services/enrichment/test_pipeline.py && poetry run isort app/services/enrichment/pipeline.py tests/unit/services/enrichment/test_pipeline.py
cd /Users/hongyang/Projects/GoMuseum && git add backend/app/services/enrichment/pipeline.py backend/tests/unit/services/enrichment/test_pipeline.py
git commit -m "feat(enrichment): generate 编排 helper _row_to_obj/_facts_text"
```

---

## Task 2: `generate_object`（单件编排 + 幂等跳过）

**Files:**
- Modify: `backend/app/services/enrichment/pipeline.py`
- Test: `backend/tests/integration/test_generate_pipeline.py`

设计要点：
- 查 `MuseumObject` by qid；不存在 → `{"qid":qid,"skipped":"absent"}`。
- 非 `force` 且已有 published 英语段 → `{"qid":qid,"skipped":"exists"}`（幂等，不重复付费）。
- 否则：组 obj/material/facts/sections → `enricher.generate_canonical` → `gate.gate` → 落英语 → 取已发布英语 body 喂 `translator.translate_object` → 按语言落库。
- 返回 `{"qid":qid,"counts":{"en":(pub,nr), <lang>:(pub,nr), ...}}`。

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/integration/test_generate_pipeline.py
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.models.content import ObjectContentSection
from app.models.museum import Museum
from app.models.museum_object import MuseumObject, ObjectImage
from app.services.enrichment.quality import SectionQuality
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
            ObjectContentSection.__table__,
        ],
    )
    s = sessionmaker(bind=engine)()
    m = upsert_museum(s, {"slug": "orsay", "name_en": "Orsay"})
    upsert_object(
        s, m.id,
        {"qid": "Q1", "title_en": "A", "category": "painting", "attributes": {}},
    )
    s.commit()
    yield s


class _FakeEnricher:
    def generate_canonical(self, obj, sections):
        return {"overview": "EN overview."}


class _FakeGate:
    def gate(self, material, facts, draft):
        return {
            "overview": SectionQuality(
                body="EN overview.", status="published",
                grounding_ratio=1.0, conflicts=[], score=1.0,
            )
        }


class _FakeTranslator:
    def translate_object(self, en_sections, target_langs):
        # 模拟 2c：跳过 en，铺 fr
        return {
            "fr": {
                "overview": SectionQuality(
                    body="FR aperçu.", status="published",
                    grounding_ratio=1.0, conflicts=[], score=1.0,
                )
            }
        }


def _run(session, qid, **kw):
    from app.services.enrichment.pipeline import generate_object

    return generate_object(
        session, qid,
        enricher=_FakeEnricher(), gate=_FakeGate(), translator=_FakeTranslator(),
        target_langs=["en", "fr"], model="gpt-4o-mini", **kw,
    )


def test_generate_object_persists_en_and_translation(session):
    out = _run(session, "Q1")
    assert out["counts"]["en"] == (1, 0)
    assert out["counts"]["fr"] == (1, 0)
    rows = {(r.language, r.section_code): r
            for r in session.query(ObjectContentSection).all()}
    assert rows[("en", "overview")].body == "EN overview."
    assert rows[("fr", "overview")].body == "FR aperçu."


def test_generate_object_skips_when_already_published(session):
    _run(session, "Q1")
    out2 = _run(session, "Q1")
    assert out2["skipped"] == "exists"


def test_generate_object_force_regenerates(session):
    _run(session, "Q1")
    out2 = _run(session, "Q1", force=True)
    assert "counts" in out2 and "skipped" not in out2


def test_generate_object_absent_qid(session):
    assert _run(session, "Q404")["skipped"] == "absent"
```

- [ ] **Step 2: 跑确认失败**

Run: `cd backend && poetry run pytest tests/integration/test_generate_pipeline.py -v`
Expected: FAIL（`cannot import name generate_object`）

- [ ] **Step 3: 在 `pipeline.py` 追加**

```python
from app.models.museum_object import MuseumObject  # noqa: E402
from app.models.content import ObjectContentSection  # noqa: E402


def _has_published_en(db, object_id) -> bool:
    return (
        db.query(ObjectContentSection)
        .filter_by(object_id=object_id, language="en", status="published")
        .first()
        is not None
    )


def generate_object(
    db, qid, *, enricher, gate, translator, target_langs, model, force=False
) -> dict:
    """单件：生成→质量闸→落英语→翻译→按语言落库。幂等跳过已发布英语（除非 force）。"""
    o = db.query(MuseumObject).filter_by(qid=qid).one_or_none()
    if not o:
        return {"qid": qid, "skipped": "absent"}
    if not force and _has_published_en(db, o.id):
        return {"qid": qid, "skipped": "exists"}

    obj = _row_to_obj(o)
    material = build_material(obj)
    facts = _facts_text(obj)
    sections = sections_for(o.category)

    draft = enricher.generate_canonical(obj, sections)
    gated_en = gate.gate(material, facts, draft)
    pub_en, nr_en = persist_gated_sections(db, qid, "en", gated_en, model)

    en_published = {
        code: r.body
        for code, r in gated_en.items()
        if r.status == "published" and r.body
    }
    by_lang = translator.translate_object(en_published, target_langs)

    counts = {"en": (pub_en, nr_en)}
    for lang, results in by_lang.items():
        counts[lang] = persist_gated_sections(db, qid, lang, results, model)
    return {"qid": qid, "counts": counts}
```

> 把这两个 `from app.models...` import 提到文件顶部 import 区（与现有 import 并列）即可，无需 `# noqa`；此处标注只为说明依赖。

- [ ] **Step 4: 跑确认通过**

Run: `cd backend && poetry run pytest tests/integration/test_generate_pipeline.py -v`
Expected: PASS（4 passed）

- [ ] **Step 5: 提交**

```bash
cd backend && poetry run black app/services/enrichment/pipeline.py tests/integration/test_generate_pipeline.py && poetry run isort app/services/enrichment/pipeline.py tests/integration/test_generate_pipeline.py
cd /Users/hongyang/Projects/GoMuseum && git add backend/app/services/enrichment/pipeline.py backend/tests/integration/test_generate_pipeline.py
git commit -m "feat(enrichment): generate_object 单件编排(生成→闸→翻译→落库,幂等跳过)"
```

---

## Task 3: `generate_museum`（按馆批量）

**Files:**
- Modify: `backend/app/services/enrichment/pipeline.py`
- Test: `backend/tests/integration/test_generate_pipeline.py`（追加）

设计要点：
- 查 `Museum` by slug；不存在 → `{"slug":slug,"error":"unknown museum"}`。
- 取该馆对象按 `popularity` 降序；`limit` 截断；逐件 `generate_object`，聚合。
- 返回 `{"slug":slug,"objects":N,"results":[...]}`。

- [ ] **Step 1: 写失败测试（追加；在文件顶部已 import 的基础上）**

```python
def test_generate_museum_runs_over_objects(session):
    from app.services.enrichment.pipeline import generate_museum

    out = generate_museum(
        session, "orsay",
        enricher=_FakeEnricher(), gate=_FakeGate(), translator=_FakeTranslator(),
        target_langs=["en", "fr"], model="gpt-4o-mini",
    )
    assert out["objects"] == 1
    assert out["results"][0]["qid"] == "Q1"
    # 真落库了
    assert session.query(ObjectContentSection).filter_by(language="en").count() == 1


def test_generate_museum_unknown_slug(session):
    from app.services.enrichment.pipeline import generate_museum

    out = generate_museum(
        session, "nope",
        enricher=_FakeEnricher(), gate=_FakeGate(), translator=_FakeTranslator(),
        target_langs=["en"], model="m",
    )
    assert out["error"] == "unknown museum"
```

- [ ] **Step 2: 跑确认失败**

Run: `cd backend && poetry run pytest tests/integration/test_generate_pipeline.py -k museum -v`
Expected: FAIL（`cannot import name generate_museum`）

- [ ] **Step 3: 在 `pipeline.py` 追加**（顶部 import 区加 `from app.models.museum import Museum`）

```python
def generate_museum(
    db, slug, *, enricher, gate, translator, target_langs, model, force=False, limit=None
) -> dict:
    """按馆批量：popularity 降序逐件 generate_object，聚合。"""
    m = db.query(Museum).filter_by(slug=slug).one_or_none()
    if not m:
        return {"slug": slug, "error": "unknown museum"}
    q = (
        db.query(MuseumObject)
        .filter_by(museum_id=m.id)
        .order_by(MuseumObject.popularity.desc())
    )
    if limit:
        q = q.limit(limit)
    results = [
        generate_object(
            db, o.qid,
            enricher=enricher, gate=gate, translator=translator,
            target_langs=target_langs, model=model, force=force,
        )
        for o in q.all()
    ]
    return {"slug": slug, "objects": len(results), "results": results}
```

- [ ] **Step 4: 跑确认通过**

Run: `cd backend && poetry run pytest tests/integration/test_generate_pipeline.py -v`
Expected: PASS（6 passed）

- [ ] **Step 5: 提交**

```bash
cd backend && poetry run black app/services/enrichment/pipeline.py tests/integration/test_generate_pipeline.py && poetry run isort app/services/enrichment/pipeline.py tests/integration/test_generate_pipeline.py
cd /Users/hongyang/Projects/GoMuseum && git add backend/app/services/enrichment/pipeline.py backend/tests/integration/test_generate_pipeline.py
git commit -m "feat(enrichment): generate_museum 按馆批量编排"
```

---

## Task 4: CLI `generate` 子命令 + `cmd_generate`（环境守卫）

**Files:**
- Modify: `backend/scripts/onboard.py`
- Test: `backend/tests/unit/services/enrichment/test_onboard_cli.py`（追加）

设计要点：
- `generate` 子命令参数：`--target`(必填,staging/prod)、`--qid`(单件,可空)、`--langs`(逗号分隔,可空→按馆/默认)、`--force`、`--limit`(int,可空)。
- `cmd_generate` **先做环境守卫**（与 `cmd_load` 同，防错环境），再构造 `default_complete` 组件（守卫在前，避免无 key 时也能测守卫）。
- `--langs` 解析：`"en,fr"`→`["en","fr"]`；空→`resolve_languages(cfg.languages)`。

- [ ] **Step 1: 写失败测试（追加到 `test_onboard_cli.py`）**

```python
def test_parser_generate_command():
    ns = build_parser().parse_args(
        ["orsay", "generate", "--target", "staging", "--qid", "Q1",
         "--langs", "en,fr", "--force", "--limit", "5"]
    )
    assert ns.command == "generate"
    assert ns.target == "staging" and ns.qid == "Q1"
    assert ns.langs == "en,fr" and ns.force is True and ns.limit == 5


def test_cmd_generate_aborts_on_env_mismatch(monkeypatch):
    monkeypatch.setattr(settings, "ENVIRONMENT", "staging")
    with pytest.raises(SystemExit, match="ENVIRONMENT"):
        onboard.cmd_generate(
            "orsay", qid=None, langs=None, force=False, limit=None, target="prod"
        )
```

- [ ] **Step 2: 跑确认失败**

Run: `cd backend && poetry run pytest tests/unit/services/enrichment/test_onboard_cli.py -k generate -v`
Expected: FAIL（parser 无 generate / `cmd_generate` 不存在）

- [ ] **Step 3: 改 `onboard.py`**

在 `build_parser()` 里 `load` 子命令之后追加：

```python
    ge = sub.add_parser("generate")
    ge.add_argument("--target", choices=["staging", "prod"], required=True)
    ge.add_argument("--qid", default=None)
    ge.add_argument("--langs", default=None)
    ge.add_argument("--force", action="store_true")
    ge.add_argument("--limit", type=int, default=None)
```

加 `cmd_generate`（放在 `cmd_load` 之后）：

```python
def cmd_generate(slug, qid, langs, force, limit, target) -> None:
    # 守卫：--target 必须匹配当前容器 ENVIRONMENT（与 cmd_load 同，先于构造 LLM 组件）
    expected = _ENV_BY_TARGET[target]
    if settings.ENVIRONMENT != expected:
        raise SystemExit(
            f"❌ --target={target} 期望容器 ENVIRONMENT={expected}，"
            f"但当前容器 ENVIRONMENT={settings.ENVIRONMENT}。请在 {expected} 环境容器内运行。"
        )

    from app.services.enrichment.content_enricher import (
        ContentEnricher,
        default_complete,
    )
    from app.services.enrichment.lang_config import resolve_languages
    from app.services.enrichment.pipeline import generate_museum, generate_object
    from app.services.enrichment.quality import QualityGate
    from app.services.enrichment.translator import ContentTranslator

    override = [s.strip() for s in langs.split(",")] if langs else _catalog().get(slug).languages
    target_langs = resolve_languages(override)
    enricher = ContentEnricher(default_complete)
    gate = QualityGate(default_complete)
    translator = ContentTranslator(default_complete)

    db = SessionLocal()
    try:
        if qid:
            out = generate_object(
                db, qid, enricher=enricher, gate=gate, translator=translator,
                target_langs=target_langs, model="gpt-4o-mini", force=force,
            )
        else:
            out = generate_museum(
                db, slug, enricher=enricher, gate=gate, translator=translator,
                target_langs=target_langs, model="gpt-4o-mini", force=force, limit=limit,
            )
    finally:
        db.close()
    print(f"✓ generate 完成: {out}")
```

在 `main()` 的分发里加分支（现有 `if ns.command == "fetch": ... else: cmd_load(...)` 改成显式三分支）：

```python
def main(argv=None) -> None:
    ns = build_parser().parse_args(argv)
    if ns.command == "fetch":
        cmd_fetch(ns.slug)
    elif ns.command == "generate":
        cmd_generate(ns.slug, ns.qid, ns.langs, ns.force, ns.limit, ns.target)
    else:
        cmd_load(ns.slug, ns.pack, ns.sample, ns.target)
```

- [ ] **Step 4: 跑确认通过**

Run: `cd backend && poetry run pytest tests/unit/services/enrichment/test_onboard_cli.py -v`
Expected: PASS（既有 + 新 2 全 passed）

- [ ] **Step 5: 提交**

```bash
cd backend && poetry run black scripts/onboard.py tests/unit/services/enrichment/test_onboard_cli.py && poetry run isort scripts/onboard.py tests/unit/services/enrichment/test_onboard_cli.py
cd /Users/hongyang/Projects/GoMuseum && git add backend/scripts/onboard.py backend/tests/unit/services/enrichment/test_onboard_cli.py
git commit -m "feat(enrichment): onboard generate 子命令+cmd_generate(环境守卫+构造管线)"
```

---

## 收尾

- [ ] **全套相关测试**：
```bash
cd backend && STORAGE_BACKEND=local poetry run pytest \
  tests/unit/services/enrichment/test_pipeline.py \
  tests/unit/services/enrichment/test_onboard_cli.py \
  tests/integration/test_generate_pipeline.py \
  -W "ignore::PendingDeprecationWarning" -v
```
Expected: 全 passed。

- [ ] **提 PR**：`feature/content-enrichment-phase2d1 → staging`（用 `/pr`）。无 DB 迁移。CI 绿后 squash 合并、删分支。
- [ ]（关键·可选）合并后在 staging 容器真跑一次端到端：先确保目标对象已经 fetch→load（attributes 含 `extract_*`），再
  `docker exec gomuseum_staging_backend python scripts/onboard.py orsay generate --target staging --qid <QID> --langs en,fr`，
  查 `object_content?language=fr` 看 en/fr 段落已落库、needs_review 段为"待完善"。

---

## Self-Review（计划对照 spec §7/§17）

- **§7 统一编排（生成→闸→翻译→落库）**：`generate_object`（Task 2）串起 2a/2b/2c + `persist_gated_sections` ✓。
- **§7 幂等（已 published 跳过、`--force`）**：`_has_published_en` + force 分支（Task 2）✓。
- **§17 批量 CLI（三触发之一）**：`generate_museum`（Task 3）+ `onboard generate`（Task 4）✓。
- **环境守卫（防错环境写库）**：`cmd_generate` 复用 `cmd_load` 守卫范式（Task 4）✓。
- **语言集配置驱动**：`--langs` 覆盖 / 缺省 `resolve_languages(cfg.languages)`（Task 4）✓。
- **注入式离线可测**：`generate_object`/`generate_museum` 注入 enricher/gate/translator，集成测试全 fake ✓。
- **类型一致性**：`generate_object` 返回 `{"qid","counts"|"skipped"}`、`generate_museum` 返回 `{"slug","objects","results"}`，`counts[lang]=(pub,nr)` 与 `persist_gated_sections` 返回一致（Task 2/3）✓。fake 组件签名与真实 2a/2b/2c 方法签名对齐 ✓。
- **DRY**：复用 2a `build_material`、2b `gate`/`persist_gated_sections`/`SectionQuality`、2c `translate_object`、`resolve_languages`、`sections_for` ✓。
- **本期不做（显式）**：建议问答 §12b（2d-2，需 DB 迁移）、canary 报告 §8B（2d-3）、懒生成端点/识别接入（Phase 3+）——非遗漏。
