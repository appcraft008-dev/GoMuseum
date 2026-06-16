"""把一次生成的讲解（含 5 子字段）落库到 object_content_section（按 qid + 语言）。"""

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.content import ObjectContentSection
from app.models.museum_object import MuseumObject
from app.services.storage.base import ObjectStorage

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
        existing = (
            db.query(ObjectContentSection)
            .filter_by(object_id=obj.id, language=language, section_code=code)
            .one_or_none()
        )
        row = existing or ObjectContentSection(
            object_id=obj.id, language=language, section_code=code
        )
        if existing is not None and existing.body != body:
            row.audio_key = None  # body 变更 → 旧音频失效，下次请求重生成
        row.body, row.status, row.source = body, "published", "ai_generated"
        row.model = model
        row.generated_at = datetime.now(timezone.utc)
        db.add(row)
    db.commit()
    return True


def persist_section_audio(
    db: Session,
    qid: str,
    language: str,
    section_code: str,
    audio_bytes: bytes,
    storage: ObjectStorage,
) -> str | None:
    """把一段已生成的音频落库：传 R2 + 写 object_content_sections.audio_key。

    返回 audio_key；qid 不存在返回 None。上传失败时异常上抛，绝不写 audio_key
    （避免指向缺失对象的悬空指针）。
    """
    obj = db.query(MuseumObject).filter_by(qid=qid).one_or_none()
    if not obj:
        return None
    key = f"object-audio/{qid}/{language}/{section_code}.mp3"
    storage.put(key, audio_bytes, "audio/mpeg")  # 失败则下方不执行，不写 key
    row = db.query(ObjectContentSection).filter_by(
        object_id=obj.id, language=language, section_code=section_code
    ).one_or_none() or ObjectContentSection(
        object_id=obj.id, language=language, section_code=section_code
    )
    row.audio_key = key
    db.add(row)
    db.commit()
    return key
