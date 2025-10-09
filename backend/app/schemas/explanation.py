"""
Pydantic schemas for Explanation API
Request and response models with validation
"""

from pydantic import BaseModel, Field, field_validator
from datetime import datetime
from typing import Optional, Literal, Dict, Any
from enum import Enum


class Language(str, Enum):
    """Supported languages for explanations"""

    EN = "en"
    FR = "fr"
    DE = "de"
    ES = "es"
    IT = "it"
    ZH = "zh"


class DetailLevel(str, Enum):
    """Content detail level"""

    BRIEF = "brief"  # 2-3 sentences
    STANDARD = "standard"  # 5-8 sentences
    DETAILED = "detailed"  # 10+ sentences


class ExplanationRequest(BaseModel):
    """Request schema for generating artwork explanation"""

    artwork_name: str = Field(..., min_length=1, max_length=255, description="Artwork name")
    language: Language = Field(default=Language.EN, description="Target language")
    recognition_id: Optional[str] = Field(None, description="Associated recognition result ID")

    # Optional parameters
    detail_level: DetailLevel = Field(
        default=DetailLevel.STANDARD, description="Content detail level"
    )
    include_audio: bool = Field(default=False, description="Generate TTS audio")

    @field_validator("artwork_name")
    @classmethod
    def validate_artwork_name(cls, v: str) -> str:
        """Validate and normalize artwork name"""
        v = v.strip()
        if not v:
            raise ValueError("Artwork name cannot be empty")
        return v

    class Config:
        json_schema_extra = {
            "example": {
                "artwork_name": "Mona Lisa",
                "language": "en",
                "detail_level": "standard",
                "include_audio": False,
            }
        }


class ExplanationResponse(BaseModel):
    """Response schema for explanation content"""

    id: str = Field(..., description="Unique explanation ID")
    artwork_name: str = Field(..., description="Artwork name")
    language: str = Field(..., description="Language code")
    content: str = Field(..., description="Explanation content")
    audio_url: Optional[str] = Field(None, description="TTS audio URL")
    audio_duration_seconds: Optional[int] = Field(None, description="Audio duration")

    # Metadata
    timestamp: datetime = Field(..., description="Creation timestamp")
    cached: bool = Field(default=False, description="Whether served from cache")
    processing_time_ms: int = Field(default=0, description="Processing time in milliseconds")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")

    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "artwork_name": "Mona Lisa",
                "language": "en",
                "content": "The Mona Lisa is a portrait painting by Leonardo da Vinci...",
                "audio_url": "https://cdn.gomuseum.com/audio/550e8400.mp3",
                "audio_duration_seconds": 45,
                "timestamp": "2024-10-03T12:00:00",
                "cached": False,
                "processing_time_ms": 1200,
            }
        }


class TTSRequest(BaseModel):
    """Request schema for generating TTS audio"""

    explanation_id: str = Field(..., description="Explanation content ID")
    voice: Literal["alloy", "echo", "fable", "onyx", "nova", "shimmer"] = Field(
        default="alloy", description="Voice selection"
    )
    speed: float = Field(default=1.0, ge=0.25, le=4.0, description="Speech speed multiplier")

    class Config:
        json_schema_extra = {
            "example": {"explanation_id": "550e8400-e29b-41d4-a716-446655440000", "voice": "alloy", "speed": 1.0}
        }


class TTSResponse(BaseModel):
    """Response schema for TTS audio"""

    audio_url: str = Field(..., description="Audio file URL")
    duration_seconds: int = Field(..., description="Audio duration")
    file_size_bytes: int = Field(..., description="File size")
    cached: bool = Field(default=False, description="Whether served from cache")

    class Config:
        json_schema_extra = {
            "example": {
                "audio_url": "https://cdn.gomuseum.com/audio/550e8400.mp3",
                "duration_seconds": 45,
                "file_size_bytes": 1024000,
                "cached": False,
            }
        }


class StreamEventType(str, Enum):
    """SSE stream event types"""

    CONTENT_START = "content_start"
    CONTENT_CHUNK = "content_chunk"
    CONTENT_COMPLETE = "content_complete"
    AUDIO_START = "audio_start"
    AUDIO_COMPLETE = "audio_complete"
    ERROR = "error"


class StreamEvent(BaseModel):
    """SSE stream event schema"""

    event_type: StreamEventType = Field(..., description="Event type")
    data: Dict[str, Any] = Field(..., description="Event data")
    timestamp: datetime = Field(default_factory=datetime.now, description="Event timestamp")

    class Config:
        json_schema_extra = {
            "example": {
                "event_type": "content_complete",
                "data": {"content": "The Mona Lisa is...", "processing_time_ms": 1200},
                "timestamp": "2024-10-03T12:00:00",
            }
        }


class ExplanationError(BaseModel):
    """Error response schema"""

    error: str = Field(..., description="Error type")
    detail: Optional[str] = Field(None, description="Detailed error message")

    class Config:
        json_schema_extra = {
            "example": {"error": "UnsupportedLanguage", "detail": "Language 'xx' is not supported"}
        }
