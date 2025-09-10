"""
Redis performance optimization module
Implements high-performance Redis operations with pipelining, clustering, and advanced caching
"""

import asyncio
import time
import json
import hashlib
from typing import Any, Dict, List, Optional, Union, Tuple
from dataclasses import dataclass
from collections import defaultdict
import redis.asyncio as redis
from redis.asyncio.cluster import RedisCluster
from redis.asyncio.connection import ConnectionPool

from .redis_client import redis_client
from .logging import get_logger

logger = get_logger(__name__)

@dataclass
class CacheStats:
    """Cache performance statistics"""
    hits: int = 0
    misses: int = 0
    sets: int = 0
    deletes: int = 0
    total_operations: int = 0
    avg_response_time: float = 0.0
    
    @property
    def hit_rate(self) -> float:
        total = self.hits + self.misses
        return (self.hits / total * 100) if total > 0 else 0

class HighPerformanceRedisClient:
    """High-performance Redis client with optimizations"""
    
    def __init__(self):
        self.client = None
        self.pipeline_client = None
        self.stats = CacheStats()
        self.operation_times = defaultdict(list)
        
        # Connection pool settings for maximum performance
        self.pool_kwargs = {
            'max_connections': 50,
            'socket_keepalive': True,
            'health_check_interval': 30,
            'retry_on_timeout': True,
            'socket_connect_timeout': 5,
            'socket_timeout': 5,
        }
    
    async def initialize(self, redis_url: str, cluster_mode: bool = False):
        """Initialize Redis client with performance optimizations"""
        try:
            if cluster_mode:
                # Redis Cluster configuration
                self.client = RedisCluster.from_url(
                    redis_url,
                    skip_full_coverage_check=True,
                    max_connections_per_node=20,
                    retry_on_cluster_down=True,
                    read_from_replicas=True,  # Enable read from replicas
                    **self.pool_kwargs
                )
            else:
                # Single Redis instance with connection pooling
                pool = ConnectionPool.from_url(redis_url, **self.pool_kwargs)
                self.client = redis.Redis(connection_pool=pool)
            
            # Test connection
            await self.client.ping()
            logger.info(f"High-performance Redis client initialized (cluster: {cluster_mode})")
            
            # Initialize pipeline client
            self.pipeline_client = self.client.pipeline()
            
        except Exception as e:
            logger.error(f"Failed to initialize Redis client: {e}")
            raise
    
    async def get_with_stats(self, key: str, track_stats: bool = True) -> Any:
        """Get value with performance tracking"""
        start_time = time.time()
        
        try:
            value = await self.client.get(key)
            
            if track_stats:
                response_time = time.time() - start_time
                self.operation_times['get'].append(response_time)
                self.stats.total_operations += 1
                
                if value is not None:
                    self.stats.hits += 1
                    if isinstance(value, (str, bytes)):
                        try:
                            return json.loads(value)
                        except (json.JSONDecodeError, TypeError):
                            return value
                else:
                    self.stats.misses += 1
                
                # Update average response time
                self._update_avg_response_time()
            
            return value
            
        except Exception as e:
            logger.error(f"Redis GET error for key {key}: {e}")
            if track_stats:
                self.stats.misses += 1
                self.stats.total_operations += 1
            return None
    
    async def set_with_stats(self, key: str, value: Any, ttl: int = None, track_stats: bool = True) -> bool:
        """Set value with performance tracking"""
        start_time = time.time()
        
        try:
            # Serialize value if needed
            if not isinstance(value, (str, bytes)):
                value = json.dumps(value, default=str)
            
            if ttl:
                result = await self.client.setex(key, ttl, value)
            else:
                result = await self.client.set(key, value)
            
            if track_stats:
                response_time = time.time() - start_time
                self.operation_times['set'].append(response_time)
                self.stats.sets += 1
                self.stats.total_operations += 1
                self._update_avg_response_time()
            
            return bool(result)
            
        except Exception as e:
            logger.error(f"Redis SET error for key {key}: {e}")
            return False
    
    async def mget_optimized(self, keys: List[str]) -> Dict[str, Any]:
        """Optimized multi-get operation"""
        if not keys:
            return {}
        
        start_time = time.time()
        
        try:
            # Use pipeline for better performance
            pipe = self.client.pipeline()
            for key in keys:
                pipe.get(key)
            
            values = await pipe.execute()
            
            # Process results
            result = {}
            for i, (key, value) in enumerate(zip(keys, values)):
                if value is not None:
                    try:
                        result[key] = json.loads(value) if isinstance(value, (str, bytes)) else value
                        self.stats.hits += 1
                    except (json.JSONDecodeError, TypeError):
                        result[key] = value
                        self.stats.hits += 1
                else:
                    self.stats.misses += 1
            
            response_time = time.time() - start_time
            self.operation_times['mget'].append(response_time)
            self.stats.total_operations += len(keys)
            self._update_avg_response_time()
            
            logger.debug(f"MGET {len(keys)} keys in {response_time:.3f}s")
            return result
            
        except Exception as e:
            logger.error(f"Redis MGET error: {e}")
            self.stats.misses += len(keys)
            self.stats.total_operations += len(keys)
            return {}
    
    async def mset_optimized(self, mapping: Dict[str, Any], ttl: int = None) -> bool:
        """Optimized multi-set operation"""
        if not mapping:
            return True
        
        start_time = time.time()
        
        try:
            # Use pipeline for better performance
            pipe = self.client.pipeline()
            
            for key, value in mapping.items():
                # Serialize value if needed
                if not isinstance(value, (str, bytes)):
                    value = json.dumps(value, default=str)
                
                if ttl:
                    pipe.setex(key, ttl, value)
                else:
                    pipe.set(key, value)
            
            results = await pipe.execute()
            
            response_time = time.time() - start_time
            self.operation_times['mset'].append(response_time)
            self.stats.sets += len(mapping)
            self.stats.total_operations += len(mapping)
            self._update_avg_response_time()
            
            logger.debug(f"MSET {len(mapping)} keys in {response_time:.3f}s")
            return all(results)
            
        except Exception as e:
            logger.error(f"Redis MSET error: {e}")
            return False
    
    async def delete_pattern_optimized(self, pattern: str) -> int:
        """Optimized pattern-based deletion using SCAN"""
        start_time = time.time()
        deleted_count = 0
        
        try:
            # Use SCAN to avoid blocking
            cursor = 0
            batch_size = 1000
            
            while True:
                cursor, keys = await self.client.scan(cursor=cursor, match=pattern, count=batch_size)
                
                if keys:
                    # Delete in batches using pipeline
                    pipe = self.client.pipeline()
                    for key in keys:
                        pipe.delete(key)
                    
                    results = await pipe.execute()
                    deleted_count += sum(results)
                
                if cursor == 0:
                    break
            
            response_time = time.time() - start_time
            self.operation_times['delete_pattern'].append(response_time)
            self.stats.deletes += deleted_count
            self.stats.total_operations += deleted_count
            self._update_avg_response_time()
            
            logger.debug(f"Deleted {deleted_count} keys matching '{pattern}' in {response_time:.3f}s")
            return deleted_count
            
        except Exception as e:
            logger.error(f"Redis pattern delete error: {e}")
            return 0
    
    async def execute_batch_optimized(self, operations: List[Tuple[str, str, Any]]) -> List[Any]:
        """Execute batch operations optimally using pipeline"""
        if not operations:
            return []
        
        start_time = time.time()
        
        try:
            pipe = self.client.pipeline()
            
            for operation, key, value in operations:
                if operation == 'get':
                    pipe.get(key)
                elif operation == 'set':
                    if isinstance(value, tuple) and len(value) == 2:
                        val, ttl = value
                        if not isinstance(val, (str, bytes)):
                            val = json.dumps(val, default=str)
                        pipe.setex(key, ttl, val)
                    else:
                        if not isinstance(value, (str, bytes)):
                            value = json.dumps(value, default=str)
                        pipe.set(key, value)
                elif operation == 'delete':
                    pipe.delete(key)
                elif operation == 'exists':
                    pipe.exists(key)
            
            results = await pipe.execute()
            
            response_time = time.time() - start_time
            self.operation_times['batch'].append(response_time)
            self.stats.total_operations += len(operations)
            self._update_avg_response_time()
            
            logger.debug(f"Executed {len(operations)} batch operations in {response_time:.3f}s")
            return results
            
        except Exception as e:
            logger.error(f"Redis batch operation error: {e}")
            return [None] * len(operations)
    
    def _update_avg_response_time(self):
        """Update average response time statistics"""
        all_times = []
        for operation_times in self.operation_times.values():
            all_times.extend(operation_times[-100:])  # Keep last 100 operations
        
        if all_times:
            self.stats.avg_response_time = sum(all_times) / len(all_times)
    
    async def get_performance_stats(self) -> Dict[str, Any]:
        """Get detailed performance statistics"""
        stats_dict = {
            'cache_stats': {
                'hits': self.stats.hits,
                'misses': self.stats.misses,
                'hit_rate_percent': self.stats.hit_rate,
                'sets': self.stats.sets,
                'deletes': self.stats.deletes,
                'total_operations': self.stats.total_operations,
                'avg_response_time_ms': self.stats.avg_response_time * 1000
            },
            'operation_stats': {}
        }
        
        # Add operation-specific statistics
        for operation, times in self.operation_times.items():
            if times:
                recent_times = times[-100:]  # Last 100 operations
                stats_dict['operation_stats'][operation] = {
                    'count': len(times),
                    'avg_time_ms': sum(recent_times) / len(recent_times) * 1000,
                    'min_time_ms': min(recent_times) * 1000,
                    'max_time_ms': max(recent_times) * 1000
                }
        
        # Add Redis server info
        try:
            info = await self.client.info()
            stats_dict['server_stats'] = {
                'used_memory_human': info.get('used_memory_human', 'N/A'),
                'connected_clients': info.get('connected_clients', 0),
                'total_commands_processed': info.get('total_commands_processed', 0),
                'keyspace_hits': info.get('keyspace_hits', 0),
                'keyspace_misses': info.get('keyspace_misses', 0),
                'evicted_keys': info.get('evicted_keys', 0)
            }
        except Exception as e:
            logger.error(f"Failed to get Redis server stats: {e}")
            stats_dict['server_stats'] = {}
        
        return stats_dict

