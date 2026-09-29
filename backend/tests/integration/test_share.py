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
    s.add(CategorySection(category="painting", section_code="guide", sort_order=1))
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
        "image_url": "https://gomuseum.app/a/orsay/Q1/card.png?lang=zh",
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
