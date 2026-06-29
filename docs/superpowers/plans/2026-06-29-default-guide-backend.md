# 默认标准讲解(阶段1 后端)Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 后端产出「默认标准讲解」(`default_guide`,单主线·5拍·长度分级)供前端分层导览页(PR #92,已容错)消费;并加作者实体材料修"作者拍空"。

**Architecture:** 复用现有生成/三类闸/翻译。默认讲解 = 一次独立生成 → 三类闸 → 落 `section_code="guide"` → 翻译;`get_object_content` 把 guide 段抽成顶层 `default_guide`。作者材料 = 生成时临时查 Wikidata(作品→P170→作者维基标题)再抓作者 Wikipedia,**只动 material.py**(不碰 catalog/loader)。纯加法、无迁移。spec `docs/superpowers/specs/2026-06-28-guide-system-redesign-design.md`。

**Tech Stack:** Python + pytest;注入式 complete,离线可测。

**顺序**:Task 1-5 = 默认讲解核心(解锁前端);Task 6-7 = 作者材料(增强)。

---

## File Structure

- **Modify** `backend/app/services/enrichment/category_config.py` — `GUIDE_KEY_THRESHOLD` + `guide_target_chars(popularity)`。
- **Modify** `backend/app/services/enrichment/prompts.py` — `build_default_guide_prompt`。
- **Modify** `backend/app/services/enrichment/content_enricher.py` — `generate_default_guide` + build_material 纳入 `artist_extract_*`。
- **Modify** `backend/app/services/enrichment/pipeline.py` — generate_object 增产 guide 段。
- **Modify** `backend/app/services/enrichment/material.py` — `fetch_artist_material` + 接入 fetch_object_material。
- **Modify** `backend/app/services/museum_repo.py` — get_object_content 加 `default_guide`。
- **Modify** `backend/docs/architecture/museum-api-contract.md`（在仓库根 `docs/architecture/`）— 补 default_guide。

测试:`test_prompts.py`、`test_content_enricher.py`、`test_default_guide.py`(新)、`test_generate_pipeline.py`、`test_material.py`、`test_pack_and_content_facts.py`。

> 命令在 `backend/` 下跑。

---

### Task 1: 长度分级配置

**Files:**
- Modify: `backend/app/services/enrichment/category_config.py`
- Test: `backend/tests/unit/services/enrichment/test_category_config.py`

- [ ] **Step 1: 写失败测试**

```python
def test_guide_target_chars_tiers():
    from app.services.enrichment.category_config import guide_target_chars

    lo, hi = guide_target_chars(5)      # 普通件
    assert (lo, hi) == (270, 420)
    lo2, hi2 = guide_target_chars(50)   # 重点件(>=阈值)
    assert (lo2, hi2) == (420, 675)
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && python -m pytest tests/unit/services/enrichment/test_category_config.py::test_guide_target_chars_tiers -q`
Expected: FAIL

- [ ] **Step 3: 实现** — 在 `category_config.py` 末尾加:

```python
# 默认讲解长度档（中文字，已×1.5）。重点件 = popularity>=阈值。spec §3.1。
GUIDE_KEY_THRESHOLD = 30


def guide_target_chars(popularity: int | None) -> tuple[int, int]:
    if (popularity or 0) >= GUIDE_KEY_THRESHOLD:
        return (420, 675)
    return (270, 420)
```

- [ ] **Step 4: 通过 + 提交**

Run: `cd backend && python -m pytest tests/unit/services/enrichment/test_category_config.py -q` → PASS
```bash
cd backend && git add app/services/enrichment/category_config.py tests/unit/services/enrichment/test_category_config.py
git commit -m "feat(guide): 默认讲解长度分级配置(普通/重点·×1.5)"
```

---

### Task 2: 默认讲解 prompt

**Files:**
- Modify: `backend/app/services/enrichment/prompts.py`
- Test: `backend/tests/unit/services/enrichment/test_prompts.py`

- [ ] **Step 1: 写失败测试**

