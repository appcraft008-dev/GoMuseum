# app/services/object_importer.py
"""把一条馆/展品数据幂等 upsert 进库。匹配优先级：qid → (museum, inventory_number)。

注意：若一条数据既无 qid 又无 inventory_number，则无法定位既有行，每次都会插入新行。
来自 Wikidata 的数据总有 qid，故该情况只会出现在手工直接调用且剥离了两者时。
"""

import logging
import uuid

from sqlalchemy.orm import Session

from app.models.museum import Museum
from app.models.museum_object import MuseumObject, ObjectImage

logger = logging.getLogger(__name__)


def upsert_museum(db: Session, m: dict) -> Museum:
    obj = db.query(Museum).filter_by(slug=m["slug"]).one_or_none() or Museum(
        slug=m["slug"]
    )
    for k in ("qid", "name_zh", "name_en", "city_zh", "city_en", "country"):
        if m.get(k) is not None:
            setattr(obj, k, m[k])
    db.add(obj)
    db.flush()
    return obj


def find_object(db: Session, museum_id: uuid.UUID, art: dict) -> MuseumObject | None:
    if art.get("qid"):
        hit = db.query(MuseumObject).filter_by(qid=art["qid"]).one_or_none()
        if hit:
            return hit
    if art.get("inventory_number"):
        return (
            db.query(MuseumObject)
            .filter_by(museum_id=museum_id, inventory_number=art["inventory_number"])
            .one_or_none()
        )
    return None


def upsert_object(db: Session, museum_id: uuid.UUID, art: dict) -> MuseumObject:
    obj = find_object(db, museum_id, art) or MuseumObject(museum_id=museum_id)
    # 跨馆 qid 撞车保护：按 qid 命中了别馆的行时，不静默改其归属，仅告警（极少见，P195 通常单值）
    if obj.museum_id is not None and obj.museum_id != museum_id:
        logger.warning(
            "QID %s 已属于博物馆 %s，本次导入归属 %s——跳过归属改写",
            art.get("qid"),
            obj.museum_id,
            museum_id,
        )
    else:
        obj.museum_id = museum_id
    for k in (
        "qid",
        "inventory_number",
        "title_zh",
        "title_en",
        "artist_zh",
        "artist_en",
        "year",
        "period_zh",
        "period_en",
        "popularity",
    ):
        if art.get(k) is not None:
            setattr(obj, k, art[k])
    # category 只在显式提供时覆盖；新行由模型默认 "painting" 填充（避免把已有 sculpture 改回 painting）
    if art.get("category"):
        obj.category = art["category"]
    obj.attributes = {
        k: v for k, v in (art.get("attributes") or {}).items() if v is not None
    }
    db.add(obj)
    db.flush()

    # 主图：按 (object, role=primary) 幂等
    src = art.get("image")
    if src:
        img = db.query(ObjectImage).filter_by(
            object_id=obj.id, role="primary"
        ).one_or_none() or ObjectImage(object_id=obj.id, role="primary")
        img.source_url = src.replace("http://", "https://")
        db.add(img)
    db.flush()
    return obj
