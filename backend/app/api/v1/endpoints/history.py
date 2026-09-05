"""足迹(用户识别历史)。

## 这套端点为什么被重写(2026-09-05)

原实现读 `recognition_results` 表 —— prod 上 **0 行**。唯一会写它的是老端点
`/api/v1/recognition/recognize`,而 App 从不调它(`recognizeArtwork` 用例在前端
全仓库零 UI 调用方)。App 真正走 `/api/v1/recognize`,落的是 `recognition_events`。
所以足迹 tab(底部四主 tab 之一)不是"数据少",是**结构上永远空**:用户点进去
只会看到「还没有足迹,去拍一张吧」,拍完回来还是这句。

现在读 `recognition_events`(该表随迁移 x1u0 有了 `user_id`),作品名/艺术家/缩略图
按 qid 从馆藏目录解析。

## 两条不许再破的纪律

1. **必须鉴权、必须按 user 过滤。** 重写前这四个端点**零鉴权**:prod 上匿名
   `GET /history/recent` 返回 200,`DELETE /history/{uuid}` 查得到就删。同一个用户
   标识既然进了表,读写就都得认人。
2. **`artwork_name`/`artist`/`period`/`description` 恒为字符串,永不 null。**
   已发布的 App 里 `HistoryItemModel.fromJson` 是裸 `as String` 强转
   (`json['artist'] as String`),给 null 会让老 App 的足迹页整页崩 —— 与
   2026-06-16 那次 `title_zh` 变 null 的事故同型。回退在后端做,不指望前端。
   `test_history.py::test_never_null_strings` 钉着这条。

响应形状保持老 `RecognitionResponse` 兼容,新增字段(`museum_slug`/`qid`/
`thumbnail`)是**加法** —— 老 App 忽略,新 App 才用得上 slug+qid 跳真讲解。
"""

import logging
import uuid
from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.museum_object import MuseumObject
from app.models.recognition_event import RecognitionEvent
from app.services.auth_service import AuthService

logger = logging.getLogger(__name__)

router = APIRouter()
security = HTTPBearer()


def _me(db: Session, credentials: HTTPAuthorizationCredentials) -> str:
    """当前用户 id。**从令牌取,绝不从查询参数取** —— 同 entitlements.py 的理由:
    足迹是个人数据,当成 query param 等于任何人都能读、能删别人的。"""
    return str(AuthService.get_current_user(db, credentials.credentials).id)


def _footprint_qid(ev: RecognitionEvent) -> Optional[str]:
    """这次识别到底看的是哪件 —— 没有把握就不算足迹。

    用户确认过(confirmed_qid)最可信;没确认过就只认 `outcome == "match"`。
    `candidates` 的 top_qid 是"还没定的几个猜测里分最高的那个",把它当成
    「你看过这件」是在替用户编经历。判据与 `coverage/display_state.py` 里
    那条展陈证据完全一致,别让两处漂开。"""
    if ev.confirmed_qid:
        return ev.confirmed_qid
    if ev.outcome == "match" and ev.top_qid:
        return ev.top_qid
    return None


def _mine(db: Session, user_id: str, *, since=None) -> List[RecognitionEvent]:
    """该用户可能算足迹的事件,新到旧。

    SQL 这层只做**粗筛超集**(有 qid 就捞回来),精确判据全部交给
    `_footprint_qid` 一处说了算。两处各写一遍"什么算足迹"是 bug 温床:
    先前版本就是这样,把 SQL 那份改错了行为却不变(另一份兜住了),
    等于错误被藏起来 —— 破坏性验证正是这么发现的。"""
    q = db.query(RecognitionEvent).filter(
        RecognitionEvent.user_id == user_id,
        or_(
            RecognitionEvent.confirmed_qid.isnot(None),
            RecognitionEvent.top_qid.isnot(None),
        ),
    )
    if since is not None:
        q = q.filter(RecognitionEvent.created_at >= since)
    return q.order_by(RecognitionEvent.created_at.desc()).all()


def _render(db, storage, ev: RecognitionEvent, obj: MuseumObject) -> dict:
    """一条足迹 → 响应体。四个字符串字段的回退在这里兜死(见模块 docstring 纪律 2)。"""
    from app.services.recognition.service import _summary

    lang = ev.language or "zh"
    s = _summary(db, storage, obj, lang)
    period = (obj.period_zh if lang.startswith("zh") else obj.period_en) or (
        obj.period_en or obj.period_zh
    )
    return {
        # id 是**事件** id,不是藏品 id —— DELETE /history/{id} 要用它
        "id": str(ev.id),
        # `_summary` 的 title 已带 i18n → en → zh → qid 四级回退,这里不再叠一层
        "artwork_name": s["title"],
        "artist": s["artist"] or "",
        "period": period or "",
        # 老字段。这里没有 AI 简介可填,给空串而不是 null(纪律 2)。
        "description": "",
        # top_score 可能为 None(确认回填的事件),也可能因引擎不同越界
        "confidence": min(max(ev.top_score or 0.0, 0.0), 1.0),
        "timestamp": ev.created_at,
        # —— 以下为加法字段,老 App 忽略 ——
        "museum_slug": ev.museum_slug or s["museum"],
        "qid": obj.qid,
        "thumbnail": s["thumbnail"],
    }