```python
from app.services.enrichment.prompts import build_default_guide_prompt


def test_default_guide_prompt_five_beats_single_throughline():
    system, user = build_default_guide_prompt("MAT", "FACTS", (270, 420))
    blob = (system + user).lower()
    assert "one" in blob and ("throughline" in blob or "core point" in blob or "single" in blob)
    # 5拍结构关键词
    assert "notice" in blob or "look" in blob          # 引导观察
    assert "remember" in blob or "memory" in blob or "question" in blob  # 记忆点/开放问题
    assert "270" in user and "420" in user             # 长度目标
    assert "do not invent" in blob or "not in the material" in blob  # 接地铁律
    assert "headline" in blob or "more content" in blob or "don't cover everything" in blob  # 去重提示
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && python -m pytest tests/unit/services/enrichment/test_prompts.py::test_default_guide_prompt_five_beats_single_throughline -q`
Expected: FAIL

- [ ] **Step 3: 实现** — 在 `prompts.py` 加:

```python
_DEFAULT_GUIDE_SYSTEM = (
    "You are a museum audio-guide writer. Write ONE short spoken on-site guide for a visitor "
    "standing in front of the artwork, built around a SINGLE core point (one throughline) — "
    "not a summary of everything. Structure (5 beats, flowing, not labeled): "
    "(1) a hook that gets them looking; (2) guide them to NOTICE 1-2 concrete details; "
    "(3) explain why those details matter; (4) add only the necessary background; "
    "(5) end on a memory point or an open question. "
    "Voice: colloquial, second-person, vivid storytelling that makes facts come alive "
    "(a great popular-history narrator). You MAY freely use framing/second-person guidance "
    "and gentle impressions clearly phrased as impression. You MUST NOT invent verifiable "
    "facts (names, dates, events, attributions, medium, what is depicted) not in the material. "
    "This is the HEADLINE; deep modules cover the rest, so DON'T try to cover everything. "
    "Write in English, ONE continuous narration. Return ONLY the text, no commentary, no quotes."
)


def build_default_guide_prompt(material: str, facts: str, target_chars: tuple[int, int]):
    lo, hi = target_chars
    user = (
        f"Target length: ~{lo}-{hi} Chinese-character equivalent (a target, not a hard limit; "
        f"shorter is fine if material is thin).\n\n"
        f"Key facts:\n{facts}\n\nMaterial:\n{material}"
    )
    return _DEFAULT_GUIDE_SYSTEM, user
```

- [ ] **Step 4: 通过 + 提交**

Run: `cd backend && python -m pytest tests/unit/services/enrichment/test_prompts.py -q` → PASS
```bash
cd backend && git add app/services/enrichment/prompts.py tests/unit/services/enrichment/test_prompts.py
git commit -m "feat(guide): build_default_guide_prompt(单主线·5拍·长度·去重提示)"
```

---

### Task 3: generate_default_guide

**Files:**
- Modify: `backend/app/services/enrichment/content_enricher.py`
- Test: `backend/tests/unit/services/enrichment/test_content_enricher.py`

参考既有:`ContentEnricher.__init__(self, complete)`;`build_material(obj)`;`generate_canonical` 用 `self._complete(system,user)`。

- [ ] **Step 1: 写失败测试**

```python
def test_generate_default_guide_returns_text_with_length_target():
    from app.services.enrichment.content_enricher import ContentEnricher

    captured = {}

    def fake(system, user):
        captured["user"] = user
        return "A single-throughline guide. Notice the eyes. Remember this."

    enr = ContentEnricher(complete=fake)
    out = enr.generate_default_guide(
        {"qid": "Q1", "title_en": "X", "category": "painting",
         "attributes": {"extract_en": "Foo."}},
        facts="- Title: X",
        target_chars=(270, 420),
    )
    assert "Notice the eyes" in out
    assert "270" in captured["user"] and "420" in captured["user"]


def test_generate_default_guide_empty_returns_none():
    from app.services.enrichment.content_enricher import ContentEnricher

    enr = ContentEnricher(complete=lambda s, u: "   ")
    assert enr.generate_default_guide(
        {"qid": "Q1", "category": "painting", "attributes": {}}, "", (270, 420)
    ) is None
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && python -m pytest tests/unit/services/enrichment/test_content_enricher.py -q`
Expected: FAIL（无 generate_default_guide）

- [ ] **Step 3: 实现** — 在 `content_enricher.py` 顶部 import 区加 `from app.services.enrichment.prompts import build_default_guide_prompt`(与既有 import 并列);在 `ContentEnricher` 加方法:

