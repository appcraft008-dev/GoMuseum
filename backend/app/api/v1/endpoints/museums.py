"""Museum pack endpoints

提供馆包数据（馆藏清单/元信息），数据由 DB 读取（Phase 5 改造）。
"""

import logging

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.services.museum_repo import get_museum_pack as repo_pack
from app.services.museum_repo import (
    get_object_content,
)
from app.services.museum_repo import list_museums as repo_list
from app.services.museum_repo import list_objects as repo_list_objects

logger = logging.getLogger(__name__)

router = APIRouter()

_bearer = HTTPBearer(auto_error=False)


def _require_audio_access(
    db: Session, credentials: HTTPAuthorizationCredentials | None, qid: str
) -> tuple[str, str]:
    """语音付费墙的**唯一执行点**。前端的付费墙 UI 只是它的表达——
    没有这道闸,老 App / curl / 改客户端都能白拿音频,还会触发 TTS 花我们的钱。

    必须在触发生成**之前**调用。拒绝返 402(不是 403):前端据此弹付费页。
    返回 (user_id, kind);kind == "claimable" 时**音频送达后**才认领首件——
    生成可能 404/409/503,在这里认领会让用户"什么都没听到但名额没了"。
    """
    from app.services import entitlement_service as es
    from app.services.auth_service import AuthService
    from app.services.event_log import log_event

    if credentials is None:
        raise HTTPException(status_code=401, detail={"reason": "auth_required"})
    user_id = str(AuthService.get_current_user(db, credentials.credentials).id)
    kind = es.audio_access(db, user_id, qid)
    if kind == "denied":
        # 服务端自己就知道付费墙被撞到了,不必等前端埋点
        log_event(db, "paywall_viewed_from_audio", user_id=user_id, qid=qid)
        raise HTTPException(status_code=402, detail={"reason": "pass_required"})
    return user_id, kind


def _claim_after_success(db: Session, gate: tuple[str, str], qid: str) -> None:
    """音频确实送达了才认领首件(见 _require_audio_access 的说明)。"""
    from app.services import entitlement_service as es

    user_id, kind = gate
    if kind == "claimable":
        es.claim_audio_now(db, user_id, qid)


@router.get("")
def list_museums(db: Session = Depends(get_db)) -> list[dict]:
    """已收录馆包列表（不含完整馆藏，供探索页索引）"""
    return repo_list(db)


@router.get("/{slug}/objects/{qid}/content")
def object_content(
    slug: str,
    qid: str,
    background_tasks: BackgroundTasks,
    language: str = "zh",
    db: Session = Depends(get_db),
) -> dict:
    """展品讲解（按 tab 分节返回）。stub 首次访问触发懒生成（后台,契约§路线图3c）。
    ⚠️ 顺序:先 maybe_trigger 上锁、再读内容——否则首次触发的那次请求会返回
    generating=false（锁尚未落库）,前端渲染"待完善"完整页且不轮询,永不刷新。"""
    from app.services.enrichment.lazy import maybe_trigger

    maybe_trigger(db, qid, schedule=background_tasks.add_task, language=language)
    data = get_object_content(db, slug, qid, language)
    if data is None:
        raise HTTPException(status_code=404, detail=f"object not found: {qid}")
    return data


