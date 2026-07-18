"""slim 裁剪:金样本规则保留 ~300-500 件,其余对象连子行删(embeddings→images/sections/qa)。
artists/museums/用户表不动;零 LLM;幂等。spec 2026-07-17-staging-lightweight §1。"""

import sys

sys.path.insert(0, ".")

TOP_PER_CATEGORY = 30
EDGE_ARTISTS = [
    "Georges Seurat",
    "Auguste Renoir",
    "Pierre-Auguste Renoir",
    "Henri de Toulouse-Lautrec",
]


def golden_ids(db) -> set:
    from app.models.museum_object import MuseumObject, ObjectImage

    keep: set = set()

    def add(rows):
        keep.update(oid for (oid,) in rows)

    for (cat,) in db.query(MuseumObject.category).distinct():
        if not cat:
            continue
        add(
            db.query(MuseumObject.id)
            .filter_by(category=cat)
            .order_by(MuseumObject.popularity.desc().nullslast(), MuseumObject.id)
            .limit(TOP_PER_CATEGORY)
        )
    # 合成 qid 带图(樱桃全保)
    add(
        db.query(MuseumObject.id)
        .filter(MuseumObject.qid.like("joconde-%"))
        .join(ObjectImage, ObjectImage.object_id == MuseumObject.id)
        .distinct()
    )
    # 合成 qid 文字层样本 30
    has_img = db.query(ObjectImage.object_id)
    add(
        db.query(MuseumObject.id)
        .filter(MuseumObject.qid.like("joconde-%"), ~MuseumObject.id.in_(has_img))
        .order_by(MuseumObject.id)
        .limit(30)
    )
    # 多视角(有 view 行)
    add(db.query(ObjectImage.object_id).filter(ObjectImage.role == "view").distinct())
    # 多音译作者件
    add(db.query(MuseumObject.id).filter(MuseumObject.artist_en.in_(EDGE_ARTISTS)))
    # 裸 stub 2 + empty 5
    add(
        db.query(MuseumObject.id)
        .filter((MuseumObject.title_en.is_(None)) | (MuseumObject.title_en == ""))
        .order_by(MuseumObject.id)
        .limit(2)
    )
    add(
        db.query(MuseumObject.id)
        .filter_by(content_status="empty")
        .order_by(MuseumObject.id)
        .limit(5)
    )
    return keep


def prune(db) -> dict:
    from app.models.content import ObjectContentSection, ObjectSuggestedQuestion
    from app.models.museum_object import MuseumObject, ObjectImage
    from app.models.object_embedding import ObjectEmbedding

    keep = golden_ids(db)
    total = db.query(MuseumObject.id).count()
    doomed = [oid for (oid,) in db.query(MuseumObject.id) if oid not in keep]
    for i in range(0, len(doomed), 500):  # 分批落盘(批处理纪律②)
        batch = doomed[i : i + 500]
        db.query(ObjectEmbedding).filter(ObjectEmbedding.object_id.in_(batch)).delete(
            synchronize_session=False
        )
        for model in (ObjectImage, ObjectContentSection, ObjectSuggestedQuestion):
            db.query(model).filter(model.object_id.in_(batch)).delete(
                synchronize_session=False
            )
        db.query(MuseumObject).filter(MuseumObject.id.in_(batch)).delete(
            synchronize_session=False
        )
        db.commit()
    return {
        "before": total,
        "deleted": len(doomed),
        "after": db.query(MuseumObject.id).count(),
    }


if __name__ == "__main__":
    import argparse

    from app.core.database import SessionLocal
    from app.models.museum_object import MuseumObject

    ap = argparse.ArgumentParser()
    ap.add_argument("--yes", action="store_true")
    ns = ap.parse_args()
    db = SessionLocal()
    keep_n = len(golden_ids(db))
    total_n = db.query(MuseumObject.id).count()
    print(f"金样本保留 {keep_n} / 总 {total_n},将删除 {total_n - keep_n} 件")
    if not ns.yes:
        raise SystemExit("预览模式:加 --yes 执行(破坏性)")
    print(prune(db))
