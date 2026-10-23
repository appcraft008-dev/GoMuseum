"""网站页面:首页/城市/馆/作者(spec 2026-10-22-website-v1 §四/§五/§七)。"""

from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import settings
from app.core.database import Base, get_db
from app.main import app
from app.models.app_event import AppEvent
from app.models.artist import Artist
from app.models.content import ObjectContentSection, ObjectSuggestedQuestion
from app.models.museum import Museum
from app.models.museum_object import MuseumObject, ObjectImage
from app.services.object_importer import upsert_museum, upsert_object
from app.services.website import data as wd
from app.services.website import trials

MS1 = "Q737062"  # orsay 必看清单第一件


def _work(s, m, qid, langs, *, artist=None, category="painting", audio=False):
    o = upsert_object(
        s,
        m.id,
        {
            "qid": qid,
            "title_en": f"Title{qid}",
            "category": category,
            "attributes": {"artist_qid": artist} if artist else {},
        },
    )
    s.add(ObjectImage(object_id=o.id, image_key=f"images/{qid}/0", sort=0))
    for lang in langs:
        s.add(
            ObjectContentSection(
                object_id=o.id,
                language=lang,
                section_code="guide",
                body=f"guide {qid} {lang}",
                status="published",
                audio_key=f"object-audio/{qid}/{lang}/guide-x.mp3" if audio else None,
            )
        )


@pytest.fixture()
def db(monkeypatch):
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
            ObjectSuggestedQuestion.__table__,
            Artist.__table__,
            AppEvent.__table__,
        ],
    )
    s = sessionmaker(bind=engine)()
    orsay = upsert_museum(
        s, {"slug": "orsay", "name_en": "Musée d'Orsay", "city_en": "Paris"}
    )
    rijks = upsert_museum(
        s, {"slug": "rijks", "name_en": "SecretRijks", "city_en": "Amsterdam"}
    )
    amx = upsert_museum(s, {"slug": "amx", "name_en": "AmxMuseum", "city_en": "Ams"})
    s.add(Artist(qid="Q296", name_en="Claude Monet"))
    _work(s, orsay, MS1, ("en", "zh"), artist="Q296", audio=True)
    _work(s, orsay, "Q100", ("en", "zh", "fr"), artist="Q296")
    _work(s, orsay, "Q101", ("zh",), artist="Q296")
    _work(s, orsay, "Q103", ("en",), category="sculpture")
    _work(s, rijks, "Q900", ("en",), artist="Q296")
    _work(s, amx, "Q800", ("en",), artist="Q296")
    s.query(Museum).filter_by(slug="orsay").update(
        {"published_at": datetime(2026, 1, 1)}
    )
    s.commit()
    trials._cache.clear()
    monkeypatch.setattr(wd, "THIN_MUSEUM", 2)
    monkeypatch.setattr(wd, "THIN_ARTIST", 1)
    monkeypatch.setattr(settings, "SHARE_PLAY_LIVE", False)
    monkeypatch.setattr(settings, "PUBLIC_WEB_BASE_URL", "https://gomuseum.app")
    app.dependency_overrides[get_db] = lambda: (yield s)
    yield s
    app.dependency_overrides.clear()


@pytest.fixture()
def client(db):
    return TestClient(app)


def _publish(s, slug):
    s.query(Museum).filter_by(slug=slug).update({"published_at": datetime(2026, 1, 1)})
    s.commit()


def test_home_single_city(client):
    r = client.get("/en/")
    assert r.status_code == 200
    assert 'hreflang="x-default" href="https://gomuseum.app/en/"' in r.text
    assert "Musée d&#39;Orsay" in r.text
    assert 'data-section="cities"' not in r.text
    assert f"/en/paris/orsay/{MS1}/" in r.text  # 必看卡片


def test_home_two_cities_groups(client, db):
    _publish(db, "amx")
    r = client.get("/en/")
    assert 'data-section="cities"' in r.text
    assert "AmxMuseum" in r.text


