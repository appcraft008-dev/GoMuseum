# 内容富化 Phase 1c — 多类别骨架 + 抓取整合 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans. Steps use checkbox (`- [ ]`).
> ⚠️ **重构提示**：改函数签名时 grep 范围必须含 `backend/tests/`（1b 教训：Fetcher 签名漏改集成测试致 CI 挂）。

**Goal:** 让富化产出真正可被详情端点消费——多类别段落骨架（单一真相源 + 标签多语言）seed 进库；把 Wikipedia 叙事素材接进两阶段抓取（WikidataSource 捕获各语言 sitelink 标题 → Fetcher 注入 context → WikipediaSource 触发）；QID redirect 归并。1b 的 loader 已能吃新 pack（attributes 自动落库），本期不改 loader。

**Architecture:** 全部在 `backend/`。扩 `enrichment/category_config.py`（加 `category→sections` + `section→多语言标签`）；改 `scripts/seed_sections.py`（多类别、读配置）；改 `app/services/museum_repo.py`（按语言本地化段落标签）；改 `enrichment/sources/wikidata.py`（捕获 sitelink 标题 + QID redirect）；改 `enrichment/fetcher.py`（注入 wiki_titles 进 context）。

**Tech Stack:** Python 3.11 / pytest / 既有 enrichment 框架。

**分支：** 从最新 `staging` 切 `feature/content-enrichment-phase1c`。**测试：** `cd backend && poetry run pytest`（用 storage 的测试加 `STORAGE_BACKEND=local`）。

**对应 spec：** §6/§18b-1（类别→段落单一真相源）、§18b-2（标签多语言）、§5（Wikipedia 多源语言、QID redirect）。

---

## File Structure

| 文件 | 责任 | 改动 |
|---|---|---|
| `enrichment/category_config.py` | 加 `SECTIONS_BY_CATEGORY` + `SECTION_LABELS`（单一真相源） | 改 |
| `scripts/seed_sections.py` | 多类别 seed（读 category_config，不硬编码绘画） | 改 |
| `app/services/museum_repo.py` | `get_object_content` 段落标签按 `language` 本地化 | 改 |
| `enrichment/sources/wikidata.py` | 捕获各语言 sitelink 标题入 `fields["wiki_titles"]` + QID redirect 归并 | 改 |
| `enrichment/fetcher.py` | 把脊柱的 `wiki_titles` 注入 enrich 的 context | 改 |

---

## Task 1: category_config 加 `category→sections` + `section→多语言标签`

**Files:** Modify `backend/app/services/enrichment/category_config.py`；Test `backend/tests/unit/services/enrichment/test_category_config.py`（追加）

- [ ] **Step 1: 失败测试（追加）**
```python
def test_sections_by_category_and_fallback():
    from app.services.enrichment.category_config import sections_for
    assert sections_for("painting") == [
        "overview", "artist", "background", "analysis", "significance", "facts"
    ]
    assert sections_for("sculpture")[:3] == ["overview", "artist", "material-technique"]
    # 未知类别 → 通用兜底集
    assert sections_for("unknown") == ["overview", "background", "significance", "facts"]


def test_section_label_localized_with_en_fallback():
    from app.services.enrichment.category_config import section_label
    assert section_label("overview", "zh") == "通用描述"
    assert section_label("overview", "en") == "Overview"
    assert section_label("overview", "fr") == "Aperçu"
    # 未配语言 → 回退 en
    assert section_label("overview", "xx") == "Overview"
```

- [ ] **Step 2: 跑确认失败** — `cd backend && poetry run pytest tests/unit/services/enrichment/test_category_config.py -k 'sections or label' -v`。

