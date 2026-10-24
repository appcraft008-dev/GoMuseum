"""sitemap / robots(spec 2026-10-22-website-v1 §四)。"""

import xml.etree.ElementTree as ET
from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.web import site_pages
from app.core.config import settings
from app.core.database import Base, get_db
from app.main import app
from app.models.artist import Artist
from app.models.content import ObjectContentSection
from app.models.museum import Museum
from app.models.museum_object import MuseumObject, ObjectImage
from app.services.object_importer import upsert_museum, upsert_object
from app.services.website import data as wd

NS = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}


def _work(s, m, qid, langs, artist="Q296"):
    o = upsert_object(
        s,
        m.id,
        {
            "qid": qid,
            "title_en": qid,
            "category": "painting",
            "attributes": {"artist_qid": artist},
        },
    )
    s.add(ObjectImage(object_id=o.id, image_key=f"images/{qid}/0", sort=0))
    for lang in langs:
        s.add(
            ObjectContentSection(
                object_id=o.id,
                language=lang,
                section_code="guide",
                body="x",
                status="published",
            )
        )


@pytest.fixture()
def client(monkeypatch):
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
    orsay = upsert_museum(s, {"slug": "orsay", "name_en": "O", "city_en": "Paris"})
    rijks = upsert_museum(s, {"slug": "rijks", "name_en": "R", "city_en": "Amsterdam"})
    s.add(Artist(qid="Q296", name_en="Monet"))
    _work(s, orsay, "Q1", ("en", "zh"))
    _work(s, orsay, "Q2", ("en",))
    _work(s, orsay, "Q3", ("zh",))
    _work(s, rijks, "Q9", ("en", "zh"))
    s.query(Museum).filter_by(slug="orsay").update(
        {"published_at": datetime(2026, 1, 1)}
    )
    s.commit()
    monkeypatch.setattr(wd, "THIN_MUSEUM", 2)
    monkeypatch.setattr(wd, "THIN_ARTIST", 2)
    monkeypatch.setattr(settings, "PUBLIC_WEB_BASE_URL", "https://gomuseum.app")
    site_pages._sitemap_cache.clear()
    app.dependency_overrides[get_db] = lambda: (yield s)
    yield TestClient(app)
    app.dependency_overrides.clear()


def _locs(xml):
    return [e.text for e in ET.fromstring(xml).findall(".//s:loc", NS)]


def test_robots(client):
    r = client.get("/robots.txt")
    assert r.text.splitlines() == [
        "User-agent: *",
        "Allow: /",
        "Disallow: /w/audio/",
        "Disallow: /w/e",
        "Sitemap: https://gomuseum.app/sitemap.xml",
    ]


def test_index_lists_ten_language_sitemaps(client):
    locs = _locs(client.get("/sitemap.xml").text)
    assert len(locs) == 10
    assert "https://gomuseum.app/sitemap-zh-hant.xml" in locs


def test_language_sitemap_content(client):
    r = client.get("/sitemap-en.xml")
    assert r.headers["content-type"].startswith("application/xml")
    locs = _locs(r.text)
    base = "https://gomuseum.app/en"
    assert f"{base}/" in locs
    assert f"{base}/paris/" in locs
    assert f"{base}/paris/orsay/" in locs
    assert f"{base}/paris/orsay/artists/Q296/" in locs
    assert f"{base}/paris/orsay/Q1/" in locs and f"{base}/paris/orsay/Q2/" in locs
    assert f"{base}/paris/orsay/Q3/" not in locs  # 只有 zh
    assert not any("rijks" in u or "Q9" in u or "amsterdam" in u for u in locs)


def test_thin_language_omits_listing_pages(client):
    locs = _locs(client.get("/sitemap-fr.xml").text)
    assert locs == ["https://gomuseum.app/fr/"]  # fr 无作品:只有首页


def test_alternates_only_existing_languages(client):
    xml = client.get("/sitemap-en.xml").text
    root = ET.fromstring(xml)
    for url in root.findall("s:url", NS):
        if url.find("s:loc", NS).text.endswith("/orsay/Q1/"):
            alts = {
                a.get("hreflang")
                for a in url.findall("{http://www.w3.org/1999/xhtml}link")
            }
            assert alts == {"en", "zh", "x-default"}


def test_unknown_language_sitemap_404(client):
    assert client.get("/sitemap-xx.xml").status_code == 404


def test_sitemap_is_valid_xml_when_urls_need_escaping(client, monkeypatch):
    monkeypatch.setattr(settings, "PUBLIC_WEB_BASE_URL", "https://go&museum.app")
    for path in ("/sitemap.xml", "/sitemap-en.xml"):
        root = ET.fromstring(client.get(path).content)  # 未转义的 & 会解析失败
        assert "https://go&museum.app/" in "".join(root.itertext())
