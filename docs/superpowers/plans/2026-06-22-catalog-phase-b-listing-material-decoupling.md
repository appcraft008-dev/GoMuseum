# Catalog Phase B — 列目录/抓材料解耦 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把「列目录」（廉价批量产 stub 元数据）与「抓富化材料」（逐件、生成时按需）解耦，让目录可扩容到全量而不预付材料成本。

**Architecture:** 新增 `material.fetch_object_material`（逐件路由富化源→merge）与 `catalog_loader.load_stubs`（StubRecord→stub 对象，只元数据+路由信息）。`generate_object` 检测到 `content_status="stub"` 时先逐件抓材料再生成，生成后流转 `content_status`→ready/empty。`onboard catalog` 子命令跑「列→去重→落 stub」。核心生成/闸/翻译管线不变。

**Tech Stack:** FastAPI + SQLAlchemy + pytest（sqlite 内存库做集成）。注入式组件，离线可测。

**Scope（与 spec §9 的边界）：** 本期只做单源（Wikidata）下的**解耦 + 逐件材料 + content_status 流转**。`identity.merge_stubs` 已是强键（qid/馆藏号）去重，单源即 no-op，够用；**真模糊去重/字段级合并/拥有馆解析/Europeana 连接器留 Phase C**（需第二源才有跨源可并）。**无 Alembic 迁移**：`content_status` 列 Phase A 已加；qid 全局唯一对单源足够（Wikidata QID 本就全局唯一），partial-unique 留 Phase C 配合无 qid 的 Europeana 件。

---

## File Structure

- **Modify** `backend/app/services/enrichment/catalog_source.py` — `StubRecord` 加 `external_ids` + `wiki_titles`（路由信息，供生成时抓材料）。
- **Modify** `backend/app/services/enrichment/sources/wikidata_catalog.py` — `WikidataCatalog.list` 填充 `external_ids`(P347)+`wiki_titles`（en + country_lang sitelink）。
- **Modify** `backend/app/services/object_importer.py` — `_find_object` 公开为 `find_object`（catalog_loader 复用查找）。
- **Create** `backend/app/services/enrichment/material.py` — `fetch_object_material(qid, external_ids, wiki_titles, registry) -> dict`：逐件路由富化源→enrich→merge→返回材料 attributes。
- **Create** `backend/app/services/enrichment/catalog_loader.py` — `load_stubs(db, museum, stubs) -> dict`：StubRecord 列灌成 stub 对象（保留已有材料、不下调 ready）。
- **Modify** `backend/app/services/enrichment/pipeline.py` — `generate_object`/`generate_museum` 加 `registry` 注入；stub 件生成前抓材料；生成后流转 `content_status`。
- **Modify** `backend/scripts/onboard.py` — 加 `catalog` 子命令；`cmd_generate` 构造 registry 并下传。

测试：
- **Modify** `backend/tests/unit/services/enrichment/test_catalog_source.py`
- **Modify** `backend/tests/unit/services/enrichment/test_wikidata_catalog.py`
- **Create** `backend/tests/unit/services/object_importer/test_find_object.py`
- **Create** `backend/tests/unit/services/enrichment/test_material.py`
- **Create** `backend/tests/integration/test_catalog_loader.py`
- **Modify** `backend/tests/integration/test_generate_pipeline.py`
- **Create** `backend/tests/unit/services/enrichment/test_onboard_parser.py`

---

### Task 1: StubRecord 加路由字段

**Files:**
- Modify: `backend/app/services/enrichment/catalog_source.py`
- Test: `backend/tests/unit/services/enrichment/test_catalog_source.py`

- [ ] **Step 1: 写失败测试**

在 `test_catalog_source.py` 末尾追加：

