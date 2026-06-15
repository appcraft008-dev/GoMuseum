# tests/integration/test_object_importer.py
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.models.museum import Museum
from app.models.museum_object import MuseumObject, ObjectImage
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
    yield sessionmaker(bind=engine)()


def _art():
    return {
        "qid": "Q12418",
        "title_zh": "蒙娜丽莎",
        "title_en": "Mona Lisa",
        "artist_zh": "达芬奇",
        "artist_en": "Leonardo",
        "year": "1503",
        "period_zh": "文艺复兴",
        "period_en": "Renaissance",
        "popularity": 99,
        "inventory_number": "INV. 779",
        "image": "http://x/a.jpg",
        "attributes": {"material": "oil on panel"},
    }


def test_upsert_is_idempotent(session):
    m = upsert_museum(
        session,
        {
            "slug": "orsay",
            "qid": "Q23402",
            "name_en": "Orsay",
            "name_zh": "奥赛",
            "city_en": "Paris",
            "city_zh": "巴黎",
            "country": "FR",
        },
    )
    upsert_object(session, m.id, _art())
    session.commit()
    upsert_object(session, m.id, _art())
    session.commit()  # 第二次不应重复
    assert session.query(MuseumObject).count() == 1
    assert session.query(ObjectImage).count() == 1
    obj = session.query(MuseumObject).one()
    assert obj.inventory_number == "INV. 779"
    assert obj.attributes["material"] == "oil on panel"


def test_upsert_matches_by_inventory_when_no_qid(session):
    """无 qid 时应回退到 (museum_id, inventory_number) 匹配，仍然幂等。"""
    m = upsert_museum(session, {"slug": "orsay", "name_en": "Orsay"})
    art = _art()
    art["qid"] = None
    upsert_object(session, m.id, art)
    session.commit()
    upsert_object(session, m.id, art)
    session.commit()
    assert session.query(MuseumObject).count() == 1


def test_category_not_overwritten_when_absent(session):
    """已有 category 不应被缺省导入数据覆盖回 painting。"""
    m = upsert_museum(session, {"slug": "orsay", "name_en": "Orsay"})
    art = _art()
    art["category"] = "sculpture"
    upsert_object(session, m.id, art)
    session.commit()
    art_no_cat = _art()  # 不含 category 键
    upsert_object(session, m.id, art_no_cat)
    session.commit()
    assert session.query(MuseumObject).one().category == "sculpture"
