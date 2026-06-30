# 作者卡(结构化必选)Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `get_object_content` 增一个**必选常驻**的 `artist` 卡片(生卒/国籍/代表作 from 作者 Wikidata 实体 + 复用 artist 段叙事为 bio);artist 段移出 tabs。

**Architecture:** 新 `fetch_artist_facts`(独立 SPARQL,注入式)抓 P569/P570/P27/P800 → 落 attributes;`get_object_content` 组装 artist 卡 + artist 段移出 tabs。无迁移。spec `2026-06-30-artist-card-design.md`。

**Tech Stack:** Python + pytest;注入式 run_query,离线可测。

> 命令在 `backend/` 下跑。

---

### Task 1: fetch_artist_facts(作者结构化属性)

**Files:**
- Modify: `backend/app/services/enrichment/material.py`
- Test: `backend/tests/unit/services/enrichment/test_artist_material.py`(若无则 `test_material.py`,按实际存在的作者测试文件)

参考:`material.py` 的 `fetch_artist_material(qid, registry, *, run_query, country_lang)`、`_default_artist_query(sparql)`、`_wd.SPARQL_ENDPOINT`/`USER_AGENT`。

- [ ] **Step 1: 写失败测试** — 加(放与作者材料同一测试文件):

```python
def test_fetch_artist_facts_parses_structured():
    from app.services.enrichment.material import fetch_artist_facts

    def fake(sparql):
        return [
            {"birth": {"value": "1832-01-23T00:00:00Z"}, "death": {"value": "1883-04-30T00:00:00Z"},
             "natLabel": {"value": "France"}, "workLabel": {"value": "Olympia"}},
            {"natLabel": {"value": "France"}, "workLabel": {"value": "The Fifer"}},
            {"natLabel": {"value": "France"}, "workLabel": {"value": "Olympia"}},  # 重复
        ]

    f = fetch_artist_facts("Q1", run_query=fake)
    assert f["artist_birth"] == "1832" and f["artist_death"] == "1883"
    assert f["artist_nationality"] == "France"
    assert f["artist_notable_works"] == ["Olympia", "The Fifer"]  # 去重保序


def test_fetch_artist_facts_empty_on_no_rows():
    from app.services.enrichment.material import fetch_artist_facts
    assert fetch_artist_facts("Q1", run_query=lambda s: []) == {}
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && python -m pytest tests/unit/services/enrichment/test_artist_material.py -q`（无 fetch_artist_facts → FAIL;若文件名不同,用实际作者测试文件路径）
Expected: FAIL

- [ ] **Step 3: 实现** — `material.py` 加:

```python
_ARTIST_FACTS_QUERY = """
SELECT ?birth ?death ?natLabel ?workLabel WHERE {{
  wd:{qid} wdt:P170 ?artist .
  OPTIONAL {{ ?artist wdt:P569 ?birth. }}
  OPTIONAL {{ ?artist wdt:P570 ?death. }}
  OPTIONAL {{ ?artist wdt:P27 ?nat. }}
  OPTIONAL {{ ?artist wdt:P800 ?work. }}
  SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
}}
"""


def fetch_artist_facts(qid, *, run_query=None) -> dict:
    """作者 Wikidata 实体结构化属性 → {artist_birth/death/nationality/notable_works}。无→{}。"""
    run_query = run_query or _default_artist_query
    rows = run_query(_ARTIST_FACTS_QUERY.format(qid=qid))
    if not rows:
        return {}
    out = {}
    works = []
    for row in rows:
        b = (row.get("birth") or {}).get("value")
        d = (row.get("death") or {}).get("value")
        nat = (row.get("natLabel") or {}).get("value")
        w = (row.get("workLabel") or {}).get("value")
        if b and "artist_birth" not in out:
            out["artist_birth"] = b[:4]
        if d and "artist_death" not in out:
            out["artist_death"] = d[:4]
        if nat and "artist_nationality" not in out:
            out["artist_nationality"] = nat
        if w and w not in works:
            works.append(w)
    if works:
        out["artist_notable_works"] = works[:5]
    return out
```

- [ ] **Step 4: 通过 + 提交**

Run: `cd backend && python -m pytest tests/unit/services/enrichment/test_artist_material.py -q`（PASS）
```bash
cd backend && git add app/services/enrichment/material.py tests/unit/services/enrichment/test_artist_material.py
git commit -m "feat(artist): fetch_artist_facts 抓作者生卒/国籍/代表作"
```

