"""通票按馆求值(spec 2026-09-28-multi-city-expansion §2.2/§3.1-3.4/§3.7,D7/D8)。

这里的每一格都是钱:
- 持巴黎票在荷兰的馆**不能**听、不能不限次识别、激活不能烧掉巴黎那张;
- 反过来巴黎票在巴黎**必须**照常放行 —— 只测"拦得住"的那一半,一个把所有人都拦下的
  实现也会全绿(test-across-config-dimension)。
- 涉及扣额度的格子断言额度数字与解锁清单本身,不只断言状态码。
"""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app.main import app
from app.models.app_event import AppEvent
from app.models.artist import Artist
from app.models.museum import Museum
from app.models.museum_object import MuseumObject, ObjectImage
from app.models.purchase import Entitlement
from app.models.recognition_demand import RecognitionDemand
from app.models.recognition_event import RecognitionEvent
from app.models.user_benefits import UserBenefits
from app.services import entitlement_service as es
from app.services.object_importer import upsert_museum, upsert_object

PARIS = SimpleNamespace(city_en="Paris", country="FR")
AMSTERDAM = SimpleNamespace(city_en="Amsterdam", country="NL")
DEN_HAAG = SimpleNamespace(city_en="The Hague", country="NL")
MADRID = SimpleNamespace(city_en="Madrid", country="ES")


# ---- 范围语法 -------------------------------------------------------------

MATRIX = [
    # scope,          巴黎,  阿姆斯特丹, 海牙,  马德里
    ("city:paris", True, False, False, False),
    ("paris", True, False, False, False),  # 旧写法 = city:paris(存量行不迁移)
    ("country:NL", False, True, True, False),  # 国家票覆盖荷兰所有城市
    ("*", True, True, True, True),
    ("", False, False, False, False),  # 未知商品 → 空范围,不再默认巴黎
]


@pytest.mark.parametrize("scope,paris,ams,hague,madrid", MATRIX)
def test_scope_matrix(scope, paris, ams, hague, madrid):
    got = [es.covers_museum(scope, m) for m in (PARIS, AMSTERDAM, DEN_HAAG, MADRID)]
    assert got == [paris, ams, hague, madrid]


def test_unknown_product_covers_nothing():
    """此前 pass_scope 对未知商品默认 "paris":新国家漏配商品会静默变成巴黎票。"""
    assert es.pass_scope("typo_pass_7d") == ""
    assert not es.covers_museum(es.pass_scope("typo_pass_7d"), PARIS)


def test_pass_for_museum_respects_on_sale(monkeypatch):
    assert es.pass_for_museum(PARIS) == "paris_pass_7d"
    monkeypatch.setitem(es.PASSES["nl_pass_7d"], "on_sale", False)
    assert es.pass_for_museum(AMSTERDAM) is None, "不在售的票不能下发"
    monkeypatch.setitem(es.PASSES["nl_pass_7d"], "on_sale", True)
    assert es.pass_for_museum(AMSTERDAM) == "nl_pass_7d"
    assert es.pass_for_museum(DEN_HAAG) == "nl_pass_7d"
    assert es.pass_for_museum(MADRID) is None


def test_pass_labels_cover_all_ten_languages():
    langs = {"zh", "zh-hant", "en", "fr", "de", "es", "it", "ja", "ko", "pl"}
    for pid, p in es.PASSES.items():
        assert set(p["label"]) == langs, pid


# ---- 库级:resolve / activate / audio ---------------------------------------


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
            Artist.__table__,
            Entitlement.__table__,
            UserBenefits.__table__,
            RecognitionEvent.__table__,
            RecognitionDemand.__table__,
            AppEvent.__table__,
        ],
    )
    s = sessionmaker(bind=engine)()
    for slug, city, country, qid in (
        ("orsay", "Paris", "FR", "Q1"),
        ("rijks", "Amsterdam", "NL", "Q9"),
    ):
        m = upsert_museum(
            s, {"slug": slug, "name_en": slug, "city_en": city, "country": country}
        )
        m.published_at = datetime(2026, 1, 1)
        upsert_object(s, m.id, {"qid": qid, "title_en": qid, "attributes": {}})
    s.commit()
    return s


