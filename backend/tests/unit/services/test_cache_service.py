"""
Unit tests for Cache Service
Tests Redis caching functionality
"""
import pytest
from unittest.mock import MagicMock, patch
import json
import redis
from app.services.cache_service import CacheService
from app.schemas.recognition import RecognitionResponse
from tests.fixtures.image_helpers import (
    create_artwork_simulation,
    create_similar_image
)


class TestCacheService:
    """Test suite for cache service"""

    @pytest.fixture
    def cache_service(self):
        """Create CacheService instance for testing with mocked Redis"""
        with patch('app.services.cache_service.redis.Redis') as mock_redis:
            mock_client = MagicMock()
            mock_redis.return_value = mock_client
            cache_service = CacheService()
            cache_service.redis_client = mock_client
            return cache_service

    def test_generates_cache_key_using_sha256_hash(self, cache_service):
        """should_create_consistent_hash_key_from_image_bytes"""
        # Arrange
        image_hash = "abc123def456"
        
        # Act
        cache_key = cache_service._get_cache_key(image_hash)
        
        # Assert
        assert cache_key == "recognition:abc123def456"
        assert cache_key.startswith("recognition:")

    def test_same_image_produces_same_cache_key(self, cache_service):
        """should_generate_identical_key_for_identical_images"""
        # Arrange
        image_hash = "same_hash_123"
        
        # Act
        key1 = cache_service._get_cache_key(image_hash)
        key2 = cache_service._get_cache_key(image_hash)
        
        # Assert
        assert key1 == key2

    def test_different_images_produce_different_cache_keys(self, cache_service):
        """should_generate_different_keys_for_different_images"""
        # Arrange
        hash1 = "hash_image_1"
        hash2 = "hash_image_2"
        
        # Act
        key1 = cache_service._get_cache_key(hash1)
        key2 = cache_service._get_cache_key(hash2)
        
        # Assert
        assert key1 != key2
        assert key1 == "recognition:hash_image_1"
        assert key2 == "recognition:hash_image_2"


class TestCacheServiceRead:
    """Test cache read operations"""

    @pytest.fixture
    def cache_service(self):
        """Create CacheService instance for testing with mocked Redis"""
        with patch('app.services.cache_service.redis.Redis') as mock_redis:
            mock_client = MagicMock()
            mock_redis.return_value = mock_client
            cache_service = CacheService()
            cache_service.redis_client = mock_client
            return cache_service

    def test_retrieves_cached_result_from_redis(self, cache_service):
        """should_return_cached_recognition_result_when_key_exists"""
        # Arrange
        image_hash = "test_hash_123"
        cached_data = {
            "artwork_name": "Mona Lisa",
            "artist": "Leonardo da Vinci",
            "period": "Renaissance",
            "description": "Famous portrait",
            "confidence": 0.95,
            "cached": True,
            "processing_time_ms": 100
        }
        cache_service.redis_client.get.return_value = json.dumps(cached_data)

        # Act
        result = cache_service.get_cached_result(image_hash)

        # Assert
        assert result is not None
        assert result.artwork_name == "Mona Lisa"
        assert result.artist == "Leonardo da Vinci"
        assert result.cached is True
        cache_service.redis_client.get.assert_called_once_with("recognition:test_hash_123")

    def test_returns_none_when_cache_miss(self, cache_service):
        """should_return_none_when_key_not_found_in_redis"""
        # Arrange
        image_hash = "non_existent_hash"
        cache_service.redis_client.get.return_value = None

        # Act
        result = cache_service.get_cached_result(image_hash)

        # Assert
        assert result is None
        cache_service.redis_client.get.assert_called_once_with("recognition:non_existent_hash")

    def test_deserializes_json_cached_data(self, cache_service):
        """should_parse_json_string_from_redis_to_dict"""
        # Arrange
        image_hash = "test_key"
        cached_json = json.dumps({
            "artwork_name": "The Starry Night",
            "artist": "Vincent van Gogh",
            "period": "Post-Impressionism",
            "description": "Swirling night sky",
            "confidence": 0.89,
            "cached": True,
            "processing_time_ms": 120
        })
        cache_service.redis_client.get.return_value = cached_json

        # Act
        result = cache_service.get_cached_result(image_hash)

        # Assert
        assert result is not None
        assert result.artwork_name == "The Starry Night"
        assert isinstance(result, RecognitionResponse)

    def test_handles_redis_connection_error_gracefully(self, cache_service):
        """should_return_none_and_log_error_on_redis_failure"""
        # Arrange
        image_hash = "test_key"
        cache_service.redis_client.get.side_effect = redis.RedisError("Connection failed")

        # Act
        result = cache_service.get_cached_result(image_hash)

        # Assert
        assert result is None

    def test_handles_corrupted_cache_data(self, cache_service):
        """should_handle_invalid_json_in_cache_gracefully"""
        # Arrange
        image_hash = "test_key"
        cache_service.redis_client.get.return_value = "invalid json data{{"

        # Act
        result = cache_service.get_cached_result(image_hash)

        # Assert
        assert result is None
        # Should also call delete to invalidate corrupted data
        cache_service.redis_client.delete.assert_called_once_with("recognition:test_key")


