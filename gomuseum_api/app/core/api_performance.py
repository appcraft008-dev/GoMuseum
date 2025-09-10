"""
FastAPI performance optimization module
Implements high-performance API routing, response optimization, and async processing
"""

import asyncio
import time
import gzip
import io
from typing import Any, Dict, List, Optional, Union, Callable
from functools import wraps, lru_cache
from dataclasses import dataclass
import json
import hashlib
from concurrent.futures import ThreadPoolExecutor

from fastapi import Request, Response, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.gzip import GZipMiddleware
from starlette.responses import Response as StarletteResponse

from .logging import get_logger
from .redis_performance import hp_redis_client
from .metrics import metrics

logger = get_logger(__name__)

# Thread pool for CPU-intensive tasks
cpu_pool = ThreadPoolExecutor(max_workers=4, thread_name_prefix="api_cpu")
io_pool = ThreadPoolExecutor(max_workers=8, thread_name_prefix="api_io")

@dataclass
class ResponseCacheConfig:
    """Response cache configuration"""
    ttl: int = 300  # 5 minutes default
    vary_by_user: bool = False
    vary_by_params: bool = True
    compress: bool = True
    max_size: int = 1024 * 1024  # 1MB max response size

class HighPerformanceJSONEncoder(json.JSONEncoder):
    """Optimized JSON encoder for API responses"""
    
    def default(self, obj):
        if hasattr(obj, 'isoformat'):  # datetime objects
            return obj.isoformat()
        elif hasattr(obj, '__dict__'):  # Custom objects
            return obj.__dict__
        elif hasattr(obj, '__str__'):  # UUID and other string-convertible objects
            return str(obj)
        return super().default(obj)

class ResponseCompressionMiddleware(BaseHTTPMiddleware):
    """High-performance response compression middleware"""
    
    def __init__(self, app, minimum_size: int = 1024):
        super().__init__(app)
        self.minimum_size = minimum_size
        
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)
        
        # Only compress JSON responses above minimum size
        if (response.headers.get("content-type", "").startswith("application/json") and
            hasattr(response, 'body') and len(response.body) > self.minimum_size):
            
            # Check if client accepts gzip
            accept_encoding = request.headers.get("accept-encoding", "")
            if "gzip" in accept_encoding:
                compressed_body = gzip.compress(response.body)
                if len(compressed_body) < len(response.body):
                    response.body = compressed_body
                    response.headers["content-encoding"] = "gzip"
                    response.headers["content-length"] = str(len(compressed_body))
        
        return response

class ResponseCacheMiddleware(BaseHTTPMiddleware):
    """High-performance response caching middleware"""
    
    def __init__(self, app, default_ttl: int = 300):
        super().__init__(app)
        self.default_ttl = default_ttl
        self.cache_configs = {}
    
    def configure_endpoint(self, path: str, config: ResponseCacheConfig):
        """Configure caching for specific endpoint"""
        self.cache_configs[path] = config
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Only cache GET requests
        if request.method != "GET":
            return await call_next(request)
        
        path = request.url.path
        config = self.cache_configs.get(path, ResponseCacheConfig())
        
        # Generate cache key
        cache_key_parts = [f"response:{path}"]
        
        if config.vary_by_params and request.query_params:
            params_str = "&".join(f"{k}={v}" for k, v in sorted(request.query_params.items()))
            cache_key_parts.append(hashlib.sha256(params_str.encode()).hexdigest()[:16])
        
        if config.vary_by_user:
            user_id = getattr(request.state, 'user_id', None)
            if user_id:
                cache_key_parts.append(str(user_id))
        
        cache_key = ":".join(cache_key_parts)
        
        # Try to get cached response
        cached_response = await hp_redis_client.get_with_stats(cache_key)
        if cached_response:
            metrics.increment_counter("api_cache_hits")
            
            # Decompress if needed
            if cached_response.get('compressed'):
                body = gzip.decompress(cached_response['body'])
            else:
                body = cached_response['body']
            
            return JSONResponse(
                content=json.loads(body),
                headers=cached_response.get('headers', {})
            )
        
        # Generate response
        start_time = time.time()
        response = await call_next(request)
        response_time = time.time() - start_time
        
        # Cache successful responses
        if response.status_code == 200 and hasattr(response, 'body'):
            try:
                body = response.body
                if len(body) <= config.max_size:
                    cache_data = {
                        'body': body,
                        'headers': dict(response.headers),
                        'compressed': False
                    }
                    
                    # Compress large responses
                    if config.compress and len(body) > 1024:
                        compressed_body = gzip.compress(body)
                        if len(compressed_body) < len(body):
                            cache_data['body'] = compressed_body
                            cache_data['compressed'] = True
                    
                    await hp_redis_client.set_with_stats(cache_key, cache_data, ttl=config.ttl)
                    metrics.increment_counter("api_cache_sets")
            
            except Exception as e:
                logger.warning(f"Failed to cache response for {path}: {e}")
        
        # Track response time
        metrics.record_histogram("api_response_time_seconds", response_time, tags={
            "endpoint": path,
            "status_code": str(response.status_code)
        })
        
        return response

