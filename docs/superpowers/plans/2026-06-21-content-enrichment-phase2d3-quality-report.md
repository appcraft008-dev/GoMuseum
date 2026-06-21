# 内容富化 Phase 2d-3 canary 质量报告 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 从 DB 已生成内容算一份"内容质量报告"（每馆/每语言：覆盖率、published/needs_review 数与比例、缺音频数），CLI 一键看，作为批量生成后、上 prod 前的金丝雀关卡（spec §8B）。

**Architecture:** 新增 `enrichment/content_report.py`（`build_quality_report` 纯查询计算，dict + markdown）；`onboard.py` 加只读 `report` 子命令。与既有 `report.py`（fetch 期数据覆盖报告）职责分开，不动它。

**Tech Stack:** Python 3.11 · FastAPI · SQLAlchemy · pytest。

**本期范围（§8B 子集，无 DB 迁移）:** 覆盖率 / needs_review% / 各语言覆盖 / 缺音频数——全部从现有列算。**接地分分布、源冲突数需额外落库列（score/conflicts），属后续（DB 迁移）显式不做**。

**前置事实（已验证，勿重查）:**
- `ObjectContentSection` 列：`object_id` / `language` / `section_code` / `body` / `audio_key`(nullable) / `status`(published|needs_review|draft) / `source` / `model`（`app/models/content.py`）。gate 的 grounding_ratio/score **未落库**（`persist_gated_sections` 只存 body/status/model）→ 本期报告不含接地分分布。
- `Museum`(slug 唯一) / `MuseumObject`(museum_id)（`app/models/museum.py` / `museum_object.py`）。
- `resolve_languages(override)`、`MuseumConfig.languages`（`lang_config.py` / `catalog.py`，2c）。
- `onboard.py`：`from scripts import onboard` 可导入；`build_parser()` 用 subparsers；`_catalog()` 取 `MuseumConfig`；测试范式 `tests/unit/services/enrichment/test_onboard_cli.py`。
- 集成测试可仿 `tests/integration/test_content_persist.py` 的 in-memory SQLite + `upsert_museum`/`upsert_object` fixture，并直接造 `ObjectContentSection` 行。

---

## 文件结构

| 文件 | 职责 | 动作 |
|---|---|---|
| `backend/app/services/enrichment/content_report.py` | `build_quality_report(db, slug, languages, as_markdown=False)` | **新建** |
| `backend/scripts/onboard.py` | 加只读 `report` 子命令 + `cmd_report` | 修改 |
| `backend/tests/integration/test_content_report.py` | 报告计算 + markdown 集成测试 | **新建** |
| `backend/tests/unit/services/enrichment/test_onboard_cli.py` | 追加 report parser 测试 | 修改 |

**报告 dict 形状（先定死）:**

```python
{
  "slug": "orsay",
  "objects_total": 3,
  "languages": {
    "en": {"published": 5, "needs_review": 2, "pct_needs_review": 0.286,
           "objects_covered": 2, "coverage": 0.667},
    "fr": {...},
  },
  "missing_audio": 5,   # 已发布但无 audio_key 的段数
}
# 未知馆 → {"slug": slug, "error": "unknown museum"}
```

---

## Task 1: `build_quality_report`（计算 dict）

**Files:**
- Create: `backend/app/services/enrichment/content_report.py`
- Test: `backend/tests/integration/test_content_report.py`

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/integration/test_content_report.py
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.models.content import ObjectContentSection
from app.models.museum import Museum
from app.models.museum_object import MuseumObject, ObjectImage
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
    o1 = upsert_object(s, m.id, {"qid": "Q1", "title_en": "A", "category": "painting"})
    o2 = upsert_object(s, m.id, {"qid": "Q2", "title_en": "B", "category": "painting"})
    upsert_object(s, m.id, {"qid": "Q3", "title_en": "C", "category": "painting"})
    s.commit()
    # Q1 en: overview published(有音频) + artist needs_review；fr: overview published(无音频)
    # Q2 en: overview published(无音频)
    rows = [
        ObjectContentSection(object_id=o1.id, language="en", section_code="overview",
                             body="x", status="published", audio_key="a.mp3"),
        ObjectContentSection(object_id=o1.id, language="en", section_code="artist",
                             body=None, status="needs_review"),
        ObjectContentSection(object_id=o1.id, language="fr", section_code="overview",
                             body="y", status="published"),
        ObjectContentSection(object_id=o2.id, language="en", section_code="overview",
                             body="z", status="published"),
    ]
    s.add_all(rows)
    s.commit()
    yield s


def test_quality_report_counts_and_coverage(session):
    from app.services.enrichment.content_report import build_quality_report

    rep = build_quality_report(session, "orsay", ["en", "fr"])
    assert rep["objects_total"] == 3
    en = rep["languages"]["en"]
    assert en["published"] == 2 and en["needs_review"] == 1
    assert en["pct_needs_review"] == round(1 / 3, 3)
    assert en["objects_covered"] == 2          # Q1, Q2 有已发布 en
    assert en["coverage"] == round(2 / 3, 3)
    fr = rep["languages"]["fr"]
    assert fr["published"] == 1 and fr["needs_review"] == 0
    assert fr["objects_covered"] == 1
    # 已发布但无音频：Q1 fr overview + Q2 en overview = 2（Q1 en overview 有音频）
    assert rep["missing_audio"] == 2