def _hydrate(db: Session, events: List[RecognitionEvent]) -> List[dict]:
    """批量把事件渲染成足迹,顺带丢掉目录里已查无此物的 qid。

    ponytail: qid→object 一次查回来(避免 N+1);`_summary` 内部每件仍会各查
    artist/image/museum 三次 —— 一页 20 条约 60 次轻查询,现在够用。真慢了
    再把 `_summary` 批量化,别提前造抽象。"""
    from app.services.storage import get_object_storage

    pairs = [(ev, _footprint_qid(ev)) for ev in events]
    qids = {q for _, q in pairs if q}
    if not qids:
        return []
    objs = {
        o.qid: o
        for o in db.query(MuseumObject).filter(MuseumObject.qid.in_(qids)).all()
    }
    storage = get_object_storage()
    return [_render(db, storage, ev, objs[q]) for ev, q in pairs if q and q in objs]


@router.get("/recent")
def get_recent_history(
    limit: int = Query(default=20, le=100, description="Maximum number of results"),
    offset: int = Query(default=0, ge=0, description="Number of results to skip"),
    days: Optional[int] = Query(default=None, description="Filter by last N days"),
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
) -> List[dict]:
    """我的足迹(新到旧)。

    只返回**当前令牌所属账号**的记录。x1u0 之前的老事件没有 user_id,
    因此谁也看不到 —— 足迹从这次上线后的新识别开始攒。
    """
    user_id = _me(db, credentials)
    since = datetime.utcnow() - timedelta(days=days) if days else None
    # 先渲染再切片:够不够格算足迹、藏品还在不在目录,都是 SQL 里判不了的,
    # 在 SQL 层分页会让每页少几条(甚至整页空)。足迹是几十到几百条量级,
    # ponytail: 上千条了再谈游标分页。
    items = _hydrate(db, _mine(db, user_id, since=since))
    return items[offset : offset + limit]


@router.get("/search")
def search_history(
    query: str = Query(..., min_length=2, description="Search query"),
    limit: int = Query(default=20, le=100),
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
) -> List[dict]:
    """在我的足迹里搜作品名/艺术家。

    ponytail: 在渲染结果上过滤,而不是拼 SQL —— 标题是多语言回退出来的
    (`title_i18n` → title_zh → title_en → qid),SQL 里根本没有"用户看到的那个名字"
    这一列可比。足迹是几十到几百条量级,先取回再筛完全够;上千条了再谈索引。
    """
    user_id = _me(db, credentials)
    needle = query.lower()
    hits = [
        r
        for r in _hydrate(db, _mine(db, user_id))
        if needle in r["artwork_name"].lower() or needle in r["artist"].lower()
    ]
    return hits[:limit]


@router.get("/stats")
def get_history_stats(
    days: Optional[int] = Query(default=30, description="Time period in days"),
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
):
    """我的足迹统计(近 N 天)。

    走的是和 `/recent` **同一条**渲染路径 —— 统计口径必须和用户屏幕上数得出来的
    条数一致,否则「12 件」配着 9 条列表,谁也说不清哪个错了。"""
    user_id = _me(db, credentials)
    cutoff = datetime.utcnow() - timedelta(days=days)
    items = _hydrate(db, _mine(db, user_id, since=cutoff))
    scores = [i["confidence"] for i in items if i["confidence"] > 0]
    return {
        "period_days": days,
        "total_recognitions": len(items),
        "unique_artworks": len({i["qid"] for i in items}),
        "museums_visited": len({i["museum_slug"] for i in items if i["museum_slug"]}),
        "average_confidence": round(sum(scores) / len(scores), 3) if scores else 0.0,
        "period_start": cutoff.isoformat(),
        "period_end": datetime.utcnow().isoformat(),
    }


@router.delete("/{event_id}")
def delete_history_item(
    event_id: str,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
):
    """从我的足迹里删掉一条。

    **删的是关联,不是行**:`user_id` 清成 NULL,事件行留下。同一行还兼着
    识别率 KPI 与展陈证据(`coverage/display_state.py` 按它判断某件是否在展),
    整行删掉等于用"删我的足迹"这个动作去改馆藏的在展判断。清掉 user_id 之后
    这条记录不再指向任何人,对用户而言就是删干净了。

    别人的记录一律 404(不是 403)—— 不确认"这个 id 存在但不是你的"。
    """
    user_id = _me(db, credentials)
    try:
        # 先解析成 UUID 对象:字符串比较在 UUID 列上直接抛错(SQLite AttributeError /
        # Postgres DataError),非 UUID 的路径也要走 404 而不是 500
        eid = uuid.UUID(event_id)
    except ValueError:
        ev = None
    else:
        ev = (
            db.query(RecognitionEvent)
            .filter(RecognitionEvent.id == eid, RecognitionEvent.user_id == user_id)
            .one_or_none()
        )
    if ev is None:
        raise HTTPException(
            status_code=404,
            detail={"error": "NotFound", "detail": f"footprint {event_id} not found"},
        )
    ev.user_id = None
    db.commit()
    return {"success": True, "message": f"footprint {event_id} removed"}