```python
    def generate_default_guide(self, obj: dict, facts: str, target_chars) -> str | None:
        """单主线默认讲解(纯文本)。空串→None。"""
        material = build_material(obj)
        system, user = build_default_guide_prompt(material, facts, target_chars)
        raw = self._complete(system, user)
        text = raw.strip() if isinstance(raw, str) else ""
        return text or None
```

- [ ] **Step 4: 通过 + 提交**

Run: `cd backend && python -m pytest tests/unit/services/enrichment/test_content_enricher.py -q` → PASS
```bash
cd backend && git add app/services/enrichment/content_enricher.py tests/unit/services/enrichment/test_content_enricher.py
git commit -m "feat(guide): ContentEnricher.generate_default_guide"
```

---

### Task 4: pipeline 增产 guide 段(三类闸 + 翻译)

**Files:**
- Modify: `backend/app/services/enrichment/pipeline.py`
- Test: `backend/tests/integration/test_generate_pipeline.py`

参考既有 `generate_object`:`obj=_row_to_obj(o)`、`material=build_material(obj)`、`facts=_facts_text(obj)`;`gate.check_section(material,facts,body)->SectionQuality`;`persist_gated_sections(db,qid,lang,{code:SQ},model)`;`translator.translate_object({code:body}, langs)->{lang:{code:SQ}}`。`enricher` 注入。

- [ ] **Step 1: 写失败测试**（复用文件内 session/_FakeEnricher/_FakeGate/_FakeTranslator;给 _FakeEnricher 加 generate_default_guide,_FakeTranslator 已译 overview→改造支持 guide）

```python
def test_generate_object_produces_guide_section(session):
    from app.models.content import ObjectContentSection
    from app.services.enrichment.pipeline import generate_object
    from app.services.enrichment.quality import SectionQuality

    class _GuideEnricher(_FakeEnricher):
        def generate_default_guide(self, obj, facts, target_chars):
            return "Guide hook. Notice the eyes."

    class _GuideGate(_FakeGate):
        def check_section(self, material, facts, body):
            return SectionQuality(body=body, status="published",
                                  grounding_ratio=1.0, conflicts=[], score=1.0)

    class _GuideTranslator(_FakeTranslator):
        def translate_object(self, en_sections, target_langs):
            return {"fr": {c: SectionQuality(body="FR " + b, status="published",
                    grounding_ratio=1.0, conflicts=[], score=1.0)
                    for c, b in en_sections.items()}}

    out = generate_object(
        session, "Q1", enricher=_GuideEnricher(), gate=_GuideGate(),
        translator=_GuideTranslator(), target_langs=["en", "fr"], model="m",
    )
    rows = {(r.language, r.section_code): r
            for r in session.query(ObjectContentSection).all()}
    assert rows[("en", "guide")].body == "Guide hook. Notice the eyes."
    assert rows[("fr", "guide")].body.startswith("FR ")
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && python -m pytest tests/integration/test_generate_pipeline.py::test_generate_object_produces_guide_section -q`
Expected: FAIL

- [ ] **Step 3: 实现** — 在 `pipeline.py` 顶部 import 区加 `from app.services.enrichment.category_config import guide_target_chars`。在 `generate_object` 里、英语段落落库之后(`pub_en, nr_en = ...` 与 content_status 流转附近)、翻译之前,插入 guide 生成与并入翻译集:

```python
    # 默认讲解(单主线):生成→三类闸→并入英语已发布集,随后统一翻译
    guide_text = (
        enricher.generate_default_guide(obj, facts, guide_target_chars(o.popularity))
        if hasattr(enricher, "generate_default_guide")
        else None
    )
    if guide_text:
        gq = gate.check_section(material, facts, guide_text)
        persist_gated_sections(db, qid, "en", {"guide": gq}, model)
        if gq.status == "published" and gq.body:
            en_published["guide"] = gq.body
```

> 注:`en_published` 是已有的「英语已发布段 dict」(`{code: body}`),`translator.translate_object(en_published, target_langs)` 已对它逐段翻译并 `persist_gated_sections` 落各语种——guide 段并入后**自动随其它段一起翻译落库**,无需额外翻译代码。确认 `en_published` 变量名与现有代码一致;若不同则对齐。

