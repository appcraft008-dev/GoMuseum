# 博物馆富化管线 v1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把"加一个新博物馆"做成可靠流程：fetch（Wikidata，源可扩）→ 落版本化 pack 到 R2 → staging 装样本验证 → prod 装全量（同一 pack）。

**Architecture:** 三阶段（FETCH→LOAD），源可插拔（v1 仅 Wikidata），环境感知（staging 样本/prod 全量取自同一 R2 artifact）。新增 `backend/app/services/enrichment/` 包 + `onboard` CLI；`museum_object` 加 `sources` JSONB 存各源原始包。

**Tech Stack:** Python 3.11 / SQLAlchemy / Alembic / PostgreSQL(JSONB) / Cloudflare R2（经现有 `ObjectStorage` 抽象）/ `requests`（Wikidata SPARQL）/ PyYAML / pytest。

**Spec:** `docs/superpowers/specs/2026-06-16-museum-enrichment-pipeline-v1-design.md`

---

## 共享类型（贯穿全计划，先看一遍再动手）

- `MuseumConfig`（dataclass，见 Task 2）：`slug, name_zh, name_en, city_zh, city_en, country, wikidata_qid, category_filter, fetch_limit, sample_size, sample_qids: list[str]`。
- `ObjectContribution`（dataclass，见 Task 3）：`source: str, qid: str, fields: dict, raw: dict`。
- **pack 格式**（dict，Fetcher 产出 / Loader 消费）：
  ```python
  {
    "museum": {"slug","qid","name_zh","name_en","city_zh","city_en","country"},
    "objects": [
      { "qid","category","title_zh","title_en","artist_zh","artist_en",
        "year","period_zh","period_en","inventory_number","popularity","attributes",
        "image": {"source_url","license","credit"} | None,
        "sources": {"wikidata": {"raw": {...}, "fetched_at": "ISO8601"}} }
    ],
    "fetched_at": "ISO8601",
    "source_versions": {"wikidata": "v1"}
  }
  ```
- `museum_object.attributes` 已存在（canonical 补充结构化属性）；本计划**新增** `museum_object.sources`（各源原始包）。

依赖安装（若缺）：`pyyaml` 加入 `backend/pyproject.toml` 的 deps（Task 2 Step 0 处理）。

---

## Task 1: Schema —— museum_object 加 `sources` JSONB

**Files:**
- Modify: `backend/app/models/museum_object.py`
- Create: `backend/alembic/versions/e1a1_add_object_sources.py`
- Test: `backend/tests/unit/models/test_museum_object_sources.py`

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/unit/models/test_museum_object_sources.py
from app.models.museum_object import MuseumObject


def test_museum_object_has_sources_column_default_dict():
    obj = MuseumObject()
    # 模型列定义存在且默认空 dict（SQLAlchemy 在 flush 时填默认；这里验证列已声明）
    assert "sources" in MuseumObject.__table__.columns
    col = MuseumObject.__table__.columns["sources"]
    assert col.nullable is False
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && pytest tests/unit/models/test_museum_object_sources.py -v`
Expected: FAIL（`KeyError: 'sources'` —— 列不存在）

- [ ] **Step 3: 加列**

在 `backend/app/models/museum_object.py` 的 `MuseumObject` 类里，紧挨现有 `attributes` 列之后加：

```python
    # 各源原始包 + provenance：{"wikidata": {"raw": {...}, "fetched_at": "..."}}
    sources = Column(
        MutableDict.as_mutable(JSON().with_variant(JSONB, "postgresql")),
        nullable=False,
        default=dict,
        server_default="{}",
    )
