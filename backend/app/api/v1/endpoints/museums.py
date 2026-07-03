"""Museum pack endpoints

提供馆包数据（馆藏清单/元信息），数据由 DB 读取（Phase 5 改造）。
"""

import logging

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile
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
    """展品讲解（按 tab 分节返回）。stub 首次访问触发懒生成（后台,契约§路线图3c）"""
    data = get_object_content(db, slug, qid, language)
    if data is None:
        raise HTTPException(status_code=404, detail=f"object not found: {qid}")
    from app.services.enrichment.lazy import maybe_trigger

    maybe_trigger(db, qid, schedule=background_tasks.add_task, language=language)
    return data


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
async def recognize_artwork(
    slug: str,
    image: UploadFile = File(...),
    language: str = "zh",
    mode: str = "artwork",
    db: Session = Depends(get_db),
) -> dict:
    """拍照识别(接地:身份只来自目录命中;mode=label 为引导补拍的墙签纯转写)"""
    from app.services.recognition.service import recognize

    data = await image.read()
    out = recognize(db, slug, data, language=language, mode=mode)
    if out is None:
        raise HTTPException(status_code=404, detail=f"museum not found: {slug}")
    return out


@router.get("/{slug}")
def get_museum_pack(
    slug: str, language: str = "zh", db: Session = Depends(get_db)
) -> dict:
    """完整馆包：馆元数据 + 按热度排序的馆藏列表"""
    pack = repo_pack(db, slug, language)
    if pack is None:
        raise HTTPException(status_code=404, detail=f"museum pack not found: {slug}")
    return pack
