# 通用目录 Phase A：CatalogSource 抽象 + Wikidata 重构 + content_status Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 引入 `CatalogSource` 抽象 + `StubRecord` + `WikidataCatalog`（把现有 Wikidata 主干能力以新接口产 stub，行为不变）+ identity 去重骨架 + 对象 `content_status` 列与迁移，作通用全量目录的地基。

**Architecture:** 纯**加法**——新增抽象/连接器/去重骨架与现有两阶段 fetch **并存不互改**（现有 `WikidataSource.fetch()` 与 Fetcher 不动，Phase B 才重接线）；`MuseumObject` 加 `content_status`（stub/generating/ready/empty），迁移加列、回填函数另跑。注入式、离线可测。

**Tech Stack:** Python 3.11 · FastAPI · SQLAlchemy · Alembic · pytest。

**本期范围（spec `2026-06-22-universal-catalog-spine-design.md` Phase A）:** CatalogSource 抽象 + WikidataCatalog（行为不变，仍 247）+ identity 骨架（单源 no-op、强键去重）+ `content_status` 列/迁移/回填。**Phase B（重接线 Fetcher + 真去重 + 列目录/抓材料解耦）、C（Europeana）、D（懒生成）、富化提厚不在本期。**

**前置事实（已验证，勿重查）:**
- `MuseumObject`（`app/models/museum_object.py`）已有：`qid`(unique,nullable)、`inventory_number`、`(museum_id,inventory_number)` 唯一约束 `uq_object_museum_inventory`、`popularity`、`category`、`title_en`、`attributes`、`sources`。**无 `content_status`**。
- 现有 `WikidataSource`（`app/services/enrichment/sources/wikidata.py`）：模块级 `QUERY`（SPARQL）、`_PAGE=200`、`_v(row,key)`、`WikidataSource.fetch(cfg)` 分页跑 SPARQL→产 `ObjectContribution`。该类 Phase A **不动**。
- `category_for(p31_qid)` 在 `app/services/enrichment/category_config.py`。
- `MuseumConfig`（`app/services/enrichment/catalog.py`）：`slug`/`wikidata_qid`/`categories`/`category_filter`/`country_lang`/`fetch_limit` 等。
- `ObjectContentSection`（`app/models/content.py`）：`object_id`/`status`（published/needs_review）。
- Alembic 当前 head = `f2a2_add_suggested_questions`。迁移用 `from alembic import op` / `import sqlalchemy as sa`。
- 集成测试 in-memory SQLite fixture 范式见 `tests/integration/test_content_persist.py`（`upsert_museum`/`upsert_object`）。

---

## 文件结构

| 文件 | 职责 | 动作 |
|---|---|---|
| `backend/app/services/enrichment/catalog_source.py` | `StubRecord` 数据类 + `CatalogSource` ABC | **新建** |
| `backend/app/services/enrichment/sources/wikidata_catalog.py` | `WikidataCatalog`（产 StubRecord，复用 `wikidata.QUERY`/`_v`） | **新建** |
| `backend/app/services/enrichment/identity.py` | `merge_stubs`（强键去重骨架） | **新建** |
| `backend/app/models/museum_object.py` | 加 `content_status` 列 | 修改 |
| `backend/alembic/versions/a3b3_add_content_status.py` | 加列迁移 | **新建** |
| `backend/app/services/enrichment/backfill.py` | `backfill_content_status(db)`（247 回填） | **新建** |
| `backend/tests/unit/services/enrichment/test_catalog_source.py` | StubRecord/ABC 单测 | **新建** |
| `backend/tests/unit/services/enrichment/test_wikidata_catalog.py` | WikidataCatalog 单测 | **新建** |
| `backend/tests/unit/services/enrichment/test_identity.py` | merge_stubs 单测 | **新建** |
| `backend/tests/integration/test_content_status.py` | content_status 列默认 + 回填集成 | **新建** |

**关键接口（先定死）:**
```python
@dataclass
class StubRecord:
    inventory_number: str | None
    qid: str | None
    title: str | None
    artist: str | None
    year: str | None
    category: str | None
    image_url: str | None
    popularity: int | None
    owning_museum: str
    source: str
    raw: dict = field(default_factory=dict)

class CatalogSource(ABC):
    name: str
    def list(self, museum_cfg) -> Iterable[StubRecord]: ...

# identity.py
def merge_stubs(records: list[StubRecord]) -> list[StubRecord]: ...   # 强键去重,首条胜

# backfill.py
def backfill_content_status(db) -> dict: ...   # {"ready": n, "stub": m}
```

