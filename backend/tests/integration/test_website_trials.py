"""试听(spec 2026-10-22-website-v1 §6):每馆每语言自动 ≤5 件,只有它们的音频能经
/w/audio 拿到(1 小时预签名),其余一律同一个 404;网页层不点火、不合成。"""

from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app.main import app
from app.models.artist import Artist
from app.models.content import ObjectContentSection, ObjectSuggestedQuestion
from app.models.museum import Museum
from app.models.museum_object import MuseumObject, ObjectImage
from app.services.object_importer import upsert_museum, upsert_object
from app.services.website import trials

# orsay 必看清单(museums.yaml)的前三件
MS1, MS2, MS3 = "Q737062", "Q152509", "Q683274"


def _work(s, m, qid, *, audio=(), lang="zh", artist=None, qa_audio=False):
    o = upsert_object(
        s,
        m.id,
        {
            "qid": qid,
            "title_en": qid,
            "category": "painting",
            "attributes": {"artist_qid": artist} if artist else {},
        },
    )
    s.add(ObjectImage(object_id=o.id, image_key=f"images/{qid}/0", sort=0))
    for code in ("guide", "background", "analysis"):
        s.add(
            ObjectContentSection(
                object_id=o.id,
                language=lang,
                section_code=code,
                body=f"{code} {qid}",
                status="published",
                audio_key=(
                    f"object-audio/{qid}/{lang}/{code}-x.mp3" if code in audio else None
                ),
            )
        )
    s.add(
        ObjectSuggestedQuestion(
            object_id=o.id,
            language=lang,
            question="q?",
            answer="a.",
            sort=1,
            status="published",
            audio_key=f"object-audio/{qid}/{lang}/qa-1.mp3" if qa_audio else None,
        )
    )
    return o


@pytest.fixture()
def db(monkeypatch):
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(
        bind=engine,
        tables=[
            Museum.__table__,
            MuseumObject.__table__,
            ObjectImage.__table__,
            ObjectContentSection.__table__,
            ObjectSuggestedQuestion.__table__,
            Artist.__table__,
        ],
    )
    s = sessionmaker(bind=engine)()
    orsay = upsert_museum(s, {"slug": "orsay", "name_en": "Orsay", "city_en": "Paris"})
    rijks = upsert_museum(s, {"slug": "rijks", "name_en": "R", "city_en": "Amsterdam"})
    amx = upsert_museum(s, {"slug": "amx", "name_en": "A", "city_en": "Amsterdam"})
    s.add(Artist(qid="Q296", name_en="Monet", bio_audio={"zh": "artist-audio/x.mp3"}))
    _work(s, orsay, MS1, audio=("guide",))
    _work(s, orsay, MS2, audio=("guide", "background", "analysis"), qa_audio=True)
    _work(s, orsay, MS3, audio=("background",))  # 导览没音频 → 不能当试听
    _work(s, orsay, "Q5000", audio=("guide", "background", "analysis"))  # 不在清单
    _work(s, rijks, "Q900", audio=("guide",))
    for i in range(7):
        _work(s, amx, f"Q80{i}", audio=("guide",) + (("background",) if i == 3 else ()))
    s.query(Museum).filter(Museum.slug.in_(["orsay", "amx"])).update(
        {"published_at": datetime(2026, 1, 1)}, synchronize_session=False
    )
    s.commit()
    trials._cache.clear()

    def _boom(*a, **k):
        raise AssertionError("网页层不许点火/合成")

    monkeypatch.setattr("app.services.enrichment.lazy.maybe_trigger", _boom)
    monkeypatch.setattr("app.services.tts_service.TTSService.generate_audio", _boom)
    app.dependency_overrides[get_db] = lambda: (yield s)
    yield s
    app.dependency_overrides.clear()


@pytest.fixture()
def client(db):
    return TestClient(app, follow_redirects=False)


def _m(db, slug):
    return db.query(Museum).filter_by(slug=slug).one()


def test_trials_only_from_must_see_with_guide_audio_in_list_order(db):
    # 清单顺序优先:MS2 音频更全也排在 MS1 后(prod 上蒙娜丽莎就是这样被挤掉的)
    assert trials.trial_qids(db, _m(db, "orsay"), "zh") == [MS1, MS2]


def test_trials_without_must_see_fullest_first_capped(db):
    got = trials.trial_qids(db, _m(db, "amx"), "zh")
    assert len(got) == trials.TRIAL_LIMIT == 5
    assert got[0] == "Q803"


def test_trials_none_when_no_audio_in_language(db):
    assert trials.trial_qids(db, _m(db, "orsay"), "fr") == []


def test_trial_parts(db):
    o = db.query(MuseumObject).filter_by(qid=MS2).one()
    o.attributes = {"artist_qid": "Q296"}
    db.commit()
    parts = trials.trial_parts(db, o, "zh")
    assert set(parts) == {"guide", "background", "analysis", "artist_bio", "qa-1"}


def test_audio_redirects_for_trial(client):
    r = client.get(f"/w/audio/orsay/{MS2}/background", params={"lang": "zh"})
    assert r.status_code == 302
    assert f"object-audio/{MS2}/zh/background-x.mp3" in r.headers["location"]
    assert r.headers["cache-control"] == "no-store"


def test_audio_404_is_uniform(client):
    paths = [
        ("/w/audio/orsay/Q5000/guide", "zh"),  # 有音频但不是试听件
        ("/w/audio/rijks/Q900/guide", "zh"),  # 隐身馆
        (f"/w/audio/orsay/{MS2}/facts", "zh"),  # 没有这段
        (f"/w/audio/orsay/{MS2}/guide", "fr"),  # 该语言不是试听
        ("/w/audio/nope/Q1/guide", "zh"),
    ]
    bodies = set()
    for p, lang in paths:
        r = client.get(p, params={"lang": lang})
        assert r.status_code == 404, p
        bodies.add(r.content)
    assert len(bodies) == 1


def test_audio_unknown_lang_not_cached(client):
    assert (
        client.get(f"/w/audio/orsay/{MS2}/guide", params={"lang": "zzz"}).status_code
        == 404
    )
    assert not any(k[1] == "zzz" for k in trials._cache)
