# 博物馆介绍+封面 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 每馆一段 AI 生成接地介绍(`description_i18n`)+ 一张 LLM 得体性筛选的封面(`cover_image_key`),馆包出 `description`/`cover_image` 两个 null 安全字段;`onboard <slug> intro` 一步生成,上新馆自动有。

**Architecture:** 复用富化管线(QualityGate 接地校验 + ContentTranslator 补语种);新增馆级材料抓取(qid→sitelinks→en extract);封面=top-10 有图件逐件 LLM 文本判定。核心逻辑集中在新模块 `museum_intro.py`(全注入可测),onboard 只做 wiring。

**Tech Stack:** SQLAlchemy/alembic/pytest(sqlite StaticPool fixture)/requests。

## Global Constraints

- spec: `docs/superpowers/specs/2026-07-18-museum-intro-design.md`
- 幂等 = **按语言维度补缺**(en 在→只翻缺语;全齐跳过;`--force` 重生成);语言集 = `resolve_languages(cfg.languages)` 馆配置驱动,不硬编
- gate 不过 = 该语言不落库(无 needs_review 状态机);无材料 = skip(宁缺毋滥)
- 封面判定:古典/宗教/神话裸体可接受;写实露骨性描绘(《世界的起源》类)否决;判定失败**保守跳过该件**
- 不碰开放时间/票价;alembic down_revision = `p1m2`(执行前 `ls backend/alembic/versions` 再确认 head)
- black 格式化;测试 fixture 照 `tests/unit/services/test_museum_repo_coverage.py` 模式

---

### Task 1: 迁移 + Museum 模型两列

**Files:**
- Modify: `backend/app/models/museum.py`
- Create: `backend/alembic/versions/q1n3_add_museum_intro.py`

**Interfaces:**
- Produces: `Museum.description_i18n: JSON|None`、`Museum.cover_image_key: Text|None`

- [ ] **Step 1: 模型加列**(照 `stats` 列的写法,在 `stats` 列之后加)

```python
    description_i18n = Column(JSON, nullable=True)  # {lang: 叙事介绍};gate 通过才写
    cover_image_key = Column(Text, nullable=True)  # 封面(得体性筛选后固化的 R2 基础键)
```

(文件顶部 import 需含 `Text`:`from sqlalchemy import JSON, Column, DateTime, String, Text, func`)

- [ ] **Step 2: 迁移文件**

```python
# backend/alembic/versions/q1n3_add_museum_intro.py
"""museums 加 description_i18n(AI 接地介绍)+ cover_image_key(得体封面)。"""

import sqlalchemy as sa

from alembic import op

revision = "q1n3"
down_revision = "p1m2"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("museums", sa.Column("description_i18n", sa.JSON(), nullable=True))
    op.add_column("museums", sa.Column("cover_image_key", sa.Text(), nullable=True))


def downgrade():
    op.drop_column("museums", "cover_image_key")
    op.drop_column("museums", "description_i18n")
```

- [ ] **Step 3: 验证**(sqlite create_all 吃新列)

Run: `cd backend && python -c "
from sqlalchemy import create_engine
from app.core.database import Base
from app.models.museum import Museum
e = create_engine('sqlite://'); Base.metadata.create_all(e, tables=[Museum.__table__])
m = Museum(slug='x'); m.description_i18n = {'en': 'hi'}; m.cover_image_key = 'k'
print('ok')"`
Expected: `ok`

- [ ] **Step 4: Commit**

```bash
git add backend/app/models/museum.py backend/alembic/versions/q1n3_add_museum_intro.py
git commit -m "feat(museum): description_i18n + cover_image_key 两列(迁移 q1n3)"
```

### Task 2: 馆包 description + cover_image 字段

**Files:**
- Modify: `backend/app/services/museum_repo.py`(`get_museum_pack` 的 `pack.update` 处)
- Test: `backend/tests/integration/test_museum_pack_intro.py`(新)

**Interfaces:**
- Consumes: Task 1 两列;既有 `_sized(storage, key, "large")`、`get_object_storage`
- Produces: 馆包 `description: str|None`、`cover_image: str|None`

- [ ] **Step 1: 失败测试**

