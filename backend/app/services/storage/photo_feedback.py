"""S5 识别照片反馈的**私有**存储。

与 `get_object_storage()`(公开资产桶 gomuseum-assets)完全分开:独立桶、独立凭据、
不绑域名。public_url 对它没有意义,看图只走 presigned_url。"""

from app.core.config import settings

_instance = None


def get_photo_feedback_storage():
    """未配齐 → None(功能关闭)。"""
    global _instance
    if _instance is None:
        if not (
            settings.PHOTO_FEEDBACK_R2_BUCKET
            and settings.PHOTO_FEEDBACK_R2_ACCESS_KEY_ID
            and settings.PHOTO_FEEDBACK_R2_SECRET_ACCESS_KEY
            and settings.R2_ENDPOINT_URL
        ):
            return None
        from app.services.storage.r2 import R2ObjectStorage

        _instance = R2ObjectStorage(
            settings.R2_ENDPOINT_URL,
            settings.PHOTO_FEEDBACK_R2_ACCESS_KEY_ID,
            settings.PHOTO_FEEDBACK_R2_SECRET_ACCESS_KEY,
            settings.PHOTO_FEEDBACK_R2_BUCKET,
            "",  # 私有桶没有公开地址
        )
    return _instance


def photo_feedback_available() -> bool:
    """开关打开且私有桶已配。识别响应的 photo_feedback 字段、上传端点都看它。"""
    return (
        bool(settings.PHOTO_FEEDBACK_ENABLED)
        and get_photo_feedback_storage() is not None
    )
