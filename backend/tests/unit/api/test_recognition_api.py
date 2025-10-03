"""
Comprehensive Unit tests for Recognition API endpoints
Tests all recognition endpoints with full coverage
"""
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch, Mock
from fastapi.testclient import TestClient
from fastapi import UploadFile
from io import BytesIO
from datetime import datetime

from app.api.v1.endpoints.recognition import (
    router, 
    get_recognition_service_dependency,
    recognize_artwork,
    get_recognition_result,
    get_recognition_stats,
    get_recent_recognitions
)
from app.schemas.recognition import RecognitionResponse
from app.core.exceptions import ValidationException, ServiceException, TimeoutException, NotFoundException


class TestRecognitionServiceDependency:
    """Test recognition service dependency injection"""
    
    @patch('app.api.v1.endpoints.recognition.get_ai_service')
    @patch('app.api.v1.endpoints.recognition.CacheService')
    @patch('app.api.v1.endpoints.recognition.ImageService')
    @patch('app.api.v1.endpoints.recognition.RecognitionService')
    def test_get_recognition_service_dependency(
        self, mock_recognition_service, mock_image_service, 
        mock_cache_service, mock_get_ai_service
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


class TestRecognizeArtworkEndpoint:
    """Test the main recognition endpoint"""

    @pytest.mark.asyncio
    async def test_recognize_artwork_success(self):
        """Test successful artwork recognition"""
        # Mock UploadFile
        mock_image = MagicMock(spec=UploadFile)
        mock_image.filename = "artwork.jpg"
        mock_image.content_type = "image/jpeg"
        mock_image.read = AsyncMock(return_value=b"fake_image_data")
        
        # Mock service
        mock_service = MagicMock()
        mock_recognition_result = RecognitionResponse(
            id="test-id-123",
            artwork_name="Mona Lisa",
            artist="Leonardo da Vinci", 
            period="Renaissance",
            description="Famous portrait painting",
            confidence=0.95,
            timestamp=datetime.now(),
            cached=False,
            processing_time_ms=1500
        )
        mock_service.recognize_artwork = AsyncMock(return_value=mock_recognition_result)
        
        # Mock response object
        mock_response = MagicMock()
        mock_response.headers = {}
        
        # Call the endpoint
        result = await recognize_artwork(mock_image, mock_service, mock_response)
        
        # Verify calls
        mock_image.read.assert_called_once()
        mock_service.recognize_artwork.assert_called_once_with(b"fake_image_data")
        
        # Verify response
        assert result == mock_recognition_result
        assert mock_response.headers["X-Cache-Status"] == "MISS"

    @pytest.mark.asyncio
    async def test_recognize_artwork_invalid_content_type(self):
        """Test rejection of invalid image format"""
        mock_image = MagicMock(spec=UploadFile)
        mock_image.filename = "document.pdf"
        mock_image.content_type = "application/pdf"
        
        mock_service = MagicMock()
        mock_response = MagicMock()
        
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            await recognize_artwork(mock_image, mock_service, mock_response)
        
        assert exc_info.value.status_code == 400
        assert "ValidationError" in str(exc_info.value.detail)
        assert "Content-Type must be image/jpeg or image/png" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_recognize_artwork_content_type_validation_png(self):
        """Test that PNG format is accepted"""
        mock_image = MagicMock(spec=UploadFile)
        mock_image.filename = "artwork.png"
        mock_image.content_type = "image/png"
        mock_image.read = AsyncMock(return_value=b"fake_png_data")
        
        mock_service = MagicMock()
        mock_recognition_result = RecognitionResponse(
            id="test-id-456",
            artwork_name="Starry Night",
            artist="Vincent van Gogh",
            period="Post-Impressionism", 
            description="Famous night scene painting",
            confidence=0.92
        )
        mock_service.recognize_artwork = AsyncMock(return_value=mock_recognition_result)
        
        result = await recognize_artwork(mock_image, mock_service, None)
        assert result == mock_recognition_result

    @pytest.mark.asyncio
    async def test_recognize_artwork_validation_exception(self):
        """Test handling of ValidationException"""
        mock_image = MagicMock(spec=UploadFile)
        mock_image.filename = "artwork.jpg"
        mock_image.content_type = "image/jpeg"
        mock_image.read = AsyncMock(return_value=b"fake_image_data")
        
        mock_service = MagicMock()
        mock_service.recognize_artwork = AsyncMock(
            side_effect=ValidationException("Image is corrupted", detail="Invalid JPEG format")
        )
        
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            await recognize_artwork(mock_image, mock_service, None)
        
        assert exc_info.value.status_code == 400
        detail = exc_info.value.detail
        assert detail["error"] == "ValidationError"
        assert "Invalid JPEG format" in detail["detail"]

    @pytest.mark.asyncio
    async def test_recognize_artwork_timeout_exception(self):
        """Test handling of TimeoutException"""
        mock_image = MagicMock(spec=UploadFile)
        mock_image.filename = "artwork.jpg"
        mock_image.content_type = "image/jpeg"
        mock_image.read = AsyncMock(return_value=b"fake_image_data")
        
        mock_service = MagicMock()
        mock_service.recognize_artwork = AsyncMock(
            side_effect=TimeoutException("Recognition timed out", detail="AI service took too long")
        )
        
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            await recognize_artwork(mock_image, mock_service, None)
        
        assert exc_info.value.status_code == 504
        detail = exc_info.value.detail
        assert detail["error"] == "TimeoutError"
        assert "AI service took too long" in detail["detail"]

    @pytest.mark.asyncio
    async def test_recognize_artwork_service_exception(self):
        """Test handling of ServiceException"""
        mock_image = MagicMock(spec=UploadFile)
        mock_image.filename = "artwork.jpg"
        mock_image.content_type = "image/jpeg"
        mock_image.read = AsyncMock(return_value=b"fake_image_data")
        
        mock_service = MagicMock()
        mock_service.recognize_artwork = AsyncMock(
            side_effect=ServiceException("AI service unavailable", detail="OpenAI API down")
        )
        
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            await recognize_artwork(mock_image, mock_service, None)
        
        assert exc_info.value.status_code == 500
        detail = exc_info.value.detail
        assert detail["error"] == "ServiceError"
        assert "OpenAI API down" in detail["detail"]

    @pytest.mark.asyncio
    async def test_recognize_artwork_unexpected_exception(self):
        """Test handling of unexpected exceptions"""
        mock_image = MagicMock(spec=UploadFile)
        mock_image.filename = "artwork.jpg"
        mock_image.content_type = "image/jpeg"
        mock_image.read = AsyncMock(return_value=b"fake_image_data")
        
        mock_service = MagicMock()
        mock_service.recognize_artwork = AsyncMock(
            side_effect=Exception("Unexpected database error")
        )
        
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            await recognize_artwork(mock_image, mock_service, None)
        
        assert exc_info.value.status_code == 500
        detail = exc_info.value.detail
        assert detail["error"] == "InternalServerError"
        assert "Unexpected database error" in detail["detail"]

    @pytest.mark.asyncio
    @patch('app.api.v1.endpoints.recognition.logger')
    async def test_recognize_artwork_logging(self, mock_logger):
        """Test that proper logging occurs"""
        mock_image = MagicMock(spec=UploadFile)
        mock_image.filename = "artwork.jpg"
        mock_image.content_type = "image/jpeg"
        mock_image.read = AsyncMock(return_value=b"fake_image_data_123")
        
        mock_service = MagicMock()
        mock_recognition_result = RecognitionResponse(
            id="test-id-789",
            artwork_name="The Scream",
            artist="Edvard Munch",
            period="Expressionism",
            description="Famous expressionist painting",
            confidence=0.88
        )
        mock_service.recognize_artwork = AsyncMock(return_value=mock_recognition_result)
        
        await recognize_artwork(mock_image, mock_service, None)
        
        # Check logging calls
        assert mock_logger.info.call_count >= 3
        
        # Check specific log messages
        call_args_list = [call[0][0] for call in mock_logger.info.call_args_list]
        assert any("Received recognition request for file: artwork.jpg" in msg for msg in call_args_list)
        
        # 动态计算长度
        expected_len = len(b"fake_image_data_123")
        assert any(f"Read {expected_len} bytes from uploaded file" in msg for msg in call_args_list)
        
        assert any("Recognition successful: The Scream" in msg for msg in call_args_list)

    @pytest.mark.asyncio
    @patch('app.api.v1.endpoints.recognition.logger')
    async def test_recognize_artwork_validation_error_logging(self, mock_logger):
        """Test logging of validation errors"""
        mock_image = MagicMock(spec=UploadFile)
        mock_image.filename = "artwork.jpg"
        mock_image.content_type = "image/jpeg"
        mock_image.read = AsyncMock(return_value=b"fake_image_data")
        
        mock_service = MagicMock()
        mock_service.recognize_artwork = AsyncMock(
            side_effect=ValidationException("Test validation error")
        )
        
        from fastapi import HTTPException
        with pytest.raises(HTTPException):
            await recognize_artwork(mock_image, mock_service, None)
        
        mock_logger.warning.assert_called_once()
        warning_msg = mock_logger.warning.call_args[0][0]
        assert "Validation error: Test validation error" in warning_msg

    @pytest.mark.asyncio
    @patch('app.api.v1.endpoints.recognition.logger')
    async def test_recognize_artwork_timeout_error_logging(self, mock_logger):
        """Test logging of timeout errors"""
        mock_image = MagicMock(spec=UploadFile)
        mock_image.filename = "artwork.jpg"
        mock_image.content_type = "image/jpeg"
        mock_image.read = AsyncMock(return_value=b"fake_image_data")
        
        mock_service = MagicMock()
        mock_service.recognize_artwork = AsyncMock(
            side_effect=TimeoutException("Test timeout error")
        )
        
        from fastapi import HTTPException
        with pytest.raises(HTTPException):
            await recognize_artwork(mock_image, mock_service, None)
        
        mock_logger.error.assert_called()
        error_msg = mock_logger.error.call_args[0][0]
        assert "Timeout error: Test timeout error" in error_msg

    @pytest.mark.asyncio
    async def test_recognize_artwork_response_object_optional(self):
        """Test that response object is optional"""
        mock_image = MagicMock(spec=UploadFile)
        mock_image.filename = "artwork.jpg"
        mock_image.content_type = "image/jpeg"
        mock_image.read = AsyncMock(return_value=b"fake_image_data")
        
        mock_service = MagicMock()
        mock_recognition_result = RecognitionResponse(
            id="test-id-999",
            artwork_name="Test Artwork",
            artist="Test Artist",
            period="Test Period",
            description="Test description",
            confidence=0.75
        )
        mock_service.recognize_artwork = AsyncMock(return_value=mock_recognition_result)
        
        # Call without response object (None)
        result = await recognize_artwork(mock_image, mock_service, None)
        
        assert result == mock_recognition_result


# -------------------
# 其余 TestGetRecognitionResultEndpoint / TestGetRecognitionStatsEndpoint /
# TestGetRecentRecognitionsEndpoint / TestRecognitionAPILogger / TestRecognitionAPIRouter /
# TestIntegrationWithFastAPI / TestValidationExceptionDetail / TestEdgeCases
# 保持不变，直接沿用你当前文件里的内容即可
# -------------------
