import asyncio
import hashlib
import json
import time
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, Optional, List, Union
from enum import Enum
import random

from .redis_client import redis_client, get_cache_key
from .logging import get_logger
from .metrics import track_cache_hit, track_cache_miss, increment_counter, set_gauge

logger = get_logger(__name__)


class CacheLevel(str, Enum):
    """Cache levels for multi-tier caching"""
    L1_MEMORY = "l1_memory"      # In-memory cache (fastest)
    L2_REDIS = "l2_redis"        # Redis cache (fast)
    L3_DATABASE = "l3_database"  # Database cache (slowest)


class CacheStrategy(str, Enum):
    """Cache invalidation strategies"""
    TTL = "ttl"                  # Time-based expiration
    LRU = "lru"                  # Least Recently Used
    LFU = "lfu"                  # Least Frequently Used
    WRITE_THROUGH = "write_through"  # Write to cache and storage simultaneously
    WRITE_BACK = "write_back"    # Write to cache first, storage later
    REFRESH_AHEAD = "refresh_ahead"  # Refresh before expiration


class CacheEntry:
    """Cache entry with metadata"""
    
    def __init__(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None,
        tags: Optional[List[str]] = None,
        priority: int = 1
    ):
        self.key = key
        self.value = value
        self.ttl = ttl
        self.tags = tags or []
        self.priority = priority
        self.created_at = datetime.now(timezone.utc)
        self.accessed_at = datetime.now(timezone.utc)
        self.access_count = 0
        self.size = self._calculate_size()
    
    def _calculate_size(self) -> int:
        """Estimate memory size of the cache entry"""
        try:
            if isinstance(self.value, (dict, list)):
                return len(json.dumps(self.value, default=str))
            else:
                return len(str(self.value))
        except:
            return 1024  # Default size estimate
    
    def is_expired(self) -> bool:
        """Check if the cache entry is expired"""
        if not self.ttl:
            return False
        
        age = datetime.now(timezone.utc) - self.created_at
        return age.total_seconds() > self.ttl
    
    def access(self):
        """Mark entry as accessed"""
        self.accessed_at = datetime.now(timezone.utc)
        self.access_count += 1
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            "key": self.key,
            "value": self.value,
            "ttl": self.ttl,
            "tags": self.tags,
            "priority": self.priority,
            "created_at": self.created_at.isoformat(),
            "accessed_at": self.accessed_at.isoformat(),
            "access_count": self.access_count,
            "size": self.size
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CacheEntry":
        """Create from dictionary"""
        entry = cls(
            key=data["key"],
            value=data["value"],
            ttl=data.get("ttl"),
            tags=data.get("tags", []),
            priority=data.get("priority", 1)
        )
        entry.created_at = datetime.fromisoformat(data["created_at"])
        entry.accessed_at = datetime.fromisoformat(data["accessed_at"])
        entry.access_count = data.get("access_count", 0)
        entry.size = data.get("size", 0)
        return entry


