"""作品页 + 旧分享链接(spec 2026-10-22-website-v1 §5.4、§四)。"""

import re
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
from app.models.content import (
    CategorySection,
    ObjectContentSection,
    ObjectSuggestedQuestion,
    SectionType,
)
from app.models.museum import Museum
from app.models.museum_object import MuseumObject, ObjectImage
from app.services.object_importer import upsert_museum, upsert_object
from app.services.website import trials

MS1, MS2 = "Q737062", "Q152509"  # orsay 必看清单前两件


def _sec(s, o, code, lang, *, audio=False):
    s.add(
        ObjectContentSection(
            object_id=o.id,
            language=lang,
            section_code=code,
            body=f"{code}-body {o.qid}",
            status="published",
            audio_key=f"object-audio/{o.qid}/{lang}/{code}-x.mp3" if audio else None,
        )
    )


def _obj(s, m, qid, artist="Q296"):
    o = upsert_object(
        s,
        m.id,
        {
            "qid": qid,
            "title_en": f"Title{qid}",
            "category": "painting",
            "attributes": {"artist_qid": artist},
        },
    )
    s.add(
        ObjectImage(
            object_id=o.id, image_key=f"images/{qid}/0", sort=0, credit="Photo X"
        )
    )
    return o


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
            SectionType.__table__,
            CategorySection.__table__,
            ObjectContentSection.__table__,
            ObjectSuggestedQuestion.__table__,
            Artist.__table__,
            AppEvent.__table__,
        ],
    )
    s = sessionmaker(bind=engine)()
    for code, sort in (("guide", 0), ("background", 1), ("analysis", 2)):
        s.add(SectionType(code=code, label_zh=code, label_en=code, default_sort=sort))
    s.add(CategorySection(category="painting", section_code="background", sort_order=1))
    s.add(CategorySection(category="painting", section_code="analysis", sort_order=2))
    orsay = upsert_museum(s, {"slug": "orsay", "name_en": "Orsay", "city_en": "Paris"})
    s.add(
        Artist(
            qid="Q296",
            name_en="Claude Monet",
            bio={"en": "Monet bio."},
            bio_audio={"en": "artist-audio/Q296/en.mp3"},
        )
    )
    trial = _obj(s, orsay, MS1)
    for code in ("guide", "background", "analysis"):
        _sec(s, trial, code, "en", audio=code != "analysis")
    s.add(
        ObjectSuggestedQuestion(
            object_id=trial.id,
            language="en",
            question="Why?",
            answer="Because.",
            sort=1,
            status="published",
            audio_key="object-audio/qa.mp3",
        )
    )
    other = _obj(s, orsay, MS2)
    _sec(s, other, "guide", "en")
    plain = _obj(s, orsay, "Q500")  # 不在必看清单 → 不会是试听件
    _sec(s, plain, "guide", "en", audio=True)
    _sec(s, plain, "background", "en", audio=True)
    s.query(Museum).filter_by(slug="orsay").update(
        {"published_at": datetime(2026, 1, 1)}
    )
    s.commit()
    trials._cache.clear()
    monkeypatch.setattr(settings, "PUBLIC_WEB_BASE_URL", "https://gomuseum.app")

    def _boom(*a, **k):
        raise AssertionError("网页层不许点火/合成")

    monkeypatch.setattr("app.services.enrichment.lazy.maybe_trigger", _boom)
    monkeypatch.setattr("app.services.tts_service.TTSService.generate_audio", _boom)
    app.dependency_overrides[get_db] = lambda: (yield s)
    yield s
    app.dependency_overrides.clear()


@pytest.fixture()
def client(db):
    return TestClient(app, follow_redirects=False)


def _keys(html):
    return re.findall(r'data-key="([^"]+)"', html)


def test_trial_work_sections_in_order_with_audio(client):
    r = client.get(f"/en/paris/orsay/{MS1}/")
    assert r.status_code == 200
    assert _keys(r.text) == ["guide", "artist_bio", "background", "analysis", "qa-1"]
    srcs = re.findall(r'data-src="([^"]+)"', r.text)
    assert f"/w/audio/orsay/{MS1}/guide?lang=en" in srcs
    assert f"/w/audio/orsay/{MS1}/artist_bio?lang=en" in srcs
    assert not any("/analysis?" in u for u in srcs)  # 没录的段不给 ▶


