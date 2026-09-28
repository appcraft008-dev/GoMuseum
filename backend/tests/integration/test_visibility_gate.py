"""上新馆可见性闸的 2×2(spec 2026-09-20 §七):

|            | 已放出馆 | 隐身馆   |
|------------|----------|----------|
| 普通调用者 | 看得到   | **看不到** |
| 预览调用者 | 看得到   | 看得到   |

每个接了闸的端点都跑这张表(登记簿见 tests/unit/api/test_visibility_routes.py)。
只测"预览者看得到"那一格会绿,而且证明不了任何事 —— 洞在没测的格子里永远是绿的。

两条额外纪律:
- **隐身 = 与"不存在"不可区分**:断言响应体与未知 slug/qid 的一模一样(不是 403)。
- **凡涉及花钱的格子,断言花钱那一步没被调用**,不只断言 404 —— 先调 LLM/TTS
  再返回 404 的实现照样全绿,而钱已经付了。
"""

from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

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
from app.models.purchase import Entitlement
from app.models.recognition_event import RecognitionEvent
from app.models.user_benefits import UserBenefits
from app.services.object_importer import upsert_museum, upsert_object

NORMAL = {"Authorization": "Bearer normal"}
PREVIEW = {"Authorization": "Bearer preview"}
CALLERS = {"anon": {}, "normal": NORMAL}  # 两种"普通调用者"都要看不到


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
            UserBenefits.__table__,
            Entitlement.__table__,
            RecognitionEvent.__table__,
            AppEvent.__table__,
        ],
    )
    s = sessionmaker(bind=engine)()
    s.add(SectionType(code="guide", label_zh="讲解", label_en="Guide", default_sort=1))
    s.add(CategorySection(category="painting", section_code="guide", sort_order=1))
    for slug, qid, title in (("orsay", "Q1", "Olympia"), ("rijks", "Q9", "Nightwatch")):
        m = upsert_museum(s, {"slug": slug, "name_en": slug, "city_en": "X"})
        o = upsert_object(
            s,
            m.id,
            {
                "qid": qid,
                "title_en": title,
                "category": "painting",
                "image": f"http://i/{qid}.jpg",
                "attributes": {},
            },
        )
        s.add(
            ObjectContentSection(
                object_id=o.id, language="zh", section_code="guide", body="正文"
            )
        )
    # 只放出奥赛;rijks 保持 published_at IS NULL(准备中)
    s.query(Museum).filter_by(slug="orsay").update(
        {"published_at": datetime(2026, 1, 1)}
    )
    s.add(UserBenefits(user_id="u-normal", recognition_quota=5))
    s.add(UserBenefits(user_id="u-preview", recognition_quota=5))
    s.commit()

    from app.services.auth_service import AuthService

    users = {
        "normal": _User("u-normal", False),
        "preview": _User("u-preview", True),
    }

    def _current(db, token):
        if token not in users:
            raise ValueError("bad token")
        return users[token]

    monkeypatch.setattr(AuthService, "get_current_user", staticmethod(_current))
    # 搜索索引是进程内缓存,别让别的用例的库串进来
    monkeypatch.setattr("app.services.search.inprocess._index_cache", {})
    app.dependency_overrides[get_db] = lambda: (yield s)
    yield s
    app.dependency_overrides.pop(get_db, None)


@pytest.fixture()
def client(db):
    return TestClient(app)


def _spy(monkeypatch, target, ret=None):
    calls = []

    def fake(*a, **k):
        calls.append((a, k))
        return ret

    monkeypatch.setattr(target, fake)
    return calls


# ---- 发现:馆列表 / 全局搜索 -------------------------------------------------


@pytest.mark.parametrize("who", list(CALLERS))
def test_list_hides_unpublished_museum(client, who):
    slugs = [
        m["slug"] for m in client.get("/api/v1/museums", headers=CALLERS[who]).json()
    ]
    assert slugs == ["orsay"]


def test_list_shows_unpublished_museum_to_preview(client):
    slugs = {m["slug"] for m in client.get("/api/v1/museums", headers=PREVIEW).json()}
    assert slugs == {"orsay", "rijks"}


@pytest.mark.parametrize("who", list(CALLERS))
def test_global_search_hides_unpublished(client, who):
    r = client.get("/api/v1/search?q=nightwatch", headers=CALLERS[who]).json()
    assert r["objects"] == []
    r = client.get("/api/v1/search?q=rijks", headers=CALLERS[who]).json()
    assert r["museums"] == []


