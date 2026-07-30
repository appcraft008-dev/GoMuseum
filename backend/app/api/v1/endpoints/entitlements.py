"""统一权益接口(收费模式定案 2026-07-27)。

**前端唯一入口**:不得自行组合 expires_at/quota 等字段判断——
多端各写一套必然不一致(过期没关、退款没撤、恢复购买错位)。前端只看 `can`。
(`is_premium`/`day_pass_active` 已随老商品下线移除,不再有第二套真相源。)

⚠️ user_id **从令牌取,绝不从查询参数取**:权益是钱。曾把 `user_id` 当 query param,
等于任何人都能读别人的权益,更糟的是 `POST /activate` 可以烧掉别人的 7 天票
(激活即开始连续计时、幂等不可撤)。与 payment.py 一致走 AuthService。
"""

import logging

from fastapi import APIRouter, Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.user_benefits import UserBenefits
from app.services import entitlement_service as es
from app.services.auth_service import AuthService
from app.services.event_log import log_event

logger = logging.getLogger(__name__)
router = APIRouter()
security = HTTPBearer()


def _benefits(db: Session, user_id: str):
    return db.query(UserBenefits).filter_by(user_id=user_id).one_or_none()


def _me(db: Session, credentials: HTTPAuthorizationCredentials):
    """返回 (user_id, is_guest) —— is_guest 决定 can.purchase(买票前须登录)。"""
    user = AuthService.get_current_user(db, credentials.credentials)
    return str(user.id), bool(user.is_guest)


@router.get("/me")
def my_entitlements(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
) -> dict:
    """当前权益。到期在读取时实时判定,不依赖定时任务(漏跑=白送权限)。"""
    user_id, is_guest = _me(db, credentials)
    return es.summary(db, user_id, _benefits(db, user_id), is_guest=is_guest)


@router.post("/activate")
def activate_pass(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
) -> dict:
    """首次使用高级功能、且**用户显式确认**后调用,开始连续 7×24h。

    ⚠️ 绝不静默激活:旅游产品用户常提前几天买,误触一次就烧掉整张票=差评来源。
    幂等:已激活再调不续期也不重置。
    """
    user_id, is_guest = _me(db, credentials)
    es.activate(db, user_id)
    log_event(db, "pass_activated", user_id=user_id)
    return es.summary(db, user_id, _benefits(db, user_id), is_guest=is_guest)
