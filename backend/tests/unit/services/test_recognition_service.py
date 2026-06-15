"""
Comprehensive Unit tests for Recognition Service
Tests the core business logic for artwork recognition workflow
"""

import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest

from app.core.exceptions import NotFoundException, ServiceException, ValidationException
from app.models.recognition_result import RecognitionResult
from app.schemas.recognition import RecognitionResponse
from app.services.recognition_service import RecognitionService, get_recognition_service


class TestRecognitionServiceInitialization:
    """Test recognition service initialization"""

    def test_init_stores_dependencies(self):
        """should_store_all_injected_dependencies"""
        # Arrange
        mock_db = MagicMock()
        mock_ai_service = MagicMock()
        mock_cache_service = MagicMock()
        mock_image_service = MagicMock()

        # Act
        service = RecognitionService(
            db=mock_db,
            ai_service=mock_ai_service,
            cache_service=mock_cache_service,
            image_service=mock_image_service,
        )

        # Assert
        assert service.db == mock_db
        assert service.ai_service == mock_ai_service
        assert service.cache_service == mock_cache_service
        assert service.image_service == mock_image_service


class TestRecognizeArtworkWorkflow:
    """Test the main recognition workflow"""

    @pytest.fixture
    def service_with_mocks(self):
        """Create RecognitionService with all mocked dependencies"""
        mock_db = MagicMock()
        mock_ai_service = MagicMock()
        mock_cache_service = MagicMock()
        mock_image_service = MagicMock()

        service = RecognitionService(
            db=mock_db,
            ai_service=mock_ai_service,
            cache_service=mock_cache_service,
            image_service=mock_image_service,
        )

        return service, mock_db, mock_ai_service, mock_cache_service, mock_image_service

    @pytest.mark.asyncio
    async def test_recognize_artwork_complete_flow_success(self, service_with_mocks):
        """should_execute_full_recognition_workflow_when_no_cache"""
        # Arrange
        service, mock_db, mock_ai, mock_cache, mock_image = service_with_mocks

        test_image_data = b"fake_image_bytes"
        test_hash = "abc123hash"
        test_phash = "0123456789abcdef"
        test_base64 = "base64_encoded_image"

        # Mock image service
        mock_image.validate_image.return_value = True
        mock_image.generate_hash.return_value = test_hash
        mock_image.generate_perceptual_hash.return_value = test_phash
        mock_image.to_base64.return_value = test_base64

        # Mock cache miss (both file hash and perceptual hash)
        mock_cache.get_cached_result.return_value = None
        mock_cache.get_similar_cached_result.return_value = None

        # Mock database miss
        mock_db.query.return_value.filter.return_value.first.return_value = None

        # Mock AI service
        ai_result = {
            "artwork_name": "Mona Lisa",
            "artist": "Leonardo da Vinci",
            "period": "Renaissance",
            "description": "Famous portrait",
            "confidence": 0.95,
        }
        mock_ai.recognize_with_timeout = AsyncMock(return_value=ai_result)

        # Create a mock RecognitionResult that will be added to the database
        saved_id = uuid4()
        mock_db_result = MagicMock(spec=RecognitionResult)
        mock_db_result.id = saved_id
        mock_db_result.image_hash = test_hash
        mock_db_result.artwork_name = ai_result["artwork_name"]
        mock_db_result.artist = ai_result["artist"]
        mock_db_result.period = ai_result["period"]
        mock_db_result.description = ai_result["description"]
        mock_db_result.confidence = ai_result["confidence"]
        mock_db_result.timestamp = datetime.now()

        # Mock RecognitionResponse.model_validate to return a proper response
        expected_response = RecognitionResponse(
            id=str(saved_id),
            artwork_name=ai_result["artwork_name"],
            artist=ai_result["artist"],
            period=ai_result["period"],
            description=ai_result["description"],
            confidence=ai_result["confidence"],
        )

        with patch.object(
            RecognitionResponse, "model_validate", return_value=expected_response
        ) as mock_validate:
            # Act
            result = await service.recognize_artwork(test_image_data)

            # Assert
            mock_image.validate_image.assert_called_once_with(test_image_data)
            mock_image.generate_hash.assert_called_once_with(test_image_data)
            mock_cache.get_cached_result.assert_called_once_with(test_hash)
            mock_ai.recognize_with_timeout.assert_called_once_with(test_base64)
            mock_db.add.assert_called_once()
            mock_db.commit.assert_called_once()
            mock_cache.cache_result.assert_called_once()
            mock_validate.assert_called_once()

            assert result.artwork_name == "Mona Lisa"

    @pytest.mark.asyncio
    async def test_recognize_artwork_cache_hit(self, service_with_mocks):
        """should_return_cached_result_without_calling_ai"""
        # Arrange
        service, mock_db, mock_ai, mock_cache, mock_image = service_with_mocks

        test_image_data = b"fake_image_bytes"
        test_hash = "abc123hash"

        mock_image.validate_image.return_value = True
        mock_image.generate_hash.return_value = test_hash

        # Mock cache hit
        cached_response = RecognitionResponse(
            id="cached-id-123",
            artwork_name="Starry Night",
            artist="Vincent van Gogh",
            period="Post-Impressionism",
            description="Night scene painting",
            confidence=0.92,
        )
        mock_cache.get_cached_result.return_value = cached_response

        # Act
        result = await service.recognize_artwork(test_image_data)

        # Assert
        assert result == cached_response
        mock_db.query.assert_not_called()
        mock_ai.recognize_with_timeout.assert_not_called()
        mock_db.add.assert_not_called()

    @pytest.mark.asyncio
    async def test_recognize_artwork_db_hit_cache_miss(self, service_with_mocks):
        """should_return_db_result_and_update_cache_when_cache_miss"""
        # Arrange
        service, mock_db, mock_ai, mock_cache, mock_image = service_with_mocks

        test_image_data = b"fake_image_bytes"
        test_hash = "abc123hash"
        test_phash = "fedcba9876543210"

        mock_image.validate_image.return_value = True
        mock_image.generate_hash.return_value = test_hash
        mock_image.generate_perceptual_hash.return_value = test_phash

        # Mock cache miss (both layers)
        mock_cache.get_cached_result.return_value = None
        mock_cache.get_similar_cached_result.return_value = None

        # Mock database hit - create a proper mock RecognitionResult
        db_id = uuid4()
        db_result = MagicMock(spec=RecognitionResult)
        db_result.id = db_id
        db_result.image_hash = test_hash
        db_result.artwork_name = "The Scream"
        db_result.artist = "Edvard Munch"
        db_result.period = "Expressionism"
        db_result.description = "Famous expressionist painting"
        db_result.confidence = 0.88
        db_result.timestamp = datetime.now()
        mock_db.query.return_value.filter.return_value.first.return_value = db_result

        # Mock RecognitionResponse.model_validate
        expected_response = RecognitionResponse(
            id=str(db_id),
            artwork_name="The Scream",
            artist="Edvard Munch",
            period="Expressionism",
            description="Famous expressionist painting",
            confidence=0.88,
        )

        with patch.object(
            RecognitionResponse, "model_validate", return_value=expected_response
        ):
            # Act
            result = await service.recognize_artwork(test_image_data)

            # Assert
            assert result.artwork_name == "The Scream"
            mock_ai.recognize_with_timeout.assert_not_called()
            mock_db.add.assert_not_called()
            mock_cache.cache_result.assert_called_once_with(
                test_hash, result, test_phash
            )

    @pytest.mark.asyncio
    async def test_recognize_artwork_validates_image_first(self, service_with_mocks):
        """should_validate_image_before_any_other_operation"""
        # Arrange
        service, mock_db, mock_ai, mock_cache, mock_image = service_with_mocks

        test_image_data = b"invalid_data"

        mock_image.validate_image.side_effect = ValidationException("Invalid image")

        # Act & Assert
        with pytest.raises(ServiceException) as exc_info:
            await service.recognize_artwork(test_image_data)

        # Verify validation was called first
        mock_image.validate_image.assert_called_once_with(test_image_data)
        # Verify other operations were not called
        mock_image.generate_hash.assert_not_called()
        mock_cache.get_cached_result.assert_not_called()
        mock_ai.recognize_with_timeout.assert_not_called()

    @pytest.mark.asyncio
    async def test_recognize_artwork_ai_timeout_handling(self, service_with_mocks):
        """should_rollback_db_and_raise_exception_on_ai_timeout"""
        # Arrange
        service, mock_db, mock_ai, mock_cache, mock_image = service_with_mocks

        test_image_data = b"fake_image_bytes"
        test_hash = "abc123hash"

        mock_image.validate_image.return_value = True
        mock_image.generate_hash.return_value = test_hash
        mock_image.to_base64.return_value = "base64_data"
        mock_cache.get_cached_result.return_value = None
        mock_db.query.return_value.filter.return_value.first.return_value = None

        # Mock AI timeout
        mock_ai.recognize_with_timeout = AsyncMock(
            side_effect=asyncio.TimeoutError("AI timeout")
        )

        # Act & Assert
        with pytest.raises(ServiceException):
            await service.recognize_artwork(test_image_data)

        mock_db.rollback.assert_called_once()

    @pytest.mark.asyncio
    async def test_recognize_artwork_ai_service_exception(self, service_with_mocks):
        """should_handle_ai_service_exceptions_gracefully"""
        # Arrange
        service, mock_db, mock_ai, mock_cache, mock_image = service_with_mocks

        test_image_data = b"fake_image_bytes"
        test_hash = "abc123hash"

        mock_image.validate_image.return_value = True
        mock_image.generate_hash.return_value = test_hash
        mock_image.to_base64.return_value = "base64_data"
        mock_cache.get_cached_result.return_value = None
        mock_db.query.return_value.filter.return_value.first.return_value = None

        # Mock AI service exception
        mock_ai.recognize_with_timeout = AsyncMock(
            side_effect=Exception("OpenAI API error")
        )

        # Act & Assert
        with pytest.raises(ServiceException) as exc_info:
            await service.recognize_artwork(test_image_data)

        assert "Recognition failed" in str(exc_info.value)
        mock_db.rollback.assert_called_once()

    @pytest.mark.asyncio
    async def test_recognize_artwork_saves_to_database(self, service_with_mocks):
        """should_persist_recognition_result_to_database"""
        # Arrange
        service, mock_db, mock_ai, mock_cache, mock_image = service_with_mocks

        test_image_data = b"fake_image_bytes"
        test_hash = "abc123hash"
        test_phash = "abc123perceptual"

        mock_image.validate_image.return_value = True
        mock_image.generate_hash.return_value = test_hash
        mock_image.generate_perceptual_hash.return_value = test_phash
        mock_image.to_base64.return_value = "base64_data"
        mock_cache.get_cached_result.return_value = None
        mock_cache.get_similar_cached_result.return_value = None
        mock_db.query.return_value.filter.return_value.first.return_value = None

        ai_result = {
            "artwork_name": "Guernica",
            "artist": "Pablo Picasso",
            "period": "Cubism",
            "description": "Anti-war painting",
            "confidence": 0.91,
        }
        mock_ai.recognize_with_timeout = AsyncMock(return_value=ai_result)

        # Mock RecognitionResponse.model_validate
        saved_id = uuid4()
        expected_response = RecognitionResponse(
            id=str(saved_id),
            artwork_name=ai_result["artwork_name"],
            artist=ai_result["artist"],
            period=ai_result["period"],
            description=ai_result["description"],
            confidence=ai_result["confidence"],
        )

        with patch.object(
            RecognitionResponse, "model_validate", return_value=expected_response
        ):
            # Act
            await service.recognize_artwork(test_image_data)

            # Assert
            mock_db.add.assert_called_once()
            added_model = mock_db.add.call_args[0][0]
            assert isinstance(added_model, RecognitionResult)
            assert added_model.image_hash == test_hash
            assert added_model.artwork_name == "Guernica"
            assert added_model.artist == "Pablo Picasso"

            mock_db.commit.assert_called_once()
            mock_db.refresh.assert_called_once()

    @pytest.mark.asyncio
    async def test_recognize_artwork_db_commit_failure(self, service_with_mocks):
        """should_rollback_on_database_commit_failure"""
        # Arrange
        service, mock_db, mock_ai, mock_cache, mock_image = service_with_mocks

        test_image_data = b"fake_image_bytes"

        mock_image.validate_image.return_value = True
        mock_image.generate_hash.return_value = "hash123"
        mock_image.to_base64.return_value = "base64"
        mock_cache.get_cached_result.return_value = None
        mock_db.query.return_value.filter.return_value.first.return_value = None

        ai_result = {
            "artwork_name": "Test",
            "artist": "Test Artist",
            "period": "Test",
            "description": "Test",
            "confidence": 0.5,
        }
        mock_ai.recognize_with_timeout = AsyncMock(return_value=ai_result)

        # Mock commit failure
        mock_db.commit.side_effect = Exception("DB commit failed")

        # Act & Assert
        with pytest.raises(ServiceException):
            await service.recognize_artwork(test_image_data)

        mock_db.rollback.assert_called_once()

    @pytest.mark.asyncio
    async def test_recognize_artwork_rollback_on_error(self, service_with_mocks):
        """should_always_rollback_database_on_any_exception"""
        # Arrange
        service, mock_db, mock_ai, mock_cache, mock_image = service_with_mocks

        test_image_data = b"fake_image_bytes"

        # Simulate any unexpected error
        mock_image.validate_image.side_effect = RuntimeError("Unexpected error")

        # Act & Assert
        with pytest.raises(ServiceException):
            await service.recognize_artwork(test_image_data)

        mock_db.rollback.assert_called_once()


