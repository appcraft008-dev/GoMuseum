"""讲解页打开埋点(P3-14②):App 进讲解页时报一次 content_viewed + 入口。

不挂在 /content 上:生成中那个接口每 4s 轮询一次,会重复计数。"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app.main import app
from app.models.app_event import AppEvent


@pytest.fixture()
def client():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(bind=engine, tables=[AppEvent.__table__])
    s = sessionmaker(bind=engine)()

    def _override():
        yield s

    app.dependency_overrides[get_db] = _override
    yield TestClient(app), s
    app.dependency_overrides.pop(get_db, None)


def test_viewed_logs_entry(client):
    c, s = client
    r = c.post("/api/v1/museums/orsay/objects/Q1/viewed", json={"from": "search"})
    assert r.status_code == 204
    e = s.query(AppEvent).one()
    assert (e.name, e.museum_slug, e.props) == (
        "content_viewed",
        "orsay",
        {"qid": "Q1", "from": "search"},
    )


def test_unknown_entry_rejected(client):
    c, s = client
    r = c.post("/api/v1/museums/orsay/objects/Q1/viewed", json={"from": "evil"})
    assert r.status_code == 422
    assert s.query(AppEvent).count() == 0
