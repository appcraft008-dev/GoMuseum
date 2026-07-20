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
        "cover_image",  # 加法字段:探索页缩略图(spec 2026-07-20)
    }
    assert rows[0]["artwork_count"] == 1
    assert rows[0]["cover_image"] is None  # 未设 cover_image_key → null(前端隐藏)


def test_list_cover_image_thumb_url(session, monkeypatch):
    from app.models.museum import Museum
    from app.services import museum_repo

    class _Storage:
        def public_url(self, key):
            return f"https://r2/{key}"

    monkeypatch.setattr(museum_repo, "get_object_storage", lambda: _Storage())
    m = session.query(Museum).filter_by(slug="orsay").one()
    m.cover_image_key = "images/Q23402/0"
    session.commit()
    rows = list_museums(session)
    row = next(r for r in rows if r["slug"] == "orsay")
    assert row["cover_image"] == "https://r2/images/Q23402/0_thumb.jpg"


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
        "catalog_count",  # 加法字段:有图件数(在线图录)
        "archive_count",  # 加法字段:总件数(档案)
        "categories",
        "artworks",
        "description",  # 加法字段:馆介绍(spec 2026-07-18)
        "cover_image",  # 加法字段:封面
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


def test_pack_title_zh_falls_back_when_null(session):
    # 富化数据常缺中文标题；title_zh 必须永不为 null（否则前端强转崩）
    m = session.query(Museum).filter_by(slug="orsay").one()
    upsert_object(
        session,
        m.id,
        {"qid": "Q2", "title_zh": None, "title_en": "Sunrise", "attributes": {}},
    )
    upsert_object(
        session,
        m.id,
        {"qid": "Q3", "title_zh": None, "title_en": None, "attributes": {}},
    )
    session.commit()
    by_qid = {a["qid"]: a for a in get_museum_pack(session, "orsay")["artworks"]}
    assert by_qid["Q2"]["title_zh"] == "Sunrise"  # 回退 title_en
    assert by_qid["Q3"]["title_zh"] == "Q3"  # 再回退 qid
    assert all(a["title_zh"] is not None for a in by_qid.values())