class TestGetRecognitionById:
    """Test retrieval of recognition results by ID"""

    @pytest.fixture
    def service_with_mocks(self):
        """Create RecognitionService with mocked database"""
        mock_db = MagicMock()
        service = RecognitionService(
            db=mock_db,
            ai_service=MagicMock(),
            cache_service=MagicMock(),
            image_service=MagicMock(),
        )
        return service, mock_db

    def test_get_recognition_by_id_success(self, service_with_mocks):
        """should_return_recognition_response_when_found"""
        # Arrange
        service, mock_db = service_with_mocks

        test_id = uuid4()
        # Create a proper mock RecognitionResult
        db_result = MagicMock(spec=RecognitionResult)
        db_result.id = test_id
        db_result.image_hash = "hash123"
        db_result.artwork_name = "The Thinker"
        db_result.artist = "Auguste Rodin"
        db_result.period = "Modern"
        db_result.description = "Bronze sculpture"
        db_result.confidence = 0.89
        db_result.timestamp = datetime.now()
        mock_db.query.return_value.filter.return_value.first.return_value = db_result

        # Mock RecognitionResponse.model_validate
        expected_response = RecognitionResponse(
            id=str(test_id),
            artwork_name="The Thinker",
            artist="Auguste Rodin",
            period="Modern",
            description="Bronze sculpture",
            confidence=0.89,
        )

        with patch.object(
            RecognitionResponse, "model_validate", return_value=expected_response
        ):
            # Act
            result = service.get_recognition_by_id(str(test_id))

            # Assert
            assert isinstance(result, RecognitionResponse)
            assert result.artwork_name == "The Thinker"
            assert result.artist == "Auguste Rodin"

    def test_get_recognition_by_id_not_found(self, service_with_mocks):
        """should_raise_not_found_exception_when_id_does_not_exist"""
        # Arrange
        service, mock_db = service_with_mocks

        test_id = uuid4()
        mock_db.query.return_value.filter.return_value.first.return_value = None

        # Act & Assert
        with pytest.raises(NotFoundException) as exc_info:
            service.get_recognition_by_id(str(test_id))

        assert "not found" in str(exc_info.value).lower()

    def test_get_recognition_by_id_invalid_uuid(self, service_with_mocks):
        """should_raise_service_exception_for_invalid_uuid_format"""
        # Arrange
        service, mock_db = service_with_mocks

        invalid_id = "not-a-valid-uuid"

        # Act & Assert
        with pytest.raises(ServiceException) as exc_info:
            service.get_recognition_by_id(invalid_id)

        assert "Invalid recognition ID format" in str(exc_info.value)

    def test_get_recognition_by_id_database_error(self, service_with_mocks):
        """should_handle_database_query_errors"""
        # Arrange
        service, mock_db = service_with_mocks

        test_id = uuid4()
        mock_db.query.side_effect = Exception("Database connection lost")

        # Act & Assert
        with pytest.raises(ServiceException) as exc_info:
            service.get_recognition_by_id(str(test_id))

        assert "Failed to retrieve recognition result" in str(exc_info.value)