def test_global_search_shows_unpublished_to_preview(client):
    r = client.get("/api/v1/search?q=nightwatch", headers=PREVIEW).json()
    assert [o["qid"] for o in r["objects"]] == ["Q9"]
    r = client.get("/api/v1/search?q=rijks", headers=PREVIEW).json()
    assert [m["slug"] for m in r["museums"]] == ["rijks"]


def test_global_search_still_finds_published(client):
    r = client.get("/api/v1/search?q=olympia").json()
    assert [o["qid"] for o in r["objects"]] == ["Q1"]


# ---- 直达:按 slug 的端点 ----------------------------------------------------

SLUG_PATHS = [
    "/api/v1/museums/{s}",
    "/api/v1/museums/{s}/objects",
    "/api/v1/museums/{s}/search?q=a",
]


@pytest.mark.parametrize("path", SLUG_PATHS)
@pytest.mark.parametrize("who", list(CALLERS))
def test_hidden_slug_is_indistinguishable_from_unknown(client, path, who):
    hidden = client.get(path.format(s="rijks"), headers=CALLERS[who])
    unknown = client.get(path.format(s="nope"), headers=CALLERS[who])
    assert hidden.status_code == unknown.status_code == 404
    assert hidden.text.replace("rijks", "nope") == unknown.text


@pytest.mark.parametrize("path", SLUG_PATHS)
def test_hidden_slug_open_to_preview(client, path):
    assert client.get(path.format(s="rijks"), headers=PREVIEW).status_code == 200


@pytest.mark.parametrize("path", SLUG_PATHS)
@pytest.mark.parametrize("who", ["anon", "normal", "preview"])
def test_published_slug_open_to_everyone(client, path, who):
    headers = {**CALLERS, "preview": PREVIEW}[who]
    assert client.get(path.format(s="orsay"), headers=headers).status_code == 200


# ---- 讲解:闸必须站在懒生成(付费 LLM)上游 ------------------------------------


def test_hidden_content_404_and_never_triggers_generation(client, monkeypatch):
    calls = _spy(monkeypatch, "app.services.enrichment.lazy.maybe_trigger")
    hidden = client.get("/api/v1/museums/rijks/objects/Q9/content", headers=NORMAL)
    unknown = client.get("/api/v1/museums/orsay/objects/Q404/content", headers=NORMAL)
    assert hidden.status_code == unknown.status_code == 404
    assert hidden.text.replace("Q9", "Q404") == unknown.text
    # 借已放出馆的 slug 去拿隐身馆的 qid:同样看不到
    assert (
        client.get(
            "/api/v1/museums/orsay/objects/Q9/content", headers=NORMAL
        ).status_code
        == 404
    )
    assert calls == [q for q in calls if q[0][1] == "Q404"], "隐身藏品绝不能点燃懒生成"


def test_hidden_content_open_to_preview(client, monkeypatch):
    _spy(monkeypatch, "app.services.enrichment.lazy.maybe_trigger")
    r = client.get(
        "/api/v1/museums/rijks/objects/Q9/content?language=zh", headers=PREVIEW
    )
    assert r.status_code == 200


# ---- 音频:闸必须站在 TTS 上游 -----------------------------------------------


@pytest.fixture()
def audio_spies(monkeypatch):
    # 付费墙另有专测;这里让它放行,只考可见性
    monkeypatch.setattr(
        "app.api.v1.endpoints.museums._require_audio_access", lambda *a, **k: "u"
    )
    made = _spy(
        monkeypatch,
        "app.services.enrichment.lazy_audio.get_or_make_audio_url",
        ret=("http://a/x.mp3", "ok"),
    )

    async def fake_stream(*a, **k):
        streamed.append(a)
        return "cached", "http://a/x.mp3"

    streamed = []
    monkeypatch.setattr(
        "app.services.enrichment.streaming_audio.stream_section_audio", fake_stream
    )
    return made, streamed


@pytest.mark.parametrize("suffix", ["audio", "audio/stream"])
def test_hidden_audio_404_and_never_synthesizes(client, audio_spies, suffix):
    made, streamed = audio_spies
    r = client.get(f"/api/v1/museums/rijks/objects/Q9/{suffix}", headers=NORMAL)
    assert r.status_code == 404
    r = client.get(f"/api/v1/museums/orsay/objects/Q9/{suffix}", headers=NORMAL)
    assert r.status_code == 404
    assert made == [] and streamed == [], "隐身藏品绝不能触发 TTS"


@pytest.mark.parametrize("suffix", ["audio", "audio/stream"])
def test_hidden_audio_open_to_preview(client, audio_spies, suffix):
    r = client.get(f"/api/v1/museums/rijks/objects/Q9/{suffix}", headers=PREVIEW)
    assert r.status_code == 200


# ---- 识别 -------------------------------------------------------------------