def async_cached(ttl: int = 300, key_prefix: str = None):
    """Decorator for caching async function results"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Generate cache key
            key_parts = [key_prefix or func.__name__]
            
            # Add function arguments to key
            if args:
                key_parts.append(hashlib.sha256(str(args).encode()).hexdigest()[:8])
            if kwargs:
                sorted_kwargs = sorted(kwargs.items())
                key_parts.append(hashlib.sha256(str(sorted_kwargs).encode()).hexdigest()[:8])
            
            cache_key = ":".join(key_parts)
            
            # Try cache first
            cached_result = await hp_redis_client.get_with_stats(cache_key)
            if cached_result is not None:
                return cached_result
            
            # Execute function
            start_time = time.time()
            result = await func(*args, **kwargs)
            execution_time = time.time() - start_time
            
            # Cache result
            try:
                await hp_redis_client.set_with_stats(cache_key, result, ttl=ttl)
                logger.debug(f"Cached result for {func.__name__} (exec: {execution_time:.3f}s)")
            except Exception as e:
                logger.warning(f"Failed to cache result for {func.__name__}: {e}")
            
            return result
        
        return wrapper
    return decorator

def cpu_bound(func):
    """Decorator for CPU-intensive operations"""
    @wraps(func)
    async def wrapper(*args, **kwargs):
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(cpu_pool, func, *args, **kwargs)
    return wrapper

def io_bound(func):
    """Decorator for I/O-intensive operations"""
    @wraps(func)
    async def wrapper(*args, **kwargs):
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(io_pool, func, *args, **kwargs)
    return wrapper

class OptimizedJSONResponse(JSONResponse):
    """Optimized JSON response with custom encoder and compression"""
    
    def __init__(
        self,
        content: Any = None,
        status_code: int = 200,
        headers: Optional[Dict[str, str]] = None,
        compress: bool = True,
        **kwargs
    ):
        self.compress_response = compress
        super().__init__(content, status_code, headers, **kwargs)
    
    def render(self, content: Any) -> bytes:
        """Render content with optimized JSON encoder"""
        if content is None:
            return b""
        
        # Use optimized JSON encoder
        json_str = json.dumps(
            content,
            cls=HighPerformanceJSONEncoder,
            ensure_ascii=False,
            separators=(',', ':')  # Minimal separators for smaller size
        )
        
        json_bytes = json_str.encode('utf-8')
        
        # Compress if enabled and beneficial
        if self.compress_response and len(json_bytes) > 1024:
            compressed = gzip.compress(json_bytes)
            if len(compressed) < len(json_bytes):
                self.headers["content-encoding"] = "gzip"
                return compressed
        
        return json_bytes

class StreamingJSONResponse(StreamingResponse):
    """Streaming JSON response for large datasets"""
    
    def __init__(self, items, chunk_size: int = 100, **kwargs):
        self.items = items
        self.chunk_size = chunk_size
        super().__init__(self._generate_chunks(), media_type="application/json", **kwargs)
    
    async def _generate_chunks(self):
        """Generate JSON chunks for streaming"""
        yield b'{"items":['
        
        first_item = True
        item_count = 0
        
        async for item in self._iter_items():
            if not first_item:
                yield b','
            else:
                first_item = False
            
            # Serialize item
            item_json = json.dumps(item, cls=HighPerformanceJSONEncoder, separators=(',', ':'))
            yield item_json.encode('utf-8')
            
            item_count += 1
        
        yield f'],"total":{item_count}}}'.encode('utf-8')
    
    async def _iter_items(self):
        """Iterate over items in chunks"""
        if hasattr(self.items, '__aiter__'):
            async for item in self.items:
                yield item
        else:
            for item in self.items:
                yield item

@lru_cache(maxsize=1000)
def get_response_schema_cache(endpoint: str, status_code: int) -> Dict[str, Any]:
    """Cache response schemas for faster validation"""
    # This would be populated with actual response schemas
    return {}

class BatchRequestProcessor:
    """Process multiple API requests in batch for better performance"""
    
    def __init__(self, max_batch_size: int = 50, batch_timeout: float = 0.1):
        self.max_batch_size = max_batch_size
        self.batch_timeout = batch_timeout
        self.pending_requests = []
        self.batch_lock = asyncio.Lock()
    
    async def add_request(self, request_data: Dict[str, Any]) -> Any:
        """Add request to batch and wait for result"""
        request_future = asyncio.Future()
        
        async with self.batch_lock:
            self.pending_requests.append((request_data, request_future))
            
            # Process batch if full or timeout reached
            if len(self.pending_requests) >= self.max_batch_size:
                await self._process_batch()
        
        # Wait for result
        return await request_future
    
    async def _process_batch(self):
        """Process current batch of requests"""
        if not self.pending_requests:
            return
        
        current_batch = self.pending_requests[:]
        self.pending_requests.clear()
        
        try:
            # Process all requests in parallel
            tasks = []
            for request_data, future in current_batch:
                task = asyncio.create_task(self._process_single_request(request_data))
                tasks.append((task, future))
            
            # Wait for all tasks to complete
            for task, future in tasks:
                try:
                    result = await task
                    future.set_result(result)
                except Exception as e:
                    future.set_exception(e)
        
        except Exception as e:
            # Set exception for all pending requests
            for _, future in current_batch:
                if not future.done():
                    future.set_exception(e)
    
    async def _process_single_request(self, request_data: Dict[str, Any]) -> Any:
        """Process a single request (override in subclass)"""
        await asyncio.sleep(0.01)  # Simulate processing
        return {"processed": True, "data": request_data}

# Recognition-specific optimizations
class RecognitionOptimizer:
    """Optimizations specific to artwork recognition endpoint"""
    
    def __init__(self):
        self.image_cache = {}
        self.result_cache = {}
        self.batch_processor = BatchRequestProcessor(max_batch_size=10, batch_timeout=0.05)
    
    @async_cached(ttl=1800, key_prefix="recognition")  # 30 minutes cache
    async def get_cached_recognition(self, image_hash: str) -> Optional[Dict[str, Any]]:
        """Get cached recognition result"""
        return None  # Will be handled by cache decorator
    
    async def preprocess_image_async(self, image_bytes: bytes) -> bytes:
        """Async image preprocessing"""
        @cpu_bound
        def preprocess_cpu(image_data: bytes) -> bytes:
            # Simulate image preprocessing (resize, normalize, etc.)
            # In real implementation, this would use PIL/OpenCV
            return image_data
        
        return await preprocess_cpu(image_bytes)
    
    async def batch_recognize_images(self, images: List[bytes]) -> List[Dict[str, Any]]:
        """Batch recognition for better GPU utilization"""
        # This would interface with the actual ML model
        results = []
        for image in images:
            # Simulate recognition
            result = {
                "candidates": [
                    {"artwork_id": "sample", "confidence": 0.85, "name": "Sample Artwork"}
                ],
                "processing_time": 0.1
            }
            results.append(result)
        
        return results

# Global instances
response_cache_middleware = ResponseCacheMiddleware(None)
recognition_optimizer = RecognitionOptimizer()

# Configuration functions
def configure_api_performance():
    """Configure API performance settings"""
    # Configure response caching for specific endpoints
    response_cache_middleware.configure_endpoint(
        "/api/v1/recognize", 
        ResponseCacheConfig(ttl=1800, vary_by_user=True, compress=True)
    )
    
    response_cache_middleware.configure_endpoint(
        "/api/v1/user/profile",
        ResponseCacheConfig(ttl=300, vary_by_user=True)
    )
    
    response_cache_middleware.configure_endpoint(
        "/api/v1/museums",
        ResponseCacheConfig(ttl=3600, vary_by_params=True)
    )
    
    logger.info("API performance configuration applied")

def get_optimized_json_response(content: Any, status_code: int = 200) -> OptimizedJSONResponse:
    """Get optimized JSON response"""
    return OptimizedJSONResponse(content=content, status_code=status_code)

def get_streaming_response(items, chunk_size: int = 100) -> StreamingJSONResponse:
    """Get streaming JSON response for large datasets"""
    return StreamingJSONResponse(items, chunk_size=chunk_size)