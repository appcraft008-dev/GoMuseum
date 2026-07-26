# tests/integration/test_museum_repo.py
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.models.artist import Artist
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
        tables=[
            Museum.__table__,
            MuseumObject.__table__,
            ObjectImage.__table__,
            Artist.__table__,
        ],
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


def test_pack_title_en_falls_back_to_i18n(session):
    # names(Batch 路径)只写 attributes.title_i18n 不写列;法语源大馆 title_en 列多为空
    # (卢浮宫实测 9505/17283 列空、9497 件 i18n 里有英文名)→ 只读列会让英文用户
    # 看到一半藏品标题空白。与 title_zh 对称:i18n 优先。
    m = session.query(Museum).filter_by(slug="orsay").one()
    o = upsert_object(
        session,
        m.id,
        {"qid": "Q9", "title_zh": None, "title_en": None, "attributes": {}},
    )
    o.attributes = {"title_i18n": {"en": "Battle of the Amazons", "zh": "亚马逊之战"}}
    session.commit()
    art = {a["qid"]: a for a in get_museum_pack(session, "orsay")["artworks"]}["Q9"]
    assert art["title_en"] == "Battle of the Amazons"  # i18n 补上,不再 null
    assert art["title_zh"] == "亚马逊之战"


def test_pack_artist_name_localized_from_artist_i18n(session):
    # 作者本地化真相源是 Artist.name_i18n(names 写这里,不写 MuseumObject.artist_* 列)。
    # 馆包此前只读裸列 → 卢浮宫 10041 件作者名在中文视图全显拉丁文。
    m = session.query(Museum).filter_by(slug="orsay").one()
    o = upsert_object(
        session,
        m.id,
        {"qid": "Q7", "title_en": "The Barque of Dante", "attributes": {}},
    )
    o.artist_en = "Eugène Delacroix"
    o.attributes = {"artist_qid": "Q33477"}
    session.add(
        Artist(
            qid="Q33477",
            name_en="Eugène Delacroix",
            name_i18n={"zh": "欧仁·德拉克罗瓦", "en": "Eugène Delacroix"},
        )
    )
    session.commit()
    art = {a["qid"]: a for a in get_museum_pack(session, "orsay")["artworks"]}["Q7"]
    assert art["artist_zh"] == "欧仁·德拉克罗瓦"  # 不再显拉丁文
    assert art["artist_en"] == "Eugène Delacroix"


def test_pack_artist_falls_back_to_column_without_artist_row(session):
    # 无 Artist 行(未解析作者)→ 回落对象列,不返 null
    m = session.query(Museum).filter_by(slug="orsay").one()
    o = upsert_object(session, m.id, {"qid": "Q8", "title_en": "X", "attributes": {}})
    o.artist_en = "Anonymous Master"
    session.commit()
    art = {a["qid"]: a for a in get_museum_pack(session, "orsay")["artworks"]}["Q8"]
    assert art["artist_en"] == "Anonymous Master"