def _img():
    return {"image": ("a.jpg", b"fake", "image/jpeg")}


@pytest.mark.parametrize(
    "url",
    ["/api/v1/museums/rijks/recognize", "/api/v1/recognize?museum=rijks"],
)
def test_recognize_in_hidden_museum_404_before_any_work(client, monkeypatch, url):
    calls = _spy(monkeypatch, "app.services.recognition.service.recognize_billed")
    r = client.post(url, files=_img(), headers=NORMAL)
    assert r.status_code == 404
    assert calls == [], "隐身馆:扣费/GPT/嵌入之前就拦下"


def test_global_recognize_passes_fresh_visible_set(client, db, monkeypatch):
    calls = _spy(
        monkeypatch,
        "app.services.recognition.service.recognize_billed",
        ret={"outcome": "unrecognized", "match": None, "candidates": []},
    )
    client.post("/api/v1/recognize", files=_img(), headers=NORMAL)
    client.post("/api/v1/recognize", files=_img(), headers=PREVIEW)
    orsay = db.query(Museum).filter_by(slug="orsay").one().id
    assert calls[0][1]["visible"] == {orsay}
    assert calls[1][1]["visible"] is None


def test_recognition_drops_hidden_hits_and_splits_cache(db):
    from app.services.recognition.service import _cache_key, _drop_hidden

    orsay = db.query(Museum).filter_by(slug="orsay").one().id
    ranked = [("Q9", 0.95), ("Q1", 0.9)]
    assert _drop_hidden(db, ranked, {orsay}) == [("Q1", 0.9)]
    assert _drop_hidden(db, ranked, None) == ranked
    # 预览者的结果(可能含隐身藏品)绝不能被普通用户从缓存命中
    assert _cache_key(None, "sha", "zh", None) != _cache_key(None, "sha", "zh", {orsay})


def test_confirm_on_hidden_qid_charges_nothing(client, db, monkeypatch):
    calls = _spy(monkeypatch, "app.services.recognition.events.confirm_event", ret=True)
    r = client.post(
        "/api/v1/recognize/confirm", json={"phash": "p", "qid": "Q9"}, headers=NORMAL
    )
    assert r.status_code == 204
    assert calls == []
    assert (
        db.query(UserBenefits).filter_by(user_id="u-normal").one().recognition_quota
        == 5
    )


# ---- 手动解锁:闸必须站在扣额度上游 -----------------------------------------


def test_unlock_hidden_qid_is_404_and_keeps_quota(client, db):
    hidden = client.post("/api/v1/entitlements/audio/unlock?qid=Q9", headers=NORMAL)
    unknown = client.post("/api/v1/entitlements/audio/unlock?qid=Q404", headers=NORMAL)
    assert hidden.status_code == unknown.status_code == 404
    assert hidden.json() == unknown.json()
    assert (
        db.query(UserBenefits).filter_by(user_id="u-normal").one().recognition_quota
        == 5
    )


def test_unlock_hidden_qid_open_to_preview(client):
    r = client.post("/api/v1/entitlements/audio/unlock?qid=Q9", headers=PREVIEW)
    assert r.status_code == 200
    assert "Q9" in r.json()["free_audio_qids"]


# ---- 对照组:已放出馆的藏品级端点对普通调用者必须照常开放 --------------------
# 没有这组,一个"qid 一律不可见"的过严实现能让上面全部用例照绿(破坏验证实测)。


def test_published_content_open_to_normal(client, monkeypatch):
    _spy(monkeypatch, "app.services.enrichment.lazy.maybe_trigger")
    r = client.get(
        "/api/v1/museums/orsay/objects/Q1/content?language=zh", headers=NORMAL
    )
    assert r.status_code == 200


@pytest.mark.parametrize("suffix", ["audio", "audio/stream"])
def test_published_audio_open_to_normal(client, audio_spies, suffix):
    r = client.get(f"/api/v1/museums/orsay/objects/Q1/{suffix}", headers=NORMAL)
    assert r.status_code == 200


def test_unlock_published_qid_spends_quota(client, db):
    r = client.post("/api/v1/entitlements/audio/unlock?qid=Q1", headers=NORMAL)
    assert r.status_code == 200
    assert (
        db.query(UserBenefits).filter_by(user_id="u-normal").one().recognition_quota
        == 4
    )


def test_confirm_on_published_qid_reaches_billing(client, monkeypatch):
    calls = _spy(
        monkeypatch, "app.services.recognition.events.confirm_event", ret=False
    )
    client.post(
        "/api/v1/recognize/confirm", json={"phash": "p", "qid": "Q1"}, headers=NORMAL
    )
    assert len(calls) == 1