```python
def test_stubrecord_carries_routing_info():
    from app.services.enrichment.catalog_source import StubRecord

    s = StubRecord(
        inventory_number="RF 2772",
        qid="Q1",
        title="T",
        artist="A",
        year="1868",
        category="painting",
        image_url=None,
        popularity=3,
        owning_museum="orsay",
        source="wikidata",
        external_ids={"P347": "000PE026604"},
        wiki_titles={"en": "The_Balcony"},
    )
    assert s.external_ids == {"P347": "000PE026604"}
    assert s.wiki_titles == {"en": "The_Balcony"}


def test_stubrecord_routing_defaults_empty():
    from app.services.enrichment.catalog_source import StubRecord

    s = StubRecord(
        inventory_number=None,
        qid="Q1",
        title="T",
        artist=None,
        year=None,
        category=None,
        image_url=None,
        popularity=None,
        owning_museum="orsay",
        source="wikidata",
    )
    assert s.external_ids == {} and s.wiki_titles == {}
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && python -m pytest tests/unit/services/enrichment/test_catalog_source.py -q`
Expected: FAIL（`StubRecord.__init__` 不接受 `external_ids`）

- [ ] **Step 3: 加字段**

在 `catalog_source.py` 的 `StubRecord` 中，`raw` 字段之后加两个默认空 dict 字段：

```python
    raw: dict = field(default_factory=dict)
    external_ids: dict = field(default_factory=dict)  # 跨源 ID（如 P347），供生成时路由富化源
    wiki_titles: dict = field(default_factory=dict)   # 各语言维基条目标题，供 Wikipedia 富化
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd backend && python -m pytest tests/unit/services/enrichment/test_catalog_source.py -q`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
cd backend && git add app/services/enrichment/catalog_source.py tests/unit/services/enrichment/test_catalog_source.py
git commit -m "feat(catalog): StubRecord 加 external_ids/wiki_titles 路由字段"
```

---

### Task 2: WikidataCatalog 填充路由信息

**Files:**
- Modify: `backend/app/services/enrichment/sources/wikidata_catalog.py`
- Test: `backend/tests/unit/services/enrichment/test_wikidata_catalog.py`

- [ ] **Step 1: 写失败测试**

在 `test_wikidata_catalog.py` 末尾追加（注意 `_row` 辅助函数已存在）：

```python
def test_wikidata_catalog_extracts_routing():
    cell = lambda v: {"value": v}
    row = _row("Q775407", "The Balcony", 12, inv="RF 2772")
    row["joconde"] = cell("000PE026604")
    row["sitelink_en"] = cell("https://en.wikipedia.org/wiki/The_Balcony")
    row["sitelink_cl"] = cell("https://fr.wikipedia.org/wiki/Le_Balcon")
    cat = WikidataCatalog(run_query=lambda sparql: [row])
    s = list(cat.list(_Cfg()))[0]
    assert s.external_ids == {"P347": "000PE026604"}
    assert s.wiki_titles == {"en": "The_Balcony", "fr": "Le_Balcon"}


def test_wikidata_catalog_routing_empty_when_absent():
    cat = WikidataCatalog(run_query=lambda sparql: [_row("Q1", "A", 5)])
    s = list(cat.list(_Cfg()))[0]
    assert s.external_ids == {} and s.wiki_titles == {}
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && python -m pytest tests/unit/services/enrichment/test_wikidata_catalog.py -q`
Expected: FAIL（`external_ids`/`wiki_titles` 为空，未填充）

- [ ] **Step 3: 在 list 里抽取路由信息**

在 `wikidata_catalog.py` 的 `list` 方法里，`for row in rows:` 循环内、`yield StubRecord(...)` 之前，插入路由抽取（镜像 `wikidata.WikidataSource.fetch` 的逻辑）：

```python
                p31 = (row.get("p31", {}) or {}).get("value", "").rsplit("/", 1)[-1]
                ext = {}
                jo = _wd._v(row, "joconde")
                if jo:
                    ext["P347"] = jo
                titles = {}
                se = _wd._v(row, "sitelink_en")
                if se:
                    titles["en"] = se.rsplit("/", 1)[-1]
                scl = _wd._v(row, "sitelink_cl")
                if scl:
                    titles[cfg.country_lang or "fr"] = scl.rsplit("/", 1)[-1]
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
                    external_ids=ext,
                    wiki_titles=titles,
                )
