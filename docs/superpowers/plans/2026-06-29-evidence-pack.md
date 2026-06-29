# 证据包（阶段1）Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 每件生成时从配全的源组装一份**分类证据包**(结构原子事实 + 标源叙事块 + LLM 抽的争议项)落 `MuseumObject.evidence_pack`;并据其结构化事实把"作品信息"面板**策展+人性化**(去学术噪音)。

**Architecture:** 新 `evidence.py` 组装证据包(注入式 run_query/complete,离线可测);复用现有 attributes(Joconde/Wikipedia 已抓)+ 新 Wikidata 富属性查询。本期**只建+存+用于 facts 面板**,生成主路径不切到证据包(阶段2)。纯加法 + 一个新列迁移。spec `docs/superpowers/specs/2026-06-29-evidence-pack-design.md`。

**Tech Stack:** Python + pytest + SQLAlchemy/Alembic;注入式组件。

---

## File Structure

- **Modify** `backend/app/models/museum_object.py` — `evidence_pack` JSONB 列 + Alembic 迁移。
- **Create** `backend/app/services/enrichment/evidence.py` — `build_evidence_pack` + 富属性 SPARQL + topic 映射 + 争议抽出 prompt。
- **Modify** `backend/app/services/enrichment/sources/joconde.py` — 补字段。
- **Modify** `backend/app/services/enrichment/pipeline.py` — generate_object 产出+落 evidence_pack(缺则建,try/except)。
- **Modify** `backend/app/services/museum_repo.py` — get_object_content.facts 策展+人性化。
- **Modify** `docs/architecture/museum-api-contract.md` — 回写(evidence_pack + facts 策展)。

测试:`test_evidence.py`(新)、`test_joconde_source.py`、`test_generate_pipeline.py`、`test_pack_and_content_facts.py`。

> 命令在 `backend/` 下跑。

---

### Task 1: evidence_pack 列 + 迁移

**Files:**
- Modify: `backend/app/models/museum_object.py`
- Create: `backend/alembic/versions/h1e4_add_evidence_pack.py`
- Test: `backend/tests/integration/test_evidence_pack_column.py`

参考既有:`museum_object.py` 已用 `MutableDict.as_mutable(JSON().with_variant(JSONB,"postgresql"))`(见 `attributes`/`sources`)。alembic head = `g1d3_add_guide_section_type`。

- [ ] **Step 1: 写失败测试**

```python
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.models.museum import Museum
from app.models.museum_object import MuseumObject, ObjectImage
from app.services.object_importer import upsert_museum, upsert_object


def test_evidence_pack_column_roundtrip():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(bind=engine, tables=[Museum.__table__, MuseumObject.__table__, ObjectImage.__table__])
    s = sessionmaker(bind=engine)()
    m = upsert_museum(s, {"slug": "orsay", "name_en": "Orsay"})
    o = upsert_object(s, m.id, {"qid": "Q1", "title_en": "X"})
    o.evidence_pack = {"facts": [{"claim": "c", "value": "v"}]}
    s.commit()
    assert s.query(MuseumObject).filter_by(qid="Q1").one().evidence_pack["facts"][0]["value"] == "v"
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && python -m pytest tests/integration/test_evidence_pack_column.py -q`
Expected: FAIL（无 evidence_pack 属性）

- [ ] **Step 3: 加列** — 在 `museum_object.py` 的 `MuseumObject` 里(`sources` 列附近)加:

```python
    evidence_pack = Column(
        MutableDict.as_mutable(JSON().with_variant(JSONB, "postgresql")),
        nullable=True,
    )  # 分类证据包(facts/narrative/flagged);内容生成的材料底座
```

- [ ] **Step 4: 写迁移** — `backend/alembic/versions/h1e4_add_evidence_pack.py`:

```python
"""add evidence_pack JSONB column to museum_objects"""
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "h1e4_add_evidence_pack"
down_revision = "g1d3_add_guide_section_type"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "museum_objects",
        sa.Column("evidence_pack", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("museum_objects", "evidence_pack")
```

- [ ] **Step 5: 运行确认通过 + 单 head 校验**

Run: `cd backend && python -m pytest tests/integration/test_evidence_pack_column.py -q`（PASS）
Run: `cd backend && python -c "from alembic.config import Config; from alembic.script import ScriptDirectory; print(ScriptDirectory.from_config(Config('alembic.ini')).get_heads())"`（应只有 `['h1e4_add_evidence_pack']`）

- [ ] **Step 6: 提交**

