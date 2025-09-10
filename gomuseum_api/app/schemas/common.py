from pydantic import BaseModel, Field
from typing import Generic, TypeVar, Optional, Any, Dict
from datetime import datetime
from enum import Enum

T = TypeVar('T')

class ResponseStatus(str, Enum):
    """API response status enumeration"""
    SUCCESS = "success"
    ERROR = "error"
    WARNING = "warning"


class APIResponse(BaseModel, Generic[T]):
    """Standardized API response format"""
    status: ResponseStatus = ResponseStatus.SUCCESS
    data: Optional[T] = None
    message: Optional[str] = None
    error_code: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    request_id: Optional[str] = None
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class ErrorDetail(BaseModel):
    """Detailed error information"""
    code: str
    message: str
    field: Optional[str] = None
    details: Optional[Dict[str, Any]] = None


class PaginationMeta(BaseModel):
    """Pagination metadata"""
    page: int
    per_page: int
    total: int
    total_pages: int
    has_prev: bool
    has_next: bool


class PaginatedResponse(BaseModel, Generic[T]):
    """Paginated response format"""
    data: list[T]
    meta: PaginationMeta
    
    
# Utility functions for creating standardized responses
def success_response(
    data: Optional[Any] = None,
    message: Optional[str] = None,
    request_id: Optional[str] = None
) -> Dict[str, Any]:
    """Create a successful response"""
    response = APIResponse[Any](
        status=ResponseStatus.SUCCESS,
        data=data,
        message=message,
        request_id=request_id
    )
    return response.model_dump(exclude_none=True)


def error_response(
    message: str,
    error_code: Optional[str] = None,
    data: Optional[Any] = None,
    request_id: Optional[str] = None
) -> Dict[str, Any]:
    """Create an error response"""
    response = APIResponse[Any](
        status=ResponseStatus.ERROR,
        data=data,
        message=message,
        error_code=error_code,
        request_id=request_id
    )
    return response.model_dump(exclude_none=True)


def validation_error_response(
    errors: list[ErrorDetail],
    request_id: Optional[str] = None
) -> Dict[str, Any]:
    """Create a validation error response"""
    return error_response(
        message="Validation failed",
        error_code="VALIDATION_ERROR",
        data={"errors": [error.model_dump() for error in errors]},
        request_id=request_id
    )