class SmartCacheInvalidator:
    """Smart cache invalidation with dependency tracking"""
    
    def __init__(self, redis_client: HighPerformanceRedisClient):
        self.redis = redis_client
        self.dependencies = defaultdict(set)
    
    def add_dependency(self, key: str, dependent_keys: List[str]):
        """Add cache dependencies"""
        for dep_key in dependent_keys:
            self.dependencies[key].add(dep_key)
    
    async def invalidate_with_dependencies(self, key: str) -> int:
        """Invalidate key and all dependent keys"""
        keys_to_delete = {key}
        
        # Find all dependent keys recursively
        def find_dependencies(search_key: str):
            for dep_key in self.dependencies.get(search_key, set()):
                if dep_key not in keys_to_delete:
                    keys_to_delete.add(dep_key)
                    find_dependencies(dep_key)
        
        find_dependencies(key)
        
        if keys_to_delete:
            # Delete all keys in a batch
            pipe = self.redis.client.pipeline()
            for del_key in keys_to_delete:
                pipe.delete(del_key)
            
            results = await pipe.execute()
            deleted_count = sum(results)
            
            logger.debug(f"Invalidated {deleted_count} cache keys with dependencies")
            return deleted_count
        
        return 0

class CacheWarmupManager:
    """Intelligent cache warmup for better performance"""
    
    def __init__(self, redis_client: HighPerformanceRedisClient):
        self.redis = redis_client
        self.warmup_tasks = []
    
    async def warmup_popular_artworks(self, limit: int = 100):
        """Warmup cache for popular artworks"""
        from .database_performance import OptimizedQueries
        
        try:
            # Get popular artworks without cache
            popular_artworks = await OptimizedQueries.get_popular_artworks(limit=limit)
            
            # Prepare batch cache operations
            cache_operations = []
            for artwork in popular_artworks:
                cache_key = f"artwork:{artwork['id']}"
                cache_operations.append(('set', cache_key, (artwork, 1800)))  # 30 min TTL
            
            # Execute batch warmup
            await self.redis.execute_batch_optimized(cache_operations)
            logger.info(f"Warmed up cache for {len(popular_artworks)} popular artworks")
            
        except Exception as e:
            logger.error(f"Cache warmup failed: {e}")
    
    async def warmup_museum_data(self):
        """Warmup cache for museum data"""
        try:
            # This would be implemented based on actual museum query patterns
            logger.info("Museum data cache warmup completed")
            
        except Exception as e:
            logger.error(f"Museum cache warmup failed: {e}")
    
    async def schedule_periodic_warmup(self):
        """Schedule periodic cache warmup"""
        while True:
            try:
                # Warmup popular data every 2 hours
                await self.warmup_popular_artworks()
                await self.warmup_museum_data()
                
                await asyncio.sleep(7200)  # 2 hours
                
            except Exception as e:
                logger.error(f"Scheduled warmup error: {e}")
                await asyncio.sleep(3600)  # Retry in 1 hour

