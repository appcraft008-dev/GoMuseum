"""
Custom exception classes for GoMuseum backend
Provides domain-specific exceptions with clear error messages
"""

from typing import Optional


class GoMuseumException(Exception):
    """Base exception class for all GoMuseum errors"""

    def __init__(self, message: str, detail: Optional[str] = None):
        self.message = message
        self.detail = detail
        super().__init__(self.message)


class ValidationException(GoMuseumException):
    """Raised when input validation fails"""

    pass


class ServiceException(GoMuseumException):
    """Raised when a service operation fails"""

    pass


class DatabaseException(GoMuseumException):
    """Raised when database operations fail"""

    pass


class CacheException(GoMuseumException):
    """Raised when cache operations fail"""

    pass


class AIServiceException(GoMuseumException):
    """Raised when AI service calls fail"""

    pass


class ImageProcessingException(GoMuseumException):
    """Raised when image processing fails"""

    pass


class TimeoutException(GoMuseumException):
    """Raised when operations exceed timeout limits"""

    pass


class NotFoundException(GoMuseumException):
    """Raised when requested resource is not found"""

    pass