```

（`MutableDict`/`JSON`/`JSONB` 现有 import 已具备，与 `attributes` 同款。）

- [ ] **Step 4: 跑测试确认通过**

Run: `cd backend && pytest tests/unit/models/test_museum_object_sources.py -v`
Expected: PASS

- [ ] **Step 5: 写 alembic 迁移**

```python
# backend/alembic/versions/e1a1_add_object_sources.py
"""add museum_object.sources jsonb

Revision ID: e1a1_add_object_sources
Revises: d6ca257376ac
Create Date: 2026-06-16
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "e1a1_add_object_sources"
down_revision = "d6ca257376ac"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "museum_objects",
        sa.Column("sources", JSONB(), nullable=False, server_default="{}"),
    )


def downgrade() -> None:
    op.drop_column("museum_objects", "sources")
```

- [ ] **Step 6: 验证迁移链单 head + 可升级**

Run: `cd backend && alembic heads && alembic upgrade head`
Expected: 单一 head `e1a1_add_object_sources`；升级无报错（PostgreSQL）。

- [ ] **Step 7: Commit**

```bash
git add backend/app/models/museum_object.py backend/alembic/versions/e1a1_add_object_sources.py backend/tests/unit/models/test_museum_object_sources.py
git commit -m "feat(schema): museum_object 加 sources JSONB(各源原始包)"
```

---

## Task 2: MuseumCatalog + MuseumConfig（museums.yaml）

**Files:**
- Create: `backend/museums.yaml`
- Create: `backend/app/services/enrichment/__init__.py`（空）
- Create: `backend/app/services/enrichment/catalog.py`
- Test: `backend/tests/unit/services/enrichment/__init__.py`（空）, `backend/tests/unit/services/enrichment/test_catalog.py`
- Modify: `backend/pyproject.toml`（加 `pyyaml`）

- [ ] **Step 0: 加依赖 pyyaml**

在 `backend/pyproject.toml` 的 `[project] dependencies`（或 poetry deps）里加 `"pyyaml>=6.0"`，然后 `cd backend && pip install -e ".[dev,test]"`。

- [ ] **Step 1: 写 museums.yaml（orsay 配置）**

```yaml
# backend/museums.yaml —— 馆配置：加一个馆 = 加一段
museums:
  orsay:
    name_zh: 奥赛博物馆
    name_en: Musée d'Orsay
    city_zh: 巴黎
    city_en: Paris
    country: FR
    wikidata_qid: Q23402
    category_filter: Q3305213   # 绘画；以后加雕塑 Q860861 等
    fetch_limit: 300
    sample_size: 30
    sample_qids: []             # 可选：刻意纳入的边界 QID
```

- [ ] **Step 2: 写失败测试**

```python
# backend/tests/unit/services/enrichment/test_catalog.py
import pytest
from app.services.enrichment.catalog import MuseumCatalog, MuseumConfig


def test_get_returns_typed_config():
    cat = MuseumCatalog.from_file("museums.yaml")
    cfg = cat.get("orsay")
    assert isinstance(cfg, MuseumConfig)
    assert cfg.slug == "orsay"
    assert cfg.wikidata_qid == "Q23402"
    assert cfg.sample_size == 30
    assert cfg.sample_qids == []


def test_unknown_slug_raises():
    cat = MuseumCatalog.from_file("museums.yaml")
    with pytest.raises(KeyError):
        cat.get("nope")
```

- [ ] **Step 3: 跑测试确认失败**

Run: `cd backend && pytest tests/unit/services/enrichment/test_catalog.py -v`
Expected: FAIL（模块不存在）

- [ ] **Step 4: 实现 catalog.py**

```python
# backend/app/services/enrichment/catalog.py
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml


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


class MuseumCatalog:
    def __init__(self, configs: dict[str, MuseumConfig]):
        self._configs = configs

    @classmethod
    def from_file(cls, path: str | Path) -> "MuseumCatalog":
        data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
        configs: dict[str, MuseumConfig] = {}
        for slug, m in (data.get("museums") or {}).items():
            configs[slug] = MuseumConfig(
                slug=slug,
                name_zh=m["name_zh"],
                name_en=m["name_en"],
                city_zh=m["city_zh"],
                city_en=m["city_en"],
                country=m["country"],
                wikidata_qid=m["wikidata_qid"],
                category_filter=m["category_filter"],
                fetch_limit=int(m["fetch_limit"]),
                sample_size=int(m["sample_size"]),
                sample_qids=list(m.get("sample_qids") or []),
            )
        return cls(configs)

    def get(self, slug: str) -> MuseumConfig:
        if slug not in self._configs:
            raise KeyError(f"未知馆: {slug}")
        return self._configs[slug]
```

- [ ] **Step 5: 跑测试确认通过**

Run: `cd backend && pytest tests/unit/services/enrichment/test_catalog.py -v`（在 `backend/` 下跑，相对路径 `museums.yaml` 成立）
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/museums.yaml backend/app/services/enrichment/ backend/tests/unit/services/enrichment/ backend/pyproject.toml
git commit -m "feat(enrichment): MuseumCatalog + museums.yaml 馆配置"
```

---

## Task 3: Source 抽象 + ObjectContribution

**Files:**
- Create: `backend/app/services/enrichment/sources/__init__.py`（空）
- Create: `backend/app/services/enrichment/sources/base.py`
- Test: `backend/tests/unit/services/enrichment/test_source_base.py`

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/unit/services/enrichment/test_source_base.py
from app.services.enrichment.sources.base import ObjectContribution, Source


def test_contribution_holds_source_qid_fields_raw():
    c = ObjectContribution(source="wikidata", qid="Q1", fields={"year": "1866"}, raw={"x": 1})
    assert c.source == "wikidata" and c.qid == "Q1"
    assert c.fields["year"] == "1866" and c.raw == {"x": 1}


def test_source_is_abstract():
    assert hasattr(Source, "fetch")
    import inspect
    assert inspect.isabstract(Source)
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && pytest tests/unit/services/enrichment/test_source_base.py -v`
Expected: FAIL（模块不存在）

- [ ] **Step 3: 实现 base.py**

```python
# backend/app/services/enrichment/sources/base.py
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Iterable

from app.services.enrichment.catalog import MuseumConfig


@dataclass
class ObjectContribution:
    source: str
    qid: str
    fields: dict = field(default_factory=dict)  # canonical 候选字段
    raw: dict = field(default_factory=dict)  # 该源原始包


class Source(ABC):
    name: str

    @abstractmethod
    def fetch(self, cfg: MuseumConfig) -> Iterable[ObjectContribution]:
        """抓某馆 → 逐 object 产出贡献。"""
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd backend && pytest tests/unit/services/enrichment/test_source_base.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/enrichment/sources/ backend/tests/unit/services/enrichment/test_source_base.py
git commit -m "feat(enrichment): Source 抽象 + ObjectContribution"
```

---

## Task 4: Merger（字段级优先级合并）

**Files:**
- Create: `backend/app/services/enrichment/merge.py`
- Test: `backend/tests/unit/services/enrichment/test_merge.py`

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/unit/services/enrichment/test_merge.py
from app.services.enrichment.merge import merge_contributions
from app.services.enrichment.sources.base import ObjectContribution


def test_single_source_projects_fields_and_raw():
    c = ObjectContribution("wikidata", "Q1", {"year": "1866", "title_zh": "起源"}, {"r": 1})
    out = merge_contributions([c])
    assert out["qid"] == "Q1"
    assert out["year"] == "1866"
    assert out["sources"]["wikidata"]["raw"] == {"r": 1}
    assert "fetched_at" in out["sources"]["wikidata"]


def test_precedence_higher_source_wins_per_field():
    wiki = ObjectContribution("wikidata", "Q1", {"year": "1866", "title_zh": "A"}, {})
    manual = ObjectContribution("manual", "Q1", {"year": "1865"}, {})
    out = merge_contributions([wiki, manual])  # 默认 manual > wikidata
    assert out["year"] == "1865"  # manual 覆盖
    assert out["title_zh"] == "A"  # wikidata 独有保留
    assert set(out["sources"].keys()) == {"wikidata", "manual"}
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && pytest tests/unit/services/enrichment/test_merge.py -v`
Expected: FAIL（模块不存在）

- [ ] **Step 3: 实现 merge.py**

```python
# backend/app/services/enrichment/merge.py
from __future__ import annotations

import logging
from datetime import datetime, timezone

from app.services.enrichment.sources.base import ObjectContribution

logger = logging.getLogger(__name__)

# 优先级：越靠后越高。v1 只有 wikidata。
PRECEDENCE = ["wikidata", "official", "manual"]


def _rank(source: str) -> int:
    return PRECEDENCE.index(source) if source in PRECEDENCE else -1


def merge_contributions(contribs: list[ObjectContribution]) -> dict:
    """同一 object 的多源贡献 → canonical dict（含 sources 原始包）。"""
    if not contribs:
        raise ValueError("空贡献")
    qid = contribs[0].qid
    now = datetime.now(timezone.utc).isoformat()

    canonical: dict = {"qid": qid}
    field_source: dict[str, str] = {}
    sources: dict[str, dict] = {}

    for c in sorted(contribs, key=lambda x: _rank(x.source)):  # 低→高，高的后写覆盖
        sources[c.source] = {"raw": c.raw, "fetched_at": now}
        for k, v in c.fields.items():
            if v is None:
                continue
            if k in field_source and _rank(c.source) == _rank(field_source[k]):
                logger.warning("字段冲突 qid=%s field=%s 同级源", qid, k)
            canonical[k] = v
            field_source[k] = c.source

    canonical["sources"] = sources
    return canonical
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd backend && pytest tests/unit/services/enrichment/test_merge.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/enrichment/merge.py backend/tests/unit/services/enrichment/test_merge.py
git commit -m "feat(enrichment): Merger 字段级优先级合并"
```

---

## Task 5: WikidataSource（SPARQL 抓取 + 分页 + 限速）

**说明：** CI 不打真 Wikidata。把"发 HTTP 请求 + 解析"拆成可注入的 `_run_query(sparql) -> list[dict]`，测试时 mock 它。SPARQL 逻辑迁自现有 `backend/scripts/build_museum_pack.py`。

**Files:**
- Create: `backend/app/services/enrichment/sources/wikidata.py`
- Test: `backend/tests/unit/services/enrichment/test_wikidata_source.py`

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/unit/services/enrichment/test_wikidata_source.py
from app.services.enrichment.catalog import MuseumConfig
from app.services.enrichment.sources.wikidata import WikidataSource

CFG = MuseumConfig(
    slug="orsay", name_zh="奥赛", name_en="Orsay", city_zh="巴黎", city_en="Paris",
    country="FR", wikidata_qid="Q23402", category_filter="Q3305213",
    fetch_limit=2, sample_size=2, sample_qids=[],
)

FAKE_ROWS = [
    {"item": {"value": "http://www.wikidata.org/entity/Q12418"},
     "label_zh": {"value": "蒙娜丽莎"}, "label_en": {"value": "Mona Lisa"},
     "creator_zh": {"value": "达芬奇"}, "year": {"value": "1503"},
     "image": {"value": "http://x/ml.jpg"}, "links": {"value": "120"}},
]


def test_fetch_yields_contributions_with_qid_fields_raw(monkeypatch):
    src = WikidataSource()
    monkeypatch.setattr(src, "_run_query", lambda sparql: FAKE_ROWS)
    out = list(src.fetch(CFG))
    assert len(out) == 1
    c = out[0]
    assert c.source == "wikidata"
    assert c.qid == "Q12418"
    assert c.fields["title_zh"] == "蒙娜丽莎"
    assert c.fields["artist_zh"] == "达芬奇"
    assert c.fields["popularity"] == 120
    assert c.fields["category"] == "painting"
    assert c.raw["item"]["value"].endswith("Q12418")
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && pytest tests/unit/services/enrichment/test_wikidata_source.py -v`
Expected: FAIL（模块不存在）

- [ ] **Step 3: 实现 wikidata.py**

```python
# backend/app/services/enrichment/sources/wikidata.py
from __future__ import annotations

import time
from typing import Iterable

import requests

from app.services.enrichment.catalog import MuseumConfig
from app.services.enrichment.sources.base import ObjectContribution, Source

SPARQL_ENDPOINT = "https://query.wikidata.org/sparql"
USER_AGENT = "GoMuseum/0.1 (enrichment; contact: dev@gomuseum.app)"

QUERY = """
SELECT ?item ?label_zh ?label_en ?creator_zh ?creator_en ?year ?image ?links ?inventory WHERE {{
  ?item wdt:P195 wd:{museum} . ?item wdt:P31 wd:{category} . ?item wdt:P18 ?image .
  ?item wikibase:sitelinks ?links .
  OPTIONAL {{ ?item rdfs:label ?label_zh . FILTER(LANG(?label_zh)="zh") }}
  OPTIONAL {{ ?item rdfs:label ?label_en . FILTER(LANG(?label_en)="en") }}
  OPTIONAL {{ ?item wdt:P170 ?creator .
    OPTIONAL {{ ?creator rdfs:label ?creator_zh . FILTER(LANG(?creator_zh)="zh") }}
    OPTIONAL {{ ?creator rdfs:label ?creator_en . FILTER(LANG(?creator_en)="en") }} }}
  OPTIONAL {{ ?item wdt:P571 ?date . BIND(YEAR(?date) AS ?year) }}
  OPTIONAL {{ ?item wdt:P217 ?inventory }}
}} ORDER BY DESC(?links) LIMIT {limit} OFFSET {offset}
"""

_PAGE = 200  # 每页；大馆翻页


class WikidataSource(Source):
    name = "wikidata"

    def _run_query(self, sparql: str) -> list[dict]:
        r = requests.get(
            SPARQL_ENDPOINT,
            params={"query": sparql, "format": "json"},
            headers={"User-Agent": USER_AGENT, "Accept": "application/sparql-results+json"},
            timeout=60,
        )
        r.raise_for_status()
        return r.json()["results"]["bindings"]

    def fetch(self, cfg: MuseumConfig) -> Iterable[ObjectContribution]:
        seen: set[str] = set()
        fetched = 0
        offset = 0
        while fetched < cfg.fetch_limit:
            page = min(_PAGE, cfg.fetch_limit - fetched)
            rows = self._run_query(
                QUERY.format(
                    museum=cfg.wikidata_qid, category=cfg.category_filter,
                    limit=page, offset=offset,
                )
            )
            if not rows:
                break
            for row in rows:
                qid = row["item"]["value"].rsplit("/", 1)[-1]
                if qid in seen:
                    continue
                seen.add(qid)
                yield ObjectContribution(
                    source="wikidata", qid=qid, raw=row,
                    fields={
                        "category": "painting",
                        "title_zh": _v(row, "label_zh"),
                        "title_en": _v(row, "label_en"),
                        "artist_zh": _v(row, "creator_zh"),
                        "artist_en": _v(row, "creator_en"),
                        "year": _v(row, "year"),
                        "inventory_number": _v(row, "inventory"),
                        "popularity": int(_v(row, "links") or 0),
                        "image_url": _v(row, "image"),
                    },
                )
            fetched += len(rows)
            offset += len(rows)
            time.sleep(1)  # 礼貌限速


def _v(row: dict, key: str):
    cell = row.get(key)
    return cell["value"] if cell else None
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd backend && pytest tests/unit/services/enrichment/test_wikidata_source.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/enrichment/sources/wikidata.py backend/tests/unit/services/enrichment/test_wikidata_source.py
git commit -m "feat(enrichment): WikidataSource(SPARQL+分页+限速,HTTP 可注入)"
```

---

## Task 6: PackStore（R2 存取 pack）

**Files:**
- Create: `backend/app/services/enrichment/pack_store.py`
- Test: `backend/tests/unit/services/enrichment/test_pack_store.py`

- [ ] **Step 1: 写失败测试**（用假 storage，不打真 R2）

```python
# backend/tests/unit/services/enrichment/test_pack_store.py
from app.services.enrichment.pack_store import PackStore


class FakeStorage:
    def __init__(self):
        self.blobs = {}

    def put(self, key, data, content_type):
        self.blobs[key] = data

    def get(self, key):
        return self.blobs.get(key)


def test_put_returns_versioned_key_and_get_roundtrips():
    st = FakeStorage()
    ps = PackStore(st)
    pack = {"museum": {"slug": "orsay"}, "objects": [{"qid": "Q1"}]}
    key = ps.put("orsay", pack)
    assert key.startswith("museum-packs/orsay/") and key.endswith(".json")
    assert ps.get(key) == pack


def test_latest_key_picks_most_recent():
    st = FakeStorage()
    ps = PackStore(st)
    k1 = ps.put("orsay", {"a": 1})
    k2 = ps.put("orsay", {"a": 2})
    assert ps.latest_key("orsay", listing=[k1, k2]) == max(k1, k2)
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && pytest tests/unit/services/enrichment/test_pack_store.py -v`
Expected: FAIL（模块不存在）

- [ ] **Step 3: 实现 pack_store.py**

```python
# backend/app/services/enrichment/pack_store.py
from __future__ import annotations

import json
from datetime import datetime, timezone


class PackStore:
    """版本化 pack 存取，复用 ObjectStorage（R2/local）。"""

    def __init__(self, storage):
        self._storage = storage

    def _key(self, slug: str) -> str:
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")
        return f"museum-packs/{slug}/{ts}.json"

    def put(self, slug: str, pack: dict) -> str:
        key = self._key(slug)
        self._storage.put(
            key, json.dumps(pack, ensure_ascii=False).encode("utf-8"), "application/json"
        )
        return key

    def get(self, key: str) -> dict:
        data = self._storage.get(key)
        if data is None:
            raise FileNotFoundError(key)
        return json.loads(data)

    def latest_key(self, slug: str, listing: list[str]) -> str | None:
        ks = [k for k in listing if k.startswith(f"museum-packs/{slug}/")]
        return max(ks) if ks else None  # 时间戳 key 字典序 = 时间序
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd backend && pytest tests/unit/services/enrichment/test_pack_store.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/enrichment/pack_store.py backend/tests/unit/services/enrichment/test_pack_store.py
git commit -m "feat(enrichment): PackStore 版本化 pack 存取(复用 ObjectStorage)"
```

---

## Task 7: Fetcher（编排源 + 合并 → 组 pack → 写 R2）

**Files:**
- Create: `backend/app/services/enrichment/fetcher.py`
- Test: `backend/tests/unit/services/enrichment/test_fetcher.py`

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/unit/services/enrichment/test_fetcher.py
from app.services.enrichment.catalog import MuseumConfig
from app.services.enrichment.fetcher import Fetcher
from app.services.enrichment.sources.base import ObjectContribution

CFG = MuseumConfig("orsay", "奥赛", "Orsay", "巴黎", "Paris", "FR", "Q23402",
                   "Q3305213", 10, 5, [])


class FakeSource:
    name = "wikidata"

    def fetch(self, cfg):
        yield ObjectContribution("wikidata", "Q1",
                                 {"title_zh": "起源", "image_url": "http://x/a.jpg"}, {"r": 1})
        yield ObjectContribution("wikidata", "Q2", {"title_zh": "午餐"}, {"r": 2})


class FakeCatalog:
    def get(self, slug):
        return CFG


class FakePackStore:
    def __init__(self):
        self.saved = None

    def put(self, slug, pack):
        self.saved = pack
        return f"museum-packs/{slug}/X.json"


def test_fetch_builds_pack_with_museum_and_objects():
    ps = FakePackStore()
    f = Fetcher(catalog=FakeCatalog(), sources=[FakeSource()], pack_store=ps)
    key = f.fetch("orsay")
    assert key.endswith(".json")
    pack = ps.saved
    assert pack["museum"]["slug"] == "orsay" and pack["museum"]["qid"] == "Q23402"
    qids = {o["qid"] for o in pack["objects"]}
    assert qids == {"Q1", "Q2"}
    q1 = next(o for o in pack["objects"] if o["qid"] == "Q1")
    assert q1["title_zh"] == "起源"
    assert q1["image"]["source_url"] == "http://x/a.jpg"
    assert q1["sources"]["wikidata"]["raw"] == {"r": 1}
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && pytest tests/unit/services/enrichment/test_fetcher.py -v`
Expected: FAIL（模块不存在）

- [ ] **Step 3: 实现 fetcher.py**

```python
# backend/app/services/enrichment/fetcher.py
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone

from app.services.enrichment.merge import merge_contributions


class Fetcher:
    def __init__(self, catalog, sources: list, pack_store):
        self._catalog = catalog
        self._sources = sources
        self._pack_store = pack_store

    def fetch(self, slug: str) -> str:
        cfg = self._catalog.get(slug)
        by_qid = defaultdict(list)
        for src in self._sources:
            for contrib in src.fetch(cfg):
                by_qid[contrib.qid].append(contrib)

        objects = []
        for qid, contribs in by_qid.items():
            merged = merge_contributions(contribs)
            image_url = merged.pop("image_url", None)
            obj = {
                "qid": qid,
                "category": merged.get("category", "painting"),
                "title_zh": merged.get("title_zh"),
                "title_en": merged.get("title_en"),
                "artist_zh": merged.get("artist_zh"),
                "artist_en": merged.get("artist_en"),
                "year": merged.get("year"),
                "period_zh": merged.get("period_zh"),
                "period_en": merged.get("period_en"),
                "inventory_number": merged.get("inventory_number"),
                "popularity": merged.get("popularity", 0),
                "attributes": merged.get("attributes", {}),
                "image": {"source_url": image_url, "license": None, "credit": None}
                if image_url else None,
                "sources": merged["sources"],
            }
            objects.append(obj)

        pack = {
            "museum": {
                "slug": cfg.slug, "qid": cfg.wikidata_qid,
                "name_zh": cfg.name_zh, "name_en": cfg.name_en,
                "city_zh": cfg.city_zh, "city_en": cfg.city_en, "country": cfg.country,
            },
            "objects": objects,
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "source_versions": {s.name: "v1" for s in self._sources},
        }
        return self._pack_store.put(slug, pack)
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd backend && pytest tests/unit/services/enrichment/test_fetcher.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/enrichment/fetcher.py backend/tests/unit/services/enrichment/test_fetcher.py
git commit -m "feat(enrichment): Fetcher 编排源+合并→组 pack→写 R2"
```

---

## Task 8: Loader（读 pack → 幂等 upsert → raw 入 sources，样本/全量）

**说明：** 复用现有 `app.services.object_importer.upsert_museum/upsert_object`（幂等 by qid）。Loader 额外：① 样本筛选（popularity top-N + sample_qids）② upsert 后把 `obj["sources"]` 写进行的 `sources` 列 ③ **不触碰 object_content_sections**。用真 DB session（integration 测试在 Task 11；这里 Task 8 用 unit + 内存逻辑测样本筛选，DB upsert 留集成）。

**Files:**
- Create: `backend/app/services/enrichment/loader.py`
- Test: `backend/tests/unit/services/enrichment/test_loader_sampling.py`

- [ ] **Step 1: 写失败测试（样本筛选逻辑，纯函数）**

```python
# backend/tests/unit/services/enrichment/test_loader_sampling.py
from app.services.enrichment.loader import select_sample


def _objs():
    return [{"qid": f"Q{i}", "popularity": i} for i in range(10)]  # Q0..Q9，热度=i


def test_sample_takes_top_n_by_popularity():
    out = select_sample(_objs(), sample_size=3, sample_qids=[])
    assert {o["qid"] for o in out} == {"Q9", "Q8", "Q7"}


def test_sample_includes_fixed_qids_dedup():
    out = select_sample(_objs(), sample_size=2, sample_qids=["Q0"])
    qids = {o["qid"] for o in out}
    assert "Q0" in qids  # 固定 QID 强制纳入
    assert "Q9" in qids and "Q8" in qids  # top-2
    assert len(out) == 3  # 去重后 3 条
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && pytest tests/unit/services/enrichment/test_loader_sampling.py -v`
Expected: FAIL（模块不存在）

- [ ] **Step 3: 实现 loader.py**

```python
# backend/app/services/enrichment/loader.py
from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.museum_object import MuseumObject
from app.services.object_importer import upsert_museum, upsert_object


def select_sample(objects: list[dict], sample_size: int, sample_qids: list[str]) -> list[dict]:
    by_qid = {o["qid"]: o for o in objects}
    top = sorted(objects, key=lambda o: o.get("popularity", 0), reverse=True)[:sample_size]
    chosen = {o["qid"]: o for o in top}
    for q in sample_qids:
        if q in by_qid:
            chosen[q] = by_qid[q]
    return list(chosen.values())


def load(db: Session, pack: dict, *, sample: bool) -> int:
    """把 pack 灌入 db。sample=True 只灌样本。返回入库 object 数。"""
    museum = upsert_museum(db, pack["museum"])
    objects = pack["objects"]
    if sample:
        # sample_size/sample_qids 由调用方塞进 pack["_sample"]（CLI 注入）
        cfg = pack.get("_sample", {})
        objects = select_sample(objects, cfg.get("size", 30), cfg.get("qids", []))

    n = 0
    for art in objects:
        obj = upsert_object(db, museum.id, art)  # 幂等 by qid，写 canonical + attributes
        # 写各源原始包到 sources 列（不碰 object_content_sections）
        obj.sources = art.get("sources", {})
        # 主图（若有）经 upsert_object 内部处理 art["image"]；此处仅确保不破坏
        n += 1
    db.commit()
    return n
```

> 注：确认现有 `upsert_object` 接受 `art["image"]`（dict 形态）；若其期望的是 `art["image"]` 为 url 字符串，Fetcher 的 `obj["image"]` 结构需与之对齐（实现时对照 `object_importer.py` 的 image 处理分支，必要时在本 Task 调整 Fetcher 的 image 字段形态以匹配——这是 Task 7/8 间的接口一致性点）。

- [ ] **Step 4: 跑测试确认通过**

Run: `cd backend && pytest tests/unit/services/enrichment/test_loader_sampling.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/enrichment/loader.py backend/tests/unit/services/enrichment/test_loader_sampling.py
git commit -m "feat(enrichment): Loader 样本筛选 + 幂等灌库 + raw 入 sources"
```

---

## Task 9: SampleReporter（覆盖率/分布/异常报告）

**Files:**
- Create: `backend/app/services/enrichment/report.py`
- Test: `backend/tests/unit/services/enrichment/test_report.py`

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/unit/services/enrichment/test_report.py
from app.services.enrichment.report import build_report


def test_report_counts_coverage_and_distribution():
    objs = [
        {"qid": "Q1", "category": "painting", "title_zh": "A", "title_en": "A",
         "artist_zh": "x", "year": "1866", "image": {"source_url": "u"}},
        {"qid": "Q2", "category": "sculpture", "title_zh": None, "title_en": "B",
         "artist_zh": None, "year": None, "image": None},
    ]
    rep = build_report("orsay", objs)
    assert rep["total"] == 2
    assert rep["coverage"]["image"] == 0.5
    assert rep["coverage"]["artist_zh"] == 0.5
    assert rep["coverage"]["title_zh"] == 0.5
    assert rep["category_dist"] == {"painting": 1, "sculpture": 1}
    assert "Q2" in rep["anomalies"]["missing_image"]


def test_report_renders_markdown():
    md = build_report("orsay", [{"qid": "Q1", "category": "painting",
                                 "title_zh": "A", "title_en": "A", "artist_zh": "x",
                                 "year": "1", "image": {"source_url": "u"}}],
                      as_markdown=True)
    assert "# 抽样报告: orsay" in md
    assert "覆盖率" in md
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && pytest tests/unit/services/enrichment/test_report.py -v`
Expected: FAIL（模块不存在）

- [ ] **Step 3: 实现 report.py**

```python
# backend/app/services/enrichment/report.py
from __future__ import annotations

from collections import Counter

_FIELDS = ["image", "artist_zh", "year", "title_zh", "title_en"]


def _has(o: dict, field: str) -> bool:
    if field == "image":
        return bool(o.get("image"))
    return bool(o.get(field))


def build_report(slug: str, objects: list[dict], as_markdown: bool = False):
    total = len(objects) or 1
    coverage = {f: round(sum(_has(o, f) for o in objects) / total, 3) for f in _FIELDS}
    category_dist = dict(Counter(o.get("category", "?") for o in objects))
    anomalies = {
        "missing_image": [o["qid"] for o in objects if not o.get("image")][:20],
        "missing_zh_label": [o["qid"] for o in objects if not o.get("title_zh")][:20],
    }
    rep = {
        "slug": slug, "total": len(objects),
        "coverage": coverage, "category_dist": category_dist, "anomalies": anomalies,
    }
    if not as_markdown:
        return rep
    lines = [f"# 抽样报告: {slug}", "", f"- 对象数: {rep['total']}", "", "## 覆盖率"]
    lines += [f"- {f}: {coverage[f]*100:.0f}%" for f in _FIELDS]
    lines += ["", "## 类型分布"] + [f"- {k}: {v}" for k, v in category_dist.items()]
    lines += ["", "## 异常",
              f"- 缺主图: {len(anomalies['missing_image'])} 条 {anomalies['missing_image']}",
              f"- 缺中文标签: {len(anomalies['missing_zh_label'])} 条"]
    return "\n".join(lines)
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd backend && pytest tests/unit/services/enrichment/test_report.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/enrichment/report.py backend/tests/unit/services/enrichment/test_report.py
git commit -m "feat(enrichment): SampleReporter 覆盖率/分布/异常报告"
```

---

## Task 10: onboard CLI（fetch / load 子命令）

**Files:**
- Create: `backend/scripts/onboard.py`
- Test: `backend/tests/unit/services/enrichment/test_onboard_cli.py`

- [ ] **Step 1: 写失败测试**（测参数解析 + 分发，不真连 DB/R2）

```python
# backend/tests/unit/services/enrichment/test_onboard_cli.py
from scripts.onboard import build_parser


def test_parser_fetch():
    ns = build_parser().parse_args(["orsay", "fetch"])
    assert ns.slug == "orsay" and ns.command == "fetch"


def test_parser_load_staging_sample():
    ns = build_parser().parse_args(
        ["orsay", "load", "--target", "staging", "--pack", "k.json", "--sample"]
    )
    assert ns.command == "load" and ns.target == "staging"
    assert ns.pack == "k.json" and ns.sample is True
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && pytest tests/unit/services/enrichment/test_onboard_cli.py -v`
Expected: FAIL（模块不存在）

- [ ] **Step 3: 实现 scripts/onboard.py**

```python
# backend/scripts/onboard.py
"""上馆 CLI：fetch（抓→R2 pack）/ load（pack→DB，staging 样本/prod 全量）。