def test_quality_report_unknown_museum(session):
    from app.services.enrichment.content_report import build_quality_report

    assert build_quality_report(session, "nope", ["en"])["error"] == "unknown museum"
```

- [ ] **Step 2: 跑确认失败**

Run: `cd backend && poetry run pytest tests/integration/test_content_report.py -v`
Expected: FAIL（`ModuleNotFoundError: content_report`）

- [ ] **Step 3: 创建 `backend/app/services/enrichment/content_report.py`**

```python
"""内容质量报告（canary）：从 DB 已生成内容算覆盖率/needs_review%/缺音频。spec §8B。
接地分分布/源冲突需额外落库列（score/conflicts），属后续，本期不含。"""

from __future__ import annotations

from app.models.content import ObjectContentSection
from app.models.museum import Museum
from app.models.museum_object import MuseumObject


def build_quality_report(db, slug: str, languages: list[str], as_markdown: bool = False):
    m = db.query(Museum).filter_by(slug=slug).one_or_none()
    if not m:
        return {"slug": slug, "error": "unknown museum"}

    obj_ids = [o.id for o in db.query(MuseumObject).filter_by(museum_id=m.id).all()]
    total = len(obj_ids)
    rows = (
        db.query(ObjectContentSection)
        .filter(ObjectContentSection.object_id.in_(obj_ids))
        .all()
        if obj_ids
        else []
    )

    per_lang = {}
    for lang in languages:
        lrows = [r for r in rows if r.language == lang]
        pub = sum(1 for r in lrows if r.status == "published")
        nr = sum(1 for r in lrows if r.status == "needs_review")
        covered = len({r.object_id for r in lrows if r.status == "published"})
        denom = pub + nr
        per_lang[lang] = {
            "published": pub,
            "needs_review": nr,
            "pct_needs_review": round(nr / denom, 3) if denom else 0.0,
            "objects_covered": covered,
            "coverage": round(covered / total, 3) if total else 0.0,
        }

    missing_audio = sum(
        1 for r in rows if r.status == "published" and not r.audio_key
    )
    rep = {
        "slug": slug,
        "objects_total": total,
        "languages": per_lang,
        "missing_audio": missing_audio,
    }
    return _to_markdown(rep) if as_markdown else rep


def _to_markdown(rep: dict) -> str:
    lines = [
        f"# 内容质量报告: {rep['slug']}",
        "",
        f"- 对象数: {rep['objects_total']}",
        f"- 已发布但缺音频: {rep['missing_audio']}",
        "",
        "## 各语言",
    ]
    for lang, s in rep["languages"].items():
        lines.append(
            f"- {lang}: 覆盖 {s['coverage']*100:.0f}% "
            f"({s['objects_covered']}/{rep['objects_total']}), "
            f"published {s['published']}, needs_review {s['needs_review']} "
            f"({s['pct_needs_review']*100:.0f}%)"
        )
    return "\n".join(lines)
```

> `_to_markdown` 本任务即写好（Task 2 直接测它），保持模块自洽。

- [ ] **Step 4: 跑确认通过**

Run: `cd backend && poetry run pytest tests/integration/test_content_report.py -v`
Expected: PASS（2 passed）（单文件触发覆盖率门时加 `--no-cov`）

- [ ] **Step 5: 提交**

```bash
cd backend && poetry run black app/services/enrichment/content_report.py tests/integration/test_content_report.py && poetry run isort app/services/enrichment/content_report.py tests/integration/test_content_report.py
cd /Users/hongyang/Projects/GoMuseum && git add backend/app/services/enrichment/content_report.py backend/tests/integration/test_content_report.py
git commit -m "feat(enrichment): 内容质量报告 build_quality_report(覆盖率/needs_review%/缺音频)"
```

---

## Task 2: markdown 渲染

**Files:**
- Test: `backend/tests/integration/test_content_report.py`（追加）

`_to_markdown` 已在 Task 1 实现；本任务补测试锁行为。

- [ ] **Step 1: 写测试（追加）**

```python
def test_quality_report_markdown(session):
    from app.services.enrichment.content_report import build_quality_report

    md = build_quality_report(session, "orsay", ["en", "fr"], as_markdown=True)
    assert isinstance(md, str)
    assert "# 内容质量报告: orsay" in md
    assert "对象数: 3" in md
    assert "已发布但缺音频: 2" in md
    assert "- en:" in md and "- fr:" in md
    assert "needs_review" in md
