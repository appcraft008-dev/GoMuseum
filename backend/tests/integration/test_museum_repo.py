# tests/integration/test_museum_repo.py
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.models.museum import Museum
from app.models.museum_object import MuseumObject, ObjectImage
from app.services.museum_repo import get_museum_pack, list_museums
from app.services.object_importer import upsert_museum, upsert_object


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
    m = upsert_museum(
        s,
        {
            "slug": "orsay",
            "qid": "Q23402",
            "name_zh": "奥赛",
            "name_en": "Orsay",
            "city_zh": "巴黎",
            "city_en": "Paris",
            "country": "FR",
        },
    )
    upsert_object(
        s,
        m.id,
        {
            "qid": "Q1",
            "title_zh": "甲",
            "title_en": "A",
            "artist_zh": "X",
            "artist_en": "X",
            "year": "1880",
            "period_zh": "现实主义",
            "period_en": "Realism",
            "popularity": 50,
            "image": "http://x/a.jpg",
            "attributes": {},
        },
    )
    s.commit()
    yield s


def test_list_shape(session):
    rows = list_museums(session)
    assert rows[0].keys() == {
        "slug",
        "name_zh",
        "name_en",
        "city_zh",
        "city_en",
        "country",
        "artwork_count",
    }
    assert rows[0]["artwork_count"] == 1


def test_pack_shape(session):
    pack = get_museum_pack(session, "orsay")
    assert pack["slug"] == "orsay" and pack["artwork_count"] == 1
    assert set(pack.keys()) == {
        "slug",
        "qid",
        "name_zh",
        "name_en",
        "city_zh",
        "city_en",
        "country",
        "generated_at",
        "source",
        "artwork_count",
        "artworks",
    }
    art = pack["artworks"][0]
    assert set(art.keys()) == {
        "qid",
        "title_zh",
        "title_en",
        "artist_zh",
        "artist_en",
        "year",
        "period_zh",
        "period_en",
        "image",
        "popularity",
    }