class L1MemoryCache:
    """In-memory cache for fastest access"""
    
    def __init__(self, max_size: int = 1000, max_memory_mb: int = 100):
        self.cache: Dict[str, CacheEntry] = {}
        self.max_size = max_size
        self.max_memory_mb = max_memory_mb
        self.current_memory = 0
        
    async def get(self, key: str) -> Optional[Any]:
        """Get value from L1 cache"""
        entry = self.cache.get(key)
        
        if not entry:
            return None
        
        if entry.is_expired():
            await self.delete(key)
            return None
        
        entry.access()
        return entry.value
    
    async def set(
        self, 
        key: str, 
        value: Any, 
        ttl: Optional[int] = None,
        tags: Optional[List[str]] = None,
        priority: int = 1
    ) -> bool:
        """Set value in L1 cache"""
        entry = CacheEntry(key, value, ttl, tags, priority)
        
        # Check memory limits
        if self._would_exceed_limits(entry):
            await self._evict_entries()
        
        # Remove old entry if exists
        if key in self.cache:
            old_entry = self.cache[key]
            self.current_memory -= old_entry.size
        
        # Add new entry
        self.cache[key] = entry
        self.current_memory += entry.size
        
        return True
    
    async def delete(self, key: str) -> bool:
        """Delete value from L1 cache"""
        if key in self.cache:
            entry = self.cache.pop(key)
            self.current_memory -= entry.size
            return True
        return False
    
    async def clear(self):
        """Clear all entries"""
        self.cache.clear()
        self.current_memory = 0
    
    def _would_exceed_limits(self, entry: CacheEntry) -> bool:
        """Check if adding entry would exceed limits"""
        new_memory_mb = (self.current_memory + entry.size) / (1024 * 1024)
        return (
            len(self.cache) >= self.max_size or
            new_memory_mb > self.max_memory_mb
        )
    
    async def _evict_entries(self):
        """Evict entries using LRU strategy"""
        if not self.cache:
            return
        
        # Sort by last accessed time (LRU)
        sorted_entries = sorted(
            self.cache.items(),
            key=lambda x: x[1].accessed_at
        )
        
        # Remove oldest 20% of entries
        evict_count = max(1, len(sorted_entries) // 5)
        
        for i in range(evict_count):
            key, entry = sorted_entries[i]
            await self.delete(key)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get L1 cache statistics"""
        return {
            "size": len(self.cache),
            "max_size": self.max_size,
            "memory_mb": self.current_memory / (1024 * 1024),
            "max_memory_mb": self.max_memory_mb,
            "utilization_percent": (len(self.cache) / self.max_size) * 100
        }


class AdvancedCacheManager:
    """Advanced multi-level cache manager with intelligent strategies"""
    
    def __init__(self):
        self.l1_cache = L1MemoryCache()
        self.cache_hits = {"l1": 0, "l2": 0, "total": 0}
        self.cache_misses = 0
        
        # Cache warming configuration
        self.warm_cache_enabled = True
        self.warm_cache_patterns = [
            "recognition:*",  # Pre-cache popular recognition results
            "user:quota:*",   # Cache user quota information
        ]
        
        # Cache refresh configuration
        self.refresh_ahead_enabled = True
        self.refresh_threshold = 0.8  # Refresh when 80% of TTL elapsed
    
    async def get(
        self, 
        key: str, 
        default: Any = None,
        warm_on_miss: bool = True
    ) -> Any:
        """Get value from multi-level cache"""
        
        # Try L1 cache first
        value = await self.l1_cache.get(key)
        if value is not None:
            self.cache_hits["l1"] += 1
            self.cache_hits["total"] += 1
            track_cache_hit()
            return value
        
        # Try L2 (Redis) cache
        redis_key = get_cache_key("cache", key)
        value = await redis_client.get(redis_key)
        
        if value is not None:
            self.cache_hits["l2"] += 1
            self.cache_hits["total"] += 1
            track_cache_hit()
            
            # Promote to L1 cache
            await self.l1_cache.set(key, value, ttl=300)  # 5 minutes in L1
            
            return value
        
        # Cache miss
        self.cache_misses += 1
        track_cache_miss()
        
        # Trigger cache warming if enabled
        if warm_on_miss and self.warm_cache_enabled:
            asyncio.create_task(self._warm_related_cache(key))
        
        return default
    
    async def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None,
        tags: Optional[List[str]] = None,
        priority: int = 1,
        strategy: CacheStrategy = CacheStrategy.WRITE_THROUGH
    ) -> bool:
        """Set value in multi-level cache with strategy"""
        
        success = True
        
        if strategy == CacheStrategy.WRITE_THROUGH:
            # Write to both L1 and L2 simultaneously
            l1_task = self.l1_cache.set(key, value, ttl, tags, priority)
            l2_task = self._set_l2_cache(key, value, ttl, tags)
            
            l1_success, l2_success = await asyncio.gather(l1_task, l2_task)
            success = l1_success and l2_success
            
        elif strategy == CacheStrategy.WRITE_BACK:
            # Write to L1 immediately, L2 later
            await self.l1_cache.set(key, value, ttl, tags, priority)
            asyncio.create_task(self._set_l2_cache(key, value, ttl, tags))
            
        elif strategy == CacheStrategy.REFRESH_AHEAD:
            # Set normally, but schedule refresh before expiration
            await self.l1_cache.set(key, value, ttl, tags, priority)
            await self._set_l2_cache(key, value, ttl, tags)
            
            if ttl and self.refresh_ahead_enabled:
                refresh_time = ttl * self.refresh_threshold
                asyncio.create_task(self._schedule_refresh(key, refresh_time))
        
        # Track cache operations
        increment_counter("cache_set_operations")
        
        return success
    
    async def delete(self, key: str) -> bool:
        """Delete from all cache levels"""
        l1_success = await self.l1_cache.delete(key)
        
        redis_key = get_cache_key("cache", key)
        l2_success = await redis_client.delete(redis_key)
        
        increment_counter("cache_delete_operations")
        
        return l1_success or l2_success
    
    async def delete_by_tags(self, tags: List[str]) -> int:
        """Delete all cache entries with specified tags"""
        deleted_count = 0
        
        # This would require tag indexing in a production system
        # For now, implement a basic pattern-based deletion
        
        for tag in tags:
            pattern_key = get_cache_key("cache", f"tag:{tag}:*")
            # In a real implementation, we'd use Redis SCAN with patterns
            
        increment_counter("cache_tag_delete_operations")
        
        return deleted_count
    
    async def warm_cache(self, patterns: Optional[List[str]] = None):
        """Warm cache with frequently accessed data"""
        if not self.warm_cache_enabled:
            return
        
        patterns = patterns or self.warm_cache_patterns
        
        logger.info(f"Starting cache warming with patterns: {patterns}")
        
        for pattern in patterns:
            try:
                await self._warm_pattern(pattern)
            except Exception as e:
                logger.error(f"Cache warming failed for pattern {pattern}: {e}")
        
        logger.info("Cache warming completed")
    
    async def _warm_pattern(self, pattern: str):
        """Warm cache for a specific pattern"""
        # This would require integration with your data sources
        # For recognition results, pre-compute popular image hashes
        # For user quotas, pre-load active users
        
        if pattern.startswith("recognition:"):
            await self._warm_recognition_cache()
        elif pattern.startswith("user:quota:"):
            await self._warm_user_quota_cache()
    
    async def _warm_recognition_cache(self):
        """Pre-warm recognition result cache"""
        # Example: Load popular artworks or recent recognition results
        popular_artworks = [
            "mona_lisa_hash",
            "starry_night_hash", 
            "the_scream_hash"
        ]
        
        for artwork_hash in popular_artworks:
            key = f"recognition:{artwork_hash}"
            # Check if already cached
            if await self.get(key, warm_on_miss=False) is None:
                # Load from database and cache
                # mock_result = await load_artwork_data(artwork_hash)
                mock_result = {"name": "Cached Artwork", "artist": "Famous Artist"}
                await self.set(key, mock_result, ttl=3600)
    
    async def _warm_user_quota_cache(self):
        """Pre-warm user quota cache"""
        # Example: Load quota for active users
        # This would integrate with your user service
        pass
    
    async def _warm_related_cache(self, missed_key: str):
        """Warm cache for keys related to the missed key"""
        # Intelligent cache warming based on access patterns
        # For example, if user:123:quota was missed, warm user:123:profile
        
        if "user:" in missed_key and ":quota" in missed_key:
            # Extract user ID and warm related data
            parts = missed_key.split(":")
            if len(parts) >= 2:
                user_id = parts[1]
                related_keys = [
                    f"user:{user_id}:profile",
                    f"user:{user_id}:settings",
                    f"user:{user_id}:history"
                ]
                
                for related_key in related_keys:
                    # Load and cache related data
                    pass
    
    async def _set_l2_cache(
        self, 
        key: str, 
        value: Any, 
        ttl: Optional[int] = None,
        tags: Optional[List[str]] = None
    ) -> bool:
        """Set value in L2 (Redis) cache"""
        redis_key = get_cache_key("cache", key)
        
        # Create cache entry with metadata
        cache_entry = {
            "value": value,
            "tags": tags or [],
            "created_at": datetime.now(timezone.utc).isoformat(),
            "accessed_at": datetime.now(timezone.utc).isoformat(),
            "access_count": 0
        }
        
        return await redis_client.set(redis_key, cache_entry, ttl)
    
    async def _schedule_refresh(self, key: str, delay: float):
        """Schedule cache refresh before expiration"""
        await asyncio.sleep(delay)
        
        # Check if key still exists and refresh if needed
        value = await self.get(key, warm_on_miss=False)
        if value is not None:
            # Trigger refresh from original data source
            # This would integrate with your data loading logic
            logger.info(f"Refreshing cache key: {key}")
    
    async def get_comprehensive_stats(self) -> Dict[str, Any]:
        """Get comprehensive cache statistics"""
        l1_stats = self.l1_cache.get_stats()
        
        # Redis stats
        redis_stats = await redis_client.get_stats() if redis_client.redis else {}
        
        # Hit rates
        total_requests = self.cache_hits["total"] + self.cache_misses
        hit_rate = (self.cache_hits["total"] / total_requests * 100) if total_requests > 0 else 0
        
        l1_hit_rate = (self.cache_hits["l1"] / total_requests * 100) if total_requests > 0 else 0
        l2_hit_rate = (self.cache_hits["l2"] / total_requests * 100) if total_requests > 0 else 0
        
        stats = {
            "overall": {
                "hit_rate_percent": hit_rate,
                "total_hits": self.cache_hits["total"],
                "total_misses": self.cache_misses,
                "total_requests": total_requests
            },
            "l1_memory": {
                **l1_stats,
                "hit_rate_percent": l1_hit_rate,
                "hits": self.cache_hits["l1"]
            },
            "l2_redis": {
                **redis_stats,
                "hit_rate_percent": l2_hit_rate,
                "hits": self.cache_hits["l2"]
            },
            "configuration": {
                "warm_cache_enabled": self.warm_cache_enabled,
                "refresh_ahead_enabled": self.refresh_ahead_enabled,
                "refresh_threshold": self.refresh_threshold
            }
        }
        
        # Update metrics
        set_gauge("cache_hit_rate_percent", hit_rate)
        set_gauge("cache_l1_utilization_percent", l1_stats["utilization_percent"])
        set_gauge("cache_l1_memory_mb", l1_stats["memory_mb"])
        
        return stats
    
    async def optimize_cache(self):
        """Perform cache optimization tasks"""
        logger.info("Starting cache optimization")
        
        try:
            # Clear expired entries from L1
            expired_keys = []
            for key, entry in self.l1_cache.cache.items():
                if entry.is_expired():
                    expired_keys.append(key)
            
            for key in expired_keys:
                await self.l1_cache.delete(key)
            
            if expired_keys:
                logger.info(f"Cleaned up {len(expired_keys)} expired L1 cache entries")
            
            # Perform cache warming
            await self.warm_cache()
            
            # Update cache statistics
            stats = await self.get_comprehensive_stats()
            logger.info(f"Cache optimization completed. Hit rate: {stats['overall']['hit_rate_percent']:.1f}%")
            
        except Exception as e:
            logger.error(f"Cache optimization failed: {e}")


# Global cache manager instance
cache_manager = AdvancedCacheManager()


# Convenience functions
async def get_cached(key: str, default: Any = None) -> Any:
    """Get value from cache - convenience function"""
    return await cache_manager.get(key, default)


async def set_cached(
    key: str, 
    value: Any, 
    ttl: Optional[int] = None,
    tags: Optional[List[str]] = None,
    strategy: CacheStrategy = CacheStrategy.WRITE_THROUGH
) -> bool:
    """Set value in cache - convenience function"""
    return await cache_manager.set(key, value, ttl, tags, strategy=strategy)


async def delete_cached(key: str) -> bool:
    """Delete value from cache - convenience function"""
    return await cache_manager.delete(key)


async def get_cache_stats() -> Dict[str, Any]:
    """Get cache statistics - convenience function"""
    return await cache_manager.get_comprehensive_stats()


# Cache optimization task
async def start_cache_optimization():
    """Start periodic cache optimization"""
    while True:
        try:
            await cache_manager.optimize_cache()
            await asyncio.sleep(3600)  # Run every hour
        except Exception as e:
            logger.error(f"Cache optimization task error: {e}")
            await asyncio.sleep(1800)  # Wait 30 minutes on error