class TestGetRecentRecognitions:
    """Test retrieval of recent recognition results"""

    @pytest.fixture
    def service_with_mocks(self):
        """Create RecognitionService with mocked database"""
        mock_db = MagicMock()
        service = RecognitionService(
            db=mock_db,
            ai_service=MagicMock(),
            cache_service=MagicMock(),
            image_service=MagicMock(),
        )
        return service, mock_db

    def test_get_recent_recognitions_default_limit(self, service_with_mocks):
        """should_return_10_most_recent_results_by_default"""
        # Arrange
        service, mock_db = service_with_mocks

        # Create 15 mock results with proper timestamp
        now = datetime.now()
        mock_db_results = []
        for i in range(10):
            mock_result = MagicMock(spec=RecognitionResult)
            mock_result.id = uuid4()
            mock_result.image_hash = f"hash{i}"
            mock_result.artwork_name = f"Artwork {i}"
            mock_result.artist = f"Artist {i}"
            mock_result.period = "Period"
            mock_result.description = "Description"
            mock_result.confidence = 0.8
            mock_result.timestamp = now
            mock_db_results.append(mock_result)

        mock_db.query.return_value.order_by.return_value.limit.return_value.all.return_value = (
            mock_db_results
        )

        # Mock RecognitionResponse.model_validate for list comprehension
        def mock_validate(db_result):
            return RecognitionResponse(
                id=str(db_result.id),
                artwork_name=db_result.artwork_name,
                artist=db_result.artist,
                period=db_result.period,
                description=db_result.description,
                confidence=db_result.confidence,
            )

        with patch.object(
            RecognitionResponse, "model_validate", side_effect=mock_validate
        ):
            # Act
            results = service.get_recent_recognitions()

            # Assert
            assert len(results) == 10
            mock_db.query.return_value.order_by.return_value.limit.assert_called_with(
                10
            )

    def test_get_recent_recognitions_custom_limit(self, service_with_mocks):
        """should_respect_custom_limit_parameter"""
        # Arrange
        service, mock_db = service_with_mocks

        now = datetime.now()
        mock_db_results = []
        for i in range(5):
            mock_result = MagicMock(spec=RecognitionResult)
            mock_result.id = uuid4()
            mock_result.image_hash = f"hash{i}"
            mock_result.artwork_name = f"Artwork {i}"
            mock_result.artist = f"Artist {i}"
            mock_result.period = "Period"
            mock_result.description = "Description"
            mock_result.confidence = 0.8
            mock_result.timestamp = now
            mock_db_results.append(mock_result)

        mock_db.query.return_value.order_by.return_value.limit.return_value.all.return_value = (
            mock_db_results
        )

        # Mock RecognitionResponse.model_validate for list comprehension
        def mock_validate(db_result):
            return RecognitionResponse(
                id=str(db_result.id),
                artwork_name=db_result.artwork_name,
                artist=db_result.artist,
                period=db_result.period,
                description=db_result.description,
                confidence=db_result.confidence,
            )

        with patch.object(
            RecognitionResponse, "model_validate", side_effect=mock_validate
        ):
            # Act
            results = service.get_recent_recognitions(limit=5)

            # Assert
            assert len(results) == 5
            mock_db.query.return_value.order_by.return_value.limit.assert_called_with(5)

    def test_get_recent_recognitions_empty_result(self, service_with_mocks):
        """should_return_empty_list_when_no_results"""
        # Arrange
        service, mock_db = service_with_mocks

        mock_db.query.return_value.order_by.return_value.limit.return_value.all.return_value = (
            []
        )

        # Act
        results = service.get_recent_recognitions()

        # Assert
        assert results == []
        assert isinstance(results, list)

    def test_get_recent_recognitions_database_error(self, service_with_mocks):
        """should_raise_service_exception_on_database_error"""
        # Arrange
        service, mock_db = service_with_mocks

        mock_db.query.side_effect = Exception("Database error")

        # Act & Assert
        with pytest.raises(ServiceException) as exc_info:
            service.get_recent_recognitions()

        assert "Failed to retrieve recent recognitions" in str(exc_info.value)


