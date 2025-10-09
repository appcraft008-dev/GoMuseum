"""
Unit tests for Explanation Service
Tests the core business logic for artwork explanation generation (Step 2)
Following TDD Red-Green-Refactor methodology
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4
from datetime import datetime

from app.services.explanation_service import ExplanationService
from app.schemas.explanation import ExplanationResponse, Language, DetailLevel
from app.models.explanation import Explanation
from app.core.exceptions import ServiceException, NotFoundException


class TestExplanationServiceInitialization:
    """Test explanation service initialization"""

    def test_init_stores_dependencies(self):
        """should_store_all_injected_dependencies"""
        # Arrange
        mock_db = MagicMock()
        mock_ai_service = MagicMock()
        mock_cache_service = MagicMock()
        mock_tts_service = MagicMock()

        # Act
        service = ExplanationService(
            db=mock_db,
            ai_service=mock_ai_service,
            cache_service=mock_cache_service,
            tts_service=mock_tts_service,
        )

        # Assert
        assert service.db == mock_db
        assert service.ai_service == mock_ai_service
        assert service.cache_service == mock_cache_service
        assert service.tts_service == mock_tts_service


class TestGenerateExplanation:
    """Test the main explanation generation workflow"""

    @pytest.fixture
    def service_with_mocks(self):
        """Create ExplanationService with all mocked dependencies"""
        mock_db = MagicMock()
        mock_ai_service = MagicMock()
        mock_cache_service = MagicMock()
        mock_tts_service = MagicMock()

        service = ExplanationService(
            db=mock_db,
            ai_service=mock_ai_service,
            cache_service=mock_cache_service,
            tts_service=mock_tts_service,
        )

        return service, mock_db, mock_ai_service, mock_cache_service, mock_tts_service

    @pytest.mark.asyncio
    async def test_generate_explanation_cache_hit(self, service_with_mocks):
        """should_return_cached_explanation_when_cache_exists"""
        # Arrange
        service, mock_db, mock_ai, mock_cache, mock_tts = service_with_mocks

        test_artwork = "Mona Lisa"
        test_language = "en"
        cache_key = f"explanation:{test_artwork}:{test_language}"

        cached_data = {
            "id": str(uuid4()),
            "artwork_name": test_artwork,
            "language": test_language,
            "content": "The Mona Lisa is a portrait painting...",
            "timestamp": datetime.now().isoformat(),
        }

        mock_cache.get.return_value = cached_data

        # Act
        result = await service.generate_explanation(
            artwork_name=test_artwork, language=test_language
        )

        # Assert
        mock_cache.get.assert_called_once_with(cache_key)
        assert result.artwork_name == test_artwork
        assert result.language == test_language
        assert result.cached is True
        mock_ai.recognize.assert_not_called()  # Should not call AI if cache hit

    @pytest.mark.asyncio
    async def test_generate_explanation_database_hit(self, service_with_mocks):
        """should_return_db_explanation_when_cache_miss_but_db_exists"""
        # Arrange
        service, mock_db, mock_ai, mock_cache, mock_tts = service_with_mocks

        test_artwork = "Mona Lisa"
        test_language = "en"

        # Mock cache miss
        mock_cache.get.return_value = None

        # Mock database hit
        db_result = MagicMock(spec=Explanation)
        db_result.id = uuid4()
        db_result.artwork_name = test_artwork
        db_result.language = test_language
        db_result.content = "The Mona Lisa is a portrait painting..."
        db_result.audio_url = None
        db_result.timestamp = datetime.now()

        mock_db.query.return_value.filter.return_value.first.return_value = db_result

        # Act
        result = await service.generate_explanation(
            artwork_name=test_artwork, language=test_language
        )

        # Assert
        assert result.artwork_name == test_artwork
        assert result.language == test_language
        mock_cache.set.assert_called_once()  # Should write to cache
        mock_ai.recognize.assert_not_called()  # Should not call AI if DB hit

    @pytest.mark.asyncio
    async def test_generate_explanation_ai_generation(self, service_with_mocks):
        """should_call_ai_service_when_no_cache_and_no_db"""
        # Arrange
        service, mock_db, mock_ai, mock_cache, mock_tts = service_with_mocks

        test_artwork = "Mona Lisa"
        test_language = "en"

        # Mock cache miss
        mock_cache.get.return_value = None

        # Mock database miss (initial query)
        # Use side_effect to support multiple calls: first None, then saved object
        saved_explanation = MagicMock(spec=Explanation)
        saved_explanation.id = uuid4()
        saved_explanation.artwork_name = test_artwork
        saved_explanation.language = test_language
        saved_explanation.content = "The Mona Lisa, painted by Leonardo da Vinci in the 16th century..."
        saved_explanation.timestamp = datetime.now()
        saved_explanation.audio_url = None
        saved_explanation.audio_duration_seconds = None

        mock_db.query.return_value.filter.return_value.first.side_effect = [None, saved_explanation]

        # Mock AI service
        ai_result = {
            "content": "The Mona Lisa, painted by Leonardo da Vinci in the 16th century...",
            "word_count": 50,
        }
        mock_ai.generate_content = AsyncMock(return_value=ai_result)

        # Mock database add/commit/refresh
        mock_db.add.return_value = None
        mock_db.commit.return_value = None
        mock_db.refresh.return_value = None

        # Act
        result = await service.generate_explanation(
            artwork_name=test_artwork, language=test_language, detail_level="standard"
        )

        # Assert
        mock_ai.generate_content.assert_called_once()
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()
        mock_cache.set.assert_called_once()  # Should write to cache
        assert result.artwork_name == test_artwork
        assert result.language == test_language

    @pytest.mark.asyncio
    async def test_generate_explanation_unsupported_language(self, service_with_mocks):
        """should_raise_exception_for_unsupported_language"""
        # Arrange
        service, mock_db, mock_ai, mock_cache, mock_tts = service_with_mocks

        # Act & Assert
        with pytest.raises(ServiceException) as exc_info:
            await service.generate_explanation(
                artwork_name="Mona Lisa", language="xx"  # Unsupported language
            )

        assert "not supported" in str(exc_info.value).lower()


class TestBuildPrompt:
    """Test prompt engineering for different languages and detail levels"""

    @pytest.fixture
    def service(self):
        """Create minimal service for prompt testing"""
        mock_db = MagicMock()
        mock_ai = MagicMock()
        mock_cache = MagicMock()

        return ExplanationService(
            db=mock_db,
            ai_service=mock_ai,
            cache_service=mock_cache,
        )

    def test_build_prompt_english_standard(self, service):
        """should_generate_correct_prompt_for_english_standard_level"""
        # Act
        prompt = service._build_prompt(
            artwork_name="Mona Lisa", language="en", detail_level="standard"
        )

        # Assert
        assert "Mona Lisa" in prompt
        assert "detailed explanation" in prompt.lower()
        assert isinstance(prompt, str)

    def test_build_prompt_chinese_brief(self, service):
        """should_generate_correct_prompt_for_chinese_brief_level"""
        # Act
        prompt = service._build_prompt(
            artwork_name="蒙娜丽莎", language="zh", detail_level="brief"
        )

        # Assert
        assert "蒙娜丽莎" in prompt
        assert "简要介绍" in prompt or "简短" in prompt
        assert isinstance(prompt, str)

    def test_build_prompt_with_recognition_context(self, service):
        """should_include_recognition_data_in_prompt_when_provided"""
        # Arrange
        recognition_data = {
            "artist": "Leonardo da Vinci",
            "period": "Renaissance",
            "description": "Portrait painting of a woman",
        }

        # Act
        prompt = service._build_prompt(
            artwork_name="Mona Lisa",
            language="en",
            detail_level="standard",
            recognition_data=recognition_data,
        )

        # Assert
        assert "Leonardo da Vinci" in prompt
        assert "Renaissance" in prompt


class TestGenerateContentHash:
    """Test content hash generation for deduplication"""

    @pytest.fixture
    def service(self):
        """Create minimal service"""
        return ExplanationService(
            db=MagicMock(), ai_service=MagicMock(), cache_service=MagicMock()
        )

    def test_generate_content_hash_consistent(self, service):
        """should_generate_same_hash_for_same_input"""
        # Act
        hash1 = service._generate_content_hash("Mona Lisa", "en")
        hash2 = service._generate_content_hash("Mona Lisa", "en")

        # Assert
        assert hash1 == hash2
        assert len(hash1) == 64  # SHA256 produces 64 hex characters

    def test_generate_content_hash_different_artwork(self, service):
        """should_generate_different_hash_for_different_artwork"""
        # Act
        hash1 = service._generate_content_hash("Mona Lisa", "en")
        hash2 = service._generate_content_hash("The Starry Night", "en")

        # Assert
        assert hash1 != hash2

    def test_generate_content_hash_different_language(self, service):
        """should_generate_different_hash_for_different_language"""
        # Act
        hash1 = service._generate_content_hash("Mona Lisa", "en")
        hash2 = service._generate_content_hash("Mona Lisa", "zh")

        # Assert
        assert hash1 != hash2


class TestCacheStrategyEdgeCases:
    """Test cache-related edge cases and error handling"""

    @pytest.fixture
    def service_with_mocks(self):
        """Create service with mocks"""
        mock_db = MagicMock()
        mock_ai = MagicMock()
        mock_cache = MagicMock()

        service = ExplanationService(
            db=mock_db, ai_service=mock_ai, cache_service=mock_cache
        )

        return service, mock_db, mock_ai, mock_cache

    @pytest.mark.asyncio
    async def test_cache_write_failure_does_not_break_flow(self, service_with_mocks):
        """should_continue_successfully_even_if_cache_write_fails"""
        # Arrange
        service, mock_db, mock_ai, mock_cache = service_with_mocks

        # Mock cache miss
        mock_cache.get.return_value = None

        # Mock database hit
        db_result = MagicMock(spec=Explanation)
        db_result.id = uuid4()
        db_result.artwork_name = "Mona Lisa"
        db_result.language = "en"
        db_result.content = "Content..."
        db_result.timestamp = datetime.now()

        mock_db.query.return_value.filter.return_value.first.return_value = db_result

        # Mock cache write failure
        mock_cache.set.side_effect = Exception("Redis connection error")

        # Act - Should not raise exception
        result = await service.generate_explanation(
            artwork_name="Mona Lisa", language="en"
        )

        # Assert
        assert result.artwork_name == "Mona Lisa"
        # Cache failure should be logged but not break the flow