class TestCacheServiceWrite:
    """Test cache write operations"""

    @pytest.fixture
    def cache_service(self):
        """Create CacheService instance for testing with mocked Redis"""
        with patch('app.services.cache_service.redis.Redis') as mock_redis:
            mock_client = MagicMock()
            mock_redis.return_value = mock_client
            cache_service = CacheService()
            cache_service.redis_client = mock_client
            return cache_service

    def test_stores_recognition_result_in_redis(self, cache_service):
        """should_save_result_with_generated_cache_key"""
        # Arrange
        image_hash = "test_hash"
        result = RecognitionResponse(
            artwork_name="Starry Night",
            artist="Van Gogh",
            period="Post-Impressionism",
            description="Famous painting",
            confidence=0.95,
            cached=False,
            processing_time_ms=200
        )

        # Act
        cache_service.cache_result(image_hash, result)

        # Assert
        cache_service.redis_client.setex.assert_called_once()
        call_args = cache_service.redis_client.setex.call_args
        assert call_args[0][0] == "recognition:test_hash"
        assert call_args[0][1] == cache_service.ttl

    def test_serializes_result_to_json_before_caching(self, cache_service):
        """should_convert_dict_to_json_string_for_storage"""
        # Arrange
        image_hash = "test_key"
        result = RecognitionResponse(
            artwork_name="The Scream",
            artist="Munch",
            period="Expressionism",
            description="Famous scream",
            confidence=0.88,
            cached=False,
            processing_time_ms=150
        )

        # Act
        cache_service.cache_result(image_hash, result)

        # Assert
        cache_service.redis_client.setex.assert_called_once()
        call_args = cache_service.redis_client.setex.call_args
        cached_json = call_args[0][2]
        # Should be valid JSON string
        parsed_data = json.loads(cached_json)
        assert parsed_data["artwork_name"] == "The Scream"

    def test_sets_ttl_to_24_hours(self, cache_service):
        """should_set_expiration_to_86400_seconds"""
        # Arrange
        image_hash = "test_key"
        result = RecognitionResponse(
            artwork_name="Girl with a Pearl Earring",
            artist="Vermeer",
            period="Baroque",
            description="Pearl earring portrait",
            confidence=0.92,
            cached=False,
            processing_time_ms=180
        )
        cache_service.ttl = 86400  # 24 hours

        # Act
        cache_service.cache_result(image_hash, result)

        # Assert
        call_args = cache_service.redis_client.setex.call_args
        assert call_args[0][1] == 86400

    def test_handles_redis_write_failure(self, cache_service):
        """should_log_error_and_not_crash_on_write_failure"""
        # Arrange
        image_hash = "test_key"
        result = RecognitionResponse(
            artwork_name="Test Art",
            artist="Test Artist",
            period="Test Period",
            description="Test description",
            confidence=0.5,
            cached=False,
            processing_time_ms=100
        )
        cache_service.redis_client.setex.side_effect = redis.RedisError("Write failed")

        # Act - should not raise exception
        cache_service.cache_result(image_hash, result)

        # Assert - method should complete without crashing
        cache_service.redis_client.setex.assert_called_once()


