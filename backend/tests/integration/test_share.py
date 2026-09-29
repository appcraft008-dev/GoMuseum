"""分享层(spec 2026-09-20-share-web-pages-design)。

三处出口(内容接口 share 字段 / 公开网页 / 分享图)共用 app.services.share 的判定。
这里钉的是会被后人顺手改坏的几条:隐身馆对外人不可分享(预览账号也不行)、
按**请求语言**判有没有正文、网页里绝不出现音频、匿名访问不点燃生成。
"""

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

AUDIO_KEY = "object-audio/Q1/zh/guide-7f3a9c.mp3"
PREVIEW = {"Authorization": "Bearer preview"}


class _User:
    def __init__(self, uid, can_preview):
        self.id = uid
        self.can_preview = can_preview
        self.is_guest = False


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
    s.add(SectionType(code="guide", label_zh="讲解", label_en="Guide", default_sort=1))
    # 与 prod 同形:guide 不在 category_sections 里(它走 default_guide,不进 tabs)
    s.add(CategorySection(category="painting", section_code="background", sort_order=1))
    # orsay 已放出:Q1 有主图+中文正文+音频;Q2 有中文正文但无图;Q3 无任何正文
    # rijks 隐身:Q9 什么都有
    for slug, qid, body, image in (
        ("orsay", "Q1", "这是一幅画。它画于 1863 年。", True),
        ("orsay", "Q2", "无图的一件。", False),
        ("orsay", "Q3", None, True),
        ("rijks", "Q9", "夜巡正文。", True),
    ):
        m = upsert_museum(s, {"slug": slug, "name_en": slug, "city_en": "X"})
        o = upsert_object(
            s,
            m.id,
            {
                "qid": qid,
                "title_en": f"T{qid}",
                "category": "painting",
                "attributes": {},
            },
        )
        if image:
            s.add(
                ObjectImage(
                    object_id=o.id,
                    image_key=f"images/{qid}/0",
                    sort=0,
                    credit="Photo: Test Museum",
                )
            )
        if body:
            s.add(
                ObjectContentSection(
                    object_id=o.id,
                    language="zh",
                    section_code="guide",
                    body=body,
                    audio_key=AUDIO_KEY if qid == "Q1" else None,
                )
            )
    s.query(Museum).filter_by(slug="orsay").update(
        {"published_at": datetime(2026, 1, 1)}
    )
    s.commit()

    from app.services.auth_service import AuthService

    def _current(db, token):
        if token != "preview":
            raise ValueError("bad token")
        return _User("u-preview", True)

    monkeypatch.setattr(AuthService, "get_current_user", staticmethod(_current))
    monkeypatch.setattr(settings, "PUBLIC_WEB_BASE_URL", "https://gomuseum.app")
    app.dependency_overrides[get_db] = lambda: (yield s)
    yield s
    app.dependency_overrides.clear()


@pytest.fixture()
def client(db):
    return TestClient(app)


def _content(client, slug, qid, lang="zh", headers=None):
    r = client.get(
        f"/api/v1/museums/{slug}/objects/{qid}/content",
        params={"language": lang},
        headers=headers or {},
    )
    assert r.status_code == 200, r.text
    return r.json()


def test_share_field_for_shareable_object(client):
    share = _content(client, "orsay", "Q1")["share"]
    assert share == {
        "url": "https://gomuseum.app/a/orsay/Q1?lang=zh&s=app",
        "text": "《TQ1》",
        "image_url": "https://gomuseum.app/a/orsay/Q1/card.jpg?lang=zh",
    }


def test_share_null_when_language_has_no_guide(client):
    # 对象在 zh 有正文,en 没有 —— 按请求语言判,不按对象级状态
    assert _content(client, "orsay", "Q1", lang="en")["share"] is None


def test_share_null_without_image(client):
    assert _content(client, "orsay", "Q2")["share"] is None


def test_share_null_without_guide_text(client):
    assert _content(client, "orsay", "Q3")["share"] is None