---

### Task 2: pipeline 落作者结构化属性

**Files:**
- Modify: `backend/app/services/enrichment/pipeline.py`
- Test: `backend/tests/integration/test_generate_pipeline.py`

参考:`generate_object` 现有 `if registry is not None:` 块里调 `fetch_artist_material(o.qid, registry, country_lang="fr")` 并 `o.attributes = {**(o.attributes or {}), **artist_mat}`。

- [ ] **Step 1: 写失败测试** — 追加(用 monkeypatch 让 fetch_artist_facts 返固定值,验证并入 attributes;registry 传一个非 None 的桩):

```python
def test_generate_object_stores_artist_facts(session, monkeypatch):
    import app.services.enrichment.pipeline as pl
    from app.models.museum_object import MuseumObject
    from app.services.enrichment.pipeline import generate_object

    monkeypatch.setattr(pl, "_artist_facts", lambda qid: {"artist_birth": "1832", "artist_nationality": "France"})

    generate_object(session, "Q1", enricher=_FakeEnricher(), gate=_FakeGate(),
                    translator=_FakeTranslator(), target_langs=["en"], model="m",
                    registry=object())  # 非 None 触发作者块
    o = session.query(MuseumObject).filter_by(qid="Q1").one()
    assert o.attributes.get("artist_birth") == "1832"
```

> 注:为可注入,pipeline 内用一个薄包装 `_artist_facts(qid)` 调 `fetch_artist_facts`;测试 monkeypatch 它,避免真实网络 + 避免依赖 registry 内部。

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && python -m pytest tests/integration/test_generate_pipeline.py::test_generate_object_stores_artist_facts -q`
Expected: FAIL

- [ ] **Step 3: 实现** — 在 `pipeline.py`:
(a) 加薄包装(顶部）:
```python
def _artist_facts(qid):
    from app.services.enrichment.material import fetch_artist_facts

    return fetch_artist_facts(qid)
```
(b) 在 `generate_object` 现有作者材料块(registry 门控)里,`fetch_artist_material` 之后加:
```python
        try:
            af = _artist_facts(o.qid)
        except Exception:
            af = {}
        if af:
            o.attributes = {**(o.attributes or {}), **af}
            db.flush()
```

- [ ] **Step 4: 通过(含原有用例) + 提交**

Run: `cd backend && python -m pytest tests/integration/test_generate_pipeline.py -q`（全 PASS）
```bash
cd backend && git add app/services/enrichment/pipeline.py tests/integration/test_generate_pipeline.py
git commit -m "feat(artist): generate_object 落作者结构化属性(registry门控)"
```

---

### Task 3: get_object_content 增 artist 卡 + artist 移出 tabs

**Files:**
- Modify: `backend/app/services/museum_repo.py`
- Test: `backend/tests/integration/test_pack_and_content_facts.py`

参考:`get_object_content` 现 tabs 来自 category_sections join;`default_guide`/guide 段是单独读、不入 tabs 的范例;`_pick(language, ...)`。

- [ ] **Step 1: 写失败测试** — 追加:

```python
def test_content_artist_card(session):
    from app.models.content import ObjectContentSection
    from app.models.museum_object import MuseumObject
    from app.services.museum_repo import get_object_content

    o = session.query(MuseumObject).filter_by(qid="Q1").one()
    o.artist_zh = "马奈"
    o.attributes = {
        "artist_birth": "1832", "artist_death": "1883",
        "artist_nationality": "France", "artist_notable_works": ["Olympia"],
    }
    session.add(ObjectContentSection(object_id=o.id, language="zh", section_code="artist",
                                     body="马奈生平叙事。", status="published"))
    session.commit()
    d = get_object_content(session, "orsay", "Q1", "zh")
    a = d["artist"]
    assert a["name"] == "马奈" and a["birth"] == "1832" and a["death"] == "1883"
    assert a["nationality"] == "France" and a["notable_works"] == ["Olympia"]
    assert a["bio"] == "马奈生平叙事。"
    # artist 段不在 tabs
    assert all(t["section_code"] != "artist" for t in d["tabs"])


