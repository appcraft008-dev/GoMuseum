"""Museum pack endpoints

提供馆包数据（馆藏清单/元信息），数据由 DB 读取（Phase 5 改造）。
"""

import logging
from typing import Literal

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    HTTPException,
    Path,
    Request,
    Response,
    UploadFile,
)
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.config import MAX_PAGE_LIMIT
from app.core.database import get_db
from app.services.museum_repo import get_museum_pack as repo_pack
from app.services.museum_repo import (
    get_object_content,
)
from app.services.museum_repo import list_museums as repo_list
from app.services.museum_repo import list_objects as repo_list_objects
from app.services.share import share_info
from app.services.visibility import can_preview, museum_visible, qid_visible

logger = logging.getLogger(__name__)

router = APIRouter()

_bearer = HTTPBearer(auto_error=False)


def _require_audio_access(
    db: Session,
    credentials: HTTPAuthorizationCredentials | None,
    qid: str,
    *,
    language: str = "zh",
    section: str = "guide",
) -> str:
    """语音付费墙的**唯一执行点**。前端的付费墙 UI 只是它的表达——
    没有这道闸,老 App / curl / 改客户端都能白拿音频,还会触发 TTS 花我们的钱。

    必须在触发生成**之前**调用。拒绝返 402(不是 403):前端据此弹付费页。
    """
    from app.services import entitlement_service as es
    from app.services.auth_service import AuthService
    from app.services.event_log import log_event

    if credentials is None:
        raise HTTPException(status_code=401, detail={"reason": "auth_required"})
    user_id = str(AuthService.get_current_user(db, credentials.credentials).id)
    # scope 校验:通票只解锁覆盖**这件作品所在馆**的范围(按 qid 反查,不信 URL 的 slug)
    museum = es.museum_of_qid(db, qid)
    kind = es.audio_access(
        db, user_id, qid, language=language, section=section, museum=museum
    )
    if kind == "denied":
        # 服务端自己就知道付费墙被撞到了,不必等前端埋点
        log_event(db, "paywall_viewed_from_audio", user_id=user_id, qid=qid)
        raise HTTPException(
            status_code=402, detail=_pass_required(db, museum, language)
        )
    return user_id


def _pass_required(db: Session, museum, language: str) -> dict:
    """402 响应体。`pass` = 这家馆该买的那张票(加法字段;老 App 只读 reason)。
    撞墙那一刻兜底:拿着老馆包缓存的 App 也不会卖错票(spec 2026-09-28 §3.3)。"""
    from app.services import entitlement_service as es

    return {
        "reason": "pass_required",
        "pass": es.pass_offer(db, museum, language) if museum is not None else None,
    }


def _caller(db: Session, credentials: HTTPAuthorizationCredentials | None):
    """令牌 → 用户对象，**坏/过期令牌一律当匿名(None)，绝不 401**。

    与 `recognize_global._user_id` 同款。401 在这里是不能出的:老 App 拿着过期
    token 打探索页/详情页,一旦 401 整页就崩了 —— 而这两个端点本来就允许匿名读。
    """
    if not credentials:
        return None
    try:
        from app.services.auth_service import AuthService

        return AuthService.get_current_user(db, credentials.credentials)
    except Exception:
        return None


def _hidden(db: Session, credentials, slug: str, qid: str | None = None) -> bool:
    """可见性闸(spec 2026-09-20)。True = 调用方按"不存在"返回它自己的 404。
    必须放在任何花钱动作(懒生成/TTS)**之前**。"""
    preview = can_preview(db, credentials)
    if not museum_visible(db, slug, preview):
        return True
    return qid is not None and not qid_visible(db, qid, preview)


