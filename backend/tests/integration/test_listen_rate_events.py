"""V78 埋点(10-31 用户定):完播率 audio_played + 讲解点赞/踩 content_rated。

audio_engine 由**后端按上报时刻**查 DB 写进事件,不靠 App 传:音频以后会被替换
(Google → VoxCPM2),事后再按 (qid, 语言, 段) 去 join,得到的是替换后的引擎。
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app.main import app
from app.models.app_event import AppEvent
from app.models.content import (
    ObjectContentSection,
    ObjectSuggestedQuestion,
    SectionType,
)
from app.models.feedback import OBJECT_KINDS
from app.models.museum import Museum
from app.models.museum_object import MuseumObject
from app.services.object_importer import upsert_museum, upsert_object


@pytest.fixture()
def client():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(
        bind=engine,
        tables=[
            Museum.__table__,
            MuseumObject.__table__,
            SectionType.__table__,
            ObjectContentSection.__table__,
            ObjectSuggestedQuestion.__table__,
            AppEvent.__table__,
        ],
    )
    s = sessionmaker(bind=engine)()
    s.add(SectionType(code="guide", label_zh="讲解", label_en="Guide", default_sort=1))
    m = upsert_museum(s, {"slug": "orsay", "name_en": "Orsay", "city_en": "Paris"})
    o = upsert_object(s, m.id, {"qid": "Q1", "title_en": "T", "category": "painting"})
    s.add(
        ObjectContentSection(
            object_id=o.id,
            language="es",
            section_code="guide",
            body="x",
            audio_key="k",
            audio_engine="voxcpm2",
        )
    )
    s.add(
        ObjectSuggestedQuestion(
            object_id=o.id,
            language="es",
            sort=2,
            question="q",
            answer="a",
            audio_engine="google-chirp3",
        )
    )
    s.commit()

    def _override():
        yield s

    app.dependency_overrides[get_db] = _override
    yield TestClient(app), s
    app.dependency_overrides.pop(get_db, None)


def _played(c, **kw):
    body = {
        "language": "es",
        "section": "guide",
        "played_s": 81.4,
        "duration_s": 92.0,
        "end": "pause",
        "session": "abc",
    }
    body.update(kw)
    return c.post("/api/v1/museums/orsay/objects/Q1/played", json=body)


def test_played_logs_engine_looked_up_at_report_time(client):
    c, s = client
    assert _played(c).status_code == 204
    e = s.query(AppEvent).one()
    assert (e.name, e.museum_slug) == ("audio_played", "orsay")
    assert e.props == {
        "qid": "Q1",
        "language": "es",
        "section": "guide",
        "qa_sort": None,
        "played_s": 81.4,
        "duration_s": 92.0,
        "end": "pause",
        "session": "abc",
        "audio_engine": "voxcpm2",
    }


def test_played_qa_engine_from_question_row(client):
    c, s = client
    assert _played(c, section="qa", qa_sort=2, duration_s=None).status_code == 204
    p = s.query(AppEvent).one().props
    assert (p["audio_engine"], p["qa_sort"], p["duration_s"]) == (
        "google-chirp3",
        2,
        None,
    )


def test_played_unknown_object_still_logged_without_engine(client):
    """埋点 fire-and-forget:查不到引擎不报错,记 None。"""
    c, s = client
    r = c.post(
        "/api/v1/museums/orsay/objects/Q404/played",
        json={"language": "es", "section": "guide", "played_s": 3, "end": "exit"},
    )
    assert r.status_code == 204
    assert s.query(AppEvent).one().props["audio_engine"] is None


@pytest.mark.parametrize(
    "bad", [{"end": "evil"}, {"played_s": -1}, {"played_s": 999999}]
)
def test_played_rejects_bad_input(client, bad):
    c, s = client
    assert _played(c, **bad).status_code == 422
    assert s.query(AppEvent).count() == 0


def test_rated_logs_value_and_guide_engine(client):
    c, s = client
    r = c.post(
        "/api/v1/museums/orsay/objects/Q1/rated",
        json={"language": "es", "value": "down"},
    )
    assert r.status_code == 204
    e = s.query(AppEvent).one()
    assert (e.name, e.props) == (
        "content_rated",
        {"qid": "Q1", "language": "es", "value": "down", "audio_engine": "voxcpm2"},
    )


def test_rated_rejects_unknown_value(client):
    c, s = client
    r = c.post(
        "/api/v1/museums/orsay/objects/Q1/rated",
        json={"language": "es", "value": "meh"},
    )
    assert r.status_code == 422


def test_feedback_has_new_object_kinds():
    assert {"info_wrong", "too_shallow"} <= set(OBJECT_KINDS)
