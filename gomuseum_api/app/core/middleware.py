import time
import uuid
from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp
from typing import Callable, Optional

from .metrics import track_api_request, increment_counter
from .logging import get_logger
from .auth import UserRateLimit

logger = get_logger(__name__)


class MetricsMiddleware(BaseHTTPMiddleware):
    """Middleware to automatically track API metrics"""
    
    def __init__(self, app: ASGIApp):
        super().__init__(app)
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Generate request ID
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id
        
        # Start timing
        start_time = time.time()
        
        # Get endpoint and method
        method = request.method
        path = request.url.path
        
        # Process request
        try:
            response = await call_next(request)
            
            # Calculate duration
            duration = time.time() - start_time
            
            # Track metrics
            track_api_request(
                endpoint=path,
                method=method,
                duration=duration,
                status_code=response.status_code
            )
            
            # Add request ID to response headers
            response.headers["X-Request-ID"] = request_id
            
            # Log request
            logger.info(
                f"{method} {path} - {response.status_code}",
                extra={
                    "request_id": request_id,
                    "method": method,
                    "path": path,
                    "status_code": response.status_code,
                    "duration": duration,
                    "user_agent": request.headers.get("user-agent", ""),
                    "ip": request.client.host if request.client else ""
                }
            )
            
            return response
            
        except Exception as e:
            # Calculate duration even for errors
            duration = time.time() - start_time
            
            # Track error metrics
            track_api_request(
                endpoint=path,
                method=method,
                duration=duration,
                status_code=500
            )
            
            increment_counter("api_exceptions_total")
            
            # Log error
            logger.error(
                f"{method} {path} - Exception: {str(e)}",
                extra={
                    "request_id": request_id,
                    "method": method,
                    "path": path,
                    "duration": duration,
                    "exception": str(e)
                },
                exc_info=True
            )
            
            # Re-raise the exception
            raise


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Basic rate limiting middleware"""
    
    def __init__(
        self, 
        app: ASGIApp, 
        calls: int = 100, 
        period: int = 3600,
        skip_paths: Optional[list] = None
    ):
        super().__init__(app)
        self.calls = calls
        self.period = period
        self.skip_paths = skip_paths or ["/health", "/docs", "/openapi.json"]
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Skip rate limiting for certain paths
        if request.url.path in self.skip_paths:
            return await call_next(request)
        
        # Get client identifier (IP address for now)
        client_ip = request.client.host if request.client else "unknown"
        
        # Check rate limit
        if not UserRateLimit.check_rate_limit(client_ip, self.calls, self.period):
            logger.warning(
                f"Rate limit exceeded for {client_ip}",
                extra={
                    "client_ip": client_ip,
                    "path": request.url.path,
                    "rate_limit": f"{self.calls}/{self.period}s"
                }
            )
            
            increment_counter("rate_limit_exceeded_total")
            
            return JSONResponse(
                status_code=429,
                content={
                    "error": "rate_limit_exceeded",
                    "message": f"Rate limit of {self.calls} requests per {self.period} seconds exceeded",
                    "retry_after": self.period
                },
                headers={"Retry-After": str(self.period)}
            )
        
        return await call_next(request)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security headers to all responses"""
    
    def __init__(self, app: ASGIApp):
        super().__init__(app)
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)
        
        # Add security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        
        # Content Security Policy (Swagger UI friendly)
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
            "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://fastapi.tiangolo.com; "
            "img-src 'self' data: https: https://fastapi.tiangolo.com; "
            "font-src 'self' https://cdn.jsdelivr.net; "
            "connect-src 'self'"
        )
        
        return response


class RequestSizeLimitMiddleware(BaseHTTPMiddleware):
    """Limit request body size"""
    
    def __init__(self, app: ASGIApp, max_size: int = 10 * 1024 * 1024):  # 10MB default
        super().__init__(app)
        self.max_size = max_size
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Check content length
        content_length = request.headers.get("content-length")
        
        if content_length:
            content_length = int(content_length)
            if content_length > self.max_size:
                logger.warning(
                    f"Request body too large: {content_length} bytes",
                    extra={
                        "client_ip": request.client.host if request.client else "unknown",
                        "path": request.url.path,
                        "content_length": content_length,
                        "max_size": self.max_size
                    }
                )
                
                increment_counter("request_too_large_total")
                
                return JSONResponse(
                    status_code=413,
                    content={
                        "error": "request_too_large",
                        "message": f"Request body too large. Maximum allowed: {self.max_size} bytes",
                        "max_size": self.max_size
                    }
                )
        
        return await call_next(request)


class HealthCheckMiddleware(BaseHTTPMiddleware):
    """Handle health check requests efficiently"""
    
    def __init__(self, app: ASGIApp):
        super().__init__(app)
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Quick response for health checks to avoid unnecessary processing
        if request.url.path == "/health" and request.method == "GET":
            return JSONResponse(
                status_code=200,
                content={
                    "status": "healthy",
                    "timestamp": time.time()
                }
            )
        
        return await call_next(request)