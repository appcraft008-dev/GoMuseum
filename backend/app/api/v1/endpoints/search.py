"""搜索端点(加法契约,识别机制的姊妹功能)。

- 全局(探索页):GET /api/v1/search —— 跨馆藏品 + 博物馆本身。
- 馆域(馆列表页):GET /api/v1/museums/{slug}/search —— 只搜当前馆藏品(无 museums 段)。

稳定契约 + 可替换引擎:用户可感知行为跨引擎不变;引擎(进程内→Meilisearch)可插拔。
无图 stub 照常出现(has_image=False),是文字可识别层的主入口。
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.museum import Museum
from app.services.search.inprocess import search as run_search
from app.services.storage import get_object_storage

router = APIRouter()


@router.get("/search")
def global_search(
    q: str = "", language: str = "zh", limit: int = 20, db: Session = Depends(get_db)
) -> dict:
    museums, objects = run_search(
        db, get_object_storage(), q, museum_id=None, language=language, limit=limit
    )
    return {"query": q, "museums": museums, "objects": objects}


@router.get("/museums/{slug}/search")
def museum_search(
    slug: str,
    q: str = "",
    language: str = "zh",
    limit: int = 20,
    db: Session = Depends(get_db),
) -> dict:
    m = db.query(Museum).filter_by(slug=slug).first()
    if not m:
        raise HTTPException(status_code=404, detail=f"museum not found: {slug}")
    _, objects = run_search(
        db, get_object_storage(), q, museum_id=m.id, language=language, limit=limit
    )
    return {"query": q, "objects": objects}