用法：
  python scripts/onboard.py <slug> fetch
  python scripts/onboard.py <slug> load --target staging --pack <key> --sample
  python scripts/onboard.py <slug> load --target prod    --pack <key>
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.database import SessionLocal  # noqa: E402
from app.services.enrichment.catalog import MuseumCatalog  # noqa: E402
from app.services.enrichment.fetcher import Fetcher  # noqa: E402
from app.services.enrichment.loader import load  # noqa: E402
from app.services.enrichment.pack_store import PackStore  # noqa: E402
from app.services.enrichment.report import build_report  # noqa: E402
from app.services.enrichment.sources.wikidata import WikidataSource  # noqa: E402
from app.services.storage import get_object_storage  # noqa: E402

CATALOG_PATH = Path(__file__).resolve().parents[1] / "museums.yaml"


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="上馆富化管线")
    p.add_argument("slug")
    sub = p.add_subparsers(dest="command", required=True)
    sub.add_parser("fetch")
    lo = sub.add_parser("load")
    lo.add_argument("--target", choices=["staging", "prod"], required=True)
    lo.add_argument("--pack", default=None)
    lo.add_argument("--sample", action="store_true")
    return p


def _catalog() -> MuseumCatalog:
    return MuseumCatalog.from_file(CATALOG_PATH)