```bash
cd backend && git add app/models/museum_object.py alembic/versions/h1e4_add_evidence_pack.py tests/integration/test_evidence_pack_column.py
git commit -m "feat(evidence): MuseumObject.evidence_pack 列 + 迁移"
```

---

### Task 2: Wikidata 富属性 → 事实原子

**Files:**
- Create: `backend/app/services/enrichment/evidence.py`
- Test: `backend/tests/unit/services/enrichment/test_evidence.py`

参考既有:`material.fetch_artist_material` 的注入式 run_query 模式;`sources/wikidata.py` 的 `SPARQL_ENDPOINT`/`USER_AGENT`/`_v`。

- [ ] **Step 1: 写失败测试**

```python
def test_fetch_rich_facts_maps_props_to_topics():
    from app.services.enrichment.evidence import fetch_rich_facts

    def fake_run_query(sparql):
        # 模拟 wikibase:label 服务返回值+标签
        return [
            {"pid": {"value": "P88"}, "vLabel": {"value": "Khalil Bey"}},
            {"pid": {"value": "P180"}, "vLabel": {"value": "female nude"}},
            {"pid": {"value": "P135"}, "vLabel": {"value": "Realism"}},
        ]

    facts = fetch_rich_facts("Q1", run_query=fake_run_query)
    by = {f["source"]: f for f in facts}
    assert by["wikidata:P88"]["value"] == "Khalil Bey" and by["wikidata:P88"]["topic"] == "background"
    assert by["wikidata:P180"]["topic"] == "analysis"
    assert by["wikidata:P135"]["topic"] == "significance"


def test_fetch_rich_facts_empty_on_no_rows():
    from app.services.enrichment.evidence import fetch_rich_facts
    assert fetch_rich_facts("Q1", run_query=lambda s: []) == []
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && python -m pytest tests/unit/services/enrichment/test_evidence.py -q`
Expected: FAIL（无 evidence 模块）

- [ ] **Step 3: 实现** — `evidence.py`:

```python
"""证据包组装:结构原子事实 + 标源叙事块 + LLM 抽争议。spec 2026-06-29-evidence-pack。"""

from __future__ import annotations

from app.services.enrichment.sources import wikidata as _wd

# 富属性 → (claim 中文名, lane topic)。结构化 → type=fact。
_RICH_PROPS = {
    "P88": ("委托人", "background"),
    "P180": ("描绘内容", "analysis"),
    "P186": ("材质", "analysis"),
    "P135": ("艺术流派", "significance"),
    "P136": ("题材", "significance"),
    "P1343": ("著录文献", "material"),
}

_RICH_QUERY = """
SELECT ?pid ?vLabel WHERE {{
  VALUES ?prop {{ wdt:P88 wdt:P180 wdt:P186 wdt:P135 wdt:P136 wdt:P1343 }}
  wd:{qid} ?prop ?v .
  ?p wikibase:directClaim ?prop . BIND(STRAFTER(STR(?p), "entity/") AS ?pid)
  SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
}}
"""


def _default_run_query(sparql):
    import requests

    r = requests.get(
        _wd.SPARQL_ENDPOINT,
        params={"query": sparql, "format": "json"},
        headers={"User-Agent": _wd.USER_AGENT, "Accept": "application/sparql-results+json"},
        timeout=60,
    )
    r.raise_for_status()
    return r.json()["results"]["bindings"]


def fetch_rich_facts(qid: str, *, run_query=None) -> list[dict]:
    """Wikidata 富属性 → 事实原子 [{claim,value,source,topic}]。无→[]。"""
    run_query = run_query or _default_run_query
    rows = run_query(_RICH_QUERY.format(qid=qid))
    out = []
    for row in rows:
        pid = (row.get("pid") or {}).get("value", "")
        val = (row.get("vLabel") or {}).get("value")
        if pid in _RICH_PROPS and val:
            claim, topic = _RICH_PROPS[pid]
            out.append({"claim": claim, "value": val, "source": f"wikidata:{pid}", "topic": topic})
    return out
```

- [ ] **Step 4: 通过 + 提交**

Run: `cd backend && python -m pytest tests/unit/services/enrichment/test_evidence.py -q`（PASS）
```bash
cd backend && git add app/services/enrichment/evidence.py tests/unit/services/enrichment/test_evidence.py
git commit -m "feat(evidence): Wikidata 富属性→事实原子(topic映射)"
```

---

### Task 3: Joconde 补字段