def _m(db, slug):
    return db.query(Museum).filter_by(slug=slug).one()


def _ticket(db, uid, pid, *, active=True, scope=None):
    db.add(
        Entitlement(
            user_id=uid,
            entitlement_type=pid,
            scope=scope if scope is not None else es.pass_scope(pid),
            status=es.ACTIVE if active else es.PURCHASED_NOT_ACTIVATED,
            activated_at=datetime.now(timezone.utc) if active else None,
            expires_at=(
                datetime.now(timezone.utc) + timedelta(days=3) if active else None
            ),
        )
    )
    db.commit()


def _ben(db, uid, quota=5):
    b = UserBenefits(user_id=uid, recognition_quota=quota, free_audio_qids={})
    db.add(b)
    db.commit()
    return b


def test_paris_pass_opens_paris_but_not_amsterdam(db):
    _ticket(db, "u", "paris_pass_7d")
    assert es.resolve_state(db, "u", _m(db, "orsay"))[0] == es.ACTIVE
    assert es.resolve_state(db, "u", _m(db, "rijks"))[0] == es.NOT_PURCHASED
    assert es.audio_access(db, "u", "Q1", museum=_m(db, "orsay")) == "allowed"
    assert es.audio_access(db, "u", "Q9", museum=_m(db, "rijks")) == "denied"
    # 不给馆 = 任意一张票(设置页/识别前置闸)
    assert es.resolve_state(db, "u")[0] == es.ACTIVE


def test_legacy_scope_row_still_opens_paris(db):
    """DB 里已发出的旧行 scope="paris"/NULL 不迁移,必须照旧生效。"""
    _ticket(db, "a", "paris_pass_7d", scope="paris")
    _ticket(db, "b", "paris_pass_7d", scope="")
    for uid in ("a", "b"):
        assert es.resolve_state(db, uid, _m(db, "orsay"))[0] == es.ACTIVE
        assert es.resolve_state(db, uid, _m(db, "rijks"))[0] == es.NOT_PURCHASED


def test_activate_in_amsterdam_never_burns_the_paris_ticket(db):
    _ticket(db, "u", "paris_pass_7d", active=False)
    _ticket(db, "u", "nl_pass_7d", active=False)
    state, ent = es.activate(db, "u", _m(db, "rijks"))
    assert state == es.ACTIVE and ent.entitlement_type == "nl_pass_7d"
    paris = db.query(Entitlement).filter_by(entitlement_type="paris_pass_7d").one()
    assert paris.activated_at is None and paris.status == es.PURCHASED_NOT_ACTIVATED


def test_activate_with_no_covering_ticket_touches_nothing(db):
    _ticket(db, "u", "paris_pass_7d", active=False)
    state, _ = es.activate(db, "u", _m(db, "rijks"))
    assert state == es.NOT_PURCHASED
    assert db.query(Entitlement).one().activated_at is None


def test_summary_is_per_museum_and_lists_every_ticket(db):
    _ticket(db, "u", "paris_pass_7d")
    _ticket(db, "u", "nl_pass_7d", active=False)
    at_rijks = es.summary(db, "u", museum=_m(db, "rijks"), language="zh")
    assert at_rijks["state"] == es.PURCHASED_NOT_ACTIVATED
    assert at_rijks["can"]["audio_any"] is False, "巴黎票不能在荷兰显示为可播"
    at_orsay = es.summary(db, "u", museum=_m(db, "orsay"))
    assert at_orsay["can"]["audio_any"] is True
    passes = {p["product_id"]: p for p in at_rijks["passes"]}
    assert passes["paris_pass_7d"]["label"] == "巴黎"
    assert passes["paris_pass_7d"]["state"] == es.ACTIVE
    assert passes["nl_pass_7d"]["label"] == "荷兰"
    assert passes["nl_pass_7d"]["activate_by"] is not None


