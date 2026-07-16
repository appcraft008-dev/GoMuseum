"""把 CatalogSource 产的 StubRecord 列灌成 stub 对象（只元数据 + 路由信息）。
保留已有材料（不覆盖 attributes 里的 extract_* 等），不把已 ready 的件降级回 stub。
spec §6：列目录廉价批量，材料留生成时逐件抓。"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.museum_object import MuseumObject
from app.services.enrichment.catalog_source import StubRecord
from app.services.object_importer import find_object, upsert_museum, upsert_object
from app.services.recognition.matcher import normalize_inv


def filter_new_stubs(
    db: Session, museum_id, stubs: list[StubRecord]
) -> list[StubRecord]:
    """只留库里还没有的件(按归一化馆藏号 + Joconde ref/P347 去重)。
    补充源(如 Joconde)用:绝不覆盖既有 Wikidata 件的好数据,只补真正缺的。"""
    existing = (
        db.query(MuseumObject).filter_by(museum_id=museum_id).all() if museum_id else []
    )
    inv_set = {
        normalize_inv(o.inventory_number) for o in existing if o.inventory_number
    }
    p347_set = {
        (o.attributes or {}).get("external_ids", {}).get("P347") for o in existing
    }
    p347_set.discard(None)
    out = []
    for s in stubs:
        if s.inventory_number and normalize_inv(s.inventory_number) in inv_set:
            continue
        if s.external_ids.get("P347") and s.external_ids["P347"] in p347_set:
            continue
        out.append(s)
    return out


def load_stubs(db: Session, museum: dict, stubs: list[StubRecord]) -> dict:
    """StubRecord 列 → stub 对象。返回 {loaded, stub}。"""
    m = upsert_museum(db, museum)
    n_stub = 0
    for s in stubs:
        # 读既有材料，路由信息 merge 进去（不抹掉 extract_* 等已抓材料）
        existing = find_object(
            db, m.id, {"qid": s.qid, "inventory_number": s.inventory_number}
        )
        attrs = dict(existing.attributes or {}) if existing else {}
        attrs["external_ids"] = s.external_ids or {}
        attrs["wiki_titles"] = s.wiki_titles or {}
        if s.raw.get("p276_qid"):
            attrs["p276"] = s.raw["p276_qid"]
        art = {
            "qid": s.qid,
            "inventory_number": s.inventory_number,
            "title_en": s.title,
            "artist_en": s.artist,
            "year": s.year,
            "category": s.category,
            "popularity": s.popularity or 0,
            "image": s.image_url,
            "images": s.image_urls or ([s.image_url] if s.image_url else []),
            "attributes": attrs,
        }
        obj = upsert_object(db, m.id, art)
        if obj.content_status != "ready":
            obj.content_status = "stub"
            n_stub += 1
        db.add(obj)
    db.commit()
    return {"loaded": len(stubs), "stub": n_stub}
