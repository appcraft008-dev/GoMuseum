from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime

class CandidateArtwork(BaseModel):
    artwork_id: str = Field(..., description="Unique identifier for the artwork")
    name: str = Field(..., description="Name of the artwork")
    artist: str = Field(..., description="Artist name")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Recognition confidence score")
    museum: str = Field(..., description="Museum name")
    period: Optional[str] = Field(None, description="Time period or year")
    image_url: Optional[str] = Field(None, description="Thumbnail image URL")
    
    class Config:
        schema_extra = {
            "example": {
                "artwork_id": "uuid-string",
                "name": "蒙娜丽莎",
                "artist": "达芬奇",
                "confidence": 0.95,
                "museum": "卢浮宫",
                "period": "1503-1519",
                "image_url": "https://example.com/thumb.jpg"
            }
        }

class RecognitionRequest(BaseModel):
    image: str = Field(..., description="Base64 encoded image data")
    user_id: Optional[str] = Field(None, description="User ID for quota management")
    language: str = Field("zh", description="Preferred language for results")
    max_candidates: int = Field(3, ge=1, le=10, description="Maximum number of candidates to return")
    
    class Config:
        schema_extra = {
            "example": {
                "image": "data:image/jpeg;base64,/9j/4AAQSkZJRgABAQEAYABg...",
                "user_id": "uuid-string",
                "language": "zh",
                "max_candidates": 3
            }
        }

class RecognitionResponse(BaseModel):
    success: bool = Field(..., description="Whether recognition was successful")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Overall confidence score")
    processing_time: float = Field(..., description="Processing time in seconds")
    candidates: List[CandidateArtwork] = Field(..., description="List of candidate artworks")
    cached: bool = Field(False, description="Whether result was served from cache")
    timestamp: datetime = Field(..., description="Recognition timestamp")
    
    # Additional metadata
    image_hash: Optional[str] = Field(None, description="Hash of the processed image")
    model_used: Optional[str] = Field(None, description="AI model used for recognition")
    
    class Config:
        schema_extra = {
            "example": {
                "success": True,
                "confidence": 0.95,
                "processing_time": 2.3,
                "candidates": [
                    {
                        "artwork_id": "uuid-1",
                        "name": "蒙娜丽莎",
                        "artist": "达芬奇",
                        "confidence": 0.95,
                        "museum": "卢浮宫",
                        "period": "1503-1519"
                    }
                ],
                "cached": False,
                "timestamp": "2024-01-01T12:00:00Z",
                "image_hash": "abc123",
                "model_used": "gpt-4-vision"
            }
        }

class RecognitionError(BaseModel):
    success: bool = Field(False)
    error_code: str = Field(..., description="Error code")
    error_message: str = Field(..., description="Human-readable error message")
    timestamp: datetime = Field(..., description="Error timestamp")
    
    class Config:
        schema_extra = {
            "example": {
                "success": False,
                "error_code": "RECOGNITION_FAILED",
                "error_message": "Unable to recognize artwork in the provided image",
                "timestamp": "2024-01-01T12:00:00Z"
            }
        }