def test_pass_offer_lists_only_published_covered_museums(db, monkeypatch):
    monkeypatch.setitem(es.PASSES["nl_pass_7d"], "on_sale", True)
    hidden = upsert_museum(
        db, {"slug": "mauritshuis", "name_en": "Mauritshuis", "city_en": "The Hague"}
    )
    hidden.country = "NL"
    db.commit()
    offer = es.pass_offer(db, _m(db, "rijks"), "en")
    assert offer["product_id"] == "nl_pass_7d" and offer["days"] == 7
    assert offer["label"] == "Netherlands"
    assert offer["covers"] == ["rijks"], "隐身馆不能从卖点文案里泄漏"
    assert es.pass_offer(db, _m(db, "rijks"), "en", preview=True)["covers"] == [
        "Mauritshuis",
        "rijks",
    ]
    assert "rijks" not in es.pass_offer(db, _m(db, "orsay"), "en")["covers"]


def test_pass_offer_is_none_when_nothing_on_sale(db, monkeypatch):
    monkeypatch.setitem(es.PASSES["nl_pass_7d"], "on_sale", False)
    assert es.pass_offer(db, _m(db, "rijks"), "zh") is None, "绝不回落到巴黎票"


# ---- D8:免费解锁 7 天 ------------------------------------------------------


def test_free_unlock_expires_after_seven_days(db, monkeypatch):
    b = _ben(db, "u")
    es.unlock_free_audio(db, "u", ["Q1"])
    assert es.audio_access(db, "u", "Q1") == "allowed"
    t0 = datetime.now(timezone.utc)
    monkeypatch.setattr(es, "_now", lambda: t0 + timedelta(days=6, hours=23))
    assert es.audio_access(db, "u", "Q1") == "allowed"
    monkeypatch.setattr(es, "_now", lambda: t0 + timedelta(days=7, minutes=1))
    assert es.audio_access(db, "u", "Q1") == "denied"
    db.refresh(b)
    assert es.summary(db, "u", b)["free_audio_qids"] == []
    # 过期后再次(扣费)识别 → 重新计 7 天
    assert es.unlock_free_audio(db, "u", ["Q1"]) == ["Q1"]
    assert es.audio_access(db, "u", "Q1") == "allowed"


def test_legacy_list_shape_is_treated_as_expired(db):
    """迁移 e6b7 会把旧列表转成带时刻的形状;万一漏网,宁可锁住不可永久白送。"""
    b = UserBenefits(user_id="u", recognition_quota=5, free_audio_qids=["Q1"])
    db.add(b)
    db.commit()
    assert es.free_audio_qids(b) == []


def test_summary_reports_expiry_per_unlock(db):
    b = _ben(db, "u")
    es.unlock_free_audio(db, "u", ["Q1"])
    db.refresh(b)
    until = es.summary(db, "u", b)["free_audio_until"]
    assert set(until) == {"Q1"}
    left = datetime.fromisoformat(until["Q1"]) - datetime.now(timezone.utc)
    assert timedelta(days=6, hours=23) < left <= timedelta(days=7)


# ---- D7:识别按命中的馆判票 --------------------------------------------------


class _Redis:
    def get(self, k):
        return None

    def setex(self, *a):
        pass


def _recognize(db, hit_qid, uid="u"):
    from app.services.recognition.service import recognize_billed

    return recognize_billed(
        db,
        None,  # 全局识别:前置闸时还不知道是哪家馆
        _jpeg(),
        user_id=uid,
        device_id=None,
        redis=_Redis(),
        embed_fn=lambda b: "V",
        vector_query_fn=lambda db, v, mid: [(hit_qid, 0.95)],
    )


def _jpeg():
    import io

    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (64, 64), (10, 20, 30)).save(buf, format="JPEG")
    return buf.getvalue()