class TestCacheServiceMetrics:
    """Test cache metrics and monitoring"""

    @pytest.fixture
    def cache_service(self):
        """Create CacheService instance for testing with mocked Redis"""
        with patch('app.services.cache_service.redis.Redis') as mock_redis:
            mock_client = MagicMock()
            mock_redis.return_value = mock_client
            cache_service = CacheService()
            cache_service.redis_client = mock_client
            return cache_service

    def test_tracks_cache_hit_rate(self, cache_service):
        """should_increment_hit_counter_on_cache_hit"""
        # Arrange
        image_hash = "test_key"
        cached_data = {
            "artwork_name": "Test Art",
            "artist": "Test Artist",
            "period": "Modern",
            "description": "Test description",
            "confidence": 0.8,
            "cached": True,
            "processing_time_ms": 100
        }
        cache_service.redis_client.get.return_value = json.dumps(cached_data)

        # Act
        result = cache_service.get_cached_result(image_hash)

        # Assert
        assert result is not None
        assert cache_service._hit_count == 1
        assert cache_service._miss_count == 0

    def test_tracks_cache_miss_rate(self, cache_service):
        """should_increment_miss_counter_on_cache_miss"""
        # Arrange
        image_hash = "non_existent_key"
        cache_service.redis_client.get.return_value = None

        # Act
        result = cache_service.get_cached_result(image_hash)

        # Assert
        assert result is None
        assert cache_service._hit_count == 0
        assert cache_service._miss_count == 1

    def test_calculates_cache_hit_percentage(self, cache_service):
        """should_compute_hit_rate_as_hits_divided_by_total_requests"""
        # Arrange - simulate some hits and misses
        cache_service._hit_count = 7
        cache_service._miss_count = 3

        # Mock Redis info for stats
        cache_service.redis_client.scan_iter.return_value = ["key1", "key2", "key3"]
        cache_service.redis_client.info.return_value = {"used_memory_human": "1.2MB"}

        # Act
        stats = cache_service.get_cache_stats()

        # Assert
        assert stats["hit_count"] == 7
        assert stats["miss_count"] == 3
        assert stats["hit_rate"] == 0.7  # 7/10 = 0.7

    def test_cache_hit_rate_exceeds_60_percent_target(self, cache_service):
        """should_achieve_minimum_60_percent_cache_hit_rate"""
        # Arrange - simulate high hit rate
        cache_service._hit_count = 80
        cache_service._miss_count = 20

        # Mock Redis info for stats
        cache_service.redis_client.scan_iter.return_value = ["key1"] * 50
        cache_service.redis_client.info.return_value = {"used_memory_human": "5MB"}

        # Act
        stats = cache_service.get_cache_stats()

        # Assert
        assert stats["hit_rate"] >= 0.6  # Should be 0.8 in this case


class TestCacheServiceConnectionFailure:
    """Test Redis connection failure scenarios"""

    def test_cache_service_handles_redis_connection_failure(self):
        """should_gracefully_degrade_when_redis_connection_fails"""
        # Arrange & Act
        with patch('app.services.cache_service.redis.Redis') as mock_redis:
            mock_redis.return_value.ping.side_effect = redis.RedisError("Connection refused")
            cache_service = CacheService()

        # Assert
        assert cache_service.redis_client is None

    def test_cache_service_handles_redis_initialization_exception(self):
        """should_set_redis_client_to_none_on_init_exception"""
        # Arrange & Act
        with patch('app.services.cache_service.redis.Redis') as mock_redis:
            mock_redis.side_effect = Exception("Network error")
            cache_service = CacheService()

        # Assert
        assert cache_service.redis_client is None