```

（替换原有的 `p31 = ...` 与 `yield StubRecord(...)` 两段；`_wd._v` 已是模块内可用别名。）

- [ ] **Step 4: 运行测试确认通过**

Run: `cd backend && python -m pytest tests/unit/services/enrichment/test_wikidata_catalog.py -q`
Expected: PASS（含原有 2 个用例）

- [ ] **Step 5: 提交**

```bash
cd backend && git add app/services/enrichment/sources/wikidata_catalog.py tests/unit/services/enrichment/test_wikidata_catalog.py
git commit -m "feat(catalog): WikidataCatalog 抽取 P347/sitelink 路由信息进 StubRecord"
```

---

### Task 3: 公开 object_importer.find_object

**Files:**
- Modify: `backend/app/services/object_importer.py`
- Test: `backend/tests/unit/services/object_importer/test_find_object.py`

- [ ] **Step 1: 先确认私名无外部引用**

Run: `cd backend && grep -rn "_find_object" app/ tests/`
Expected: 仅 `object_importer.py` 内部出现（定义 + `upsert_object` 调用）。若有其它引用，一并改名。

- [ ] **Step 2: 写失败测试**

Create `backend/tests/unit/services/object_importer/__init__.py`（空文件）与 `test_find_object.py`：

```python
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.models.museum import Museum
from app.models.museum_object import MuseumObject, ObjectImage
from app.services.object_importer import find_object, upsert_museum, upsert_object


def _session():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(
        bind=engine,
        tables=[Museum.__table__, MuseumObject.__table__, ObjectImage.__table__],
    )
    return sessionmaker(bind=engine)()


def test_find_object_by_qid_and_inventory():
    s = _session()
    m = upsert_museum(s, {"slug": "orsay", "name_en": "Orsay"})
    upsert_object(
        s, m.id, {"qid": "Q1", "inventory_number": "RF 1", "title_en": "A"}
    )
    s.commit()
    assert find_object(s, m.id, {"qid": "Q1"}).title_en == "A"
    assert find_object(s, m.id, {"inventory_number": "RF 1"}).qid == "Q1"
    assert find_object(s, m.id, {"qid": "Q404"}) is None
