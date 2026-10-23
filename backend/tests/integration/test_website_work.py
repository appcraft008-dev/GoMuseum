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
