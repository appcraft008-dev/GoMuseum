"""存量修:作者译名一致性重扫(交接 2026-07-17-artist-name-consistency-backend)。
检测:en 段提到作者(姓)而目标语段未含作者卡规范名(name_i18n)→ 视为译名分叉,
删该段(音频随行失效)→ translate_object_language 带 glossary 重译只补缺。
范围:音译型语言(zh/zh-hant/ja/ko);拉丁语系照抄原名,风险低不扫。
幂等可重跑。staging 先跑,prod 待用户发话。"""

import sys

sys.path.insert(0, ".")

TRANSLIT_LANGS = ["zh", "zh-hant", "ja", "ko"]


def _surname_en(artist_en):
    # ponytail: 姓=最后一个词("Georges Seurat"→"Seurat");复合姓带连字符天然保留
    parts = (artist_en or "").split()
    return parts[-1] if parts else None


def _canon_key(canon):
    # 规范名取"姓"段:全名"乔治·秀拉"/"ジョルジュ・スーラ"/"조르주 쇠라" → 末段
    # (正文常只称姓;含末段即视为一致)
    for sep in ("·", "・", " "):
        if sep in canon:
            return canon.split(sep)[-1].strip()
    return canon


def rescan(db, translator):
    from app.models.content import ObjectContentSection, ObjectSuggestedQuestion
    from app.models.museum_object import MuseumObject
    from app.services.enrichment.backfill import (
        artist_names_i18n,
        translate_object_language,
    )

    objs = (
        db.query(MuseumObject)
        .join(ObjectContentSection, ObjectContentSection.object_id == MuseumObject.id)
        .filter(MuseumObject.artist_en.isnot(None))
        .distinct()
        .all()
    )
    divergent_sections = 0
    divergent_qa = 0
    fixed_langs = 0
    for o in objs:
        surname = _surname_en(o.artist_en)
        names = artist_names_i18n(db, o)
        if not surname or not names:
            continue
        en_secs = {
            r.section_code: r.body
            for r in db.query(ObjectContentSection)
            .filter_by(object_id=o.id, language="en", status="published")
            .all()
            if r.body
        }
        en_qa = {
            r.sort: r
            for r in db.query(ObjectSuggestedQuestion)
            .filter_by(object_id=o.id, language="en", status="published")
            .all()
        }
        for lang in TRANSLIT_LANGS:
            canon = names.get(lang)
            if not canon:
                continue
            key = _canon_key(canon)
            bad = False
            for sec in (
                db.query(ObjectContentSection)
                .filter_by(object_id=o.id, language=lang, status="published")
                .all()
            ):
                en_body = en_secs.get(sec.section_code)
                # en 提作者姓、译文却不含规范名 → 分叉段,删掉待重译
                if en_body and surname in en_body and key not in (sec.body or ""):
                    db.delete(sec)
                    divergent_sections += 1
                    bad = True
            qa_bad = False
            for q in (
                db.query(ObjectSuggestedQuestion)
                .filter_by(object_id=o.id, language=lang, status="published")
                .all()
            ):
                en_row = en_qa.get(q.sort)
                if en_row is None:
                    continue
                en_txt = f"{en_row.question} {en_row.answer}"
                if surname in en_txt and key not in f"{q.question} {q.answer}":
                    divergent_qa += 1
                    qa_bad = True
            if qa_bad:
                # translate_object_language 的 QA 只在该语言问答整组缺失时重译 → 整组删
                db.query(ObjectSuggestedQuestion).filter_by(
                    object_id=o.id, language=lang
                ).delete()
                bad = True
            if bad:
                db.commit()
                translate_object_language(db, o, lang, translator)
                db.commit()
                fixed_langs += 1
    return {
        "divergent_sections": divergent_sections,
        "divergent_qa": divergent_qa,
        "fixed_langs": fixed_langs,
    }


if __name__ == "__main__":
    import argparse

    from app.core.database import SessionLocal
    from app.services.enrichment.factory import build_generation_components

    ap = argparse.ArgumentParser()
    ap.add_argument("slug")
    ap.add_argument("--target", choices=["staging", "prod"], required=True)
    ap.add_argument("--allow-full", action="store_true")  # staging 护栏逃生门
    ns = ap.parse_args()
    from scripts.ops_guard import staging_require_allow_full

    staging_require_allow_full(ns.target, ns.allow_full)
    db = SessionLocal()
    c = build_generation_components(ns.slug)
    print(rescan(db, c["translator"]))
