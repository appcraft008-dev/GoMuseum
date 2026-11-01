"""存量 CC BY 图补署摄影师:`credit` 是作者本人的行,改署 Commons 上拍这张照片的人。

写入面:只有 object_images.credit;不碰图片、向量、内容、音频。默认 dry-run。
认不准的(`photo_author` 返回 None)不改,列在报告里给人看。

  python scripts/backfill_photo_credit.py --report /tmp/credit.json
  python scripts/backfill_photo_credit.py --apply --limit 10
"""

import argparse
import json
import sys
import time
from pathlib import Path
from urllib.parse import unquote

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.database import SessionLocal  # noqa: E402
from app.models.museum_object import MuseumObject, ObjectImage  # noqa: E402
from app.services.enrichment.materializer import (  # noqa: E402
    _UA,
    extmeta_fields,
    is_cc_by,
)
from app.services.matching.people import is_artist_credit  # noqa: E402
from app.services.museum_repo import artist_aliases_of  # noqa: E402

_API = "https://commons.wikimedia.org/w/api.php"
_BATCH = 40


def _title(source_url: str) -> str:
    return "File:" + unquote(source_url.rsplit("/", 1)[-1])


def fetch_fields(titles: list[str], get=requests.get) -> dict:
    """标题 → extmeta_fields。按批查 Commons;Commons 改写过的标题映射回原标题。"""
    out = {}
    for i in range(0, len(titles), _BATCH):
        batch = titles[i : i + _BATCH]
        r = get(
            _API,
            params={
                "action": "query",
                "titles": "|".join(batch),
                "prop": "imageinfo",
                "iiprop": "extmetadata|user",
                "format": "json",
                "formatversion": 2,
            },
            headers={"User-Agent": _UA},
            timeout=60,
        )
        r.raise_for_status()
        q = r.json()["query"]
        back = {n["to"]: n["from"] for n in q.get("normalized", [])}
        for p in q["pages"]:
            if p.get("imageinfo"):
                out[back.get(p["title"], p["title"])] = extmeta_fields(
                    p["imageinfo"][0]
                )
        time.sleep(1)
    return out


def plan(db, get=requests.get) -> tuple[list, list]:
    """(要改的 [(row, new_credit)], 认不准的行)。"""
    rows = (
        db.query(ObjectImage)
        .filter(
            ObjectImage.license.ilike("CC BY%"),
            ObjectImage.credit.isnot(None),
            ObjectImage.source_url.like("%Special:FilePath/%"),
        )
        .all()
    )
    objs = {}
    wrong = []
    for r in rows:
        o = objs.setdefault(r.object_id, db.get(MuseumObject, r.object_id))
        if is_cc_by(r.license) and is_artist_credit(r.credit, artist_aliases_of(db, o)):
            wrong.append(r)
    fields = fetch_fields(sorted({_title(r.source_url) for r in wrong}), get=get)
    change, unsure = [], []
    for r in wrong:
        author = (fields.get(_title(r.source_url)) or {}).get("photo_author")
        (change.append((r, author)) if author else unsure.append(r))
    return change, unsure


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--report", help="把改前改后写成 JSON")
    a = ap.parse_args()
    db = SessionLocal()
    try:
        change, unsure = plan(db)
        if a.limit:
            change = change[: a.limit]
        print(f"要改 {len(change)} 行,认不准 {len(unsure)} 行")
        if a.report:
            row = lambda r, new=None: {
                "source": r.source_url,
                "role": r.role,
                "license": r.license,
                "old": r.credit,
                "new": new,
            }
            Path(a.report).write_text(
                json.dumps(
                    {
                        "change": [row(r, n) for r, n in change],
                        "unsure": [row(r) for r in unsure],
                    },
                    ensure_ascii=False,
                    indent=1,
                )
            )
        if not a.apply:
            print("DRY-RUN")
            return
        for r, new in change:
            r.credit = new
        db.commit()
        print(f"已改 {len(change)} 行")
    finally:
        db.close()


if __name__ == "__main__":
    main()
