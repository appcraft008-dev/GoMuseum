"""S5 识别照片生命周期(每日 cron):超过 90 天或 status=done → 删私有桶对象 + image_key 置空。

照片只当信号不当资产(spec §三⑬):最长 90 天、处理完即删(取先到)。行本身(不含图像的
元数据:分数/答案/归因)保留。单个对象删失败不中断,留着下次再删。

用法:docker exec gomuseum_prod_backend python scripts/purge_recognition_photos.py
"""

import logging
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import or_  # noqa: E402

from app.models.recognition_photo_feedback import (  # noqa: E402
    KEY_PREFIX,
    RETENTION_DAYS,
    RecognitionPhotoFeedback,
)

logger = logging.getLogger("purge_recognition_photos")


def purge(db, store, now=None) -> int:
    now = now or datetime.now(timezone.utc)
    cutoff = now - timedelta(days=RETENTION_DAYS)
    rows = (
        db.query(RecognitionPhotoFeedback)
        .filter(RecognitionPhotoFeedback.image_key.isnot(None))
        .filter(
            or_(
                RecognitionPhotoFeedback.created_at < cutoff,
                RecognitionPhotoFeedback.status == "done",
            )
        )
        .all()
    )
    n = 0
    for r in rows:
        try:
            store.delete(r.image_key)
        except Exception:
            logger.exception("delete failed, will retry next run: %s", r.image_key)
            continue
        r.image_key = None
        n += 1
    db.commit()
    # 孤儿兜底:桶写成功但库写失败(且补偿删除也失败)的对象没有行指向它,上面扫不到。
    # 超过保存期且无行引用 → 删。list_keys 不可用(测试替身/本地存储)就跳过。
    referenced = {
        k
        for (k,) in db.query(RecognitionPhotoFeedback.image_key).filter(
            RecognitionPhotoFeedback.image_key.isnot(None)
        )
    }
    try:
        listing = list(store.list_keys(KEY_PREFIX))
    except (AttributeError, NotImplementedError):
        listing = []  # 存储不支持枚举(测试替身/本地存储)
    except Exception:
        # 枚举失败(R2 抖动/限流):按行清理已提交,孤儿扫描今天跳过,明天再来
        logger.exception("orphan sweep listing failed; skipped this run")
        listing = []
    for key, _size, mtime in listing:
        if key in referenced:
            continue
        if mtime.tzinfo is None:
            mtime = mtime.replace(tzinfo=timezone.utc)
        if mtime < cutoff:
            try:
                store.delete(key)
                n += 1
            except Exception:
                logger.exception("orphan delete failed: %s", key)
    return n


def main() -> int:
    logging.basicConfig(level=logging.INFO)
    from app.core.database import SessionLocal
    from app.services.storage.photo_feedback import get_photo_feedback_storage

    store = get_photo_feedback_storage()
    if store is None:
        print("photo feedback bucket not configured; nothing to purge")
        return 0
    db = SessionLocal()
    try:
        n = purge(db, store)
    finally:
        db.close()
    print(f"purged {n} photo(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