def test_non_trial_work_has_no_audio_but_marks_app(client):
    html = client.get("/en/paris/orsay/Q500/").text
    assert "/w/audio/" not in html and ".mp3" not in html
    assert "This work has audio narration" in html
    # guide、background、作者介绍(作者卡有 en 音频)三段有音频
    assert html.count("Listen in the app") == 3


def test_trial_player_has_seek_and_speed(client):
    # 和 App 一样:进度可拖、倍速可切;非试听件没有播放器
    trial = client.get(f"/en/paris/orsay/{MS1}/").text
    assert 'id="pseek" type="range"' in trial
    assert 'id="pspeed"' in trial and ">1x<" in trial
    plain = client.get("/en/paris/orsay/Q500/").text
    assert 'id="pseek"' not in plain and 'id="pspeed"' not in plain


def test_work_404_without_language_text(client):
    r = client.get(f"/fr/paris/orsay/{MS1}/")
    assert r.status_code == 404
    assert r.headers.get("x-robots-tag") == "noindex"
    assert client.get("/en/paris/orsay/Q404/").status_code == 404


def test_work_hreflang_only_languages_with_text(client):
    html = client.get(f"/en/paris/orsay/{MS1}/").text
    assert 'hreflang="en"' in html and 'hreflang="fr"' not in html


def test_other_must_see_excludes_current_and_credit_shown(client):
    html = client.get(f"/en/paris/orsay/{MS1}/").text
    other = html.split('data-section="other-must-see"')[1].split("</section>")[0]
    assert f"/en/paris/orsay/{MS2}/" in other and f"/{MS1}/" not in other
    assert "Photo X" in html


def test_legacy_link_unchanged_until_website_live(client, monkeypatch):
    monkeypatch.setattr(settings, "WEBSITE_LIVE", False)
    assert client.get(f"/a/orsay/{MS1}?lang=en").status_code == 200


def test_legacy_link_301_keeps_source(client, db, monkeypatch):
    monkeypatch.setattr(settings, "WEBSITE_LIVE", True)
    r = client.get(f"/a/orsay/{MS1}?lang=en&s=wa")
    assert r.status_code == 301
    assert r.headers["location"] == f"/en/paris/orsay/{MS1}/?s=wa"
    # 301 不能被永久缓存,否则 WEBSITE_LIVE 回滚后已缓存的访客仍被送去新页
    assert r.headers["cache-control"] == "public, max-age=86400"
    ev = db.query(AppEvent).filter_by(name="share_page_view").one()
    assert ev.props["source"] == "wa"
    assert client.get("/a/orsay/Q404?lang=en").status_code == 404


def _extra_lang(db, qid, lang):
    o = db.query(MuseumObject).filter_by(qid=qid).one()
    _sec(db, o, "guide", lang)
    db.commit()


def test_work_hreflang_limited_to_site_languages(client, db):
    _extra_lang(db, MS1, "pt")  # 库里有但网站不支持的语言
    html = client.get(f"/en/paris/orsay/{MS1}/").text
    assert 'hreflang="pt"' not in html


def test_legacy_link_never_lands_on_unsupported_language(client, db, monkeypatch):
    monkeypatch.setattr(settings, "WEBSITE_LIVE", True)
    _extra_lang(db, MS1, "pt")
    r = client.get(f"/a/orsay/{MS1}", headers={"accept-language": "pt"})
    assert r.status_code == 301 and r.headers["location"].startswith("/en/")
    r = client.get(f"/a/orsay/{MS1}", params={"lang": "en", "s": "a b&c"})
    assert r.headers["location"].endswith("?s=a%20b%26c")


ANDROID = {"user-agent": "Mozilla/5.0 (Linux; Android 14; Pixel 8) Mobile"}
IPHONE = {"user-agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X)"}


