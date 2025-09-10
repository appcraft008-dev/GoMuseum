"""
Memory optimization and async operation performance module
Implements memory-efficient data processing, object pooling, and optimized async patterns
"""

import asyncio
import gc
import sys
import tracemalloc
import weakref
from typing import Any, Dict, List, Optional, Callable, AsyncGenerator, TypeVar, Generic
from collections import deque
from dataclasses import dataclass, field
from contextlib import asynccontextmanager
import threading
import time
from concurrent.futures import ThreadPoolExecutor
import psutil
try:
    import objgraph
    HAS_OBJGRAPH = True
except ImportError:
    objgraph = None
    HAS_OBJGRAPH = False

from .logging import get_logger

logger = get_logger(__name__)

T = TypeVar('T')

@dataclass
class MemoryStats:
    """Memory usage statistics"""
    current_mb: float = 0.0
    peak_mb: float = 0.0
    available_mb: float = 0.0
    usage_percent: float = 0.0
    gc_collections: Dict[int, int] = field(default_factory=dict)
    object_counts: Dict[str, int] = field(default_factory=dict)

class MemoryProfiler:
    """Memory usage profiler and optimizer"""
    
    def __init__(self, enable_tracemalloc: bool = True):
        self.enable_tracemalloc = enable_tracemalloc
        self.snapshots = deque(maxlen=100)
        self.memory_threshold_mb = 500  # Alert if memory usage exceeds 500MB
        
        if self.enable_tracemalloc:
            tracemalloc.start()
    
    def get_memory_stats(self) -> MemoryStats:
        """Get current memory statistics"""
        process = psutil.Process()
        memory_info = process.memory_info()
        system_memory = psutil.virtual_memory()
        
        stats = MemoryStats(
            current_mb=memory_info.rss / 1024 / 1024,
            peak_mb=memory_info.peak_wss / 1024 / 1024 if hasattr(memory_info, 'peak_wss') else 0,
            available_mb=system_memory.available / 1024 / 1024,
            usage_percent=system_memory.percent,
            gc_collections={i: gc.get_count()[i] for i in range(3)}
        )
        
        # Get object counts for memory-intensive types
        stats.object_counts = {
            'dict': len([obj for obj in gc.get_objects() if type(obj) is dict]),
            'list': len([obj for obj in gc.get_objects() if type(obj) is list]),
            'str': len([obj for obj in gc.get_objects() if type(obj) is str]),
        }
        
        return stats
    
    def take_snapshot(self) -> Optional[Any]:
        """Take memory snapshot if tracemalloc is enabled"""
        if self.enable_tracemalloc:
            snapshot = tracemalloc.take_snapshot()
            self.snapshots.append((time.time(), snapshot))
            return snapshot
        return None
    
    def analyze_memory_growth(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Analyze memory growth patterns"""
        if len(self.snapshots) < 2:
            return []
        
        current_time, current = self.snapshots[-1]
        previous_time, previous = self.snapshots[-2]
        
        top_stats = current.compare_to(previous, 'lineno')
        
        growth_analysis = []
        for stat in top_stats[:limit]:
            growth_analysis.append({
                'file': stat.traceback.format()[-1],
                'size_diff_mb': stat.size_diff / 1024 / 1024,
                'count_diff': stat.count_diff,
                'time_diff': current_time - previous_time
            })
        
        return growth_analysis
    
    async def monitor_memory_usage(self, interval: float = 30.0):
        """Continuously monitor memory usage"""
        while True:
            try:
                stats = self.get_memory_stats()
                
                # Log memory usage
                logger.debug(f"Memory usage: {stats.current_mb:.1f}MB ({stats.usage_percent:.1f}%)")
                
                # Alert if memory usage is high
                if stats.current_mb > self.memory_threshold_mb:
                    logger.warning(f"High memory usage detected: {stats.current_mb:.1f}MB")
                    
                    # Force garbage collection
                    collected = gc.collect()
                    logger.info(f"Garbage collection freed {collected} objects")
                    
                    # Take snapshot for analysis
                    self.take_snapshot()
                
                await asyncio.sleep(interval)
                
            except Exception as e:
                logger.error(f"Memory monitoring error: {e}")
                await asyncio.sleep(interval * 2)

class ObjectPool(Generic[T]):
    """Generic object pool for memory optimization"""
    
    def __init__(self, factory: Callable[[], T], max_size: int = 100):
        self.factory = factory
        self.max_size = max_size
        self.pool = deque()
        self.created_count = 0
        self.borrowed_count = 0
        self.returned_count = 0
        self._lock = threading.Lock()
    
    def borrow(self) -> T:
        """Borrow an object from the pool"""
        with self._lock:
            if self.pool:
                obj = self.pool.popleft()
                self.borrowed_count += 1
                return obj
            else:
                obj = self.factory()
                self.created_count += 1
                self.borrowed_count += 1
                return obj
    
    def return_object(self, obj: T):
        """Return an object to the pool"""
        with self._lock:
            if len(self.pool) < self.max_size:
                # Reset object state if it has a reset method
                if hasattr(obj, 'reset'):
                    obj.reset()
                self.pool.append(obj)
                self.returned_count += 1
    
    def get_stats(self) -> Dict[str, int]:
        """Get pool statistics"""
        with self._lock:
            return {
                'pool_size': len(self.pool),
                'created': self.created_count,
                'borrowed': self.borrowed_count,
                'returned': self.returned_count,
                'in_use': self.borrowed_count - self.returned_count
            }

class MemoryEfficientDataProcessor:
    """Memory-efficient data processing utilities"""
    
    @staticmethod
    async def process_large_dataset_streaming(
        data_source: AsyncGenerator[T, None],
        processor: Callable[[T], Any],
        batch_size: int = 1000
    ) -> AsyncGenerator[List[Any], None]:
        """Process large dataset in streaming fashion to minimize memory usage"""
        batch = []
        
        async for item in data_source:
            batch.append(item)
            
            if len(batch) >= batch_size:
                # Process batch
                results = []
                for item in batch:
                    try:
                        result = processor(item)
                        if asyncio.iscoroutine(result):
                            result = await result
                        results.append(result)
                    except Exception as e:
                        logger.error(f"Error processing item: {e}")
                
                yield results
                
                # Clear batch to free memory
                batch.clear()
                
                # Force garbage collection periodically
                if gc.get_count()[0] > 1000:
                    gc.collect()
        
        # Process remaining items
        if batch:
            results = []
            for item in batch:
                try:
                    result = processor(item)
                    if asyncio.iscoroutine(result):
                        result = await result
                    results.append(result)
                except Exception as e:
                    logger.error(f"Error processing item: {e}")
            
            yield results
    
    @staticmethod
    def create_memory_mapped_cache(max_size_mb: int = 100) -> Dict[str, Any]:
        """Create memory-mapped cache with size limit"""
        cache = {}
        current_size = 0
        max_size_bytes = max_size_mb * 1024 * 1024
        
        def get_size(obj):
            return sys.getsizeof(obj)
        
        class SizeLimitedDict(dict):
            def __setitem__(self, key, value):
                nonlocal current_size
                
                # Remove old value if exists
                if key in self:
                    current_size -= get_size(self[key])
                
                value_size = get_size(value)
                
                # Evict items if necessary
                while current_size + value_size > max_size_bytes and self:
                    oldest_key = next(iter(self))
                    current_size -= get_size(self[oldest_key])
                    del self[oldest_key]
                
                super().__setitem__(key, value)
                current_size += value_size
            
            def __delitem__(self, key):
                nonlocal current_size
                current_size -= get_size(self[key])
                super().__delitem__(key)
        
        return SizeLimitedDict()

class AsyncBatchProcessor:
    """Optimized async batch processor with memory management"""
    
    def __init__(self, batch_size: int = 100, max_concurrent: int = 10):
        self.batch_size = batch_size
        self.max_concurrent = max_concurrent
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.processed_count = 0
        self.error_count = 0
    
    async def process_batch(
        self,
        items: List[T],
        processor: Callable[[T], Any],
        error_handler: Optional[Callable[[T, Exception], Any]] = None
    ) -> List[Any]:
        """Process a batch of items with memory optimization"""
        async with self.semaphore:
            results = []
            
            for item in items:
                try:
                    result = processor(item)
                    if asyncio.iscoroutine(result):
                        result = await result
                    results.append(result)
                    self.processed_count += 1
                    
                except Exception as e:
                    self.error_count += 1
                    if error_handler:
                        try:
                            error_result = error_handler(item, e)
                            if asyncio.iscoroutine(error_result):
                                error_result = await error_result
                            results.append(error_result)
                        except Exception as handler_error:
                            logger.error(f"Error in error handler: {handler_error}")
                            results.append(None)
                    else:
                        logger.error(f"Error processing item: {e}")
                        results.append(None)
            
            return results
    
    async def process_stream(
        self,
        items: AsyncGenerator[T, None],
        processor: Callable[[T], Any],
        error_handler: Optional[Callable[[T, Exception], Any]] = None
    ) -> AsyncGenerator[List[Any], None]:
        """Process stream of items in optimized batches"""
        batch = []
        
        async for item in items:
            batch.append(item)
            
            if len(batch) >= self.batch_size:
                results = await self.process_batch(batch, processor, error_handler)
                yield results
                
                # Clear batch and collect garbage
                batch.clear()
                if self.processed_count % 1000 == 0:
                    gc.collect()
        
        # Process remaining items
        if batch:
            results = await self.process_batch(batch, processor, error_handler)
            yield results

class LazyLoader:
    """Lazy loading utility to reduce memory usage"""
    
    def __init__(self, loader_func: Callable[[], T]):
        self.loader_func = loader_func
        self._loaded = False
        self._value = None
        self._lock = threading.Lock()
    
    @property
    def value(self) -> T:
        if not self._loaded:
            with self._lock:
                if not self._loaded:
                    self._value = self.loader_func()
                    self._loaded = True
        return self._value
    
    def reset(self):
        """Reset the lazy loader to free memory"""
        with self._lock:
            self._value = None
            self._loaded = False

class MemoryOptimizedAsyncQueue:
    """Memory-optimized async queue with overflow handling"""
    
    def __init__(self, maxsize: int = 1000, overflow_strategy: str = 'drop_oldest'):
        self.queue = asyncio.Queue(maxsize=maxsize)
        self.overflow_strategy = overflow_strategy
        self.dropped_count = 0
        self.total_added = 0
    
    async def put(self, item: T):
        """Put item with overflow handling"""
        try:
            self.queue.put_nowait(item)
            self.total_added += 1
        except asyncio.QueueFull:
            if self.overflow_strategy == 'drop_oldest':
                try:
                    self.queue.get_nowait()  # Remove oldest
                    self.queue.put_nowait(item)
                    self.dropped_count += 1
                    self.total_added += 1
                except asyncio.QueueEmpty:
                    pass
            elif self.overflow_strategy == 'drop_new':
                self.dropped_count += 1
            else:  # block
                await self.queue.put(item)
                self.total_added += 1
    
    async def get(self) -> T:
        """Get item from queue"""
        return await self.queue.get()
    
    def qsize(self) -> int:
        """Get queue size"""
        return self.queue.qsize()
    
    def get_stats(self) -> Dict[str, int]:
        """Get queue statistics"""
        return {
            'size': self.qsize(),
            'total_added': self.total_added,
            'dropped': self.dropped_count
        }

# Context managers for memory optimization
@asynccontextmanager
async def memory_monitor(threshold_mb: float = 100.0):
    """Context manager that monitors memory usage during execution"""
    profiler = MemoryProfiler()
    start_stats = profiler.get_memory_stats()
    
    try:
        yield profiler
    finally:
        end_stats = profiler.get_memory_stats()
        memory_diff = end_stats.current_mb - start_stats.current_mb
        
        if memory_diff > threshold_mb:
            logger.warning(f"High memory usage detected: +{memory_diff:.1f}MB")
            
            # Analyze growth
            profiler.take_snapshot()
            growth = profiler.analyze_memory_growth()
            if growth:
                logger.info(f"Top memory growth: {growth[0]}")

@asynccontextmanager
async def optimized_batch_context(batch_size: int = 100):
    """Context manager for optimized batch processing"""
    processor = AsyncBatchProcessor(batch_size=batch_size)
    
    try:
        yield processor
    finally:
        logger.debug(f"Batch processing completed: {processor.processed_count} processed, {processor.error_count} errors")
        
        # Force garbage collection
        gc.collect()

# Global instances
memory_profiler = MemoryProfiler()
async_batch_processor = AsyncBatchProcessor()

# Object pools for common types
dict_pool = ObjectPool(dict, max_size=1000)
list_pool = ObjectPool(list, max_size=1000)

# Utility functions
def optimize_gc_settings():
    """Optimize garbage collection settings for the application"""
    # Increase GC thresholds for better performance
    gc.set_threshold(1000, 15, 15)
    
    # Enable GC debugging if needed
    # gc.set_debug(gc.DEBUG_STATS)
    
    logger.info("Garbage collection settings optimized")

async def periodic_memory_cleanup():
    """Periodic memory cleanup task"""
    while True:
        try:
            # Force garbage collection
            collected = gc.collect()
            
            # Get current memory stats
            stats = memory_profiler.get_memory_stats()
            
            # Log stats
            logger.debug(f"Memory cleanup: {collected} objects collected, {stats.current_mb:.1f}MB used")
            
            # Clear object pool stats periodically
            dict_stats = dict_pool.get_stats()
            list_stats = list_pool.get_stats()
            
            logger.debug(f"Object pools - Dict: {dict_stats}, List: {list_stats}")
            
            await asyncio.sleep(300)  # Every 5 minutes
            
        except Exception as e:
            logger.error(f"Memory cleanup error: {e}")
            await asyncio.sleep(600)  # Wait 10 minutes on error

# Startup function
async def initialize_memory_optimization():
    """Initialize memory optimization features"""
    optimize_gc_settings()
    
    # Start memory monitoring
    asyncio.create_task(memory_profiler.monitor_memory_usage())
    asyncio.create_task(periodic_memory_cleanup())
    
    logger.info("Memory optimization initialized")