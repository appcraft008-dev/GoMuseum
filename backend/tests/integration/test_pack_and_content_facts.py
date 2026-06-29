import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.models.content import (  # noqa: F401  (建表用)
    CategorySection,
    ObjectContentSection,
    ObjectSuggestedQuestion,
    SectionType,
)
from app.models.museum import Museum
from app.models.museum_object import MuseumObject, ObjectImage
from app.services.museum_repo import get_museum_pack, get_object_content
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
            CategorySection.__table__,
            ObjectContentSection.__table__,
            ObjectSuggestedQuestion.__table__,
            SectionType.__table__,
        ],
    )
    s = sessionmaker(bind=engine)()
    m = upsert_museum(s, {"slug": "orsay", "name_zh": "奥赛博物馆", "name_en": "Orsay"})
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
            "inventory_number": "RF 1995 10",
            "image": "http://img/x.jpg",
            "attributes": {
                "medium_fr": "huile sur toile",
                "dimensions": "46 x 55 cm",
                "exhibitions_fr": "1988, New York#1996, Paris",
            },
        },
    )
    upsert_object(s, m.id, {"qid": "Q2", "title_en": "S", "category": "sculpture"})
    s.query(MuseumObject).filter_by(qid="Q1").one().content_status = "ready"
    s.commit()
    yield s


def test_pack_includes_category_facet(session):
    cats = {c["code"]: c for c in get_museum_pack(session, "orsay", "zh")["categories"]}
    assert cats["all"]["count"] == 2
    assert cats["painting"] == {"code": "painting", "label": "绘画", "count": 1}
    assert cats["sculpture"]["label"] == "雕塑"


def test_content_includes_facts_title_images_status(session):
    d = get_object_content(session, "orsay", "Q1", "zh")
    assert d["title"] == "世界的起源" and d["status"] == "ready"
    assert d["images"][0]["url"] == "https://img/x.jpg"  # upsert_object 把 http→https
    f = d["facts"]
    assert f["artist"] == "库尔贝" and f["date"] == "1866"
    assert f["medium"] == "huile sur toile" and f["dimensions"] == "46 x 55 cm"
    assert f["inventory"] == "RF 1995 10" and f["location"] == "奥赛博物馆"
    assert f["exhibitions"] == ["1988, New York", "1996, Paris"]


def test_content_en_localizes(session):
    d = get_object_content(session, "orsay", "Q1", "en")
    assert d["title"] == "Origin" and d["facts"]["artist"] == "Courbet"


def test_content_returns_default_guide(session):
    from app.models.content import ObjectContentSection
    from app.models.museum_object import MuseumObject
    from app.services.museum_repo import get_object_content

    o = session.query(MuseumObject).filter_by(qid="Q1").one()
    session.add(
        ObjectContentSection(
            object_id=o.id,
            language="zh",
            section_code="guide",
            body="单主线默认讲解。",
            status="published",
        )
    )
    session.commit()
    d = get_object_content(session, "orsay", "Q1", "zh")
    assert d["default_guide"]["body"] == "单主线默认讲解。"
    assert "audio_url" in d["default_guide"]
    assert all(t["section_code"] != "guide" for t in d["tabs"])


def test_content_default_guide_null_when_absent(session):
    from app.services.museum_repo import get_object_content

    d = get_object_content(session, "orsay", "Q1", "en")
    assert d["default_guide"] is None