- [ ] **Step 3: 扩 `category_config.py`（在文件末尾追加）**
```python
# 类别 → 有序段落集（单一真相源；seed/生成/详情共用）。未知类别用 _FALLBACK。
SECTIONS_BY_CATEGORY: dict[str, list[str]] = {
    "painting": ["overview", "artist", "background", "analysis", "significance", "facts"],
    "sculpture": ["overview", "artist", "material-technique", "background", "significance", "facts"],
    "photograph": ["overview", "photographer", "context", "significance", "facts"],
    "decorative": ["overview", "maker", "material-technique", "use", "significance", "facts"],
}
_FALLBACK_SECTIONS = ["overview", "background", "significance", "facts"]

# 段落 code → 各语言标签（i18n 配置；缺语言回退 en）。十几个固定词，一次性配。
SECTION_LABELS: dict[str, dict[str, str]] = {
    "overview": {"zh": "通用描述", "en": "Overview", "fr": "Aperçu", "de": "Überblick", "es": "Resumen", "it": "Panoramica"},
    "artist": {"zh": "作者介绍", "en": "The Artist", "fr": "L'artiste", "de": "Der Künstler", "es": "El artista", "it": "L'artista"},
    "photographer": {"zh": "摄影师", "en": "The Photographer", "fr": "Le photographe", "de": "Der Fotograf", "es": "El fotógrafo", "it": "Il fotografo"},
    "maker": {"zh": "制作者", "en": "The Maker", "fr": "Le créateur", "de": "Der Hersteller", "es": "El creador", "it": "Il creatore"},
    "material-technique": {"zh": "材质工艺", "en": "Material & Technique", "fr": "Matériaux et technique", "de": "Material und Technik", "es": "Material y técnica", "it": "Materiali e tecnica"},
    "background": {"zh": "创作背景", "en": "Background", "fr": "Contexte", "de": "Hintergrund", "es": "Contexto", "it": "Contesto"},
    "context": {"zh": "拍摄背景", "en": "Context", "fr": "Contexte", "de": "Kontext", "es": "Contexto", "it": "Contesto"},
    "use": {"zh": "用途", "en": "Use", "fr": "Usage", "de": "Verwendung", "es": "Uso", "it": "Uso"},
    "analysis": {"zh": "艺术分析", "en": "Analysis", "fr": "Analyse", "de": "Analyse", "es": "Análisis", "it": "Analisi"},
    "significance": {"zh": "文化意义", "en": "Significance", "fr": "Signification", "de": "Bedeutung", "es": "Significado", "it": "Significato"},
    "facts": {"zh": "趣闻轶事", "en": "Facts", "fr": "Anecdotes", "de": "Fakten", "es": "Datos", "it": "Curiosità"},
}
# 段落默认排序值（seed 用）
SECTION_SORT = {
    "overview": 10, "artist": 20, "photographer": 20, "maker": 20,
    "material-technique": 30, "background": 30, "context": 30, "use": 35,
    "analysis": 40, "significance": 50, "facts": 60,
}


def sections_for(category: str) -> list[str]:
    return SECTIONS_BY_CATEGORY.get(category, _FALLBACK_SECTIONS)


def section_label(code: str, lang: str) -> str:
    labels = SECTION_LABELS.get(code, {})
    return labels.get(lang) or labels.get("en") or code
```

- [ ] **Step 4: 跑确认通过 + 提交** — 预期 passed。
```bash
cd backend && poetry run black app/services/enrichment/category_config.py tests/unit/services/enrichment/test_category_config.py && poetry run isort app/services/enrichment/category_config.py tests/unit/services/enrichment/test_category_config.py
cd /Users/hongyang/Projects/GoMuseum && git add backend/app/services/enrichment/category_config.py backend/tests/unit/services/enrichment/test_category_config.py
git commit -m "feat(enrichment): category_config 加 类别→段落集 + 段落多语言标签(单一真相源)"
```

---

## Task 2: seed_sections.py 多类别（读 category_config）

**Files:** Modify `backend/scripts/seed_sections.py`；Test `backend/tests/unit/services/test_seed_sections.py`（新建）

- [ ] **Step 1: 失败测试**（用 SQLite in-memory 验证 seed 产出多类别 category_sections）
```python
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.models.content import CategorySection, SectionType


@pytest.fixture()
def session():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(bind=engine, tables=[SectionType.__table__, CategorySection.__table__])
    yield sessionmaker(bind=engine)()


def test_seed_creates_multi_category_skeleton(session):
    from scripts.seed_sections import seed_into
    seed_into(session)
    cats = {c.category for c in session.query(CategorySection).all()}
    assert {"painting", "sculpture", "photograph", "decorative"} <= cats
    # painting 有 6 段
    painting = [c.section_code for c in session.query(CategorySection).filter_by(category="painting").all()]
    assert len(painting) == 6 and "artist" in painting
    # section_types 覆盖所有用到的 code
    codes = {s.code for s in session.query(SectionType).all()}
    assert {"overview", "material-technique", "photographer"} <= codes
```

- [ ] **Step 2: 跑确认失败** — `cd backend && poetry run pytest tests/unit/services/test_seed_sections.py -v`（`seed_into` 不存在）。