```python
# backend/tests/integration/test_museum_pack_intro.py
"""馆包 description(按语言解析+回退)与 cover_image(large 直链)——全 null 安全。"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.models.museum import Museum
from app.models.museum_object import MuseumObject, ObjectImage
from app.services import museum_repo
from app.services.object_importer import upsert_museum


@pytest.fixture()
def session(monkeypatch):
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(
        bind=engine,
        tables=[Museum.__table__, MuseumObject.__table__, ObjectImage.__table__],
    )
    s = sessionmaker(bind=engine)()
    upsert_museum(s, {"slug": "orsay", "name_en": "Orsay"})
    s.commit()

    class _Storage:
        def public_url(self, key):
            return f"https://r2/{key}"

    monkeypatch.setattr(museum_repo, "get_object_storage", lambda: _Storage())
    yield s


def test_pack_description_resolves_language_with_fallback(session):
    m = session.query(Museum).one()
    m.description_i18n = {"en": "EN intro.", "zh": "中文介绍。"}
    session.commit()
    assert museum_repo.get_museum_pack(session, "orsay", "zh")["description"] == "中文介绍。"
    assert museum_repo.get_museum_pack(session, "orsay", "ja")["description"] == "EN intro."  # 缺→en


def test_pack_description_and_cover_null_safe(session):
    pack = museum_repo.get_museum_pack(session, "orsay", "zh")
    assert pack["description"] is None
    assert pack["cover_image"] is None


def test_pack_cover_image_large_url(session):
    m = session.query(Museum).one()
    m.cover_image_key = "images/Q1/0"
    session.commit()
    pack = museum_repo.get_museum_pack(session, "orsay", "zh")
    assert pack["cover_image"] == "https://r2/images/Q1/0_large.jpg"
```

- [ ] **Step 2: 跑确认失败**(KeyError: 'description')

Run: `cd backend && python -m pytest tests/integration/test_museum_pack_intro.py -q --no-cov -p no:cacheprovider`

- [ ] **Step 3: 实现**(`get_museum_pack` 的 `pack.update({...})` 字典里加两项)

```python
            # 博物馆介绍(spec 2026-07-18):按语言解析,缺→en→任一→null;前端 as String? 容错
            "description": (
                (m.description_i18n or {}).get(language)
                or (m.description_i18n or {}).get("en")
                or next(iter((m.description_i18n or {}).values()), None)
            ),
            # 封面(得体性筛选后固化);large 档(hero 大图)
            "cover_image": (
                _sized(storage, m.cover_image_key, "large")
                if m.cover_image_key
                else None
            ),
```

- [ ] **Step 4: 跑测试通过 + 既有 pack 测试回归**

Run: `cd backend && python -m pytest tests/integration/test_museum_pack_intro.py tests/integration/test_museum_repo.py tests/unit/services/test_museum_repo_coverage.py -q --no-cov -p no:cacheprovider`
Expected: 全 passed

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/museum_repo.py backend/tests/integration/test_museum_pack_intro.py
git commit -m "feat(museum): 馆包加 description/cover_image 字段(按语言回退,null 安全)"
```

### Task 3: 馆级材料抓取 fetch_museum_intro_material

**Files:**
- Modify: `backend/app/services/enrichment/material.py`(文件末尾追加)
- Test: `backend/tests/unit/services/enrichment/test_material.py`(追加)

**Interfaces:**
- Produces: `fetch_museum_intro_material(qid: str, *, get_json=None) -> dict`,返回 `{"extract_en": str|None}`;`get_json(url, params) -> dict` 注入可测,None 时用 requests 真抓

- [ ] **Step 1: 失败测试**(追加到 test_material.py)

```python
def test_fetch_museum_intro_material_sitelink_then_extract():
    from app.services.enrichment.material import fetch_museum_intro_material

    calls = []

    def fake_get_json(url, params):
        calls.append(url)
        if "wikidata" in url:
            return {
                "entities": {
                    "Q23402": {"sitelinks": {"enwiki": {"title": "Musée d'Orsay"}}}
                }
            }
        return {"query": {"pages": {"1": {"extract": "The Musée d'Orsay is..."}}}}

    out = fetch_museum_intro_material("Q23402", get_json=fake_get_json)
    assert out["extract_en"].startswith("The Musée d'Orsay")
    assert any("wikidata" in u for u in calls) and any("wikipedia" in u for u in calls)


