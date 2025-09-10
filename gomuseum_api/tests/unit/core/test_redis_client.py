"""
Unit tests for Redis client module
"""
import pytest
from unittest.mock import AsyncMock, Mock, patch, MagicMock
import json
import pickle
from redis.exceptions import RedisError, ConnectionError as RedisConnectionError

from app.core.redis_client import RedisClient, get_cache_key


@pytest.mark.asyncio
class TestRedisClient:
    """Test Redis client functionality"""
    
    @pytest.fixture
    def redis_client(self):
        """Create Redis client instance for testing"""
        return RedisClient()
    
    @pytest.fixture
    def mock_redis(self):
        """Mock Redis connection"""
        mock = AsyncMock()
        mock.ping.return_value = True
        return mock
    
    async def test_connect_success(self, redis_client):
        """Test successful Redis connection"""
        with patch('redis.asyncio.from_url') as mock_from_url:
            mock_redis = AsyncMock()
            mock_redis.ping.return_value = True
            mock_from_url.return_value = mock_redis
            
            await redis_client.connect()
            
            assert redis_client.redis is not None
            mock_from_url.assert_called_once()
            mock_redis.ping.assert_called_once()
    
    async def test_connect_failure(self, redis_client):
        """Test Redis connection failure"""
        with patch('redis.asyncio.from_url') as mock_from_url:
            mock_from_url.side_effect = RedisConnectionError("Connection failed")
            
            await redis_client.connect()
            
            assert redis_client.redis is None
    
    async def test_connect_ping_failure(self, redis_client):
        """Test Redis connection with ping failure"""
        with patch('redis.asyncio.from_url') as mock_from_url:
            mock_redis = AsyncMock()
            mock_redis.ping.side_effect = RedisError("Ping failed")
            mock_from_url.return_value = mock_redis
            
            await redis_client.connect()
            
            assert redis_client.redis is None
    
    async def test_disconnect(self, redis_client, mock_redis):
        """Test Redis disconnection"""
        redis_client.redis = mock_redis
        
        await redis_client.disconnect()
        
        mock_redis.close.assert_called_once()
    
    async def test_disconnect_no_connection(self, redis_client):
        """Test disconnection when no connection exists"""
        redis_client.redis = None
        
        # Should not raise exception
        await redis_client.disconnect()
    
    async def test_get_json_value(self, redis_client, mock_redis):
        """Test getting JSON value from cache"""
        redis_client.redis = mock_redis
        test_data = {"key": "value", "number": 123}
        mock_redis.get.return_value = json.dumps(test_data).encode('utf-8')
        
        result = await redis_client.get("test_key")
        
        assert result == test_data
        mock_redis.get.assert_called_once_with("test_key")
    
    async def test_get_pickle_value(self, redis_client, mock_redis):
        """Test getting pickled value from cache"""
        redis_client.redis = mock_redis
        test_data = {"complex": object(), "data": [1, 2, 3]}
        mock_redis.get.return_value = pickle.dumps(test_data)
        
        result = await redis_client.get("test_key")
        
        assert result == test_data
        mock_redis.get.assert_called_once_with("test_key")
    
    async def test_get_nonexistent_key(self, redis_client, mock_redis):
        """Test getting nonexistent key"""
        redis_client.redis = mock_redis
        mock_redis.get.return_value = None
        
        result = await redis_client.get("nonexistent_key")
        
        assert result is None
        mock_redis.get.assert_called_once_with("nonexistent_key")
    
    async def test_get_no_connection(self, redis_client):
        """Test get when Redis is not connected"""
        redis_client.redis = None
        
        result = await redis_client.get("test_key")
        
        assert result is None
    
    async def test_get_redis_error(self, redis_client, mock_redis):
        """Test get with Redis error"""
        redis_client.redis = mock_redis
        mock_redis.get.side_effect = RedisError("Redis error")
        
        result = await redis_client.get("test_key")
        
        assert result is None
    
    async def test_set_json_value(self, redis_client, mock_redis):
        """Test setting JSON value in cache"""
        redis_client.redis = mock_redis
        test_data = {"key": "value", "number": 123}
        
        with patch('app.core.config.settings') as mock_settings:
            mock_settings.cache_ttl = 3600
            
            result = await redis_client.set("test_key", test_data)
        
        assert result is True
        mock_redis.set.assert_called_once()
        args, kwargs = mock_redis.set.call_args
        assert args[0] == "test_key"
        assert json.loads(args[1].decode('utf-8')) == test_data
        assert kwargs['ex'] == 3600
    
    async def test_set_pickle_value(self, redis_client, mock_redis):
        """Test setting complex object (pickled) in cache"""
        redis_client.redis = mock_redis
        
        class CustomObject:
            def __init__(self, value):
                self.value = value
            
            def __eq__(self, other):
                return isinstance(other, CustomObject) and self.value == other.value
        
        test_data = CustomObject("test")
        
        with patch('app.core.config.settings') as mock_settings:
            mock_settings.cache_ttl = 3600
            
            result = await redis_client.set("test_key", test_data)
        
        assert result is True
        mock_redis.set.assert_called_once()
    
    async def test_set_with_custom_ttl(self, redis_client, mock_redis):
        """Test setting value with custom TTL"""
        redis_client.redis = mock_redis
        test_data = "test_value"
        custom_ttl = 1800  # 30 minutes
        
        result = await redis_client.set("test_key", test_data, ttl=custom_ttl)
        
        assert result is True
        args, kwargs = mock_redis.set.call_args
        assert kwargs['ex'] == custom_ttl
    
    async def test_set_no_connection(self, redis_client):
        """Test set when Redis is not connected"""
        redis_client.redis = None
        
        result = await redis_client.set("test_key", "test_value")
        
        assert result is False
    
    async def test_set_redis_error(self, redis_client, mock_redis):
        """Test set with Redis error"""
        redis_client.redis = mock_redis
        mock_redis.set.side_effect = RedisError("Redis error")
        
        result = await redis_client.set("test_key", "test_value")
        
        assert result is False
    
    async def test_delete_existing_key(self, redis_client, mock_redis):
        """Test deleting existing key"""
        redis_client.redis = mock_redis
        mock_redis.delete.return_value = 1  # Key deleted
        
        result = await redis_client.delete("test_key")
        
        assert result is True
        mock_redis.delete.assert_called_once_with("test_key")
    
    async def test_delete_nonexistent_key(self, redis_client, mock_redis):
        """Test deleting nonexistent key"""
        redis_client.redis = mock_redis
        mock_redis.delete.return_value = 0  # No key deleted
        
        result = await redis_client.delete("nonexistent_key")
        
        assert result is False
    
    async def test_delete_no_connection(self, redis_client):
        """Test delete when Redis is not connected"""
        redis_client.redis = None
        
        result = await redis_client.delete("test_key")
        
        assert result is False
    
    async def test_delete_redis_error(self, redis_client, mock_redis):
        """Test delete with Redis error"""
        redis_client.redis = mock_redis
        mock_redis.delete.side_effect = RedisError("Redis error")
        
        result = await redis_client.delete("test_key")
        
        assert result is False
    
    async def test_exists_key_exists(self, redis_client, mock_redis):
        """Test checking if key exists when it does"""
        redis_client.redis = mock_redis
        mock_redis.exists.return_value = 1
        
        result = await redis_client.exists("test_key")
        
        assert result is True
        mock_redis.exists.assert_called_once_with("test_key")
    
    async def test_exists_key_not_exists(self, redis_client, mock_redis):
        """Test checking if key exists when it doesn't"""
        redis_client.redis = mock_redis
        mock_redis.exists.return_value = 0
        
        result = await redis_client.exists("test_key")
        
        assert result is False
    
    async def test_exists_no_connection(self, redis_client):
        """Test exists when Redis is not connected"""
        redis_client.redis = None
        
        result = await redis_client.exists("test_key")
        
        assert result is False
    
    async def test_exists_redis_error(self, redis_client, mock_redis):
        """Test exists with Redis error"""
        redis_client.redis = mock_redis
        mock_redis.exists.side_effect = RedisError("Redis error")
        
        result = await redis_client.exists("test_key")
        
        assert result is False
    
    async def test_increment_counter(self, redis_client, mock_redis):
        """Test incrementing counter"""
        redis_client.redis = mock_redis
        mock_redis.incr.return_value = 5
        
        result = await redis_client.increment("counter_key", 2)
        
        assert result == 5
        mock_redis.incr.assert_called_once_with("counter_key", 2)
    
    async def test_increment_default_amount(self, redis_client, mock_redis):
        """Test incrementing counter with default amount"""
        redis_client.redis = mock_redis
        mock_redis.incr.return_value = 1
        
        result = await redis_client.increment("counter_key")
        
        assert result == 1
        mock_redis.incr.assert_called_once_with("counter_key", 1)
    
    async def test_increment_no_connection(self, redis_client):
        """Test increment when Redis is not connected"""
        redis_client.redis = None
        
        result = await redis_client.increment("counter_key")
        
        assert result is None
    
    async def test_increment_redis_error(self, redis_client, mock_redis):
        """Test increment with Redis error"""
        redis_client.redis = mock_redis
        mock_redis.incr.side_effect = RedisError("Redis error")
        
        result = await redis_client.increment("counter_key")
        
        assert result is None
    
    async def test_get_stats_success(self, redis_client, mock_redis):
        """Test getting Redis statistics"""
        redis_client.redis = mock_redis
        mock_info = {
            "connected_clients": 10,
            "used_memory_human": "1.5M",
            "keyspace_hits": 1000,
            "keyspace_misses": 50,
            "total_commands_processed": 5000
        }
        mock_redis.info.return_value = mock_info
        
        result = await redis_client.get_stats()
        
        assert result == {
            "connected_clients": 10,
            "used_memory": "1.5M",
            "keyspace_hits": 1000,
            "keyspace_misses": 50,
            "total_commands_processed": 5000
        }
        mock_redis.info.assert_called_once()
    
    async def test_get_stats_no_connection(self, redis_client):
        """Test get stats when Redis is not connected"""
        redis_client.redis = None
        
        result = await redis_client.get_stats()
        
        assert result == {}
    
    async def test_get_stats_redis_error(self, redis_client, mock_redis):
        """Test get stats with Redis error"""
        redis_client.redis = mock_redis
        mock_redis.info.side_effect = RedisError("Redis error")
        
        result = await redis_client.get_stats()
        
        assert result == {}
    
    async def test_get_stats_missing_fields(self, redis_client, mock_redis):
        """Test get stats with missing fields in Redis info"""
        redis_client.redis = mock_redis
        mock_redis.info.return_value = {"connected_clients": 5}  # Missing other fields
        
        result = await redis_client.get_stats()
        
        expected = {
            "connected_clients": 5,
            "used_memory": "0B",
            "keyspace_hits": 0,
            "keyspace_misses": 0,
            "total_commands_processed": 0
        }
        assert result == expected