- [ ] **Step 3: 改 `seed_sections.py`** — 抽出 `seed_into(db)`（吃任意 session，便于测试），读 category_config：
```python
"""种子：讲解 tab 词表 + 各类别 tab 集合（幂等 upsert，读 category_config 单一真相源）。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.core.database import SessionLocal  # noqa: E402
from app.models.content import CategorySection, SectionType  # noqa: E402
from app.services.enrichment.category_config import (  # noqa: E402
    SECTION_LABELS,
    SECTION_SORT,
    SECTIONS_BY_CATEGORY,
    section_label,
)


def seed_into(db) -> None:
    # 1) section_types：所有出现过的 code
    all_codes = {c for codes in SECTIONS_BY_CATEGORY.values() for c in codes}
    for code in all_codes:
        st = db.get(SectionType, code) or SectionType(code=code)
        st.label_zh = section_label(code, "zh")
        st.label_en = section_label(code, "en")
        st.default_sort = SECTION_SORT.get(code, 99)
        db.merge(st)
    db.flush()  # FK 可见
    # 2) category_sections：每类别按序
    for category, codes in SECTIONS_BY_CATEGORY.items():
        for i, code in enumerate(codes):
            db.merge(
                CategorySection(
                    category=category, section_code=code, sort_order=(i + 1) * 10
                )
            )
    db.commit()


def seed() -> None:
    db = SessionLocal()
    try:
        seed_into(db)
        print(f"✓ seeded {len(SECTION_LABELS)} section_types, {len(SECTIONS_BY_CATEGORY)} categories")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
```
> 注：`label_zh`/`label_en` 仍写进 SectionType（向后兼容现有读路径）；fr/de/es/it 由 §Task 3 的 museum_repo 用 `section_label` 现取，不进这两列。

- [ ] **Step 4: 跑确认通过 + 提交** — 预期 passed。
```bash
cd backend && poetry run black scripts/seed_sections.py tests/unit/services/test_seed_sections.py && poetry run isort scripts/seed_sections.py tests/unit/services/test_seed_sections.py
cd /Users/hongyang/Projects/GoMuseum && git add backend/scripts/seed_sections.py backend/tests/unit/services/test_seed_sections.py
git commit -m "feat(enrichment): seed_sections 多类别(读 category_config 单一真相源)"
```

---

## Task 3: museum_repo 段落标签按语言本地化

**Files:** Modify `backend/app/services/museum_repo.py`；Test `backend/tests/integration/test_object_content_endpoint.py`（追加）

- [ ] **Step 1: 失败测试（追加）** — 法语请求时 tab label 用法语（非退回英文）：
```python
def test_object_content_labels_localized_fr(client):
    # 见文件既有 fixture：已 seed overview 段 + Q1 对象。请求 language=fr → label 应为法语
    r = client.get("/api/v1/museums/orsay/objects/Q1/content?language=fr")
    assert r.status_code == 200
    tabs = r.json()["tabs"]
    overview = next((t for t in tabs if t["section_code"] == "overview"), None)
    assert overview is not None
    assert overview["label"] == "Aperçu"   # 法语标签（来自 category_config）
```
> 若既有 fixture 未 seed `category_sections`/`section_types`，按既有 test_object_content_endpoint.py 的 seed 方式补 overview（label_zh/en + category painting→overview）。

- [ ] **Step 2: 跑确认失败** — 当前 museum_repo 用 `label_zh if zh else label_en`，fr 会得 "Overview"。

- [ ] **Step 3: 改 `museum_repo.get_object_content`** — label 改用 `section_label(code, language)`：
找到现有构造 tab 的 `label`（形如 `st.label_zh if language == "zh" else st.label_en`），替换为：
```python
from app.services.enrichment.category_config import section_label  # 顶部 import
...
                "label": section_label(cs.section_code, language),
```

- [ ] **Step 4: 跑确认通过（含既有无回归）+ 提交** — `STORAGE_BACKEND=local poetry run pytest tests/integration/test_object_content_endpoint.py -W "ignore::PendingDeprecationWarning" -v`。
```bash
cd backend && poetry run black app/services/museum_repo.py tests/integration/test_object_content_endpoint.py && poetry run isort app/services/museum_repo.py tests/integration/test_object_content_endpoint.py
cd /Users/hongyang/Projects/GoMuseum && git add backend/app/services/museum_repo.py backend/tests/integration/test_object_content_endpoint.py
git commit -m "feat(museum): object_content 段落标签按语言本地化(category_config,fr/de/...)"
```

---

## Task 4: WikidataSource 捕获 sitelink 标题 + QID redirect

**Files:** Modify `backend/app/services/enrichment/sources/wikidata.py`；Test `backend/tests/unit/services/enrichment/test_wikidata_source.py`（追加）