def test_content_artist_card_present_when_thin(session):
    # 缺结构化 + 缺 bio,artist 卡仍返(name 兜底)
    from app.models.museum_object import MuseumObject
    from app.services.museum_repo import get_object_content

    o = session.query(MuseumObject).filter_by(qid="Q1").one()
    o.attributes = {}
    session.commit()
    d = get_object_content(session, "orsay", "Q1", "zh")
    assert "artist" in d and "name" in d["artist"]
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && python -m pytest tests/integration/test_pack_and_content_facts.py::test_content_artist_card -q`
Expected: FAIL

- [ ] **Step 3: 实现** — 在 `get_object_content`:
(a) 读 artist 段正文(镜像 guide 段读法):
```python
    artist_row = (
        db.query(ObjectContentSection)
        .filter_by(object_id=obj.id, language=language, section_code="artist", status="published")
        .first()
    )
```
(b) 组装 artist 卡:
```python
    artist_card = {
        "name": _pick(language, obj.artist_zh, obj.artist_en, attrs.get("artist_fr")),
        "birth": attrs.get("artist_birth"),
        "death": attrs.get("artist_death"),
        "nationality": attrs.get("artist_nationality"),
        "notable_works": attrs.get("artist_notable_works") or [],
        "bio": artist_row.body if artist_row else None,
    }
```
   放进返回 dict:`"artist": artist_card`。
(c) tabs 组装处**排除 artist**(同 guide 排除法):tabs 列表过滤掉 `section_code == "artist"`。

- [ ] **Step 4: 通过(含既有 tabs/facts/guide 用例) + 提交**

Run: `cd backend && python -m pytest tests/integration/test_pack_and_content_facts.py tests/integration/test_museum_repo.py -q`（全 PASS;既有断言 tabs 含 artist 的需同步改）
```bash
cd backend && git add app/services/museum_repo.py tests/integration/test_pack_and_content_facts.py
git commit -m "feat(artist): get_object_content 增 artist 卡 + artist 段移出 tabs"
```

---

### Task 4: 全量回归 + 契约回写 + 前端交接

**Files:**
- Modify: `docs/architecture/museum-api-contract.md`
- Create: `docs/handoff/2026-06-30-artist-card-frontend.md`

- [ ] **Step 1: 全量回归**

Run: `cd backend && python -m pytest tests/unit/services/enrichment/ tests/integration/test_generate_pipeline.py tests/integration/test_pack_and_content_facts.py tests/integration/test_museum_repo.py -q`
Expected: PASS

- [ ] **Step 2: 回写主文档** — 端点4 加 `artist` 卡字段说明(name/birth/death/nationality/notable_works/bio,必选常驻;artist 段移出 tabs);内容体系标注作者卡;变更记录加一行。

- [ ] **Step 3: 前端交接** — `docs/handoff/2026-06-30-artist-card-frontend.md`:导览页固定展示作者卡(姓名/生卒年/国籍/代表作/经历),常驻不随空隐;artist 不再在 tabs;`notable_works`/`nationality` v1 为 en(已知限制)。

- [ ] **Step 4: 提交**

```bash
cd /Users/hongyang/Projects/GoMuseum && git add docs/architecture/museum-api-contract.md docs/handoff/2026-06-30-artist-card-frontend.md
git commit -m "docs(api): 回写作者卡契约 + 前端交接"
```

---

## Self-Review

- **Spec 覆盖**:fetch_artist_facts(T1)✓ pipeline 落库(T2)✓ artist 卡 + 移出 tabs(T3)✓ 回写+交接(T4)✓。
- **必选常驻**:artist 卡总返(name 兜底),不随动态隐(T3 测试 present_when_thin)。
- **向后兼容**:artist 卡加法;artist 移出 tabs(老前端少个 tab,内容进卡);无迁移。
- **健壮**:fetch_artist_facts 空/失败→{};pipeline try/except;registry 门控测试离线。
- **类型一致**:`fetch_artist_facts(qid,*,run_query)->dict`(T1 定义,T2 经 `_artist_facts` 包装调用);artist 卡字段(T3 定义)= 契约(T4 回写)。

## 上线验证(合 staging 后)

1. 重生成几件(registry 在 → 抓作者 facts):`generate --qid <q> --target staging --langs zh --force`。
2. curl content → `artist` 卡含生卒/国籍/代表作/bio;artist 不在 tabs。
3. 前端接卡后 APK 看作者卡常驻展示。
