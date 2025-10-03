"""
Pydantic schemas for Recognition API
Request and response models with validation
"""

from pydantic import BaseModel, Field, field_validator
from datetime import datetime
from typing import Optional
import base64


class RecognitionRequest(BaseModel):
    """Request schema for artwork recognition"""

    image: str = Field(..., description="Base64 encoded image data")

    @field_validator("image")
    @classmethod
    def validate_image_size(cls, v: str) -> str:
        """Validate Base64 string size (decoded should be < 10MB)"""
        if not v:
            raise ValueError("Image data cannot be empty")

        try:
            # Calculate decoded size
            # Base64 encoding increases size by ~33%, so we check encoded size first
            max_encoded_size = (10 * 1024 * 1024 * 4) // 3  # ~13.3MB encoded
            if len(v) > max_encoded_size:
                raise ValueError("Image size exceeds 10MB limit")

            # Try to decode to verify it's valid base64
            decoded = base64.b64decode(v)
            if len(decoded) > 10 * 1024 * 1024:
                raise ValueError("Decoded image size exceeds 10MB limit")

        except Exception as e:
            if "exceeds 10MB" in str(e):
                raise
            raise ValueError(f"Invalid base64 image data: {str(e)}")

        return v


class RecognitionResponse(BaseModel):
    """Response schema for artwork recognition"""

    id: str = Field(default="", description="Unique recognition result ID")
    artwork_name: str = Field(..., description="Name of the recognized artwork")
    artist: str = Field(..., description="Artist who created the artwork")
    period: str = Field(..., description="Historical period")
    description: str = Field(..., description="Detailed description of the artwork")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score (0-1)")
    timestamp: datetime = Field(default_factory=datetime.now, description="When the recognition was performed")
    
    # Additional fields for cache and performance tracking
    cached: bool = Field(default=False, description="Whether result was served from cache")
    processing_time_ms: int = Field(default=0, description="Processing time in milliseconds")

    class Config:
        from_attributes = True  # Updated from orm_mode in Pydantic v2
        json_schema_extra = {
            "example": {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "artwork_name": "Mona Lisa",
                "artist": "Leonardo da Vinci",
                "period": "Renaissance",
                "description": "A portrait painting of a woman with an enigmatic smile",
                "confidence": 0.95,
                "timestamp": "2025-10-01T12:00:00",
                "cached": False,
                "processing_time_ms": 1500,
            }
        }


class RecognitionError(BaseModel):
    """Error response schema"""

    error: str = Field(..., description="Error type")
    detail: Optional[str] = Field(None, description="Detailed error message")

    class Config:
        json_schema_extra = {
            "example": {
                "error": "ValidationError",
                "detail": "Image size exceeds 10MB limit",
            }
        }


class CacheStats(BaseModel):
    """Cache statistics schema"""

    total_cached: int = Field(..., description="Total number of cached items")
    memory_used: str = Field(..., description="Memory used by cache")
    hit_rate: Optional[float] = Field(
        None, ge=0.0, le=1.0, description="Cache hit rate"
    )


class PerformanceStats(BaseModel):
    """Performance metrics schema"""

    total_requests: int = Field(..., description="Total number of requests")
    average_latency: float = Field(..., description="Average latency in seconds")
    p95_latency: float = Field(..., description="P95 latency in seconds")
    p99_latency: float = Field(..., description="P99 latency in seconds")
    min_latency: float = Field(..., description="Minimum latency in seconds")
    max_latency: float = Field(..., description="Maximum latency in seconds")
