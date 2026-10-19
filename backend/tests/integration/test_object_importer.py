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
    (否则 qid/署名/图被改写、缺的字段留旧值 → 一行混两件,2026-10-19 查出 10 行);
    唯一约束放开后(10-19)两件各占一行。"""
    from app.services.object_importer import find_object

    m = upsert_museum(session, {"slug": "orsay", "name_en": "Orsay"})
    painting = {
        "qid": "Q17491121",
        "inventory_number": "RF 166",
        "artist_en": "Henri Regnault",
        "image": "https://example.org/regnault.jpg",
        "attributes": {"creator_qids": ["Q553571"]},
    }
    upsert_object(session, m.id, painting)
    session.commit()
    sculpture = {
        "qid": "Q76465029",
        "inventory_number": "RF 166",
        "title_en": "Joan of Arc at Domrémy",
        "artist_en": "Henri Chapu",
        "image": "https://example.org/chapu.jpg",
        "attributes": {"creator_qids": ["Q654201"]},
    }
    assert find_object(session, m.id, sculpture) is None
    upsert_object(session, m.id, sculpture)
    session.commit()
    rows = {o.qid: o for o in session.query(MuseumObject).all()}
    assert set(rows) == {"Q17491121", "Q76465029"}
    assert (rows["Q17491121"].artist_en, rows["Q17491121"].title_en) == (
        "Henri Regnault",
        None,
    )
    assert rows["Q76465029"].artist_en == "Henri Chapu"
    # 两件都在后,按 qid 重导仍各回各行;无 qid 按号兜底有歧义 → 不猜
    assert find_object(session, m.id, sculpture).qid == "Q76465029"
    assert find_object(session, m.id, painting).qid == "Q17491121"
    assert find_object(session, m.id, {"inventory_number": "RF 166"}) is None


def _existing_rf1(session, attrs):
    m = upsert_museum(session, {"slug": "orsay", "name_en": "Orsay"})
    upsert_object(
        session,
        m.id,
        {"qid": "QA", "inventory_number": "RF 1", "attributes": attrs},
    )
    session.commit()
    return m


@pytest.mark.parametrize(
    "existing,incoming",
    [
        ({"creator_qids": ["C1"]}, ["C1"]),  # 作者有交集 = Wikidata 重复条目
        ({"artist_qid": "C1"}, ["C1", "C2"]),  # 老行只有 artist_qid 也认
        ({"creator_qids": ["C1"]}, None),  # 新件作者未知 → 不敢当两件
        ({}, ["C2"]),  # 老行作者未知 → 不敢当两件
    ],
)
def test_new_row_on_taken_inventory_needs_disjoint_creators(
    session, existing, incoming
):
    """唯一约束放开后,同号新行只给「作者毫无交集」的另一件作品(Fable 审查 10-19):
    否则重复条目按 qid 找不到旧行、会新建出同一件作品的第二行。"""
    from app.services.object_importer import InventoryCollision

    m = _existing_rf1(session, existing)
    art = {"qid": "QB", "inventory_number": "RF 1"}
    if incoming:
        art["attributes"] = {"creator_qids": incoming}
    with pytest.raises(InventoryCollision):
        upsert_object(session, m.id, art)
    session.rollback()
    assert [o.qid for o in session.query(MuseumObject).all()] == ["QA"]