def test_fetch_museum_intro_material_no_sitelink():
    from app.services.enrichment.material import fetch_museum_intro_material

    out = fetch_museum_intro_material(
        "Q1", get_json=lambda u, p: {"entities": {"Q1": {"sitelinks": {}}}}
    )
    assert out["extract_en"] is None
```

- [ ] **Step 2: 跑确认失败**(ImportError)

- [ ] **Step 3: 实现**(material.py 末尾;UA 常量若文件内已有则复用)

```python
def fetch_museum_intro_material(qid: str, *, get_json=None) -> dict:
    """馆级接地材料(spec 2026-07-18):qid → enwiki sitelink → en 全文 extract。
    馆没有对象级 wiki_titles 管道,故独立小抓取。get_json 注入可测;失败返 extract_en=None
    (调用方宁缺毋滥 skip)。"""
    if get_json is None:
        import requests

        def get_json(url, params):
            r = requests.get(
                url,
                params=params,
                headers={"User-Agent": "GoMuseumBot/0.1 (contact appcraft008@gmail.com)"},
                timeout=30,
            )
            r.raise_for_status()
            return r.json()

    try:
        ent = get_json(
            "https://www.wikidata.org/w/api.php",
            {"action": "wbgetentities", "ids": qid, "props": "sitelinks", "format": "json"},
        )
        title = (
            ent.get("entities", {}).get(qid, {}).get("sitelinks", {}).get("enwiki", {})
        ).get("title")
        if not title:
            return {"extract_en": None}
        data = get_json(
            "https://en.wikipedia.org/w/api.php",
            {
                "action": "query",
                "prop": "extracts",
                "explaintext": 1,
                "format": "json",
                "titles": title,
            },
        )
        pages = data.get("query", {}).get("pages", {})
        extract = next(iter(pages.values()), {}).get("extract") or None
        return {"extract_en": extract[:8000] if extract else None}
    except Exception:
        return {"extract_en": None}
```

- [ ] **Step 4: 跑通过** `python -m pytest tests/unit/services/enrichment/test_material.py -q --no-cov -p no:cacheprovider`

- [ ] **Step 5: Commit** `git add ... && git commit -m "feat(enrichment): 馆级材料抓取(qid→sitelink→en extract)"`

### Task 4: prompts(介绍生成 + 封面得体性)

**Files:**
- Modify: `backend/app/services/enrichment/prompts.py`(末尾追加)
- Test: `backend/tests/unit/services/enrichment/test_prompts.py`(若无此文件则新建,只测这两个)

**Interfaces:**
- Produces: `build_museum_intro_prompt(name_en, material) -> (system, user)`;`build_cover_safety_prompt(title, artist, category) -> (system, user)`

- [ ] **Step 1: 失败测试**

```python
def test_build_museum_intro_prompt_grounded_no_logistics():
    from app.services.enrichment.prompts import build_museum_intro_prompt

    system, user = build_museum_intro_prompt("Musée d'Orsay", "MATERIAL TEXT")
    assert "Musée d'Orsay" in user and "MATERIAL TEXT" in user
    assert "opening hours" in system  # 明令禁止运营数据


def test_build_cover_safety_prompt_json_contract():
    from app.services.enrichment.prompts import build_cover_safety_prompt

    system, user = build_cover_safety_prompt("L'Origine du monde", "Courbet", "painting")
    assert "appropriate" in system and "Courbet" in user
```

- [ ] **Step 2: 跑确认失败** → **Step 3: 实现**(prompts.py 末尾)

```python
_MUSEUM_INTRO_SYSTEM = (
    "You write ONE engaging paragraph (~100-160 words) introducing a museum for an "
    "audio-guide app — the museum's history, identity, star works and style, in a warm "
    "spoken hook tone. Grounded STRICTLY in the provided MATERIAL — never invent facts; "
    "weave stable facts (founding year, building, collection era) into the narrative. "
    "Do NOT mention opening hours, ticket prices, or visitor logistics. Original wording "
    "— do not copy sentences from the source. Return ONLY the paragraph, no headings."
)


