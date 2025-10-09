"""
Unit tests for TTS Service
Tests audio generation and storage for artwork explanations (Step 2)
Following TDD Red-Green-Refactor methodology
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch, mock_open
from uuid import uuid4
from datetime import datetime, timedelta
import os

from app.services.tts_service import TTSService
from app.schemas.tts import TTSRequest, TTSResponse, Voice
from app.core.exceptions import ServiceException


class TestTTSServiceInitialization:
    """Test TTS service initialization"""

    def test_init_stores_dependencies(self):
        """should_store_all_injected_dependencies"""
        # Arrange
        mock_cache_service = MagicMock()
        mock_storage_path = "/tmp/audio"

        # Act
        service = TTSService(
            cache_service=mock_cache_service,
            storage_path=mock_storage_path,
        )

        # Assert
        assert service.cache_service == mock_cache_service
        assert service.storage_path == mock_storage_path


class TestGenerateAudio:
    """Test TTS audio generation workflow"""

    @pytest.fixture
    def service_with_mocks(self):
        """Create TTSService with mocked dependencies"""
        mock_cache = MagicMock()
        storage_path = "/tmp/audio"

        service = TTSService(
            cache_service=mock_cache,
            storage_path=storage_path,
        )

        return service, mock_cache

    @pytest.mark.asyncio
    async def test_generate_audio_cache_hit(self, service_with_mocks):
        """should_return_cached_audio_when_cache_exists"""
        # Arrange
        service, mock_cache = service_with_mocks

        test_text = "The Mona Lisa is a portrait painting..."
        test_language = "en"
        test_voice = "alloy"
        cache_key = f"tts:{test_text[:50]}:{test_language}:{test_voice}"

        cached_data = {
            "id": str(uuid4()),
            "audio_url": "https://cdn.example.com/audio/abc123.mp3",
            "file_path": "/tmp/audio/abc123.mp3",
            "file_size_bytes": 45678,
            "duration_seconds": 15,
            "voice": test_voice,
            "model": "tts-1",
            "created_at": datetime.now().isoformat(),
        }

        mock_cache.get.return_value = cached_data

        # Act
        result = await service.generate_audio(
            text=test_text, language=test_language, voice=test_voice
        )

        # Assert
        mock_cache.get.assert_called_once()
        assert result.audio_url == cached_data["audio_url"]
        assert result.voice == test_voice
        assert result.cached is True

    @pytest.mark.asyncio
    async def test_generate_audio_openai_call(self, service_with_mocks):
        """should_call_openai_tts_api_when_no_cache"""
        # Arrange
        service, mock_cache = service_with_mocks

        test_text = "The Mona Lisa is a portrait painting by Leonardo da Vinci."
        test_language = "en"
        test_voice = "alloy"

        # Mock cache miss
        mock_cache.get.return_value = None

        # Mock OpenAI TTS API response
        mock_audio_content = b"fake_audio_data_12345"
        mock_response = MagicMock()
        mock_response.content = mock_audio_content

        # Mock file operations
        with patch("builtins.open", mock_open()) as mock_file, \
             patch("app.services.tts_service.AsyncOpenAI") as mock_openai_class, \
             patch("os.path.getsize", return_value=len(mock_audio_content)), \
             patch("os.makedirs"):

            mock_openai = MagicMock()
            mock_openai_class.return_value = mock_openai
            mock_openai.audio.speech.create = AsyncMock(return_value=mock_response)

            # Act
            result = await service.generate_audio(
                text=test_text, language=test_language, voice=test_voice
            )

            # Assert
            mock_openai.audio.speech.create.assert_called_once()
            call_kwargs = mock_openai.audio.speech.create.call_args.kwargs
            assert call_kwargs["input"] == test_text
            assert call_kwargs["voice"] == test_voice
            assert call_kwargs["model"] == "tts-1"

            assert result.voice == test_voice
            assert result.cached is False
            mock_cache.set.assert_called_once()  # Should cache the result

    @pytest.mark.asyncio
    async def test_generate_audio_unsupported_voice(self, service_with_mocks):
        """should_raise_exception_for_unsupported_voice"""
        # Arrange
        service, mock_cache = service_with_mocks

        # Act & Assert
        with pytest.raises(ServiceException) as exc_info:
            await service.generate_audio(
                text="Some text", language="en", voice="invalid_voice"
            )

        assert "not supported" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_generate_audio_empty_text(self, service_with_mocks):
        """should_raise_exception_for_empty_text"""
        # Arrange
        service, mock_cache = service_with_mocks

        # Act & Assert
        with pytest.raises(ServiceException) as exc_info:
            await service.generate_audio(text="", language="en", voice="alloy")

        assert "empty" in str(exc_info.value).lower() or "required" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_generate_audio_text_too_long(self, service_with_mocks):
        """should_raise_exception_for_text_exceeding_limit"""
        # Arrange
        service, mock_cache = service_with_mocks

        # Create text longer than 4096 characters (OpenAI TTS limit)
        long_text = "a" * 5000

        # Act & Assert
        with pytest.raises(ServiceException) as exc_info:
            await service.generate_audio(text=long_text, language="en", voice="alloy")

        assert "too long" in str(exc_info.value).lower() or "limit" in str(exc_info.value).lower()


class TestVoiceSelection:
    """Test voice selection for different languages"""

    @pytest.fixture
    def service(self):
        """Create minimal service"""
        return TTSService(
            cache_service=MagicMock(),
            storage_path="/tmp/audio",
        )

    def test_get_recommended_voice_for_language(self, service):
        """should_recommend_appropriate_voice_for_each_language"""
        # Test recommendations
        recommendations = {
            "en": "alloy",
            "fr": "echo",
            "de": "fable",
            "es": "nova",
            "it": "shimmer",
            "zh": "onyx",
        }

        for lang, expected_voice in recommendations.items():
            voice = service.get_recommended_voice(lang)
            assert voice in ["alloy", "echo", "fable", "onyx", "nova", "shimmer"]


class TestStorageAndURL:
    """Test audio file storage and URL generation"""

    @pytest.fixture
    def service(self):
        """Create minimal service"""
        return TTSService(
            cache_service=MagicMock(),
            storage_path="/tmp/audio",
        )

    def test_generate_file_path(self, service):
        """should_generate_unique_file_path_with_uuid"""
        # Act
        file_path1 = service._generate_file_path()
        file_path2 = service._generate_file_path()

        # Assert
        assert file_path1 != file_path2
        assert file_path1.endswith(".mp3")
        assert "/tmp/audio/" in file_path1

    def test_generate_cdn_url(self, service):
        """should_generate_cdn_url_from_file_path"""
        # Arrange
        file_path = "/tmp/audio/abc123.mp3"

        # Act
        url = service._generate_cdn_url(file_path)

        # Assert
        assert "abc123.mp3" in url
        assert url.startswith("http")


class TestCacheStrategy:
    """Test TTS cache behavior with 30-day TTL"""

    @pytest.fixture
    def service_with_mocks(self):
        """Create service with mocks"""
        mock_cache = MagicMock()
        service = TTSService(
            cache_service=mock_cache,
            storage_path="/tmp/audio",
        )
        return service, mock_cache

    @pytest.mark.asyncio
    async def test_cache_ttl_is_30_days(self, service_with_mocks):
        """should_cache_tts_results_with_30_day_ttl"""
        # Arrange
        service, mock_cache = service_with_mocks

        test_text = "Test audio content"
        mock_cache.get.return_value = None

        # Mock OpenAI and file operations
        with patch("app.services.tts_service.AsyncOpenAI") as mock_openai_class, \
             patch("builtins.open", mock_open()), \
             patch("os.path.getsize", return_value=1024), \
             patch("os.makedirs"):

            mock_openai = MagicMock()
            mock_openai_class.return_value = mock_openai
            mock_response = MagicMock()
            mock_response.content = b"audio_data"
            mock_openai.audio.speech.create = AsyncMock(return_value=mock_response)

            # Act
            await service.generate_audio(text=test_text, language="en", voice="alloy")

            # Assert
            mock_cache.set.assert_called_once()
            call_args = mock_cache.set.call_args
            ttl = call_args.kwargs.get("ttl") if call_args.kwargs else call_args[0][2]
            assert ttl == 2592000  # 30 days in seconds


class TestErrorHandling:
    """Test error handling for TTS operations"""

    @pytest.fixture
    def service_with_mocks(self):
        """Create service with mocks"""
        mock_cache = MagicMock()
        service = TTSService(
            cache_service=mock_cache,
            storage_path="/tmp/audio",
        )
        return service, mock_cache

    @pytest.mark.asyncio
    async def test_openai_api_failure_handling(self, service_with_mocks):
        """should_handle_openai_api_errors_gracefully"""
        # Arrange
        service, mock_cache = service_with_mocks

        mock_cache.get.return_value = None

        # Mock OpenAI API error
        with patch("app.services.tts_service.AsyncOpenAI") as mock_openai_class:
            mock_openai = MagicMock()
            mock_openai_class.return_value = mock_openai
            mock_openai.audio.speech.create = AsyncMock(
                side_effect=Exception("OpenAI API error")
            )

            # Act & Assert
            with pytest.raises(ServiceException) as exc_info:
                await service.generate_audio(
                    text="Test", language="en", voice="alloy"
                )

            assert "failed" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_storage_failure_handling(self, service_with_mocks):
        """should_handle_file_storage_errors"""
        # Arrange
        service, mock_cache = service_with_mocks

        mock_cache.get.return_value = None

        # Mock OpenAI success but file write failure
        with patch("app.services.tts_service.AsyncOpenAI") as mock_openai_class, \
             patch("builtins.open", side_effect=IOError("Disk full")):

            mock_openai = MagicMock()
            mock_openai_class.return_value = mock_openai
            mock_response = MagicMock()
            mock_response.content = b"audio_data"
            mock_openai.audio.speech.create = AsyncMock(return_value=mock_response)

            # Act & Assert
            with pytest.raises(ServiceException) as exc_info:
                await service.generate_audio(
                    text="Test", language="en", voice="alloy"
                )

            assert "storage" in str(exc_info.value).lower() or "failed" in str(exc_info.value).lower()
