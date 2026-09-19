"""反馈端点。正负成对 —— 只测"能收下"的话,一个无条件 INSERT 的实现也全绿。

最要紧的一组是**坐标必填**:一条不知道指向哪件藏品、哪个语种的"内容反馈"
是垃圾数据。而 `scope=app` 必须不受这条约束,否则就是一刀切 —— 两侧都要测,
否则"判对了"和"收太松/收太紧"分不开。
"""

import pytest
from fastapi.testclient import TestClient

from app.core.database import Base, get_db
from app.main import app
from app.models.feedback import Feedback

OBJECT_OK = {
    "scope": "object",
    "kind": "content_wrong",
    "museum_slug": "petit-palais",
    "qid": "Q3937645",
    "language": "zh-hant",
    "text": "年代写错了",
    "device_id": "dev-1",
    "app_version": "GoMuseum 1.0.0 (31)",
    "platform": "android",
}
APP_OK = {
    "scope": "app",
    "kind": "feature_request",
    "text": "希望能离线听",
    "device_id": "dev-2",
    "app_version": "GoMuseum 1.0.0 (31)",
    "platform": "ios",
}


@pytest.fixture
def db_session():
    """只建 feedbacks 一张表。

    不用 `Base.metadata.create_all`：别的表里有 Postgres 专用的 CHECK（`NOW()`），
    在 SQLite 上建不起来 —— 而这组测试只关心反馈这一张。
    """
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Feedback.__table__.create(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


@pytest.fixture
def client(db_session):
    app.dependency_overrides[get_db] = lambda: db_session
    yield TestClient(app)
    app.dependency_overrides.clear()


def post(client, payload):
    return client.post("/api/v1/feedback", json=payload)


# ── 正样本 ──────────────────────────────────────────────────────────


def test_匿名可提交藏品反馈并落库(client, db_session):
    assert post(client, OBJECT_OK).status_code == 204

    row = db_session.query(Feedback).one()
    assert row.scope == "object"
    assert row.qid == "Q3937645"
    assert row.language == "zh-hant"  # 繁体不能被降级成 zh
    assert row.kind == "content_wrong"
    assert row.device_id == "dev-1"
    assert row.status == "new"
    assert row.user_id is None  # 匿名


def test_app级反馈不带坐标也收(client, db_session):
    """负样本的对照组:证明坐标必填不是一刀切。

    少了这条,把校验写成"所有反馈都要 qid"同样全绿。
    """
    assert post(client, APP_OK).status_code == 204
    assert db_session.query(Feedback).one().qid is None


def test_文本可以为空(client):
    payload = {**OBJECT_OK}
    payload.pop("text")
    assert post(client, payload).status_code == 204


# ── 负样本 ──────────────────────────────────────────────────────────


@pytest.mark.parametrize("missing", ["museum_slug", "qid", "language"])
def test_藏品反馈缺坐标一律拒收(client, db_session, missing):
    payload = {**OBJECT_OK}
    payload.pop(missing)
    assert post(client, payload).status_code == 422
    assert db_session.query(Feedback).count() == 0


def test_未知kind拒收(client, db_session):
    assert post(client, {**OBJECT_OK, "kind": "bogus"}).status_code == 422
    assert db_session.query(Feedback).count() == 0


def test_未知scope拒收(client, db_session):
    assert post(client, {**OBJECT_OK, "scope": "universe"}).status_code == 422
    assert db_session.query(Feedback).count() == 0


def test_超长文本拒收(client, db_session):
    assert post(client, {**OBJECT_OK, "text": "啊" * 1001}).status_code == 422
    assert db_session.query(Feedback).count() == 0


def test_刚好1000字收下(client):
    """边界的另一侧 —— 只测"超了拒收"的话,把上限写成 1 也全绿。"""
    assert post(client, {**OBJECT_OK, "text": "啊" * 1000}).status_code == 204


def test_无效令牌不丢反馈只是记成匿名(client, db_session):
    """令牌过期不该让用户白填一遍。"""
    r = client.post(
        "/api/v1/feedback", json=OBJECT_OK, headers={"Authorization": "Bearer garbage"}
    )
    assert r.status_code == 204
    assert db_session.query(Feedback).one().user_id is None
