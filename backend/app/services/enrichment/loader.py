from __future__ import annotations

from sqlalchemy.orm import Session

from app.services.object_importer import upsert_museum, upsert_object


def select_sample(
    objects: list[dict], sample_size: int, sample_qids: list[str]
) -> list[dict]:
    by_qid = {o["qid"]: o for o in objects}
    top = sorted(objects, key=lambda o: o.get("popularity", 0), reverse=True)[
        :sample_size
    ]
    chosen = {o["qid"]: o for o in top}
    for q in sample_qids:
        if q in by_qid:
            chosen[q] = by_qid[q]
    return list(chosen.values())


def load(db: Session, pack: dict, *, sample: bool) -> int:
    """把 pack 灌入 db。sample=True 只灌样本（pack["_sample"]={"size","qids"}）。返回入库数。"""
    museum = upsert_museum(db, pack["museum"])
    objects = pack["objects"]
    if sample:
        cfg = pack.get("_sample", {})
        objects = select_sample(objects, cfg.get("size", 30), cfg.get("qids", []))

    n = 0
    for art in objects:
        # upsert_object 期望 art["image"] 是 url 字符串；pack 里是 dict → 转换（浅拷贝不改 pack）
        art_in = dict(art)
        img = art_in.get("image")
        if isinstance(img, dict):
            art_in["image"] = img.get("source_url")
        obj = upsert_object(
            db, museum.id, art_in
        )  # 幂等 by qid，写 canonical+attributes+主图
        obj.sources = art.get(
            "sources", {}
        )  # 各源原始包入库；不碰 object_content_sections
        n += 1
    db.commit()
    return n
