"""
Unified Exception Handling Module

Provides consistent exception handling, error responses, and logging
across the entire application following DDD error handling patterns.
"""

from typing import Any, Dict, Optional, Union
from fastapi import HTTPException, Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.status import (
    HTTP_400_BAD_REQUEST, HTTP_401_UNAUTHORIZED, HTTP_403_FORBIDDEN,
    HTTP_404_NOT_FOUND, HTTP_409_CONFLICT, HTTP_422_UNPROCESSABLE_ENTITY,
    HTTP_429_TOO_MANY_REQUESTS, HTTP_500_INTERNAL_SERVER_ERROR
)
import traceback
from datetime import datetime, timezone

from app.core.logging import get_logger

logger = get_logger(__name__)


# Domain Exceptions (Business Logic Errors)
class DomainException(Exception):
    """Base class for domain/business logic exceptions"""
    def __init__(self, message: str, error_code: str = "DOMAIN_ERROR", details: Optional[Dict] = None):
        self.message = message
        self.error_code = error_code
        self.details = details or {}
        super().__init__(message)


class ValidationError(DomainException):
    """Domain validation errors"""
    def __init__(self, message: str, field: Optional[str] = None, details: Optional[Dict] = None):
        super().__init__(message, "VALIDATION_ERROR", details)
        self.field = field


class BusinessRuleViolation(DomainException):
    """Business rule violations"""
    def __init__(self, message: str, rule: str, details: Optional[Dict] = None):
        super().__init__(message, "BUSINESS_RULE_VIOLATION", details)
        self.rule = rule


class ResourceNotFound(DomainException):
    """Resource not found errors"""
    def __init__(self, resource_type: str, resource_id: str, details: Optional[Dict] = None):
        message = f"{resource_type} with ID '{resource_id}' not found"
        super().__init__(message, "RESOURCE_NOT_FOUND", details)
        self.resource_type = resource_type
        self.resource_id = resource_id


class ResourceConflict(DomainException):
    """Resource conflict errors"""
    def __init__(self, resource_type: str, conflict_reason: str, details: Optional[Dict] = None):
        message = f"{resource_type} conflict: {conflict_reason}"
        super().__init__(message, "RESOURCE_CONFLICT", details)
        self.resource_type = resource_type
        self.conflict_reason = conflict_reason


# Infrastructure Exceptions
class InfrastructureException(Exception):
    """Base class for infrastructure exceptions"""
    def __init__(self, message: str, error_code: str = "INFRASTRUCTURE_ERROR", details: Optional[Dict] = None):
        self.message = message
        self.error_code = error_code
        self.details = details or {}
        super().__init__(message)


class DatabaseException(InfrastructureException):
    """Database-related errors"""
    def __init__(self, message: str, query: Optional[str] = None, details: Optional[Dict] = None):
        super().__init__(message, "DATABASE_ERROR", details)
        self.query = query


class CacheException(InfrastructureException):
    """Cache-related errors"""
    def __init__(self, message: str, cache_key: Optional[str] = None, details: Optional[Dict] = None):
        super().__init__(message, "CACHE_ERROR", details)
        self.cache_key = cache_key


class ExternalServiceException(InfrastructureException):
    """External service errors"""
    def __init__(self, service_name: str, message: str, status_code: Optional[int] = None, details: Optional[Dict] = None):
        super().__init__(message, "EXTERNAL_SERVICE_ERROR", details)
        self.service_name = service_name
        self.status_code = status_code


# Authentication & Authorization Exceptions
class AuthenticationException(Exception):
    """Authentication-related errors"""
    def __init__(self, message: str, error_code: str = "AUTHENTICATION_ERROR", details: Optional[Dict] = None):
        self.message = message
        self.error_code = error_code
        self.details = details or {}
        super().__init__(message)


class AuthorizationException(Exception):
    """Authorization-related errors"""
    def __init__(self, message: str, required_permission: Optional[str] = None, details: Optional[Dict] = None):
        self.message = message
        self.error_code = "AUTHORIZATION_ERROR"
        self.required_permission = required_permission
        self.details = details or {}
        super().__init__(message)


