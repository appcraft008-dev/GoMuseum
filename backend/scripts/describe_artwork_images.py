"""看藏品照片写外观描述,落 attributes.visual_description_en,供生成时当材料。

为什么需要(2026-09-13 实证):材料里没有视觉信息时,模型会编外观描写,
而接地闸**结构性抓不到** —— 它把「muted background」这类句子归成 IMPRESSION 放行。
机制、选型实证与反例都写在 `app/services/enrichment/vision.py` 的模块注释里。

与 discover_joconde_refs 同构:**发现一次、落库、永久复用**。
描述是这件作品的结构性属性,不该每次 generate 都重新看一遍图(那是重复付费)。

用法:
    python scripts/describe_artwork_images.py --museum petit_palais            # dry-run
    python scripts/describe_artwork_images.py --museum petit_palais --apply
    python scripts/describe_artwork_images.py --museum petit_palais --limit 10
    python scripts/describe_artwork_images.py --qid Q104444957 --apply
幂等:已有 visual_description_en 的件跳过。中断后重跑即续。
只处理**有本地图**(image_key 非空)的件;无图的件报出计数,不静默跳过。

跑完对这些件重新 generate(--force)才会用上新材料 —— 本脚本不碰
object_content_sections,也不动 audio_key。
"""

import argparse
import sys
import time

sys.path.insert(0, "/app")

from sqlalchemy.orm.attributes import flag_modified  # noqa: E402

from app.core.database import SessionLocal  # noqa: E402
from app.models.museum import Museum  # noqa: E402
from app.models.museum_object import MuseumObject, ObjectImage  # noqa: E402
from app.services.enrichment.vision import DETAIL, MODEL, describe_image  # noqa: E402
from app.services.storage import get_object_storage  # noqa: E402

_PAUSE = 0.2  # 礼貌限速
# 描述写进哪个键。前缀 `visual_description_` 会被 build_material 收进
# [VISIBLE IN THE ARTWORK] 块 —— 所以来源标记**不能**用同前缀,否则
# 「gpt-4o/high」会被当成材料喂给模型(见 tests 里钉这条的用例)。
_KEY = "visual_description_en"
_VIA_KEY = "visual_via"


def image_url_for(db, obj) -> str | None:
    """取这件的主图公网 URL(large 档)。没有本地图返回 None。

    按 sort 取第一张而不是挑 role=='primary':实测存量有 role 为 view 的
    单图件,挑 primary 会把它们整批判成"无图"。
    """
    img = (
        db.query(ObjectImage)
        .filter(ObjectImage.object_id == obj.id, ObjectImage.image_key.isnot(None))
        .order_by(ObjectImage.sort.asc().nullslast())
        .first()
    )
    if not img:
        return None
    return get_object_storage().public_url(f"{img.image_key}_large.jpg")


def main(slug, qid, apply, limit, model, detail):
    db = SessionLocal()
    try:
        q = db.query(MuseumObject)
        if qid:
            q = q.filter(MuseumObject.qid == qid)
        else:
            m = db.query(Museum).filter_by(slug=slug).one_or_none()
            if not m:
                raise SystemExit(f"❌ 未知馆: {slug}")
            q = q.filter(MuseumObject.museum_id == m.id).order_by(
                MuseumObject.popularity.desc()
            )
        objs = q.all()

        todo, no_image, already = [], 0, 0
        for o in objs:
            if (o.attributes or {}).get(_KEY):
                already += 1
                continue
            url = image_url_for(db, o)
            if not url:
                no_image += 1
                continue
            todo.append((o, url))
        if limit:
            todo = todo[:limit]

        print(
            f"{slug or qid}: 待描述 {len(todo)} 件"
            f"(已有描述 {already} 件跳过,无本地图 {no_image} 件做不了)"
        )
        print(f"模型 {model} / detail={detail}")

        done = 0
        for i, (o, url) in enumerate(todo, 1):
            text = describe_image(url, model=model, detail=detail)
            if apply:
                attrs = dict(o.attributes or {})
                attrs[_KEY] = text
                attrs[_VIA_KEY] = f"{model}/{detail}"
                o.attributes = attrs
                flag_modified(o, "attributes")
                db.commit()
            done += 1
            if i <= 2 or i % 50 == 0:
                print(f"  [{i}/{len(todo)}] {o.qid}: {text[:90]}…")
            time.sleep(_PAUSE)

        mode = "已写入" if apply else "dry-run(加 --apply 生效)"
        print(f"\n{mode}: 描述 {done} / {len(todo)} 件")
        if no_image:
            print(f"⚠️ {no_image} 件没有本地图,这条路帮不到它们(需另想办法)")
    finally:
        db.close()


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--museum", help="馆 slug")
    p.add_argument("--qid", help="只处理单件")
    p.add_argument("--apply", action="store_true")
    p.add_argument("--limit", type=int, help="只处理前 N 件(试跑)")
    p.add_argument("--model", default=MODEL)
    p.add_argument("--detail", default=DETAIL, choices=["high", "low"])
    a = p.parse_args()
    if not a.museum and not a.qid:
        raise SystemExit("❌ 需要 --museum 或 --qid")
    main(a.museum, a.qid, a.apply, a.limit, a.model, a.detail)
