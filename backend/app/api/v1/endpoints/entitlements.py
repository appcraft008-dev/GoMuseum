"""统一权益接口(收费模式定案 2026-07-27)。

**前端唯一入口**:不得自行组合 is_premium/day_pass_active/expires_at/quota 判断——
多端各写一套必然不一致(过期没关、退款没撤、恢复购买错位)。前端只看 `can`。
"""

import logging

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.user_benefits import UserBenefits
from app.services import entitlement_service as es

logger = logging.getLogger(__name__)
router = APIRouter()


def _benefits(db: Session, user_id: str):
    return db.query(UserBenefits).filter_by(user_id=user_id).one_or_none()


@router.get("/me")
def my_entitlements(user_id: str, db: Session = Depends(get_db)) -> dict:
    """当前权益。到期在读取时实时判定,不依赖定时任务(漏跑=白送权限)。"""
    return es.summary(db, user_id, _benefits(db, user_id))


@router.post("/activate")
def activate_pass(user_id: str, db: Session = Depends(get_db)) -> dict:
    """首次使用高级功能、且**用户显式确认**后调用,开始连续 7×24h。

    ⚠️ 绝不静默激活:旅游产品用户常提前几天买,误触一次就烧掉整张票=差评来源。
    幂等:已激活再调不续期也不重置。
    """
    es.activate(db, user_id)
    return es.summary(db, user_id, _benefits(db, user_id))
