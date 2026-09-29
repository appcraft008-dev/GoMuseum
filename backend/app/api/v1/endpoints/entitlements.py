"""统一权益接口(收费模式定案 2026-07-27)。

**前端唯一入口**:不得自行组合 expires_at/quota 等字段判断——
多端各写一套必然不一致(过期没关、退款没撤、恢复购买错位)。前端只看 `can`。
(`is_premium`/`day_pass_active` 已随老商品下线移除,不再有第二套真相源。)

⚠️ user_id **从令牌取,绝不从查询参数取**:权益是钱。曾把 `user_id` 当 query param,
等于任何人都能读别人的权益,更糟的是 `POST /activate` 可以烧掉别人的 7 天票
(激活即开始连续计时、幂等不可撤)。与 payment.py 一致走 AuthService。
"""

import logging

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.user_benefits import UserBenefits
from app.services import entitlement_service as es
from app.services.auth_service import AuthService
from app.services.event_log import log_event
from app.services.visibility import can_preview

logger = logging.getLogger(__name__)
router = APIRouter()
security = HTTPBearer()


def _benefits(db: Session, user_id: str):
    return db.query(UserBenefits).filter_by(user_id=user_id).one_or_none()


def _museum(db: Session, slug: str | None, credentials):
    """`?museum=slug` → 馆。不给 = None(任意一张票)。
    未知/隐身馆一律 404(可见性闸:与"不存在"不可区分)。"""
    if not slug:
        return None
    from app.models.museum import Museum
    from app.services.visibility import museum_visible

    if not museum_visible(db, slug, can_preview(db, credentials)):
        raise HTTPException(status_code=404, detail=f"museum not found: {slug}")
    return db.query(Museum).filter_by(slug=slug).one()


def _me(db: Session, credentials: HTTPAuthorizationCredentials):
    """返回 (user_id, is_guest) —— is_guest 决定 can.purchase(买票前须登录)。"""
    user = AuthService.get_current_user(db, credentials.credentials)
    return str(user.id), bool(user.is_guest)


@router.get("/me")
def my_entitlements(
    museum: str | None = None,
    language: str = "zh",
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
) -> dict:
    """当前权益。到期在读取时实时判定,不依赖定时任务(漏跑=白送权限)。

    `museum`(加法,可选):馆内页面带上 → state/can 只看覆盖这家馆的票。
    持巴黎票进荷兰的馆,不能显示"通票生效中"而点播放却 402。"""
    user_id, is_guest = _me(db, credentials)
    return es.summary(
        db,
        user_id,
        _benefits(db, user_id),
        is_guest=is_guest,
        museum=_museum(db, museum, credentials),
        language=language,
        preview=can_preview(db, credentials),
    )


@router.get("/history")
def my_pass_history(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
) -> dict:
    """票据历史(新到旧),供权益页显示「购买记录」与「上一张票」。

    **加法端点**:老 App 不知道它存在,契约前向兼容。
    与 `/me` 分开是因为 `/me` 是热路径 —— 历史只有这一页要看。
    """
    user_id, _ = _me(db, credentials)
    return {"passes": es.history(db, user_id)}


@router.post("/activate")
def activate_pass(
    museum: str | None = None,
    language: str = "zh",
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
) -> dict:
    """首次使用高级功能、且**用户显式确认**后调用,开始连续 7×24h。

    ⚠️ 绝不静默激活:旅游产品用户常提前几天买,误触一次就烧掉整张票=差评来源。
    幂等:已激活再调不续期也不重置。

    `museum`(加法,可选):只激活覆盖这家馆的那张 —— 同时持两国未激活票时,
    在荷兰点激活绝不能烧掉巴黎那张。老 App 不带 = 旧行为。
    """
    user_id, is_guest = _me(db, credentials)
    m = _museum(db, museum, credentials)
    es.activate(db, user_id, m)
    log_event(db, "pass_activated", user_id=user_id)
    return es.summary(
        db,
        user_id,
        _benefits(db, user_id),
        is_guest=is_guest,
        museum=m,
        language=language,
    )


@router.post("/audio/unlock")
def unlock_audio(
    qid: str,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
) -> dict:
    """用 1 次免费额度解锁这件作品的语音(主讲解段)。

    免费额度是**一个池子**:拍照识别扣它,在藏品页主动解锁也扣它。
    这样"免费能体验多少"就只有一个数字,不必再维护第二个(2026-09-19 定)。

    ⚠️ **必须由用户显式确认后才调**(同 /activate 的理由):静默扣掉一次额度,
    用户在一件无所谓的作品上花掉名额、走到真正想听的那件前才发现,是差评来源。
    确认文案要写明"将用掉 1 次"。

    幂等:已解锁(或通票生效)直接返回,**不重复扣**。额度为 0 → 402,前端弹付费墙。
    """

    user_id, is_guest = _me(db, credentials)
    benefits = _benefits(db, user_id)

    # qid 必须真实存在。不校验的话,客户端一个笔误就让用户白掉一次额度 ——
    # 这是他花钱换来的东西,而且 404 比"扣了钱什么也没解锁"好排查得多。
    # 隐身馆的藏品与不存在的同一个 404,且在扣额度之前(可见性闸)。
    from app.services.visibility import qid_visible

    museum = es.museum_of_qid(db, qid)
    if museum is None or not qid_visible(db, qid, can_preview(db, credentials)):
        raise HTTPException(status_code=404, detail={"reason": "object_not_found"})

    def _done():
        return es.summary(
            db, user_id, _benefits(db, user_id), is_guest=is_guest, museum=museum
        )

    # 覆盖**这件作品所在馆**的票生效中:本来就能听,不扣。只看任意一张票的话,
    # 持巴黎票在荷兰点「解锁」会幂等返回、什么都没解锁 —— 用户卡死。
    if es.resolve_state(db, user_id, museum)[0] == es.ACTIVE:
        return _done()
    # 已解锁且未过期:直接返回,绝不二次扣费(重复点"解锁"不该花两次额度)
    if qid in es.free_audio_qids(benefits):
        return _done()

    from app.services.benefits_service import BenefitsService

    # ⚠️ 顺序:**先扣费再解锁**。反过来的话扣费失败(额度已空)时权益已经发出去,
    # 等于白送 —— 而这条路径正是免费用户撞墙后走的,白送的就是我们要卖的东西。
    if not BenefitsService(db).consume_recognition(user_id=user_id):
        log_event(db, "paywall_viewed_from_audio", user_id=user_id, qid=qid)
        raise HTTPException(
            status_code=402,
            detail={"reason": "pass_required", "pass": es.pass_offer(db, museum)},
        )
    es.unlock_free_audio(db, user_id, [qid])
    log_event(db, "free_audio_unlocked", user_id=user_id, qid=qid)
    return _done()
