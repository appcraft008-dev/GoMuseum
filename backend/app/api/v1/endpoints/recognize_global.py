"""全局识别端点 POST /api/v1/recognize(museum 可选)。

museum 不给 → 全局跨馆识别(service slug=None);给了不存在 → 404;给了且存在 →
馆内语义(与老端点 /museums/{slug}/recognize 完全一致)。老端点内部委托到本文件的
run_recognition,共享身份解析/计费/错误映射,行为零变化。契约加法,不动老端点。
"""

import logging
import time
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import get_db

logger = logging.getLogger(__name__)

router = APIRouter()
# 必看打卡(spec 2026-10-27 §五.1):快门现场拍 = camera,相册/最近照片 = gallery;
# 缺省 = 未知(老 App),永不算打卡
Capture = Literal["camera", "gallery"]
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
    capture: str | None = None,
) -> dict:
    """共享识别逻辑:身份(Bearer 令牌或 device_id)→ 计费识别 → 402/404 映射。
    slug=None 为全局跨馆;slug 给了但目录无此馆 → out is None → 404。
    计费语义不变:配额用尽在 GPT 调用前抛 QuotaExceededError → 402。"""
    from app.services.event_log import log_event
    from app.services.recognition.service import (
        QuotaExceededError,
        recognize_billed,
    )
    from app.services.visibility import (
        can_preview,
        museum_visible,
        visible_museum_ids,
    )

    user_id = _user_id(db, credentials)
    if not user_id and not device_id:
        raise HTTPException(status_code=401, detail={"reason": "identity_required"})
    preview = can_preview(db, credentials)
    # 隐身馆与未知馆同一个 404,且在扣费/调 GPT 之前
    if slug is not None and not museum_visible(db, slug, preview):
        raise HTTPException(status_code=404, detail=f"museum not found: {slug}")
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
            visible=visible_museum_ids(db, preview),
            capture=capture,
        )
    except QuotaExceededError as e:
        # 付费漏斗的关键一环:没有它就答不出"多少人撞到额度墙"
        log_event(
            db,
            "free_quota_exhausted",
            user_id=user_id,
            device_id=device_id,
            museum_slug=slug,
        )
        from app.services.entitlement_service import pass_offer

        # `pass` 加法字段:撞墙那家馆该买的票(馆未知 = 全局识别前置闸 → null)
        # `museum` 加法字段:撞墙那家馆的 slug。前端据此按馆查权益 —— 持荷兰(生效)+
        # 巴黎(未激活)两张票时,全局 state 是 active,不按馆查就认不出该弹激活
        # 而不是付费墙(2026-10-05 真机)。
        raise HTTPException(
            status_code=402,
            detail={
                "reason": "quota_exceeded",
                "pass": (
                    pass_offer(db, e.museum, language) if e.museum is not None else None
                ),
                "museum": e.museum.slug if e.museum is not None else None,
            },
        )
    if out is None:
        raise HTTPException(status_code=404, detail=f"museum not found: {slug}")
    m = out.get("match") or {}
    if out.get("outcome") == "match" and m.get("qid"):
        _log_success(
            db, m.get("museum"), qid=m["qid"], user_id=user_id, device_id=device_id
        )
    return out


def _log_success(db, museum_slug, qid=None, **who) -> None:
    """识别成功 = 直判命中,或候选首次被点选(P3-14)。museum_used 每次成功都记,
    ops_report 按 (user, 馆) 去重算跨馆复用。qid 只记在 recognition_succeeded(加法)。"""
    from app.services.event_log import log_event

    log_event(db, "recognition_succeeded", museum_slug=museum_slug, qid=qid, **who)
    log_event(db, "museum_used", museum_slug=museum_slug, **who)


@router.post("/recognize")
def recognize_global(
    image: UploadFile = File(...),
    museum: str | None = None,
    language: str = "zh",
    mode: str = "artwork",
    device_id: str | None = None,
    capture: Capture | None = None,
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
        capture=capture,
    )


class ConfirmRequest(BaseModel):
    phash: str
    qid: str
    # S4:"search" = 用户在选择页搜到这件(识别没认出来)。只记答案,不计费 ——
    # 搜索一直是免费的,听讲解走详情页手动解锁。缺省=候选确认(现行计费语义)。
    source: Literal["candidates", "search"] = "candidates"


