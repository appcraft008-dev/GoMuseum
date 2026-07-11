"""view 参考图相似度审查:用自家 DINOv2 引擎审查自家参考图。

Commons 分类混入习作/版画/无关照片(实测 14% 相似度<0.4,如 La Danse 0.27)——污染的
view 既毒化识别索引又脏详情页图集。对每个有 embedding 的 view,与同展品 primary 的
embedding 算余弦(向量已单位归一化 float32,点积即余弦);sim<阈值 → 删该 view 的
ObjectEmbedding + ObjectImage 行(不动 R2 文件)。容器内跑,幂等可重复。"""

from __future__ import annotations

import argparse

import numpy as np

from app.core.database import SessionLocal
from app.models.museum_object import MuseumObject, ObjectImage
from app.models.object_embedding import ObjectEmbedding
from app.services.recognition.embedder import MODEL_NAME


def vet_views(db, min_sim: float = 0.4, dry_run: bool = False) -> tuple[int, int]:
    """→ (checked, deleted)。checked=有 primary+view 双向量、可判定的 view 数。"""
    view_embs = (
        db.query(ObjectImage, ObjectEmbedding)
        .join(ObjectEmbedding, ObjectEmbedding.image_id == ObjectImage.id)
        .filter(ObjectImage.role == "view", ObjectEmbedding.model == MODEL_NAME)
        .all()
    )
    checked = deleted = 0
    for img, emb in view_embs:
        primary = (
            db.query(ObjectImage)
            .filter_by(object_id=img.object_id, role="primary")
            .order_by(ObjectImage.sort)
            .first()
        )
        if primary is None:
            continue
        pemb = (
            db.query(ObjectEmbedding)
            .filter_by(image_id=primary.id, model=MODEL_NAME)
            .first()
        )
        if pemb is None:
            continue
        checked += 1
        v = np.frombuffer(emb.vec, dtype=np.float32)
        p = np.frombuffer(pemb.vec, dtype=np.float32)
        sim = float(np.dot(v, p))
        if sim < min_sim:
            o = db.query(MuseumObject).filter_by(id=img.object_id).first()
            label = (o.title_en or o.qid) if o else str(img.object_id)
            prefix = "[dry] " if dry_run else ""
            print(f"{prefix}DELETE view sim={sim:.3f} {label}", flush=True)
            deleted += 1
            if not dry_run:
                db.delete(emb)
                db.delete(img)
                if deleted % 20 == 0:
                    db.commit()
    if not dry_run:
        db.commit()
    return checked, deleted


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--min-sim", type=float, default=0.4)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    db = SessionLocal()
    checked, deleted = vet_views(db, min_sim=args.min_sim, dry_run=args.dry_run)
    verb = "would delete" if args.dry_run else "deleted"
    print(f"DONE checked={checked} {verb}={deleted} (min_sim={args.min_sim})")


if __name__ == "__main__":
    main()
