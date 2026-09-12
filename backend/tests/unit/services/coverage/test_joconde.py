"""Joconde 区域适配器:Reference→Localisation 展陈证据。fake http 注入,不打真网。
canned JSON 摘自真实 tabular-api.data.gouv.fr 响应(2026-09 迁移后)。"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.models.museum import Museum
from app.models.museum_object import MuseumObject, ObjectImage
from app.services.coverage.joconde import (
    enrich_museum_display,
    fetch_joconde_evidence,
)
from app.services.enrichment.sources import joconde as _src
from app.services.object_importer import upsert_museum, upsert_object

CANNED_DATASET = {"resources": [{"id": "csv-rid", "format": "csv"}]}
# 真实表格 API 响应形状(Reference__exact 过滤,命中 1 条)
CANNED_HIT = {
    "meta": {"page": 1, "page_size": 1, "total": 1},
    "data": [
        {
            "Reference": "09880004556",
            "Localisation": "Valence ; musée des beaux-arts",
            "Exposition": None,
            "Nom_officiel_musee": "musée des beaux-arts",
        }
    ],
}
CANNED_EMPTY = {"meta": {"total": 0}, "data": []}


@pytest.fixture(autouse=True)
def _reset_rid_cache():
    """模块级 rid 缓存跨测试会串味。每例清一次。"""
    _src._rid_cache = None
    yield
    _src._rid_cache = None


class _Resp:
    def __init__(self, data, status=200):
        self._data = data
        self.status_code = status

    def json(self):
        return self._data


def _fake_get(data, status=200):
    """dataset 元数据请求恒成功;status 只作用于数据请求 —— 否则"非200→None"
    这条测试会在 rid 解析阶段就短路,测不到它本来要测的那段。"""

    def get(url, params=None, headers=None, timeout=None):
        if url.startswith(_src.DATASET_API):
            return _Resp(CANNED_DATASET)
        return _Resp(data, status)

    return get


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
    m = upsert_museum(s, {"slug": "orsay", "name_en": "Orsay"})
    s.commit()
    return s, m


def test_fetch_parses_localisation():
    """命中 → location 取 localisation,detail 含原始字段摘录。"""
    ev = fetch_joconde_evidence("09880004556", http_get=_fake_get(CANNED_HIT))
    assert ev["location"] == "Valence ; musée des beaux-arts"
    assert "Valence" in ev["detail"]


def test_fetch_not_found_returns_none():
    """无命中 → None(不崩)。"""
    assert (
        fetch_joconde_evidence("00000000000", http_get=_fake_get(CANNED_EMPTY)) is None
    )


def test_fetch_http_error_returns_none():
    """非 200 → None(不崩)。"""
    assert fetch_joconde_evidence("x", http_get=_fake_get({}, status=500)) is None


def test_enrich_writes_evidence_for_object_with_ref(session):
    s, m = session
    upsert_object(
        s,
        m.id,
        {
            "qid": "Q1",
            "title_en": "A",
            "attributes": {"external_ids": {"P347": "09880004556"}},
        },
    )
    s.commit()

    counts = enrich_museum_display(
        s, "orsay", fetch=lambda ref: {"location": "Salle 23", "detail": "Salle 23"}
    )

    assert counts == {"checked": 1, "evidenced": 1}
    obj = s.query(MuseumObject).filter_by(qid="Q1").one()
    evidence = obj.attributes["display"]["evidence"]
    assert any(
        e["source"] == "joconde" and e["type"] == "location_claim" for e in evidence
    )
    assert obj.attributes["display"]["location"] == "Salle 23"


def test_enrich_skips_object_without_ref(session):
    s, m = session
    upsert_object(s, m.id, {"qid": "Q2", "title_en": "B"})  # 无 external_ids
    s.commit()

    counts = enrich_museum_display(s, "orsay", fetch=lambda ref: pytest.fail("不该抓"))

    assert counts == {"checked": 0, "evidenced": 0}
    obj = s.query(MuseumObject).filter_by(qid="Q2").one()
    assert "display" not in (obj.attributes or {})


def test_enrich_fetch_none_no_evidence_no_crash(session):
    s, m = session
    upsert_object(
        s,
        m.id,
        {
            "qid": "Q3",
            "title_en": "C",
            "attributes": {"external_ids": {"P347": "99999999999"}},
        },
    )
    s.commit()

    counts = enrich_museum_display(s, "orsay", fetch=lambda ref: None)

    assert counts == {"checked": 1, "evidenced": 0}
    obj = s.query(MuseumObject).filter_by(qid="Q3").one()
    assert "display" not in (obj.attributes or {})


def test_enrich_unknown_slug_raises(session):
    """typo 馆名 → SystemExit,不静默 0/0。"""
    s, _ = session
    with pytest.raises(SystemExit):
        enrich_museum_display(s, "no-such-museum", fetch=lambda ref: None)