```

- [ ] **Step 3: 运行测试确认失败**

Run: `cd backend && python -m pytest tests/unit/services/object_importer/test_find_object.py -q`
Expected: FAIL（`cannot import name 'find_object'`）

- [ ] **Step 4: 改名 _find_object → find_object**

在 `object_importer.py`：将函数定义 `def _find_object(` 改为 `def find_object(`，并把 `upsert_object` 内的调用 `_find_object(db, museum_id, art)` 改为 `find_object(db, museum_id, art)`。

- [ ] **Step 5: 运行测试确认通过**

Run: `cd backend && python -m pytest tests/unit/services/object_importer/test_find_object.py tests/unit/services/enrichment/test_loader_sampling.py -q`
Expected: PASS

- [ ] **Step 6: 提交**

```bash
cd backend && git add app/services/object_importer.py tests/unit/services/object_importer/
git commit -m "refactor(importer): 公开 find_object 供 catalog_loader 复用"
```

---

### Task 4: fetch_object_material 逐件材料富化

**Files:**
- Create: `backend/app/services/enrichment/material.py`
- Test: `backend/tests/unit/services/enrichment/test_material.py`

- [ ] **Step 1: 写失败测试**

Create `test_material.py`：

```python
from app.services.enrichment.material import fetch_object_material
from app.services.enrichment.registry import SourceRegistry
from app.services.enrichment.sources.base import ObjectContribution, Source


class _FakeWiki(Source):
    name = "wikipedia"

    def fetch(self, cfg):
        return []

    def enrich(self, qid, external_ids, context):
        title = (context.get("wiki_titles") or {}).get("en")
        if not title:
            return None
        return ObjectContribution(
            source="wikipedia", qid=qid, fields={"extract_en": f"lead of {title}"}, raw={}
        )


def test_fetch_object_material_returns_enrichment_attributes():
    reg = SourceRegistry([_FakeWiki()])
    out = fetch_object_material("Q1", {}, {"en": "The_Balcony"}, reg)
    assert out["extract_en"] == "lead of The_Balcony"
    # 身份/留痕键不进材料
    assert "qid" not in out and "sources" not in out and "external_ids" not in out


def test_fetch_object_material_empty_when_no_contribs():
    reg = SourceRegistry([_FakeWiki()])
    assert fetch_object_material("Q1", {}, {}, reg) == {}
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && python -m pytest tests/unit/services/enrichment/test_material.py -q`
Expected: FAIL（`No module named 'app.services.enrichment.material'`）

- [ ] **Step 3: 实现 material.py**

```python
"""逐件材料富化：给一件（qid + 外部ID + wiki 标题）按需路由富化源、抓材料、merge。
= 把 Fetcher 一锅式抓取的「逐件富化」半边抽出，供生成时按需调用（spec §6 列目录/抓材料解耦）。"""

from __future__ import annotations

from app.services.enrichment.fetcher import _CORE
from app.services.enrichment.merge import merge_contributions


def fetch_object_material(
    qid: str, external_ids: dict, wiki_titles: dict, registry
) -> dict:
    """路由富化源→enrich→merge，返回材料 attributes（剥身份/留痕键）。无贡献→{}。"""
    context = {"wiki_titles": wiki_titles or {}}
    contribs = []
    for src in registry.route(external_ids or {}):
        c = src.enrich(qid, external_ids or {}, context)
        if c is not None:
            contribs.append(c)
    if not contribs:
        return {}
    merged = merge_contributions(contribs)
    merged.pop("image_url", None)
    return {k: v for k, v in merged.items() if k not in _CORE}
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd backend && python -m pytest tests/unit/services/enrichment/test_material.py -q`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
cd backend && git add app/services/enrichment/material.py tests/unit/services/enrichment/test_material.py
git commit -m "feat(catalog): fetch_object_material 逐件按需材料富化"
```

---

### Task 5: load_stubs 落 stub 对象

**Files:**
- Create: `backend/app/services/enrichment/catalog_loader.py`
- Test: `backend/tests/integration/test_catalog_loader.py`

- [ ] **Step 1: 写失败测试**

Create `test_catalog_loader.py`：

```python
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.models.museum import Museum
from app.models.museum_object import MuseumObject, ObjectImage
from app.services.enrichment.catalog_loader import load_stubs
from app.services.enrichment.catalog_source import StubRecord


def _session():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(
        bind=engine,
        tables=[Museum.__table__, MuseumObject.__table__, ObjectImage.__table__],
    )
    return sessionmaker(bind=engine)()


def _stub(qid, title="T", inv=None):
    return StubRecord(
        inventory_number=inv,
        qid=qid,
        title=title,
        artist="Manet",
        year="1868",
        category="painting",
        image_url="http://img/x.jpg",
        popularity=5,
        owning_museum="orsay",
        source="wikidata",
        external_ids={"P347": "j1"},
        wiki_titles={"en": "The_Balcony"},
    )


def _museum():
    return {"slug": "orsay", "name_en": "Orsay", "name_zh": "奥赛"}


def test_load_stubs_creates_stub_objects_with_routing():
    s = _session()
    out = load_stubs(s, _museum(), [_stub("Q1", inv="RF 1")])
    assert out["loaded"] == 1 and out["stub"] == 1
    o = s.query(MuseumObject).filter_by(qid="Q1").one()
    assert o.content_status == "stub"
    assert o.title_en == "T" and o.popularity == 5
    assert o.attributes["external_ids"] == {"P347": "j1"}
    assert o.attributes["wiki_titles"] == {"en": "The_Balcony"}
    img = s.query(ObjectImage).filter_by(object_id=o.id, role="primary").one()
    assert img.source_url == "https://img/x.jpg"


def test_load_stubs_preserves_ready_status_and_material():
    s = _session()
    load_stubs(s, _museum(), [_stub("Q1")])
    o = s.query(MuseumObject).filter_by(qid="Q1").one()
    o.content_status = "ready"
    o.attributes = {**o.attributes, "extract_en": "已生成材料"}
    s.commit()
    # 再列一次：不下调 ready，且保留已抓材料
    out = load_stubs(s, _museum(), [_stub("Q1")])
    assert out["stub"] == 0
    o2 = s.query(MuseumObject).filter_by(qid="Q1").one()
    assert o2.content_status == "ready"
    assert o2.attributes["extract_en"] == "已生成材料"
    assert o2.attributes["external_ids"] == {"P347": "j1"}
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && python -m pytest tests/integration/test_catalog_loader.py -q`
Expected: FAIL（`No module named '...catalog_loader'`）

- [ ] **Step 3: 实现 catalog_loader.py**

```python
"""把 CatalogSource 产的 StubRecord 列灌成 stub 对象（只元数据 + 路由信息）。
保留已有材料（不覆盖 attributes 里的 extract_* 等），不把已 ready 的件降级回 stub。
spec §6：列目录廉价批量，材料留生成时逐件抓。"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.services.enrichment.catalog_source import StubRecord
from app.services.object_importer import find_object, upsert_museum, upsert_object


def load_stubs(db: Session, museum: dict, stubs: list[StubRecord]) -> dict:
    """StubRecord 列 → stub 对象。返回 {loaded, stub}。"""
    m = upsert_museum(db, museum)
    n_stub = 0
    for s in stubs:
        # 读既有材料，路由信息 merge 进去（不抹掉 extract_* 等已抓材料）
        existing = find_object(db, m.id, {"qid": s.qid, "inventory_number": s.inventory_number})
        attrs = dict(existing.attributes or {}) if existing else {}
        attrs["external_ids"] = s.external_ids or {}
        attrs["wiki_titles"] = s.wiki_titles or {}
        art = {
            "qid": s.qid,
            "inventory_number": s.inventory_number,
            "title_en": s.title,
            "artist_en": s.artist,
            "year": s.year,
            "category": s.category,
            "popularity": s.popularity or 0,
            "image": s.image_url,
            "attributes": attrs,
        }
        obj = upsert_object(db, m.id, art)
        if obj.content_status != "ready":
            obj.content_status = "stub"
            n_stub += 1
        db.add(obj)
    db.commit()
    return {"loaded": len(stubs), "stub": n_stub}
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd backend && python -m pytest tests/integration/test_catalog_loader.py -q`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
cd backend && git add app/services/enrichment/catalog_loader.py tests/integration/test_catalog_loader.py
git commit -m "feat(catalog): load_stubs 落 stub 对象（保留材料、不下调 ready）"
```

---

### Task 6: generate_object 逐件抓材料 + content_status 流转

**Files:**
- Modify: `backend/app/services/enrichment/pipeline.py`
- Test: `backend/tests/integration/test_generate_pipeline.py`

- [ ] **Step 1: 写失败测试**

在 `test_generate_pipeline.py` 末尾追加（复用文件内 `session`/`_FakeEnricher`/`_FakeGate`/`_FakeTranslator`）：

```python
class _FakeRegistry:
    def __init__(self):
        self.calls = []

    def route(self, external_ids):
        from app.services.enrichment.sources.base import ObjectContribution, Source

        outer = self

        class _Src(Source):
            name = "wikipedia"

            def fetch(self, cfg):
                return []

            def enrich(self, qid, ext, ctx):
                outer.calls.append(qid)
                return ObjectContribution(
                    source="wikipedia", qid=qid, fields={"extract_en": "fetched"}, raw={}
                )

        return [_Src()]


def test_generate_object_fetches_material_for_stub_and_marks_ready(session):
    from app.models.museum_object import MuseumObject
    from app.services.enrichment.pipeline import generate_object

    o = session.query(MuseumObject).filter_by(qid="Q1").one()
    o.content_status = "stub"
    o.attributes = {"external_ids": {}, "wiki_titles": {"en": "X"}}
    session.commit()

    reg = _FakeRegistry()
    out = generate_object(
        session,
        "Q1",
        enricher=_FakeEnricher(),
        gate=_FakeGate(),
        translator=_FakeTranslator(),
        target_langs=["en", "fr"],
        model="gpt-4o-mini",
        registry=reg,
    )
    assert "counts" in out and reg.calls == ["Q1"]
    o2 = session.query(MuseumObject).filter_by(qid="Q1").one()
    assert o2.content_status == "ready"
    assert o2.attributes["extract_en"] == "fetched"


def test_generate_object_marks_empty_when_nothing_published(session):
    from app.models.museum_object import MuseumObject
    from app.services.enrichment.pipeline import generate_object
    from app.services.enrichment.quality import SectionQuality

    class _RejectGate:
        def gate(self, material, facts, draft):
            return {
                "overview": SectionQuality(
                    body=None, status="needs_review", grounding_ratio=0.0
                )
            }

    out = generate_object(
        session,
        "Q1",
        enricher=_FakeEnricher(),
        gate=_RejectGate(),
        translator=_FakeTranslator(),
        target_langs=["en"],
        model="m",
    )
    assert out["counts"]["en"] == (0, 1)
    o = session.query(MuseumObject).filter_by(qid="Q1").one()
    assert o.content_status == "empty"


def test_generate_object_no_registry_skips_material_fetch(session):
    # 无 registry：不抓材料（兼容老全量路径），仍正常生成 + 流转 ready
    from app.models.museum_object import MuseumObject
    from app.services.enrichment.pipeline import generate_object

    o = session.query(MuseumObject).filter_by(qid="Q1").one()
    o.content_status = "stub"
    session.commit()
    out = generate_object(
        session,
        "Q1",
        enricher=_FakeEnricher(),
        gate=_FakeGate(),
        translator=_FakeTranslator(),
        target_langs=["en"],
        model="m",
    )
    assert "counts" in out
    assert session.query(MuseumObject).filter_by(qid="Q1").one().content_status == "ready"
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && python -m pytest tests/integration/test_generate_pipeline.py -q`
Expected: FAIL（`generate_object` 不接受 `registry`；无 content_status 流转）

- [ ] **Step 3: 改 pipeline.py**

在 `pipeline.py` 顶部 import 区加：

```python
from app.services.enrichment.material import fetch_object_material
```

`generate_object` 签名加 `registry=None`（放在 `qa_suggester=None` 之后）：

```python
def generate_object(
    db,
    qid,
    *,
    enricher,
    gate,
    translator,
    target_langs,
    model,
    force=False,
    qa_suggester=None,
    registry=None,
) -> dict:
```

在 `if not force and _has_published_en(db, o.id):` 的 return 之后、`obj = _row_to_obj(o)` 之前，插入 stub 逐件抓材料：

```python
    if registry is not None and o.content_status == "stub":
        attrs = o.attributes or {}
        fetched = fetch_object_material(
            o.qid,
            attrs.get("external_ids") or {},
            attrs.get("wiki_titles") or {},
            registry,
        )
        if fetched:
            o.attributes = {**attrs, **fetched}
            db.flush()
```

在 `pub_en, nr_en = persist_gated_sections(db, qid, "en", gated_en, model)` 之后，插入 content_status 流转：

```python
    o.content_status = "ready" if pub_en > 0 else "empty"
    db.flush()
```

`generate_museum` 签名加 `registry=None`，并在调用 `generate_object(...)` 时透传 `registry=registry`：

```python
def generate_museum(
    db,
    slug,
    *,
    enricher,
    gate,
    translator,
    target_langs,
    model,
    force=False,
    limit=None,
    qa_suggester=None,
    registry=None,
) -> dict:
```

循环内的 `generate_object(...)` 调用加一行 `registry=registry,`。

- [ ] **Step 4: 运行测试确认通过**

Run: `cd backend && python -m pytest tests/integration/test_generate_pipeline.py -q`
Expected: PASS（含原有用例）

- [ ] **Step 5: 提交**

```bash
cd backend && git add app/services/enrichment/pipeline.py tests/integration/test_generate_pipeline.py
git commit -m "feat(catalog): generate_object 对 stub 逐件抓材料 + content_status 流转"
```

---

### Task 7: onboard catalog 子命令 + generate 接 registry

**Files:**
- Modify: `backend/scripts/onboard.py`
- Test: `backend/tests/unit/services/enrichment/test_onboard_parser.py`

- [ ] **Step 1: 写失败测试**

Create `test_onboard_parser.py`：

```python
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "scripts"))