def cmd_fetch(slug: str) -> None:
    ps = PackStore(get_object_storage())
    fetcher = Fetcher(catalog=_catalog(), sources=[WikidataSource()], pack_store=ps)
    key = fetcher.fetch(slug)
    print(f"✓ pack 已写入: {key}")


def cmd_load(slug: str, pack_key: str, sample: bool) -> None:
    ps = PackStore(get_object_storage())
    if not pack_key:
        raise SystemExit("请用 --pack <key> 指定 pack")
    pack = ps.get(pack_key)
    if sample:
        cfg = _catalog().get(slug)
        pack["_sample"] = {"size": cfg.sample_size, "qids": cfg.sample_qids}
    db = SessionLocal()
    try:
        n = load(db, pack, sample=sample)
    finally:
        db.close()
    print(f"✓ 入库 {n} 件 (sample={sample})")
    if sample:
        objs = pack["objects"]
        print(build_report(slug, objs, as_markdown=True))


def main(argv=None) -> None:
    ns = build_parser().parse_args(argv)
    if ns.command == "fetch":
        cmd_fetch(ns.slug)
    else:
        cmd_load(ns.slug, ns.pack, ns.sample)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd backend && pytest tests/unit/services/enrichment/test_onboard_cli.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/scripts/onboard.py backend/tests/unit/services/enrichment/test_onboard_cli.py
