import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.models.artist import Artist
from app.models.content import ObjectContentSection
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
        tables=[
            Museum.__table__,
            MuseumObject.__table__,
            ObjectImage.__table__,
            Artist.__table__,
            ObjectContentSection.__table__,
        ],
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
            # 多语显示名走 title_i18n(权威→翻译→en);列 title_zh 仅回退兜底
            "attributes": {"title_i18n": {"zh": "世界的起源", "en": "Origin"}},
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
    o1 = s.query(MuseumObject).filter_by(qid="Q1").one()
    o1.content_status = "ready"
    # ready 应有已发布内容(zh):content_status 按请求语言解读
    s.add(
        ObjectContentSection(
            object_id=o1.id,
            language="zh",
            section_code="guide",
            body="中文讲解。",
            status="published",
        )
    )
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


def test_list_objects_content_status_is_language_aware(session):
    # 对象级 ready 但请求语言无已发布内容 → 列表应显"待完善"(empty),不再骗用户
    zh = {i["qid"]: i for i in list_objects(session, "orsay", language="zh")["items"]}
    de = {i["qid"]: i for i in list_objects(session, "orsay", language="de")["items"]}
    assert zh["Q1"]["content_status"] == "ready"  # zh 有内容
    assert de["Q1"]["content_status"] == "empty"  # de 无内容 → 待完善
    assert de["Q3"]["content_status"] == "stub"  # stub 保持(懒生成入口)


def test_list_objects_artist_resolves_via_name_i18n(session):
    # 契约§3:artist 同 title 走多语显示名规则(name_i18n 权威→legacy→en)
    o = session.query(MuseumObject).filter_by(qid="Q1").one()
    o.attributes = {**(o.attributes or {}), "artist_qid": "Q34618"}
    session.add(
        Artist(
            qid="Q34618",
            name_en="Courbet",
            name_i18n={"en": "Courbet", "fr": "Gustave Courbet", "zh": "库尔贝"},
        )
    )
    session.commit()
    items = {
        i["qid"]: i for i in list_objects(session, "orsay", language="fr")["items"]
    }
    assert items["Q1"]["artist"] == "Gustave Courbet"  # fr 权威标签
    items_de = {
        i["qid"]: i for i in list_objects(session, "orsay", language="de")["items"]
    }
    assert items_de["Q1"]["artist"] == "Courbet"  # de 无标签 → en 兜底
    # 无 artist_qid 的对象仍走 legacy 列
    assert items["Q2"]["artist"] == "Manet"


def test_list_thumbnail_uses_thumb_tier_when_materialized(session):
    # image_key=基础键 → 列表出 _thumb.jpg 档;无 key 回退 source_url(既有测试保)
    o = session.query(MuseumObject).filter_by(qid="Q1").one()
    img = session.query(ObjectImage).filter_by(object_id=o.id).one()
    img.image_key = "images/Q1/0"
    session.commit()
    items = {
        i["qid"]: i for i in list_objects(session, "orsay", language="zh")["items"]
    }
    assert items["Q1"]["thumbnail"].endswith("images/Q1/0_thumb.jpg")
