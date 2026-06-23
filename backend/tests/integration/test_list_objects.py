import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.models.museum import Museum
from app.models.museum_object import MuseumObject, ObjectImage
from app.services.museum_repo import list_objects
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
    m = upsert_museum(s, {"slug": "orsay", "name_en": "Orsay"})
    upsert_object(
        s,
        m.id,
        {
            "qid": "Q1",
            "title_zh": "世界的起源",
            "title_en": "Origin",
            "artist_zh": "库尔贝",
            "artist_en": "Courbet",
            "year": "1866",
            "category": "painting",
            "popularity": 50,
            "image": "http://i/1.jpg",
        },
    )
    upsert_object(
        s,
        m.id,
        {
            "qid": "Q2",
            "title_en": "Olympia",
            "artist_en": "Manet",
            "category": "painting",
            "popularity": 40,
        },
    )
    upsert_object(
        s,
        m.id,
        {"qid": "Q3", "title_en": "Low", "category": "painting", "popularity": 10},
    )
    upsert_object(
        s,
        m.id,
        {"qid": "Q4", "title_en": "Statue", "category": "sculpture", "popularity": 30},
    )
    s.query(MuseumObject).filter_by(qid="Q1").one().content_status = "ready"
    s.commit()
    yield s


def test_list_objects_paginates_by_popularity_desc(session):
    page = list_objects(session, "orsay", language="zh", limit=2, offset=0)
    assert page["total"] == 4 and page["limit"] == 2 and page["offset"] == 0
    assert [i["qid"] for i in page["items"]] == ["Q1", "Q2"]  # pop 50,40
    page2 = list_objects(session, "orsay", language="zh", limit=2, offset=2)
    assert [i["qid"] for i in page2["items"]] == ["Q4", "Q3"]  # pop 30,10


def test_list_objects_filters_by_category(session):
    page = list_objects(session, "orsay", language="zh", category="sculpture")
    assert page["total"] == 1 and [i["qid"] for i in page["items"]] == ["Q4"]


def test_list_objects_zh_titles_with_fallback(session):
    items = {
        i["qid"]: i for i in list_objects(session, "orsay", language="zh")["items"]
    }
    assert items["Q1"]["title"] == "世界的起源" and items["Q1"]["artist"] == "库尔贝"
    assert items["Q2"]["title"] == "Olympia"
    assert items["Q2"]["artist"] == "Manet"


def test_list_objects_en_titles(session):
    items = {
        i["qid"]: i for i in list_objects(session, "orsay", language="en")["items"]
    }
    assert items["Q1"]["title"] == "Origin" and items["Q1"]["artist"] == "Courbet"


def test_list_objects_item_shape(session):
    i = list_objects(session, "orsay", language="zh", limit=1)["items"][0]
    assert set(i.keys()) == {
        "qid",
        "title",
        "artist",
        "year",
        "thumbnail",
        "content_status",
    }
    assert i["qid"] == "Q1" and i["content_status"] == "ready"
    assert i["thumbnail"] == "https://i/1.jpg"


def test_list_objects_unknown_museum(session):
    assert list_objects(session, "nope", language="zh") is None
