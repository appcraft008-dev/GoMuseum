# tests/integration/test_object_content_endpoint.py
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app.main import app
from app.models.content import (
    CategorySection,
    ObjectContentSection,
    ObjectSuggestedQuestion,
    SectionType,
)
from app.models.museum import Museum
from app.models.museum_object import MuseumObject, ObjectImage
from app.services.object_importer import upsert_museum, upsert_object


@pytest.fixture()
def client():
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
        ],
    )
    s = sessionmaker(bind=engine)()
    m = upsert_museum(s, {"slug": "orsay", "name_en": "Orsay"})
    obj = upsert_object(
        s,
        m.id,
        {
            "qid": "Q1",
            "title_en": "A",
            "category": "painting",
            "image": "http://x/a.jpg",
            "attributes": {},
        },
    )
    # A second museum for slug-mismatch test
    m2 = upsert_museum(s, {"slug": "louvre", "name_en": "Louvre"})
    s.add(
        SectionType(
            code="overview", label_zh="通用描述", label_en="Overview", default_sort=10
        )
    )
    s.add(CategorySection(category="painting", section_code="overview", sort_order=10))
    s.add(
        ObjectContentSection(
            object_id=obj.id, language="zh", section_code="overview", body="讲解正文"
        )
    )
    # fr 也给已发布正文,否则无正文的 tab 现在会被动态隐藏(空 tab 不返)
    s.add(
        ObjectContentSection(
            object_id=obj.id, language="fr", section_code="overview", body="texte fr"
        )
    )
    s.commit()
    app.dependency_overrides[get_db] = lambda: (yield s)
    yield TestClient(app)
    app.dependency_overrides.pop(get_db, None)
    s.close()


def test_object_content_tabs(client):
    r = client.get("/api/v1/museums/orsay/objects/Q1/content?language=zh")
    assert r.status_code == 200
    tabs = r.json()["tabs"]
    assert tabs[0]["section_code"] == "overview"
    assert tabs[0]["label"] == "通用描述"
    assert tabs[0]["body"] == "讲解正文"


def test_object_content_not_found(client):
    """Non-existent qid returns 404."""
    r = client.get("/api/v1/museums/orsay/objects/QNOPE/content")
    assert r.status_code == 404


def test_object_content_slug_mismatch(client):
    """Object exists but under a different museum slug → 404."""
    r = client.get("/api/v1/museums/louvre/objects/Q1/content?language=zh")
    assert r.status_code == 404


def test_object_content_labels_localized_fr(client):
    r = client.get("/api/v1/museums/orsay/objects/Q1/content?language=fr")
    assert r.status_code == 200
    tabs = r.json()["tabs"]
    overview = next((t for t in tabs if t["section_code"] == "overview"), None)
    assert overview is not None
    assert overview["label"] == "Aperçu"


def _make_stub(monkeypatch):
    """把 Q1 变成纯 stub 件，并让懒生成的后台任务空跑（只落锁，不真花钱）。"""
    import app.core.config as cfg
    import app.services.enrichment.lazy as lazy

    monkeypatch.setattr(cfg.settings, "ENVIRONMENT", "staging")
    monkeypatch.setattr(lazy, "run_lazy_generation", lambda *a, **k: None)

    from sqlalchemy.orm import Session

    from app.models.museum_object import MuseumObject

    db: Session = next(iter(app.dependency_overrides[get_db]()))
    o = db.query(MuseumObject).filter_by(qid="Q1").one()
    o.content_status = "stub"
    db.query(ObjectContentSection).delete()
    db.commit()


def _as_logged_in(monkeypatch):
    """让 `_caller_id` 认出一个身份。返回请求要带的 header。"""
    from app.services.auth_service import AuthService

    monkeypatch.setattr(
        AuthService,
        "get_current_user",
        staticmethod(lambda db, token: type("U", (), {"id": "user-1"})()),
    )
    return {"Authorization": "Bearer whatever"}


def test_first_open_of_stub_returns_generating_true(client, monkeypatch):
    # 竞态修复:首次点开未富化件,端点应先触发懒生成上锁、再读内容 → generating=true
    # (原 bug:先读后触发→首请求 generating=false→前端显"待完善"不轮询,永不刷新)
    #
    # 2026-09-20 起这条**必须带令牌**:匿名不再点火(成本闸)。它与下面那条
    # `..._anonymous_does_not_trigger` 是同一张 2×2 的两格,**缺一半等于没测** ——
    # 只留这条的话,把整个闸删掉也会绿;只留那条的话,把 maybe_trigger 整个删掉也会绿。
    _make_stub(monkeypatch)
    headers = _as_logged_in(monkeypatch)

    r = client.get(
        "/api/v1/museums/orsay/objects/Q1/content?language=zh", headers=headers
    )
    assert r.status_code == 200
    assert r.json()["generating"] is True  # 触发在读之前 → 锁已可见


def test_first_open_of_stub_anonymous_does_not_trigger(client, monkeypatch):
    """匿名点开 stub 件:照常拿到内容,但**一分钱都不花**。

    断言的是"生成函数没被调用"而不是状态码 —— 状态码对证明不了闸站在花费**上游**,
    一个先调 LLM 再返回 200 的实现照样全绿,而钱已经付了。
    """
    import app.services.enrichment.lazy as lazy

    _make_stub(monkeypatch)
    calls = []
    monkeypatch.setattr(lazy, "run_lazy_generation", lambda *a, **k: calls.append(a))

    r = client.get("/api/v1/museums/orsay/objects/Q1/content?language=zh")
    assert r.status_code == 200
    assert calls == []
    assert r.json()["generating"] is False  # 没上锁


def test_broken_token_is_treated_as_anonymous_not_401(client, monkeypatch):
    """坏/过期令牌 → 按匿名处理，**绝不 401**。

    老 App 拿着过期 token 打详情页,一旦 401 整页就崩了 —— 而这个端点本来就允许匿名读。
    """
    import app.services.enrichment.lazy as lazy
    from app.services.auth_service import AuthService

    _make_stub(monkeypatch)
    calls = []
    monkeypatch.setattr(lazy, "run_lazy_generation", lambda *a, **k: calls.append(a))

    def _boom(db, token):
        raise ValueError("token expired")

    monkeypatch.setattr(AuthService, "get_current_user", staticmethod(_boom))

    r = client.get(
        "/api/v1/museums/orsay/objects/Q1/content?language=zh",
        headers={"Authorization": "Bearer expired"},
    )
    assert r.status_code == 200  # 不是 401
    assert calls == []  # 也不点火


def test_daily_budget_exhausted_blocks_generation(client, monkeypatch):
    """当日预算用尽:持令牌也不点火。

    这是身份闸覆盖不到的那一半 —— 注册一个号就能刷,可追溯但不会自动停。
    """
    import app.services.enrichment.lazy as lazy

    _make_stub(monkeypatch)
    headers = _as_logged_in(monkeypatch)
    calls = []
    monkeypatch.setattr(lazy, "run_lazy_generation", lambda *a, **k: calls.append(a))
    monkeypatch.setattr(lazy, "daily_budget_exhausted", lambda db, **k: True)

    r = client.get(
        "/api/v1/museums/orsay/objects/Q1/content?language=zh", headers=headers
    )
    assert r.status_code == 200
    assert calls == []