@router.get("")
def list_museums(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> list[dict]:
    """已收录馆包列表（不含完整馆藏，供探索页索引）"""
    return repo_list(db, preview=can_preview(db, credentials))


@router.get("/{slug}/must-see")
def museum_must_see(
    slug: str,
    language: str = "zh",
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> dict:
    """必看护照页(spec 2026-10-27 必看打卡 §五.4):清单 + 当前轮进度 + 勋章。

    令牌可选:匿名只给清单。清单里目录查不到/没图的件也列出(标题回退 qid),
    分母始终是清单件数。读的时候算出某轮打满会顺手落勋章(见 must_see_checkin)。"""
    from app.services import must_see
    from app.services.must_see_checkin import progress

    if _hidden(db, credentials, slug):
        raise HTTPException(status_code=404, detail=f"museum not found: {slug}")
    listed = must_see.MUST_SEE.get(slug) or []
    locs = must_see.MUST_SEE_LOCATION.get(slug) or {}
    from app.services.museum_repo import must_see_objects

    # 同馆藏列表的标题/作者/缩略图口径,但不过滤无图件、不整馆 count()
    by_qid = must_see_objects(db, slug, listed, language)
    if by_qid is None:  # 目录里没有这家馆
        raise HTTPException(status_code=404, detail=f"museum not found: {slug}")
    items = []
    for q in listed:
        it = by_qid.get(q) or {}
        items.append(
            {
                "qid": q,
                "title": it.get("title") or q,
                "artist": it.get("artist") or "",
                "thumbnail": it.get("thumbnail"),
                "location": locs.get(q),
            }
        )
    user = _caller(db, credentials)
    return {"items": items, **progress(db, str(user.id) if user else None, slug)}


@router.get("/{slug}/objects/{qid}/content")
def object_content(
    slug: str,
    qid: str,
    background_tasks: BackgroundTasks,
    request: Request,
    language: str = "zh",
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> dict:
    """展品讲解（按 tab 分节返回）。stub 首次访问触发懒生成（后台,契约§路线图3c）。
    ⚠️ 顺序:先 maybe_trigger 上锁、再读内容——否则首次触发的那次请求会返回
    generating=false（锁尚未落库）,前端渲染"待完善"完整页且不轮询,永不刷新。

    ⚠️ **读内容公开，但点燃付费生成要身份**（2026-09-20 安全审计）。
    `maybe_trigger` 下游是真金白银的 LLM 调用,而本端点无鉴权、无限流,
    qid 又能从同样匿名的 `/objects` 列表枚举 —— prod 有 26,556 件 stub,
    等于一条任何人都能打开的水龙头,烧的还不只是钱:按接地闸的外观描写盲区,
    规模化生成冷门件会把大量脑补内容**永久**写进库。

    匿名照常拿到已有内容(探索页不带令牌是正常形态,游客也持 `/auth/guest` 发的
    令牌),只是不点火。副产品:将来的公开网页层 `/a/{slug}/{qid}` 天然不点火。
    """
    from app.services.enrichment.lazy import imageless_stub, maybe_trigger

    if _hidden(db, credentials, slug, qid):
        raise HTTPException(status_code=404, detail=f"object not found: {qid}")
    reason = None
    user = _caller(db, credentials)
    if user is not None:
        reason = maybe_trigger(
            db,
            qid,
            schedule=background_tasks.add_task,
            language=language,
            user_id=str(user.id),
            # ProxyHeadersMiddleware(main.py)已把它解析成真实客户端 IP
            ip=request.client.host if request.client else None,
            exempt=bool(getattr(user, "can_preview", False)),
            # 身份不明按游客,走更严的那一档(与 _charge 的默认一致)
            is_guest=bool(getattr(user, "is_guest", True)),
        )
    data = get_object_content(db, slug, qid, language)
    if data is None:
        raise HTTPException(status_code=404, detail=f"object not found: {qid}")
    if user is None and data["status"] == "empty":
        # 匿名不点火,但无图 stub 也要告诉 App 别给「重试」(方案 B)。
        # 只在没内容时才查,不给每次匿名浏览多一次往返。
        from app.models.museum_object import MuseumObject

        obj = db.query(MuseumObject).filter_by(qid=qid).one()
        if imageless_stub(db, obj):
            reason = "no_image"
    # 加法字段(2026-10-10):为什么没在生成。"daily_cap"=当日懒生成预算用尽;
    # "no_image"=无图作品不生成(2026-10-11 方案 B);null=无特别原因
    data["unavailable_reason"] = reason
    # 加法字段(2026-09-29 分享):null = 这件在这个语言下不可分享,App 不显示分享键
    data["share"] = share_info(db, slug, qid, language, data)
    return data


class ViewedRequest(BaseModel):
    # 讲解页入口:识别/搜索/馆藏列表/足迹/首页继续游览/分享链接
    from_: Literal["recognition", "search", "collection", "history", "home", "link"] = (
        Field(alias="from")
    )


@router.post("/{slug}/objects/{qid}/viewed", status_code=204)
def object_viewed(
    body: ViewedRequest,
    slug: str = Path(max_length=64),
    qid: str = Path(max_length=32),
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> Response:
    """App 进讲解页报一次 content_viewed(P3-14②,加法端点)。fire-and-forget 恒 204。
    不挂在 /content 上:生成中那个接口每 4s 轮询,会重复计数。"""
    from app.services.event_log import log_event

    user = _caller(db, credentials)
    log_event(
        db,
        "content_viewed",
        user_id=str(user.id) if user else None,
        museum_slug=slug,
        qid=qid,
        **{"from": body.from_},
    )
    return Response(status_code=204)


def _audio_engine(db: Session, qid: str, language: str, section: str, qa_sort=None):
    """上报时刻这段音频是哪个引擎录的。音频以后会被替换,事后再 join 会张冠李戴。
    查不到/出错 → None(埋点绝不报错)。artist_bio 不查(作者卡跨件共享,与作品无关)。"""
    from app.models.content import ObjectContentSection, ObjectSuggestedQuestion
    from app.models.museum_object import MuseumObject

    try:
        obj = db.query(MuseumObject.id).filter_by(qid=qid).first()
        if obj is None or section == "artist_bio":
            return None
        if section == "qa":
            row = (
                db.query(ObjectSuggestedQuestion.audio_engine)
                .filter_by(object_id=obj.id, language=language, sort=qa_sort)
                .first()
            )
        else:
            row = (
                db.query(ObjectContentSection.audio_engine)
                .filter_by(object_id=obj.id, language=language, section_code=section)
                .first()
            )
        return row[0] if row else None
    except Exception:
        logger.exception("audio engine lookup failed")
        return None


class PlayedRequest(BaseModel):
    language: str = Field(max_length=8)
    section: str = Field(max_length=32)
    qa_sort: int | None = None
    # 播放位置(秒,按音频时间,不受倍速影响)。上限 10 小时,挡住垃圾值
    played_s: float = Field(ge=0, le=36000)
    duration_s: float | None = Field(default=None, ge=0, le=36000)  # 流式拿不到总长
    end: Literal["pause", "complete", "switch", "exit"]
    # 一次「加载→收听」一个 id:暂停再续播会报多条,分析时按 session 取最大 played_s
    session: str | None = Field(default=None, max_length=36)


@router.post("/{slug}/objects/{qid}/played", status_code=204)
def object_played(
    body: PlayedRequest,
    slug: str = Path(max_length=64),
    qid: str = Path(max_length=32),
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> Response:
    """完播率埋点 audio_played(V78,加法端点)。fire-and-forget 恒 204。"""
    from app.services.event_log import log_event

    user = _caller(db, credentials)
    log_event(
        db,
        "audio_played",
        user_id=str(user.id) if user else None,
        museum_slug=slug,
        qid=qid,
        **body.model_dump(),
        audio_engine=_audio_engine(db, qid, body.language, body.section, body.qa_sort),
    )
    return Response(status_code=204)


class RatedRequest(BaseModel):
    language: str = Field(max_length=8)
    value: Literal["up", "down"]


@router.post("/{slug}/objects/{qid}/rated", status_code=204)
def object_rated(
    body: RatedRequest,
    slug: str = Path(max_length=64),
    qid: str = Path(max_length=32),
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> Response:
    """讲解点赞/踩 content_rated(V78,加法端点)。fire-and-forget 恒 204。
    改主意会再报一条,分析时按人×件取最后一条。引擎取主讲解段的(评价挂在主讲解末尾)。"""
    from app.services.event_log import log_event

    user = _caller(db, credentials)
    log_event(
        db,
        "content_rated",
        user_id=str(user.id) if user else None,
        museum_slug=slug,
        qid=qid,
        language=body.language,
        value=body.value,
        audio_engine=_audio_engine(db, qid, body.language, "guide"),
    )
    return Response(status_code=204)


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

    _require_audio_access(db, credentials, qid, language=language, section=section)
    # 放在鉴权之后、TTS 之前:匿名对隐身馆和未知 qid 同样先吃 401,不泄漏差异
    if _hidden(db, credentials, slug, qid):
        raise HTTPException(status_code=404, detail={"reason": "no_published_text"})

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

    _require_audio_access(db, credentials, qid, language=language, section=section)
    # 放在鉴权之后、TTS 之前:匿名对隐身馆和未知 qid 同样先吃 401,不泄漏差异
    if _hidden(db, credentials, slug, qid):
        raise HTTPException(status_code=404, detail={"reason": "no_published_text"})

    try:
        status, payload = await stream_section_audio(qid, language, section)
    except Exception:
        logger.exception("TTS stream failed: %s/%s/%s", qid, language, section)
        raise HTTPException(status_code=503, detail={"reason": "tts_failed"})
    if status == "busy":
        raise HTTPException(status_code=409, detail={"reason": "audio_generating"})
    if status == "no_text":
        raise HTTPException(status_code=404, detail={"reason": "no_published_text"})
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
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> dict:
    """分页藏品列表（A2/A3 列表页）"""
    if _hidden(db, credentials, slug):
        raise HTTPException(status_code=404, detail=f"museum not found: {slug}")
    page = repo_list_objects(
        db,
        slug,
        language=language,
        category=category,
        sort=sort,
        limit=min(limit, MAX_PAGE_LIMIT),
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
    capture: Literal["camera", "gallery"] | None = None,
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
        capture=capture,
    )


@router.get("/{slug}")
def get_museum_pack(
    slug: str,
    language: str = "zh",
    artworks: bool = True,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> dict:
    """完整馆包：馆元数据 + 按热度排序的馆藏列表。

    `artworks=false` 省掉藏品数组(加法参数,缺省 true 保老 App 不变)——
    列表页走分页 /objects,门面只要 cover/categories/description。
    卢浮宫实测:全量 5.0MB/5.7s → 省掉后 KB 级。"""
    if _hidden(db, credentials, slug):
        raise HTTPException(status_code=404, detail=f"museum pack not found: {slug}")
    pack = repo_pack(
        db,
        slug,
        language,
        artworks=artworks,
        preview=can_preview(db, credentials),
    )
    if pack is None:
        raise HTTPException(status_code=404, detail=f"museum pack not found: {slug}")
    return pack
