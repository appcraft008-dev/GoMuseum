"""view 参考图相似度审查:用自家 DINOv2 引擎审查自家参考图。

Commons 分类混入习作/版画/无关照片(实测 14% 相似度<0.4,如 La Danse 0.27)——污染的
view 既毒化识别索引又脏详情页图集。对每个有 embedding 的 view,与同展品 primary 的
embedding 算余弦(向量已单位归一化 float32,点积即余弦),三段策略:
sim < delete_below → 删该 view 的 ObjectEmbedding + ObjectImage 行(不动 R2 文件);
delete_below ≤ sim < quarantine_below → role 改 view_quarantine + 删向量(出索引、出图集,
行保留可回溯);≥ quarantine_below → 保留。纯自动无人审(spec ④);错杀极端角度由照片
飞轮补回。容器内跑,幂等可重复。"""

from __future__ import annotations

import argparse

import numpy as np

from app.core.database import SessionLocal
from app.models.museum_object import MuseumObject, ObjectImage
from app.models.object_embedding import ObjectEmbedding
from app.services.recognition.embedder import MODEL_NAME


def vet_views(
    db,
    *,
    delete_below: float = 0.25,
    quarantine_below: float = 0.4,
    dry_run: bool = False,
) -> dict:
    """→ {"checked", "deleted", "quarantined"}。checked=有 primary+view 双向量、可判定的 view 数。"""
    view_embs = (
        db.query(ObjectImage, ObjectEmbedding)
        .join(ObjectEmbedding, ObjectEmbedding.image_id == ObjectImage.id)
        .filter(ObjectImage.role == "view", ObjectEmbedding.model == MODEL_NAME)
        .all()
    )
    checked = deleted = quarantined = 0
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
        if sim >= quarantine_below:
            continue
        o = db.query(MuseumObject).filter_by(id=img.object_id).first()
        label = (o.title_en or o.qid) if o else str(img.object_id)
        prefix = "[dry] " if dry_run else ""
        if sim < delete_below:
            print(f"{prefix}DELETE view sim={sim:.3f} {label}", flush=True)
            deleted += 1
            if not dry_run:
                db.delete(emb)
                db.delete(img)
        else:
            print(f"{prefix}QUARANTINE view sim={sim:.3f} {label}", flush=True)
            quarantined += 1
            if not dry_run:
                img.role = "view_quarantine"
                db.delete(emb)  # 出索引;行保留可回溯
        if not dry_run and (deleted + quarantined) % 20 == 0:
            db.commit()
    if not dry_run:
        db.commit()
    return {"checked": checked, "deleted": deleted, "quarantined": quarantined}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--delete-below", type=float, default=0.25)
    ap.add_argument("--quarantine-below", type=float, default=0.4)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    db = SessionLocal()
    res = vet_views(
        db,
        delete_below=args.delete_below,
        quarantine_below=args.quarantine_below,
        dry_run=args.dry_run,
    )
    verb = "would " if args.dry_run else ""
    print(
        f"DONE checked={res['checked']} {verb}deleted={res['deleted']} "
        f"{verb}quarantined={res['quarantined']} "
        f"(delete_below={args.delete_below} quarantine_below={args.quarantine_below})"
    )


if __name__ == "__main__":
    main()
