"""入库即嵌入(生成一次永久落库):补图/backfill 共用。失败只记日志不阻断主流程。"""

from __future__ import annotations

import io
import logging

from app.models.object_embedding import ObjectEmbedding
from app.services.recognition.embedder import MODEL_NAME, get_embedder

logger = logging.getLogger(__name__)

_UNSET = object()  # 区分"未传"(回退 get_embedder)与"显式 None"(不回退)


def embed_image_row(db, row, image_bytes: bytes, embedder=_UNSET) -> bool:
    if embedder is _UNSET:
        embedder = get_embedder()
    if embedder is None:
        return False
    try:
        existing = (
            db.query(ObjectEmbedding)
            .filter_by(image_id=row.id, model=MODEL_NAME)
            .one_or_none()
        )
        if existing is not None:
            return True  # 幂等:已有 (image_id, MODEL_NAME) 不重插
        from PIL import Image

        vec = embedder.embed(Image.open(io.BytesIO(image_bytes)))
        # view 入库闸:primary 已有向量时先算相似度再决定 删/隔离/入库。
        # 纯自动无人审(spec ④);错杀极端角度由照片飞轮补回。
        # primary 向量尚不存在 → 照常嵌入(后续 vet CLI 兜底)。
        if row.role == "view":
            import numpy as np

            from app.models.museum_object import ObjectImage

            primary = (
                db.query(ObjectImage)
                .filter_by(object_id=row.object_id, role="primary")
                .order_by(ObjectImage.sort)
                .first()
            )
            pemb = (
                db.query(ObjectEmbedding)
                .filter_by(image_id=primary.id, model=MODEL_NAME)
                .first()
                if primary is not None
                else None
            )
            if pemb is not None:
                sim = float(
                    np.dot(
                        vec.astype("float32"),
                        np.frombuffer(pemb.vec, dtype="float32"),
                    )
                )
                if sim < 0.25:
                    db.delete(row)
                    return False
                if sim < 0.4:
                    row.role = "view_quarantine"
                    return False
        db.add(
            ObjectEmbedding(
                object_id=row.object_id,
                image_id=row.id,
                model=MODEL_NAME,
                vec=vec.astype("float32").tobytes(),
            )
        )
        return True  # 不 commit:随调用方事务落盘
    except Exception:
        logger.exception("embed_image_row failed (image_id=%s)", row.id)
        return False
