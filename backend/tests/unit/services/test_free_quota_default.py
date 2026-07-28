"""免费识别额度的默认值有唯一真相源(settings.FREE_RECOGNITION_QUOTA)。

此前同一个数字写死在三处(模型 default / benefits_service 建行 / entitlement 兜底),
改一处漏两处。这两条用例锁住"改配置三处一起变",而不是锁死具体数字 5。
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import settings
from app.core.database import Base
from app.models.user import User
from app.models.user_benefits import UserBenefits
from app.services.benefits_service import BenefitsService


@pytest.fixture()
def db():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(
        bind=engine, tables=[User.__table__, UserBenefits.__table__]
    )
    s = sessionmaker(bind=engine)()
    yield s
    s.close()


def test_free_tier_is_five():
    """当前定案:免费 5 次(2026-07-28 由 10 收紧)。"""
    assert settings.FREE_RECOGNITION_QUOTA == 5


def test_new_user_gets_configured_quota(db, monkeypatch):
    monkeypatch.setattr(settings, "FREE_RECOGNITION_QUOTA", 5)
    b = BenefitsService(db).get_or_create_benefits(user_id="new-user")
    assert b.recognition_quota == 5


def test_model_default_follows_settings(db, monkeypatch):
    """不经 service 直接建行(如迁移/脚本)也要拿到配置值,不是写死的 10。"""
    monkeypatch.setattr(settings, "FREE_RECOGNITION_QUOTA", 3)
    b = UserBenefits(user_id="direct")
    db.add(b)
    db.commit()
    db.refresh(b)
    assert b.recognition_quota == 3
