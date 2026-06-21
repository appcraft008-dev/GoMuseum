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


def get_section_audio_key(
    db: Session, qid: str, language: str, section_code: str
) -> str | None:
    """返回该 section 已落库的 audio_key；对象不存在/无行/无音频均返回 None。"""
    obj = db.query(MuseumObject).filter_by(qid=qid).one_or_none()
    if not obj:
        return None
    row = (
        db.query(ObjectContentSection)
        .filter_by(object_id=obj.id, language=language, section_code=section_code)
        .one_or_none()
    )
    return row.audio_key if row else None


def _upsert_section(db, obj, language, code, body, status, model):
    """查/建 (obj,lang,section) 行并赋值。供 persist_generated_sections / persist_gated_sections 复用。"""
    row = (
        db.query(ObjectContentSection)
        .filter_by(object_id=obj.id, language=language, section_code=code)
        .one_or_none()
    ) or ObjectContentSection(object_id=obj.id, language=language, section_code=code)
    row.body = body
    row.status = status
    row.source = "ai_generated"
    row.model = model
    row.generated_at = datetime.now(timezone.utc)
    db.add(row)


def persist_generated_sections(
    db: Session, qid: str, language: str, sections: dict, model: str | None = None
) -> int:
    """把生成的分段 body 落库（按 obj/lang/section upsert）。body 为 None/空的段不发布。返回发布数。"""
    obj = db.query(MuseumObject).filter_by(qid=qid).one_or_none()
    if not obj:
        return 0
    n = 0
    for code, body in sections.items():
        if not body:
            continue
        _upsert_section(db, obj, language, code, body, "published", model)
        n += 1
    db.commit()
    return n


def persist_gated_sections(
    db, qid: str, language: str, results: dict, model: str | None = None
):
    """把质量闸结果落库（按 obj/lang/section upsert）。published 与 needs_review 段都建行，
    body 可为 None（needs_review 占位）。返回 (published_count, needs_review_count)。未知 qid → (0,0)。
    """
    obj = db.query(MuseumObject).filter_by(qid=qid).one_or_none()
    if not obj:
        return (0, 0)
    pub = nr = 0
    for code, r in results.items():
        _upsert_section(db, obj, language, code, r.body, r.status, model)
        if r.status == "published":
            pub += 1
        else:
            nr += 1
    db.commit()
    return (pub, nr)
