# 作者一等实体 + 中文名 + 状态修 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 作者按 artist QID 生成一次、同作者复用(一致/完整/省);缺中文标题补译;状态按语言判空。

**Architecture:** 新 `artists` 表 + `MuseumObject.attributes["artist_qid"]`;pipeline 生成/复用 Artist、artist 退出 per-work 段;作者卡与 status 读取时从 artists 表/按语言判。spec `2026-07-02-artist-entity-design.md`。

**Tech Stack:** Python + SQLAlchemy/Alembic + pytest。

> 命令在 `backend/` 下跑。alembic head 见 `alembic/versions`(当前 `i1f5_retire_overview_tab`)。

---

### Task 1: Artist 模型 + 迁移

**Files:**
- Create: `backend/app/models/artist.py`
- Create: `backend/alembic/versions/j1g6_add_artists.py`
- Test: `backend/tests/integration/test_artist_model.py`

参考 `app/models/museum.py`(Base、Column 风格);JSONB 用 `museum_object.py` 的 `MutableDict.as_mutable(JSON().with_variant(JSONB,"postgresql"))` 模式。

- [ ] **Step 1: 写失败测试**

```python
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.models.artist import Artist


def test_artist_roundtrip():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(bind=engine, tables=[Artist.__table__])
    s = sessionmaker(bind=engine)()
    s.add(Artist(qid="Q296", name_zh="梵高", name_en="Van Gogh", birth="1853",
                 death="1890", nationality="Netherlands",
                 notable_works=["Starry Night"], bio={"zh": "梵高生平", "en": "bio"}))
    s.commit()
    s.expire_all()
    a = s.query(Artist).filter_by(qid="Q296").one()
    assert a.name_zh == "梵高" and a.bio["zh"] == "梵高生平" and a.notable_works == ["Starry Night"]
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && python -m pytest tests/integration/test_artist_model.py -q`
Expected: FAIL

- [ ] **Step 3: 实现** — `app/models/artist.py`:

```python
"""作者一等实体:按 artist QID 生成一次的规范作者介绍,同作者作品复用。"""

from sqlalchemy import Column, DateTime, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.mutable import MutableDict, MutableList
from sqlalchemy.types import JSON

from app.core.database import Base

_JSON = JSON().with_variant(JSONB, "postgresql")


class Artist(Base):
    __tablename__ = "artists"

    qid = Column(String(32), primary_key=True)  # 作者 Wikidata QID(P170)
    name_zh = Column(String(255), nullable=True)
    name_en = Column(String(255), nullable=True)
    birth = Column(String(16), nullable=True)
    death = Column(String(16), nullable=True)
    nationality = Column(String(128), nullable=True)
    notable_works = Column(MutableList.as_mutable(_JSON), nullable=True)
    bio = Column(MutableDict.as_mutable(_JSON), nullable=True)  # {lang: text}
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
```

- [ ] **Step 4: 写迁移** — `alembic/versions/j1g6_add_artists.py`(down_revision=`i1f5_retire_overview_tab`):

```python
"""add artists table (作者一等实体)"""
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "j1g6_add_artists"
down_revision = "i1f5_retire_overview_tab"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "artists",
        sa.Column("qid", sa.String(length=32), primary_key=True),
        sa.Column("name_zh", sa.String(length=255), nullable=True),
        sa.Column("name_en", sa.String(length=255), nullable=True),
        sa.Column("birth", sa.String(length=16), nullable=True),
        sa.Column("death", sa.String(length=16), nullable=True),
        sa.Column("nationality", sa.String(length=128), nullable=True),
        sa.Column("notable_works", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("bio", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("artists")
```

- [ ] **Step 5: 通过 + 单 head 校验 + 提交**

Run: `cd backend && python -m pytest tests/integration/test_artist_model.py -q`（PASS）
Run: `cd backend && python -c "from alembic.config import Config; from alembic.script import ScriptDirectory; print(ScriptDirectory.from_config(Config('alembic.ini')).get_heads())"`（应 `['j1g6_add_artists']`）
```bash
cd backend && git add app/models/artist.py alembic/versions/j1g6_add_artists.py tests/integration/test_artist_model.py
git commit -m "feat(artist): Artist 一等实体模型 + 迁移"
```