**Files:**
- Modify: `backend/app/services/enrichment/sources/joconde.py`
- Test: `backend/tests/unit/services/enrichment/test_joconde_source.py`

- [ ] **Step 1: 加失败测试** — 在 `test_enrich_maps_french_fields` 的 fake fields 补 `"domaine":"peinture","denomination":"tableau","ecole_pays":"France","periode_de_creation":"3e quart 19e siècle","localisation":"Paris ; musée d'Orsay"`,并末尾断言:

```python
    assert c.fields["domaine_fr"] == "peinture"
    assert c.fields["denomination_fr"] == "tableau"
    assert c.fields["school_fr"] == "France"
    assert c.fields["location_fr"] == "Paris ; musée d'Orsay"
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && python -m pytest tests/unit/services/enrichment/test_joconde_source.py -q`
Expected: FAIL

- [ ] **Step 3: 实现** — 在 `joconde.py` 的 `fields` 字典里补:

```python
            "subjects_fr": f.get("sujet_represente"),
            "period_fr": f.get("periode_de_creation"),
            "domaine_fr": f.get("domaine"),
            "denomination_fr": f.get("denomination"),
            "school_fr": f.get("ecole_pays"),
            "location_fr": f.get("localisation"),
```

- [ ] **Step 4: 通过 + 提交**

Run: `cd backend && python -m pytest tests/unit/services/enrichment/test_joconde_source.py -q`（PASS）
```bash
cd backend && git add app/services/enrichment/sources/joconde.py tests/unit/services/enrichment/test_joconde_source.py
git commit -m "feat(evidence): Joconde 补 domaine/denomination/school/location"
```

---

### Task 4: build_evidence_pack 组装(facts + narrative)

**Files:**
- Modify: `backend/app/services/enrichment/evidence.py`
- Test: `backend/tests/unit/services/enrichment/test_evidence.py`

- [ ] **Step 1: 写失败测试**

```python
def test_build_evidence_pack_assembles_facts_and_narrative():
    from app.services.enrichment.evidence import build_evidence_pack

    obj = {
        "qid": "Q1", "title_en": "Origin", "artist_en": "Courbet", "year": "1866",
        "attributes": {
            "medium_fr": "huile sur toile", "subjects_fr": "nu",
            "extract_en": "<work article>", "artist_extract_en": "<artist bio>",
        },
    }
    pack = build_evidence_pack(
        obj, run_query=lambda s: [], complete=None  # 无富属性、无 LLM
    )
    fact_sources = {f["source"] for f in pack["facts"]}
    assert "joconde:medium" in fact_sources or any("medium" in s for s in fact_sources)
    nsrc = {n["source"] for n in pack["narrative"]}
    assert "wikipedia:work" in nsrc and "wikipedia:artist" in nsrc
    assert all(n["type"] == "mainstream" for n in pack["narrative"])
    assert pack["flagged"] == []  # complete=None → 不抽争议
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && python -m pytest tests/unit/services/enrichment/test_evidence.py::test_build_evidence_pack_assembles_facts_and_narrative -q`
Expected: FAIL

- [ ] **Step 3: 实现** — 在 `evidence.py` 加(顶部 `_JOCONDE_FACT_KEYS` 映射 attributes 键→(claim,topic,tier)):

```python
# Joconde/基础 attributes → (claim, topic, display tier)。wall_label=进面板, material=只喂生成。
_ATTR_FACTS = {
    "medium_fr": ("材质", "analysis", "wall_label"),
    "dimensions": ("尺寸", "analysis", "wall_label"),
    "inventory_number": ("馆藏号", "background", "wall_label"),
    "subjects_fr": ("主题", "analysis", "material"),
    "provenance_fr": ("来源流转", "background", "material"),
    "exhibitions_fr": ("展览史", "background", "material"),
    "bibliography_fr": ("参考文献", "material", "material"),
    "period_fr": ("创作时期", "background", "material"),
    "school_fr": ("流派国别", "significance", "material"),
}


def build_evidence_pack(obj: dict, *, run_query=None, complete=None) -> dict:
    """组装证据包:结构原子 facts + 标源 narrative + (可选)LLM flagged。"""
    attrs = obj.get("attributes") or {}
    facts = []
    # 基础事实(对象字段)
    for claim, key, topic, tier in [
        ("艺术家", "artist_en", "artist", "wall_label"),
        ("年代", "year", "background", "wall_label"),
        ("标题", "title_en", "background", "wall_label"),
    ]:
        if obj.get(key):
            facts.append({"claim": claim, "value": obj[key], "source": f"object:{key}", "topic": topic, "tier": tier})
    # Joconde/attributes 事实
    for key, (claim, topic, tier) in _ATTR_FACTS.items():
        if attrs.get(key):
            facts.append({"claim": claim, "value": attrs[key], "source": f"joconde:{key}", "topic": topic, "tier": tier})
    # Wikidata 富属性
    if obj.get("qid"):
        for f in fetch_rich_facts(obj["qid"], run_query=run_query):
            f.setdefault("tier", "material")
            facts.append(f)
    # 叙事块
    narrative = []
    for key, src in [("extract_en", "wikipedia:work"), ("extract_fr", "wikipedia:work"),
                     ("artist_extract_en", "wikipedia:artist"), ("artist_extract_fr", "wikipedia:artist")]:
        if attrs.get(key):
            narrative.append({"text": attrs[key], "source": src, "type": "mainstream"})
    # 争议抽出(Task 5 接 complete)
    flagged = _extract_flagged(narrative, complete) if complete else []
    return {"facts": facts, "narrative": narrative, "flagged": flagged}


def _extract_flagged(narrative, complete) -> list:
    return []  # Task 5 实现
```

