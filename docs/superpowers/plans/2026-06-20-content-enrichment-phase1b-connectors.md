# 内容富化 Phase 1b — 三连接器 + 两阶段抓取 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans. Steps use checkbox (`- [ ]`).

**Goal:** 在 1a 地基上接真实数据源——类别配置化、WikidataSource 多类别+图可选+捕获外部ID、两阶段抓取（脊柱 Wikidata → 按外部ID 路由 enrich）、JocondeSource（P347 自动发现，权威法语事实）、WikipediaSource（多源语言叙事素材）。真实验证"Wikidata 外部ID → Joconde → official 优先合并"接缝。

**Architecture:** 全部在 `backend/app/services/enrichment/`。新增 `category_config.py`、`sources/wikipedia.py`、`sources/joconde.py`；改 `sources/base.py`（加 `enrich`）、`sources/wikidata.py`（多类别/图可选/外部ID/PoliteSession+SourceCache）、`catalog.py`（MuseumConfig 加 `categories`/`country_lang`，向后兼容）、`fetcher.py`（两阶段）、`museums.yaml`。连接器单测全离线（注入 `_run_query`/transport）；真实联网仅在跑 onboard 验证时。

**Tech Stack:** Python 3.11 / pytest / requests / 1a 的 `PoliteSession`+`SourceCache`+`SourceRegistry`+`merge`。

**分支：** `feature/content-enrichment-phase1b`（已从 staging 切）。**测试：** `cd backend && poetry run pytest`（无 backend/.venv；用到 storage 的测试加 `STORAGE_BACKEND=local`）。

**对应 spec：** §5（源/多源语言/礼貌）、§5b（official 优先）、§18b-1/6（类别单一真相源/外部ID路由）、JocondeSource（§5）。

---

## File Structure

| 文件 | 责任 | 改动 |
|---|---|---|
| `enrichment/category_config.py` | 单一真相源：P31 QID→类别名 | 新建 |
| `enrichment/sources/base.py` | `Source` 加 `enrich(qid,external_ids,context)->ObjectContribution\|None`（默认 None） | 改 |
| `enrichment/sources/wikidata.py` | 多类别 + 图可选 + 捕获外部ID(P347) + 类别用 category_config | 改 |
| `enrichment/catalog.py` | MuseumConfig 加 `categories:list`/`country_lang`（向后兼容） | 改 |
| `enrichment/sources/joconde.py` | JocondeSource：probe(P347) + enrich(REF→base-joconde-extrait) | 新建 |
| `enrichment/sources/wikipedia.py` | WikipediaSource：enrich(sitelink→REST extract，多源语言) | 新建 |
| `enrichment/fetcher.py` | 两阶段：脊柱 fetch + 按外部ID 路由 enrich | 改 |

---

## Task 1: `category_config.py`（P31→类别 单一真相源）

**Files:** Create `backend/app/services/enrichment/category_config.py`；Test `backend/tests/unit/services/enrichment/test_category_config.py`

- [ ] **Step 1: 失败测试**
```python
from app.services.enrichment.category_config import category_for, DEFAULT_CATEGORY


def test_known_qids_map():
    assert category_for("Q3305213") == "painting"
    assert category_for("Q860861") == "sculpture"
    assert category_for("Q125191") == "photograph"


def test_unknown_falls_back():
    assert category_for("Q999999") == DEFAULT_CATEGORY
    assert category_for(None) == DEFAULT_CATEGORY
```

- [ ] **Step 2: 跑确认失败** — `cd backend && poetry run pytest tests/unit/services/enrichment/test_category_config.py -v` → ModuleNotFoundError。

- [ ] **Step 3: 实现**
```python
"""类别单一真相源：Wikidata P31 QID → canonical 类别名。
seed/抓取/生成器/prompt 共用，加新类别=改这里、零代码。"""

from __future__ import annotations

CATEGORY_BY_QID: dict[str, str] = {
    "Q3305213": "painting",
    "Q860861": "sculpture",
    "Q125191": "photograph",
}
DEFAULT_CATEGORY = "unknown"


def category_for(p31_qid: str | None) -> str:
    return CATEGORY_BY_QID.get(p31_qid or "", DEFAULT_CATEGORY)
```

