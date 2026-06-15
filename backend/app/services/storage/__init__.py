"""存储工厂：按 settings.STORAGE_BACKEND 返回单例 ObjectStorage。"""

from app.core.config import settings
from app.services.storage.base import ObjectStorage  # noqa: F401

_instance: ObjectStorage | None = None


def get_object_storage() -> ObjectStorage:
    global _instance
    if _instance is None:
        if settings.STORAGE_BACKEND == "r2":
            from app.services.storage.r2 import R2ObjectStorage

            _instance = R2ObjectStorage(
                settings.R2_ENDPOINT_URL,
                settings.R2_ACCESS_KEY_ID,
                settings.R2_SECRET_ACCESS_KEY,
                settings.R2_BUCKET,
                settings.R2_PUBLIC_BASE_URL,
            )
        else:
            from app.services.storage.local import LocalObjectStorage

            _instance = LocalObjectStorage(
                settings.STORAGE_LOCAL_DIR,
                settings.STORAGE_PUBLIC_BASE_URL,
            )
    return _instance
