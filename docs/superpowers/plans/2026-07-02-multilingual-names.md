# 多语显示名(语言无关)Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 显示名(title / artist.name)按请求语言解析:Wikidata 权威标签 → en 翻译兜底 → en 原名。语言无关(加语言=加配置)。

**Architecture:** 生成时抓 Wikidata 多语 labels 填 `title_i18n`(attributes)/`name_i18n`(Artist),缺则翻译;端点经 `resolve_name` 按语言取。spec `2026-07-02-multilingual-names-design.md`。规则已入主契约。

**Tech Stack:** Python + SQLAlchemy/Alembic + pytest。

> 命令在 `backend/` 下跑。alembic head = `j1g6_add_artists`。

---

### Task 1: Artist.name_i18n 列 + 迁移

**Files:**
- Modify: `backend/app/models/artist.py`
- Create: `backend/alembic/versions/k1h7_add_name_i18n.py`
- Test: `backend/tests/integration/test_artist_model.py`

参考:`artist.py` 的 `bio` 列(`MutableDict.as_mutable(JSON().with_variant(JSONB,"postgresql"))`,**每列内联** JSON 实例,别共享)。

- [ ] **Step 1: 写失败测试** — 追加:

```python
def test_artist_name_i18n_roundtrip():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool
    from app.core.database import Base
    from app.models.artist import Artist

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(bind=engine, tables=[Artist.__table__])
    s = sessionmaker(bind=engine)()
    s.add(Artist(qid="Q7", name_i18n={"en": "Sisley", "fr": "Sisley", "zh": "西斯莱"}))
    s.commit(); s.expire_all()
    assert s.query(Artist).filter_by(qid="Q7").one().name_i18n["zh"] == "西斯莱"
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && python -m pytest tests/integration/test_artist_model.py::test_artist_name_i18n_roundtrip -q`
Expected: FAIL

- [ ] **Step 3: 实现** —
(a) `artist.py` 加列(在 `bio` 附近,内联 JSON):
```python
    name_i18n = Column(
        MutableDict.as_mutable(JSON().with_variant(JSONB, "postgresql")), nullable=True
    )  # {lang: name} 多语显示名
```
(b) 迁移 `k1h7_add_name_i18n.py`(down_revision=`j1g6_add_artists`):
```python
"""add artists.name_i18n"""
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from alembic import op

revision = "k1h7_add_name_i18n"
down_revision = "j1g6_add_artists"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("artists", sa.Column("name_i18n", postgresql.JSONB(astext_type=sa.Text()), nullable=True))


def downgrade() -> None:
    op.drop_column("artists", "name_i18n")
```

- [ ] **Step 4: 通过 + 单 head + 提交**

Run: `cd backend && python -m pytest tests/integration/test_artist_model.py -q`（PASS）
Run: `cd backend && python -c "from alembic.config import Config; from alembic.script import ScriptDirectory; print(ScriptDirectory.from_config(Config('alembic.ini')).get_heads())"`（应 `['k1h7_add_name_i18n']`）
```bash
cd backend && git add app/models/artist.py alembic/versions/k1h7_add_name_i18n.py tests/integration/test_artist_model.py
git commit -m "feat(i18n): Artist.name_i18n 多语名字列 + 迁移"
```

---

### Task 2: fetch_wikidata_labels(抓多语标签)

**Files:**
- Modify: `backend/app/services/enrichment/material.py`
- Test: `backend/tests/unit/services/enrichment/test_material.py`

参考:`_default_run_query`/SPARQL 注入式模式;`_wd.SPARQL_ENDPOINT`。

- [ ] **Step 1: 写失败测试**

```python
def test_fetch_wikidata_labels():
    from app.services.enrichment.material import fetch_wikidata_labels

    def fake(sparql):
        return [
            {"l": {"value": "La Nuit étoilée", "xml:lang": "fr"}},
            {"l": {"value": "Starry Night", "xml:lang": "en"}},
        ]

    out = fetch_wikidata_labels("Q1", ["en", "fr", "de"], run_query=fake)
    assert out == {"fr": "La Nuit étoilée", "en": "Starry Night"}  # 只含 Wikidata 有的
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && python -m pytest tests/unit/services/enrichment/test_material.py::test_fetch_wikidata_labels -q`
Expected: FAIL

- [ ] **Step 3: 实现** — `material.py` 加:

```python
_LABELS_QUERY = """
SELECT ?l WHERE {{ wd:{qid} rdfs:label ?l . FILTER(lang(?l) IN ({langs})) }}
"""


def fetch_wikidata_labels(qid: str, langs: list, *, run_query=None) -> dict:
    """Wikidata 实体在 langs 的官方标签 → {lang: label}(只含有的)。"""
    run_query = run_query or _default_run_query
    langlist = ", ".join('"%s"' % x for x in langs)
    rows = run_query(_LABELS_QUERY.format(qid=qid, langs=langlist))
    out = {}
    for row in rows:
        lv = row.get("l") or {}
        lang = lv.get("xml:lang") or lv.get("lang")
        val = lv.get("value")
        if lang in langs and val and lang not in out:
            out[lang] = val
    return out
```