@router.get("/{slug}/objects/{qid}/audio")
def object_audio(
    slug: str,
    qid: str,
    language: str = "zh",
    section: str = "guide",
    qa_sort: int | None = None,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> dict:
    """音频懒生成(点播放触发):guide/深度模块(section=段code)、问答(section=qa&qa_sort=N)、
    作者介绍(section=artist_bio,按作者共享)。语速由客户端 setPlaybackRate。
    同步 def:_synth 内 asyncio.run 不与主事件循环冲突(同 recognize 端点)。"""
    from app.services.enrichment.lazy_audio import (
        get_or_make_artist_bio_audio_url,
        get_or_make_audio_url,
        get_or_make_qa_audio_url,
    )

    gate = _require_audio_access(db, credentials, qid)

    try:
        if section == "qa":
            if qa_sort is None:
                raise HTTPException(
                    status_code=422, detail={"reason": "qa_sort_required"}
                )
            url, status = get_or_make_qa_audio_url(db, qid, language, qa_sort)
        elif section == "artist_bio":
            url, status = get_or_make_artist_bio_audio_url(db, qid, language)
        else:
            url, status = get_or_make_audio_url(db, slug, qid, language, section)
    except HTTPException:
        raise
    except Exception:
        logger.exception("TTS audio failed: %s/%s/%s", qid, language, section)
        raise HTTPException(status_code=503, detail={"reason": "tts_failed"})
    if status == "busy":
        raise HTTPException(status_code=409, detail={"reason": "audio_generating"})
    if status == "no_text":
        raise HTTPException(status_code=404, detail={"reason": "no_published_text"})
    _claim_after_success(db, gate, qid)
    return {"audio_url": url}


@router.get("/{slug}/objects/{qid}/audio/stream")
async def object_audio_stream(
    slug: str,
    qid: str,
    language: str = "zh",
    section: str = "guide",
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
):
    """流式音频(边生成边播,一次 TTS 调用 tee 落库)。首播缩短等待;缓存命中返 R2 URL。
    落库跑 detached task,用户中途退出也把整段落 R2(tts-1 按字符已付费,抽完最省)。
    guide/深度段;qa/artist_bio 仍走非流式 /audio(v1 范围)。"""
    from app.services.enrichment.streaming_audio import stream_section_audio

    gate = _require_audio_access(db, credentials, qid)

    try:
        status, payload = await stream_section_audio(qid, language, section)
    except Exception:
        logger.exception("TTS stream failed: %s/%s/%s", qid, language, section)
        raise HTTPException(status_code=503, detail={"reason": "tts_failed"})
    if status == "busy":
        raise HTTPException(status_code=409, detail={"reason": "audio_generating"})
    if status == "no_text":
        raise HTTPException(status_code=404, detail={"reason": "no_published_text"})
    _claim_after_success(db, gate, qid)
    if status == "cached":
        # 已落库:不重复生成,直接给 R2 直链(前端从 R2 播)
        return {"audio_url": payload}
    return StreamingResponse(payload, media_type="audio/mpeg")


@router.get("/{slug}/objects")
def list_objects(
    slug: str,
    language: str = "zh",
    category: str | None = None,
    sort: str = "popularity",
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
) -> dict:
    """分页藏品列表（A2/A3 列表页）"""
    page = repo_list_objects(
        db,
        slug,
        language=language,
        category=category,
        sort=sort,
        limit=limit,
        offset=offset,
    )
    if page is None:
        raise HTTPException(status_code=404, detail=f"museum not found: {slug}")
    return page


@router.post("/{slug}/recognize")
def recognize_artwork(
    slug: str,
    image: UploadFile = File(...),
    language: str = "zh",
    mode: str = "artwork",
    device_id: str | None = None,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> dict:
    """拍照识别(接地:身份只来自目录命中;mode=label 为引导补拍的墙签纯转写)。
    计费:match/candidates 扣1,unrecognized/缓存命中不扣,超额 402(规则用户批准)。
    身份=Bearer 令牌(App 全局拦截器自带)或 device_id(curl/匿名测试)。
    同步 def:FastAPI 扔线程池执行 → vision 内 asyncio.run 不与主事件循环冲突。
    实现委托给 recognize_global.run_recognition(全局端点共享同一逻辑),行为不变。"""
    from app.api.v1.endpoints.recognize_global import run_recognition

    return run_recognition(
        db,
        slug,
        image,
        language=language,
        mode=mode,
        device_id=device_id,
        credentials=credentials,
    )


@router.get("/{slug}")
def get_museum_pack(
    slug: str,
    language: str = "zh",
    artworks: bool = True,
    db: Session = Depends(get_db),
) -> dict:
    """完整馆包：馆元数据 + 按热度排序的馆藏列表。

    `artworks=false` 省掉藏品数组(加法参数,缺省 true 保老 App 不变)——
    列表页走分页 /objects,门面只要 cover/categories/description。
    卢浮宫实测:全量 5.0MB/5.7s → 省掉后 KB 级。"""
    pack = repo_pack(db, slug, language, artworks=artworks)
    if pack is None:
        raise HTTPException(status_code=404, detail=f"museum pack not found: {slug}")
    return pack
