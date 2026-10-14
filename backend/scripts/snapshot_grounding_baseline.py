"""存量划线快照(P1-9B spec §6):新写作要求上 prod 当天跑一次,存旧产物的指纹。

以后判断某段是不是旧写作要求的产物:id 在快照里且正文 sha 没变。
不靠 generated_at —— 修补脚本(如 fix_guide_museum_ending.py)走 _upsert_section 会刷新它,
内容却还是旧的。只读,不写库。

用法(prod 容器):
  python scripts/snapshot_grounding_baseline.py --out /tmp/grounding-baseline-<D>.json.gz
然后拷到宿主机 /opt/gomuseum/backups/。
"""

import argparse
import gzip
import hashlib
import json
import sys
from datetime import datetime, timezone

sys.path.insert(0, "/app")


def sha(text):
    return None if text is None else hashlib.sha256(text.encode("utf-8")).hexdigest()


def build_snapshot(db) -> dict:
    from app.models.content import ObjectContentSection, ObjectSuggestedQuestion
    from app.models.museum import Museum
    from app.models.museum_object import MuseumObject

    sections = [
        {
            "id": str(s.id),
            "qid": qid,
            "section": s.section_code,
            "generated_at": s.generated_at.isoformat() if s.generated_at else None,
            "sha": sha(s.body),
        }
        for s, qid in db.query(ObjectContentSection, MuseumObject.qid)
        .join(MuseumObject, MuseumObject.id == ObjectContentSection.object_id)
        .filter(
            ObjectContentSection.language == "en",
            ObjectContentSection.status == "published",
        )
        .order_by(MuseumObject.qid, ObjectContentSection.section_code)
    ]
    questions = [
        {
            "id": str(q.id),
            "qid": qid,
            "language": q.language,
            "sort": q.sort,
            "sha": sha(f"{q.question}\n{q.answer}"),
        }
        for q, qid in db.query(ObjectSuggestedQuestion, MuseumObject.qid)
        .join(MuseumObject, MuseumObject.id == ObjectSuggestedQuestion.object_id)
        .filter(ObjectSuggestedQuestion.status == "published")
        .order_by(
            MuseumObject.qid,
            ObjectSuggestedQuestion.language,
            ObjectSuggestedQuestion.sort,
        )
    ]
    museums = [
        {
            "slug": m.slug,
            "sha": {k: sha(v) for k, v in sorted((m.description_i18n or {}).items())},
        }
        for m in db.query(Museum).order_by(Museum.slug)
        if m.description_i18n
    ]
    return {"sections": sections, "questions": questions, "museums": museums}


def _session():
    from app.core.database import SessionLocal

    return SessionLocal()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    db = _session()
    try:
        doc = {"at": datetime.now(timezone.utc).isoformat(), **build_snapshot(db)}
    finally:
        db.close()
    with open(a.out, "wb") as f:
        f.write(gzip.compress(json.dumps(doc, ensure_ascii=False).encode("utf-8")))
    print(
        f"sections {len(doc['sections'])} questions {len(doc['questions'])} museums {len(doc['museums'])} → {a.out}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
