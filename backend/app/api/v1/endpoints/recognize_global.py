"""全局识别端点 POST /api/v1/recognize(museum 可选)。

museum 不给 → 全局跨馆识别(service slug=None);给了不存在 → 404;给了且存在 →
馆内语义(与老端点 /museums/{slug}/recognize 完全一致)。老端点内部委托到本文件的
run_recognition,共享身份解析/计费/错误映射,行为零变化。契约加法,不动老端点。
"""

import logging

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db

logger = logging.getLogger(__name__)

router = APIRouter()
_bearer = HTTPBearer(auto_error=False)


def _user_id(db: Session, credentials: HTTPAuthorizationCredentials | None):
    """令牌 → user_id。坏/过期令牌按匿名处理(识别可退 device_id)。"""
    if not credentials:
        return None
    try:
        from app.services.auth_service import AuthService

        return str(AuthService.get_current_user(db, credentials.credentials).id)
    except Exception:
        return None


def run_recognition(
    db: Session,
    slug: str | None,
    image: UploadFile,
    *,
    language: str,
    mode: str,
    device_id: str | None,
    credentials: HTTPAuthorizationCredentials | None,
) -> dict:
    """共享识别逻辑:身份(Bearer 令牌或 device_id)→ 计费识别 → 402/404 映射。
    slug=None 为全局跨馆;slug 给了但目录无此馆 → out is None → 404。
    计费语义不变:配额用尽在 GPT 调用前抛 QuotaExceededError → 402。"""
    from app.services.event_log import log_event
    from app.services.recognition.service import (
        QuotaExceededError,
        recognize_billed,
    )

    user_id = _user_id(db, credentials)
    if not user_id and not device_id:
        raise HTTPException(status_code=401, detail={"reason": "identity_required"})
    data = image.file.read()
    try:
        out = recognize_billed(
            db,
            slug,
            data,
            user_id=user_id,
            device_id=device_id,
            language=language,
            mode=mode,
        )
    except QuotaExceededError:
        # 付费漏斗的关键一环:没有它就答不出"多少人撞到额度墙"
        log_event(
            db,
            "free_quota_exhausted",
            user_id=user_id,
            device_id=device_id,
            museum_slug=slug,
        )
        raise HTTPException(status_code=402, detail={"reason": "quota_exceeded"})
    if out is None:
        raise HTTPException(status_code=404, detail=f"museum not found: {slug}")
    return out


@router.post("/recognize")
def recognize_global(
    image: UploadFile = File(...),
    museum: str | None = None,
    language: str = "zh",
    mode: str = "artwork",
    device_id: str | None = None,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> dict:
    """拍照识别(museum 可选:不给=全库跨馆;给了不存在→404;给了存在=馆内)。
    身份=Bearer 令牌或 device_id;计费/分流语义同馆内端点。"""
    return run_recognition(
        db,
        museum,
        image,
        language=language,
        mode=mode,
        device_id=device_id,
        credentials=credentials,
    )


class ConfirmRequest(BaseModel):
    phash: str
    qid: str


@router.post("/recognize/confirm", status_code=204)
def recognize_confirm(
    body: ConfirmRequest,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> Response:
    """用户从候选卡点选「就是这件」:回填 confirmed_qid(展陈证据)**并在此计费**。

    这里是候选态唯一的扣费点(2026-09-20 改,见 recognize_billed):返回候选时
    不扣,用户点「都不是」就什么也没花 —— 不为失败付费。点选=确认识别成功,
    扣 1 次并解锁这件的主讲解语音,与 match 那条路完全同价。

    仍是 fire-and-forget(恒 204):扣不动额度也不报错,用户进详情页点播放时
    会照常弹付费墙 —— 那里才是付费墙该出现的地方。

    ⚠️ **只在首次确认时解锁**。重复确认(点错了回去改选另一件)不扣费,但也不
    再解锁:事件行只存 top_qid,这里无从知道那次识别到底给了哪几个候选,放行的话
    qid 可以任填 —— 确认过一次就能用一次额度解锁全馆。改选那件要听,走详情页
    的手动解锁确认(`/entitlements/audio/unlock`,那里明写"将用掉 1 次")。"""
    from app.services.recognition.events import confirm_event

    first_time = confirm_event(db, body.phash, body.qid)
    user_id = _user_id(db, credentials)
    # 匿名(无令牌)跳过:解锁的音频要令牌才用得上,扣了也无处兑现。
    if first_time and user_id:
        from app.services import entitlement_service as es
        from app.services.benefits_service import BenefitsService

        # 通票生效期内不动免费额度(不限次识别是卖给他的权益)。
        if es.resolve_state(db, user_id)[0] != es.ACTIVE:
            # 顺序同 /entitlements/audio/unlock:**先扣再解**。反过来写的话
            # 额度已空时权益已经发出去,白送的正是我们要卖的东西。
            if not BenefitsService(db).consume_recognition(user_id=user_id):
                return Response(status_code=204)
        es.unlock_free_audio(db, user_id, [body.qid])
    return Response(status_code=204)
