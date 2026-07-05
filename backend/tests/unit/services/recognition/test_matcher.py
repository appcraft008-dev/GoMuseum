"""匹配层(不变核心):候选名/墙签行 → 该馆目录多语模糊匹配 → [(qid, score)]。
R1 接地:只有匹配到真实目录记录才可能被展示。离线 sqlite。"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.models.artist import Artist
from app.models.museum import Museum
from app.models.museum_object import MuseumObject, ObjectImage
from app.services.object_importer import upsert_museum, upsert_object
from app.services.recognition import matcher
from app.services.recognition.matcher import HIGH, LOW, build_index, match, normalize


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
            Artist.__table__,
        ],
    )
    s = sessionmaker(bind=engine)()
    m = upsert_museum(s, {"slug": "orsay", "name_en": "Orsay"})
    upsert_object(
        s,
        m.id,
        {
            "qid": "Q334138",
            "title_en": "The Origin of the World",
            "artist_en": "Gustave Courbet",
            "category": "painting",
            "attributes": {
                "title_i18n": {
                    "en": "The Origin of the World",
                    "fr": "L'Origine du monde",
                    "zh": "世界的起源",
                },
                "artist_qid": "Q34618",
            },
        },
    )
    upsert_object(
        s,
        m.id,
        {
            "qid": "Q778242",
            "title_en": "The Raft of the Medusa study",
            "artist_en": "Théodore Géricault",
            "category": "painting",
            "attributes": {
                "title_i18n": {
                    "en": "The Raft of the Medusa study",
                    "fr": "Le Radeau de la Méduse",
                }
            },
        },
    )
    s.commit()
    matcher._index_cache.clear()
    yield s
    matcher._index_cache.clear()


def _mid(s):
    return s.query(Museum).filter_by(slug="orsay").one().id


def test_normalize_strips_accents_case_punct():
    assert normalize("Théodore, Géricault!") == "theodore gericault"
    assert normalize("  L'Origine   du  monde ") == "l origine du monde"


def test_zh_query_hits_via_title_i18n(session):
    idx = build_index(session, _mid(session))
    out = match(idx, ["世界的起源"], [])
    assert out[0][0] == "Q334138" and out[0][1] >= HIGH


def test_approximate_en_query_hits(session):
    idx = build_index(session, _mid(session))
    out = match(idx, ["Origin of the World"], [])
    assert out[0][0] == "Q334138" and out[0][1] >= LOW


def test_label_lines_match_with_artist_bonus(session):
    # 近似题名(精确匹配会打满 1.0,加分无从体现)+ 作者行 → 分数应高于无作者行
    idx = build_index(session, _mid(session))
    plain = match(idx, [], ["Radeau Méduse"])
    boosted = match(idx, [], ["Radeau Méduse", "Théodore Géricault", "1819"])
    assert boosted[0][0] == "Q778242"
    assert boosted[0][1] > plain[0][1]  # 作者行加分


def test_unrelated_query_scores_below_low(session):
    idx = build_index(session, _mid(session))
    out = match(idx, ["Mona Lisa"], [])
    assert not out or out[0][1] < LOW


def test_index_cached_per_museum(session):
    calls = {"n": 0}
    orig = session.query

    def counting_query(*a, **kw):
        calls["n"] += 1
        return orig(*a, **kw)

    session.query = counting_query
    mid = _mid(session)
    calls["n"] = 0
    build_index(session, mid)
    first = calls["n"]
    build_index(session, mid)
    assert calls["n"] == first  # 二次走缓存,不再查库