- [ ] **Step 4: 跑确认通过** — 预期 2 passed。
- [ ] **Step 5: 提交**
```bash
cd backend && poetry run black app/services/enrichment/category_config.py tests/unit/services/enrichment/test_category_config.py && poetry run isort app/services/enrichment/category_config.py tests/unit/services/enrichment/test_category_config.py
cd /Users/hongyang/Projects/GoMuseum && git add backend/app/services/enrichment/category_config.py backend/tests/unit/services/enrichment/test_category_config.py
git commit -m "feat(enrichment): category_config 单一真相源(P31→类别)"
```

---

## Task 2: MuseumConfig 加 `categories` + `country_lang`（向后兼容）

**Files:** Modify `backend/app/services/enrichment/catalog.py`；Test `backend/tests/unit/services/enrichment/test_catalog.py`（追加）；Modify `backend/museums.yaml`

- [ ] **Step 1: 失败测试（追加 test_catalog.py）**
```python
def test_categories_and_country_lang_parsed(tmp_path):
    from app.services.enrichment.catalog import MuseumCatalog
    p = tmp_path / "m.yaml"
    p.write_text(
        "museums:\n"
        "  orsay:\n"
        "    name_zh: 奥赛\n    name_en: Orsay\n    city_zh: 巴黎\n    city_en: Paris\n"
        "    country: FR\n    wikidata_qid: Q23402\n    category_filter: Q3305213\n"
        "    categories: [Q3305213, Q860861]\n    country_lang: fr\n"
        "    fetch_limit: 5\n    sample_size: 2\n",
        encoding="utf-8",
    )
    cfg = MuseumCatalog.from_file(p).get("orsay")
    assert cfg.categories == ["Q3305213", "Q860861"]
    assert cfg.country_lang == "fr"


def test_categories_defaults_to_category_filter(tmp_path):
    from app.services.enrichment.catalog import MuseumCatalog
    p = tmp_path / "m.yaml"
    p.write_text(
        "museums:\n  orsay:\n    name_zh: 奥赛\n    name_en: Orsay\n    city_zh: 巴黎\n"
        "    city_en: Paris\n    country: FR\n    wikidata_qid: Q23402\n"
        "    category_filter: Q3305213\n    fetch_limit: 5\n    sample_size: 2\n",
        encoding="utf-8",
    )
    cfg = MuseumCatalog.from_file(p).get("orsay")
    assert cfg.categories == ["Q3305213"]  # 缺省回退 category_filter
    assert cfg.country_lang is None
```

- [ ] **Step 2: 跑确认失败** — `cd backend && poetry run pytest tests/unit/services/enrichment/test_catalog.py -v` → AttributeError（无 categories/country_lang）。

- [ ] **Step 3: 改 catalog.py** — `MuseumConfig` 加两字段，`from_file` 解析（向后兼容）：
```python
@dataclass(frozen=True)
class MuseumConfig:
    slug: str
    name_zh: str
    name_en: str
    city_zh: str
    city_en: str
    country: str
    wikidata_qid: str
    category_filter: str
    fetch_limit: int
    sample_size: int
    sample_qids: list[str] = field(default_factory=list)
    categories: list[str] = field(default_factory=list)
    country_lang: str | None = None
```
`from_file` 里 `MuseumConfig(...)` 调用追加：
```python
                categories=list(m.get("categories") or [m["category_filter"]]),
                country_lang=m.get("country_lang"),
```

- [ ] **Step 4: museums.yaml 给 orsay 加** `categories: [Q3305213]` 和 `country_lang: fr`（本期先绘画，雕塑/摄影 QID 待 1c 真实上馆时加）：
```yaml
    category_filter: Q3305213
    categories: [Q3305213]
    country_lang: fr
```

- [ ] **Step 5: 跑确认通过 + 提交** — `cd backend && poetry run pytest tests/unit/services/enrichment/test_catalog.py -v` 全 passed。
```bash
cd backend && poetry run black app/services/enrichment/catalog.py tests/unit/services/enrichment/test_catalog.py && poetry run isort app/services/enrichment/catalog.py tests/unit/services/enrichment/test_catalog.py
cd /Users/hongyang/Projects/GoMuseum && git add backend/app/services/enrichment/catalog.py backend/tests/unit/services/enrichment/test_catalog.py backend/museums.yaml
git commit -m "feat(enrichment): MuseumConfig 加 categories/country_lang(向后兼容)"
```

