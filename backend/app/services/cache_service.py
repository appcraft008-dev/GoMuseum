"""
Cache Service
Handles Redis caching for recognition results with perceptual hash similarity matching
"""

import json
import redis
from typing import Optional, List, Tuple
from app.core.config import settings
from app.schemas.recognition import RecognitionResponse
from app.services.image_service import ImageService
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

    def _get_perceptual_cache_key(self, perceptual_hash: str) -> str:
        """Generate cache key from perceptual hash"""
        return f"phash:{perceptual_hash}"

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

    def get_similar_cached_result(
        self, perceptual_hash: str, similarity_threshold: float = 0.90
    ) -> Optional[Tuple[RecognitionResponse, float]]:
        """
        Find cached recognition result by perceptual hash similarity.

        Searches for cached results with similar perceptual hashes (same artwork,
        different photo). This enables cache hits across different users photographing
        the same artwork.

        Args:
            perceptual_hash: Perceptual hash of the query image
            similarity_threshold: Minimum similarity (0.0-1.0). Default 0.90 (90%)

        Returns:
            Tuple of (RecognitionResponse, similarity_score) if found, None otherwise

        Example:
            User A takes photo of "Mona Lisa" → phash: "8f373e0c183f1e3f"
            User B takes photo of "Mona Lisa" → phash: "8f373e0c183f1e3e"
            get_similar_cached_result("8f373e0c183f1e3e", 0.90)
            → Returns cached result from User A (98.4% similar)
        """
        if not self.redis_client:
            logger.warning("Redis client not available, skipping similarity search")
            self._miss_count += 1
            return None

        try:
            # Scan all perceptual hash keys
            pattern = "phash:*"
            best_match = None
            best_similarity = 0.0

            for key in self.redis_client.scan_iter(match=pattern, count=100):
                # Extract cached perceptual hash from key
                cached_phash = key.split(":", 1)[1]

                # Calculate similarity
                similarity = ImageService.hash_similarity(
                    perceptual_hash, cached_phash
                )

                # Track best match
                if similarity >= similarity_threshold and similarity > best_similarity:
                    best_similarity = similarity
                    best_match = key

                # Perfect match found, stop searching
                if similarity >= 0.99:
                    break

            if best_match:
                cached_data = self.redis_client.get(best_match)
                if cached_data:
                    try:
                        data = json.loads(cached_data)
                        result = RecognitionResponse(**data)
                        logger.info(
                            f"Similarity cache hit! key: {best_match}, "
                            f"similarity: {best_similarity:.2%}"
                        )
                        self._hit_count += 1
                        return (result, best_similarity)
                    except json.JSONDecodeError as e:
                        logger.error(f"Failed to deserialize cached data: {str(e)}")

            logger.debug(
                f"No similar cached result found for phash: {perceptual_hash[:16]}..."
            )
            self._miss_count += 1
            return None

        except redis.RedisError as e:
            logger.error(f"Redis error during similarity search: {str(e)}")
            self._miss_count += 1
            return None
        except Exception as e:
            logger.error(f"Unexpected error during similarity search: {str(e)}")
            self._miss_count += 1
            return None

    def cache_result(
        self,
        image_hash: str,
        result: RecognitionResponse,
        perceptual_hash: Optional[str] = None,
    ) -> None:
        """
        Store recognition result in Redis cache (both file hash and perceptual hash)

        Args:
            image_hash: SHA256 hash of the image (file-based)
            result: Recognition result to cache
            perceptual_hash: Optional perceptual hash for similarity matching
        """
        if not self.redis_client:
            logger.warning("Redis client not available, skipping cache write")
            return

        try:
            # Convert Pydantic model to dict then to JSON
            data = result.model_dump(mode="json")
            json_data = json.dumps(data, default=str)

            # Cache by file hash (exact match)
            file_key = self._get_cache_key(image_hash)
            self.redis_client.setex(file_key, self.ttl, json_data)
            logger.info(f"Cached result for file key: {file_key} with TTL: {self.ttl}s")

            # Also cache by perceptual hash (similarity match)
            if perceptual_hash:
                phash_key = self._get_perceptual_cache_key(perceptual_hash)
                # Use longer TTL for perceptual hash (7 days)
                phash_ttl = self.ttl * 7
                self.redis_client.setex(phash_key, phash_ttl, json_data)
                logger.info(
                    f"Cached result for phash key: {phash_key} with TTL: {phash_ttl}s"
                )

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