- [ ] **Step 1: 失败测试（追加）** — SPARQL 行带 `sitelink_en`/`sitelink_fr` → 产出 `fields["wiki_titles"]`：
```python
def test_captures_sitelink_titles(monkeypatch):
    from app.services.enrichment.sources.wikidata import WikidataSource

    rows = [{
        "item": {"value": "http://www.wikidata.org/entity/Q1"},
        "label_en": {"value": "A"}, "links": {"value": "5"},
        "p31": {"value": "http://www.wikidata.org/entity/Q3305213"},
        "sitelink_en": {"value": "https://en.wikipedia.org/wiki/Bedroom_in_Arles"},
        "sitelink_fr": {"value": "https://fr.wikipedia.org/wiki/La_Chambre_à_Arles"},
    }]
    src = WikidataSource()
    monkeypatch.setattr(src, "_run_query", lambda sparql: rows)
    monkeypatch.setattr("app.services.enrichment.sources.wikidata.time.sleep", lambda s: None)
    c = list(src.fetch(CFG))[0]
    assert c.fields["wiki_titles"]["en"] == "Bedroom_in_Arles"
    assert c.fields["wiki_titles"]["fr"] == "La_Chambre_à_Arles"
```

- [ ] **Step 2: 跑确认失败**。

- [ ] **Step 3: 改 wikidata.py**
  - QUERY 加 sitelink schema 段（en + 馆国语言）。因 SPARQL 模板里语言要动态，用 `cfg.country_lang`：在 `fetch` 里 format 一个 `country_lang`（缺省 "fr"），QUERY 加：
```sparql
  OPTIONAL {{ ?art_en schema:about ?item ; schema:isPartOf <https://en.wikipedia.org/> ; schema:name ?sitelink_en . }}
  OPTIONAL {{ ?art_cl schema:about ?item ; schema:isPartOf <https://{country_lang}.wikipedia.org/> ; schema:name ?sitelink_cl . }}
```
  SELECT 加 `?sitelink_en ?sitelink_cl`。`fetch` 每行：
```python
                titles = {}
                se = _v(row, "sitelink_en")
                if se:
                    titles["en"] = se.rsplit("/", 1)[-1]
                scl = _v(row, "sitelink_cl")
                if scl:
                    titles[cfg.country_lang or "fr"] = scl.rsplit("/", 1)[-1]
                # …在 fields 里加：
                "wiki_titles": titles,
```
  > schema:name 返回的是页面标题（带空格/下划线视情况）；用 URL 末段 `rsplit("/",1)[-1]` 取标题更稳。测试用带 URL 的 `schema:name`——实现按 URL 末段取。**若 schema:name 实际返回纯标题而非 URL，则去掉 rsplit**；本任务以测试为准（测试给 URL）。
  - **QID redirect**：Wikidata `?item` 偶尔是重定向。处理：`_run_query` 返回的 item 已是规范 QID（SPARQL 自动解析重定向），故 SPARQL 路径通常无需额外处理；**本任务仅加注释说明"SPARQL 已解析 redirect；按 entity-data REST 抓取的源(如未来)需自行跟随"**，不写额外代码（避免无依据实现）。

- [ ] **Step 4: 跑确认通过 + 提交** — `… test_wikidata_source.py -v` 全 passed（既有用例 FAKE_ROWS 无 sitelink → wiki_titles={}，不破）。
```bash
cd backend && poetry run black app/services/enrichment/sources/wikidata.py tests/unit/services/enrichment/test_wikidata_source.py && poetry run isort app/services/enrichment/sources/wikidata.py tests/unit/services/enrichment/test_wikidata_source.py
cd /Users/hongyang/Projects/GoMuseum && git add backend/app/services/enrichment/sources/wikidata.py backend/tests/unit/services/enrichment/test_wikidata_source.py
git commit -m "feat(enrichment): WikidataSource 捕获各语言 sitelink 标题(wiki_titles)"
```

---

## Task 5: Fetcher 把 wiki_titles 注入 enrich 的 context

**Files:** Modify `backend/app/services/enrichment/fetcher.py`；Test `backend/tests/unit/services/enrichment/test_fetcher.py`（追加）

- [ ] **Step 1: 失败测试（追加）** — 富化源 enrich 收到的 context 含脊柱的 wiki_titles：
```python
def test_enrich_context_carries_wiki_titles():
    from app.services.enrichment.fetcher import Fetcher
    from app.services.enrichment.registry import SourceRegistry
    from app.services.enrichment.sources.base import ObjectContribution, Source

    seen = {}

    class Spine(Source):
        name = "wikidata"
        def fetch(self, cfg):
            yield ObjectContribution(source="wikidata", qid="Q1",
                fields={"title_en": "A", "external_ids": {}, "wiki_titles": {"en": "T"}, "popularity": 1}, raw={})

    class Wiki(Source):
        name = "wikipedia"
        def probe(self, ext): return True
        def enrich(self, qid, ext, context):
            seen["ctx"] = context
            return None
        def fetch(self, cfg): return []

    class Store:
        def put(self, slug, pack): return "k"

    Fetcher(catalog=<含orsay的catalog>, spine=Spine(), registry=SourceRegistry([Wiki()]), pack_store=Store()).fetch("orsay")
    assert seen["ctx"]["wiki_titles"] == {"en": "T"}
```

