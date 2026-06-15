# scripts/migrate_redis_explanations.py
"""把 Redis 里已生成的讲解永久落库到 object_content_section（无损：5 子字段→5 section）。
匹配展品：按 title_zh/title_en + 语言扫描所有展品，命中其讲解键则落库。"""
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.core.database import SessionLocal
from app.models.content import ObjectContentSection
from app.models.museum_object import MuseumObject
from app.services.content_cache import get_content_cache

# Redis payload 子字段 → section_code
FIELD_MAP = {
    "summary": "overview",
    "historical_context": "background",
    "artistic_analysis": "analysis",
    "cultural_significance": "significance",
}


def _facts_text(payload: dict) -> str | None:
    facts = payload.get("interesting_facts")
    if not facts:
        return None
    return "\n".join(f"- {f}" for f in facts)


def migrate(languages=("zh", "en")):
    cache = get_content_cache()
    if cache._redis is None:
        sys.exit(
            "ERROR: Redis 不可用，终止迁移（避免静默空跑）。检查 REDIS_HOST/REDIS_PORT。"
        )
    db = SessionLocal()
    written = 0
    try:
        for obj in db.query(MuseumObject).all():
            for lang in languages:
                title = obj.title_zh if lang == "zh" else obj.title_en
                artist = obj.artist_zh if lang == "zh" else obj.artist_en
                if not title:
                    continue
                payload = cache.get_explanation(title, artist or "", lang)
                if not payload:
                    continue
                sections = {sec: payload.get(field) for field, sec in FIELD_MAP.items()}
                sections["facts"] = _facts_text(payload)
                for code, body in sections.items():
                    if not body:
                        continue
                    existing = (
                        db.query(ObjectContentSection)
                        .filter_by(object_id=obj.id, language=lang, section_code=code)
                        .one_or_none()
                    )
                    row = existing or ObjectContentSection(
                        object_id=obj.id, language=lang, section_code=code
                    )
                    row.body = body
                    row.status = "published"
                    row.source = "ai_generated"
                    row.generated_at = row.generated_at or datetime.now(timezone.utc)
                    db.add(row)
                    written += 1
        db.commit()
        print(f"✓ 迁移落库 {written} 条讲解 section")
    finally:
        db.close()


if __name__ == "__main__":
    migrate()