class TestCacheKeyGeneration:
    """Test cache key generation utility"""
    
    def test_get_cache_key_basic(self):
        """Test basic cache key generation"""
        key = get_cache_key("user", "123")
        
        assert key.startswith("gomuseum:user:")
        assert len(key.split(":")) == 3  # gomuseum:user:hash
        assert len(key.split(":")[-1]) == 16  # Hash should be 16 characters
    
    def test_get_cache_key_multiple_args(self):
        """Test cache key generation with multiple arguments"""
        key = get_cache_key("recognition", "user_123", "image_456", "v1")
        
        assert key.startswith("gomuseum:recognition:")
        assert len(key.split(":")) == 3
    
    def test_get_cache_key_consistency(self):
        """Test that same arguments produce same key"""
        key1 = get_cache_key("user", "123", "profile")
        key2 = get_cache_key("user", "123", "profile")
        
        assert key1 == key2
    
    def test_get_cache_key_different_args_different_keys(self):
        """Test that different arguments produce different keys"""
        key1 = get_cache_key("user", "123")
        key2 = get_cache_key("user", "456")
        
        assert key1 != key2
    
    def test_get_cache_key_collision_prevention(self):
        """Test that potential collisions are prevented"""
        # These could potentially collide if not properly hashed
        key1 = get_cache_key("user", "12", "3")
        key2 = get_cache_key("user", "1", "23")
        
        assert key1 != key2
    
    def test_get_cache_key_special_characters(self):
        """Test cache key generation with special characters"""
        key = get_cache_key("user", "user@example.com", "data:image/png")
        
        assert key.startswith("gomuseum:user:")
        assert len(key.split(":")) == 3
    
    def test_get_cache_key_empty_args(self):
        """Test cache key generation with empty arguments"""
        key = get_cache_key("prefix")
        
        assert key.startswith("gomuseum:prefix:")
        assert len(key.split(":")) == 3
    
    def test_get_cache_key_unicode(self):
        """Test cache key generation with unicode characters"""
        key = get_cache_key("artwork", "梵高", "向日葵")
        
        assert key.startswith("gomuseum:artwork:")
        assert len(key.split(":")) == 3


