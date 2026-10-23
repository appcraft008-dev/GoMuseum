"""游客登录限速(spec §4.2):原来每进程 5 次/时,共用 WiFi 的团体一来就不够用。"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app.core.rate_limit import limiter
from app.main import app
from app.models.app_event import AppEvent
from app.models.user import User
from app.models.user_benefits import UserBenefits


@pytest.fixture()
def client(monkeypatch):
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(
        bind=engine,
        tables=[User.__table__, UserBenefits.__table__, AppEvent.__table__],
    )
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    def override():
        db = Session()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override
    monkeypatch.setattr(limiter, "enabled", True)  # conftest 默认关了限流
    limiter.reset()
    yield TestClient(app)
    limiter.reset()
    app.dependency_overrides.pop(get_db, None)


def test_guest_login_allows_30_per_hour_from_one_ip(client):
    for i in range(30):
        r = client.post("/api/v1/auth/guest", json={"device_id": f"dev-{i}"})
        assert r.status_code == 200, (i, r.text)
    assert (
        client.post("/api/v1/auth/guest", json={"device_id": "dev-30"}).status_code
        == 429
    )