- [ ] **Step 4: 通过(含原有用例) + 提交**

Run: `cd backend && python -m pytest tests/integration/test_generate_pipeline.py -q` → PASS
```bash
cd backend && git add app/services/enrichment/pipeline.py tests/integration/test_generate_pipeline.py
git commit -m "feat(guide): generate_object 增产 default guide 段(三类闸+随段翻译)"
```

---

### Task 5: 契约 default_guide 字段

**Files:**
- Modify: `backend/app/services/museum_repo.py`
- Test: `backend/tests/integration/test_pack_and_content_facts.py`

参考既有 `get_object_content`:`tabs` 由 category mapping 逐段构建;返回 dict 含 tabs/suggested_questions/facts/...。`guide` 段不在 category mapping 里(它不是 6 模块之一),故需单独读取。

- [ ] **Step 1: 写失败测试**（在该文件 fixture 基础上为 Q1 落一个 guide 段）

```python
def test_content_returns_default_guide(session):
    from app.models.content import ObjectContentSection
    from app.services.museum_repo import get_object_content

    o = session.query(  # 取对象 id
        __import__("app.models.museum_object", fromlist=["MuseumObject"]).MuseumObject
    ).filter_by(qid="Q1").one()
    session.add(ObjectContentSection(
        object_id=o.id, language="zh", section_code="guide",
        body="单主线默认讲解。", status="published"))
    session.commit()
    d = get_object_content(session, "orsay", "Q1", "zh")
    assert d["default_guide"]["body"] == "单主线默认讲解。"
    assert "audio_url" in d["default_guide"]
    # guide 不混进 tabs
    assert all(t["section_code"] != "guide" for t in d["tabs"])


def test_content_default_guide_null_when_absent(session):
    from app.services.museum_repo import get_object_content
    d = get_object_content(session, "orsay", "Q1", "en")
    assert d["default_guide"] is None
```

> 注:`ObjectContentSection` 字段名以模型为准(body/status/section_code/language/object_id/audio_key)。若构造参数不符,按模型调整。

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && python -m pytest tests/integration/test_pack_and_content_facts.py -q`
Expected: FAIL（无 default_guide）

- [ ] **Step 3: 实现** — 在 `get_object_content` 的 `return {...}` 之前,加读取 guide 段(复用已查的 `storage`):

```python
    guide_row = (
        db.query(ObjectContentSection)
        .filter_by(object_id=obj.id, language=language, section_code="guide")
        .one_or_none()
    )
    default_guide = (
        {
            "body": guide_row.body,
            "audio_url": (
                storage.public_url(guide_row.audio_key)
                if guide_row.audio_key
                else None
            ),
        }
        if guide_row and guide_row.body
        else None
    )
```

并在返回 dict 加 `"default_guide": default_guide,`。**确认 `tabs` 构建不含 guide**:tabs 来自 category mapping(`CategorySection`),guide 不在其中,天然不混入——若实现里 tabs 改为"全部段落"则需显式排除 `section_code != "guide"`。

- [ ] **Step 4: 通过(含既有 facts 用例) + 提交**

Run: `cd backend && python -m pytest tests/integration/test_pack_and_content_facts.py -q` → PASS
```bash
cd backend && git add app/services/museum_repo.py tests/integration/test_pack_and_content_facts.py
git commit -m "feat(guide): get_object_content 加 default_guide 顶层字段"
```

---

### Task 6: 作者实体材料抓取

**Files:**
- Modify: `backend/app/services/enrichment/material.py`
- Test: `backend/tests/unit/services/enrichment/test_material.py`

参考既有 `material.fetch_object_material(qid, external_ids, wiki_titles, registry)`;`registry.get("wikipedia")` 返 WikipediaSource(其 `enrich(qid, ext, context)` 读 `context["wiki_titles"]` 抓 extract,产 `{extract_<lang>:...}`)。Wikidata SPARQL 端点见 `sources/wikidata.py`(`SPARQL_ENDPOINT`/`USER_AGENT`)。

- [ ] **Step 1: 写失败测试**

```python
def test_fetch_artist_material_via_injected_query():
    from app.services.enrichment.material import fetch_artist_material
    from app.services.enrichment.registry import SourceRegistry
    from app.services.enrichment.sources.base import ObjectContribution, Source

    # 假 Wikidata 查询:作品→作者维基标题
    def fake_run_query(sparql):
        return [{"al_en": {"value": "https://en.wikipedia.org/wiki/Gustave_Courbet"}}]

    class _Wiki(Source):
        name = "wikipedia"
        def fetch(self, cfg): return []
        def enrich(self, qid, ext, ctx):
            t = (ctx.get("wiki_titles") or {}).get("en")
            return ObjectContribution(source="wikipedia", qid=qid,
                fields={"extract_en": f"bio of {t}"}, raw={}) if t else None

    reg = SourceRegistry([_Wiki()])
    out = fetch_artist_material("Q1", reg, run_query=fake_run_query, country_lang="fr")
    assert out["artist_extract_en"] == "bio of Gustave_Courbet"


