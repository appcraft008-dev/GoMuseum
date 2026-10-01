"""一次性:嵌入存量参考图(image_key 非空且缺 MODEL_NAME 向量)。容器内跑,可重复。"""

from __future__ import annotations

import argparse

from app.core.database import SessionLocal
from app.models.museum_object import ObjectImage
from app.models.object_embedding import ObjectEmbedding
from app.services.recognition.embedder import MODEL_NAME, get_embedder
from app.services.recognition.embeddings import embed_image_row
from app.services.storage import get_object_storage


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()
    db, storage = SessionLocal(), get_object_storage()
    embedder = get_embedder()
    if embedder is None:
        raise SystemExit("embedder unavailable (model not in R2?)")
    done_ids = {
        r[0]
        for r in db.query(ObjectEmbedding.image_id).filter_by(model=MODEL_NAME).all()
    }
    # 换引擎补向量:别的模型已收录的图 = 已治理过的图库,原样补、不再过 view 闸
    # (闸门槛按旧模型标定,重跑会误删/误隔离),新引擎图库与旧引擎逐张一致。
    mirrored = {
        r[0]
        for r in db.query(ObjectEmbedding.image_id)
        .filter(ObjectEmbedding.model != MODEL_NAME)
        .all()
    }
    q = db.query(ObjectImage).filter(ObjectImage.image_key.isnot(None))
    # 跳过已嵌入(幂等可重跑);隔离图只在旧引擎收录过时才补(否则新引擎图库会混进被隔离的垃圾图)
    rows = [
        r
        for r in q.all()
        if r.id not in done_ids and (r.role != "view_quarantine" or r.id in mirrored)
    ]
    if args.limit:
        rows = rows[: args.limit]
    ok = fail = 0
    for i, row in enumerate(rows, 1):
        data = storage.get(f"{row.image_key}_large.jpg")
        vet = row.id not in mirrored
        if data and embed_image_row(db, row, data, embedder=embedder, vet=vet):
            ok += 1
        else:
            fail += 1
        if i % 20 == 0:
            db.commit()
            print(f"{i}/{len(rows)} ok={ok} fail={fail}", flush=True)
    db.commit()
    print(f"DONE {len(rows)} ok={ok} fail={fail}")


if __name__ == "__main__":
    main()