---

## Task 3: `Source.enrich` 接口（per-object 富化源）

**Files:** Modify `backend/app/services/enrichment/sources/base.py`；Test `backend/tests/unit/services/enrichment/test_source_base.py`（追加）

- [ ] **Step 1: 失败测试（追加）**
```python
def test_source_enrich_default_returns_none():
    from app.services.enrichment.sources.base import Source

    class Spine(Source):
        name = "x"

        def fetch(self, cfg):
            return []

    # 默认 enrich 返回 None（脊柱源不做 per-object 富化）
    assert Spine().enrich("Q1", {"P347": "REF"}, {}) is None
```

- [ ] **Step 2: 跑确认失败** — `… test_source_base.py -k enrich -v` → AttributeError。

- [ ] **Step 3: base.py 加 `enrich`（默认 None）** — 在 `probe` 之后：
```python
    def enrich(self, qid: str, external_ids: dict, context: dict):
        """per-object 富化：给定对象的 qid + 外部ID + 上下文 → 返回一条 ObjectContribution 或 None。
        脊柱源（Wikidata）默认 None；富化源（Joconde/Wikipedia）重写。"""
        return None
```

- [ ] **Step 4: 跑确认通过 + 提交** — 预期 passed。
```bash
cd backend && poetry run black app/services/enrichment/sources/base.py tests/unit/services/enrichment/test_source_base.py && poetry run isort app/services/enrichment/sources/base.py tests/unit/services/enrichment/test_source_base.py
cd /Users/hongyang/Projects/GoMuseum && git add backend/app/services/enrichment/sources/base.py backend/tests/unit/services/enrichment/test_source_base.py
git commit -m "feat(enrichment): Source.enrich per-object 富化接口(默认None)"
```

---

## Task 4: WikidataSource 多类别 + 图可选 + 捕获外部ID

**Files:** Modify `backend/app/services/enrichment/sources/wikidata.py`；Test `backend/tests/unit/services/enrichment/test_wikidata_source.py`（追加/改）

- [ ] **Step 1: 失败测试（追加）** — 验证图可选、按 P31 映射类别、捕获 P347 外部ID：
```python
def test_image_optional_and_external_ids_and_category(monkeypatch):
    from app.services.enrichment.sources.wikidata import WikidataSource

    rows = [
        {
            "item": {"value": "http://www.wikidata.org/entity/Q1"},
            "label_en": {"value": "A"},
            "links": {"value": "5"},
            "p31": {"value": "http://www.wikidata.org/entity/Q860861"},  # sculpture
            "joconde": {"value": "000PE004070"},
            # 注意：无 image → 图可选
        }
    ]
    src = WikidataSource()
    monkeypatch.setattr(src, "_run_query", lambda sparql: rows)
    monkeypatch.setattr(
        "app.services.enrichment.sources.wikidata.time.sleep", lambda s: None
    )
    out = list(src.fetch(CFG))  # CFG.categories 至少含一类
    assert len(out) == 1
    c = out[0]
    assert c.fields["category"] == "sculpture"      # 按 P31 映射
    assert c.fields.get("image_url") is None         # 无图也产出
    assert c.fields["external_ids"] == {"P347": "000PE004070"}  # 捕获外部ID
```
> 把文件顶部 `CFG` 改为含 `categories=["Q3305213"]`（或在测试内构造）。既有 `test_fetch_yields_contributions_with_qid_fields_raw` 保持能过（FAKE_ROWS 无 p31→category 回退 unknown；若该用例断言 category=="painting" 需改为按 CFG 首类或 unknown——按实际实现调整断言，不破语义）。

- [ ] **Step 2: 跑确认失败** — `… test_wikidata_source.py -v`。

- [ ] **Step 3: 改 wikidata.py**
  - QUERY：`?item wdt:P18 ?image` 移入 `OPTIONAL`；SELECT 加 `?p31 ?joconde`；用 `VALUES ?cat { wd:Q… wd:Q… }` 支持多类别、并 `?item wdt:P31 ?p31`（取实例类型）：
