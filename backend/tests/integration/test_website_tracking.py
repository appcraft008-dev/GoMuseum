"""网站自记统计(spec 2026-10-22-website-v1 §七/§八):无 cookie、白名单、按设备区分。"""

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
from app.services.object_importer import upsert_museum
from app.services.website import trials
from app.services.website.tracking import device_class, internal_referrer

IPHONE = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit Mobile/15E148"
)
IPAD = "Mozilla/5.0 (iPad; CPU OS 17_0 like Mac OS X) AppleWebKit Mobile/15E148"
ANDROID = "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit Chrome/120 Mobile"
DESKTOP = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit Chrome/120 Safari"
GOOGLEBOT = "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)"


def test_device_class():
    assert [device_class(u) for u in (IPHONE, IPAD, ANDROID, DESKTOP, GOOGLEBOT)] == [
        "iphone",
        "ipad",
        "android",
        "desktop",
        "bot",
    ]


def test_internal_referrer(monkeypatch):
    monkeypatch.setattr(settings, "PUBLIC_WEB_BASE_URL", "https://gomuseum.app")
    assert internal_referrer("https://gomuseum.app/en/paris/")
    assert not internal_referrer("https://www.google.com/")
    assert not internal_referrer("")


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
    upsert_museum(s, {"slug": "orsay", "name_en": "O", "city_en": "Paris"})
    s.query(Museum).update({"published_at": datetime(2026, 1, 1)})
    s.commit()
    trials._cache.clear()
    monkeypatch.setattr(settings, "PUBLIC_WEB_BASE_URL", "https://gomuseum.app")
    monkeypatch.setattr(settings, "SHARE_PLAY_LIVE", True)
    app.dependency_overrides[get_db] = lambda: (yield s)
    yield s
    app.dependency_overrides.clear()


@pytest.fixture()
def client(db):
    return TestClient(app)


def test_page_view_logged_without_cookie(client, db):
    r = client.get(
        "/en/",
        headers={"user-agent": ANDROID, "referer": "https://gomuseum.app/fr/"},
    )
    assert "set-cookie" not in r.headers
    ev = db.query(AppEvent).filter_by(name="web_page_view").one()
    assert ev.props["page_type"] == "home" and ev.props["lang"] == "en"
    assert ev.props["device"] == "android" and ev.props["internal_ref"] is True
    assert ev.props["bot"] is False


def test_beacon_whitelist(client, db):
    ok = client.post(
        "/w/e",
        json={"name": "web_download_click", "lang": "en", "page_type": "home"},
    )
    bad = client.post("/w/e", json={"name": "drop_table", "lang": "en"})
    big = client.post("/w/e", json={"name": "web_share_click", "x": "y" * 3000})
    assert ok.status_code == bad.status_code == big.status_code == 204
    assert "set-cookie" not in ok.headers
    names = [e.name for e in db.query(AppEvent)]
    assert names == ["web_download_click"]


def test_iphone_gets_no_play_link(client):
    html = client.get("/en/", headers={"user-agent": IPHONE}).text
    assert "play.google.com" not in html
    assert "iPhone version is in development" in html


def test_desktop_gets_qr(client):
    html = client.get("/en/", headers={"user-agent": DESKTOP}).text
    assert 'class="qr"' in html and "data:image/svg+xml" in html
    android = client.get("/en/", headers={"user-agent": ANDROID}).text
    assert 'class="qr"' not in android
