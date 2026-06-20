"""集成测试：上馆全流程 fetch → load staging --sample → load prod 全量。

mock WikidataSource._run_query + time.sleep，使用 SQLite in-memory 真 session。
"""

import json

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.models.museum import Museum
from app.models.museum_object import MuseumObject, ObjectImage
from app.services.enrichment.catalog import MuseumConfig
from app.services.enrichment.fetcher import Fetcher
from app.services.enrichment.loader import load
from app.services.enrichment.pack_store import PackStore
from app.services.enrichment.registry import SourceRegistry
from app.services.enrichment.sources.wikidata import WikidataSource

CFG = MuseumConfig(
    "orsay",
    "奥赛",
    "Orsay",
    "巴黎",
    "Paris",
    "FR",
    "Q23402",
    "Q3305213",
    5,  # fetch_limit
    2,  # sample_size
    [],
)

# Wikidata SPARQL 返回行，模拟 5 件藏品
ROWS = [
    {
        "item": {"value": f"http://www.wikidata.org/entity/Q{i}"},
        "label_zh": {"value": f"作品{i}"},
        "label_en": {"value": f"Work{i}"},
        "image": {"value": f"http://x/{i}.jpg"},
        "links": {"value": str(100 - i)},
    }
    for i in range(5)
]


# ---------- 辅助 stub ----------


class _MemStorage:
    """内存存储 stub，模拟 ObjectStorage (R2/local)。"""

    def __init__(self):
        self._b: dict[str, bytes] = {}

    def put(self, key: str, data: bytes, content_type: str) -> None:
        self._b[key] = data

    def get(self, key: str):
        return self._b.get(key)


class _OneCatalog:
    """只返回 orsay 配置的最小 catalog stub。"""

    def get(self, slug: str) -> MuseumConfig:
        return CFG


# ---------- fixture ----------


@pytest.fixture()
def session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(
        bind=engine,
        tables=[Museum.__table__, MuseumObject.__table__, ObjectImage.__table__],
    )
    yield sessionmaker(bind=engine)()


# ---------- 工具函数 ----------


def _build_pack(monkeypatch) -> tuple[PackStore, str]:
    """运行 Fetcher（mock _run_query + sleep），返回 (pack_store, key)。"""
    src = WikidataSource()

    # _run_query 在 OFFSET 0 时返回 5 行，其他 offset 返回空（fetch_limit=5 只跑一次）
    monkeypatch.setattr(
        src,
        "_run_query",
        lambda sparql: ROWS if "OFFSET 0" in sparql else [],
    )
    # 跳过礼貌限速
    monkeypatch.setattr(
        "app.services.enrichment.sources.wikidata.time.sleep", lambda _: None
    )

    ps = PackStore(_MemStorage())
    key = Fetcher(
        catalog=_OneCatalog(),
        spine=src,
        registry=SourceRegistry([]),
        pack_store=ps,
    ).fetch("orsay")
    return ps, key


# ---------- 测试 ----------


def test_full_flow_sample_then_full(session, monkeypatch):
    """
    Step 1: load sample (size=2) → 入库 2 条
    Step 2: load full       (5 件) → 入库 5 条（幂等 upsert）
    断言：Museum 只有 1 行；Q0 的 sources 包含 wikidata 键。
    """
    ps, key = _build_pack(monkeypatch)
    pack = ps.get(key)

    # --- 样本加载 ---
    sample_pack = json.loads(json.dumps(pack))  # 深拷贝，不改原 pack
    sample_pack["_sample"] = {"size": 2, "qids": []}
    n_sample = load(session, sample_pack, sample=True)
    assert n_sample == 2
    assert session.query(MuseumObject).count() == 2

    # --- 全量加载（幂等 upsert） ---
    n_full = load(session, pack, sample=False)
    assert n_full == 5
    assert session.query(MuseumObject).count() == 5
    assert session.query(Museum).filter_by(slug="orsay").count() == 1

    # --- sources 字段入库验证 ---
    obj = session.query(MuseumObject).filter_by(qid="Q0").one()
    assert "wikidata" in obj.sources