class TestGetStatistics:
    """Test statistics retrieval"""

    @pytest.fixture
    def service_with_mocks(self):
        """Create RecognitionService with mocked dependencies"""
        mock_db = MagicMock()
        mock_cache = MagicMock()
        service = RecognitionService(
            db=mock_db,
            ai_service=MagicMock(),
            cache_service=mock_cache,
            image_service=MagicMock(),
        )
        return service, mock_db, mock_cache

    def test_get_statistics_calculation(self, service_with_mocks):
        """should_calculate_and_return_statistics"""
        # Arrange
        service, mock_db, mock_cache = service_with_mocks

        # Mock database stats
        mock_db.query.return_value.count.return_value = 42
        mock_db.query.return_value.scalar.return_value = 0.87

        # Mock cache stats
        cache_stats = {"total_cached": 15, "hit_rate": 0.65, "redis_available": True}
        mock_cache.get_cache_stats.return_value = cache_stats

        # Act
        stats = service.get_statistics()

        # Assert
        assert stats["total_recognitions"] == 42
        assert stats["average_confidence"] == 0.87
        assert stats["cache_stats"]["total_cached"] == 15
        assert stats["cache_stats"]["hit_rate"] == 0.65

    def test_get_statistics_handles_errors_gracefully(self, service_with_mocks):
        """should_return_default_values_on_error"""
        # Arrange
        service, mock_db, mock_cache = service_with_mocks

        mock_db.query.side_effect = Exception("Database error")

        # Act
        stats = service.get_statistics()

        # Assert
        assert stats["total_recognitions"] == 0
        assert stats["average_confidence"] == 0.0
        assert "error" in stats["cache_stats"]


