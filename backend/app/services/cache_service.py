"""
Cache Service
Handles Redis caching for recognition results
"""

import json
import redis
from typing import Optional
from app.core.config import settings
from app.schemas.recognition import RecognitionResponse
import logging

logger = logging.getLogger(__name__)


class CacheService:
    """Service for managing Redis cache"""

    def __init__(self):
        """Initialize Redis connection"""
        try:
            self.redis_client = redis.Redis(
                host=settings.REDIS_HOST,
                port=settings.REDIS_PORT,
                db=settings.REDIS_DB,
                password=settings.REDIS_PASSWORD,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5,
            )
            # Test connection
            self.redis_client.ping()
            logger.info("Redis connection established")
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {str(e)}")
            # Don't raise exception, allow graceful degradation
            self.redis_client = None

        self.ttl = settings.CACHE_TTL_SECONDS
        self._hit_count = 0
        self._miss_count = 0

    def _get_cache_key(self, image_hash: str) -> str:
        """Generate cache key from image hash"""
        return f"recognition:{image_hash}"

    def get_cached_result(self, image_hash: str) -> Optional[RecognitionResponse]:
        """
        Retrieve cached recognition result from Redis

        Args:
            image_hash: SHA256 hash of the image

        Returns:
            RecognitionResponse if found, None otherwise
        """
        if not self.redis_client:
            logger.warning("Redis client not available, skipping cache lookup")
            self._miss_count += 1
            return None

        try:
            key = self._get_cache_key(image_hash)
            cached_data = self.redis_client.get(key)

            if cached_data:
                logger.info(f"Cache hit for key: {key}")
                self._hit_count += 1
                try:
                    data = json.loads(cached_data)
                    return RecognitionResponse(**data)
                except json.JSONDecodeError as e:
                    logger.error(f"Failed to deserialize cached data: {str(e)}")
                    # Invalidate corrupted cache entry
                    self.invalidate_cache(image_hash)
                    self._miss_count += 1
                    return None
            else:
                logger.debug(f"Cache miss for key: {key}")
                self._miss_count += 1
                return None

        except redis.RedisError as e:
            logger.error(f"Redis error during cache lookup: {str(e)}")
            self._miss_count += 1
            return None
        except Exception as e:
            logger.error(f"Unexpected error during cache lookup: {str(e)}")
            self._miss_count += 1
            return None

    def cache_result(self, image_hash: str, result: RecognitionResponse) -> None:
        """
        Store recognition result in Redis cache

        Args:
            image_hash: SHA256 hash of the image
            result: Recognition result to cache
        """
        if not self.redis_client:
            logger.warning("Redis client not available, skipping cache write")
            return

        try:
            key = self._get_cache_key(image_hash)
            # Convert Pydantic model to dict then to JSON
            data = result.model_dump(mode="json")
            json_data = json.dumps(data, default=str)

            self.redis_client.setex(key, self.ttl, json_data)
            logger.info(f"Cached result for key: {key} with TTL: {self.ttl}s")

        except redis.RedisError as e:
            logger.error(f"Redis error during cache write: {str(e)}")
            # Don't raise exception, cache write failure shouldn't break the app
        except Exception as e:
            logger.error(f"Unexpected error during cache write: {str(e)}")

    def invalidate_cache(self, image_hash: str) -> None:
        """
        Remove cached result from Redis

        Args:
            image_hash: SHA256 hash of the image
        """
        if not self.redis_client:
            return

        try:
            key = self._get_cache_key(image_hash)
            deleted = self.redis_client.delete(key)
            if deleted:
                logger.info(f"Invalidated cache for key: {key}")
            else:
                logger.debug(f"No cache entry found for key: {key}")
        except redis.RedisError as e:
            logger.error(f"Redis error during cache invalidation: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error during cache invalidation: {str(e)}")

    def get_cache_stats(self) -> dict:
        """
        Get cache statistics

        Returns:
            Dictionary with cache statistics
        """
        if not self.redis_client:
            return {
                "total_cached": 0,
                "memory_used": "0B",
                "hit_count": self._hit_count,
                "miss_count": self._miss_count,
                "hit_rate": 0.0,
                "redis_available": False,
            }

        try:
            # Count keys with our prefix
            pattern = "recognition:*"
            keys = list(self.redis_client.scan_iter(match=pattern))
            total_cached = len(keys)

            # Get memory info
            info = self.redis_client.info("memory")
            memory_used = info.get("used_memory_human", "0B")

            # Calculate hit rate
            total_requests = self._hit_count + self._miss_count
            hit_rate = self._hit_count / total_requests if total_requests > 0 else 0.0

            return {
                "total_cached": total_cached,
                "memory_used": memory_used,
                "hit_count": self._hit_count,
                "miss_count": self._miss_count,
                "hit_rate": hit_rate,
                "redis_available": True,
            }

        except redis.RedisError as e:
            logger.error(f"Redis error while getting stats: {str(e)}")
            return {
                "total_cached": 0,
                "memory_used": "0B",
                "hit_count": self._hit_count,
                "miss_count": self._miss_count,
                "hit_rate": 0.0,
                "redis_available": False,
            }

    def clear_all_cache(self) -> int:
        """
        Clear all recognition cache entries

        Returns:
            Number of keys deleted
        """
        if not self.redis_client:
            return 0

        try:
            pattern = "recognition:*"
            keys = list(self.redis_client.scan_iter(match=pattern))
            if keys:
                deleted = self.redis_client.delete(*keys)
                logger.info(f"Cleared {deleted} cache entries")
                return deleted
            return 0
        except redis.RedisError as e:
            logger.error(f"Redis error while clearing cache: {str(e)}")
            return 0

    def health_check(self) -> bool:
        """
        Check if Redis is available

        Returns:
            True if Redis is responsive
        """
        if not self.redis_client:
            return False

        try:
            self.redis_client.ping()
            return True
        except Exception:
            return False
