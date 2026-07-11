"""orsay 目录 → manifest.json(qid/popularity/category/图URL)。唯一碰 DB 的一步,只读。
在 VPS staging 容器内跑: python -m scripts.recognition_bench.export_manifest orsay。"""

from __future__ import annotations

import json
import sys

from app.models.museum import Museum
from app.models.museum_object import MuseumObject, ObjectImage
from app.services.museum_repo import _sized


def _storage():
    try:
        from app.services.storage import get_object_storage

        return get_object_storage()
    except Exception:
        return None  # 本地无 R2 配置时回退 source_url


def export_manifest(db, slug: str) -> dict:
    museum = db.query(Museum).filter_by(slug=slug).one()
    storage = _storage()
    objects = []
    rows = (
        db.query(MuseumObject)
        .filter_by(museum_id=museum.id)
        .order_by(MuseumObject.popularity.desc())
        .all()
    )
    for o in rows:
        if not o.qid:
            continue
        imgs = (
            db.query(ObjectImage)
            .filter_by(object_id=o.id)
            .order_by(ObjectImage.sort)
            .all()
        )
        urls = []
        for i in imgs:
            if i.image_key and storage:
                urls.append(_sized(storage, i.image_key, "large"))
            elif i.source_url:
                urls.append(i.source_url)
        if not urls:
            continue
        objects.append(
            {
                "qid": o.qid,
                "popularity": o.popularity or 0,
                "category": o.category,
                "title_en": o.title_en,
                "images": urls,
            }
        )
    return {"museum": slug, "objects": objects}


if __name__ == "__main__":
    from app.core.database import SessionLocal

    db = SessionLocal()
    try:
        print(json.dumps(export_manifest(db, sys.argv[1]), ensure_ascii=False))
    finally:
        db.close()