class TestGetRecognitionServiceFactory:
    """Test the factory function for creating RecognitionService"""

    def test_get_recognition_service_with_all_dependencies(self):
        """should_use_provided_dependencies"""
        # Arrange
        mock_db = MagicMock()
        mock_ai = MagicMock()
        mock_cache = MagicMock()
        mock_image = MagicMock()

        # Act
        service = get_recognition_service(
            db=mock_db,
            ai_service=mock_ai,
            cache_service=mock_cache,
            image_service=mock_image,
        )

        # Assert
        assert isinstance(service, RecognitionService)
        assert service.db == mock_db
        assert service.ai_service == mock_ai
        assert service.cache_service == mock_cache
        assert service.image_service == mock_image

    @patch("app.services.ai_service.get_ai_service")
    @patch("app.services.recognition_service.CacheService")
    @patch("app.services.recognition_service.ImageService")
    def test_get_recognition_service_creates_default_dependencies(
        self, mock_image_class, mock_cache_class, mock_get_ai
    ):
        """should_create_default_dependencies_when_not_provided"""
        # Arrange
        mock_db = MagicMock()
        mock_ai_instance = MagicMock()
        mock_cache_instance = MagicMock()
        mock_image_instance = MagicMock()

        mock_get_ai.return_value = mock_ai_instance
        mock_cache_class.return_value = mock_cache_instance
        mock_image_class.return_value = mock_image_instance

        # Act
        service = get_recognition_service(db=mock_db)

        # Assert
        mock_get_ai.assert_called_once()
        mock_cache_class.assert_called_once()
        mock_image_class.assert_called_once()

        assert service.ai_service == mock_ai_instance
        assert service.cache_service == mock_cache_instance
        assert service.image_service == mock_image_instance