> 注:Wikidata 富属性 `fetch_rich_facts` 默认会真连网;测试传 `run_query=lambda s: []` 跳过。`tier` 字段供 Task 7 面板策展。

- [ ] **Step 4: 通过 + 提交**

Run: `cd backend && python -m pytest tests/unit/services/enrichment/test_evidence.py -q`（PASS）
```bash
cd backend && git add app/services/enrichment/evidence.py tests/unit/services/enrichment/test_evidence.py
git commit -m "feat(evidence): build_evidence_pack 组装 facts(分级tier)+narrative"
```

---

### Task 5: 争议抽出(LLM)

**Files:**
- Modify: `backend/app/services/enrichment/evidence.py`
- Test: `backend/tests/unit/services/enrichment/test_evidence.py`

参考:`content_enricher._parse_json` 容错解析。

- [ ] **Step 1: 写失败测试**

```python
def test_extract_flagged_classifies_contested():
    import json as _json
    from app.services.enrichment.evidence import build_evidence_pack

    def fake(system, user):
        return _json.dumps({"flagged": [
            {"text": "研究者认为模特是 X", "type": "contested"},
            {"text": "可能创作于战前", "type": "inference"},
        ]})

    obj = {"qid": "Q1", "attributes": {"extract_en": "Scholars believe the model was X. Possibly made before the war."}}
    pack = build_evidence_pack(obj, run_query=lambda s: [], complete=fake)
    types = {f["type"] for f in pack["flagged"]}
    assert "contested" in types and "inference" in types


def test_extract_flagged_robust_on_llm_error():
    from app.services.enrichment.evidence import build_evidence_pack

    def boom(system, user):
        raise RuntimeError("llm down")

    pack = build_evidence_pack({"qid": "Q1", "attributes": {"extract_en": "x"}}, run_query=lambda s: [], complete=boom)
    assert pack["flagged"] == []  # LLM 失败优雅降级
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && python -m pytest tests/unit/services/enrichment/test_evidence.py -q`
Expected: FAIL

- [ ] **Step 3: 实现** — 替换 `_extract_flagged`:

```python
_FLAGGED_SYSTEM = (
    "You are a sourcing analyst. From the MATERIAL, extract ONLY sentences that are NOT "
    "settled fact — i.e. scholarly opinion / interpretation, hedged claims (may, possibly, "
    "believed), disputes, or unverified attributions (e.g. the model's identity). For each, "
    "classify type as one of: contested | inference | unverified. Ignore plain facts. "
    'Return STRICT JSON: {"flagged": [{"text": "...", "type": "..."}]} (empty if none). No commentary.'
)


def _extract_flagged(narrative, complete) -> list:
    text = "\n\n".join(n["text"] for n in narrative if n.get("text"))
    if not text.strip():
        return []
    try:
        from app.services.enrichment.content_enricher import _parse_json

        raw = complete(_FLAGGED_SYSTEM, f"MATERIAL:\n{text}")
        items = _parse_json(raw).get("flagged") or []
        return [
            {"text": it["text"], "type": it.get("type", "contested"), "source": "wikipedia"}
            for it in items
            if isinstance(it, dict) and it.get("text")
        ]
    except Exception:
        return []
```

- [ ] **Step 4: 通过 + 提交**