class RejectRequest(BaseModel):
    phash: str = Field(max_length=64)
    # 候选恒 ≤3;上限放宽到 10 防客户端变化,qid 长度同列宽 32
    qids: list[Annotated[str, Field(max_length=32)]] = Field(max_length=10)


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
    from app.services.recognition.events import clear_capture, confirm_event
    from app.services.visibility import can_preview, qid_visible

    # 隐身馆的藏品:什么都不做(恒 204,与未知 qid 不可区分)
    if not qid_visible(db, body.qid, can_preview(db, credentials)):
        return Response(status_code=204)
    first_time = confirm_event(db, body.phash, body.qid, body.source)
    if body.source == "search":
        return Response(status_code=204)
    if not first_time:
        # 改选:同一张照片已扣过一次,不再扣,打卡跟着挪到新选的这件(spec §五.3 边角)
        return Response(status_code=204)
    # 必看打卡只认扣费通过的确认:没走到「票覆盖 / 扣成」就撤销这行的 capture(§五.2)
    try:
        if not _bill_confirm(db, body.qid, _user_id(db, credentials)):
            clear_capture(db, phash=body.phash)
    except BaseException:
        clear_capture(db, phash=body.phash)
        raise
    return Response(status_code=204)


def _bill_confirm(db: Session, qid: str, user_id: str | None) -> bool:
    """候选首次确认的计费。返回这次是否已付(票覆盖或扣成)。"""
    from app.services import entitlement_service as es
    from app.services.benefits_service import BenefitsService

    museum = es.museum_of_qid(db, qid)
    _log_success(db, museum.slug if museum else None, qid=qid, user_id=user_id)
    # 匿名(无令牌)跳过:解锁的音频要令牌才用得上,扣了也无处兑现。
    if not user_id:
        return False
    # D7/D8:覆盖**这件所在馆**的票生效中 → 不扣、也不写免费解锁(票本来就覆盖)。
    # 只看任意一张票的话,持最便宜的票就能在别的城市逐件白拿主讲解。
    if es.resolve_state(db, user_id, museum)[0] == es.ACTIVE:
        return True
    benefits = BenefitsService(db)
    # 这件已解锁未过期 → 不再扣(同 recognize_billed 的重拍不扣)。实际路径:作品照
    # 认不出 → 说明牌直接命中(已扣、已解锁)→ App 进讲解页用作品照 phash 发确认
    if qid in es.free_audio_qids(benefits.get_or_create_benefits(user_id=user_id)):
        return True
    # 顺序同 /entitlements/audio/unlock:**先扣再解**。反过来写的话
    # 额度已空时权益已经发出去,白送的正是我们要卖的东西。
    if not benefits.consume_recognition(user_id=user_id):
        return False
    es.unlock_free_audio(db, user_id, [qid])
    return True


@router.post("/recognize/reject", status_code=204)
def recognize_reject(body: RejectRequest, db: Session = Depends(get_db)) -> Response:
    """候选卡「都不是」(S3):记下被否定的候选,喂识别质量分析。fire-and-forget 恒 204。
    不计费、不需身份 —— 只写作品 qid,不含用户信息。"""
    from app.services.recognition.events import reject_event

    reject_event(db, body.phash, body.qids)
    return Response(status_code=204)


# 比这更晚才到的 client-event 算补发:其间可能换过账号,令牌不一定是当时的人。
_CLIENT_EVENT_LATE_S = 60


class ClientEventRequest(BaseModel):
    """只有 App 看得到的事(V79,加法端点):
    额度付费页真弹出来了(后端 402 时记的 free_quota_exhausted 只是「撞墙」,
    弹没弹出来后端不知道);语音付费墙真弹出来了(额度用完时 App 本地就拦下,
    不发请求,V80);识别请求没拿到结果(没网时请求根本到不了这里,
    App 先攒在本机,联网后补报,`at` 是真实发生时刻)。"""

    name: Literal[
        "paywall_viewed_from_quota",
        "paywall_viewed_from_audio",
        "recognition_failed",
    ]
    museum: str | None = Field(default=None, max_length=64)
    qid: str | None = Field(default=None, max_length=32)
    reason: Literal["no_network", "timeout", "server", "other"] | None = None
    device_id: str | None = Field(default=None, max_length=64)
    at: float | None = None  # epoch 秒


@router.post("/recognize/client-event", status_code=204)
def recognize_client_event(
    body: ClientEventRequest,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> Response:
    """fire-and-forget 恒 204;名字走白名单,购买等后端自记的事件不许客户端伪造。"""
    from app.services.event_log import log_event

    props = {
        k: v
        for k, v in (("reason", body.reason), ("at", body.at), ("qid", body.qid))
        if v is not None
    }
    late = body.at is not None and time.time() - body.at > _CLIENT_EVENT_LATE_S
    log_event(
        db,
        body.name,
        # 补发且有设备号:只记设备。运营报告按设备把它并回当时的账号
        user_id=None if late and body.device_id else _user_id(db, credentials),
        device_id=body.device_id,
        museum_slug=body.museum,
        **props,
    )
    return Response(status_code=204)
