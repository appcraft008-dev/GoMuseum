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


def test_inventory_fallback_does_not_merge_different_wikidata_items(session):
    """奥赛油画与雕塑两套编号都叫 RF n:RF 166 既是 Regnault 油画 Q17491121
    又是 Chapu 雕塑 Q76465029。按馆藏号兜底不能把另一个 Wikidata 条目并进这行
    (否则 qid/署名/图被改写、缺的字段留旧值 → 一行混两件,2026-10-19 查出 10 行)。"""
    from sqlalchemy.exc import IntegrityError

    from app.services.object_importer import find_object

    m = upsert_museum(session, {"slug": "orsay", "name_en": "Orsay"})
    painting = {
        "qid": "Q17491121",
        "inventory_number": "RF 166",
        "artist_en": "Henri Regnault",
        "image": "https://example.org/regnault.jpg",
    }
    upsert_object(session, m.id, painting)
    session.commit()
    sculpture = {
        "qid": "Q76465029",
        "inventory_number": "RF 166",
        "title_en": "Joan of Arc at Domrémy",
        "artist_en": "Henri Chapu",
        "image": "https://example.org/chapu.jpg",
    }
    assert find_object(session, m.id, sculpture) is None
    with pytest.raises(IntegrityError):  # 撞唯一约束 → 由 load_stubs 的 SAVEPOINT 跳过
        upsert_object(session, m.id, sculpture)
    session.rollback()
    obj = session.query(MuseumObject).one()
    assert (obj.qid, obj.artist_en, obj.title_en) == (
        "Q17491121",
        "Henri Regnault",
        None,
    )
    assert session.query(ObjectImage).one().source_url.endswith("regnault.jpg")
