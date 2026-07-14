"""识别计费身份串号修复:匿名/令牌失败的请求绝不命中某个账号的配额行。
prod 实证:登录 appcraft008(999999)却 402——device fallback `.first()` 撞到别账号耗尽行。"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

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


def _row(db, **kw):
    b = UserBenefits(**kw)
    db.add(b)
    db.commit()
    db.refresh(b)
    return b


def test_anonymous_request_never_bills_account_row(db):
    # 账号 A 的配额行(已耗尽),挂在设备 D 上
    _row(
        db,
        user_id="acct-A",
        device_id="D",
        recognition_quota=0,
        total_recognitions_used=10,
    )
    # 令牌抽风 → user_id=None → 只按 device 找。修前:撞 A 的耗尽行→402。
    access = BenefitsService(db).check_access(user_id=None, device_id="D")
    assert access["has_access"] is True  # 修后:不碰 A,走匿名行,有额度
    a = db.query(UserBenefits).filter_by(user_id="acct-A").one()
    assert a.recognition_quota == 0 and a.total_recognitions_used == 10  # A 未被误动


def test_anonymous_reuses_existing_anonymous_row(db):
    _row(
        db,
        user_id=None,
        device_id="D2",
        recognition_quota=10,
        total_recognitions_used=3,
    )
    b = BenefitsService(db).get_or_create_benefits(user_id=None, device_id="D2")
    assert b.user_id is None and b.total_recognitions_used == 3  # 复用,不新建
    assert db.query(UserBenefits).filter_by(device_id="D2").count() == 1


def test_logged_in_hits_own_row(db):
    # 同设备两账号:A 耗尽、B 有额度;B 登录必须命中 B 自己
    _row(
        db,
        user_id="acct-A",
        device_id="D",
        recognition_quota=0,
        total_recognitions_used=10,
    )
    _row(
        db,
        user_id="acct-B",
        device_id="D",
        recognition_quota=999999,
        total_recognitions_used=5,
    )
    access = BenefitsService(db).check_access(user_id="acct-B", device_id="D")
    assert access["has_access"] is True and access["total_used"] == 5