from onboard import build_parser


def test_parser_supports_catalog_subcommand():
    ns = build_parser().parse_args(["orsay", "catalog", "--target", "prod"])
    assert ns.command == "catalog" and ns.slug == "orsay" and ns.target == "prod"
```

> 注：`parents[4]` 从 `tests/unit/services/enrichment/test_onboard_parser.py` 回到 `backend/`，再进 `scripts/`。运行前先确认层级，必要时调整索引。

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && python -m pytest tests/unit/services/enrichment/test_onboard_parser.py -q`
Expected: FAIL（`invalid choice: 'catalog'`）

- [ ] **Step 3: 加 catalog 子命令 + 构造逻辑**

在 `onboard.py` 的 `build_parser` 里，`lo = sub.add_parser("load")` 段之后加：

```python
    ca = sub.add_parser("catalog")
    ca.add_argument("--target", choices=["staging", "prod"], required=True)
```

新增 `cmd_catalog`（放在 `cmd_load` 之后）：

```python
def cmd_catalog(slug: str, target: str) -> None:
    expected = _ENV_BY_TARGET[target]
    if settings.ENVIRONMENT != expected:
        raise SystemExit(
            f"❌ --target={target} 期望容器 ENVIRONMENT={expected}，"
            f"但当前容器 ENVIRONMENT={settings.ENVIRONMENT}。请在 {expected} 环境容器内运行。"
        )
    from app.services.enrichment.catalog_loader import load_stubs
    from app.services.enrichment.identity import merge_stubs
    from app.services.enrichment.sources.wikidata_catalog import WikidataCatalog

    cfg = _catalog().get(slug)
    stubs = merge_stubs(list(WikidataCatalog().list(cfg)))
    museum = {
        "slug": cfg.slug,
        "qid": cfg.wikidata_qid,
        "name_zh": cfg.name_zh,
        "name_en": cfg.name_en,
        "city_zh": cfg.city_zh,
        "city_en": cfg.city_en,
        "country": cfg.country,
    }
    db = SessionLocal()
    try:
        out = load_stubs(db, museum, stubs)
    finally:
        db.close()
    print(f"✓ catalog 落库: {out}")
```

