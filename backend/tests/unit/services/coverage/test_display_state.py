"""展陈状态汇总:流量证据→CONFIRMED;P276→LIKELY;无→UNKNOWN;evidence追加去重。"""

from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.models.museum import Museum
from app.models.museum_object import MuseumObject, ObjectImage
from app.models.recognition_event import RecognitionEvent
from app.services.coverage.display_state import add_evidence, recompute_display
from app.services.object_importer import upsert_museum, upsert_object


@pytest.fixture()
def session():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(
        bind=engine,
        tables=[
            Museum.__table__,
            MuseumObject.__table__,
            ObjectImage.__table__,
            RecognitionEvent.__table__,
        ],
    )
    s = sessionmaker(bind=engine)()
    m = upsert_museum(s, {"slug": "orsay", "name_en": "Orsay"})
    s.commit()
    return s, m


def _event(s, qid, days_ago, outcome="match"):
    s.add(
        RecognitionEvent(
            museum_slug="orsay",
            phash="p" * 16,
            outcome=outcome,
            top_qid=qid if outcome == "match" else None,
            engine="vector",
            created_at=datetime.utcnow() - timedelta(days=days_ago),
        )
    )
    s.commit()


def test_traffic_evidence_confirms_display(session):
    """用例1: 造 match 事件(qid=Q1,15天前) → recompute → CONFIRMED_ON_DISPLAY,evidence 含 recognition_traffic。"""
    s, m = session
    upsert_object(s, m.id, {"qid": "Q1", "title_en": "A"})
    s.commit()
    _event(s, "Q1", days_ago=15)

    counts = recompute_display(s, "orsay")

    obj = s.query(MuseumObject).filter_by(qid="Q1").one()
    assert counts == {"confirmed": 1, "likely": 0, "unknown": 0}
    assert obj.attributes["display"]["status"] == "CONFIRMED_ON_DISPLAY"
    evidence = obj.attributes["display"]["evidence"]
    assert any(
        e["source"] == "recognition_traffic" and e["type"] == "confirmed_scan"
        for e in evidence
    )


def test_p276_without_traffic_is_likely(session):
    """用例2: Q2 attributes["p276"]="Q123" 无事件 → LIKELY_ON_DISPLAY。"""
    s, m = session
    upsert_object(
        s, m.id, {"qid": "Q2", "title_en": "B", "attributes": {"p276": "Q123"}}
    )
    s.commit()

    counts = recompute_display(s, "orsay")

    obj = s.query(MuseumObject).filter_by(qid="Q2").one()
    assert counts == {"confirmed": 0, "likely": 1, "unknown": 0}
    assert obj.attributes["display"]["status"] == "LIKELY_ON_DISPLAY"
    evidence = obj.attributes["display"]["evidence"]
    assert any(
        e["source"] == "wikidata_p276" and e["type"] == "location_claim"
        for e in evidence
    )


def test_no_evidence_is_unknown(session):
    """用例3: Q3 全无 → UNKNOWN。"""
    s, m = session
    upsert_object(s, m.id, {"qid": "Q3", "title_en": "C"})
    s.commit()

    counts = recompute_display(s, "orsay")

    obj = s.query(MuseumObject).filter_by(qid="Q3").one()
    assert counts == {"confirmed": 0, "likely": 0, "unknown": 1}
    assert obj.attributes["display"]["status"] == "UNKNOWN"


def test_stale_event_outside_window_not_confirmed(session):
    """用例4: 事件在 40 天前(超30天窗) → 不算 confirmed(落到 UNKNOWN)。"""
    s, m = session
    upsert_object(s, m.id, {"qid": "Q4", "title_en": "D"})
    s.commit()
    _event(s, "Q4", days_ago=40)

    counts = recompute_display(s, "orsay", traffic_days=30)

    obj = s.query(MuseumObject).filter_by(qid="Q4").one()
    assert counts["confirmed"] == 0
    assert obj.attributes["display"]["status"] == "UNKNOWN"


def test_joconde_evidence_survives_recompute(session):
    """用例5: 先 add_evidence(joconde location_claim) 再 recompute → evidence 两条共存,joconde 不被清掉。"""
    s, m = session
    obj = upsert_object(
        s, m.id, {"qid": "Q5", "title_en": "E", "attributes": {"p276": "Q999"}}
    )
    s.commit()
    add_evidence(
        obj,
        source="joconde",
        type="location_claim",
        detail="Salle 23",
        location="Salle 23",
    )
    s.commit()

    recompute_display(s, "orsay")

    obj = s.query(MuseumObject).filter_by(qid="Q5").one()
    evidence = obj.attributes["display"]["evidence"]
    sources = {(e["source"], e["type"]) for e in evidence}
    assert sources == {
        ("joconde", "location_claim"),
        ("wikidata_p276", "location_claim"),
    }
    assert obj.attributes["display"]["location"] == "Salle 23"
    assert obj.attributes["display"]["status"] == "LIKELY_ON_DISPLAY"


def test_add_evidence_dedupes_same_source_type(session):
    """用例6: add_evidence 同 source+type 重复调用 → 只留最新一条。"""
    s, m = session
    obj = upsert_object(s, m.id, {"qid": "Q6", "title_en": "F"})
    s.commit()

    add_evidence(obj, source="joconde", type="location_claim", detail="Salle 1")
    add_evidence(obj, source="joconde", type="location_claim", detail="Salle 2")

    evidence = obj.attributes["display"]["evidence"]
    assert len(evidence) == 1
    assert evidence[0]["detail"] == "Salle 2"


def test_add_evidence_does_not_set_status(session):
    """add_evidence 是纯证据追加,不决定 status(status 是 recompute 的职责)。"""
    s, m = session
    obj = upsert_object(s, m.id, {"qid": "Q7", "title_en": "G"})
    s.commit()

    add_evidence(obj, source="joconde", type="location_claim", detail="Salle 1")

    assert "status" not in obj.attributes["display"]