---

## Task 1: `StubRecord` + `CatalogSource` ABC

**Files:**
- Create: `backend/app/services/enrichment/catalog_source.py`
- Test: `backend/tests/unit/services/enrichment/test_catalog_source.py`

- [ ] **Step 1: 写失败测试**
```python
# backend/tests/unit/services/enrichment/test_catalog_source.py
from app.services.enrichment.catalog_source import CatalogSource, StubRecord


def test_stubrecord_fields_and_defaults():
    r = StubRecord(
        inventory_number="RF 2772", qid="Q775407", title="The Balcony",
        artist="Manet", year="1868", category="painting",
        image_url="http://x/a.jpg", popularity=12, owning_museum="orsay",
        source="wikidata",
    )
    assert r.qid == "Q775407" and r.owning_museum == "orsay"
    assert r.raw == {}  # 默认空 dict


def test_catalogsource_is_abstract():
    import pytest

    with pytest.raises(TypeError):
        CatalogSource()  # 抽象类不可实例化
```

- [ ] **Step 2: 跑确认失败** — `cd backend && poetry run pytest tests/unit/services/enrichment/test_catalog_source.py -v`（Expected FAIL: ModuleNotFoundError）

- [ ] **Step 3: 创建 `catalog_source.py`**
```python
"""目录层抽象：CatalogSource 列对象产 StubRecord（元数据+身份），供身份去重 + 落 stub。
spec 2026-06-22-universal-catalog-spine-design §4。"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Iterable


@dataclass
class StubRecord:
    inventory_number: str | None
    qid: str | None
    title: str | None
    artist: str | None
    year: str | None
    category: str | None
    image_url: str | None
    popularity: int | None
    owning_museum: str
    source: str
    raw: dict = field(default_factory=dict)


class CatalogSource(ABC):
    name: str = "catalog"

    @abstractmethod
    def list(self, museum_cfg) -> Iterable[StubRecord]:
        """列该馆全部对象，产 StubRecord。"""
        raise NotImplementedError
```

- [ ] **Step 4: 跑确认通过** — 同 Step 2 命令（Expected PASS, 2 passed；单文件覆盖率门加 `--no-cov`）

- [ ] **Step 5: 提交**
```bash
cd backend && poetry run black app/services/enrichment/catalog_source.py tests/unit/services/enrichment/test_catalog_source.py && poetry run isort app/services/enrichment/catalog_source.py tests/unit/services/enrichment/test_catalog_source.py
cd /Users/hongyang/Projects/GoMuseum && git add backend/app/services/enrichment/catalog_source.py backend/tests/unit/services/enrichment/test_catalog_source.py
git commit -m "feat(catalog): CatalogSource 抽象 + StubRecord"
```

---

## Task 2: `WikidataCatalog`（产 StubRecord，复用现有 SPARQL）

**Files:**
- Create: `backend/app/services/enrichment/sources/wikidata_catalog.py`
- Test: `backend/tests/unit/services/enrichment/test_wikidata_catalog.py`

设计要点：复用 `wikidata.QUERY` / `wikidata._v` / `wikidata._PAGE`；`run_query` 注入式（默认真实 SPARQL，测试传假）。行为对齐 `WikidataSource.fetch` 的对象集（同 qid 集），只是产 StubRecord。`owning_museum = cfg.slug`，`title = label_en`，`artist = creator_en`，`category = category_for(p31)`，`popularity = links`。

