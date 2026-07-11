"""views.py: 雕塑多视角补图。
add_view_images 门控(仅 sculpture 且现有图 <3)/角色/顺延 sort/幂等/cap;
fetch_view_urls 解析(P18 排除、非图排除、max_n) — http_get 注入,不走真网络。"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.models.museum import Museum
from app.models.museum_object import MuseumObject, ObjectImage
from app.services.enrichment.views import add_view_images, fetch_view_urls
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
    s.commit()
    return s, m


def _make_obj(s, m, category, n_images):
    o = upsert_object(
        s, m.id, {"qid": f"Q-{category}-{n_images}", "category": category}
    )
    for i in range(n_images):
        s.add(
            ObjectImage(
                object_id=o.id, role="primary", source_url=f"http://x/{i}.jpg", sort=i
            )
        )
    s.commit()
    return o


def _n_images(s, o):
    return s.query(ObjectImage).filter_by(object_id=o.id).count()


def test_non_sculpture_no_action(session):
    s, m = session
    o = _make_obj(s, m, "painting", 1)
    calls = []
    n = add_view_images(s, o, fetch=lambda qid, max_n: calls.append(qid) or [])
    assert n == 0 and calls == [] and _n_images(s, o) == 1


def test_sculpture_with_enough_images_no_action(session):
    s, m = session
    o = _make_obj(s, m, "sculpture", 3)
    calls = []
    n = add_view_images(s, o, fetch=lambda qid, max_n: calls.append(qid) or [])
    assert n == 0 and calls == [] and _n_images(s, o) == 3


def test_sculpture_inserts_up_to_cap(session):
    s, m = session
    o = _make_obj(s, m, "sculpture", 1)  # sort=0 existing
    urls = [f"https://c/v{i}.jpg" for i in range(6)]
    n = add_view_images(s, o, max_total=5, fetch=lambda qid, max_n: urls)
    assert n == 4  # 1 existing + 4 new = 5 cap
    views = (
        s.query(ObjectImage)
        .filter_by(object_id=o.id, role="view")
        .order_by(ObjectImage.sort)
        .all()
    )
    assert [v.source_url for v in views] == urls[:4]
    assert [v.sort for v in views] == [1, 2, 3, 4]  # 顺延 existing max sort(0)+1


def test_idempotent(session):
    s, m = session
    o = _make_obj(s, m, "sculpture", 1)
    urls = ["https://c/a.jpg", "https://c/b.jpg"]
    first = add_view_images(s, o, max_total=5, fetch=lambda qid, max_n: urls)
    s.commit()
    second = add_view_images(s, o, max_total=5, fetch=lambda qid, max_n: urls)
    assert first == 2 and second == 0 and _n_images(s, o) == 3


def test_fetch_view_urls_parsing():
    # 假 http_get:按 URL/params 返回预置 Wikidata / Commons JSON
    p18 = "Statue front.jpg"

    def fake_get(url, params):
        if "wikidata" in url:
            return {
                "entities": {
                    "Q42": {
                        "claims": {
                            "P18": [{"mainsnak": {"datavalue": {"value": p18}}}],
                            "P373": [
                                {"mainsnak": {"datavalue": {"value": "Some sculpture"}}}
                            ],
                        },
                        "sitelinks": {},
                    }
                }
            }
        if params.get("list") == "categorymembers":
            return {
                "query": {
                    "categorymembers": [
                        {"title": "File:Statue front.jpg"},  # P18 本尊,排除
                        {"title": "File:Statue side.jpg"},
                        {"title": "File:Statue back.png"},
                        {"title": "File:Statue notes.svg"},  # 非图,排除
                        {"title": "File:Statue extra.jpeg"},
                    ]
                }
            }
        # imageinfo
        title = params["titles"]
        return {
            "query": {
                "pages": {
                    "1": {
                        "imageinfo": [
                            {"thumburl": f"https://thumb/{title}".replace(" ", "_")}
                        ]
                    }
                }
            }
        }

    urls = fetch_view_urls("Q42", max_n=2, http_get=fake_get)
    assert urls == [
        "https://thumb/File:Statue_side.jpg",
        "https://thumb/File:Statue_back.png",
    ]  # P18 排除、svg 排除、max_n=2 截断
