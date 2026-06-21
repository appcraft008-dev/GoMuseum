"""内容质量报告（canary）：从 DB 已生成内容算覆盖率/needs_review%/缺音频。spec §8B。
接地分分布/源冲突需额外落库列（score/conflicts），属后续，本期不含。"""

from __future__ import annotations

from app.models.content import ObjectContentSection
from app.models.museum import Museum
from app.models.museum_object import MuseumObject


def build_quality_report(
    db, slug: str, languages: list[str], as_markdown: bool = False
):
    m = db.query(Museum).filter_by(slug=slug).one_or_none()
    if not m:
        return {"slug": slug, "error": "unknown museum"}

    obj_ids = [o.id for o in db.query(MuseumObject).filter_by(museum_id=m.id).all()]
    total = len(obj_ids)
    rows = (
        db.query(ObjectContentSection)
        .filter(ObjectContentSection.object_id.in_(obj_ids))
        .all()
        if obj_ids
        else []
    )

    per_lang = {}
    for lang in languages:
        lrows = [r for r in rows if r.language == lang]
        pub = sum(1 for r in lrows if r.status == "published")
        nr = sum(1 for r in lrows if r.status == "needs_review")
        covered = len({r.object_id for r in lrows if r.status == "published"})
        denom = pub + nr
        per_lang[lang] = {
            "published": pub,
            "needs_review": nr,
            "pct_needs_review": round(nr / denom, 3) if denom else 0.0,
            "objects_covered": covered,
            "coverage": round(covered / total, 3) if total else 0.0,
        }

    missing_audio = sum(1 for r in rows if r.status == "published" and not r.audio_key)
    rep = {
        "slug": slug,
        "objects_total": total,
        "languages": per_lang,
        "missing_audio": missing_audio,
    }
    return _to_markdown(rep) if as_markdown else rep


def _to_markdown(rep: dict) -> str:
    lines = [
        f"# 内容质量报告: {rep['slug']}",
        "",
        f"- 对象数: {rep['objects_total']}",
        f"- 已发布但缺音频: {rep['missing_audio']}",
        "",
        "## 各语言",
    ]
    for lang, s in rep["languages"].items():
        lines.append(
            f"- {lang}: 覆盖 {s['coverage']*100:.0f}% "
            f"({s['objects_covered']}/{rep['objects_total']}), "
            f"published {s['published']}, needs_review {s['needs_review']} "
            f"({s['pct_needs_review']*100:.0f}%)"
        )
    return "\n".join(lines)