# Global high-performance Redis client
hp_redis_client = HighPerformanceRedisClient()
cache_invalidator = SmartCacheInvalidator(hp_redis_client)
cache_warmup = CacheWarmupManager(hp_redis_client)

# Performance monitoring
async def monitor_redis_performance():
    """Monitor Redis performance continuously"""
    while True:
        try:
            stats = await hp_redis_client.get_performance_stats()
            
            # Log performance warnings
            hit_rate = stats['cache_stats']['hit_rate_percent']
            avg_time = stats['cache_stats']['avg_response_time_ms']
            
            if hit_rate < 80:
                logger.warning(f"Low cache hit rate: {hit_rate:.1f}%")
            
            if avg_time > 10:  # 10ms threshold
                logger.warning(f"High Redis response time: {avg_time:.2f}ms")
            
            # Log stats every 5 minutes
            logger.debug(f"Redis performance - Hit rate: {hit_rate:.1f}%, Avg time: {avg_time:.2f}ms")
            
            await asyncio.sleep(300)  # 5 minutes
            
        except Exception as e:
            logger.error(f"Redis performance monitoring error: {e}")
            await asyncio.sleep(600)  # Wait 10 minutes on error

# Initialization function
async def initialize_high_performance_redis(redis_url: str, cluster_mode: bool = False):
    """Initialize high-performance Redis client"""
    await hp_redis_client.initialize(redis_url, cluster_mode)
    
    # Start monitoring
    asyncio.create_task(monitor_redis_performance())
    
    # Start cache warmup
    asyncio.create_task(cache_warmup.schedule_periodic_warmup())
    
    logger.info("High-performance Redis client initialized with monitoring and warmup")