"""未收录需求记录(契约R5 需求自适应):同 (馆, phash) 幂等计数;墙签文字/候选有值则更新。"""

from __future__ import annotations

from app.models.recognition_demand import RecognitionDemand


def record_demand(
    db, slug: str, phash: str, *, label_text=None, candidates=None, language="zh"
) -> int:
    """记一次未收录需求,返回当前 hit_count。"""
    row = (
        db.query(RecognitionDemand)
        .filter_by(museum_slug=slug, phash=phash)
        .one_or_none()
    )
    if row is None:
        row = RecognitionDemand(
            museum_slug=slug,
            phash=phash,
            label_text=label_text,
            gpt_candidates=candidates,
            language=language,
        )
        db.add(row)
    else:
        row.hit_count = (row.hit_count or 1) + 1
        if label_text:
            row.label_text = label_text
        if candidates:
            row.gpt_candidates = candidates
    db.commit()
    return row.hit_count or 1
