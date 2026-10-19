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
        rows = (
            db.query(MuseumObject)
            .filter_by(museum_id=museum_id, inventory_number=art["inventory_number"])
            .all()
        )
        # 同馆同号却是另一个 Wikidata 条目 = 另一件作品(奥赛油画/雕塑两套 RF 编号),
        # 不能并进那行,让调用方新建一行
        rows = [
            r
            for r in rows
            if not (_both_wikidata(r.qid, art.get("qid")) and r.qid != art["qid"])
        ]
        # 同号多件又没有 qid 可分辨 → 不猜
        return rows[0] if len(rows) == 1 else None
    return None


class InventoryCollision(ValueError):
    pass


def _guard_renumber(db: Session, obj: MuseumObject, inv: str | None) -> None:
    """已有行不许改号改到同馆别的行占着的号上(唯一约束放开后由这里接手)。
    prod 实证:Wikidata 重复条目按 qid 命中 B 行、却带着 A 行的号。新行同号是 find_object
    判过的另一件作品,放行。load_stubs 的 SAVEPOINT 接住异常、跳过该件。"""
    if obj.id is None or not inv or inv == obj.inventory_number:
        return
    taken = (
        db.query(MuseumObject.id)
        .filter(
            MuseumObject.museum_id == obj.museum_id,
            MuseumObject.inventory_number == inv,
            MuseumObject.id != obj.id,
        )
        .first()
    )
    if taken:
        raise InventoryCollision(f"{obj.qid}: 馆藏号 {inv} 已被同馆另一行占用")


def _both_wikidata(a, b) -> bool:
    return bool(a and b and a.startswith("Q") and b.startswith("Q"))


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
    _guard_renumber(db, obj, art.get("inventory_number"))
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
    # 匹配别名是离线一次性生成的(scripts/add_match_aliases.py),重导入不能冲掉
    keep = {k: v for k, v in (obj.attributes or {}).items() if k == "match_aliases"}
    obj.attributes = {
        **keep,
        **{k: v for k, v in (art.get("attributes") or {}).items() if v is not None},
    }
    db.add(obj)
    db.flush()

    # 图：多角度列表(首张 primary,其余 view)按 (object, sort) 幂等;
    # 单图老调用方走 image 键(等价单元素列表;老 primary 行 sort=0 自然对齐)
    images = art.get("images") or ([art["image"]] if art.get("image") else [])
    for i, src in enumerate(images):
        if not src:
            continue
        img = db.query(ObjectImage).filter_by(
            object_id=obj.id, sort=i
        ).one_or_none() or ObjectImage(object_id=obj.id, sort=i)
        img.role = "primary" if i == 0 else "view"
        img.source_url = src.replace("http://", "https://")
        db.add(img)
    db.flush()
    return obj