- [ ] **Step 1: 写失败测试**
```python
# backend/tests/unit/services/enrichment/test_wikidata_catalog.py
from app.services.enrichment.sources.wikidata_catalog import WikidataCatalog


class _Cfg:
    slug = "orsay"
    wikidata_qid = "Q23402"
    categories = ["Q3305213"]
    category_filter = "Q3305213"
    country_lang = "fr"
    fetch_limit = 200


def _row(qid, title, links, inv=None, p31="Q3305213"):
    cell = lambda v: {"value": v}
    r = {
        "item": cell(f"http://www.wikidata.org/entity/{qid}"),
        "label_en": cell(title),
        "creator_en": cell("Manet"),
        "year": cell("1868"),
        "links": cell(str(links)),
        "p31": cell(f"http://www.wikidata.org/entity/{p31}"),
    }
    if inv:
        r["inventory"] = cell(inv)
    return r


def test_wikidata_catalog_lists_stubrecords():
    rows = [_row("Q775407", "The Balcony", 12, inv="RF 2772")]
    cat = WikidataCatalog(run_query=lambda sparql: rows)
    out = list(cat.list(_Cfg()))
    assert len(out) == 1
    s = out[0]
    assert s.qid == "Q775407" and s.title == "The Balcony"
    assert s.artist == "Manet" and s.year == "1868"
    assert s.inventory_number == "RF 2772"
    assert s.popularity == 12 and s.category == "painting"
    assert s.owning_museum == "orsay" and s.source == "wikidata"


def test_wikidata_catalog_dedups_and_stops_on_empty_page():
    # 同 qid 跨页重复只产一次；空页停止翻页
    page1 = [_row("Q1", "A", 5), _row("Q1", "A", 5)]
    calls = {"n": 0}

    def fake(sparql):
        calls["n"] += 1
        return page1 if calls["n"] == 1 else []

    cat = WikidataCatalog(run_query=fake)
    out = list(cat.list(_Cfg()))
    assert [s.qid for s in out] == ["Q1"]
```

- [ ] **Step 2: 跑确认失败** — `cd backend && poetry run pytest tests/unit/services/enrichment/test_wikidata_catalog.py -v`（Expected FAIL: ModuleNotFoundError）

- [ ] **Step 3: 创建 `sources/wikidata_catalog.py`**
```python
"""WikidataCatalog：用现有 Wikidata SPARQL 主干列对象、产 StubRecord。
复用 wikidata.QUERY/_v/_PAGE；run_query 注入式（默认真实 SPARQL）。spec §4。
注：现有 WikidataSource.fetch 保留不动；Phase B 才让 Fetcher 改用本类。"""

from __future__ import annotations

import time
from typing import Iterable

import requests

from app.services.enrichment.catalog_source import CatalogSource, StubRecord
from app.services.enrichment.category_config import category_for
from app.services.enrichment.sources import wikidata as _wd


def _default_run_query(sparql: str) -> list[dict]:
    r = requests.get(
        _wd.SPARQL_ENDPOINT,
        params={"query": sparql, "format": "json"},
        headers={
            "User-Agent": _wd.USER_AGENT,
            "Accept": "application/sparql-results+json",
        },
        timeout=60,
    )
    r.raise_for_status()
    return r.json()["results"]["bindings"]


class WikidataCatalog(CatalogSource):
    name = "wikidata"

    def __init__(self, run_query=None):
        self._run_query = run_query or _default_run_query

    def list(self, cfg) -> Iterable[StubRecord]:
        cats = cfg.categories or [cfg.category_filter]
        cat_values = " ".join(f"wd:{q}" for q in cats)
        seen: set[str] = set()
        fetched = 0
        offset = 0
        while fetched < cfg.fetch_limit:
            page = min(_wd._PAGE, cfg.fetch_limit - fetched)
            rows = self._run_query(
                _wd.QUERY.format(
                    museum=cfg.wikidata_qid,
                    cat_values=cat_values,
                    country_lang=(cfg.country_lang or "fr"),
                    limit=page,
                    offset=offset,
                )
            )
            if not rows:
                break
            for row in rows:
                qid = row["item"]["value"].rsplit("/", 1)[-1]
                if qid in seen:
                    continue
                seen.add(qid)
                p31 = (row.get("p31", {}) or {}).get("value", "").rsplit("/", 1)[-1]
                yield StubRecord(
                    inventory_number=_wd._v(row, "inventory"),
                    qid=qid,
                    title=_wd._v(row, "label_en"),
                    artist=_wd._v(row, "creator_en"),
                    year=_wd._v(row, "year"),
                    category=category_for(p31),
                    image_url=_wd._v(row, "image"),
                    popularity=int(_wd._v(row, "links") or 0),
                    owning_museum=cfg.slug,
                    source="wikidata",
                    raw=row,
                )
            fetched += len(rows)
            offset += len(rows)
            if self._run_query is _default_run_query:
                time.sleep(1)  # 真实抓取礼貌限速；测试注入时不睡
```

- [ ] **Step 4: 跑确认通过** — 同 Step 2（Expected PASS, 2 passed）

- [ ] **Step 5: 提交**
```bash
cd backend && poetry run black app/services/enrichment/sources/wikidata_catalog.py tests/unit/services/enrichment/test_wikidata_catalog.py && poetry run isort app/services/enrichment/sources/wikidata_catalog.py tests/unit/services/enrichment/test_wikidata_catalog.py
cd /Users/hongyang/Projects/GoMuseum && git add backend/app/services/enrichment/sources/wikidata_catalog.py backend/tests/unit/services/enrichment/test_wikidata_catalog.py
git commit -m "feat(catalog): WikidataCatalog 产 StubRecord(复用现有SPARQL,行为对齐)"
```

