"""
Comprehensive Unit tests for Recognition Service
Tests the core business logic for artwork recognition workflow
"""
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4, UUID
from datetime import datetime

from app.services.recognition_service import RecognitionService, get_recognition_service
from app.schemas.recognition import RecognitionResponse
from app.models.recognition_result import RecognitionResult
from app.core.exceptions import ServiceException, NotFoundException, ValidationException


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
            image_service=mock_image_service
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
            image_service=mock_image_service
        )

        return service, mock_db, mock_ai_service, mock_cache_service, mock_image_service

    @pytest.mark.asyncio
    async def test_recognize_artwork_complete_flow_success(self, service_with_mocks):
        """should_execute_full_recognition_workflow_when_no_cache"""
        # Arrange
        service, mock_db, mock_ai, mock_cache, mock_image = service_with_mocks

        test_image_data = b"fake_image_bytes"
        test_hash = "abc123hash"
        test_base64 = "base64_encoded_image"

        # Mock image service
        mock_image.validate_image.return_value = True
        mock_image.generate_hash.return_value = test_hash
        mock_image.to_base64.return_value = test_base64

        # Mock cache miss
        mock_cache.get_cached_result.return_value = None

        # Mock database miss
        mock_db.query.return_value.filter.return_value.first.return_value = None

        # Mock AI service
        ai_result = {
            "artwork_name": "Mona Lisa",
            "artist": "Leonardo da Vinci",
            "period": "Renaissance",
            "description": "Famous portrait",
            "confidence": 0.95
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
            confidence=ai_result["confidence"]
        )

        with patch.object(RecognitionResponse, 'model_validate', return_value=expected_response) as mock_validate:
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
            confidence=0.92
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

        mock_image.validate_image.return_value = True
        mock_image.generate_hash.return_value = test_hash

        # Mock cache miss
        mock_cache.get_cached_result.return_value = None

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
            confidence=0.88
        )

        with patch.object(RecognitionResponse, 'model_validate', return_value=expected_response):
            # Act
            result = await service.recognize_artwork(test_image_data)

            # Assert
            assert result.artwork_name == "The Scream"
            mock_ai.recognize_with_timeout.assert_not_called()
            mock_db.add.assert_not_called()
            mock_cache.cache_result.assert_called_once_with(test_hash, result)

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
        mock_ai.recognize_with_timeout = AsyncMock(side_effect=asyncio.TimeoutError("AI timeout"))

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

        mock_image.validate_image.return_value = True
        mock_image.generate_hash.return_value = test_hash
        mock_image.to_base64.return_value = "base64_data"
        mock_cache.get_cached_result.return_value = None
        mock_db.query.return_value.filter.return_value.first.return_value = None

        ai_result = {
            "artwork_name": "Guernica",
            "artist": "Pablo Picasso",
            "period": "Cubism",
            "description": "Anti-war painting",
            "confidence": 0.91
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
            confidence=ai_result["confidence"]
        )

        with patch.object(RecognitionResponse, 'model_validate', return_value=expected_response):
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
            "confidence": 0.5
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
            image_service=MagicMock()
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
            confidence=0.89
        )

        with patch.object(RecognitionResponse, 'model_validate', return_value=expected_response):
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
            image_service=MagicMock()
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

        mock_db.query.return_value.order_by.return_value.limit.return_value.all.return_value = mock_db_results

        # Mock RecognitionResponse.model_validate for list comprehension
        def mock_validate(db_result):
            return RecognitionResponse(
                id=str(db_result.id),
                artwork_name=db_result.artwork_name,
                artist=db_result.artist,
                period=db_result.period,
                description=db_result.description,
                confidence=db_result.confidence
            )

        with patch.object(RecognitionResponse, 'model_validate', side_effect=mock_validate):
            # Act
            results = service.get_recent_recognitions()

            # Assert
            assert len(results) == 10
            mock_db.query.return_value.order_by.return_value.limit.assert_called_with(10)

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

        mock_db.query.return_value.order_by.return_value.limit.return_value.all.return_value = mock_db_results

        # Mock RecognitionResponse.model_validate for list comprehension
        def mock_validate(db_result):
            return RecognitionResponse(
                id=str(db_result.id),
                artwork_name=db_result.artwork_name,
                artist=db_result.artist,
                period=db_result.period,
                description=db_result.description,
                confidence=db_result.confidence
            )

        with patch.object(RecognitionResponse, 'model_validate', side_effect=mock_validate):
            # Act
            results = service.get_recent_recognitions(limit=5)

            # Assert
            assert len(results) == 5
            mock_db.query.return_value.order_by.return_value.limit.assert_called_with(5)

    def test_get_recent_recognitions_empty_result(self, service_with_mocks):
        """should_return_empty_list_when_no_results"""
        # Arrange
        service, mock_db = service_with_mocks

        mock_db.query.return_value.order_by.return_value.limit.return_value.all.return_value = []

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
            image_service=MagicMock()
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
        cache_stats = {
            "total_cached": 15,
            "hit_rate": 0.65,
            "redis_available": True
        }
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
            image_service=mock_image
        )

        # Assert
        assert isinstance(service, RecognitionService)
        assert service.db == mock_db
        assert service.ai_service == mock_ai
        assert service.cache_service == mock_cache
        assert service.image_service == mock_image

    @patch('app.services.ai_service.get_ai_service')
    @patch('app.services.recognition_service.CacheService')
    @patch('app.services.recognition_service.ImageService')
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