class RateLimitException(Exception):
    """Rate limiting errors"""
    def __init__(self, message: str, limit: int, window: int, details: Optional[Dict] = None):
        self.message = message
        self.error_code = "RATE_LIMIT_EXCEEDED"
        self.limit = limit
        self.window = window
        self.details = details or {}
        super().__init__(message)


# Error Response Formatters
class ErrorResponseFormatter:
    """Formats error responses consistently"""
    
    @staticmethod
    def format_error_response(
        error_code: str,
        message: str,
        details: Optional[Dict] = None,
        timestamp: Optional[str] = None,
        request_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Format standardized error response"""
        response = {
            "error": {
                "code": error_code,
                "message": message,
                "timestamp": timestamp or datetime.now(timezone.utc).isoformat()
            }
        }
        
        if details:
            response["error"]["details"] = details
        
        if request_id:
            response["error"]["request_id"] = request_id
        
        return response
    
    @staticmethod
    def format_validation_error_response(
        errors: list,
        message: str = "Validation failed"
    ) -> Dict[str, Any]:
        """Format validation error response"""
        return ErrorResponseFormatter.format_error_response(
            error_code="VALIDATION_ERROR",
            message=message,
            details={"validation_errors": errors}
        )


# Exception to HTTP Status Code Mapping
def get_http_status_code(exception: Exception) -> int:
    """Map exceptions to appropriate HTTP status codes"""
    
    # Domain exceptions
    if isinstance(exception, ValidationError):
        return HTTP_422_UNPROCESSABLE_ENTITY
    
    if isinstance(exception, BusinessRuleViolation):
        return HTTP_400_BAD_REQUEST
    
    if isinstance(exception, ResourceNotFound):
        return HTTP_404_NOT_FOUND
    
    if isinstance(exception, ResourceConflict):
        return HTTP_409_CONFLICT
    
    # Authentication & Authorization
    if isinstance(exception, AuthenticationException):
        return HTTP_401_UNAUTHORIZED
    
    if isinstance(exception, AuthorizationException):
        return HTTP_403_FORBIDDEN
    
    if isinstance(exception, RateLimitException):
        return HTTP_429_TOO_MANY_REQUESTS
    
    # FastAPI HTTPException
    if isinstance(exception, HTTPException):
        return exception.status_code
    
    # Infrastructure exceptions -> Internal Server Error
    if isinstance(exception, InfrastructureException):
        return HTTP_500_INTERNAL_SERVER_ERROR
    
    # Default to Internal Server Error
    return HTTP_500_INTERNAL_SERVER_ERROR


# Global Exception Handler
class ExceptionHandlerMiddleware(BaseHTTPMiddleware):
    """Global exception handling middleware"""
    
    async def dispatch(self, request: Request, call_next):
        try:
            response = await call_next(request)
            return response
            
        except Exception as e:
            return await self._handle_exception(request, e)
    
    async def _handle_exception(self, request: Request, exception: Exception) -> JSONResponse:
        """Handle exceptions and return appropriate responses"""
        
        request_id = getattr(request.state, 'request_id', None)
        
        # Log exception details
        logger.error(
            f"Exception in {request.method} {request.url.path}: {str(exception)}",
            extra={
                "exception_type": type(exception).__name__,
                "request_id": request_id,
                "path": request.url.path,
                "method": request.method,
                "client_ip": request.client.host if request.client else None
            },
            exc_info=True
        )
        
        # Get HTTP status code
        status_code = get_http_status_code(exception)
        
        # Format error response based on exception type
        if isinstance(exception, DomainException):
            error_response = ErrorResponseFormatter.format_error_response(
                error_code=exception.error_code,
                message=exception.message,
                details=exception.details,
                request_id=request_id
            )
        
        elif isinstance(exception, AuthenticationException):
            error_response = ErrorResponseFormatter.format_error_response(
                error_code=exception.error_code,
                message=exception.message,
                details=exception.details,
                request_id=request_id
            )
        
        elif isinstance(exception, AuthorizationException):
            error_response = ErrorResponseFormatter.format_error_response(
                error_code=exception.error_code,
                message=exception.message,
                details={
                    "required_permission": exception.required_permission,
                    **exception.details
                },
                request_id=request_id
            )
        
        elif isinstance(exception, RateLimitException):
            error_response = ErrorResponseFormatter.format_error_response(
                error_code=exception.error_code,
                message=exception.message,
                details={
                    "limit": exception.limit,
                    "window": exception.window,
                    **exception.details
                },
                request_id=request_id
            )
        
        elif isinstance(exception, HTTPException):
            error_response = ErrorResponseFormatter.format_error_response(
                error_code="HTTP_ERROR",
                message=str(exception.detail) if exception.detail else "HTTP Error",
                request_id=request_id
            )
        
        else:
            # Generic internal server error
            error_response = ErrorResponseFormatter.format_error_response(
                error_code="INTERNAL_SERVER_ERROR",
                message="An unexpected error occurred. Please try again later.",
                request_id=request_id
            )
        
        return JSONResponse(
            status_code=status_code,
            content=error_response
        )


# Convenience functions for raising HTTP exceptions
def raise_validation_error(message: str, field: Optional[str] = None, details: Optional[Dict] = None):
    """Raise a validation error"""
    raise ValidationError(message, field, details)


def raise_not_found(resource_type: str, resource_id: str, details: Optional[Dict] = None):
    """Raise a not found error"""
    raise ResourceNotFound(resource_type, resource_id, details)


def raise_conflict(resource_type: str, conflict_reason: str, details: Optional[Dict] = None):
    """Raise a conflict error"""
    raise ResourceConflict(resource_type, conflict_reason, details)


def raise_business_rule_violation(message: str, rule: str, details: Optional[Dict] = None):
    """Raise a business rule violation"""
    raise BusinessRuleViolation(message, rule, details)


def raise_authentication_error(message: str, details: Optional[Dict] = None):
    """Raise an authentication error"""
    raise AuthenticationException(message, details=details)


def raise_authorization_error(message: str, required_permission: Optional[str] = None, details: Optional[Dict] = None):
    """Raise an authorization error"""
    raise AuthorizationException(message, required_permission, details)


def raise_rate_limit_error(message: str, limit: int, window: int, details: Optional[Dict] = None):
    """Raise a rate limit error"""
    raise RateLimitException(message, limit, window, details)


# Error tracking for monitoring
class ErrorTracker:
    """Track errors for monitoring and alerting"""
    
    def __init__(self):
        self.error_counts = {}
        self.error_patterns = {}
    
    def track_error(self, exception: Exception, request_path: str):
        """Track error occurrence"""
        error_type = type(exception).__name__
        
        # Count errors by type
        if error_type not in self.error_counts:
            self.error_counts[error_type] = 0
        self.error_counts[error_type] += 1
        
        # Track error patterns
        pattern_key = f"{error_type}:{request_path}"
        if pattern_key not in self.error_patterns:
            self.error_patterns[pattern_key] = 0
        self.error_patterns[pattern_key] += 1
        
        # Log for monitoring systems
        if self.error_counts[error_type] > 10:  # Alert threshold
            logger.warning(
                f"High error frequency detected: {error_type}",
                extra={
                    "error_type": error_type,
                    "count": self.error_counts[error_type],
                    "path_pattern": request_path
                }
            )
    
    def get_error_stats(self) -> Dict[str, Any]:
        """Get error statistics"""
        return {
            "error_counts": self.error_counts.copy(),
            "error_patterns": self.error_patterns.copy(),
            "total_errors": sum(self.error_counts.values())
        }


# Global error tracker
error_tracker = ErrorTracker()


# Health check for exception handling
def exception_handling_health_check() -> Dict[str, Any]:
    """Check exception handling system health"""
    try:
        stats = error_tracker.get_error_stats()
        
        return {
            "status": "healthy",
            "error_tracking": "enabled",
            "total_errors_tracked": stats["total_errors"],
            "unique_error_types": len(stats["error_counts"])
        }
        
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e)
        }