---

## Task 3: `identity.merge_stubs`（强键去重骨架）

**Files:**
- Create: `backend/app/services/enrichment/identity.py`
- Test: `backend/tests/unit/services/enrichment/test_identity.py`

设计要点：Phase A 只做**强键去重 + 首条胜**（单源天然无重复 → pass-through；为 Phase B 多源打底）。键：`(owning_museum, 归一化馆藏号)` > `qid` > 每条独立。归一化：去空白、大写、去标点。**字段级合并（§5b）留 Phase B。**

- [ ] **Step 1: 写失败测试**
```python
# backend/tests/unit/services/enrichment/test_identity.py
from app.services.enrichment.catalog_source import StubRecord
from app.services.enrichment.identity import merge_stubs


def _s(qid=None, inv=None, museum="orsay", source="wikidata", title="t"):
    return StubRecord(
        inventory_number=inv, qid=qid, title=title, artist=None, year=None,
        category="painting", image_url=None, popularity=None,
        owning_museum=museum, source=source,
    )


def test_merge_distinct_passthrough():
    recs = [_s(qid="Q1"), _s(qid="Q2")]
    assert [r.qid for r in merge_stubs(recs)] == ["Q1", "Q2"]


def test_merge_dedup_by_inventory_normalized():
    # 同馆同馆藏号(写法不同) → 一条,首条胜
    recs = [_s(inv="RF 2772", title="first"), _s(inv="rf-2772", title="second")]
    out = merge_stubs(recs)
    assert len(out) == 1 and out[0].title == "first"


def test_merge_dedup_by_qid():
    recs = [_s(qid="Q5", title="a"), _s(qid="Q5", title="b")]
    out = merge_stubs(recs)
    assert len(out) == 1 and out[0].title == "a"


def test_merge_inventory_namespaced_by_museum():
    # 同馆藏号但不同馆 → 不并(跨馆不唯一)
    recs = [_s(inv="RF 1", museum="orsay"), _s(inv="RF 1", museum="louvre")]
    assert len(merge_stubs(recs)) == 2
```

- [ ] **Step 2: 跑确认失败** — `cd backend && poetry run pytest tests/unit/services/enrichment/test_identity.py -v`（Expected FAIL）

- [ ] **Step 3: 创建 `identity.py`**
```python
"""身份去重：多源 StubRecord 按强键归并成一对象。
Phase A 只做强键去重+首条胜（单源 pass-through）；字段级合并(§5b)+模糊匹配 Phase B。
spec §5。"""

from __future__ import annotations

import re

from app.services.enrichment.catalog_source import StubRecord


def _norm_inv(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.lower())


def _key(r: StubRecord):
    if r.owning_museum and r.inventory_number:
        return ("inv", r.owning_museum, _norm_inv(r.inventory_number))
    if r.qid:
        return ("qid", r.qid)
    return ("uid", id(r))


def merge_stubs(records: list[StubRecord]) -> list[StubRecord]:
    """强键去重（(馆,馆藏号)>qid），首条胜。无重复时原样返回。"""
    seen: dict = {}
    out: list[StubRecord] = []
    for r in records:
        k = _key(r)
        if k in seen:
            continue
        seen[k] = r
        out.append(r)
    return out
```

- [ ] **Step 4: 跑确认通过** — 同 Step 2（Expected PASS, 4 passed）

- [ ] **Step 5: 提交**
```bash
cd backend && poetry run black app/services/enrichment/identity.py tests/unit/services/enrichment/test_identity.py && poetry run isort app/services/enrichment/identity.py tests/unit/services/enrichment/test_identity.py
cd /Users/hongyang/Projects/GoMuseum && git add backend/app/services/enrichment/identity.py backend/tests/unit/services/enrichment/test_identity.py
git commit -m "feat(catalog): identity.merge_stubs 强键去重骨架"
```

---

## Task 4: `content_status` 列 + Alembic 迁移

**Files:**
- Modify: `backend/app/models/museum_object.py`
- Create: `backend/alembic/versions/a3b3_add_content_status.py`
- Test: `backend/tests/integration/test_content_status.py`