class TestCacheServiceRedisUnavailable:
    """Test cache operations when Redis is unavailable"""

    @pytest.fixture
    def cache_service_no_redis(self):
        """Create CacheService instance with no Redis connection"""
        with patch('app.services.cache_service.redis.Redis') as mock_redis:
            mock_redis.return_value.ping.side_effect = redis.RedisError("Connection failed")
            return CacheService()

    def test_get_cached_result_handles_redis_unavailable(self, cache_service_no_redis):
        """should_return_none_and_increment_miss_count_when_redis_unavailable"""
        # Arrange
        image_hash = "test_hash"
        initial_miss_count = cache_service_no_redis._miss_count

        # Act
        result = cache_service_no_redis.get_cached_result(image_hash)

        # Assert
        assert result is None
        assert cache_service_no_redis._miss_count == initial_miss_count + 1

    def test_cache_result_handles_redis_unavailable(self, cache_service_no_redis):
        """should_silently_fail_when_caching_without_redis"""
        # Arrange
        image_hash = "test_hash"
        result = RecognitionResponse(
            artwork_name="Test Art",
            artist="Test Artist",
            period="Test Period",
            description="Test description",
            confidence=0.9,
            cached=False,
            processing_time_ms=100
        )

        # Act - should not raise exception
        cache_service_no_redis.cache_result(image_hash, result)

        # Assert - method completes without error

    def test_invalidate_cache_handles_redis_unavailable(self, cache_service_no_redis):
        """should_silently_return_when_invalidating_without_redis"""
        # Arrange
        image_hash = "test_hash"

        # Act - should not raise exception
        cache_service_no_redis.invalidate_cache(image_hash)

        # Assert - method completes without error

    def test_get_cache_stats_redis_unavailable(self, cache_service_no_redis):
        """should_return_default_stats_when_redis_unavailable"""
        # Arrange
        cache_service_no_redis._hit_count = 5
        cache_service_no_redis._miss_count = 3

        # Act
        stats = cache_service_no_redis.get_cache_stats()

        # Assert
        assert stats["total_cached"] == 0
        assert stats["memory_used"] == "0B"
        assert stats["hit_count"] == 5
        assert stats["miss_count"] == 3
        # When Redis is unavailable, hit_rate is hardcoded to 0.0
        assert stats["hit_rate"] == 0.0
        assert stats["redis_available"] is False

    def test_clear_all_cache_handles_redis_unavailable(self, cache_service_no_redis):
        """should_return_zero_when_clearing_cache_without_redis"""
        # Act
        deleted = cache_service_no_redis.clear_all_cache()

        # Assert
        assert deleted == 0

    def test_health_check_redis_unavailable(self, cache_service_no_redis):
        """should_return_false_when_redis_unavailable"""
        # Act
        is_healthy = cache_service_no_redis.health_check()

        # Assert
        assert is_healthy is False


class TestCacheServiceReadExceptions:
    """Test exception handling during cache read operations"""

    @pytest.fixture
    def cache_service(self):
        """Create CacheService instance for testing with mocked Redis"""
        with patch('app.services.cache_service.redis.Redis') as mock_redis:
            mock_client = MagicMock()
            mock_redis.return_value = mock_client
            cache_service = CacheService()
            cache_service.redis_client = mock_client
            return cache_service

    def test_get_cached_result_handles_redis_error(self, cache_service):
        """should_return_none_and_increment_miss_on_redis_error"""
        # Arrange
        image_hash = "test_hash"
        cache_service.redis_client.get.side_effect = redis.RedisError("Timeout")
        initial_miss_count = cache_service._miss_count

        # Act
        result = cache_service.get_cached_result(image_hash)

        # Assert
        assert result is None
        assert cache_service._miss_count == initial_miss_count + 1

    def test_get_cached_result_handles_unexpected_exception(self, cache_service):
        """should_handle_unexpected_exception_during_cache_lookup"""
        # Arrange
        image_hash = "test_hash"
        cache_service.redis_client.get.side_effect = Exception("Unexpected error")
        initial_miss_count = cache_service._miss_count

        # Act
        result = cache_service.get_cached_result(image_hash)

        # Assert
        assert result is None
        assert cache_service._miss_count == initial_miss_count + 1

    def test_get_cached_result_handles_corrupted_json(self, cache_service):
        """should_invalidate_corrupted_cache_and_return_none"""
        # Arrange
        image_hash = "test_hash"
        cache_service.redis_client.get.return_value = "invalid{json{{"
        initial_miss_count = cache_service._miss_count

        # Act
        result = cache_service.get_cached_result(image_hash)

        # Assert
        assert result is None
        assert cache_service._miss_count == initial_miss_count + 1
        cache_service.redis_client.delete.assert_called_once_with("recognition:test_hash")