在 `cmd_generate` 里构造 registry 并下传。把 LLM 组件构造段之后、`db = SessionLocal()` 之前加：

```python
    from app.services.enrichment.http_client import PoliteSession
    from app.services.enrichment.registry import SourceRegistry
    from app.services.enrichment.sources.joconde import JocondeSource
    from app.services.enrichment.sources.wikipedia import WikipediaSource

    ua = "GoMuseumBot/0.1 (https://gomuseum.app; contact appcraft008@gmail.com)"
    session = PoliteSession(user_agent=ua, min_interval=1.0)
    registry = SourceRegistry(
        [JocondeSource(session=session), WikipediaSource(session=session)]
    )
```

并在 `cmd_generate` 内两处 `generate_object(...)`/`generate_museum(...)` 调用各加一行 `registry=registry,`。

在 `main` 的分发里加：

```python
    elif ns.command == "catalog":
        cmd_catalog(ns.slug, ns.target)
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd backend && python -m pytest tests/unit/services/enrichment/test_onboard_parser.py -q`
Expected: PASS

- [ ] **Step 5: 全量后端测试 + 提交**

Run: `cd backend && python -m pytest -q`
Expected: PASS（全绿）

```bash
cd backend && git add scripts/onboard.py tests/unit/services/enrichment/test_onboard_parser.py
git commit -m "feat(catalog): onboard catalog 子命令 + generate 接富化 registry"
```