def _quota(db, uid="u"):
    db.expire_all()
    return db.query(UserBenefits).filter_by(user_id=uid).one().recognition_quota


def _unlocked(db, uid="u"):
    db.expire_all()
    return es.free_audio_qids(db.query(UserBenefits).filter_by(user_id=uid).one())


def test_pass_covering_the_hit_is_unlimited_and_writes_no_free_unlock(db):
    _ben(db, "u", quota=5)
    _ticket(db, "u", "paris_pass_7d")
    assert _recognize(db, "Q1")["outcome"] == "match"
    assert _quota(db) == 5, "票覆盖命中的馆:不动免费额度"
    assert _unlocked(db) == [], "D8:持票识别不写免费解锁(票过期后自然锁)"


def test_pass_elsewhere_is_charged_like_a_free_user(db):
    _ben(db, "u", quota=5)
    _ticket(db, "u", "paris_pass_7d")
    assert _recognize(db, "Q9")["outcome"] == "match"
    assert _quota(db) == 4, "巴黎票在荷兰命中:与免费用户同价"
    assert _unlocked(db) == ["Q9"]


def test_pass_elsewhere_with_no_quota_is_402_for_that_museum(db):
    from app.services.recognition.service import QuotaExceededError

    _ben(db, "u", quota=0)
    _ticket(db, "u", "paris_pass_7d")
    with pytest.raises(QuotaExceededError) as e:
        _recognize(db, "Q9")
    assert e.value.museum.slug == "rijks", "402 要卖荷兰的票,不是巴黎的"
    assert _unlocked(db) == [], "402 之前绝不能先解锁"


def test_reshooting_an_unlocked_artwork_is_free(db):
    _ben(db, "u", quota=5)
    _recognize(db, "Q9")
    _recognize(db, "Q9")
    assert _quota(db) == 4


# ---- 接口层:402 下发该馆的票 / 按馆的权益 / 解锁不卡死 ---------------------

AUTH = {"Authorization": "Bearer t"}


@pytest.fixture()
def client(db, monkeypatch):
    from app.services.auth_service import AuthService

    user = SimpleNamespace(id="u", is_guest=False, can_preview=False)
    monkeypatch.setattr(
        AuthService, "get_current_user", staticmethod(lambda d, t: user)
    )
    monkeypatch.setitem(es.PASSES["nl_pass_7d"], "on_sale", True)
    app.dependency_overrides[get_db] = lambda: (yield db)
    yield TestClient(app)
    app.dependency_overrides.pop(get_db, None)


def test_audio_402_sells_the_ticket_of_the_artworks_museum(client, db):
    _ben(db, "u", quota=5)
    _ticket(db, "u", "paris_pass_7d")
    # URL 里写 orsay 也没用:按 qid 反查作品所在的馆
    r = client.get("/api/v1/museums/orsay/objects/Q9/audio", headers=AUTH)
    assert r.status_code == 402
    assert r.json()["detail"]["pass"]["product_id"] == "nl_pass_7d"


def test_unlock_with_a_paris_pass_in_amsterdam_is_not_stuck(client, db):
    """此前 `resolve_state==ACTIVE`(任意票)就幂等返回:什么都没解锁,用户卡死。"""
    _ben(db, "u", quota=5)
    _ticket(db, "u", "paris_pass_7d")
    r = client.post("/api/v1/entitlements/audio/unlock?qid=Q9", headers=AUTH)
    assert r.status_code == 200
    assert "Q9" in r.json()["free_audio_qids"]
    assert _quota(db) == 4


def test_unlock_under_a_covering_pass_charges_nothing(client, db):
    _ben(db, "u", quota=5)
    _ticket(db, "u", "paris_pass_7d")
    r = client.post("/api/v1/entitlements/audio/unlock?qid=Q1", headers=AUTH)
    assert r.status_code == 200 and _quota(db) == 5