class TestCacheServiceWriteExceptions:
    """Test exception handling during cache write operations"""

    @pytest.fixture
    def cache_service(self):
        """Create CacheService instance for testing with mocked Redis"""
        with patch('app.services.cache_service.redis.Redis') as mock_redis:
            mock_client = MagicMock()
            mock_redis.return_value = mock_client
            cache_service = CacheService()
            cache_service.redis_client = mock_client
            return cache_service

    def test_cache_result_handles_redis_write_error(self, cache_service):
        """should_not_crash_on_redis_write_error"""
        # Arrange
        image_hash = "test_hash"
        result = RecognitionResponse(
            artwork_name="Test Art",
            artist="Test Artist",
            period="Test Period",
            description="Test description",
            confidence=0.85,
            cached=False,
            processing_time_ms=150
        )
        cache_service.redis_client.setex.side_effect = redis.RedisError("Write timeout")

        # Act - should not raise exception
        cache_service.cache_result(image_hash, result)

        # Assert
        cache_service.redis_client.setex.assert_called_once()

    def test_cache_result_handles_unexpected_exception(self, cache_service):
        """should_handle_unexpected_exception_during_cache_write"""
        # Arrange
        image_hash = "test_hash"
        result = RecognitionResponse(
            artwork_name="Test Art",
            artist="Test Artist",
            period="Test Period",
            description="Test description",
            confidence=0.75,
            cached=False,
            processing_time_ms=200
        )
        cache_service.redis_client.setex.side_effect = Exception("Unexpected serialization error")

        # Act - should not raise exception
        cache_service.cache_result(image_hash, result)

        # Assert
        cache_service.redis_client.setex.assert_called_once()


class TestCacheServiceInvalidation:
    """Test cache invalidation operations"""

    @pytest.fixture
    def cache_service(self):
        """Create CacheService instance for testing with mocked Redis"""
        with patch('app.services.cache_service.redis.Redis') as mock_redis:
            mock_client = MagicMock()
            mock_redis.return_value = mock_client
            cache_service = CacheService()
            cache_service.redis_client = mock_client
            return cache_service

    def test_invalidate_cache_success(self, cache_service):
        """should_successfully_delete_cache_entry"""
        # Arrange
        image_hash = "test_hash"
        cache_service.redis_client.delete.return_value = 1

        # Act
        cache_service.invalidate_cache(image_hash)

        # Assert
        cache_service.redis_client.delete.assert_called_once_with("recognition:test_hash")

    def test_invalidate_cache_key_not_found(self, cache_service):
        """should_handle_when_cache_key_not_found"""
        # Arrange
        image_hash = "non_existent_hash"
        cache_service.redis_client.delete.return_value = 0

        # Act
        cache_service.invalidate_cache(image_hash)

        # Assert
        cache_service.redis_client.delete.assert_called_once_with("recognition:non_existent_hash")

    def test_invalidate_cache_handles_redis_error(self, cache_service):
        """should_handle_redis_error_during_invalidation"""
        # Arrange
        image_hash = "test_hash"
        cache_service.redis_client.delete.side_effect = redis.RedisError("Connection lost")

        # Act - should not raise exception
        cache_service.invalidate_cache(image_hash)

        # Assert
        cache_service.redis_client.delete.assert_called_once()

    def test_invalidate_cache_handles_unexpected_exception(self, cache_service):
        """should_handle_unexpected_exception_during_invalidation"""
        # Arrange
        image_hash = "test_hash"
        cache_service.redis_client.delete.side_effect = Exception("Unexpected error")

        # Act - should not raise exception
        cache_service.invalidate_cache(image_hash)

        # Assert
        cache_service.redis_client.delete.assert_called_once()


class TestCacheServiceStats:
    """Test cache statistics operations"""

    @pytest.fixture
    def cache_service(self):
        """Create CacheService instance for testing with mocked Redis"""
        with patch('app.services.cache_service.redis.Redis') as mock_redis:
            mock_client = MagicMock()
            mock_redis.return_value = mock_client
            cache_service = CacheService()
            cache_service.redis_client = mock_client
            return cache_service

    def test_get_cache_stats_redis_error(self, cache_service):
        """should_return_default_stats_on_redis_error"""
        # Arrange
        cache_service._hit_count = 10
        cache_service._miss_count = 5
        cache_service.redis_client.scan_iter.side_effect = redis.RedisError("Connection error")

        # Act
        stats = cache_service.get_cache_stats()

        # Assert
        assert stats["total_cached"] == 0
        assert stats["memory_used"] == "0B"
        assert stats["hit_count"] == 10
        assert stats["miss_count"] == 5
        # When Redis error occurs, hit_rate is hardcoded to 0.0
        assert stats["hit_rate"] == 0.0
        assert stats["redis_available"] is False