def test_fetch_artist_material_empty_when_no_artist():
    from app.services.enrichment.material import fetch_artist_material
    from app.services.enrichment.registry import SourceRegistry
    out = fetch_artist_material("Q1", SourceRegistry([]), run_query=lambda s: [], country_lang="fr")
    assert out == {}
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && python -m pytest tests/unit/services/enrichment/test_material.py::test_fetch_artist_material_via_injected_query -q`
Expected: FAIL

- [ ] **Step 3: 实现** — 在 `material.py` 加(SPARQL 取作品 P170 作者的 en + 馆所在国语维基标题):

```python
from app.services.enrichment.sources import wikidata as _wd

_ARTIST_QUERY = """
SELECT ?al_en ?al_cl WHERE {{
  wd:{qid} wdt:P170 ?artist .
  OPTIONAL {{ ?a_en schema:about ?artist ; schema:isPartOf <https://en.wikipedia.org/> ; schema:name ?al_en . }}
  OPTIONAL {{ ?a_cl schema:about ?artist ; schema:isPartOf <https://{cl}.wikipedia.org/> ; schema:name ?al_cl . }}
}} LIMIT 1
"""


def _default_artist_query(sparql):
    import requests

    r = requests.get(
        _wd.SPARQL_ENDPOINT,
        params={"query": sparql, "format": "json"},
        headers={"User-Agent": _wd.USER_AGENT, "Accept": "application/sparql-results+json"},
        timeout=60,
    )
    r.raise_for_status()
    return r.json()["results"]["bindings"]


def fetch_artist_material(qid, registry, *, run_query=None, country_lang="fr") -> dict:
    """抓作者实体 Wikipedia(作品→P170→作者维基标题→extract)。无作者/无维基→{}。"""
    run_query = run_query or _default_artist_query
    rows = run_query(_ARTIST_QUERY.format(qid=qid, cl=country_lang or "fr"))
    if not rows:
        return {}
    row = rows[0]
    titles = {}
    se = (row.get("al_en") or {}).get("value")
    if se:
        titles["en"] = se.rsplit("/", 1)[-1]
    scl = (row.get("al_cl") or {}).get("value")
    if scl:
        titles[country_lang or "fr"] = scl.rsplit("/", 1)[-1]
    if not titles:
        return {}
    wiki = registry.get("wikipedia")
    if wiki is None:
        return {}
    contrib = wiki.enrich(qid, {}, {"wiki_titles": titles})
    if contrib is None:
        return {}
    return {
        f"artist_{k}": v
        for k, v in contrib.fields.items()
        if k.startswith("extract_") and v
    }
