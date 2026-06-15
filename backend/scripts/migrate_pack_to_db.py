# scripts/migrate_pack_to_db.py
"""把现有 museum_packs/<slug>.json 灌入 DB（幂等，复用 object_importer）。"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.core.database import SessionLocal
from app.services.object_importer import upsert_museum, upsert_object

PACK_DIR = Path(__file__).resolve().parents[1] / "museum_packs"


def migrate(slug: str):
    pack = json.loads((PACK_DIR / f"{slug}.json").read_text())
    db = SessionLocal()
    try:
        m = upsert_museum(db, pack)
        n = 0
        for art in pack["artworks"]:
            upsert_object(db, m.id, art)
            n += 1
        db.commit()
        print(f"✓ {slug}: 1 museum, {n} objects 入库")
    finally:
        db.close()


if __name__ == "__main__":
    migrate(sys.argv[1] if len(sys.argv) > 1 else "orsay")