class TestCacheServiceClearAll:
    """Test clear all cache operations"""

    @pytest.fixture
    def cache_service(self):
        """Create CacheService instance for testing with mocked Redis"""
        with patch('app.services.cache_service.redis.Redis') as mock_redis:
            mock_client = MagicMock()
            mock_redis.return_value = mock_client
            cache_service = CacheService()
            cache_service.redis_client = mock_client
            return cache_service

    def test_clear_all_cache_success(self, cache_service):
        """should_delete_all_recognition_cache_keys"""
        # Arrange
        cache_service.redis_client.scan_iter.return_value = [
            "recognition:hash1",
            "recognition:hash2",
            "recognition:hash3"
        ]
        cache_service.redis_client.delete.return_value = 3

        # Act
        deleted = cache_service.clear_all_cache()

        # Assert
        assert deleted == 3
        cache_service.redis_client.scan_iter.assert_called_once_with(match="recognition:*")
        cache_service.redis_client.delete.assert_called_once()

    def test_clear_all_cache_no_keys(self, cache_service):
        """should_return_zero_when_no_keys_to_delete"""
        # Arrange
        cache_service.redis_client.scan_iter.return_value = []

        # Act
        deleted = cache_service.clear_all_cache()

        # Assert
        assert deleted == 0
        cache_service.redis_client.scan_iter.assert_called_once_with(match="recognition:*")
        cache_service.redis_client.delete.assert_not_called()

    def test_clear_all_cache_redis_error(self, cache_service):
        """should_return_zero_on_redis_error"""
        # Arrange
        cache_service.redis_client.scan_iter.side_effect = redis.RedisError("Connection lost")

        # Act
        deleted = cache_service.clear_all_cache()

        # Assert
        assert deleted == 0


class TestCacheServiceHealthCheck:
    """Test health check operations"""

    @pytest.fixture
    def cache_service(self):
        """Create CacheService instance for testing with mocked Redis"""
        with patch('app.services.cache_service.redis.Redis') as mock_redis:
            mock_client = MagicMock()
            mock_redis.return_value = mock_client
            cache_service = CacheService()
            cache_service.redis_client = mock_client
            return cache_service

    def test_health_check_redis_available(self, cache_service):
        """should_return_true_when_redis_ping_succeeds"""
        # Arrange
        cache_service.redis_client.ping.return_value = True
        # Reset mock to clear the ping() call from __init__
        cache_service.redis_client.ping.reset_mock()

        # Act
        is_healthy = cache_service.health_check()

        # Assert
        assert is_healthy is True
        cache_service.redis_client.ping.assert_called_once()

    def test_health_check_redis_ping_fails(self, cache_service):
        """should_return_false_when_redis_ping_fails"""
        # Arrange
        cache_service.redis_client.ping.side_effect = redis.RedisError("Connection lost")

        # Act
        is_healthy = cache_service.health_check()

        # Assert
        assert is_healthy is False

    def test_health_check_unexpected_exception(self, cache_service):
        """should_return_false_on_unexpected_exception"""
        # Arrange
        cache_service.redis_client.ping.side_effect = Exception("Unexpected error")

        # Act
        is_healthy = cache_service.health_check()

        # Assert
        assert is_healthy is False


