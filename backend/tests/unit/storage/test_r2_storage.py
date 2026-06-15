import os
import uuid

import pytest

from app.core.config import settings


@pytest.mark.skipif(
    not (os.environ.get("RUN_R2_LIVE") and settings.R2_ACCESS_KEY_ID),
    reason="R2 实连测试默认跳过：需 RUN_R2_LIVE=1 且配置凭证（避免默认套件依赖外网/拖慢）",
)
def test_r2_roundtrip():
    from app.services.storage.r2 import R2ObjectStorage

    s = R2ObjectStorage(
        settings.R2_ENDPOINT_URL,
        settings.R2_ACCESS_KEY_ID,
        settings.R2_SECRET_ACCESS_KEY,
        settings.R2_BUCKET,
        settings.R2_PUBLIC_BASE_URL,
    )
    key = f"diagnostics/test_{uuid.uuid4().hex}.txt"
    assert s.exists(key) is False
    s.put(key, b"r2 ok", "text/plain")
    try:
        assert s.get(key) == b"r2 ok"
        assert s.exists(key) is True
    finally:
        s.delete(key)
    assert s.exists(key) is False