---

### Task 2: fetch_artist_facts 返回 artist_qid

**Files:**
- Modify: `backend/app/services/enrichment/material.py`
- Test: `backend/tests/unit/services/enrichment/test_material.py`

参考:`_ARTIST_FACTS_QUERY`(`wd:{qid} wdt:P170 ?artist`)、`fetch_artist_facts` 返 dict。

- [ ] **Step 1: 写失败测试**

```python
def test_fetch_artist_facts_returns_artist_qid():
    from app.services.enrichment.material import fetch_artist_facts

    def fake(sparql):
        return [{"artist": {"value": "http://www.wikidata.org/entity/Q296"},
                 "natLabel": {"value": "Netherlands"}}]

    f = fetch_artist_facts("Q1", run_query=fake)
    assert f["artist_qid"] == "Q296"
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && python -m pytest tests/unit/services/enrichment/test_material.py::test_fetch_artist_facts_returns_artist_qid -q`
Expected: FAIL

- [ ] **Step 3: 实现** —
(a) `_ARTIST_FACTS_QUERY` 的 SELECT 加 `?artist`（已有 `wd:{qid} wdt:P170 ?artist`，只需 SELECT 出来）：`SELECT ?artist ?birth ?death ?natLabel ?workLabel WHERE {{ ... }}`。
(b) `fetch_artist_facts` 循环里取 artist QID（首个）：
```python
        if "artist_qid" not in out:
            au = (row.get("artist") or {}).get("value", "")
            if au:
                out["artist_qid"] = au.rsplit("/", 1)[-1]
```

- [ ] **Step 4: 通过 + 提交**

Run: `cd backend && python -m pytest tests/unit/services/enrichment/test_material.py -q`（PASS）
```bash
cd backend && git add app/services/enrichment/material.py tests/unit/services/enrichment/test_material.py
git commit -m "feat(artist): fetch_artist_facts 返回 artist_qid"
```

---

### Task 3: generate_artist_bio(一次生成作者介绍)

**Files:**
- Modify: `backend/app/services/enrichment/content_enricher.py`
- Modify: `backend/app/services/enrichment/prompts.py`
- Test: `backend/tests/unit/services/enrichment/test_content_enricher.py`

参考:`generate_default_guide`(单段生成范例);`build_material`(渲染 artist_extract_* 的 [ABOUT THE ARTIST] 块);`section_role("artist")` 的语气。

- [ ] **Step 1: 写失败测试**

```python
def test_generate_artist_bio():
    from app.services.enrichment.content_enricher import ContentEnricher

    enr = ContentEnricher(complete=lambda s, u: "梵高是荷兰后印象派先驱……")
    bio = enr.generate_artist_bio({"artist_extract_en": "Van Gogh was a Dutch painter..."})
    assert bio and "梵高" in bio
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && python -m pytest tests/unit/services/enrichment/test_content_enricher.py::test_generate_artist_bio -q`
Expected: FAIL

- [ ] **Step 3: 实现** —
(a) `prompts.py` 加 `build_artist_bio_prompt(material)`（system=作者其人语气,要求生平/性格/艺术史地位,~200-300 字,接地）：
```python
_ARTIST_BIO_SYSTEM = (
    "You write a concise, engaging biography of an ARTIST (the maker), using ONLY the MATERIAL. "
    "Cover: who they were, their life and character, what drove them, their place in art history. "
    "~200-300 Chinese-char equivalent. Grounded only, no fabrication. Return plain prose, no headings."
)


def build_artist_bio_prompt(material: str):
    return _ARTIST_BIO_SYSTEM, f"MATERIAL (about the artist):\n{material}"
```
(b) `content_enricher.generate_artist_bio(self, artist_obj) -> str|None`：把 artist_extract_* 拼成 material → complete → strip：
```python
    def generate_artist_bio(self, artist_obj: dict) -> str | None:
        parts = [v for k, v in artist_obj.items() if k.startswith("artist_extract_") and v]
        if not parts:
            return None
        material = "\n\n".join(parts)
        system, user = build_artist_bio_prompt(material)
        raw = self._complete(system, user)
        return raw.strip() if isinstance(raw, str) and raw.strip() else None
```
（import build_artist_bio_prompt。）