- [ ] **Step 4: 通过 + 提交**

Run: `cd backend && python -m pytest tests/unit/services/enrichment/test_material.py -q`（PASS）
```bash
cd backend && git add app/services/enrichment/material.py tests/unit/services/enrichment/test_material.py
git commit -m "feat(i18n): fetch_wikidata_labels 抓实体多语官方标签"
```

---

### Task 3: pipeline 填 title_i18n / name_i18n(权威 + 翻译兜底)

**Files:**
- Modify: `backend/app/services/enrichment/pipeline.py`
- Test: `backend/tests/integration/test_generate_pipeline.py`

参考:`generate_object` 的 registry 门控块、`target_langs`、`translator.translate_section`、Artist 创建段。加 `_wikidata_labels` 薄包装(测试 monkeypatch)。`DEFAULT_LANGUAGES` 来源:`from app.services.enrichment.translator import DEFAULT_LANGUAGES`(或按实际;测试用 target_langs)。

- [ ] **Step 1: 写失败测试**

```python
def test_generate_fills_title_and_artist_name_i18n(session, monkeypatch):
    import app.services.enrichment.pipeline as pl
    from app.models.artist import Artist
    from app.models.museum_object import MuseumObject
    from app.services.enrichment.pipeline import generate_object

    monkeypatch.setattr(pl, "_artist_facts", lambda qid: {"artist_qid": "Q7"})
    # work labels: fr 权威有、de 无(翻译兜底);artist labels: 都无(翻译兜底)
    monkeypatch.setattr(pl, "_wikidata_labels", lambda qid, langs: {"fr": "La Nuit"} if qid != "Q7" else {})

    class _Enr(_FakeEnricher):
        def generate_artist_bio(self, o): return "bio。"

    o = session.query(MuseumObject).filter_by(qid="Q1").one()
    o.title_en = "Starry Night"; o.artist_en = "Van Gogh"; o.attributes = {"artist_extract_en": "x"}
    session.commit()
    generate_object(session, "Q1", enricher=_Enr(), gate=_FakeGate(), translator=_FakeTranslator(),
                    target_langs=["en", "fr", "de"], model="m", registry=_FakeRegistry(), force=True)
    o2 = session.query(MuseumObject).filter_by(qid="Q1").one()
    ti = o2.attributes.get("title_i18n") or {}
    assert ti["fr"] == "La Nuit"  # 权威
    assert "Starry Night" in ti["de"]  # de 无权威 → 翻译兜底(_FakeTranslator 回显)
    ni = session.query(Artist).filter_by(qid="Q7").one().name_i18n or {}
    assert "Van Gogh" in ni["fr"]  # 作者无权威 → 翻译兜底
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && python -m pytest tests/integration/test_generate_pipeline.py::test_generate_fills_title_and_artist_name_i18n -q`
Expected: FAIL

- [ ] **Step 3: 实现** —
(a) 顶部薄包装:
```python
def _wikidata_labels(qid, langs):
    from app.services.enrichment.material import fetch_wikidata_labels

    return fetch_wikidata_labels(qid, langs)


def _fill_i18n(existing, en_name, labels, langs, translator):
    """权威标签优先,缺则从 en 翻译,en 兜底。返回 {lang: name}。"""
    out = dict(existing or {})
    out.setdefault("en", en_name)
    for lang in langs:
        if out.get(lang):
            continue
        if labels.get(lang):
            out[lang] = labels[lang]
        elif lang != "en" and en_name and hasattr(translator, "translate_section"):
            try:
                out[lang] = translator.translate_section(en_name, lang)
            except Exception:
                pass
    return out
```
(b) `generate_object` 的 registry 块里(拿到 target_langs 后):
- 标题:
```python
        try:
            wlabels = _wikidata_labels(o.qid, target_langs)
            ti = _fill_i18n(o.attributes.get("title_i18n"), o.title_en, wlabels, target_langs, translator)
            o.attributes = {**(o.attributes or {}), "title_i18n": ti}
            if ti.get("zh") and not o.title_zh:
                o.title_zh = ti["zh"]  # 回填列(兼容)
            db.flush()
        except Exception:
            pass
```
- 作者名:在 Artist 创建/更新段(`aqid` 那块)填 `name_i18n`:
```python
                try:
                    alabels = _wikidata_labels(aqid, target_langs)
                    art.name_i18n = _fill_i18n(art.name_i18n, o.artist_en, alabels, target_langs, translator)
                except Exception:
                    pass
```

- [ ] **Step 4: 通过(含既有) + 提交**

Run: `cd backend && python -m pytest tests/integration/test_generate_pipeline.py -q`（全 PASS）
```bash
cd backend && git add app/services/enrichment/pipeline.py tests/integration/test_generate_pipeline.py
git commit -m "feat(i18n): pipeline 填 title_i18n/name_i18n(Wikidata权威+翻译兜底,语言无关)"
```

