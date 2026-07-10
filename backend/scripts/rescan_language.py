"""存量全库重扫:所有语言所有已发布段过语言一致性检测器,污染的清空重译(走翻译闸)。
幂等可重跑。staging 先跑,prod 待用户发话。"""

import sys

sys.path.insert(0, ".")


def rescan(db, slug, translator):
    from app.models.content import ObjectContentSection
    from app.models.museum_object import MuseumObject
    from app.services.enrichment.backfill import translate_object_language
    from app.services.enrichment.lang_detect import text_in_language

    objs = (
        db.query(MuseumObject)
        .join(ObjectContentSection, ObjectContentSection.object_id == MuseumObject.id)
        .distinct()
        .all()
    )
    contaminated = 0
    fixed_langs = 0
    for o in objs:
        bad_langs = set()
        for sec in (
            db.query(ObjectContentSection)
            .filter_by(object_id=o.id, status="published")
            .all()
        ):
            if sec.language != "en" and not text_in_language(
                sec.body or "", sec.language
            ):
                bad_langs.add(sec.language)
                contaminated += 1
        for lang in bad_langs:
            # 清该语言全部段 → 从 en 轴心重译(过语言闸,污染的落 needs_review)
            db.query(ObjectContentSection).filter_by(
                object_id=o.id, language=lang
            ).delete()
            db.commit()
            translate_object_language(db, o, lang, translator)
            db.commit()
            fixed_langs += 1
    return {"contaminated_sections": contaminated, "fixed_langs": fixed_langs}


if __name__ == "__main__":
    import argparse

    from app.core.database import SessionLocal
    from app.services.enrichment.factory import build_generation_components

    ap = argparse.ArgumentParser()
    ap.add_argument("slug")
    ap.add_argument("--target", choices=["staging", "prod"], required=True)
    ns = ap.parse_args()
    db = SessionLocal()
    c = build_generation_components(ns.slug)
    print(rescan(db, ns.slug, c["translator"]))