```python
QUERY = """
SELECT ?item ?label_zh ?label_en ?creator_zh ?creator_en ?year ?image ?links ?inventory ?p31 ?joconde WHERE {{
  VALUES ?cat {{ {cat_values} }}
  ?item wdt:P195 wd:{museum} . ?item wdt:P31 ?cat . ?item wdt:P31 ?p31 .
  ?item wikibase:sitelinks ?links .
  OPTIONAL {{ ?item wdt:P18 ?image }}
  OPTIONAL {{ ?item rdfs:label ?label_zh . FILTER(LANG(?label_zh)="zh") }}
  OPTIONAL {{ ?item rdfs:label ?label_en . FILTER(LANG(?label_en)="en") }}
  OPTIONAL {{ ?item wdt:P170 ?creator .
    OPTIONAL {{ ?creator rdfs:label ?creator_zh . FILTER(LANG(?creator_zh)="zh") }}
    OPTIONAL {{ ?creator rdfs:label ?creator_en . FILTER(LANG(?creator_en)="en") }} }}
  OPTIONAL {{ ?item wdt:P571 ?date . BIND(YEAR(?date) AS ?year) }}
  OPTIONAL {{ ?item wdt:P217 ?inventory }}
  OPTIONAL {{ ?item wdt:P347 ?joconde }}
}} ORDER BY DESC(?links) LIMIT {limit} OFFSET {offset}
"""
```
  - `fetch`：用 `from app.services.enrichment.category_config import category_for`；`cats = cfg.categories or [cfg.category_filter]`；`cat_values = " ".join(f"wd:{q}" for q in cats)`；format 时传 `cat_values`（去掉旧的单 `category=`）。每行：
```python
                p31_qid = (row.get("p31", {}) or {}).get("value", "").rsplit("/", 1)[-1]
                ext = {}
                jo = _v(row, "joconde")
                if jo:
                    ext["P347"] = jo
                yield ObjectContribution(
                    source="wikidata",
                    qid=qid,
                    raw=row,
                    fields={
                        "category": category_for(p31_qid),
                        "title_zh": _v(row, "label_zh"),
                        "title_en": _v(row, "label_en"),
                        "artist_zh": _v(row, "creator_zh"),
                        "artist_en": _v(row, "creator_en"),
                        "year": _v(row, "year"),
                        "inventory_number": _v(row, "inventory"),
                        "popularity": int(_v(row, "links") or 0),
                        "image_url": _v(row, "image"),
                        "external_ids": ext,
                    },
                )
```
  > 注：同一 item 多个 P31 会产生多行；`seen` 去重已处理（取第一行的 p31）。可接受。

- [ ] **Step 4: 跑确认通过 + 提交** — `… test_wikidata_source.py -v` 全 passed。
```bash
cd backend && poetry run black app/services/enrichment/sources/wikidata.py tests/unit/services/enrichment/test_wikidata_source.py && poetry run isort app/services/enrichment/sources/wikidata.py tests/unit/services/enrichment/test_wikidata_source.py
cd /Users/hongyang/Projects/GoMuseum && git add backend/app/services/enrichment/sources/wikidata.py backend/tests/unit/services/enrichment/test_wikidata_source.py
git commit -m "feat(enrichment): WikidataSource 多类别+图可选+捕获外部ID(P347)"
```

---

## Task 5: JocondeSource（P347 自动发现 + 权威法语事实）

**Files:** Create `backend/app/services/enrichment/sources/joconde.py`；Test `backend/tests/unit/services/enrichment/test_joconde_source.py`

- [ ] **Step 1: 失败测试**
```python
from app.services.enrichment.sources.joconde import JocondeSource


def test_probe_requires_p347():
    s = JocondeSource(session=None)
    assert s.probe({"P347": "000PE004070"}) is True
    assert s.probe({}) is False


def test_enrich_maps_french_fields(monkeypatch):
    # 注入 PoliteSession.get_json 返回 opendatasoft 形态
    captured = {}

    class FakeSession:
        def get_json(self, url, params=None, _transport=None):
            captured["params"] = params
            return {"records": [{"fields": {
                "titre": "Etude : torse",
                "auteur": "RENOIR Pierre Auguste",
                "materiaux_techniques": "peinture à l'huile;toile",
                "mesures": "81 H ; 64.8 L",
                "numero_inventaire": "RF 2740",
            }}]}

    s = JocondeSource(session=FakeSession())
    c = s.enrich("Q1", {"P347": "000PE004070"}, {})
    assert c is not None
    assert c.source == "official"          # 馆方权威优先级
    assert c.qid == "Q1"
    assert c.fields["title_fr"] == "Etude : torse"
    assert c.fields["medium_fr"] == "peinture à l'huile;toile"
    assert c.fields["inventory_number"] == "RF 2740"
    assert "000PE004070" in str(captured["params"])  # 按 REF 查


def test_enrich_returns_none_without_p347():
    assert JocondeSource(session=None).enrich("Q1", {}, {}) is None
```