- [ ] **Step 4: 通过 + 提交**

Run: `cd backend && python -m pytest tests/unit/services/enrichment/test_content_enricher.py tests/unit/services/enrichment/test_prompts.py -q`（PASS）
```bash
cd backend && git add app/services/enrichment/content_enricher.py app/services/enrichment/prompts.py tests/unit/services/enrichment/test_content_enricher.py
git commit -m "feat(artist): generate_artist_bio 一次生成作者介绍"
```

---

### Task 4: artist 退出 per-work 段

**Files:**
- Modify: `backend/app/services/enrichment/category_config.py`
- Test: `backend/tests/unit/services/enrichment/test_category_config.py`

- [ ] **Step 1: 写失败测试**

```python
def test_artist_not_in_per_work_sections():
    from app.services.enrichment.category_config import SECTIONS_BY_CATEGORY

    for codes in SECTIONS_BY_CATEGORY.values():
        assert "artist" not in codes  # 作者成一等实体,不再是每件的段
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && python -m pytest tests/unit/services/enrichment/test_category_config.py::test_artist_not_in_per_work_sections -q`
Expected: FAIL

- [ ] **Step 3: 实现** — `SECTIONS_BY_CATEGORY` 各类目移除 `"artist"`（painting/sculpture/decorative 等含 artist 的）。`SECTION_ROLES["artist"]` 保留（generate_artist_bio 语气参考，无害）。

- [ ] **Step 4: 通过（含既有 seed 用例，若断言段数需同步） + 提交**

Run: `cd backend && python -m pytest tests/unit/services/enrichment/test_category_config.py tests/unit/services/test_seed_sections.py -q`（PASS）
```bash
cd backend && git add app/services/enrichment/category_config.py tests/unit/services/enrichment/test_category_config.py tests/unit/services/test_seed_sections.py
git commit -m "feat(artist): artist 退出 per-work SECTIONS_BY_CATEGORY(成一等实体)"
```

---

### Task 5: pipeline — 生成/复用 Artist + 存 artist_qid + 补 title_zh

**Files:**
- Modify: `backend/app/services/enrichment/pipeline.py`
- Test: `backend/tests/integration/test_generate_pipeline.py`

参考:`generate_object` 的 registry 门控作者材料块(`_artist_facts`)、`translator`、`db`、`o`。需 `from app.models.artist import Artist`。

- [ ] **Step 1: 写失败测试**（monkeypatch _artist_facts 返 artist_qid;验证 Artist 落库 + 复用）

```python
def test_generate_object_creates_and_reuses_artist(session, monkeypatch):
    import app.services.enrichment.pipeline as pl
    from app.models.artist import Artist
    from app.models.museum_object import MuseumObject
    from app.services.enrichment.pipeline import generate_object

    monkeypatch.setattr(pl, "_artist_facts", lambda qid: {"artist_qid": "Q296", "artist_birth": "1853"})

    calls = {"n": 0}

    class _Enr(_FakeEnricher):
        def generate_artist_bio(self, artist_obj):
            calls["n"] += 1
            return "梵高生平。"

    o = session.query(MuseumObject).filter_by(qid="Q1").one()
    o.attributes = {"artist_extract_en": "Van Gogh..."}
    session.commit()
    generate_object(session, "Q1", enricher=_Enr(), gate=_FakeGate(),
                    translator=_FakeTranslator(), target_langs=["en"], model="m", registry=_FakeRegistry())
    art = session.query(Artist).filter_by(qid="Q296").one()
    assert art.bio and art.birth == "1853"
    assert session.query(MuseumObject).filter_by(qid="Q1").one().attributes.get("artist_qid") == "Q296"
    # 第二件同作者:复用,不再调 generate_artist_bio
    o2 = session.query(MuseumObject).filter_by(qid="Q1").one()  # 同件模拟复用路径
    generate_object(session, "Q1", enricher=_Enr(), gate=_FakeGate(),
                    translator=_FakeTranslator(), target_langs=["en"], model="m", registry=_FakeRegistry())
    assert calls["n"] == 1  # 只生成一次
```