def test_me_and_activate_take_a_museum(client, db):
    _ticket(db, "u", "paris_pass_7d", active=False)
    _ticket(db, "u", "nl_pass_7d", active=False)
    r = client.post("/api/v1/entitlements/activate?museum=rijks", headers=AUTH)
    assert r.json()["state"] == es.ACTIVE
    me = client.get("/api/v1/entitlements/me?museum=orsay", headers=AUTH).json()
    assert me["state"] == es.PURCHASED_NOT_ACTIVATED, "巴黎那张不能被荷兰的激活烧掉"
    assert (
        client.get("/api/v1/entitlements/me?museum=nope", headers=AUTH).status_code
        == 404
    )


def test_museum_pack_carries_its_ticket(client):
    pack = client.get("/api/v1/museums/rijks?artworks=false&language=en").json()
    assert pack["pass"]["product_id"] == "nl_pass_7d"
    assert pack["pass"]["label"] == "Netherlands"
    assert (
        client.get("/api/v1/museums/orsay?artworks=false").json()["pass"]["product_id"]
        == "paris_pass_7d"
    )


@pytest.mark.parametrize("qid,charged", [("Q1", False), ("Q9", True)])
def test_confirm_charges_by_the_confirmed_artworks_museum(
    client, db, monkeypatch, qid, charged
):
    """候选确认同 D7:巴黎票确认巴黎的件不扣不解锁;确认荷兰的件 = 免费用户同价。"""
    monkeypatch.setattr(
        "app.services.recognition.events.confirm_event", lambda *a: True
    )
    _ben(db, "u", quota=5)
    _ticket(db, "u", "paris_pass_7d")
    r = client.post(
        "/api/v1/recognize/confirm", json={"phash": "p", "qid": qid}, headers=AUTH
    )
    assert r.status_code == 204
    assert _quota(db) == (4 if charged else 5)
    assert _unlocked(db) == ([qid] if charged else [])


# ---- /me.offers:不知道在哪家馆的购买入口 ---------------------------------


def test_offers_list_every_sellable_ticket_but_never_a_hidden_one(db, monkeypatch):
    monkeypatch.setitem(es.PASSES["nl_pass_7d"], "on_sale", False)
    assert [o["product_id"] for o in es.pass_offers(db, "zh")] == ["paris_pass_7d"]
    monkeypatch.setitem(es.PASSES["nl_pass_7d"], "on_sale", True)
    # rijks 已放出 → 荷兰票可买
    assert {o["product_id"] for o in es.pass_offers(db, "zh")} == {
        "paris_pass_7d",
        "nl_pass_7d",
    }
    # rijks 改回隐身:荷兰票对公众消失(演练期的票不能从这里漏出去),预览者仍看得到
    _m(db, "rijks").published_at = None
    db.commit()
    assert [o["product_id"] for o in es.pass_offers(db, "zh")] == ["paris_pass_7d"]
    assert "nl_pass_7d" in {
        o["product_id"] for o in es.pass_offers(db, "zh", preview=True)
    }


def test_me_carries_offers(client, db):
    me = client.get("/api/v1/entitlements/me?language=en", headers=AUTH).json()
    by_id = {o["product_id"]: o for o in me["offers"]}
    assert by_id["paris_pass_7d"]["label"] == "Paris"
    assert by_id["nl_pass_7d"]["covers"] == ["rijks"]  # client fixture 把 nl 置为在售


def test_summary_reports_expired_unlocks_and_window(db, monkeypatch):
    """D8 界面:前端要能分清「从没解锁」与「解锁过但过期了」,才能写明原因。"""
    b = _ben(db, "u")
    es.unlock_free_audio(db, "u", ["Q1"])
    db.refresh(b)
    out = es.summary(db, "u", b)
    assert out["free_audio_expired"] == [] and out["free_audio_days"] == 7
    t0 = datetime.now(timezone.utc)
    monkeypatch.setattr(es, "_now", lambda: t0 + timedelta(days=8))
    out = es.summary(db, "u", b)
    assert out["free_audio_expired"] == ["Q1"]
    assert out["free_audio_qids"] == []