---

### Task 4: resolve_name + 端点按语言取

**Files:**
- Modify: `backend/app/services/museum_repo.py`
- Test: `backend/tests/integration/test_pack_and_content_facts.py`、`test_list_objects.py`

参考:`get_object_content`(作者卡 name、title)、`list_objects`(title/artist per lang)、`get_museum_pack`(artworks title_zh/en)。`_pick` 现有。

- [ ] **Step 1: 写失败测试** — `test_pack_and_content_facts.py` 追加:

```python
def test_content_title_and_artist_resolve_by_language(session):
    from app.models.artist import Artist
    from app.models.museum_object import MuseumObject
    from app.services.museum_repo import get_object_content

    o = session.query(MuseumObject).filter_by(qid="Q1").one()
    o.title_en = "Starry Night"
    o.attributes = {"artist_qid": "Q7", "title_i18n": {"en": "Starry Night", "fr": "La Nuit étoilée"}}
    session.add(Artist(qid="Q7", name_en="Van Gogh", name_i18n={"en": "Van Gogh", "fr": "Van Gogh"}))
    session.commit()
    assert get_object_content(session, "orsay", "Q1", "fr")["title"] == "La Nuit étoilée"  # 法语权威
    assert get_object_content(session, "orsay", "Q1", "en")["title"] == "Starry Night"
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && python -m pytest tests/integration/test_pack_and_content_facts.py::test_content_title_and_artist_resolve_by_language -q`
Expected: FAIL

- [ ] **Step 3: 实现** —
(a) 加 helper:
```python
def _resolve_name(i18n, language, fallback_en):
    return (i18n or {}).get(language) or fallback_en
```
(b) `get_object_content`:
- title:`title = _resolve_name(attrs.get("title_i18n"), language, obj.title_en or obj.title_zh or obj.qid)`。
- 作者卡 name:`_resolve_name(art.name_i18n if art else None, language, (art.name_en if art else None) or obj.artist_en)`(替换现 `_pick`,避开 artist_fr 脏格式)。
(c) `list_objects` 的 `title`/`artist`、`get_museum_pack` 的 `artworks[].title_zh/en` 同样经 title_i18n 解析(title_zh 用 i18n.get("zh") 兜底回填;保持字段名不变)。

- [ ] **Step 4: 通过(含既有 list/pack/content 用例) + 提交**

Run: `cd backend && python -m pytest tests/integration/test_pack_and_content_facts.py tests/integration/test_list_objects.py tests/integration/test_museum_repo.py -q -W ignore::PendingDeprecationWarning`（全 PASS;既有断言按新解析更新并说明）
```bash
cd backend && git add app/services/museum_repo.py tests/integration/
git commit -m "feat(i18n): 端点 title/artist.name 经 resolve_name 按语言解析(避开脏格式)"
```

---

### Task 5: 全量回归 + 回写主文档字段说明

**Files:**
- Modify: `docs/architecture/museum-api-contract.md`

- [ ] **Step 1: 全量回归**

Run: `cd backend && python -m pytest tests/ -q -W ignore::PendingDeprecationWarning 2>&1 | tail -12`
Expected: PASS

- [ ] **Step 2: 回写** — 端点4 作者卡 + 端点2/3 title 说明:标注"按多语显示名规则解析(title_i18n / name_i18n:权威标签→翻译→en)";变更记录加一行。

- [ ] **Step 3: 提交**

```bash
cd /Users/hongyang/Projects/GoMuseum && git add docs/architecture/museum-api-contract.md
git commit -m "docs(api): 端点 title/artist.name 多语解析字段说明"
```

---

## Self-Review

- **Spec 覆盖**:name_i18n 列+迁移(T1)✓ fetch_wikidata_labels(T2)✓ pipeline 填 i18n(T3)✓ resolve_name 端点(T4)✓ 回写(T5)✓。
- **语言无关**:`_fill_i18n` 按 target_langs 循环,加语言只改 DEFAULT_LANGUAGES(spec §6)。
- **规则**:权威→翻译→en(_fill_i18n + resolve_name)。QID 匹配键不受影响。
- **向后兼容**:title_en/zh、name_en/zh 列保留;i18n 是新真相;端点字段名不变。一个加列迁移 + attributes(无迁移)。
- **类型一致**:`fetch_wikidata_labels(qid,langs,*,run_query)->dict`(T2)→ `_wikidata_labels`(T3)→ `_fill_i18n`(T3)→ `_resolve_name`(T4)。

## 上线验证(合 staging 后)

1. 三语重生成星夜 → fr title="La Nuit étoilée…"(法语权威,不再英文);冷门件 zh 有译名。
2. 作者名 fr 不再显 Joconde 脏格式"Sisley Alfred (1839-1899)"。
3. 自动体检:各语言 title/name 都在该语言、无空、无脏格式。
