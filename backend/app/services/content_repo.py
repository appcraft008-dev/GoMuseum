"""把一次生成的讲解（含 5 子字段）落库到 object_content_section（按 qid + 语言）。"""

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.content import ObjectContentSection
from app.models.museum_object import MuseumObject

FIELD_MAP = {
    "summary": "overview",
    "historical_context": "background",
    "artistic_analysis": "analysis",
    "cultural_significance": "significance",
}


def persist_explanation(
    db: Session, qid: str, language: str, payload: dict, model: str | None = None
) -> bool:
    obj = db.query(MuseumObject).filter_by(qid=qid).one_or_none()
    if not obj:
        return False
    sections = {sec: payload.get(field) for field, sec in FIELD_MAP.items()}
    facts = payload.get("interesting_facts")
    sections["facts"] = "\n".join(f"- {f}" for f in facts) if facts else None
    for code, body in sections.items():
        if not body:
            continue
        row = db.query(ObjectContentSection).filter_by(
            object_id=obj.id, language=language, section_code=code
        ).one_or_none() or ObjectContentSection(
            object_id=obj.id, language=language, section_code=code
        )
        row.body, row.status, row.source = body, "published", "ai_generated"
        row.model = model
        row.generated_at = datetime.now(timezone.utc)
        db.add(row)
    db.commit()
    return True