> 注:`_FakeRegistry` 见文件既有(Task fixture)。若既有 registry 块因 fake 触网/报错,沿用文件既有处理不额外改。

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && python -m pytest tests/integration/test_generate_pipeline.py::test_generate_object_creates_and_reuses_artist -q`
Expected: FAIL

- [ ] **Step 3: 实现** — 在 `generate_object` 的作者材料块(registry 门控)里,`_artist_facts` 之后加:
```python
        aqid = (af or {}).get("artist_qid")
        if aqid:
            o.attributes = {**(o.attributes or {}), "artist_qid": aqid}
            db.flush()
            from app.models.artist import Artist

            art = db.query(Artist).filter_by(qid=aqid).first()
            if art is None or (force and not getattr(art, "_touched", False)):
                bio_en = enricher.generate_artist_bio(o.attributes) if hasattr(enricher, "generate_artist_bio") else None
                bios = {"en": bio_en} if bio_en else {}
                if bio_en:
                    for lang in target_langs:
                        if lang != "en":
                            bios[lang] = translator.translate_section(bio_en, lang)
                if art is None:
                    art = Artist(qid=aqid)
                    db.add(art)
                art.name_zh = o.artist_zh; art.name_en = o.artist_en
                art.birth = af.get("artist_birth"); art.death = af.get("artist_death")
                art.nationality = af.get("artist_nationality"); art.notable_works = af.get("artist_notable_works")
                if bios:
                    art.bio = bios
                db.flush()
```
（`force` 时也只在 Artist 不存在或本次未更新时生成一次——同一次 run 内不重复;跨 run 复用已存的。测试用 calls["n"]==1 验证。）

并加 **title_zh 补全**（generate_object 靠前,拿到 obj 后）:
```python
    if not o.title_zh and o.title_en and hasattr(translator, "translate_section"):
        try:
            o.title_zh = translator.translate_section(o.title_en, "zh"); db.flush()
        except Exception:
            pass
```

- [ ] **Step 4: 通过(含既有) + 提交**

Run: `cd backend && python -m pytest tests/integration/test_generate_pipeline.py -q`（全 PASS）
```bash
cd backend && git add app/services/enrichment/pipeline.py tests/integration/test_generate_pipeline.py
git commit -m "feat(artist): pipeline 生成/复用 Artist 实体 + 存 artist_qid + 补 title_zh"
```

---

### Task 6: get_object_content — 作者卡从 artists 表 + status 按语言判

**Files:**
- Modify: `backend/app/services/museum_repo.py`
- Test: `backend/tests/integration/test_pack_and_content_facts.py`

参考:现 artist 卡从 attrs/artist 段组装(Task 之前);`_pick`;返回 dict 的 `status`。

- [ ] **Step 1: 写失败测试**

```python
def test_artist_card_from_artists_table(session):
    from app.models.artist import Artist
    from app.models.museum_object import MuseumObject
    from app.services.museum_repo import get_object_content

    o = session.query(MuseumObject).filter_by(qid="Q1").one()
    o.attributes = {"artist_qid": "Q296"}
    session.add(Artist(qid="Q296", name_zh="梵高", name_en="Van Gogh", birth="1853",
                       nationality="Netherlands", notable_works=["Starry Night"], bio={"zh": "梵高生平。"}))
    session.commit()
    a = get_object_content(session, "orsay", "Q1", "zh")["artist"]
    assert a["name"] == "梵高" and a["birth"] == "1853" and a["bio"] == "梵高生平。"
    assert a["notable_works"] == ["Starry Night"]


def test_status_empty_when_language_has_no_content(session):
    from app.services.museum_repo import get_object_content

    d = get_object_content(session, "orsay", "Q1", "fr")  # fr 无 guide 无 tab
    assert d["status"] == "empty"
