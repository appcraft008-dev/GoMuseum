"""存量全库重扫:所有语言所有已发布段过语言一致性检测器,污染的清空重译(走翻译闸)。
幂等可重跑。staging 先跑,prod 待用户发话。"""

import sys

sys.path.insert(0, ".")


def rescan(db, slug, translator):
    from app.models.artist import Artist
    from app.models.content import ObjectContentSection, ObjectSuggestedQuestion
    from app.models.museum_object import MuseumObject
    from app.services.enrichment.backfill import translate_object_language
    from app.services.enrichment.lang_detect import text_in_language

    objs = (
        db.query(MuseumObject)
        .join(ObjectContentSection, ObjectContentSection.object_id == MuseumObject.id)
        .distinct()
        .all()
    )
    contaminated = 0  # 段落污染字段数
    bad_qa = 0  # 问答污染数
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
        # 问答污染也触发该语言重译(translate_object_language 重做段+问答+bio)
        for q in (
            db.query(ObjectSuggestedQuestion)
            .filter_by(object_id=o.id, status="published")
            .all()
        ):
            if q.language == "en":
                continue
            if (q.question and not text_in_language(q.question, q.language)) or (
                q.answer and not text_in_language(q.answer, q.language)
            ):
                bad_langs.add(q.language)
                bad_qa += 1
        for lang in bad_langs:
            # 清该语言段+问答 → 从 en 轴心重译(过语言闸,污染的落 needs_review)
            db.query(ObjectContentSection).filter_by(
                object_id=o.id, language=lang
            ).delete()
            db.query(ObjectSuggestedQuestion).filter_by(
                object_id=o.id, language=lang
            ).delete()
            db.commit()
            translate_object_language(db, o, lang, translator)
            db.commit()
            fixed_langs += 1
    # 作者 bio 污染:非en 从 clean en 重译;en 本身污染 → 报告(需材料重生成,走 generate)
    bad_bio_nonen = 0
    bad_bio_en = 0
    for a in db.query(Artist).all():
        bio = dict(a.bio or {})
        en_ok = bool(bio.get("en")) and text_in_language(bio["en"], "en")
        if bio.get("en") and not en_ok:
            bad_bio_en += 1
            continue  # en 坏 → 无干净轴心,报告待 generate 重生成
        for lang, txt in list(bio.items()):
            if lang == "en" or not txt:
                continue
            if not text_in_language(txt, lang) and en_ok:
                try:
                    bio[lang] = translator.translate_section(bio["en"], lang)
                    bad_bio_nonen += 1
                    # bio 变更 → 该语言旧音频失效
                    ba = dict(a.bio_audio or {})
                    ba.pop(lang, None)
                    a.bio_audio = ba
                except Exception:
                    pass
        if bio != (a.bio or {}):
            a.bio = bio
            db.commit()
    return {
        "contaminated_sections": contaminated,
        "bad_qa": bad_qa,
        "bad_bio_nonen_fixed": bad_bio_nonen,
        "bad_bio_en_report": bad_bio_en,
        "fixed_langs": fixed_langs,
    }


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