@pytest.mark.asyncio
@pytest.mark.integration
class TestRedisClientIntegration:
    """Integration tests for Redis client (requires Redis server)"""
    
    @pytest.fixture
    async def connected_redis_client(self):
        """Redis client connected to test instance"""
        client = RedisClient()
        
        # Try to connect to test Redis instance
        try:
            await client.connect()
            if client.redis is None:
                pytest.skip("Redis server not available for integration tests")
            yield client
        finally:
            await client.disconnect()
    
    async def test_round_trip_json_data(self, connected_redis_client):
        """Test storing and retrieving JSON data"""
        test_data = {"name": "test", "value": 123, "items": [1, 2, 3]}
        key = "test:json:data"
        
        # Set data
        result = await connected_redis_client.set(key, test_data, ttl=60)
        assert result is True
        
        # Get data
        retrieved = await connected_redis_client.get(key)
        assert retrieved == test_data
        
        # Clean up
        await connected_redis_client.delete(key)
    
    async def test_round_trip_pickle_data(self, connected_redis_client):
        """Test storing and retrieving pickled data"""
        class TestClass:
            def __init__(self, value):
                self.value = value
            
            def __eq__(self, other):
                return isinstance(other, TestClass) and self.value == other.value
        
        test_data = TestClass("test_value")
        key = "test:pickle:data"
        
        # Set data
        result = await connected_redis_client.set(key, test_data, ttl=60)
        assert result is True
        
        # Get data
        retrieved = await connected_redis_client.get(key)
        assert retrieved == test_data
        
        # Clean up
        await connected_redis_client.delete(key)
    
    async def test_key_expiration(self, connected_redis_client):
        """Test key expiration"""
        key = "test:expiring:key"
        
        # Set with short TTL
        result = await connected_redis_client.set(key, "test_value", ttl=1)
        assert result is True
        
        # Should exist immediately
        exists = await connected_redis_client.exists(key)
        assert exists is True
        
        # Wait for expiration
        import asyncio
        await asyncio.sleep(1.1)
        
        # Should be expired
        exists = await connected_redis_client.exists(key)
        assert exists is False
    
    async def test_counter_operations(self, connected_redis_client):
        """Test counter increment operations"""
        key = "test:counter"
        
        # First increment
        result = await connected_redis_client.increment(key, 5)
        assert result == 5
        
        # Second increment
        result = await connected_redis_client.increment(key, 3)
        assert result == 8
        
        # Default increment
        result = await connected_redis_client.increment(key)
        assert result == 9
        
        # Clean up
        await connected_redis_client.delete(key)