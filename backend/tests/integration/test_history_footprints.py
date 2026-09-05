"""足迹端点(/api/v1/history/*)。

重写前这套端点读的是一张 prod 上 **0 行**、且没有任何写入方的表,同时**零鉴权**
(匿名可读可删)。这些用例钉住重写后的四条:认人、只给自己的、四个字符串字段
永不为 null、删是断链不是删行。
"""

import uuid
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app.main import app
from app.models.artist import Artist
from app.models.museum import Museum
from app.models.museum_object import MuseumObject, ObjectImage
from app.models.recognition_event import RecognitionEvent
from app.models.user import User
from app.models.user_benefits import UserBenefits

LOUVRE = uuid.uuid4()


@pytest.fixture()
def session_factory():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(
        bind=engine,
        tables=[
            User.__table__,
            UserBenefits.__table__,
            RecognitionEvent.__table__,
            Museum.__table__,
            MuseumObject.__table__,
            ObjectImage.__table__,
            Artist.__table__,
        ],
    )
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)


@pytest.fixture()
def db(session_factory):
    s = session_factory()
    s.add(Museum(id=LOUVRE, slug="louvre", name_zh="卢浮宫", name_en="Louvre"))
    s.commit()
    yield s
    s.close()


@pytest.fixture()
def client(session_factory, db):
    def override_get_db():
        s = session_factory()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.pop(get_db, None)


def _register(client, email):
    r = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "Test1234!", "username": "足迹用户"},
    )
    assert r.status_code == 201, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _uid(db, email):
    return str(db.query(User).filter_by(email=email).one().id)


def _obj(db, qid, **kw):
    o = MuseumObject(qid=qid, museum_id=LOUVRE, **kw)
    db.add(o)
    db.commit()
    return o


def _event(db, user_id, qid=None, *, outcome="match", confirmed=None, minutes=0, **kw):
    ev = RecognitionEvent(
        museum_slug="louvre",
        phash="p" * 16,
        outcome=outcome,
        top_qid=qid,
        top_score=kw.pop("score", 0.91),
        confirmed_qid=confirmed,
        language=kw.pop("language", "zh"),
        engine="vector",
        user_id=user_id,
        created_at=datetime.utcnow() - timedelta(minutes=minutes),
    )
    db.add(ev)
    db.commit()
    return ev


# ---------------------------------------------------------------- 鉴权


@pytest.mark.parametrize(
    "method,path",
    [
        ("get", "/api/v1/history/recent"),
        ("get", "/api/v1/history/search?query=蒙娜"),
        ("get", "/api/v1/history/stats"),
        ("delete", f"/api/v1/history/{uuid.uuid4()}"),
    ],
)
def test_requires_auth(client, method, path):
    """重写前这四个在 prod 上匿名就能调(GET 返 200、DELETE 查得到就删)。"""
    assert getattr(client, method)(path).status_code in (401, 403)


def test_only_my_footprints(client, db):
    """A 的足迹里不能出现 B 的记录 —— 这是个人数据。"""
    _obj(db, "Q12418", title_zh="蒙娜丽莎", artist_zh="达芬奇")
    _obj(db, "Q45585", title_zh="自由引导人民", artist_zh="德拉克罗瓦")
    a = _register(client, "a@test.com")
    _register(client, "b@test.com")
    _event(db, _uid(db, "a@test.com"), "Q12418")
    _event(db, _uid(db, "b@test.com"), "Q45585")

    names = [
        i["artwork_name"]
        for i in client.get("/api/v1/history/recent", headers=a).json()
    ]
    assert names == ["蒙娜丽莎"]


def test_anonymous_events_belong_to_nobody(client, db):
    """x1u0 之前的老事件 user_id 为 NULL,不能漏给任何人。"""
    _obj(db, "Q12418", title_zh="蒙娜丽莎")
    a = _register(client, "a@test.com")
    _event(db, None, "Q12418")
    assert client.get("/api/v1/history/recent", headers=a).json() == []


# ---------------------------------------------------------------- 契约容错


def test_never_null_strings(client, db):
    """`artwork_name`/`artist`/`period`/`description` 恒为字符串。

    已发布的 App 里是裸 `as String` 强转,给 null 会让足迹页整页崩
    (同 2026-06-16 `title_zh` 变 null 那次事故)。这里刻意造一件
    **什么名字都没有**的藏品 —— 富化数据天然缺字段,这不是假想输入。
    """
    _obj(db, "Q999999")  # title_zh/title_en/artist_*/period_* 全 None
    a = _register(client, "a@test.com")
    _event(db, _uid(db, "a@test.com"), "Q999999", score=None)

    item = client.get("/api/v1/history/recent", headers=a).json()[0]
    for field in ("artwork_name", "artist", "period", "description"):
        assert isinstance(item[field], str), f"{field} 不是字符串:{item[field]!r}"
    assert item["artwork_name"] == "Q999999"  # 名字全缺 → 回退到 qid,不给空
    assert item["confidence"] == 0.0  # top_score 为 None 也不能崩 schema


def test_additive_fields_for_new_app(client, db):
    """新加的 museum_slug/qid 是「点进去能看真讲解」那条路的入参。"""
    _obj(db, "Q12418", title_zh="蒙娜丽莎")
    a = _register(client, "a@test.com")
    _event(db, _uid(db, "a@test.com"), "Q12418")

    item = client.get("/api/v1/history/recent", headers=a).json()[0]
    assert item["museum_slug"] == "louvre"
    assert item["qid"] == "Q12418"