git commit -m "feat(enrichment): onboard CLI(fetch/load 子命令)"
```

---

## Task 11: 集成测试（全流程，mock Wikidata + 真 DB）

**说明：** 用现有 integration 测试夹具（真 pg session）。mock `WikidataSource._run_query`，本地内存 storage 做 PackStore，跑 `fetch → load staging --sample → load prod 全量`，断言 DB 状态 + 幂等 + 不碰 sections。

**Files:**
- Create: `backend/tests/integration/test_onboard_flow.py`

- [ ] **Step 1: 写集成测试**

```python
# backend/tests/integration/test_onboard_flow.py
import json

import pytest

from app.models.museum import Museum
from app.models.museum_object import MuseumObject
from app.services.enrichment.fetcher import Fetcher
from app.services.enrichment.loader import load
from app.services.enrichment.pack_store import PackStore
from app.services.enrichment.catalog import MuseumConfig
from app.services.enrichment.sources.wikidata import WikidataSource

CFG = MuseumConfig("orsay", "奥赛", "Orsay", "巴黎", "Paris", "FR", "Q23402",
                   "Q3305213", 5, 2, [])

ROWS = [
    {"item": {"value": f"http://www.wikidata.org/entity/Q{i}"},
     "label_zh": {"value": f"作品{i}"}, "image": {"value": f"http://x/{i}.jpg"},
     "links": {"value": str(100 - i)}} for i in range(5)
]