Run: `cd backend && python -m pytest tests/unit/services/enrichment/test_evidence.py -q`（PASS）
```bash
cd backend && git add app/services/enrichment/evidence.py tests/unit/services/enrichment/test_evidence.py
git commit -m "feat(evidence): LLM 抽争议/推测/未证实项(健壮降级)"
```

---

### Task 6: pipeline 产出 + 落 evidence_pack

**Files:**
- Modify: `backend/app/services/enrichment/pipeline.py`
- Test: `backend/tests/integration/test_generate_pipeline.py`

参考:`generate_object` 已有 `registry`/作者材料抓取段;`o.attributes` 可用;`enricher._complete` 是注入的 LLM(但 build_evidence_pack 用独立 complete)。本期用 `default_complete` 跑争议抽出。

- [ ] **Step 1: 写失败测试**

```python
def test_generate_object_builds_evidence_pack(session):
    from app.models.museum_object import MuseumObject
    from app.services.enrichment.pipeline import generate_object

    o = session.query(MuseumObject).filter_by(qid="Q1").one()
    o.attributes = {"extract_en": "work text"}
    session.commit()
    generate_object(session, "Q1", enricher=_FakeEnricher(), gate=_FakeGate(),
                    translator=_FakeTranslator(), target_langs=["en"], model="m")
    o2 = session.query(MuseumObject).filter_by(qid="Q1").one()
    assert o2.evidence_pack is not None
    assert any(n["source"] == "wikipedia:work" for n in o2.evidence_pack["narrative"])
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && python -m pytest tests/integration/test_generate_pipeline.py::test_generate_object_builds_evidence_pack -q`
Expected: FAIL

- [ ] **Step 3: 实现** — 在 `generate_object` 里,英语段落落库之前(material/facts 算好之后),加(缺则建、try/except、reuse):

```python
    # 证据包:缺则建并落库(内容生成的材料底座;阶段2 才切到它生成)
    if o.evidence_pack is None or force:
        from app.services.enrichment.evidence import build_evidence_pack

        try:
            o.evidence_pack = build_evidence_pack(obj | {"qid": o.qid}, complete=_evidence_complete())
            db.flush()
        except Exception:
            pass
```

并在 `pipeline.py` 顶部加惰性 complete provider:

```python
def _evidence_complete():
    from app.services.enrichment.content_enricher import default_complete

    return default_complete
```

> 注:测试里 generate 不传 registry/真实网络;`build_evidence_pack` 的 `run_query`/`complete` 默认会连网/调 LLM——**测试用例需让 build 离线**:给 `_evidence_complete` 留注入点,或测试只断言 narrative(来自 attributes,不依赖网络)且 `run_query` 默认空失败被 try/except 吞。**实现时确认测试离线稳定**:fetch_rich_facts 网络失败 → build 内部应 try/except 让 facts 仍含 attributes 部分(在 Task 4 的 build 里给 fetch_rich_facts 包 try/except 返 [])。

- [ ] **Step 4: 通过(含原有用例) + 提交**

Run: `cd backend && python -m pytest tests/integration/test_generate_pipeline.py -q`（全 PASS）
```bash
cd backend && git add app/services/enrichment/pipeline.py app/services/enrichment/evidence.py tests/integration/test_generate_pipeline.py
git commit -m "feat(evidence): generate_object 产出并落 evidence_pack(缺则建)"
```

---

### Task 7: facts 面板策展 + 人性化

**Files:**
- Modify: `backend/app/services/museum_repo.py`
- Test: `backend/tests/integration/test_pack_and_content_facts.py`

参考:`get_object_content` 现 `facts` 取 attributes 原始值(medium_fr/dimensions/provenance/exhibitions/bibliography)。改为只返展示级 + 人性化;academic 项移出。

- [ ] **Step 1: 改测试**(把现有 facts 断言改成新预期)

```python
def test_content_facts_curated_and_humanized(session):
    from app.models.museum_object import MuseumObject
    from app.services.museum_repo import get_object_content

    o = session.query(MuseumObject).filter_by(qid="Q1").one()
    o.attributes = {
        "medium_fr": "huile sur toile", "dimensions": "en mètres : L. 0,55 ; H. 0,46",
        "provenance_fr": "coll X", "exhibitions_fr": "1988#1996", "bibliography_fr": "Tabarant 66",
    }
    # 证据包给干净 medium/dimensions(wall_label)
    o.evidence_pack = {"facts": [
        {"claim": "材质", "value": "Oil on canvas", "source": "wikidata:P186", "topic": "analysis", "tier": "wall_label"},
    ], "narrative": [], "flagged": []}
    session.commit()
    f = get_object_content(session, "orsay", "Q1", "zh")["facts"]
    # academic 项移出面板
    assert not f.get("bibliography")
    assert not f.get("provenance")
    assert not f.get("exhibitions")
    # 仍有 wall_label 项
    assert f["medium"]  # 取自 evidence_pack wall_label,或 attributes 回退
    assert "artist" in f and "date" in f
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && python -m pytest tests/integration/test_pack_and_content_facts.py -q`
Expected: FAIL