- [ ] **Step 2: 跑确认失败** — ModuleNotFoundError。

- [ ] **Step 3: 实现 `joconde.py`**
```python
"""JocondeSource：法国国家藏品库(data.culture.gouv.fr base-joconde-extrait)。
经 Wikidata P347 自动发现；提供权威法语一手事实（source=official）。"""

from __future__ import annotations

from app.services.enrichment.sources.base import ObjectContribution, Source

DATASET_URL = "https://data.culture.gouv.fr/api/records/1.0/search/"
DATASET = "base-joconde-extrait"


class JocondeSource(Source):
    name = "joconde"

    def __init__(self, session):
        self._session = session  # PoliteSession（外部注入，便于测试 + 复用限速/缓存）

    def probe(self, external_ids: dict) -> bool:
        return "P347" in external_ids

    def enrich(self, qid: str, external_ids: dict, context: dict):
        ref = external_ids.get("P347")
        if not ref:
            return None
        data = self._session.get_json(
            DATASET_URL, params={"dataset": DATASET, "q": ref, "rows": 1}
        )
        recs = data.get("records") or []
        if not recs:
            return None
        f = recs[0].get("fields", {})
        fields = {
            "title_fr": f.get("titre"),
            "artist_fr": f.get("auteur"),
            "medium_fr": f.get("materiaux_techniques"),
            "dimensions": f.get("mesures"),
            "inventory_number": f.get("numero_inventaire"),
            "provenance_fr": f.get("ancienne_appartenance"),
            "exhibitions_fr": f.get("exposition"),
            "bibliography_fr": f.get("bibliographie"),
        }
        return ObjectContribution(
            source="official", qid=qid, fields=fields, raw={"joconde": f}
        )

    def fetch(self, cfg):  # 非脊柱源，不整馆抓
        return []
```

- [ ] **Step 4: 跑确认通过 + 提交** — 预期 3 passed。
```bash
cd backend && poetry run black app/services/enrichment/sources/joconde.py tests/unit/services/enrichment/test_joconde_source.py && poetry run isort app/services/enrichment/sources/joconde.py tests/unit/services/enrichment/test_joconde_source.py
cd /Users/hongyang/Projects/GoMuseum && git add backend/app/services/enrichment/sources/joconde.py backend/tests/unit/services/enrichment/test_joconde_source.py
git commit -m "feat(enrichment): JocondeSource(P347自动发现+权威法语事实,source=official)"
```

---

## Task 6: WikipediaSource（多源语言叙事素材）

**Files:** Create `backend/app/services/enrichment/sources/wikipedia.py`；Test `backend/tests/unit/services/enrichment/test_wikipedia_source.py`

- [ ] **Step 1: 失败测试**
```python
from app.services.enrichment.sources.wikipedia import WikipediaSource


def test_enrich_pulls_extracts_for_en_and_country_lang():
    calls = []

    class FakeSession:
        def get_json(self, url, params=None, _transport=None):
            calls.append(url)
            # REST summary 形态
            lang = "fr" if "fr.wikipedia" in url else "en"
            return {"extract": f"extract-{lang}", "title": f"T-{lang}"}

    s = WikipediaSource(session=FakeSession())
    # context 给出各语言的 wikipedia 标题（来自 Wikidata sitelinks，1c 接入；本期直接传）
    c = s.enrich(
        "Q1",
        {},
        {"wiki_titles": {"en": "Bedroom_in_Arles", "fr": "La_Chambre_à_Arles"}},
    )
    assert c is not None
    assert c.source == "wikipedia"
    assert c.fields["extract_en"] == "extract-en"
    assert c.fields["extract_fr"] == "extract-fr"
    assert any("en.wikipedia" in u for u in calls)
    assert any("fr.wikipedia" in u for u in calls)


def test_enrich_none_when_no_titles():
    assert WikipediaSource(session=None).enrich("Q1", {}, {}) is None
```