def test_language_follows_the_event(client, db):
    """用哪种语言拍的,足迹就用哪种语言显示。"""
    _obj(db, "Q12418", title_zh="蒙娜丽莎", title_en="Mona Lisa")
    a = _register(client, "a@test.com")
    _event(db, _uid(db, "a@test.com"), "Q12418", language="en")

    assert (
        client.get("/api/v1/history/recent", headers=a).json()[0]["artwork_name"]
        == "Mona Lisa"
    )


# ---------------------------------------------------------------- 什么算足迹


def test_unconfirmed_candidates_are_not_footprints(client, db):
    """`candidates` 的 top_qid 只是「还没定的几个猜测里分最高的」。

    把它当成「你看过这件」是替用户编经历。判据与 coverage/display_state.py
    的展陈证据一致:确认过的、或 outcome=match 的才算。
    """
    _obj(db, "Q12418", title_zh="蒙娜丽莎")
    _obj(db, "Q45585", title_zh="自由引导人民")
    a = _register(client, "a@test.com")
    me = _uid(db, "a@test.com")
    _event(db, me, "Q12418", outcome="candidates", minutes=2)  # 没确认 → 不算
    _event(db, me, "Q45585", outcome="candidates", confirmed="Q45585", minutes=1)
    _event(db, me, None, outcome="unrecognized", minutes=0)  # 没认出来 → 不算

    names = [
        i["artwork_name"]
        for i in client.get("/api/v1/history/recent", headers=a).json()
    ]
    assert names == ["自由引导人民"]


def test_missing_object_is_skipped(client, db):
    """目录里查无此 qid(下架/改馆)时跳过,不能 500,也不能给个空壳条目。"""
    a = _register(client, "a@test.com")
    _event(db, _uid(db, "a@test.com"), "Q_NOT_IN_CATALOG")
    r = client.get("/api/v1/history/recent", headers=a)
    assert r.status_code == 200 and r.json() == []


def test_recent_is_newest_first(client, db):
    _obj(db, "Q1", title_zh="早")
    _obj(db, "Q2", title_zh="晚")
    a = _register(client, "a@test.com")
    me = _uid(db, "a@test.com")
    _event(db, me, "Q1", minutes=60)
    _event(db, me, "Q2", minutes=1)
    names = [
        i["artwork_name"]
        for i in client.get("/api/v1/history/recent", headers=a).json()
    ]
    assert names == ["晚", "早"]


# ---------------------------------------------------------------- 搜索 / 统计


def test_search_matches_displayed_name(client, db):
    """搜的是用户屏幕上看到的那个名字(多语言回退后的),不是某一列。"""
    _obj(db, "Q12418", title_zh="蒙娜丽莎", artist_zh="达芬奇")
    _obj(db, "Q45585", title_zh="自由引导人民", artist_zh="德拉克罗瓦")
    a = _register(client, "a@test.com")
    me = _uid(db, "a@test.com")
    _event(db, me, "Q12418")
    _event(db, me, "Q45585")

    hits = client.get("/api/v1/history/search?query=达芬奇", headers=a).json()
    assert [h["artwork_name"] for h in hits] == ["蒙娜丽莎"]


def test_stats_are_mine_only(client, db):
    _obj(db, "Q12418", title_zh="蒙娜丽莎")
    _obj(db, "Q45585", title_zh="自由引导人民")
    a = _register(client, "a@test.com")
    _register(client, "b@test.com")
    me = _uid(db, "a@test.com")
    _event(db, me, "Q12418")
    _event(db, me, "Q12418")  # 同一件拍两次
    _event(db, _uid(db, "b@test.com"), "Q45585")

    s = client.get("/api/v1/history/stats", headers=a).json()
    assert s["total_recognitions"] == 2
    assert s["unique_artworks"] == 1
    assert s["museums_visited"] == 1


# ---------------------------------------------------------------- 删除


def test_delete_unlinks_but_keeps_the_row(client, db):
    """删足迹 = 断链。行留下 —— 它同时是识别率 KPI 与展陈证据。"""
    _obj(db, "Q12418", title_zh="蒙娜丽莎")
    a = _register(client, "a@test.com")
    ev = _event(db, _uid(db, "a@test.com"), "Q12418")
    eid = str(ev.id)

    assert client.delete(f"/api/v1/history/{eid}", headers=a).status_code == 200
    assert client.get("/api/v1/history/recent", headers=a).json() == []

    db.expire_all()
    row = db.query(RecognitionEvent).filter_by(id=ev.id).one()
    assert row.user_id is None  # 断链
    assert row.top_qid == "Q12418" and row.outcome == "match"  # 证据还在


def test_cannot_delete_someone_elses(client, db):
    _obj(db, "Q12418", title_zh="蒙娜丽莎")
    _register(client, "a@test.com")
    b = _register(client, "b@test.com")
    ev = _event(db, _uid(db, "a@test.com"), "Q12418")

    assert client.delete(f"/api/v1/history/{ev.id}", headers=b).status_code == 404
    db.expire_all()
    assert db.query(RecognitionEvent).filter_by(id=ev.id).one().user_id is not None


def test_delete_garbage_id_is_404_not_500(client, db):
    a = _register(client, "a@test.com")
    assert client.delete("/api/v1/history/not-a-uuid", headers=a).status_code == 404
