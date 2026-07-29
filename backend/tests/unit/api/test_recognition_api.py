"""
Comprehensive Unit tests for Recognition API endpoints
Tests all recognition endpoints with full coverage
"""

import asyncio
from datetime import datetime
from io import BytesIO
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from fastapi import UploadFile
from fastapi.testclient import TestClient

from app.api.v1.endpoints.recognition import (
    get_recent_recognitions,
    get_recognition_result,
    get_recognition_service_dependency,
    get_recognition_stats,
    recognize_artwork,
    router,
)
from app.core.exceptions import (
    NotFoundException,
    ServiceException,
    TimeoutException,
    ValidationException,
)
from app.schemas.recognition import RecognitionResponse


class TestRecognitionServiceDependency:
    """Test recognition service dependency injection"""

    @patch("app.api.v1.endpoints.recognition.get_ai_service")
    @patch("app.api.v1.endpoints.recognition.CacheService")
    @patch("app.api.v1.endpoints.recognition.ImageService")
    @patch("app.api.v1.endpoints.recognition.RecognitionService")
    def test_get_recognition_service_dependency(
        self,
        mock_recognition_service,
        mock_image_service,
        mock_cache_service,
        mock_get_ai_service,
    ):
        """Test dependency injection creates proper service"""
        mock_db = MagicMock()
        mock_ai_service = MagicMock()
        mock_cache_service_instance = MagicMock()
        mock_image_service_instance = MagicMock()
        mock_recognition_service_instance = MagicMock()

        mock_get_ai_service.return_value = mock_ai_service
        mock_cache_service.return_value = mock_cache_service_instance
        mock_image_service.return_value = mock_image_service_instance
        mock_recognition_service.return_value = mock_recognition_service_instance

        result = get_recognition_service_dependency(mock_db)

        mock_get_ai_service.assert_called_once()
        mock_cache_service.assert_called_once()
        mock_image_service.assert_called_once()
        mock_recognition_service.assert_called_once_with(
            db=mock_db,
            ai_service=mock_ai_service,
            cache_service=mock_cache_service_instance,
            image_service=mock_image_service_instance,
        )
        assert result == mock_recognition_service_instance


class TestRecognizeArtworkEndpointRetired:
    """`/api/v1/recognition/recognize` 已下线(2026-07-28)。

    它是裸 GPT 猜测流:**不鉴权、不计费、不接地**,等于一条任何人都能无限调用、
    烧我们 GPT 额度的后门,同时绕过识别次数付费墙。交接文档 2026-07-03 就写明
    "违反接地原则,将下线"。前端早已改走计费路径 /api/v1/recognize。

    原先这里有 16 条用例测它的成功/异常/日志行为,随端点一并移除——
    留着会让"这个端点还该工作"这件事看起来仍然成立。
    """

    def test_retired_endpoint_returns_410_with_pointer(self):
        from fastapi.testclient import TestClient

        from app.main import app

        r = TestClient(app).post(
            "/api/v1/recognition/recognize",
            files={"image": ("a.jpg", b"x", "image/jpeg")},
        )
        assert r.status_code == 410, "下线端点不该还能识别"
        detail = r.json()["detail"]
        assert detail["reason"] == "endpoint_retired"
        assert detail["use"] == "POST /api/v1/recognize"