class TestRecognitionWithPerceptualHash:
    """Test three-layer caching with perceptual hash for Step 2 optimization"""

    @pytest.fixture
    def service_with_mocks(self):
        """Create RecognitionService with all mocked dependencies"""
        mock_db = MagicMock()
        mock_ai_service = MagicMock()
        mock_cache_service = MagicMock()
        mock_image_service = MagicMock()

        service = RecognitionService(
            db=mock_db,
            ai_service=mock_ai_service,
            cache_service=mock_cache_service,
            image_service=mock_image_service,
        )

        return service, mock_db, mock_ai_service, mock_cache_service, mock_image_service

    @pytest.mark.asyncio
    async def test_exact_file_hash_cache_hit_first(self, service_with_mocks):
        """should_return_cached_result_from_file_hash_before_checking_perceptual_hash"""
        # Arrange
        service, mock_db, mock_ai, mock_cache, mock_image = service_with_mocks

        test_image_data = b"fake_image_bytes"
        file_hash = "abc123file_hash"
        perceptual_hash = "8f373e0c183f1e3f"

        # Mock image service
        mock_image.validate_image.return_value = True
        mock_image.generate_hash.return_value = file_hash
        mock_image.generate_perceptual_hash.return_value = perceptual_hash

        # Mock exact file hash cache hit
        cached_response = RecognitionResponse(
            id="cached-id-123",
            artwork_name="Mona Lisa",
            artist="Leonardo da Vinci",
            period="Renaissance",
            description="Famous portrait",
            confidence=0.95,
            cached=True,
            processing_time_ms=50,
        )
        mock_cache.get_cached_result.return_value = cached_response

        # Act
        result = await service.recognize_artwork(test_image_data)

        # Assert - 应该返回file hash缓存结果
        assert result == cached_response
        assert result.artwork_name == "Mona Lisa"

        # 验证调用顺序: file hash先于perceptual hash
        mock_cache.get_cached_result.assert_called_once_with(file_hash)
        # 不应该调用perceptual hash similarity search
        mock_cache.get_similar_cached_result.assert_not_called()
        # 不应该调用数据库或AI
        mock_db.query.assert_not_called()
        mock_ai.recognize_with_timeout.assert_not_called()

    @pytest.mark.asyncio
    async def test_perceptual_hash_cache_hit_different_photo(self, service_with_mocks):
        """should_find_similar_result_via_perceptual_hash_when_file_hash_misses"""
        # Arrange
        service, mock_db, mock_ai, mock_cache, mock_image = service_with_mocks

        test_image_data = b"different_photo_of_same_artwork"
        file_hash = "new_file_hash_xyz"
        perceptual_hash = "8f373e0c183f1e3e"  # 相似但不完全相同

        # Mock image service
        mock_image.validate_image.return_value = True
        mock_image.generate_hash.return_value = file_hash
        mock_image.generate_perceptual_hash.return_value = perceptual_hash

        # Mock file hash cache miss
        mock_cache.get_cached_result.return_value = None

        # Mock perceptual hash similarity cache hit
        similar_response = RecognitionResponse(
            id="similar-id-456",
            artwork_name="Mona Lisa",
            artist="Leonardo da Vinci",
            period="Renaissance",
            description="Same artwork, different photo",
            confidence=0.94,
            cached=True,
            processing_time_ms=80,
        )
        similarity_score = 0.984  # 98.4% similar
        mock_cache.get_similar_cached_result.return_value = (
            similar_response,
            similarity_score,
        )

        # Act
        result = await service.recognize_artwork(test_image_data)

        # Assert - 应该返回perceptual hash相似结果
        assert result == similar_response
        assert result.artwork_name == "Mona Lisa"

        # 验证调用顺序
        mock_cache.get_cached_result.assert_called_once_with(file_hash)
        mock_cache.get_similar_cached_result.assert_called_once_with(
            perceptual_hash, similarity_threshold=0.90
        )

        # 应该用新的file hash重新缓存结果 (为了未来更快的查找)
        assert mock_cache.cache_result.call_count == 1
        cache_call = mock_cache.cache_result.call_args
        assert cache_call[0][0] == file_hash
        assert cache_call[0][1] == similar_response
        assert cache_call[0][2] == perceptual_hash

        # 不应该调用数据库或AI
        mock_db.query.assert_not_called()
        mock_ai.recognize_with_timeout.assert_not_called()

    @pytest.mark.asyncio
    async def test_caches_with_both_hashes_after_ai_recognition(
        self, service_with_mocks
    ):
        """should_cache_result_with_both_file_hash_and_perceptual_hash_after_ai"""
        # Arrange
        service, mock_db, mock_ai, mock_cache, mock_image = service_with_mocks

        test_image_data = b"brand_new_artwork_photo"
        file_hash = "new_hash_abc"
        perceptual_hash = "ff00ff00ff00ff00"

        # Mock image service
        mock_image.validate_image.return_value = True
        mock_image.generate_hash.return_value = file_hash
        mock_image.generate_perceptual_hash.return_value = perceptual_hash
        mock_image.to_base64.return_value = "base64_encoded"

        # Mock all cache misses
        mock_cache.get_cached_result.return_value = None
        mock_cache.get_similar_cached_result.return_value = None

        # Mock database miss
        mock_db.query.return_value.filter.return_value.first.return_value = None

        # Mock AI service
        ai_result = {
            "artwork_name": "The Starry Night",
            "artist": "Vincent van Gogh",
            "period": "Post-Impressionism",
            "description": "Swirling night sky painting",
            "confidence": 0.93,
        }
        mock_ai.recognize_with_timeout = AsyncMock(return_value=ai_result)

        # Mock database save
        saved_id = uuid4()
        mock_db_result = MagicMock(spec=RecognitionResult)
        mock_db_result.id = saved_id
        mock_db_result.image_hash = file_hash
        mock_db_result.artwork_name = ai_result["artwork_name"]
        mock_db_result.artist = ai_result["artist"]
        mock_db_result.period = ai_result["period"]
        mock_db_result.description = ai_result["description"]
        mock_db_result.confidence = ai_result["confidence"]
        mock_db_result.timestamp = datetime.now()

        expected_response = RecognitionResponse(
            id=str(saved_id),
            artwork_name=ai_result["artwork_name"],
            artist=ai_result["artist"],
            period=ai_result["period"],
            description=ai_result["description"],
            confidence=ai_result["confidence"],
        )

        with patch.object(
            RecognitionResponse, "model_validate", return_value=expected_response
        ):
            # Act
            result = await service.recognize_artwork(test_image_data)

            # Assert - 应该完成完整的识别流程
            assert result.artwork_name == "The Starry Night"

            # 验证三层缓存都被检查了
            mock_cache.get_cached_result.assert_called_once_with(file_hash)
            mock_cache.get_similar_cached_result.assert_called_once_with(
                perceptual_hash, similarity_threshold=0.90
            )
            mock_db.query.assert_called_once()

            # 验证AI被调用
            mock_ai.recognize_with_timeout.assert_called_once_with("base64_encoded")

            # 验证结果被同时缓存到file hash和perceptual hash
            mock_cache.cache_result.assert_called_once()
            cache_call = mock_cache.cache_result.call_args
            assert cache_call[0][0] == file_hash  # file hash
            assert cache_call[0][1].artwork_name == "The Starry Night"  # result
            assert cache_call[0][2] == perceptual_hash  # perceptual hash

    @pytest.mark.asyncio
    async def test_cache_miss_triggers_database_check(self, service_with_mocks):
        """should_query_database_when_both_cache_layers_miss"""
        # Arrange
        service, mock_db, mock_ai, mock_cache, mock_image = service_with_mocks

        test_image_data = b"image_bytes"
        file_hash = "hash_123"
        perceptual_hash = "phash_456"

        # Mock image service
        mock_image.validate_image.return_value = True
        mock_image.generate_hash.return_value = file_hash
        mock_image.generate_perceptual_hash.return_value = perceptual_hash

        # Mock both cache layers miss
        mock_cache.get_cached_result.return_value = None
        mock_cache.get_similar_cached_result.return_value = None

        # Mock database hit
        db_id = uuid4()
        db_result = MagicMock(spec=RecognitionResult)
        db_result.id = db_id
        db_result.image_hash = file_hash
        db_result.artwork_name = "Girl with a Pearl Earring"
        db_result.artist = "Johannes Vermeer"
        db_result.period = "Baroque"
        db_result.description = "Portrait painting"
        db_result.confidence = 0.91
        db_result.timestamp = datetime.now()
        mock_db.query.return_value.filter.return_value.first.return_value = db_result

        expected_response = RecognitionResponse(
            id=str(db_id),
            artwork_name="Girl with a Pearl Earring",
            artist="Johannes Vermeer",
            period="Baroque",
            description="Portrait painting",
            confidence=0.91,
        )

        with patch.object(
            RecognitionResponse, "model_validate", return_value=expected_response
        ):
            # Act
            result = await service.recognize_artwork(test_image_data)

            # Assert - 应该从数据库返回结果
            assert result.artwork_name == "Girl with a Pearl Earring"

            # 验证所有三层都被检查了
            mock_cache.get_cached_result.assert_called_once_with(file_hash)
            mock_cache.get_similar_cached_result.assert_called_once_with(
                perceptual_hash, similarity_threshold=0.90
            )
            mock_db.query.assert_called_once()

            # 验证结果被缓存 (带perceptual hash)
            mock_cache.cache_result.assert_called_once()
            cache_call = mock_cache.cache_result.call_args
            assert cache_call[0][0] == file_hash
            assert cache_call[0][1].artwork_name == "Girl with a Pearl Earring"
            assert cache_call[0][2] == perceptual_hash

            # AI不应该被调用 (数据库命中)
            mock_ai.recognize_with_timeout.assert_not_called()

    @pytest.mark.asyncio
    async def test_perceptual_hash_similarity_threshold_respected(
        self, service_with_mocks
    ):
        """should_use_90_percent_similarity_threshold_for_perceptual_cache"""
        # Arrange
        service, mock_db, mock_ai, mock_cache, mock_image = service_with_mocks

        test_image_data = b"test_image"
        file_hash = "hash_abc"
        perceptual_hash = "phash_xyz"

        mock_image.validate_image.return_value = True
        mock_image.generate_hash.return_value = file_hash
        mock_image.generate_perceptual_hash.return_value = perceptual_hash

        # Mock file hash miss
        mock_cache.get_cached_result.return_value = None

        # Mock perceptual hash miss (low similarity)
        mock_cache.get_similar_cached_result.return_value = None

        # Mock database miss
        mock_db.query.return_value.filter.return_value.first.return_value = None

        # Mock AI
        ai_result = {
            "artwork_name": "Test Artwork",
            "artist": "Test Artist",
            "period": "Test Period",
            "description": "Test Description",
            "confidence": 0.85,
        }
        mock_ai.recognize_with_timeout = AsyncMock(return_value=ai_result)
        mock_image.to_base64.return_value = "base64"

        expected_response = RecognitionResponse(
            id=str(uuid4()),
            artwork_name="Test Artwork",
            artist="Test Artist",
            period="Test Period",
            description="Test Description",
            confidence=0.85,
        )

        with patch.object(
            RecognitionResponse, "model_validate", return_value=expected_response
        ):
            # Act
            await service.recognize_artwork(test_image_data)

            # Assert - 验证相似度阈值为0.90
            mock_cache.get_similar_cached_result.assert_called_once_with(
                perceptual_hash, similarity_threshold=0.90
            )
