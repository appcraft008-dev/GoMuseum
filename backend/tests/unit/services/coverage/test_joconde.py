"""Joconde 区域适配器:reference→localisation 展陈证据。fake http 注入,不打真网。
canned JSON 摘自真实 data.culture.gouv.fr/base-joconde-extrait 响应。"""

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
from app.services.object_importer import upsert_museum, upsert_object

# 真实 opendatasoft v2.1 records 响应形状(reference 过滤,命中 1 条)
CANNED_HIT = {
    "total_count": 1,
    "results": [
        {
            "reference": "09880004556",
            "localisation": "Valence ; musée des beaux-arts",
            "exposition": None,
            "nom_officiel_musee": "musée des beaux-arts",
        }
    ],
}
CANNED_EMPTY = {"total_count": 0, "results": []}


class _Resp:
    def __init__(self, data, status=200):
        self._data = data
        self.status_code = status

    def json(self):
        return self._data


def _fake_get(data, status=200):
    def get(url, params=None, headers=None, timeout=None):
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