```

（`Artist` 表需在该文件 fixture 建表——在 `session` fixture 的 `create_all(tables=[...])` 加 `Artist.__table__`。）

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && python -m pytest tests/integration/test_pack_and_content_facts.py::test_artist_card_from_artists_table -q`
Expected: FAIL

- [ ] **Step 3: 实现** —
(a) fixture `create_all` 加 `Artist.__table__`。
(b) `get_object_content` 作者卡改从 artists 表:
```python
    from app.models.artist import Artist

    aqid = attrs.get("artist_qid")
    art = db.query(Artist).filter_by(qid=aqid).first() if aqid else None
    artist_card = {
        "name": _pick(language, (art.name_zh if art else None) or obj.artist_zh,
                      (art.name_en if art else None) or obj.artist_en, attrs.get("artist_fr")),
        "birth": art.birth if art else None,
        "death": art.death if art else None,
        "nationality": art.nationality if art else None,
        "notable_works": (art.notable_works if art else None) or [],
        "bio": (art.bio or {}).get(language) if art else None,
    }
```
（移除旧的从 artist 段/attrs 读的逻辑。）
(c) status 按语言判:在返回前,若无 guide 正文且 tabs 为空 → status="empty":
```python
    eff_status = obj.content_status
    if not (guide_body and guide_body.strip()) and not tabs:
        eff_status = "empty"
```
（`guide_body` = guide_row.body;返回 dict 的 `"status": eff_status`。）

- [ ] **Step 4: 通过(含既有 facts/guide/tabs 用例) + 提交**

Run: `cd backend && python -m pytest tests/integration/test_pack_and_content_facts.py tests/integration/test_museum_repo.py tests/integration/test_object_content_endpoint.py -q -W ignore::PendingDeprecationWarning`（全 PASS;既有作者卡用例改为建 Artist 行）
```bash
cd backend && git add app/services/museum_repo.py tests/integration/test_pack_and_content_facts.py
git commit -m "feat(artist): get_object_content 作者卡从 artists 表 + status 按语言判空"
```

---

### Task 7: 全量回归 + 回写主文档

**Files:**
- Modify: `docs/architecture/museum-api-contract.md`

- [ ] **Step 1: 全量回归**

Run: `cd backend && python -m pytest tests/ -q -W ignore::PendingDeprecationWarning 2>&1 | tail -20`
Expected: PASS（无回归；关注 test_generate_pipeline / museum_repo / material / category_config / seed）

- [ ] **Step 2: 回写主文档** — ① 作者卡说明:数据来自 `artists` 一等实体(按 artist QID 生成一次、同作者复用),artist 不再是 per-work 段;② status 按语言可返 empty;③ 中文标题缺失时生成补;④ 变更记录加一行。

- [ ] **Step 3: 提交**

```bash
cd /Users/hongyang/Projects/GoMuseum && git add docs/architecture/museum-api-contract.md
git commit -m "docs(api): 回写作者一等实体 + 状态按语言 + 中文名补全"
```

---

## Self-Review

- **Spec 覆盖**:Artist 模型+迁移(T1)✓ artist_qid(T2)✓ generate_artist_bio(T3)✓ artist 退出段(T4)✓ pipeline 生成/复用+title_zh(T5)✓ 作者卡从表+status(T6)✓ 回写(T7)✓。
- **复用**:Artist 存在则不重生成(T5 calls==1)。
- **向后兼容**:作者卡 shape 不变;无 Artist 行→回退 name;一个建表迁移;artist_qid 用 attributes 无列迁移。
- **类型一致**:`fetch_artist_facts`→`artist_qid`(T2)→pipeline 存/查 Artist(T5)→作者卡读 Artist(T6);`generate_artist_bio(artist_obj)->str|None`(T3 定义,T5 调)。

## 上线验证(合 staging 后)

1. 重生成星夜(梵高)+ 另一件梵高作品 → 二者作者卡**bio 一致且完整**;DB `artists` 有 Q296 一行。
2. 冷门件 → 有中文标题(title_zh 补了);La Guerre → status=empty(前端显待完善)。
3. 自动体检 15+ 件契约仍全过。
