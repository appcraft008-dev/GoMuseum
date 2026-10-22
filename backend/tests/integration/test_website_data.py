"""网站只读数据层(spec 2026-10-22-website-v1 §三/§四/§5.3)。

钉住:隐身馆不出现、只算有已发布 guide 的件、按请求语言判、薄页门槛、必看排前。
"""

from datetime import datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.models.artist import Artist
from app.models.content import ObjectContentSection
from app.models.museum import Museum
from app.models.museum_object import MuseumObject, ObjectImage
from app.services.object_importer import upsert_museum, upsert_object
from app.services.website import data as wd

ORSAY_FIRST_MUST_SEE = "Q737062"  # museums.yaml orsay must_see[0]


def _work(s, m, qid, *, langs=("en",), image=True, artist=None, category="painting"):
    o = upsert_object(
        s,
        m.id,
        {
            "qid": qid,
            "title_en": f"T{qid}",
            "category": category,
            "attributes": {"artist_qid": artist} if artist else {},
        },
    )
    if image:
        s.add(ObjectImage(object_id=o.id, image_key=f"images/{qid}/0", sort=0))
    for lang in langs:
        s.add(
            ObjectContentSection(
                object_id=o.id,
                language=lang,
                section_code="guide",
                body=f"guide {qid} {lang}",
                status="published",
            )
        )
    return o


@pytest.fixture()
def db():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(
        bind=engine,
        tables=[
            Museum.__table__,
            MuseumObject.__table__,
            ObjectImage.__table__,
            ObjectContentSection.__table__,
            Artist.__table__,
        ],
    )
    s = sessionmaker(bind=engine)()
    orsay = upsert_museum(
        s, {"slug": "orsay", "name_en": "Orsay", "city_en": "Paris", "country": "FR"}
    )
    rijks = upsert_museum(
        s,
        {"slug": "rijks", "name_en": "Rijks", "city_en": "Amsterdam", "country": "NL"},
    )
    amx = upsert_museum(
        s, {"slug": "amx", "name_en": "AMX", "city_en": "Amsterdam", "country": "NL"}
    )
    s.add(Artist(qid="Q296", name_en="Monet", name_i18n={"fr": "Claude Monet"}))
    _work(s, orsay, "Q100", langs=("en", "zh"), artist="Q296")
    _work(s, orsay, ORSAY_FIRST_MUST_SEE, langs=("en",), artist="Q296")
    _work(s, orsay, "Q101", langs=("zh",), artist="Q296")
    _work(s, orsay, "Q102", langs=("en",), image=False)
    _work(s, orsay, "Q103", langs=("en",), category="sculpture")
    _work(s, rijks, "Q900", langs=("en",), artist="Q296")
    _work(s, amx, "Q800", langs=("en",))
    s.query(Museum).filter(Museum.slug.in_(["orsay"])).update(
        {"published_at": datetime(2026, 1, 1)}, synchronize_session=False
    )
    s.commit()
    yield s


def _publish(s, slug):
    s.query(Museum).filter_by(slug=slug).update({"published_at": datetime(2026, 1, 1)})
    s.commit()


def test_city_slug():
    assert wd.city_slug("Paris") == "paris"
    assert wd.city_slug("São Paulo") == "sao-paulo"


def test_public_cities_hide_hidden_only_city(db):
    cities = wd.public_cities(db)
    assert [c.slug for c in cities] == ["paris"]
    assert all(m.slug != "rijks" for c in cities for m in c.museums)


def test_public_cities_two_cities_ordered_by_rank(db):
    _publish(db, "amx")
    cities = wd.public_cities(db)
    assert [c.slug for c in cities] == ["paris", "amsterdam"]  # orsay rank 2 < 末位
    ams = cities[1]
    assert [m.slug for m in ams.museums] == ["amx"]  # rijks 仍隐身


def test_find_museum_checks_city_and_visibility(db):
    assert wd.find_museum(db, "paris", "orsay").slug == "orsay"
    assert wd.find_museum(db, "amsterdam", "orsay") is None
    assert wd.find_museum(db, "amsterdam", "rijks") is None