- [ ] **Step 1: 写失败测试**
```python
# backend/tests/integration/test_content_status.py
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.models.museum import Museum
from app.models.museum_object import MuseumObject, ObjectImage
from app.services.object_importer import upsert_museum, upsert_object


@pytest.fixture()
def session():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(
        bind=engine, tables=[Museum.__table__, MuseumObject.__table__, ObjectImage.__table__]
    )
    s = sessionmaker(bind=engine)()
    m = upsert_museum(s, {"slug": "orsay", "name_en": "Orsay"})
    upsert_object(s, m.id, {"qid": "Q1", "title_en": "A", "category": "painting"})
    s.commit()
    yield s


def test_content_status_defaults_to_stub(session):
    o = session.query(MuseumObject).filter_by(qid="Q1").one()
    assert o.content_status == "stub"
```

- [ ] **Step 2: 跑确认失败** — `cd backend && poetry run pytest tests/integration/test_content_status.py -v`（Expected FAIL: AttributeError content_status）

- [ ] **Step 3a: 改 `museum_object.py`** — 在 `popularity` 列后加：
```python
    content_status = Column(
        String(16), nullable=False, default="stub", server_default="stub"
    )  # stub | generating | ready | empty
```
（`Column`/`String` 已 import。）

- [ ] **Step 3b: 创建 `alembic/versions/a3b3_add_content_status.py`**
```python
"""add museum_objects.content_status

Revision ID: a3b3_add_content_status
Revises: f2a2_add_suggested_questions
Create Date: 2026-06-22
"""

import sqlalchemy as sa

from alembic import op

revision = "a3b3_add_content_status"
down_revision = "f2a2_add_suggested_questions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "museum_objects",
        sa.Column(
            "content_status",
            sa.String(length=16),
            nullable=False,
            server_default="stub",
        ),
    )


def downgrade() -> None:
    op.drop_column("museum_objects", "content_status")
```

- [ ] **Step 4: 跑确认通过 + 迁移链** —
  `cd backend && poetry run pytest tests/integration/test_content_status.py -v`（PASS）；
  `poetry run alembic history 2>&1 | head -3`（顶部应见 `f2a2_add_suggested_questions -> a3b3_add_content_status (head)`；alembic 跑不起来时改 `/Users/hongyang/.pyenv/versions/3.11.7/bin/python3.11 -m alembic history`）。

- [ ] **Step 5: 提交**
```bash
cd backend && poetry run black app/models/museum_object.py alembic/versions/a3b3_add_content_status.py tests/integration/test_content_status.py && poetry run isort app/models/museum_object.py alembic/versions/a3b3_add_content_status.py tests/integration/test_content_status.py
cd /Users/hongyang/Projects/GoMuseum && git add backend/app/models/museum_object.py backend/alembic/versions/a3b3_add_content_status.py backend/tests/integration/test_content_status.py
git commit -m "feat(catalog): MuseumObject.content_status 列 + 迁移"
```

---

## Task 5: `backfill_content_status`（既有 247 回填）

**Files:**
- Create: `backend/app/services/enrichment/backfill.py`
- Test: `backend/tests/integration/test_content_status.py`（追加）

设计要点：有 ≥1 已发布 section 的对象 → `ready`，否则保持 `stub`。返回计数。部署后在 prod 容器手动跑一次（见收尾）。

- [ ] **Step 1: 写失败测试（追加，扩 fixture 建 ObjectContentSection 表）**

把 Task 4 的 fixture `create_all` 的 tables 列表加 `ObjectContentSection.__table__`，并在文件顶部加 `from app.models.content import ObjectContentSection`。追加：
```python
def test_backfill_sets_ready_for_objects_with_published_sections(session):
    from app.services.enrichment.backfill import backfill_content_status

    o = session.query(MuseumObject).filter_by(qid="Q1").one()
    session.add(
        ObjectContentSection(
            object_id=o.id, language="en", section_code="overview",
            body="x", status="published",
        )
    )
    # 再建一个无 section 的对象
    upsert_object(session, o.museum_id, {"qid": "Q2", "title_en": "B", "category": "painting"})
    session.commit()

    counts = backfill_content_status(session)
    assert counts == {"ready": 1, "stub": 1}
    assert session.query(MuseumObject).filter_by(qid="Q1").one().content_status == "ready"
    assert session.query(MuseumObject).filter_by(qid="Q2").one().content_status == "stub"


def test_backfill_idempotent(session):
    from app.services.enrichment.backfill import backfill_content_status

    backfill_content_status(session)
    assert backfill_content_status(session) == {"ready": 0, "stub": 2}
```
> 第二个测试：第一次回填后状态已定，第二次应"无变更"——`backfill_content_status` 只对**与目标状态不同**的对象更新并计数。Q1 应已 ready、Q2 stub，故第二次 ready=0、stub=2（stub 计已是 stub 的）。**实现据此**：counts 统计"目标态"分布（不是"本次改了几个"），见下。