def build_museum_intro_prompt(name_en: str, material: str):
    return _MUSEUM_INTRO_SYSTEM, f"Museum: {name_en}\n\nMATERIAL:\n{material}"


_COVER_SAFETY_SYSTEM = (
    "You judge whether an artwork is appropriate as the PUBLIC COVER image of a museum "
    "app (family-friendly store listing). Classical, religious or mythological nudity "
    "is acceptable art convention. Explicit realistic sexual depiction (e.g. Courbet's "
    "L'Origine du monde) is NOT appropriate. Reply STRICT JSON: "
    '{"appropriate": true} or {"appropriate": false}.'
)


def build_cover_safety_prompt(title: str, artist: str | None, category: str | None):
    return (
        _COVER_SAFETY_SYSTEM,
        f"Title: {title}\nArtist: {artist or '?'}\nCategory: {category or '?'}",
    )
```

- [ ] **Step 4: 跑通过** → **Step 5: Commit** `git commit -m "feat(enrichment): 馆介绍生成+封面得体性判定 prompt"`

### Task 5: museum_intro 核心模块(生成/补缺/封面)

**Files:**
- Create: `backend/app/services/enrichment/museum_intro.py`
- Test: `backend/tests/integration/test_museum_intro.py`

**Interfaces:**
- Consumes: Task 1 两列、Task 3 `fetch_museum_intro_material`、Task 4 两 prompt、既有 `QualityGate.check_section(material, facts, body) -> SectionQuality`、`translator.translate_section(body, lang)`、`content_enricher._parse_json`
- Produces: `generate_museum_intro(db, slug, *, complete, gate, translator, langs, force=False, fetch_material=None) -> dict`(返回 `{"generated": bool, "translated": [langs], "skipped": str|None}`);`select_cover(db, slug, *, complete, force=False, limit=10) -> str|None`

- [ ] **Step 1: 失败测试**

```python
# backend/tests/integration/test_museum_intro.py
"""馆介绍生成:按语言幂等补缺/gate失败不落/无材料skip;封面:否决件跳过选下一件。"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.models.museum import Museum
from app.models.museum_object import MuseumObject, ObjectImage
from app.services.enrichment.museum_intro import generate_museum_intro, select_cover
from app.services.enrichment.quality import SectionQuality
from app.services.object_importer import upsert_museum, upsert_object


@pytest.fixture()
def session():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(
        bind=engine,
        tables=[Museum.__table__, MuseumObject.__table__, ObjectImage.__table__],
    )
    s = sessionmaker(bind=engine)()
    upsert_museum(s, {"slug": "orsay", "name_en": "Orsay", "qid": "Q23402"})
    s.commit()
    yield s


class _Gate:
    def __init__(self, ok=True):
        self.ok = ok

    def check_section(self, material, facts, body):
        return SectionQuality(
            body=body if self.ok else None,
            status="published" if self.ok else "needs_review",
            grounding_ratio=1.0,
            conflicts=[],
            score=1.0,
        )


class _Tr:
    def translate_section(self, body, lang, **kw):
        return f"{lang}:{body}"


def _mat(qid, **kw):
    return {"extract_en": "Housed in a 1900 railway station..."}


def test_generates_en_and_fills_langs(session):
    out = generate_museum_intro(
        session, "orsay",
        complete=lambda s, u: "A grand museum intro.",
        gate=_Gate(), translator=_Tr(), langs=["en", "zh", "ja"],
        fetch_material=_mat,
    )
    m = session.query(Museum).one()
    assert m.description_i18n["en"] == "A grand museum intro."
    assert m.description_i18n["zh"].startswith("zh:")
    assert out["generated"] is True and set(out["translated"]) == {"zh", "ja"}


def test_idempotent_fills_missing_language_only(session):
    m = session.query(Museum).one()
    m.description_i18n = {"en": "Existing.", "zh": "已有。"}
    session.commit()
    called = {"gen": 0}

    def complete(s, u):
        called["gen"] += 1
        return "regen"

    out = generate_museum_intro(
        session, "orsay", complete=complete, gate=_Gate(), translator=_Tr(),
        langs=["en", "zh", "ja"], fetch_material=_mat,
    )
    m = session.query(Museum).one()
    assert called["gen"] == 0  # en 在 → 不重生成(完整性按语言维度)
    assert m.description_i18n["zh"] == "已有。"  # 已有不动
    assert m.description_i18n["ja"] == "ja:Existing."  # 只补缺
    assert out["translated"] == ["ja"]


def test_gate_fail_writes_nothing(session):
    generate_museum_intro(
        session, "orsay", complete=lambda s, u: "bad", gate=_Gate(ok=False),
        translator=_Tr(), langs=["en", "zh"], fetch_material=_mat,
    )
    assert (session.query(Museum).one().description_i18n or {}) == {}


def test_no_material_skips(session):
    out = generate_museum_intro(
        session, "orsay", complete=lambda s, u: "x", gate=_Gate(), translator=_Tr(),
        langs=["en"], fetch_material=lambda qid, **kw: {"extract_en": None},
    )
    assert out["skipped"] == "no_material"


def _add_obj(s, qid, title, pop, key="k"):
    m = s.query(Museum).one()
    o = upsert_object(s, m.id, {"qid": qid, "title_en": title, "category": "painting"})
    o.popularity = pop
    img = ObjectImage(object_id=o.id, role="primary", source_url="u", image_key=key)
    s.add(img)
    s.commit()
    return o


def test_cover_rejects_then_picks_next(session):
    _add_obj(session, "Q1", "L'Origine du monde", 99, key="imgA")
    _add_obj(session, "Q2", "Water Lilies", 50, key="imgB")

    def judge(system, user):
        return '{"appropriate": false}' if "Origine" in user else '{"appropriate": true}'

    key = select_cover(session, "orsay", complete=judge)
    assert key == "imgB"
    assert session.query(Museum).one().cover_image_key == "imgB"


def test_cover_judge_error_skips_conservatively(session):
    _add_obj(session, "Q1", "Top", 99, key="imgA")
    _add_obj(session, "Q2", "Second", 50, key="imgB")

    def judge(system, user):
        if "Top" in user:
            raise RuntimeError("llm down")
        return '{"appropriate": true}'

    assert select_cover(session, "orsay", complete=judge) == "imgB"


def test_cover_idempotent(session):
    m = session.query(Museum).one()
    m.cover_image_key = "fixed"
    session.commit()
    assert select_cover(session, "orsay", complete=lambda s, u: 1 / 0) == "fixed"
```

- [ ] **Step 2: 跑确认失败**(ModuleNotFoundError)

- [ ] **Step 3: 实现**

```python
# backend/app/services/enrichment/museum_intro.py
"""博物馆介绍 + 封面(spec 2026-07-18)。
介绍:qid→en extract→接地生成(gate 不过不落)→按语言补缺(完整性按语言维度)。
封面:top-N 有图件逐件 LLM 得体性判定(古典/宗教裸体可,写实露骨否决;判定失败保守跳过)。
门面类预生成内容(成本分界原则),每馆一次性几分钱。"""

from __future__ import annotations

import logging

from app.models.museum import Museum
from app.models.museum_object import MuseumObject, ObjectImage
from app.services.enrichment.content_enricher import _parse_json
from app.services.enrichment.material import fetch_museum_intro_material
from app.services.enrichment.prompts import (
    build_cover_safety_prompt,
    build_museum_intro_prompt,
)

logger = logging.getLogger(__name__)


def generate_museum_intro(
    db,
    slug: str,
    *,
    complete,
    gate,
    translator,
    langs: list,
    force: bool = False,
    fetch_material=None,
) -> dict:
    m = db.query(Museum).filter_by(slug=slug).one_or_none()
    if not m:
        return {"error": "unknown museum"}
    di = {} if force else dict(m.description_i18n or {})
    out = {"generated": False, "translated": [], "skipped": None}

    if not di.get("en"):
        mat = (fetch_material or fetch_museum_intro_material)(m.qid)
        extract = mat.get("extract_en")
        if not extract:
            out["skipped"] = "no_material"  # 宁缺毋滥:源薄不硬写
            return out
        system, user = build_museum_intro_prompt(m.name_en or slug, extract)
        text = (complete(system, user) or "").strip()
        q = gate.check_section(extract, f"- Museum: {m.name_en}", text)
        if q.status != "published" or not q.body:
            return out  # gate 不过=不落库,重跑再试(无 needs_review 状态机)
        di["en"] = q.body
        out["generated"] = True

    for lang in langs:  # 按语言补缺:已有语种不动,缺的从 en 轴心纯翻译
        if lang == "en" or di.get(lang):
            continue
        try:
            di[lang] = translator.translate_section(di["en"], lang)
            out["translated"].append(lang)
        except Exception:
            logger.exception("museum intro translate %s failed: %s", lang, slug)
    m.description_i18n = di
    db.flush()
    return out


def select_cover(db, slug: str, *, complete, force: bool = False, limit: int = 10):
    """top-N 热度有图件里选第一张过得体性判定的当封面;全不过→None(前端隐藏)。"""
    m = db.query(Museum).filter_by(slug=slug).one_or_none()
    if not m:
        return None
    if m.cover_image_key and not force:
        return m.cover_image_key
    rows = (
        db.query(MuseumObject, ObjectImage)
        .join(ObjectImage, ObjectImage.object_id == MuseumObject.id)
        .filter(
            MuseumObject.museum_id == m.id,
            ObjectImage.role == "primary",
            ObjectImage.image_key.isnot(None),
        )
        .order_by(MuseumObject.popularity.desc().nullslast())
        .limit(limit)
        .all()
    )
    for o, img in rows:
        system, user = build_cover_safety_prompt(
            o.title_en or o.qid, o.artist_en, o.category
        )
        try:
            ok = bool(_parse_json(complete(system, user)).get("appropriate"))
        except Exception:  # 判定失败=保守跳过该件(封面宁缺毋错)
            logger.warning("cover judge failed for %s, skip", o.qid)
            continue
        if ok:
            m.cover_image_key = img.image_key
            db.flush()
            return img.image_key
    return None
```

- [ ] **Step 4: 跑通过**

Run: `cd backend && python -m pytest tests/integration/test_museum_intro.py -q --no-cov -p no:cacheprovider`
Expected: 7 passed

- [ ] **Step 5: Commit** `git commit -m "feat(enrichment): museum_intro 核心(接地生成/按语言补缺/封面得体性筛选)"`

### Task 6: onboard 子命令 intro

**Files:**
- Modify: `backend/scripts/onboard.py`(argparse + cmd_intro + main 分发)

**Interfaces:**
- Consumes: Task 5 两函数、既有 `build_generation_components(slug)`(返回 gate/translator/target_langs)、`default_complete`、`_ENV_BY_TARGET` 守卫模式

- [ ] **Step 1: argparse**(`cr = sub.add_parser("coverage-report")` 之前加)

```python
    it = sub.add_parser("intro")  # 馆介绍+封面(spec 2026-07-18;门面类预生成,幂等按语言补缺)
    it.add_argument("--target", choices=["staging", "prod"], required=True)
    it.add_argument("--force", action="store_true")
```

- [ ] **Step 2: cmd_intro**(照 cmd_names 的 env 守卫模式)

```python
def cmd_intro(slug: str, target: str, force: bool = False) -> None:
    expected = _ENV_BY_TARGET[target]
    if settings.ENVIRONMENT != expected:
        raise SystemExit(
            f"❌ --target={target} 期望容器 ENVIRONMENT={expected}，"
            f"但当前容器 ENVIRONMENT={settings.ENVIRONMENT}。请在 {expected} 环境容器内运行。"
        )
    from app.services.enrichment.content_enricher import default_complete
    from app.services.enrichment.factory import build_generation_components
    from app.services.enrichment.museum_intro import generate_museum_intro, select_cover

    c = build_generation_components(slug)
    db = SessionLocal()
    try:
        out = generate_museum_intro(
            db,
            slug,
            complete=default_complete,
            gate=c["gate"],
            translator=c["translator"],
            langs=c["target_langs"],  # 馆配置驱动(resolve_languages),不硬编
            force=force,
        )
        cover = select_cover(db, slug, complete=default_complete, force=force)
        db.commit()
    finally:
        db.close()
    print(f"✓ intro: {out} cover={cover}")
```

- [ ] **Step 3: main 分发**(coverage-report 分支之前)

```python
    elif ns.command == "intro":
        cmd_intro(ns.slug, ns.target, ns.force)
```

- [ ] **Step 4: 冒烟**(env 守卫先拦,证 wiring 通)

Run: `cd backend && python scripts/onboard.py orsay intro --target prod 2>&1 | tail -1`
Expected: `❌ --target=prod 期望容器 ENVIRONMENT=production...`

- [ ] **Step 5: Commit** `git commit -m "feat(ops): onboard intro 子命令(馆介绍+封面)"`

### Task 7: 契约回写 + PR

**Files:**
- Modify: `docs/architecture/museum-api-contract.md`

- [ ] **Step 1: 端点 2(馆包)节加**

```markdown
- `description`:馆叙事介绍(AI 接地生成,`description_i18n[language]`,缺→en→任一→**null**);`cover_image`:得体性筛选后的封面 R2 直链(large 档,**可 null**)。前端 `as String?`,null 整块隐藏。(✅2026-07-18 spec museum-intro)
```

- [ ] **Step 2: 上新馆配方步骤串加 `intro`**(catalog→names→images→**intro**→coverage-report),并在收录策略或内容体系节加一句原则:

```markdown
- **馆介绍=门面类预生成内容(2026-07-18 定)**:同"图=门面必须预物化"侧(馆页高频入口,成本封顶=馆数×几分钱),不走懒生成;`onboard <slug> intro` 幂等按语言补缺,加语言重跑自动补。**封面=后端 LLM 得体性筛选**(server-driven:选错改后端即生效;古典/宗教裸体=艺术惯例可,写实露骨否决)。不碰开放时间/票价(易变运营数据,AI 不脏补)。
```

- [ ] **Step 3: 变更记录顶部加一条** + 全量测试 + PR

```bash
cd backend && python -m pytest tests/ -q --no-cov -p no:cacheprovider -k "museum or intro or material or prompts" && cd ..
git add -A backend docs && git commit -m "docs(api): 契约回写——馆包 description/cover_image + 上新馆配方 intro 步"
git push -u origin feature/museum-intro
gh pr create --base staging --head feature/museum-intro --title "feat(museum): 博物馆介绍+封面(接地生成/按语言幂等/得体性筛选)" --body "spec: docs/superpowers/specs/2026-07-18-museum-intro-design.md"
```

CI 绿 → squash 合并 `--delete-branch`。迁移 q1n3 随 staging 部署自动跑。

### Task 8: prod 实跑 + 验收 + 前端交接

**Files:**
- Create: `docs/handoff/2026-07-18-museum-intro-frontend.md`(前端折叠 hero 交接)

- [ ] **Step 1: 发布**(随下批 staging→main,用户点)后 prod 容器跑:`python scripts/onboard.py orsay intro --target prod`
- [ ] **Step 2: 验收**:馆包 `description` zh 非空、内容接地(1900 火车站/印象派等可溯源);`cover_image` 非 null 且**不是《世界的起源》**(Q152416 类);staging 靠 `sync_staging_from_prod` 搬运获得(零操作)
- [ ] **Step 3: 前端交接文档**:折叠 hero(封面图 + 介绍卡默认收起 1-2 行 + 展开;两字段 `as String?`,null 整块隐藏;不建 tab 的理由:藏品列表保持主视图)

---

## Self-Review

1. **Spec coverage**:§1 两列+两字段→T1/T2;§2 生成五步+幂等按语言+封面四步→T3/T4/T5,命令→T6;§3 前端→T8 交接;§4 测试→各任务 TDD+T8 验收;契约回写清单→T7 ✓
2. **Placeholder**:无 TBD;所有代码步骤给了完整代码 ✓
3. **类型一致**:`generate_museum_intro(db, slug, *, complete, gate, translator, langs, force, fetch_material)` 与 T6 调用一致;`select_cover(db, slug, *, complete, force, limit)` 一致;`fetch_museum_intro_material(qid, *, get_json)` 与 T5 的 `fetch_material or ...` 一致(T5 fake `_mat(qid, **kw)` 兼容)✓
