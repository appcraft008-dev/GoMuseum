import asyncio
import hashlib
import json
import time
import math
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
    """Cache entry with metadata and intelligent scoring"""
    
    def __init__(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None,
        tags: Optional[List[str]] = None,
        priority: int = 1,
        museum_id: Optional[str] = None,
        is_popular: bool = False
    ):
        self.key = key
        self.value = value
        self.ttl = ttl
        self.tags = tags or []
        self.priority = priority
        self.museum_id = museum_id
        self.is_popular = is_popular
        self.created_at = datetime.now(timezone.utc)
        self.accessed_at = datetime.now(timezone.utc)
        self.access_count = 0
        self.size = self._calculate_size()
        self.hit_score = 0.0  # Intelligent cache score
    
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
        """Mark entry as accessed and update hit score"""
        self.accessed_at = datetime.now(timezone.utc)
        self.access_count += 1
        self.hit_score = self._calculate_intelligent_score()
    
    def _calculate_intelligent_score(self, current_museum: Optional[str] = None) -> float:
        """
        Calculate intelligent cache score based on multiple factors.
        Higher score = more valuable to keep in cache.
        Based on architecture document 4.3.2 requirements.
        """
        now = datetime.now(timezone.utc)
        
        # Age factor (hours since last access)
        age_hours = (now - self.accessed_at).total_seconds() / 3600
        age_factor = 1.0 / (age_hours + 1)  # Newer = higher score
        
        # Frequency factor (access count)
        frequency_factor = self.access_count
        
        # Size factor (smaller files are preferred)
        size_kb = self.size / 1024
        size_factor = 1.0 / math.log(size_kb + 1) if size_kb > 0 else 1.0
        
        # Popularity weight (hot artworks get higher score)
        popularity_weight = 10.0 if self.is_popular else 1.0
        
        # Proximity weight (same museum content gets higher score)
        proximity_weight = 5.0 if self.museum_id and self.museum_id == current_museum else 1.0
        
        # Priority factor
        priority_factor = self.priority
        
        # Combined intelligent score
        # Formula: (frequency * popularity * proximity * priority * age) / log(size + 1)
        score = (frequency_factor * popularity_weight * proximity_weight * priority_factor * age_factor) / max(size_factor, 0.1)
        
        return score
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            "key": self.key,
            "value": self.value,
            "ttl": self.ttl,
            "tags": self.tags,
            "priority": self.priority,
            "museum_id": self.museum_id,
            "is_popular": self.is_popular,
            "created_at": self.created_at.isoformat(),
            "accessed_at": self.accessed_at.isoformat(),
            "access_count": self.access_count,
            "size": self.size,
            "hit_score": self.hit_score
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CacheEntry":
        """Create from dictionary"""
        entry = cls(
            key=data["key"],
            value=data["value"],
            ttl=data.get("ttl"),
            tags=data.get("tags", []),
            priority=data.get("priority", 1),
            museum_id=data.get("museum_id"),
            is_popular=data.get("is_popular", False)
        )
        entry.created_at = datetime.fromisoformat(data["created_at"])
        entry.accessed_at = datetime.fromisoformat(data["accessed_at"])
        entry.access_count = data.get("access_count", 0)
        entry.size = data.get("size", 0)
        entry.hit_score = data.get("hit_score", 0.0)
        return entry