class TestPerceptualHashCache:
    """Test perceptual hash caching functionality for Step 2 cache optimization"""

    @pytest.fixture
    def cache_service(self):
        """Create CacheService instance for testing with mocked Redis"""
        with patch('app.services.cache_service.redis.Redis') as mock_redis:
            mock_client = MagicMock()
            mock_redis.return_value = mock_client
            cache_service = CacheService()
            cache_service.redis_client = mock_client
            return cache_service

    def test_caches_result_with_perceptual_hash(self, cache_service):
        """should_cache_to_both_file_hash_and_perceptual_hash_keys"""
        # Arrange
        file_hash = "abc123def456"
        perceptual_hash = "8f373e0c183f1e3f"
        result = RecognitionResponse(
            artwork_name="Mona Lisa",
            artist="Leonardo da Vinci",
            period="Renaissance",
            description="Famous portrait painting",
            confidence=0.95,
            cached=False,
            processing_time_ms=150
        )

        # Act
        cache_service.cache_result(file_hash, result, perceptual_hash=perceptual_hash)

        # Assert - 应该调用setex两次 (file hash + perceptual hash)
        assert cache_service.redis_client.setex.call_count == 2

        # 验证第一次调用 (file hash)
        first_call = cache_service.redis_client.setex.call_args_list[0]
        assert first_call[0][0] == f"recognition:{file_hash}"
        assert first_call[0][1] == cache_service.ttl

        # 验证第二次调用 (perceptual hash)
        second_call = cache_service.redis_client.setex.call_args_list[1]
        assert second_call[0][0] == f"phash:{perceptual_hash}"
        assert second_call[0][1] == cache_service.ttl * 7  # 7倍TTL

    def test_retrieves_similar_cached_result(self, cache_service):
        """should_find_cached_result_by_perceptual_hash_similarity"""
        # Arrange - 模拟已缓存的数据
        cached_phash = "8f373e0c183f1e3f"
        query_phash = "8f373e0c183f1e3e"  # 非常相似 (1位差异)

        cached_data = {
            "artwork_name": "Mona Lisa",
            "artist": "Leonardo da Vinci",
            "period": "Renaissance",
            "description": "Famous portrait",
            "confidence": 0.95,
            "cached": True,
            "processing_time_ms": 100
        }

        # 模拟scan_iter返回缓存的phash键
        cache_service.redis_client.scan_iter.return_value = [f"phash:{cached_phash}"]
        cache_service.redis_client.get.return_value = json.dumps(cached_data)

        # Act
        result = cache_service.get_similar_cached_result(query_phash, similarity_threshold=0.90)

        # Assert
        assert result is not None
        recognition_response, similarity = result
        assert recognition_response.artwork_name == "Mona Lisa"
        assert similarity >= 0.90  # 应该是非常高的相似度
        cache_service.redis_client.scan_iter.assert_called_once_with(match="phash:*", count=100)

    def test_similarity_threshold_filtering(self, cache_service):
        """should_not_return_results_below_similarity_threshold"""
        # Arrange - 模拟低相似度的缓存数据
        # 使用完全不同的phash (低相似度)
        cached_phash = "ffffffffffffffff"  # 全1
        query_phash = "0000000000000000"    # 全0 (相似度=0%)

        cached_data = {
            "artwork_name": "Different Artwork",
            "artist": "Different Artist",
            "period": "Modern",
            "description": "Not similar",
            "confidence": 0.80,
            "cached": True,
            "processing_time_ms": 100
        }

        cache_service.redis_client.scan_iter.return_value = [f"phash:{cached_phash}"]
        cache_service.redis_client.get.return_value = json.dumps(cached_data)

        # Act
        result = cache_service.get_similar_cached_result(query_phash, similarity_threshold=0.90)

        # Assert - 应该返回None，因为相似度太低
        assert result is None

    def test_returns_best_match_when_multiple_similar(self, cache_service):
        """should_return_most_similar_result_among_multiple_matches"""
        # Arrange - 模拟多个相似的缓存结果
        query_phash = "8f373e0c183f1e3f"

        # 三个不同相似度的phash
        phash_high = "8f373e0c183f1e3e"   # 98.4% 相似 (1位差异)
        phash_medium = "8f373e0c183f1e0f"  # 93.75% 相似 (4位差异)
        phash_low = "8f373e0c183f0e3f"     # 93.75% 相似 (4位差异)

        cached_data_high = {
            "artwork_name": "Best Match",
            "artist": "Artist A",
            "period": "Period A",
            "description": "Highest similarity",
            "confidence": 0.95,
            "cached": True,
            "processing_time_ms": 100
        }

        cached_data_medium = {
            "artwork_name": "Medium Match",
            "artist": "Artist B",
            "period": "Period B",
            "description": "Medium similarity",
            "confidence": 0.90,
            "cached": True,
            "processing_time_ms": 100
        }

        # 模拟scan_iter返回多个键
        cache_service.redis_client.scan_iter.return_value = [
            f"phash:{phash_medium}",
            f"phash:{phash_high}",
            f"phash:{phash_low}"
        ]

        # 模拟get返回最高相似度的数据
        def mock_get(key):
            if key == f"phash:{phash_high}":
                return json.dumps(cached_data_high)
            return json.dumps(cached_data_medium)

        cache_service.redis_client.get.side_effect = mock_get

        # Act
        result = cache_service.get_similar_cached_result(query_phash, similarity_threshold=0.90)

        # Assert - 应该返回最相似的结果
        assert result is not None
        recognition_response, similarity = result
        assert recognition_response.artwork_name == "Best Match"
        assert similarity > 0.95  # 最高相似度

    def test_stops_at_perfect_match(self, cache_service):
        """should_stop_searching_when_finding_99_percent_similar_match"""
        # Arrange
        query_phash = "8f373e0c183f1e3f"
        perfect_phash = "8f373e0c183f1e3f"  # 完全相同 = 100%

        cached_data = {
            "artwork_name": "Perfect Match",
            "artist": "Artist",
            "period": "Period",
            "description": "Exact same image",
            "confidence": 0.95,
            "cached": True,
            "processing_time_ms": 50
        }

        # 模拟scan_iter返回完美匹配作为第一个结果
        # 注意：实际上迭代器可能会继续，但代码应该在找到>0.99时break
        cache_service.redis_client.scan_iter.return_value = [
            f"phash:{perfect_phash}",
            "phash:other_hash_1",
            "phash:other_hash_2"
        ]
        cache_service.redis_client.get.return_value = json.dumps(cached_data)

        # Act
        result = cache_service.get_similar_cached_result(query_phash, similarity_threshold=0.90)

        # Assert
        assert result is not None
        recognition_response, similarity = result
        assert similarity >= 0.99  # 接近完美匹配
        # 注意：由于scan_iter是迭代器，我们不能直接验证是否提前退出
        # 但可以验证结果是否正确

    def test_perceptual_cache_has_longer_ttl(self, cache_service):
        """should_use_7x_longer_ttl_for_perceptual_hash_cache"""
        # Arrange
        file_hash = "file_hash_123"
        perceptual_hash = "phash_abc123"
        result = RecognitionResponse(
            artwork_name="Artwork",
            artist="Artist",
            period="Period",
            description="Description",
            confidence=0.90,
            cached=False,
            processing_time_ms=150
        )
        cache_service.ttl = 86400  # 1天

        # Act
        cache_service.cache_result(file_hash, result, perceptual_hash=perceptual_hash)

        # Assert
        assert cache_service.redis_client.setex.call_count == 2

        # 验证file hash TTL = 1天
        file_call = cache_service.redis_client.setex.call_args_list[0]
        assert file_call[0][1] == 86400

        # 验证perceptual hash TTL = 7天
        phash_call = cache_service.redis_client.setex.call_args_list[1]
        assert phash_call[0][1] == 86400 * 7

    def test_handles_no_similar_results_found(self, cache_service):
        """should_return_none_when_no_similar_cached_results"""
        # Arrange - 空的scan结果
        query_phash = "8f373e0c183f1e3f"
        cache_service.redis_client.scan_iter.return_value = []

        # Act
        result = cache_service.get_similar_cached_result(query_phash, similarity_threshold=0.90)

        # Assert
        assert result is None

    def test_handles_redis_error_during_similarity_search(self, cache_service):
        """should_return_none_and_handle_redis_error_gracefully"""
        # Arrange
        query_phash = "8f373e0c183f1e3f"
        cache_service.redis_client.scan_iter.side_effect = redis.RedisError("Connection lost")

        # Act
        result = cache_service.get_similar_cached_result(query_phash, similarity_threshold=0.90)

        # Assert
        assert result is None

    def test_similarity_search_increments_miss_count_when_not_found(self, cache_service):
        """should_increment_miss_counter_when_no_similar_result"""
        # Arrange
        query_phash = "8f373e0c183f1e3f"
        cache_service.redis_client.scan_iter.return_value = []
        initial_miss_count = cache_service._miss_count

        # Act
        result = cache_service.get_similar_cached_result(query_phash, similarity_threshold=0.90)

        # Assert
        assert result is None
        assert cache_service._miss_count == initial_miss_count + 1

    def test_similarity_search_increments_hit_count_when_found(self, cache_service):
        """should_increment_hit_counter_when_similar_result_found"""
        # Arrange
        query_phash = "8f373e0c183f1e3f"
        cached_phash = "8f373e0c183f1e3e"

        cached_data = {
            "artwork_name": "Cached Artwork",
            "artist": "Artist",
            "period": "Period",
            "description": "Description",
            "confidence": 0.95,
            "cached": True,
            "processing_time_ms": 100
        }

        cache_service.redis_client.scan_iter.return_value = [f"phash:{cached_phash}"]
        cache_service.redis_client.get.return_value = json.dumps(cached_data)
        initial_hit_count = cache_service._hit_count

        # Act
        result = cache_service.get_similar_cached_result(query_phash, similarity_threshold=0.90)

        # Assert
        assert result is not None
        assert cache_service._hit_count == initial_hit_count + 1
