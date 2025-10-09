"""
TTS (Text-to-Speech) Schemas
Request/response models for audio generation (Step 2)
"""

from pydantic import BaseModel, Field, validator
from typing import Optional
from datetime import datetime
from enum import Enum


class Voice(str, Enum):
    """Supported TTS voices"""
    ALLOY = "alloy"
    ECHO = "echo"
    FABLE = "fable"
    ONYX = "onyx"
    NOVA = "nova"
    SHIMMER = "shimmer"


class TTSModel(str, Enum):
    """Supported TTS models"""
    TTS_1 = "tts-1"
    TTS_1_HD = "tts-1-hd"


class TTSRequest(BaseModel):
    """Request model for TTS audio generation"""

    text: str = Field(
        ...,
        min_length=1,
        max_length=4096,
        description="Text to convert to speech (max 4096 chars)"
    )
    language: str = Field(
        default="en",
        min_length=2,
        max_length=10,
        description="Language code (en, fr, de, es, it, zh)"
    )
    voice: Voice = Field(
        default=Voice.ALLOY,
        description="Voice to use for TTS"
    )
    model: TTSModel = Field(
        default=TTSModel.TTS_1,
        description="TTS model to use"
    )
    speed: float = Field(
        default=1.0,
        ge=0.25,
        le=4.0,
        description="Speech speed (0.25 to 4.0)"
    )

    @validator('text')
    def validate_text_not_empty(cls, v):
        if not v or not v.strip():
            raise ValueError("Text cannot be empty")
        return v.strip()

    class Config:
        use_enum_values = True
        json_schema_extra = {
            "example": {
                "text": "The Mona Lisa is a portrait painting by Leonardo da Vinci.",
                "language": "en",
                "voice": "alloy",
                "model": "tts-1",
                "speed": 1.0
            }
        }


class TTSResponse(BaseModel):
    """Response model for TTS audio generation"""

    id: str = Field(..., description="Unique audio ID")
    audio_url: str = Field(..., description="URL to access the audio file")
    file_path: str = Field(..., description="Server file path")
    file_size_bytes: int = Field(..., description="Audio file size in bytes")
    duration_seconds: Optional[int] = Field(None, description="Estimated audio duration")
    voice: str = Field(..., description="Voice used")
    model: str = Field(..., description="TTS model used")
    speed: float = Field(default=1.0, description="Speech speed")
    created_at: datetime = Field(default_factory=datetime.now, description="Creation timestamp")
    expires_at: Optional[datetime] = Field(None, description="Expiration timestamp (if applicable)")
    cached: bool = Field(default=False, description="Whether result was from cache")

    class Config:
        json_schema_extra = {
            "example": {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "audio_url": "https://cdn.example.com/audio/abc123.mp3",
                "file_path": "/app/storage/audio/abc123.mp3",
                "file_size_bytes": 45678,
                "duration_seconds": 15,
                "voice": "alloy",
                "model": "tts-1",
                "speed": 1.0,
                "created_at": "2024-10-03T14:30:00",
                "expires_at": None,
                "cached": False
            }
        }


class TTSError(BaseModel):
    """Error response for TTS operations"""

    error: str = Field(..., description="Error type")
    detail: str = Field(..., description="Error details")
    timestamp: datetime = Field(default_factory=datetime.now)

    class Config:
        json_schema_extra = {
            "example": {
                "error": "UnsupportedVoice",
                "detail": "Voice 'invalid_voice' is not supported. Supported voices: alloy, echo, fable, onyx, nova, shimmer",
                "timestamp": "2024-10-03T14:30:00"
            }
        }