- [ ] **Step 2: 跑确认失败** — ModuleNotFoundError。

- [ ] **Step 3: 实现 `wikipedia.py`**
```python
"""WikipediaSource：按对象各语言 Wikipedia 标题拉正文摘录（叙事接地素材）。
多源语言（en + 馆所在国语言）；用注入的 PoliteSession（限速/缓存）。"""

from __future__ import annotations

from app.services.enrichment.sources.base import ObjectContribution, Source

REST_SUMMARY = "https://{lang}.wikipedia.org/api/rest_v1/page/summary/{title}"


class WikipediaSource(Source):
    name = "wikipedia"

    def __init__(self, session):
        self._session = session

    def enrich(self, qid: str, external_ids: dict, context: dict):
        titles = (context or {}).get("wiki_titles") or {}
        if not titles:
            return None
        fields = {}
        for lang, title in titles.items():
            data = self._session.get_json(
                REST_SUMMARY.format(lang=lang, title=title)
            )
            extract = data.get("extract")
            if extract:
                fields[f"extract_{lang}"] = extract
        if not fields:
            return None
        return ObjectContribution(
            source="wikipedia", qid=qid, fields=fields, raw={"titles": titles}
        )

    def fetch(self, cfg):  # 非脊柱源
        return []
```
> 注：`wiki_titles`（各语言 Wikipedia 标题）来自 Wikidata sitelinks——本期由测试/调用方直接传 `context`；**fetcher 把 Wikidata sitelinks 标题填进 context 的整合属 1c**（本期只做连接器本身）。

- [ ] **Step 4: 跑确认通过 + 提交** — 预期 2 passed。
```bash
cd backend && poetry run black app/services/enrichment/sources/wikipedia.py tests/unit/services/enrichment/test_wikipedia_source.py && poetry run isort app/services/enrichment/sources/wikipedia.py tests/unit/services/enrichment/test_wikipedia_source.py
cd /Users/hongyang/Projects/GoMuseum && git add backend/app/services/enrichment/sources/wikipedia.py backend/tests/unit/services/enrichment/test_wikipedia_source.py
git commit -m "feat(enrichment): WikipediaSource(多源语言正文摘录,叙事接地素材)"
```

---

## Task 7: 两阶段 Fetcher（脊柱 + 按外部ID 路由 enrich）

**Files:** Modify `backend/app/services/enrichment/fetcher.py`；Test `backend/tests/unit/services/enrichment/test_fetcher.py`（追加）

- [ ] **Step 1: 失败测试（追加）** — 脊柱产对象（带 external_ids）→ 富化源按 probe 路由 enrich → 合并：
```python
def test_two_phase_routes_enrichment_by_external_id():
    from app.services.enrichment.fetcher import Fetcher
    from app.services.enrichment.registry import SourceRegistry
    from app.services.enrichment.sources.base import ObjectContribution, Source

    class FakeSpine(Source):
        name = "wikidata"

        def fetch(self, cfg):
            yield ObjectContribution(
                source="wikidata", qid="Q1",
                fields={"title_en": "A", "external_ids": {"P347": "REF1"}, "popularity": 5},
                raw={},
            )

    class FakeJoconde(Source):
        name = "joconde"

        def probe(self, external_ids):
            return "P347" in external_ids

        def enrich(self, qid, external_ids, context):
            return ObjectContribution(source="official", qid=qid,
                                      fields={"medium_fr": "huile"}, raw={})

        def fetch(self, cfg):
            return []

    class FakeStore:
        def __init__(self): self.pack = None
        def put(self, slug, pack): self.pack = pack; return "key"

    store = FakeStore()
    spine = FakeSpine()
    registry = SourceRegistry([FakeJoconde()])
    f = Fetcher(catalog=_catalog_with_orsay(), spine=spine, registry=registry, pack_store=store)
    f.fetch("orsay")
    obj = store.pack["objects"][0]
    assert obj["qid"] == "Q1"
    assert obj["medium_fr"] == "huile"          # Joconde enrich 合并进来了
    assert obj["sources"].keys() >= {"wikidata", "official"}
```
> `_catalog_with_orsay()` 辅助：构造一个含 orsay 的 MuseumCatalog（参考既有 test_fetcher.py 的构造方式；若已有 helper 复用）。

