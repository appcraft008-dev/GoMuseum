"""S5 识别照片自动分诊报告(沿用 feedback_report.py 惯例,不建后台)。

对 status=new 且仍存着照片的每一行,用**当前引擎**重跑这张照片:
- fixed_now     现在已经能认出答案(直判或候选第 1)→ 删图(已无诊断价值)
- no_reference  答案作品库里没有图(=没有向量,拍照不可能认出)→ 进补图队列
- real_failure  其余(含 not_found:用户最终没找到,没有答案)→ 进诊断集
附线索:模糊度(拉普拉斯方差,越小越糊)、过曝像素占比。只做线索,不当判据。
同一张照片可能有两行(found A、corrected B):复核时按 phash 取最新一行为准。

⚠️ 已知副作用:重跑 `recognize` 会照常写一条识别事件(engine 照实记)。不为它改识别服务签名。
重跑**绕过识别缓存**(否则同一张图会读回当时的旧结果,而不是当前引擎的判断)。

用法:docker exec gomuseum_prod_backend python scripts/recognition_photo_report.py [--dry-run]
  --dry-run 只打印报告,不写 triage/status、不删图。
"""

import argparse
import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def classify(answer_qid, rerun_out, answer_has_image) -> str:
    if answer_qid is None:
        return "real_failure"
    m = (rerun_out or {}).get("match") or {}
    cands = (rerun_out or {}).get("candidates") or []
    top = m.get("qid") or (cands[0].get("qid") if cands else None)
    if top == answer_qid:
        return "fixed_now"
    if not answer_has_image:
        return "no_reference"
    return "real_failure"


def clues(image_bytes: bytes) -> dict:
    """拉普拉斯方差(越小越糊)与过曝像素占比(灰度 ≥250)。只做线索,不当判据。"""
    import numpy as np
    from PIL import Image, ImageFilter

    g = Image.open(io.BytesIO(image_bytes)).convert("L")
    g.thumbnail((512, 512))
    lap = np.asarray(g.filter(ImageFilter.FIND_EDGES), dtype=float)
    arr = np.asarray(g)
    return {
        "blur": round(float(lap.var()), 1),
        "overexposed": round(float((arr >= 250).mean()), 3),
    }


class _NoCache:
    """恒不命中的缓存替身:分诊要的是**当前引擎**对这张图的判断,不是当时缓存下来的结果。"""

    def get(self, key):
        return None

    def set(self, *a, **k):
        return True  # 视为拿到在途锁,直接算

    def setex(self, *a, **k):
        pass

    def delete(self, *a, **k):
        pass


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    from app.core.database import SessionLocal
    from app.models.museum_object import MuseumObject, ObjectImage
    from app.models.recognition_photo_feedback import RecognitionPhotoFeedback as R
    from app.services.recognition.service import recognize
    from app.services.storage.photo_feedback import get_photo_feedback_storage

    store = get_photo_feedback_storage()
    if store is None:
        print("photo feedback bucket not configured; nothing to triage")
        return 0
    db = SessionLocal()
    groups: dict[str, list[str]] = {}
    try:
        rows = (
            db.query(R)
            .filter(R.status == "new", R.image_key.isnot(None))
            .order_by(R.created_at)
            .all()
        )
        for row in rows:
            data = store.get(row.image_key)
            if data is None:
                continue
            out = recognize(
                db, None, data, language=row.language or "en", redis=_NoCache()
            )
            has_img = (
                row.answer_qid is not None
                and db.query(ObjectImage)
                .join(MuseumObject, MuseumObject.id == ObjectImage.object_id)
                .filter(
                    MuseumObject.qid == row.answer_qid, ObjectImage.role == "primary"
                )
                .first()
                is not None
            )
            tri = classify(row.answer_qid, out, has_img)
            c = clues(data)
            link = None
            if not args.dry_run:
                row.triage = tri
                row.status = "triaged"
                if tri == "fixed_now":
                    store.delete(row.image_key)
                    row.image_key = None
            if row.image_key:
                link = store.presigned_url(row.image_key, expires=3600)
            groups.setdefault(tri, []).append(
                f"- `{row.created_at:%Y-%m-%d}` trigger={row.trigger} "
                f"answer={row.answer_qid} museum={row.museum_slug} "
                f"server={row.server_result} blur={c['blur']} "
                f"overexposed={c['overexposed']}"
                + (f" [photo]({link})" if link else "")
            )
        if not args.dry_run:
            db.commit()
    finally:
        db.close()

    print("# 识别照片分诊报告\n")
    for tri in ("real_failure", "no_reference", "fixed_now"):
        items = groups.get(tri, [])
        print(f"## {tri}({len(items)})\n")
        print("\n".join(items) or "(无)")
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