class L1MemoryCache:
    """
    L1 Memory Cache - 超快速内存缓存层
    
    适用场景：
    - 热点数据（高频访问）
    - 小尺寸数据（< 1KB）
    - 用户会话数据
    - 计算结果缓存
    
    不适用：
    - 大文件或图片
    - 低频访问数据
    - 临时数据
    """
    
    def __init__(self, max_size: int = 1000, max_memory_mb: int = 100):
        self.cache: Dict[str, CacheEntry] = {}
        self.max_size = max_size
        self.max_memory_mb = max_memory_mb
        self.current_memory = 0
        self.current_museum: Optional[str] = None
        
        # L1缓存边界策略配置
        self.l1_size_threshold = 1024  # 1KB - L1只缓存小数据
        self.l1_access_threshold = 3   # 访问3次以上才进入L1
        self.l1_popular_threshold = 0.8  # 热门度阈值
        
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
        priority: int = 1,
        museum_id: Optional[str] = None,
        is_popular: bool = False
    ) -> bool:
        """Set value in L1 cache with intelligent boundary enforcement"""
        entry = CacheEntry(key, value, ttl, tags, priority, museum_id, is_popular)
        
        # L1缓存边界检查 - 只缓存符合L1策略的数据
        if not self._should_cache_in_l1(entry):
            logger.debug(f"Data '{key}' rejected by L1 cache policy (size: {entry.size}, popular: {is_popular})")
            return False
        
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
        
        logger.debug(f"Cached '{key}' in L1: size={entry.size}B, priority={priority}")
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
    
    def _should_cache_in_l1(self, entry: CacheEntry) -> bool:
        """Determine if data should be cached in L1 based on intelligent boundaries"""
        
        # 大小边界：L1只缓存小数据
        if entry.size > self.l1_size_threshold:
            return False
        
        # 热点数据优先进入L1
        if entry.is_popular:
            return True
        
        # 高优先级数据
        if entry.priority >= 5:
            return True
        
        # 用户会话相关数据
        if any(tag in ["session", "user", "quota", "auth"] for tag in entry.tags):
            return True
        
        # 频繁访问的数据
        if entry.access_count >= self.l1_access_threshold:
            return True
        
        # 计算结果类数据 (通常较小且值得缓存)
        if any(tag in ["computed", "result", "processed"] for tag in entry.tags):
            return True
        
        # 默认不缓存 - L2是更合适的选择
        return False
    
    def _would_exceed_limits(self, entry: CacheEntry) -> bool:
        """Check if adding entry would exceed limits"""
        new_memory_mb = (self.current_memory + entry.size) / (1024 * 1024)
        return (
            len(self.cache) >= self.max_size or
            new_memory_mb > self.max_memory_mb
        )
    
    async def _evict_entries(self):
        """Evict entries using intelligent scoring + LRU hybrid strategy"""
        if not self.cache:
            return
        
        # Update all scores with current museum context
        for entry in self.cache.values():
            entry.hit_score = entry._calculate_intelligent_score(self.current_museum)
        
        # Sort by intelligent score (ascending - lower score = evict first)
        sorted_entries = sorted(
            self.cache.items(),
            key=lambda x: (x[1].hit_score, x[1].accessed_at)  # Score first, then LRU as tiebreaker
        )
        
        # Remove lowest scoring 20% of entries (as per architecture requirement)
        evict_count = max(1, len(sorted_entries) // 5)
        
        logger.info(f"Evicting {evict_count} entries using intelligent scoring")
        
        for i in range(evict_count):
            key, entry = sorted_entries[i]
            logger.debug(f"Evicting key '{key}' with score {entry.hit_score:.2f}")
            await self.delete(key)
        
        # Track eviction metrics
        increment_counter("cache_intelligent_evictions")
        set_gauge("cache_eviction_score_threshold", sorted_entries[evict_count-1][1].hit_score if evict_count > 0 else 0)
    
    def set_museum_context(self, museum_id: Optional[str]):
        """Set current museum context for intelligent scoring"""
        self.current_museum = museum_id
        logger.debug(f"Set museum context to: {museum_id}")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get L1 cache statistics with intelligent scoring info"""
        
        # Calculate popularity statistics
        popular_count = sum(1 for entry in self.cache.values() if entry.is_popular)
        avg_score = sum(entry.hit_score for entry in self.cache.values()) / len(self.cache) if self.cache else 0
        avg_access_count = sum(entry.access_count for entry in self.cache.values()) / len(self.cache) if self.cache else 0
        
        return {
            "size": len(self.cache),
            "max_size": self.max_size,
            "memory_mb": self.current_memory / (1024 * 1024),
            "max_memory_mb": self.max_memory_mb,
            "utilization_percent": (len(self.cache) / self.max_size) * 100,
            "popular_entries": popular_count,
            "average_hit_score": round(avg_score, 2),
            "average_access_count": round(avg_access_count, 1),
            "current_museum": self.current_museum
        }


class AdvancedCacheManager:
    """Advanced multi-level cache manager with intelligent strategies and enhanced monitoring"""
    
    def __init__(self):
        self.l1_cache = L1MemoryCache()
        self.cache_hits = {"l1": 0, "l2": 0, "total": 0, "popular": 0}
        self.cache_misses = 0
        
        # Performance tracking for 70%+ hit rate goal
        self.performance_targets = {
            "overall_hit_rate": 70.0,      # 70%+ total hit rate
            "popular_hit_rate": 90.0,      # 90%+ popular items hit rate
            "l1_response_time_ms": 10.0,   # L1 cache <10ms
            "l2_response_time_ms": 100.0   # L2 cache <100ms
        }
        
        # Cache warming configuration
        self.warm_cache_enabled = True
        self.warm_cache_patterns = [
            "recognition:*",  # Pre-cache popular recognition results
            "user:quota:*",   # Cache user quota information
        ]
        
        # Cache refresh configuration
        self.refresh_ahead_enabled = True
        self.refresh_threshold = 0.8  # Refresh when 80% of TTL elapsed
        
        # Popular items tracking (for 90%+ popular hit rate)
        self.popular_items = set()  # Track popular item keys
    
    async def get(
        self, 
        key: str, 
        default: Any = None,
        warm_on_miss: bool = True
    ) -> Any:
        """Get value from multi-level cache with intelligent promotion strategy"""
        import time
        start_time = time.perf_counter()
        is_popular_item = key in self.popular_items
        
        # Try L1 cache first (热点数据和小数据)
        value = await self.l1_cache.get(key)
        if value is not None:
            response_time_ms = (time.perf_counter() - start_time) * 1000
            
            self.cache_hits["l1"] += 1
            self.cache_hits["total"] += 1
            if is_popular_item:
                self.cache_hits["popular"] += 1
            
            track_cache_hit()
            set_gauge("cache_l1_response_time_ms", response_time_ms)
            
            # Check L1 performance target
            if response_time_ms > self.performance_targets["l1_response_time_ms"]:
                increment_counter("cache_l1_slow_responses")
            
            return value
        
        # Try L2 (Redis) cache - 所有其他数据
        redis_key = get_cache_key("cache", key)
        redis_data = await redis_client.get(redis_key)
        
        if redis_data is not None:
            response_time_ms = (time.perf_counter() - start_time) * 1000
            
            self.cache_hits["l2"] += 1
            self.cache_hits["total"] += 1
            if is_popular_item:
                self.cache_hits["popular"] += 1
            
            track_cache_hit()
            set_gauge("cache_l2_response_time_ms", response_time_ms)
            
            # Check L2 performance target
            if response_time_ms > self.performance_targets["l2_response_time_ms"]:
                increment_counter("cache_l2_slow_responses")
            
            # Extract value from Redis cache entry
            value = redis_data.get("value") if isinstance(redis_data, dict) else redis_data
            
            # 智能升级到L1：只有符合L1策略的数据才升级
            await self._try_promote_to_l1(key, value, redis_data, is_popular_item)
            
            return value
        
        # Cache miss
        self.cache_misses += 1
        track_cache_miss()
        
        # Track popular item misses (these should be rare)
        if is_popular_item:
            increment_counter("cache_popular_item_misses")
            logger.warning(f"Popular item '{key}' missed in cache - should be warmed")
        
        # Trigger cache warming if enabled
        if warm_on_miss and self.warm_cache_enabled:
            asyncio.create_task(self._warm_related_cache(key))
        
        return default
    
    async def _try_promote_to_l1(self, key: str, value: Any, redis_data: Dict, is_popular: bool):
        """智能升级L2数据到L1缓存"""
        try:
            # 从Redis缓存条目中提取metadata
            tags = redis_data.get("tags", []) if isinstance(redis_data, dict) else []
            access_count = redis_data.get("access_count", 0) if isinstance(redis_data, dict) else 0
            
            # 判断是否应该升级到L1
            should_promote = False
            
            # 热门数据必须升级
            if is_popular:
                should_promote = True
            
            # 频繁访问的数据
            elif access_count >= 5:
                should_promote = True
            
            # 用户会话数据
            elif any(tag in ["session", "user", "quota"] for tag in tags):
                should_promote = True
            
            # 小数据且有一定访问频次
            elif len(str(value)) <= 1024 and access_count >= 2:
                should_promote = True
            
            if should_promote:
                # 尝试升级到L1 (L1会自己检查边界策略)
                promoted = await self.l1_cache.set(
                    key, value, ttl=300, tags=tags, 
                    is_popular=is_popular, priority=3
                )
                
                if promoted:
                    logger.debug(f"Promoted '{key}' from L2 to L1 cache")
                    increment_counter("cache_l2_to_l1_promotions")
                else:
                    logger.debug(f"L1 cache rejected promotion of '{key}' (boundary policy)")
            
        except Exception as e:
            logger.error(f"Error promoting '{key}' to L1: {e}")
    
    async def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None,
        tags: Optional[List[str]] = None,
        priority: int = 1,
        strategy: CacheStrategy = CacheStrategy.WRITE_THROUGH,
        museum_id: Optional[str] = None,
        is_popular: bool = False
    ) -> bool:
        """Set value in multi-level cache with intelligent layer selection"""
        
        success = True
        
        # 智能选择缓存层
        entry_size = len(str(value))  # 估算数据大小
        
        if strategy == CacheStrategy.WRITE_THROUGH:
            # L1/L2策略：小数据和热点数据优先L1
            if entry_size <= 1024 or is_popular or priority >= 5:
                # 尝试L1缓存 (会自动应用边界策略)
                l1_task = self.l1_cache.set(key, value, ttl, tags, priority, museum_id, is_popular)
                l2_task = self._set_l2_cache(key, value, ttl, tags)
                
                l1_success, l2_success = await asyncio.gather(l1_task, l2_task)
                success = l2_success  # L2是主要存储，L1是可选优化
                
                if l1_success:
                    logger.debug(f"Data '{key}' cached in both L1 and L2")
                else:
                    logger.debug(f"Data '{key}' cached in L2 only (rejected by L1 policy)")
            else:
                # 大数据或低频数据只存L2
                success = await self._set_l2_cache(key, value, ttl, tags)
                logger.debug(f"Large/infrequent data '{key}' cached in L2 only")
            
        elif strategy == CacheStrategy.WRITE_BACK:
            # Write-back策略主要针对L1
            if entry_size <= 1024 or is_popular:
                await self.l1_cache.set(key, value, ttl, tags, priority, museum_id, is_popular)
                asyncio.create_task(self._set_l2_cache(key, value, ttl, tags))
            else:
                # 大数据直接写L2
                success = await self._set_l2_cache(key, value, ttl, tags)
            
        elif strategy == CacheStrategy.REFRESH_AHEAD:
            # 预刷新策略应用到两级缓存
            if entry_size <= 1024 or is_popular:
                await self.l1_cache.set(key, value, ttl, tags, priority, museum_id, is_popular)
            
            await self._set_l2_cache(key, value, ttl, tags)
            
            if ttl and self.refresh_ahead_enabled:
                refresh_time = ttl * self.refresh_threshold
                asyncio.create_task(self._schedule_refresh(key, refresh_time))
        
        # Track cache operations
        increment_counter("cache_set_operations")
        
        # Update popular items set
        if is_popular or (tags and "popular" in tags):
            self.popular_items.add(key)
        
        return success
    
    async def delete(self, key: str) -> bool:
        """Delete from all cache levels"""
        l1_success = await self.l1_cache.delete(key)
        
        redis_key = get_cache_key("cache", key)
        l2_success = await redis_client.delete(redis_key)
        
        increment_counter("cache_delete_operations")
        
        # Remove from popular items if it was popular
        self.popular_items.discard(key)
        
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
    
    def set_museum_context(self, museum_id: Optional[str]):
        """Set current museum context for intelligent cache scoring"""
        self.l1_cache.set_museum_context(museum_id)
        logger.info(f"Updated cache manager museum context to: {museum_id}")
    
    def mark_popular_items(self, keys: List[str]):
        """Mark items as popular for enhanced caching priority"""
        for key in keys:
            self.popular_items.add(key)
        logger.info(f"Marked {len(keys)} items as popular")
    
    def get_performance_status(self) -> Dict[str, Any]:
        """Check if cache performance meets targets (70%+ overall, 90%+ popular)"""
        total_requests = self.cache_hits["total"] + self.cache_misses
        
        if total_requests == 0:
            return {"status": "no_data", "message": "No cache requests yet"}
        
        overall_hit_rate = (self.cache_hits["total"] / total_requests) * 100
        
        # Calculate popular hit rate
        popular_requests = sum(1 for key in self.popular_items if key in [])  # This needs proper tracking
        popular_hit_rate = 0.0
        if len(self.popular_items) > 0:
            popular_hit_rate = (self.cache_hits["popular"] / max(1, popular_requests)) * 100
        
        status = {
            "overall_hit_rate": overall_hit_rate,
            "popular_hit_rate": popular_hit_rate,
            "targets_met": {
                "overall": overall_hit_rate >= self.performance_targets["overall_hit_rate"],
                "popular": popular_hit_rate >= self.performance_targets["popular_hit_rate"]
            },
            "performance_targets": self.performance_targets,
            "total_requests": total_requests,
            "popular_items_count": len(self.popular_items)
        }
        
        return status
    
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
        popular_hit_rate = (self.cache_hits["popular"] / max(1, len(self.popular_items)) * 100) if self.popular_items else 0
        
        stats = {
            "overall": {
                "hit_rate_percent": hit_rate,
                "total_hits": self.cache_hits["total"],
                "total_misses": self.cache_misses,
                "total_requests": total_requests,
                "targets_met": hit_rate >= self.performance_targets["overall_hit_rate"]
            },
            "popular_items": {
                "hit_rate_percent": popular_hit_rate,
                "total_popular_hits": self.cache_hits["popular"],
                "popular_items_count": len(self.popular_items),
                "targets_met": popular_hit_rate >= self.performance_targets["popular_hit_rate"]
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
            "performance_targets": self.performance_targets,
            "configuration": {
                "warm_cache_enabled": self.warm_cache_enabled,
                "refresh_ahead_enabled": self.refresh_ahead_enabled,
                "refresh_threshold": self.refresh_threshold
            }
        }
        
        # Update metrics
        set_gauge("cache_hit_rate_percent", hit_rate)
        set_gauge("cache_popular_hit_rate_percent", popular_hit_rate)
        set_gauge("cache_l1_utilization_percent", l1_stats["utilization_percent"])
        set_gauge("cache_l1_memory_mb", l1_stats["memory_mb"])
        
        # Alert if performance targets are not met
        if hit_rate < self.performance_targets["overall_hit_rate"]:
            increment_counter("cache_performance_alerts")
            logger.warning(f"Cache hit rate {hit_rate:.1f}% below target {self.performance_targets['overall_hit_rate']}%")
        
        if popular_hit_rate < self.performance_targets["popular_hit_rate"]:
            increment_counter("cache_popular_performance_alerts")
            logger.warning(f"Popular items hit rate {popular_hit_rate:.1f}% below target {self.performance_targets['popular_hit_rate']}%")
        
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
    strategy: CacheStrategy = CacheStrategy.WRITE_THROUGH,
    museum_id: Optional[str] = None,
    is_popular: bool = False,
    priority: int = 1
) -> bool:
    """Set value in cache - convenience function"""
    return await cache_manager.set(
        key=key, 
        value=value, 
        ttl=ttl, 
        tags=tags, 
        priority=priority,
        strategy=strategy
    )


async def delete_cached(key: str) -> bool:
    """Delete value from cache - convenience function"""
    return await cache_manager.delete(key)


async def get_cache_stats() -> Dict[str, Any]:
    """Get cache statistics - convenience function"""
    return await cache_manager.get_comprehensive_stats()


def set_museum_context(museum_id: Optional[str]):
    """Set current museum context for intelligent caching - convenience function"""
    cache_manager.set_museum_context(museum_id)


def mark_popular_items(keys: List[str]):
    """Mark items as popular for enhanced caching - convenience function"""  
    cache_manager.mark_popular_items(keys)


def get_cache_performance() -> Dict[str, Any]:
    """Get cache performance status - convenience function"""
    return cache_manager.get_performance_status()


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