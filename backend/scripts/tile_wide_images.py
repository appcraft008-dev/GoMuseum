"""宽幅作品识别切块(见 app/services/recognition/tiles.py)。容器内跑,可重复(已有 tile 的件跳过)。

  python scripts/tile_wide_images.py orangerie --dry-run   # 只列会切哪些件
  python scripts/tile_wide_images.py orangerie

`onboard <slug> images` 物化完成后会自动调 tile_museum,新馆/新件无需单独跑。
写入面:object_images(新 tile 行)、object_embeddings(新向量)、R2 images/{qid}/tile-*。
不碰已有行,不动音频。
"""

from __future__ import annotations

import argparse
import io

import requests
from PIL import Image

from app.core.database import SessionLocal
from app.models.museum import Museum
from app.models.museum_object import MuseumObject, ObjectImage
from app.services.enrichment.materializer import _UA
from app.services.recognition.embedder import get_embedder
from app.services.recognition.embeddings import embed_image_row
from app.services.recognition.tiles import TILE_ROLE, add_tiles, tile_boxes
from app.services.storage import get_object_storage

_HIRES_PX = 3840  # Commons 缩略图上限;large 档只有 1600,9:1 的长卷切出来只剩 180px 高


def _hires(row: ObjectImage, storage) -> Image.Image:
    """优先 Commons 高清;非 Commons 源回落 R2 large 档。"""
    if row.source_url and "Special:FilePath" in row.source_url:
        r = requests.get(
            row.source_url.split("?")[0],
            params={"width": _HIRES_PX},
            headers={"User-Agent": _UA},
            timeout=120,
        )
        r.raise_for_status()
        return Image.open(io.BytesIO(r.content))
    return Image.open(io.BytesIO(storage.get(f"{row.image_key}_large.jpg")))


def tile_museum(slug: str, dry_run: bool = False) -> int:
    """给该馆尚未切块的宽幅作品切块,返回新增块数。onboard images 物化后自动调用。"""
    db, storage = SessionLocal(), get_object_storage()
    embedder = None if dry_run else get_embedder()
    if not dry_run and embedder is None:
        raise SystemExit("embedder unavailable (model not in R2?)")
    rows = (
        db.query(MuseumObject, ObjectImage)
        .join(Museum, Museum.id == MuseumObject.museum_id)
        .join(ObjectImage, ObjectImage.object_id == MuseumObject.id)
        .filter(
            Museum.slug == slug,
            MuseumObject.qid.isnot(None),
            ObjectImage.role == "primary",
            ObjectImage.image_key.isnot(None),
        )
        .order_by(MuseumObject.qid, ObjectImage.sort)
        .all()
    )
    tiled = {
        oid
        for (oid,) in db.query(ObjectImage.object_id).filter_by(role=TILE_ROLE).all()
    }
    seen, total = set(), 0
    try:
        for obj, img in rows:
            if obj.id in seen or obj.id in tiled:
                continue
            seen.add(obj.id)
            thumb = storage.get(f"{img.image_key}_thumb.jpg")
            if not thumb:
                continue
            w, h = Image.open(io.BytesIO(thumb)).size
            if not tile_boxes(w, h):
                continue
            print(f"{obj.qid} {w}x{h} {max(w, h) / min(w, h):.1f}:1 {obj.title_en}")
            if dry_run:
                continue
            try:
                n = add_tiles(
                    db,
                    storage,
                    obj,
                    _hires(img, storage),
                    img,
                    lambda db_, row, data: embed_image_row(db_, row, data, embedder),
                )
                db.commit()
                total += n
                print(f"  +{n} tiles", flush=True)
            except Exception as e:  # 单件失败不阻断,重跑会补
                db.rollback()
                print(f"  FAIL {e}", flush=True)
    finally:
        db.close()
    print(f"DONE scanned={len(seen)} tiles={total}")
    return total


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("slug")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    tile_museum(args.slug, args.dry_run)


if __name__ == "__main__":
    main()
