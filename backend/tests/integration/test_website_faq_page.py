"""网站问答页(spec 2026-10-31-website-faq §五/§五点五/§六)。"""

import json
import logging
import re
from datetime import date, datetime
from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.web import site_pages
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
from app.services.website import faq, trials

FIX = Path(__file__).resolve().parents[1] / "fixtures" / "faq"
MS1 = "Q737062"  # orsay 必看清单第一件


def _work(s, m, qid, langs):
    o = upsert_object(
        s, m.id, {"qid": qid, "title_en": f"T{qid}", "category": "painting"}
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
    louvre = upsert_museum(
        s, {"slug": "louvre", "name_en": "Louvre Museum", "city_en": "Paris"}
    )
    _work(s, orsay, MS1, ("en", "fr"))
    _work(s, orsay, "Q100", ("en", "fr"))
    _work(s, louvre, "Q200", ("en",))  # 卢浮宫只有英文内容
    _work(s, louvre, "Q201", ("en",))
    s.query(Museum).update({"published_at": datetime(2026, 1, 1)})
    s.commit()
    trials._cache.clear()
    site_pages._sitemap_cache.clear()
    monkeypatch.setattr(wd, "THIN_MUSEUM", 1)
    monkeypatch.setattr(settings, "SHARE_PLAY_LIVE", False)
    monkeypatch.setattr(settings, "PUBLIC_WEB_BASE_URL", "https://gomuseum.app")
    monkeypatch.setattr(faq, "FAQ_ROOT", FIX)
    monkeypatch.setattr(faq, "today", lambda: date(2026, 11, 1))
    faq.load_faq.cache_clear()
    app.dependency_overrides[get_db] = lambda: (yield s)
    yield s
    app.dependency_overrides.clear()
    faq.load_faq.cache_clear()
    site_pages._sitemap_cache.clear()


@pytest.fixture()
def client(db):
    return TestClient(app)


def _jsonld(html: str) -> dict:
    blocks = re.findall(
        r'<script type="application/ld\+json">(.*?)</script>', html, re.S
    )
    return next(d for d in map(json.loads, blocks) if d.get("@type") == "FAQPage")


def _answers(ld: dict) -> str:
    return " ".join(q["acceptedAnswer"]["text"] for q in ld["mainEntity"])


def test_faq_page_ok(client):
    r = client.get("/en/paris/faq/")
    assert r.status_code == 200
    assert 'id="closed-days"' in r.text and 'id="booking"' in r.text
    assert "Louvre Museum in Paris is closed on Tuesdays." in r.text  # 占位符换成馆名


def test_faq_404_unknown_lang_or_city(client):
    assert client.get("/xx/paris/faq/").status_code == 404
    assert client.get("/en/rome/faq/").status_code == 404
    assert client.get("/de/paris/faq/").status_code == 404  # 没有 de 文本


def test_faq_hreflang_lists_all_text_langs(client):
    r = client.get("/en/paris/faq/")
    assert 'hreflang="fr" href="https://gomuseum.app/fr/paris/faq/"' in r.text
    assert 'hreflang="x-default" href="https://gomuseum.app/en/paris/faq/"' in r.text
    assert 'hreflang="de"' not in r.text


def test_pinned_section_by_date(client, monkeypatch):
    monkeypatch.setattr(faq, "today", lambda: date(2026, 11, 20))
    t = client.get("/en/paris/faq/").text
    assert 'data-section="pinned"' in t
    assert t.index('id="christmas-new-year"') < t.index('id="closed-days"')
    monkeypatch.setattr(faq, "today", lambda: date(2026, 11, 1))
    t = client.get("/en/paris/faq/").text
    assert 'data-section="pinned"' not in t
    assert t.index('id="closed-days"') < t.index('id="christmas-new-year"')


def test_dated_item_shows_applies_to(client):
    assert (
        "Applies to: December 2026 – January 2027" in client.get("/en/paris/faq/").text
    )


def test_stale_notice_and_not_in_jsonld(client, monkeypatch):
    monkeypatch.setattr(
        faq, "today", lambda: date(2026, 12, 15)
    )  # louvre 闭馆日条目已过复核日
    r = client.get("/en/paris/faq/")
    assert "This may be out of date" in r.text
    ans = _answers(_jsonld(r.text))
    assert "closed on Tuesdays" not in ans and "closed on Mondays" in ans


def test_dated_item_hidden_after_review_by(client, monkeypatch):
    monkeypatch.setattr(faq, "today", lambda: date(2027, 1, 3))
    r = client.get("/en/paris/faq/")
    assert "XMAS-ANSWER" not in r.text and 'id="christmas-new-year"' not in r.text


def test_per_museum_skips_museum_without_lang_content(client):
    t = client.get("/fr/paris/faq/").text
    assert 'id="closed-days-orsay"' in t
    assert 'id="closed-days-louvre"' not in t  # 卢浮宫没有法语内容,馆页是 404
    assert "Tuesdays" not in _answers(_jsonld(t))


def test_must_see_link_only_when_cards(client):
    t = client.get("/en/paris/faq/").text
    assert "/en/paris/orsay/#must-see" in t
    assert "/en/paris/louvre/#must-see" not in t


def test_missing_museum_part_still_renders(client, db, caplog):
    m = upsert_museum(
        db, {"slug": "orangerie", "name_en": "Orangerie", "city_en": "Paris"}
    )
    _work(db, m, "Q300", ("en",))
    db.query(Museum).filter_by(slug="orangerie").update(
        {"published_at": datetime(2026, 1, 1)}
    )
    db.commit()
    with caplog.at_level(logging.WARNING):
        r = client.get("/en/paris/faq/")
    assert r.status_code == 200 and 'id="closed-days-orsay"' in r.text
    assert any("orangerie" in rec.getMessage() for rec in caplog.records)


def test_answers_are_escaped(client):
    t = client.get("/en/paris/faq/").text
    assert "<b>&</b>" not in t and "&lt;b&gt;" in t


def test_jsonld_is_faqpage(client):
    ld = _jsonld(client.get("/en/paris/faq/").text)
    assert ld["inLanguage"] == "en" and ld["dateModified"] == "2026-10-31"
    assert len(ld["mainEntity"]) == 3


def test_jsonld_escapes_script_close(client):
    t = client.get("/en/paris/faq/").text
    blocks = re.findall(r'<script type="application/ld\+json">(.*?)</script>', t, re.S)
    assert all("alert(1)" not in b or "<script>" not in b for b in blocks)
    assert "<script>alert(1)</script>" not in t


def test_sitemap_has_faq_with_lastmod(client):
    x = client.get("/sitemap-en.xml").text
    assert "https://gomuseum.app/en/paris/faq/</loc><lastmod>2026-10-31</lastmod>" in x
    assert "https://gomuseum.app/fr/paris/faq/" in x


def test_entry_links(client):
    for path in ("/en/", "/en/paris/", "/en/paris/orsay/"):
        assert "/en/paris/faq/" in client.get(path).text, path


def test_faq_page_view_logged(client, db):
    client.get(
        "/en/paris/faq/", headers={"user-agent": "Mozilla/5.0 (Linux; Android 14)"}
    )
    evs = db.query(AppEvent).filter_by(name="web_page_view").all()
    assert [e.props["page_type"] for e in evs] == ["faq"]


def test_no_jsonld_when_every_answer_is_stale(client, monkeypatch):
    monkeypatch.setattr(faq, "today", lambda: date(2030, 1, 1))
    t = client.get("/en/paris/faq/").text
    assert '"FAQPage"' not in t and 'id="booking"' in t  # 题照常显示,只是不进 JSON-LD


def test_placeholder_for_museum_without_db_row_uses_catalog_name(client, db):
    db.query(Museum).filter_by(
        slug="louvre"
    ).delete()  # 只剩 orsay;问句里的 {louvre} 仍要换成名字
    db.commit()
    t = client.get("/en/paris/faq/").text
    assert "{louvre}" not in t and "Louvre Museum" in t


def test_crumb_links_city_only_when_city_page_exists(client, db):
    assert '<a href="/fr/paris/">' in client.get("/fr/paris/faq/").text
    db.query(ObjectContentSection).filter_by(language="fr").delete()
    db.commit()
    assert client.get("/fr/paris/").status_code == 404  # 这种语言巴黎一件内容都没有
    r = client.get("/fr/paris/faq/")
    assert r.status_code == 200
    assert '<a href="/fr/paris/">' not in r.text  # 面包屑只写城市名,不给死链


def test_faq_fill_uses_declined_name_forms():
    names, forms = {"louvre": "Luwr", "orsay": "Orsay"}, {"louvre": {"gen": "Luwru"}}
    text = "{louvre}, do {louvre:gen}, {orsay}, {orsay:gen}"
    assert (
        site_pages._faq_fill(text, names, forms) == "Luwr, do Luwru, Orsay, Orsay"
    )  # 没配变格的回落原名,不漏占位符


def test_real_polish_text_declines_louvre():
    faq.load_faq.cache_clear()
    pl = faq.load_faq("paris", faq.FAQ_ROOT).text["pl"]
    assert pl["name_forms"]["louvre"]["gen"] == "Luwru"
    raw = yaml.safe_dump(pl["items"], allow_unicode=True)
    assert "muzeum {louvre}" not in raw and "– {louvre}" not in raw
    assert "{louvre:gen}" in raw and "{louvre:loc}" in raw
