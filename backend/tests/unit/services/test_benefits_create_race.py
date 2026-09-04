"""新账号首次使用时并发建配额行 → 唯一约束冲突 → 500。

prod 实证 2026-09-04:刚注册的账号 a94cc7f7… 一进 App,
`GET /api/v1/payment/benefits` 返回 500,日志里是
`duplicate key value violates unique constraint "ix_user_benefits_user_id"`。

根因:`get_or_create_benefits` 是「先查后插」,两步之间没有互斥。App 一进首页
就并行打好几个走这条路的接口(首页额度 / 权益页 / 付费墙),于是**第一次使用**时
多个请求同时查不到、同时插入 —— 一个成功,其余撞唯一约束炸掉。

撞了不是错误,是"别人替我建好了"。
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.models.user import User
from app.models.user_benefits import UserBenefits
from app.services.benefits_service import BenefitsService


@pytest.fixture()
def engine(tmp_path):
    # 用文件库而不是 `sqlite://` + StaticPool:那种写法两个 Session 共用同一条
    # 连接、也就共用同一个事务,根本模拟不出"另一个请求抢先提交"。
    eng = create_engine(f"sqlite:///{tmp_path/'t.db'}")
    Base.metadata.create_all(bind=eng, tables=[User.__table__, UserBenefits.__table__])
    return eng


def test_concurrent_create_returns_the_winner_row_instead_of_500(engine):
    mine = sessionmaker(bind=engine)()
    other = sessionmaker(bind=engine)()
    svc = BenefitsService(mine)

    # 在我 SELECT 之后、INSERT 提交之前,另一个请求把同一行建好了。
    real_commit = mine.commit
    raced = {"done": False}

    def racing_commit():
        if not raced["done"]:
            raced["done"] = True
            other.add(
                UserBenefits(
                    user_id="u-1",
                    device_id="dev-1",
                    recognition_quota=5,
                    referral_bonus_quota=0,
                    total_recognitions_used=0,
                )
            )
            other.commit()
        return real_commit()

    mine.commit = racing_commit

    got = svc.get_or_create_benefits(user_id="u-1", device_id="dev-1")

    assert got is not None, "撞了并发就抛 500 —— 新用户第一屏就报错"
    assert got.user_id == "u-1"
    assert raced["done"], "没真的制造出竞态,这条测试等于没测"

    # 只该有一行:回查拿的是赢家那行,不是又插了一条
    mine.commit = real_commit
    assert mine.query(UserBenefits).filter(UserBenefits.user_id == "u-1").count() == 1

    mine.close()
    other.close()


def test_conflict_that_is_not_this_race_still_raises(engine):
    """唯一约束报冲突、回查却什么都没有 → 不是这个竞态,不许吞。"""
    mine = sessionmaker(bind=engine)()
    other = sessionmaker(bind=engine)()
    svc = BenefitsService(mine)

    real_commit = mine.commit

    def bogus_commit():
        # 冲突来自**另一个** user_id 的行:回查 u-1 注定查不到
        mine.rollback()
        other.add(UserBenefits(user_id="someone-else", device_id="dev-9"))
        other.commit()
        other.add(UserBenefits(user_id="someone-else", device_id="dev-9"))
        return other.commit()

    mine.commit = bogus_commit

    with pytest.raises(Exception):
        svc.get_or_create_benefits(user_id="u-1", device_id="dev-1")

    mine.close()
    other.close()