- [ ] **Step 2: 跑确认失败** — 当前 fetcher 传 `enrich(qid, ext, {})` 空 context。

- [ ] **Step 3: 改 fetcher.py** — 把脊柱的 `wiki_titles` 放进 context：
找到 `for src in self._registry.route(ext): c = src.enrich(qid, ext, {})`，改为：
```python
            context = {"wiki_titles": spine_contrib.fields.get("wiki_titles", {})}
            for src in self._registry.route(ext):
                c = src.enrich(qid, ext, context)
```

- [ ] **Step 4: 跑确认通过 + 提交** — `… test_fetcher.py -v` 全 passed。
```bash
cd backend && poetry run black app/services/enrichment/fetcher.py tests/unit/services/enrichment/test_fetcher.py && poetry run isort app/services/enrichment/fetcher.py tests/unit/services/enrichment/test_fetcher.py
cd /Users/hongyang/Projects/GoMuseum && git add backend/app/services/enrichment/fetcher.py backend/tests/unit/services/enrichment/test_fetcher.py
git commit -m "feat(enrichment): Fetcher 把 wiki_titles 注入 enrich context(Wikipedia 触发)"
```

---

## Task 6: seed 多类别骨架进 staging + prod（运维，合并后做）

- [ ] 合并本期 PR 后，在容器内跑：
```bash
ssh -i ~/.ssh/deepmeeting_deploy root@38.242.207.219 \
  "docker exec gomuseum_staging_backend python scripts/seed_sections.py && docker exec gomuseum_prod_backend python scripts/seed_sections.py"
```
预期：两环境各打印 `✓ seeded … section_types, 4 categories`。之后 `object_content` 对多类别藏品能返回 tabs（虽 body 仍空，待 Phase 2 生成）。

---

## 收尾

- [ ] **全套相关单测**：`cd backend && STORAGE_BACKEND=local poetry run pytest tests/unit/services/enrichment/ tests/unit/services/test_seed_sections.py tests/integration/test_object_content_endpoint.py -W "ignore::PendingDeprecationWarning" -v` 全 passed。
- [ ] **grep 改签名影响**：本期未改函数签名（仅加字段/参数默认值），但仍 `grep -rn "section_label\|sections_for\|seed_into" backend` 确认调用一致。
- [ ] **提 PR**：`feature/content-enrichment-phase1c → staging`。CI 绿后 squash 合并 → Task 6 seed。

---

## Self-Review（计划对照 spec）

- **§6/§18b-1 类别→段落单一真相源**：`SECTIONS_BY_CATEGORY`（Task 1）+ seed 读它（Task 2）✓。
- **§18b-2 标签多语言**：`SECTION_LABELS` + `section_label`（Task 1）+ museum_repo 本地化（Task 3）✓。馆名/城市多语言补全（从 Wikidata label）**本期未含**——下放后续（museums.yaml 现有 name_zh/en 够 zh/en 展示；多语言馆名属小补强，记入待办，避免本期过大）。
- **§5 Wikipedia 多源语言接入**：WikidataSource 捕获 sitelink 标题（Task 4）+ Fetcher 注入 context（Task 5）→ WikipediaSource（1b 已实现）触发 ✓。
- **QID redirect**：SPARQL 已解析（Task 4 注明）；REST 路径的 redirect 跟随留到真有 REST 源时做。
- **loader 落 attributes/needs_review**：1b loader 已落 attributes（含 Joconde 法语事实）✓；对象级 `needs_review` 列 MuseumObject 暂无，`_conflicts` 已存 sources JSONB 可回溯——加列留后续，本期不阻塞。
- **不在本期**：馆名城市多语言补全、对象级 needs_review 列、WikidataSource 切 PoliteSession+SourceCache、SPARQL 层 sitelinks 阈值（属 Phase 2 生成范围）。
- **类型一致**：`sections_for(category)->list`、`section_label(code,lang)->str`、`seed_into(db)`、`fields["wiki_titles"]`、context `{"wiki_titles":{...}}` 跨任务一致 ✓。