def _top(html):
    """作品页首屏(下载区之前、讲解段之前)。"""
    return html.split('id="sections"')[0]


@pytest.fixture()
def no_audio(db):
    """本件和作者都没音频:首屏没有「在 App 里听」条,才轮到下载按钮。"""
    m = db.query(Museum).filter_by(slug="orsay").one()
    _sec(db, _obj(db, m, "Q501", artist="Q999"), "guide", "en")
    db.commit()
    return "/en/paris/orsay/Q501/"


def test_work_top_cta_goes_straight_to_play_on_android(client, monkeypatch, no_audio):
    monkeypatch.setattr(settings, "SHARE_PLAY_LIVE", True)
    html = client.get(no_audio, headers=ANDROID).text
    m = re.search(r'<a class="btn work-cta" href="([^"]+)"', _top(html))
    assert m and "play.google.com" in m.group(1)
    assert "utm_content%3Dwork" in m.group(1)


def test_work_top_cta_scrolls_to_download_on_desktop(client, monkeypatch, no_audio):
    monkeypatch.setattr(settings, "SHARE_PLAY_LIVE", True)
    html = client.get(no_audio).text
    assert '<a class="btn work-cta" href="#download"' in _top(html)


def test_work_top_cta_also_on_trial_work(client, monkeypatch):
    monkeypatch.setattr(settings, "SHARE_PLAY_LIVE", True)
    assert "work-cta" in _top(client.get(f"/en/paris/orsay/{MS1}/").text)


def test_work_top_cta_hidden_on_iphone(client, monkeypatch, no_audio):
    monkeypatch.setattr(settings, "SHARE_PLAY_LIVE", True)
    assert "work-cta" not in _top(client.get(no_audio, headers=IPHONE).text)


def test_audio_lockbar_goes_straight_to_play_without_second_cta(client, monkeypatch):
    monkeypatch.setattr(settings, "SHARE_PLAY_LIVE", True)
    top = _top(client.get("/en/paris/orsay/Q500/", headers=ANDROID).text)
    m = re.search(r'<a class="lockbar" href="([^"]+)"', top)
    assert m and "play.google.com" in m.group(1)
    assert "work-cta" not in top


def test_work_cta_without_play_link_falls_back_to_download(
    client, monkeypatch, no_audio
):
    monkeypatch.setattr(settings, "SHARE_PLAY_LIVE", False)
    top = _top(client.get(no_audio, headers=ANDROID).text)
    assert '<a class="btn work-cta" href="#download"' in top


def test_work_title_says_explained_but_h1_stays_plain(client):
    html = client.get(f"/en/paris/orsay/{MS2}/").text
    title = re.search(r"<title>(.*?)</title>", html).group(1)
    assert title.startswith(f"Title{MS2} explained")
    assert title.endswith("· GoMuseum")
    assert re.search(rf"<h1[^>]*>Title{MS2}</h1>", html)


def test_work_description_leads_with_artist_and_museum(client):
    html = client.get(f"/en/paris/orsay/{MS2}/").text
    d = re.search(r'<meta name="description" content="([^"]*)"', html).group(1)
    assert d.startswith("Claude Monet")
    assert "Orsay" in d and f"guide-body {MS2}" in d


def test_work_title_copy_exists_for_every_site_language():
    from app.services.website.copy import COPY, t
    from app.services.website.data import LANGS

    for lang in LANGS:
        assert "work_title" in COPY[lang], lang
        assert "X" in t(lang, "work_title", title="X")


def test_work_shows_bce_in_byline_but_not_description(client, monkeypatch):
    from app.api.web import site_pages

    real = site_pages.get_object_content

    def with_date(*a, **k):
        data = real(*a, **k)
        data["facts"] = {"date": "-140"}
        return data

    monkeypatch.setattr(site_pages, "get_object_content", with_date)
    html = client.get(f"/en/paris/orsay/{MS2}/").text
    byline = re.search(r'<p class="byline">(.*?)</p>', html).group(1)
    assert "140 BC" in byline and "-140" not in byline
    d = re.search(r'<meta name="description" content="([^"]*)"', html).group(1)
    assert "-140" not in d