---

## Self-Review

- **Spec §9 Phase B 覆盖**：列目录/抓材料解耦（Task 4 material + Task 6 generate 接线）✓；预生成改逐件抓材料（Task 6）✓；`onboard catalog`（Task 7）✓；身份去重——`merge_stubs` 强键单源 no-op 已够（Task 7 调用），真模糊/字段级/拥有馆解析显式留 Phase C（见 Scope）。
- **无迁移**：`content_status` 列 Phase A 已加，本期纯加法代码。
- **前向兼容**：未改任何契约端点；`content_status` 流转只写既有列；老全量路径（registry=None）行为不变（Task 6 第三个用例守护）。
- **类型一致**：`fetch_object_material(qid, external_ids, wiki_titles, registry)` 在 Task 4 定义、Task 6 同签名调用；`load_stubs(db, museum, stubs)`、`find_object(db, museum_id, art)` 一致。
- **幂等**：load_stubs 不下调 ready、保留材料（Task 5 第二用例）；generate 跳过已发布英语。

## 上 staging 后的人工验证（prod 金丝雀前）

合 staging 后，可在 staging 容器内试跑（小馆/小 limit）：
1. `python scripts/onboard.py orsay catalog --target staging` → 落 stub。
2. `python scripts/onboard.py orsay generate --target staging --limit 3 --langs en` → 观察 stub 件被逐件抓材料 + 流转 ready/empty。
（prod 全量富化按既定原则另行金丝雀，不在本计划。）