class MemStorage:
    def __init__(self):
        self.b = {}

    def put(self, k, data, ct):
        self.b[k] = data

    def get(self, k):
        return self.b.get(k)


class OneCatalog:
    def get(self, slug):
        return CFG


def _fetch_pack(monkeypatch):
    src = WikidataSource()
    monkeypatch.setattr(src, "_run_query", lambda sparql: ROWS if "OFFSET 0" in sparql else [])
    ps = PackStore(MemStorage())
    key = Fetcher(catalog=OneCatalog(), sources=[src], pack_store=ps).fetch("orsay")
    return ps, key


def test_full_flow_sample_then_full(db_session, monkeypatch):
    ps, key = _fetch_pack(monkeypatch)
    pack = ps.get(key)

    # staging 样本(size=2)
    sample_pack = json.loads(json.dumps(pack))
    sample_pack["_sample"] = {"size": 2, "qids": []}
    n_sample = load(db_session, sample_pack, sample=True)
    assert n_sample == 2
    assert db_session.query(MuseumObject).count() == 2

    # prod 全量(同一 pack)→ upsert 补齐到 5
    n_full = load(db_session, pack, sample=False)
    assert n_full == 5
    assert db_session.query(MuseumObject).count() == 5  # 幂等：样本那 2 件不重复
    assert db_session.query(Museum).filter_by(slug="orsay").count() == 1

    # sources 原始包已入库
    obj = db_session.query(MuseumObject).filter_by(qid="Q0").one()
    assert "wikidata" in obj.sources