def test_hidden_museum_never_appears(client):
    for path in ("/en/", "/en/paris/", "/en/paris/orsay/", "/en/paris/artists/Q296/"):
        r = client.get(path)
        assert r.status_code == 200, path
        assert "SecretRijks" not in r.text and "Q900" not in r.text, path


def test_museum_page_filters(client, monkeypatch):
    r = client.get("/en/paris/orsay/", params={"category": "sculpture"})
    assert "/en/paris/orsay/Q103/" in r.text and "/en/paris/orsay/Q100/" not in r.text
    monkeypatch.setattr(
        "app.api.web.site_pages.run_search",
        lambda db, st, q, **kw: ([], [{"qid": "Q101"}, {"qid": "Q100"}]),
    )
    r = client.get("/fr/paris/orsay/", params={"q": "x"})
    assert "/fr/paris/orsay/Q100/" in r.text and "Q101" not in r.text


def test_thin_language_is_noindex_and_not_in_hreflang(client):
    fr = client.get("/fr/paris/orsay/")  # fr 只有 1 件 < 门槛 2
    assert fr.status_code == 200
    assert '<meta name="robots" content="noindex">' in fr.text
    en = client.get("/en/paris/orsay/")
    assert '<meta name="robots" content="noindex">' not in en.text
    assert 'hreflang="zh"' in en.text and 'hreflang="fr"' not in en.text


def test_unknown_paths_404(client):
    assert client.get("/xx/").status_code == 404
    assert client.get("/en/amsterdam/orsay/").status_code == 404
    assert client.get("/en/paris/rijks/").status_code == 404
    assert client.get("/en/nowhere/").status_code == 404


def test_museum_without_must_see_list(client, db):
    _publish(db, "amx")
    r = client.get("/en/ams/amx/")
    assert r.status_code == 200
    assert 'data-section="must-see"' not in r.text
    assert 'data-section="artists"' in r.text


def test_play_link_only_when_live(client, monkeypatch):
    assert "play.google.com" not in client.get("/en/").text
    monkeypatch.setattr(settings, "SHARE_PLAY_LIVE", True)
    html = client.get("/en/", headers={"user-agent": "Mozilla/5.0 (Linux; Android 14)"})
    assert "utm_medium%3Dweb%26utm_content%3Dhome" in html.text


def test_no_audio_leaks_into_listing_pages(client):
    for path in ("/en/", "/zh/paris/", "/zh/paris/orsay/", "/en/paris/artists/Q296/"):
        html = client.get(path).text
        assert ".mp3" not in html and "object-audio/" not in html, path


def test_artist_page_lists_only_language_works(client):
    r = client.get("/fr/paris/orsay/artists/Q296/")
    assert r.status_code == 200
    assert "/fr/paris/orsay/Q100/" in r.text and MS1 not in r.text
    assert client.get("/fr/paris/orsay/artists/Q999/").status_code == 404


def test_api_routes_not_shadowed(client):
    assert client.get("/api/health/").status_code == 200


def test_nameless_artist_page_404(client, db):
    db.add(Artist(qid="HASH1"))
    o = db.query(MuseumObject).filter_by(qid="Q103").one()
    o.attributes = {"artist_qid": "HASH1"}
    db.commit()
    assert client.get("/en/paris/orsay/artists/HASH1/").status_code == 404


def test_museum_without_language_content_not_listed(client, db):
    upsert_museum(db, {"slug": "emptyp", "name_en": "EmptyParis", "city_en": "Paris"})
    _publish(db, "emptyp")
    for path in ("/en/", "/en/paris/"):
        assert "EmptyParis" not in client.get(path).text, path


def test_theme_toggle_on_every_page(client):
    # 亮/暗开关:默认跟系统;选过的存本地,<head> 里先应用,免得刷新先闪一下另一个主题
    for path in ("/en/", "/zh/paris/orsay/"):  # base.html 共用,作品页同理
        r = client.get(path)
        assert 'class="theme-btn"' in r.text, path
        head = r.text.split("</head>")[0]
        assert "gm-theme" in head and "dataset.theme" in head, path