- [ ] **Step 3: 实现** — 改 `get_object_content` 的 `facts` 组装:
  - `medium`:优先 evidence_pack 里 `source=="wikidata:P186"` 的 wall_label 值,否则 attributes `medium_fr`。
  - `dimensions`:优先 evidence_pack 里描绘尺寸的 wall_label(P2048/P2049 若有),否则 attributes `dimensions`。
  - `provenance`/`exhibitions`/`bibliography`:**置 None/[]**(移出面板)。
  - `artist`/`date`/`inventory`/`location`:保留(现逻辑)。

  具体:在 facts dict 构建处,加一个从 `obj.evidence_pack` 取 wall_label 值的 helper `_wall(obj, claim_or_pid, fallback)`;把 `provenance`/`exhibitions`/`bibliography` 三键改为返 `None`/`[]`。

- [ ] **Step 4: 通过(含既有 facts/categories/default_guide 用例) + 提交**

Run: `cd backend && python -m pytest tests/integration/test_pack_and_content_facts.py tests/integration/test_museum_repo.py -q`（全 PASS）
```bash
cd backend && git add app/services/museum_repo.py tests/integration/test_pack_and_content_facts.py
git commit -m "feat(evidence): facts 面板策展+人性化(去学术噪音,medium/dimensions取干净源)"
```

---

### Task 8: 全量回归 + 契约文档回写

**Files:**
- Modify: `docs/architecture/museum-api-contract.md`

- [ ] **Step 1: 全量 enrichment + 集成回归**

Run: `cd backend && python -m pytest tests/unit/services/enrichment/ tests/integration/test_generate_pipeline.py tests/integration/test_pack_and_content_facts.py tests/integration/test_evidence_pack_column.py -q`
Expected: PASS（无回归）

- [ ] **Step 2: 回写主文档** — `museum-api-contract.md`:① 端点4 `facts` 说明改为"已策展+人性化(只 wall_label 级;provenance/exhibitions/bibliography 移出面板→阶段2 background 故事)";② §内容体系或新增说明 `MuseumObject.evidence_pack`(facts/narrative/flagged,内容生成材料底座);③ 变更记录加一行。

- [ ] **Step 3: 提交**

```bash
cd /Users/hongyang/Projects/GoMuseum && git add docs/architecture/museum-api-contract.md
git commit -m "docs(api): 回写 evidence_pack + facts 面板策展"
```

---

## Self-Review

- **Spec 覆盖**:evidence_pack 列+迁移(T1)✓ 富属性(T2)✓ Joconde补字段(T3)✓ build 组装 facts/narrative(T4)✓ 争议抽出(T5)✓ pipeline 产出落库(T6)✓ facts 策展人性化(T7)✓ 回写主文档(T8)✓。
- **本期边界**:证据包**只建+存+用于 facts 面板**;生成主路径不切到证据包(阶段2);Europeana 暂缓——均 spec §6 一致。
- **健壮**:fetch_rich_facts / 争议 LLM / build 全 try/except 降级(网络/LLM 抖动不拖垮生成)。
- **前向兼容**:facts 契约形状不变(provenance 等返空);evidence_pack 是后台中间产物不进端点契约;一个加列迁移。
- **类型一致**:`fetch_rich_facts(qid,*,run_query)->[{claim,value,source,topic}]`(T2 定义,T4 用);`build_evidence_pack(obj,*,run_query,complete)->{facts,narrative,flagged}`(T4/5 定义,T6 用);facts 原子带 `tier`(T4 产,T7 用)。

## 上线验证(合 staging 后)

1. staging 重生成几件:`generate --qid <q> --target staging --langs zh --force`(force 触发证据包重建)。
2. DB 查 `evidence_pack`:facts 含 P88 委托人/P180 描绘 + narrative 标源 + flagged 抽出争议。
3. `curl content?language=zh` → facts 面板**只剩干净的 medium/dimensions/artist/date/inventory/location**,无参考文献/法语收藏链。
4. staging APK 看作品信息面板变干净。