- [ ] **Step 2: 跑确认失败** — `cd backend && poetry run pytest tests/integration/test_content_status.py -k backfill -v`（Expected FAIL: ModuleNotFoundError）

- [ ] **Step 3: 创建 `backfill.py`**
```python
"""既有对象 content_status 回填：有已发布 section → ready，否则 stub。
部署后一次性跑（见 Phase A 收尾）。spec §8。"""

from __future__ import annotations

from app.models.content import ObjectContentSection
from app.models.museum_object import MuseumObject


def backfill_content_status(db) -> dict:
    """按是否有已发布 section 设 content_status。返回 {"ready": n, "stub": m}（目标态分布）。"""
    ready_ids = {
        oid
        for (oid,) in db.query(ObjectContentSection.object_id)
        .filter_by(status="published")
        .distinct()
        .all()
    }
    counts = {"ready": 0, "stub": 0}
    for o in db.query(MuseumObject).all():
        target = "ready" if o.id in ready_ids else "stub"
        if o.content_status != target:
            o.content_status = target
        counts[target] += 1
    db.commit()
    return counts
```

- [ ] **Step 4: 跑确认通过** — `cd backend && poetry run pytest tests/integration/test_content_status.py -v`（全 PASS）

- [ ] **Step 5: 提交**
```bash
cd backend && poetry run black app/services/enrichment/backfill.py tests/integration/test_content_status.py && poetry run isort app/services/enrichment/backfill.py tests/integration/test_content_status.py
cd /Users/hongyang/Projects/GoMuseum && git add backend/app/services/enrichment/backfill.py backend/tests/integration/test_content_status.py
git commit -m "feat(catalog): backfill_content_status 既有对象回填(有发布段→ready)"
```

---

## 收尾

- [ ] **全套相关测试**：
```bash
cd backend && STORAGE_BACKEND=local poetry run pytest \
  tests/unit/services/enrichment/test_catalog_source.py \
  tests/unit/services/enrichment/test_wikidata_catalog.py \
  tests/unit/services/enrichment/test_identity.py \
  tests/integration/test_content_status.py \
  -W "ignore::PendingDeprecationWarning" -v
```
Expected: 全 passed。

- [ ] **提 PR**：`feature/catalog-phase-a → staging`（用 `/pr`）。**有 DB 迁移 `a3b3`**——PR 注明部署后 `alembic upgrade head` 加列、再跑一次回填。CI 绿后 squash 合并、删分支。
- [ ]（部署后·操作）staging/prod 容器：迁移自动 apply 后，跑回填：
  `docker exec <容器> python -c "from app.core.database import SessionLocal; from app.services.enrichment.backfill import backfill_content_status; print(backfill_content_status(SessionLocal()))"`
  期望 prod 返回 `{"ready": <已生成数>, "stub": <其余>}`。

---

## Self-Review（计划对照 spec Phase A）

- **CatalogSource 抽象 + StubRecord**：Task 1 ✓（spec §4 接口）。
- **WikidataCatalog 重构、行为不变（仍 247）**：Task 2 产 StubRecord、复用现有 SPARQL、对象集对齐；现有 `WikidataSource.fetch` 不动（Phase B 才重接线）✓。
- **identity 骨架（单源 no-op、强键去重）**：Task 3，(馆,馆藏号)>qid 去重、首条胜、跨馆命名空间；字段级合并/模糊留 Phase B ✓。
- **content_status 列 + 迁移**：Task 4（默认 stub、迁移挂 f2a2 head）✓。
- **既有 247 回填**：Task 5（有发布段→ready）+ 收尾操作 ✓。
- **本期不做（显式）**：Fetcher 重接线 / 列目录-抓材料解耦 / 真去重字段合并 / Europeana / 懒生成 / 富化提厚 = Phase B-D，非遗漏。
- **类型一致性**：`StubRecord` 字段跨 Task 1/2/3 一致；`merge_stubs(list[StubRecord])->list[StubRecord]`、`backfill_content_status(db)->{"ready","stub"}` 与测试一致 ✓。
- **纯加法、低风险**：新文件 + 1 列,现有管线零改动 ✓。