- [ ] **Step 2: 跑确认失败** — `Fetcher.__init__` 现签名是 `(catalog, sources, pack_store)`，新测试用 `spine=/registry=` → TypeError。

- [ ] **Step 3: 改 `fetcher.py` 为两阶段**
```python
from __future__ import annotations

from datetime import datetime, timezone

from app.services.enrichment.merge import merge_contributions


class Fetcher:
    def __init__(self, catalog, spine, registry, pack_store):
        self._catalog = catalog
        self._spine = spine          # 脊柱源（Wikidata），fetch(cfg)→对象
        self._registry = registry    # 富化源注册表，按外部ID route
        self._pack_store = pack_store

    def fetch(self, slug: str) -> str:
        cfg = self._catalog.get(slug)
        objects = []
        for spine_contrib in self._spine.fetch(cfg):
            qid = spine_contrib.qid
            ext = spine_contrib.fields.get("external_ids", {}) or {}
            contribs = [spine_contrib]
            # 两阶段：按外部ID 路由富化源
            for src in self._registry.route(ext):
                c = src.enrich(qid, ext, {})
                if c is not None:
                    contribs.append(c)
            merged = merge_contributions(contribs)
            image_url = merged.pop("image_url", None)
            objects.append(
                {
                    "qid": qid,
                    "category": merged.get("category", "unknown"),
                    "title_zh": merged.get("title_zh"),
                    "title_en": merged.get("title_en"),
                    "artist_zh": merged.get("artist_zh"),
                    "artist_en": merged.get("artist_en"),
                    "year": merged.get("year"),
                    "inventory_number": merged.get("inventory_number"),
                    "popularity": merged.get("popularity", 0),
                    "attributes": {
                        k: v for k, v in merged.items()
                        if k not in {
                            "qid", "category", "title_zh", "title_en", "artist_zh",
                            "artist_en", "year", "inventory_number", "popularity",
                            "sources", "_conflicts", "external_ids",
                        }
                    },
                    "external_ids": ext,
                    "image": (
                        {"source_url": image_url, "license": None, "credit": None}
                        if image_url else None
                    ),
                    "needs_review": bool(merged.get("_conflicts")),
                    "sources": merged["sources"],
                }
            )
        pack = {
            "museum": {
                "slug": cfg.slug, "qid": cfg.wikidata_qid,
                "name_zh": cfg.name_zh, "name_en": cfg.name_en,
                "city_zh": cfg.city_zh, "city_en": cfg.city_en, "country": cfg.country,
            },
            "objects": objects,
            "fetched_at": datetime.now(timezone.utc).isoformat(),
        }
        return self._pack_store.put(slug, pack)
```
> 把额外的法语/英语描述等富化字段统一收进 `attributes`（loader 在 1c 决定如何落库；本期 pack 里带着即可）。`needs_review` 由 `_conflicts` 触发（§5b）。

- [ ] **Step 4: 跑确认通过 + 提交** — `… test_fetcher.py -v` 全 passed（既有 test_fetcher 用旧签名 `sources=` 的需同步改为新签名 `spine=/registry=`——一并更新既有用例）。
```bash
cd backend && poetry run black app/services/enrichment/fetcher.py tests/unit/services/enrichment/test_fetcher.py && poetry run isort app/services/enrichment/fetcher.py tests/unit/services/enrichment/test_fetcher.py
cd /Users/hongyang/Projects/GoMuseum && git add backend/app/services/enrichment/fetcher.py backend/tests/unit/services/enrichment/test_fetcher.py
git commit -m "feat(enrichment): 两阶段 Fetcher(脊柱+按外部ID路由enrich)"
```

---

## Task 8: 接线 onboard 的 fetch（PoliteSession 注入 + 注册表组装）

**Files:** Modify `backend/scripts/onboard.py`（`cmd_fetch`）；Test：手动/集成（onboard 真实联网验证，不在单测）