```

- [ ] **Step 2: 跑确认通过（_to_markdown 已存在）**

Run: `cd backend && poetry run pytest tests/integration/test_content_report.py -k markdown -v`
Expected: PASS（1 passed）

- [ ] **Step 3: 提交**

```bash
cd backend && poetry run black tests/integration/test_content_report.py && poetry run isort tests/integration/test_content_report.py
cd /Users/hongyang/Projects/GoMuseum && git add backend/tests/integration/test_content_report.py
git commit -m "test(enrichment): 质量报告 markdown 渲染断言"
```

---

## Task 3: CLI `report` 子命令（只读）

**Files:**
- Modify: `backend/scripts/onboard.py`
- Test: `backend/tests/unit/services/enrichment/test_onboard_cli.py`（追加）

设计要点：
- `report` 只读，**无环境守卫**（不写库；读当前容器 DB）。参数：`--langs`（逗号分隔，可空→`resolve_languages(cfg.languages)`）。
- `cmd_report(slug, langs)`：解析语言 → `build_quality_report(db, slug, langs, as_markdown=True)` → print。

- [ ] **Step 1: 写失败测试（追加）**

```python
def test_parser_report_command():
    ns = build_parser().parse_args(["orsay", "report", "--langs", "en,fr"])
    assert ns.command == "report"
    assert ns.langs == "en,fr"


def test_parser_report_langs_optional():
    ns = build_parser().parse_args(["orsay", "report"])
    assert ns.command == "report" and ns.langs is None
```

- [ ] **Step 2: 跑确认失败**

Run: `cd backend && poetry run pytest tests/unit/services/enrichment/test_onboard_cli.py -k report -v`
Expected: FAIL（parser 无 report 子命令）

- [ ] **Step 3: 改 `onboard.py`**

`build_parser()` 里 `generate` 子命令后追加：

```python
    rp = sub.add_parser("report")
    rp.add_argument("--langs", default=None)
```

加 `cmd_report`（放在 `cmd_generate` 后）：

```python
def cmd_report(slug, langs) -> None:
    from app.services.enrichment.content_report import build_quality_report
    from app.services.enrichment.lang_config import resolve_languages

    override = (
        [s.strip() for s in langs.split(",")] if langs else _catalog().get(slug).languages
    )
    target_langs = resolve_languages(override)
    db = SessionLocal()
    try:
        print(build_quality_report(db, slug, target_langs, as_markdown=True))
    finally:
        db.close()
```

`main()` 分发加分支（在 `generate` 分支后）：

```python
    elif ns.command == "report":
        cmd_report(ns.slug, ns.langs)
```

- [ ] **Step 4: 跑确认通过**

Run: `cd backend && poetry run pytest tests/unit/services/enrichment/test_onboard_cli.py -v`
Expected: PASS（既有 + 新 2 全 passed）

- [ ] **Step 5: 提交**

```bash
cd backend && poetry run black scripts/onboard.py tests/unit/services/enrichment/test_onboard_cli.py && poetry run isort scripts/onboard.py tests/unit/services/enrichment/test_onboard_cli.py
cd /Users/hongyang/Projects/GoMuseum && git add backend/scripts/onboard.py backend/tests/unit/services/enrichment/test_onboard_cli.py
git commit -m "feat(enrichment): onboard report 子命令(只读质量报告)"
```

---

## 收尾

- [ ] **全套相关测试**：
```bash
cd backend && STORAGE_BACKEND=local poetry run pytest \
  tests/integration/test_content_report.py \
  tests/unit/services/enrichment/test_onboard_cli.py \
  -W "ignore::PendingDeprecationWarning" -v
```
Expected: 全 passed。

- [ ] **提 PR**：`feature/content-enrichment-phase2d3 → staging`（用 `/pr`）。无 DB 迁移。CI 绿后 squash 合并、删分支。
- [ ]（可选）合并后在 staging 容器跑 `docker exec gomuseum_staging_backend python scripts/onboard.py orsay report --langs en,fr`，看已生成内容（含 Q737062）的覆盖/needs_review 概况。

---

## Self-Review（计划对照 spec §8B）

- **§8B 覆盖率**：`coverage` = 有已发布段对象 / 总对象，per-language（Task 1）✓。
- **§8B needs_review %**：`pct_needs_review` = nr/(pub+nr)，per-language（Task 1）✓。
- **§8B 各语言覆盖**：`languages` 按语言分（Task 1）✓。
- **§8B 缺音频数**：`missing_audio` = 已发布但 audio_key 空（Task 1）✓。
- **§8B 金丝雀 CLI**：`onboard report` 只读 markdown（Task 3）✓。
- **§8B 接地分分布 / 源冲突数**：**本期不做**——需落库 score/conflicts 列（DB 迁移），已在范围说明标注（非遗漏）。
- **职责分离**：新 `content_report.py`，不动 fetch 期 `report.py`（数据覆盖报告）✓。
- **类型一致性**：`build_quality_report` 返回 dict（含 `languages[lang]` 子 dict 固定键）或 markdown str，`cmd_report` 消费 markdown（Task 1/3）✓。
- **DRY**：复用 `resolve_languages` / `MuseumConfig.languages` ✓。