def test_share_null_for_hidden_museum_even_for_preview_account(client):
    # 预览账号看得到隐身馆,但分享出去的链接朋友打开是 404 → 不给分享
    assert _content(client, "rijks", "Q9", headers=PREVIEW)["share"] is None


def test_pick_language():
    from app.services.share import pick_language

    assert pick_language("fr", "", ["en", "fr"]) == "fr"
    assert pick_language("de", "", ["en", "zh"]) == "en"  # 请求的没有 → en
    assert pick_language("", "zh-TW,zh;q=0.9", ["zh", "zh-hant"]) == "zh-hant"
    assert pick_language("", "zh-CN,zh;q=0.9", ["en", "zh"]) == "zh"
    assert pick_language("", "ja-JP", ["ja", "en"]) == "ja"
    assert pick_language("", "", ["zh"]) == "zh"  # 连 en 都没有 → 第一个


def test_share_text_per_language():
    from app.services.share import share_text

    assert share_text("门闩", "弗拉戈纳尔", "zh") == "《门闩》— 弗拉戈纳尔"
    assert share_text("夜警", "レンブラント", "ja") == "『夜警』— レンブラント"
    assert share_text("The Bolt", "Fragonard", "en") == "The Bolt — Fragonard"
    assert share_text("The Bolt", None, "en") == "The Bolt"


ANDROID = {"User-Agent": "Mozilla/5.0 (Linux; Android 14; Pixel 8) Chrome/129 Mobile"}
WECHAT = {"User-Agent": ANDROID["User-Agent"] + " MicroMessenger/8.0.50"}


def test_page_renders_text(client):
    r = client.get("/a/orsay/Q1?lang=zh&s=app")
    assert r.status_code == 200
    assert "TQ1" in r.text and "这是一幅画。" in r.text
    assert 'property="og:image"' in r.text
    assert "这件有语音讲解，在 App 里听" in r.text  # Q1 guide 有音频 → 只写一句
    # 预览描述是固定一句,不是正文开头(正文开头 96% 是开场白套话)
    assert 'property="og:description" content="在 GoMuseum 读这件作品的讲解"' in r.text


def test_page_never_contains_audio(client):
    html = client.get("/a/orsay/Q1?lang=zh").text
    for leak in (AUDIO_KEY, "object-audio", "/audio", ".mp3", "<audio"):
        assert leak not in html, f"网页里出现了音频痕迹: {leak}"


def test_page_404_is_identical_for_hidden_unknown_and_empty(client):
    hidden = client.get("/a/rijks/Q9?lang=zh")
    unknown = client.get("/a/orsay/Q404?lang=zh")
    empty = client.get("/a/orsay/Q3?lang=zh")
    wrong_museum = client.get("/a/rijks/Q1?lang=zh")
    for r in (hidden, unknown, empty, wrong_museum):
        assert r.status_code == 404
        assert r.headers["x-robots-tag"] == "noindex"
        assert r.text == unknown.text


def test_page_redirects_language_without_text(client):
    r = client.get("/a/orsay/Q1?lang=en&s=app", follow_redirects=False)
    assert r.status_code == 302
    assert r.headers["location"] == "/a/orsay/Q1?lang=zh&s=app"


def test_page_never_triggers_generation(client, monkeypatch):
    import app.services.enrichment.lazy as lazy

    def boom(*a, **kw):
        raise AssertionError("公开网页点燃了懒生成")

    monkeypatch.setattr(lazy, "maybe_trigger", boom)
    assert client.get("/a/orsay/Q1?lang=zh").status_code == 200


def test_cta_has_no_play_link_before_launch(client, monkeypatch):
    monkeypatch.setattr(settings, "SHARE_PLAY_LIVE", False)
    assert (
        "play.google.com" not in client.get("/a/orsay/Q1?lang=zh", headers=ANDROID).text
    )