```

> `db_session` fixture：沿用现有 integration 测试（如 `test_object_importer.py`）的同名 fixture；若名称不同，对照该文件改用其真 pg session fixture。

- [ ] **Step 2: 跑测试确认通过**

Run: `cd backend && pytest tests/integration/test_onboard_flow.py -v`
Expected: PASS（需本地/CI 的 pg；CI 已有 postgres service）

- [ ] **Step 3: Commit**

```bash
git add backend/tests/integration/test_onboard_flow.py
git commit -m "test(enrichment): 上馆全流程集成测试(mock Wikidata+真DB)"
```

---

## Task 12: 文档 + 收尾

**Files:**
- Modify: `docs/architecture/data-and-content-architecture.md`（§10 待确认项 1-4 标记"v1 已设计/实现"）

- [ ] **Step 1: 更新数据架构文档 §10**

把 §10 待确认项中「1. 通用 schema + JSONB」「3. 富化管线三段拆分」「4. sample 脚本标准」标注为「v1 已落地，见 specs/2026-06-16-museum-enrichment-pipeline-v1」。

- [ ] **Step 2: 全量测试 + 格式**

Run: `cd backend && pytest tests/unit/services/enrichment tests/unit/models/test_museum_object_sources.py tests/integration/test_onboard_flow.py -v && black backend && isort backend`
Expected: 全绿、格式无改动。

- [ ] **Step 3: Commit**

```bash
git add docs/architecture/data-and-content-architecture.md
git commit -m "docs: 数据架构 §10 标注富化管线 v1 已落地"
```

---

## Self-Review 检查表（实现者动手前对照）

- **Spec 覆盖**：§3 schema→Task1；§4 组件→Task2-10；§5 合并→Task4；§6 artifact→Task6；§7 CLI→Task10；§8 样本+报告→Task8/9；§9 分页→Task5；§10 幂等→Task8/11；§11 测试→各 Task+Task11；§13 验收→Task11 断言。
- **接口一致性关键点**：`ObjectContribution(source,qid,fields,raw)` 贯穿 Task3/4/5/7；pack 格式（§共享类型）贯穿 Task6/7/8/11；`MuseumConfig` 字段贯穿 Task2/5/7/8/10。**Task7→Task8 的 `obj["image"]` 形态须与现有 `object_importer.upsert_object` 的 image 处理对齐**（实现 Task8 时对照 `object_importer.py`，必要时回调整 Task7 image 字段——已在 Task8 注明）。
- **环境**：CLI 在后端容器内跑；`--target` 对应各环境 DB；fetch/load 解耦经 R2 pack。
```