def test_list_works_language_image_and_must_see_first(db):
    orsay = wd.find_museum(db, "paris", "orsay")
    cards, total = wd.list_works(db, [orsay.id], "en")
    qids = [c.qid for c in cards]
    assert qids[0] == ORSAY_FIRST_MUST_SEE
    assert "Q101" not in qids  # 只有 zh 正文
    assert "Q102" not in qids  # 无图
    assert total == len(qids) == 3
    assert cards[0].city == "paris" and cards[0].museum_slug == "orsay"


def test_list_works_filters(db):
    orsay = wd.find_museum(db, "paris", "orsay")
    by_artist, _ = wd.list_works(db, [orsay.id], "en", artist_qid="Q296")
    assert {c.qid for c in by_artist} == {"Q100", ORSAY_FIRST_MUST_SEE}
    sculptures, _ = wd.list_works(db, [orsay.id], "en", category="sculpture")
    assert [c.qid for c in sculptures] == ["Q103"]
    page2, total = wd.list_works(db, [orsay.id], "en", page=2, page_size=2)
    assert total == 3 and len(page2) == 1


def test_top_artists_localized_and_counted(db):
    orsay = wd.find_museum(db, "paris", "orsay")
    arts = wd.top_artists(db, [orsay.id], "fr")
    assert arts == []  # fr 没有正文
    arts = wd.top_artists(db, [orsay.id], "en")
    assert [(a.qid, a.name, a.count) for a in arts] == [("Q296", "Monet", 2)]


def test_categories(db):
    orsay = wd.find_museum(db, "paris", "orsay")
    cats = {code: n for code, _label, n in wd.categories(db, [orsay.id], "en")}
    assert cats == {"painting": 2, "sculpture": 1}


def test_guide_count(db):
    orsay = wd.find_museum(db, "paris", "orsay")
    assert wd.guide_count(db, [orsay.id], "en") == 3
    assert wd.guide_count(db, [orsay.id], "zh") == 2


def test_page_languages_threshold(db, monkeypatch):
    orsay = wd.find_museum(db, "paris", "orsay")
    monkeypatch.setattr(wd, "THIN_MUSEUM", 3)
    assert wd.page_languages(db, [orsay.id]) == ["en"]
    monkeypatch.setattr(wd, "THIN_MUSEUM", 2)
    assert wd.page_languages(db, [orsay.id]) == ["en", "zh"]
    monkeypatch.setattr(wd, "THIN_ARTIST", 2)
    assert wd.page_languages(db, [orsay.id], artist_qid="Q296") == ["en", "zh"]
    monkeypatch.setattr(wd, "THIN_ARTIST", 3)
    assert wd.page_languages(db, [orsay.id], artist_qid="Q296") == []


def test_cards_for_qids_keeps_order_and_language(db):
    orsay = wd.find_museum(db, "paris", "orsay")
    cards = wd.cards_for_qids(db, [orsay.id], "en", ["Q103", "Q101", "Q100", "Q900"])
    assert [c.qid for c in cards] == ["Q103", "Q100"]


def test_nameless_artist_never_shows_its_id(db):
    orsay = wd.find_museum(db, "paris", "orsay")
    db.add(Artist(qid="5f46d24a3ac7899a992a2fd7f0c86e00"))
    o = db.query(MuseumObject).filter_by(qid="Q103").one()
    o.attributes = {"artist_qid": "5f46d24a3ac7899a992a2fd7f0c86e00"}
    db.commit()
    cards, _ = wd.list_works(db, [orsay.id], "en", category="sculpture")
    assert cards[0].artist is None
    assert all(
        a.qid != o.attributes["artist_qid"]
        for a in wd.top_artists(db, [orsay.id], "en")
    )


def test_nameless_artist_has_no_artist_page(db, monkeypatch):
    monkeypatch.setattr(wd, "THIN_ARTIST", 1)
    orsay = wd.find_museum(db, "paris", "orsay")
    db.add(Artist(qid="HASH1"))
    o = db.query(MuseumObject).filter_by(qid="Q103").one()
    o.attributes = {"artist_qid": "HASH1"}
    db.commit()
    assert "HASH1" not in wd.artist_languages(db, [orsay.id])
    assert "Q296" in wd.artist_languages(db, [orsay.id])