def test_cta_links_play_after_launch_but_not_in_wechat(client, monkeypatch):
    monkeypatch.setattr(settings, "SHARE_PLAY_LIVE", True)
    assert "play.google.com" in client.get("/a/orsay/Q1?lang=zh", headers=ANDROID).text
    assert (
        "play.google.com" not in client.get("/a/orsay/Q1?lang=zh", headers=WECHAT).text
    )


def test_page_view_logged_with_source(client, db):
    client.get("/a/orsay/Q1?lang=zh&s=app")
    ev = db.query(AppEvent).filter_by(name="share_page_view").one()
    assert ev.props["source"] == "app"


def test_card_404_matches_page_rules(client):
    for path in (
        "/a/rijks/Q9/card.jpg?lang=zh",
        "/a/orsay/Q3/card.jpg?lang=zh",
        "/a/orsay/Q2/card.jpg?lang=zh",
    ):  # 隐身 / 无正文 / 无图
        assert client.get(path).status_code == 404, path


def test_card_renders_jpeg(client, monkeypatch):
    import app.api.web.share_pages as sp

    sp._card_bytes.cache_clear()
    monkeypatch.setattr(sp, "render_card", lambda image, **kw: b"jpeg-fake")

    class _Storage:
        def get(self, key):
            assert key == "images/Q1/0_large.jpg"
            return b"jpeg-bytes"

        def public_url(self, key):
            return f"https://cdn.test/{key}"

    monkeypatch.setattr(sp, "get_object_storage", lambda: _Storage())
    r = client.get("/a/orsay/Q1/card.jpg?lang=zh")
    assert r.status_code == 200
    assert r.headers["content-type"] == "image/jpeg"
    assert "max-age" in r.headers["cache-control"]


def test_card_credit_drops_painter_name(client, db, monkeypatch):
    """Commons 把画家填进 credit;App/网页都去重了,分享图不能多出一行画家名(staging 实测过)。"""
    import app.api.web.share_pages as sp
    from app.services.storage import get_object_storage

    sp._card_bytes.cache_clear()
    seen = {}
    monkeypatch.setattr(
        sp, "render_card", lambda image, **kw: seen.update(kw) or b"jpg"
    )
    real = get_object_storage()

    class _Storage:
        def get(self, key):
            return b"jpeg-bytes"

        def public_url(self, key):
            return real.public_url(key)

    monkeypatch.setattr(sp, "get_object_storage", lambda: _Storage())
    db.query(MuseumObject).filter_by(qid="Q1").update({"artist_en": "Édouard Manet"})
    db.query(ObjectImage).update({"credit": "Édouard Manet"})
    db.commit()
    assert client.get("/a/orsay/Q1/card.jpg?lang=zh").status_code == 200
    assert seen["credit"] is None


def test_copy_has_same_keys_in_every_language():
    """网页按 copy[key] 取文案,某语言漏一个键 = 该语言网页 500。"""
    from app.services.share import COPY

    keys = set(COPY["en"])
    assert {lang: set(c) for lang, c in COPY.items() if set(c) != keys} == {}


# 机器访问标记:只打标记不丢数据,统计时过滤。正负样本都要有 ——
# 应用内浏览器(微信/Facebook/Instagram)背后是真人,手机型号里也可能带 bot(CUBOT)。
BOT_UAS = [
    "WhatsApp/2.23.20.0 A",  # 发链接时生成预览卡片
    "facebookexternalhit/1.1 (+http://www.facebook.com/externalhit_uatext.php)",
    "TelegramBot (like TwitterBot)",
    "Slackbot-LinkExpanding 1.0 (+https://api.slack.com/robots)",
    "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)",
    "Mozilla/5.0 (compatible; bingbot/2.0; +http://www.bing.com/bingbot.htm)",
    "Twitterbot/1.0",
    "Mozilla/5.0 (compatible; Discordbot/2.0; +https://discordapp.com)",
    "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko; compatible; GPTBot/1.2)",
    "curl/8.4.0",
    "python-requests/2.31.0",
    "",
]
HUMAN_UAS = [
    "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/129.0 Mobile Safari/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Linux; Android 13; V2227A) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/111.0 Mobile Safari/537.36 XWEB/1160065 MMWEBSDK/20231202 "
    "MicroMessenger/8.0.47.2560(0x28002F35) WeChat/arm64 Weixin NetType/WIFI",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Mobile/15E148 [FBAN/FBIOS;FBAV/470.0.0.40.97;FBBV/620000000]",
    "Mozilla/5.0 (Linux; Android 14; SM-S918B) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/129.0 Mobile Safari/537.36 Instagram 350.0.0.0 Android",
    "Mozilla/5.0 (Linux; Android 10; CUBOT X30 Build/QP1A) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0 Mobile Safari/537.36",
]