- [ ] **Step 1: 改 `cmd_fetch` 组装新依赖**（读现有 `cmd_fetch`，把旧 `Fetcher(catalog, sources=[WikidataSource()], pack_store)` 换为两阶段 + PoliteSession 注入）：
```python
def cmd_fetch(slug: str) -> None:
    from app.services.enrichment.http_client import PoliteSession
    from app.services.enrichment.registry import SourceRegistry
    from app.services.enrichment.sources.joconde import JocondeSource
    from app.services.enrichment.sources.wikipedia import WikipediaSource

    ua = "GoMuseumBot/0.1 (https://gomuseum.app; contact appcraft008@gmail.com)"
    session = PoliteSession(user_agent=ua, min_interval=1.0)
    ps = PackStore(get_object_storage())
    spine = WikidataSource()
    registry = SourceRegistry([JocondeSource(session=session), WikipediaSource(session=session)])
    fetcher = Fetcher(catalog=_catalog(), spine=spine, registry=registry, pack_store=ps)
    key = fetcher.fetch(slug)
    print(f"✓ pack 已写入: {key}")
```
> WikidataSource 也应改用注入 session（统一限速/UA）——本期可保留其内部 `_run_query`(已带 UA)，1c 再统一切到 PoliteSession+SourceCache。本期 onboard 接线以"两阶段 + Joconde/Wikipedia 富化"跑通为准。

- [ ] **Step 2: 跑既有 onboard 单测无回归** — `cd backend && poetry run pytest tests/unit/services/enrichment/test_onboard_cli.py -v`（解析类测试应不受影响；cmd_fetch 无单测，靠真实联网验证）。

- [ ] **Step 3: 提交**
```bash
cd backend && poetry run black scripts/onboard.py && poetry run isort scripts/onboard.py
cd /Users/hongyang/Projects/GoMuseum && git add backend/scripts/onboard.py
git commit -m "feat(enrichment): onboard fetch 接两阶段+PoliteSession+Joconde/Wikipedia富化"
```

---

## 收尾：整体验证

- [ ] **全套 enrichment 单测**：`cd backend && STORAGE_BACKEND=local poetry run pytest tests/unit/services/enrichment/ -v` → 全 passed。
- [ ] **（可选）真实联网冒烟**：在本地或 staging 容器跑 `python scripts/onboard.py orsay fetch`，确认 pack 写入、对象带 `external_ids`、有 P347 的对象 `sources` 含 `official`（Joconde 真实命中）、`needs_review` 合理。**遵守礼貌抓取**。
- [ ] **提 PR**：`feature/content-enrichment-phase1b → staging`（`/pr`）。CI 绿后 squash 合并。本期无 DB 迁移。

---

## Self-Review（计划对照 spec）

- **§18b-1 类别单一真相源**：`category_config`（Task 1）+ WikidataSource 用之（Task 4）✓。category→sections 部分留 1c。
- **§5 多类别抓取/图可选/多源语言**：WikidataSource 多类别 VALUES + P18 OPTIONAL（Task 4）；WikipediaSource en+country_lang（Task 6）✓。SPARQL 层 sitelinks 阈值取（替代 fetch_limit）留 1c（本期保留 fetch_limit/翻页）。
- **§18b-6 外部ID 自动路由**：WikidataSource 捕获 P347（Task 4）+ 两阶段 Fetcher route（Task 7）+ JocondeSource.probe（Task 5）✓。
- **§5b official 优先 + 冲突标 needs_review**：JocondeSource source="official"（Task 5）；Fetcher 用 `_conflicts`→`needs_review`（Task 7）✓。
- **§5 礼貌/缓存**：onboard 注入 PoliteSession（Task 8）；SourceCache 包裹连接器抓取留 1c 统一接（本期连接器用注入 session，已限速）✓。
- **不在本期**：SPARQL 层 sitelinks 阈值、QID redirect、WikidataSource 切 PoliteSession+SourceCache、fetcher 填 wiki_titles 进 context、loader 用 needs_review/external_ids 落库、多类别 seed 骨架、馆名城市多语言补全 = **1c**。
- **类型一致**：`category_for(qid)->str`、`MuseumConfig(...,categories,country_lang)`、`Source.enrich(qid,external_ids,context)->ObjectContribution|None`、`Source.probe(external_ids)->bool`、`Fetcher(catalog,spine,registry,pack_store)`、`JocondeSource(session)/.enrich`、`WikipediaSource(session)/.enrich`、`ObjectContribution(source,qid,fields,raw)` 跨任务一致 ✓。
