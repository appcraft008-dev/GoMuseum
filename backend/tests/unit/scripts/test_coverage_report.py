"""覆盖率报告(build_report)+ museums.stats 回写(write_stats)。"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.models.museum import Museum
from app.models.museum_object import MuseumObject, ObjectImage
from app.models.object_embedding import ObjectEmbedding
from app.models.recognition_event import RecognitionEvent
from app.services.object_importer import upsert_museum, upsert_object
from scripts.coverage_report import build_report, write_stats


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
            ObjectEmbedding.__table__,
            RecognitionEvent.__table__,
        ],
    )
    s = sessionmaker(bind=engine)()
    m = upsert_museum(s, {"slug": "orsay", "name_en": "Orsay"})

    o1 = upsert_object(
        s, m.id, {"qid": "Q1", "title_en": "One", "category": "painting"}
    )
    o2 = upsert_object(
        s, m.id, {"qid": "Q2", "title_en": "Two", "category": "painting"}
    )
    upsert_object(  # 无图 stub
        s, m.id, {"qid": "Q3", "title_en": "Stub", "category": "sculpture"}
    )
    s.flush()

    img1 = ObjectImage(
        object_id=o1.id, role="primary", source_url="http://x/1.jpg", image_key="k1"
    )
    img2 = ObjectImage(object_id=o2.id, role="primary", source_url="http://x/2.jpg")
    img_q = ObjectImage(
        object_id=o1.id, role="view_quarantine", source_url="http://x/bad.jpg"
    )
    s.add_all([img1, img2, img_q])
    s.flush()

    s.add(
        ObjectEmbedding(object_id=o1.id, image_id=img1.id, model="clip-v1", vec=b"\x00")
    )
    s.add(
        ObjectEmbedding(object_id=o2.id, image_id=img2.id, model="clip-v1", vec=b"\x00")
    )

    s.add(
        RecognitionEvent(
            museum_slug="orsay",
            phash="p1",
            outcome="match",
            top_qid="Q1",
            engine="vector",
        )
    )
    s.add(
        RecognitionEvent(
            museum_slug="orsay", phash="p2", outcome="unrecognized", engine="vector"
        )
    )
    s.commit()

    # 第二馆:无任何识别事件(attempts=0 场景)
    upsert_museum(s, {"slug": "louvre", "name_en": "Louvre"})
    s.commit()
    return s, m


def test_build_report_counts(session):
    s, m = session
    report = build_report(s, "orsay")
    assert report["archive_count"] == 3
    assert report["catalog_count"] == 2
    assert report["textonly_count"] == 1
    assert report["views"]["quarantined"] == 1
    assert report["kpi"] == {"attempts": 2, "hits": 1, "rate": 0.5}
    assert "generated_at" in report


def test_build_report_no_attempts_rate_none(session):
    s, m = session
    report = build_report(s, "louvre")
    assert report["kpi"] == {"attempts": 0, "hits": 0, "rate": None}


def test_write_stats_roundtrip(session):
    s, m = session
    report = build_report(s, "orsay")
    write_stats(s, "orsay", report)
    reloaded = s.query(Museum).filter_by(slug="orsay").one()
    assert reloaded.stats["coverage"]["archive_count"] == 3
    assert reloaded.stats["catalog_count"] == 2
    assert reloaded.stats["archive_count"] == 3


def test_display_reflects_recompute(session):
    s, m = session
    report = build_report(s, "orsay")
    assert report["display"].get("CONFIRMED_ON_DISPLAY", 0) >= 1


def test_unknown_slug_raises_system_exit(session):
    s, m = session
    with pytest.raises(SystemExit):
        build_report(s, "no-such-museum")


def test_global_endpoint_events_attributed_by_top_qid(session):
    """新前端走全局识别端点(museum_slug=NULL):命中该馆对象的事件按 top_qid 归馆计入;
    NULL 馆且 NULL 对象的未识别事件无法归馆,不计入任何馆。"""
    s, m = session
    s.add(
        RecognitionEvent(
            museum_slug=None,
            phash="p3",
            outcome="match",
            top_qid="Q2",
            engine="vector",
        )
    )
    s.add(
        RecognitionEvent(
            museum_slug=None, phash="p4", outcome="unrecognized", engine="vector"
        )
    )
    s.commit()
    report = build_report(s, "orsay")
    # 基线 2 事件 + 全局 match(Q2 属 orsay) = 3;NULL/NULL 未识别不计入
    assert report["kpi"]["attempts"] == 3
    assert report["kpi"]["hits"] == 2
    # louvre 不沾光:Q2 非其馆藏
    assert build_report(s, "louvre")["kpi"] == {
        "attempts": 0,
        "hits": 0,
        "rate": None,
    }