@pytest.mark.parametrize("ua", BOT_UAS)
def test_is_bot_catches_previewers_and_crawlers(ua):
    from app.services.share import is_bot

    assert is_bot(ua), ua


@pytest.mark.parametrize("ua", HUMAN_UAS)
def test_is_bot_spares_real_people(ua):
    from app.services.share import is_bot

    assert not is_bot(ua), ua


def test_page_view_marks_bot_and_keeps_ua(client, db):
    client.get("/a/orsay/Q1?lang=zh&s=app", headers={"User-Agent": BOT_UAS[0]})
    client.get("/a/orsay/Q1?lang=zh&s=app", headers={"User-Agent": HUMAN_UAS[0]})
    evs = db.query(AppEvent).filter_by(name="share_page_view").all()
    assert sorted(e.props["bot"] for e in evs) == [False, True]
    assert {e.props["ua"] for e in evs} == {BOT_UAS[0], HUMAN_UAS[0][:200]}


def _fake_card(monkeypatch):
    """替身:记下每次合成的参数,不真画图。"""
    import app.api.web.share_pages as sp

    sp._card_bytes.cache_clear()
    calls = []
    monkeypatch.setattr(
        sp, "render_card", lambda image, **kw: calls.append(kw) or b"jpg"
    )

    class _Storage:
        def get(self, key):
            return b"jpeg-bytes"

        def public_url(self, key):
            return f"https://cdn.test/{key}"

    monkeypatch.setattr(sp, "get_object_storage", lambda: _Storage())
    return calls


def test_card_qr_points_back_to_page(client, monkeypatch):
    """微信收图会丢掉链接文字 → 分享图上的二维码是回到网页的唯一路径;s=qr 单独计数。"""
    calls = _fake_card(monkeypatch)
    client.get("/a/orsay/Q1/card.jpg?lang=zh")
    assert calls[0]["qr_url"] == "https://gomuseum.app/a/orsay/Q1?lang=zh&s=qr"
    assert calls[0]["qr_caption"] == "扫码看讲解"


def test_card_rendered_once_per_content(client, monkeypatch):
    """同一件同一语言第二次分享不再现场合成(原先每次 2 秒)。"""
    calls = _fake_card(monkeypatch)
    for _ in range(3):
        assert client.get("/a/orsay/Q1/card.jpg?lang=zh").status_code == 200
    assert len(calls) == 1


def test_audio_note_is_play_entry_after_launch(client, monkeypatch):
    monkeypatch.setattr(settings, "SHARE_PLAY_LIVE", True)
    html = client.get("/a/orsay/Q1?lang=zh", headers=ANDROID).text
    assert '<a class="audio" href="https://play.google.com' in html
    # 微信里打不开 Play、iPhone 没有 App → 只是一句话
    for ua in (WECHAT, {"User-Agent": HUMAN_UAS[1]}):
        html = client.get("/a/orsay/Q1?lang=zh", headers=ua).text
        assert '<div class="audio">' in html and '<a class="audio"' not in html


def test_audio_note_plain_before_launch(client, monkeypatch):
    monkeypatch.setattr(settings, "SHARE_PLAY_LIVE", False)
    html = client.get("/a/orsay/Q1?lang=zh", headers=ANDROID).text
    assert '<div class="audio">' in html and '<a class="audio"' not in html