```

- [ ] **Step 4: 通过 + 提交**

Run: `cd backend && python -m pytest tests/unit/services/enrichment/test_material.py -q` → PASS
```bash
cd backend && git add app/services/enrichment/material.py tests/unit/services/enrichment/test_material.py
git commit -m "feat(guide): fetch_artist_material 作者实体维基素材"
```

---

### Task 7: 作者材料接入 build_material + 生成

**Files:**
- Modify: `backend/app/services/enrichment/content_enricher.py`
- Modify: `backend/app/services/enrichment/pipeline.py`
- Test: `backend/tests/unit/services/enrichment/test_content_enricher.py`

- [ ] **Step 1: 写失败测试**（build_material 纳入 artist_extract_*）

```python
def test_build_material_includes_artist_extract():
    from app.services.enrichment.content_enricher import build_material
    mat = build_material({
        "qid": "Q1", "title_en": "X", "category": "painting",
        "attributes": {"artist_extract_en": "Courbet was a French realist painter."},
    })
    assert "Courbet was a French realist painter." in mat
    assert "ARTIST" in mat or "artist" in mat.lower()
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && python -m pytest tests/unit/services/enrichment/test_content_enricher.py::test_build_material_includes_artist_extract -q`
Expected: FAIL

- [ ] **Step 3a: build_material 加 artist 块** — 在 `content_enricher.build_material` 的 `extracts` 块之后加:

```python
    artist_extracts = {
        k: v for k, v in attrs.items() if k.startswith("artist_extract_") and v
    }
    if artist_extracts:
        lines.append("\n[ABOUT THE ARTIST]")
        for k, v in artist_extracts.items():
            lines.append(f"({k}) {v}")
```

- [ ] **Step 3b: pipeline 生成时抓作者材料并并入 attributes** — 在 `pipeline.generate_object` 里,stub 抓材料(`fetch_object_material`)之后、`obj = _row_to_obj(o)` 之前,加(registry 存在时):

```python
    if registry is not None:
        from app.services.enrichment.material import fetch_artist_material

        country_lang = "fr"  # 奥赛;多馆时从 museum cfg 取，本期默认 fr
        artist_mat = fetch_artist_material(o.qid, registry, country_lang=country_lang)
        if artist_mat:
            o.attributes = {**(o.attributes or {}), **artist_mat}
            db.flush()
```

> 注:与既有 stub 材料合并逻辑并列即可;`country_lang` 本期硬编 "fr"(奥赛),多馆时从馆配置取(留 `# ponytail:`)。

- [ ] **Step 4: 通过 + 全量回归 + 提交**

Run: `cd backend && python -m pytest tests/unit/services/enrichment/ tests/integration/test_generate_pipeline.py tests/integration/test_pack_and_content_facts.py -q`
Expected: PASS（无回归）
```bash
cd backend && git add app/services/enrichment/content_enricher.py app/services/enrichment/pipeline.py tests/unit/services/enrichment/test_content_enricher.py
git commit -m "feat(guide): 作者材料接入 build_material + 生成时抓取"
```

---

### Task 8: 契约文档更新

**Files:**
- Modify: `docs/architecture/museum-api-contract.md`

- [ ] **Step 1: 加字段说明** — 在端点 4(content)的响应里补 `default_guide: {body, audio_url}`(顶层、可为 null;= 单主线默认讲解;guide 段不混入 tabs)。变更记录追加一行。

- [ ] **Step 2: 提交**

```bash
cd /Users/hongyang/Projects/GoMuseum && git add docs/architecture/museum-api-contract.md
git commit -m "docs(api): 契约补 default_guide 字段"
```

---

## Self-Review

- **Spec 覆盖**:5拍单主线 prompt(T2)✓ 长度×1.5分级(T1)✓ generate_default_guide(T3)✓ guide 段三类闸+翻译(T4)✓ default_guide 契约(T5)✓ 作者实体材料(T6-7)✓ 契约文档(T8)✓。
- **解锁前端**:T1-5 即产出 `default_guide`,前端 PR#92 已容错消费。
- **复用不重造**:guide 走 check_section/persist_gated_sections/translate_object;作者材料复用 WikipediaSource;无新表、无迁移、纯加法。
- **ponytail**:作者材料只动 material.py+生成接线(不碰 catalog/loader/SPARQL 主干);country_lang 硬编 fr 标注升级路径。
- **类型一致**:`guide_target_chars(pop)->(lo,hi)`(T1 定义,T2/T4 用);`generate_default_guide(obj,facts,target_chars)`(T3 定义,T4 调);`fetch_artist_material(qid,registry,*,run_query,country_lang)`(T6 定义,T7 调)。

## 上线验证(合 staging 后)

1. staging 重生成几件(famous + 一件有作者维基的):`generate --qid <q> --target staging --langs zh,en,fr --force`。
2. `curl '.../objects/<q>/content?language=zh'` → `default_guide.body` 是单主线~300-600字、有看点引导;作者拍不空。
3. staging APK(前端分层页)看"主角"位呈现默认讲解。
4. 满意 → prod 重生成 TOP-N。
