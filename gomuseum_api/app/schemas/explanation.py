from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime

class ExplanationRequest(BaseModel):
    artwork_id: str = Field(..., description="Artwork ID to explain")
    language: str = Field("zh", description="Language for explanation")
    style: str = Field("standard", description="Explanation style: simple, standard, detailed")
    user_id: Optional[str] = Field(None, description="User ID for personalization")
    
    class Config:
        schema_extra = {
            "example": {
                "artwork_id": "uuid-string",
                "language": "zh",
                "style": "standard",
                "user_id": "uuid-string"
            }
        }

class ExplanationSection(BaseModel):
    title: str = Field(..., description="Section title")
    content: str = Field(..., description="Section content")
    order: int = Field(..., description="Display order")
    
class ExplanationResponse(BaseModel):
    artwork_id: str = Field(..., description="Artwork ID")
    artwork_name: str = Field(..., description="Artwork name")
    artist: str = Field(..., description="Artist name")
    
    # Explanation sections
    introduction: str = Field(..., description="Brief introduction (50-100 words)")
    historical_context: str = Field(..., description="Historical background (100-150 words)")
    artistic_features: str = Field(..., description="Key artistic features (100-150 words)")
    cultural_significance: str = Field(..., description="Cultural importance (50-100 words)")
    
    # Additional info
    fun_facts: Optional[List[str]] = Field(None, description="Interesting facts")
    related_works: Optional[List[str]] = Field(None, description="Related artwork IDs")
    
    # Metadata
    language: str = Field(..., description="Language of the explanation")
    word_count: int = Field(..., description="Total word count")
    estimated_reading_time: int = Field(..., description="Estimated reading time in seconds")
    audio_available: bool = Field(False, description="Whether TTS audio is available")
    audio_url: Optional[str] = Field(None, description="URL to audio file")
    
    generated_at: datetime = Field(..., description="Generation timestamp")
    cached: bool = Field(False, description="Whether served from cache")
    
    class Config:
        schema_extra = {
            "example": {
                "artwork_id": "uuid-string",
                "artwork_name": "蒙娜丽莎",
                "artist": "列奥纳多·达芬奇",
                "introduction": "《蒙娜丽莎》是文艺复兴时期最著名的肖像画...",
                "historical_context": "这幅画创作于16世纪初的佛罗伦萨...",
                "artistic_features": "达芬奇运用了独特的渐隐法技巧...",
                "cultural_significance": "作为世界艺术史上的里程碑...",
                "fun_facts": ["画中人物的神秘微笑", "达芬奇用了四年时间完成"],
                "language": "zh",
                "word_count": 456,
                "estimated_reading_time": 90,
                "audio_available": True,
                "audio_url": "https://example.com/audio.mp3",
                "generated_at": "2024-01-01T12:00:00Z",
                "cached": False
            }
        }

class ChatRequest(BaseModel):
    artwork_id: str = Field(..., description="Artwork ID")
    question: str = Field(..., min_length=1, max_length=500, description="User question")
    language: str = Field("zh", description="Language for response")
    conversation_id: Optional[str] = Field(None, description="Conversation ID for context")
    
class ChatResponse(BaseModel):
    artwork_id: str = Field(..., description="Artwork ID")
    question: str = Field(..., description="User question")
    answer: str = Field(..., description="AI-generated answer")
    sources: Optional[List[str]] = Field(None, description="Information sources")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Answer confidence")
    conversation_id: str = Field(..., description="Conversation ID")
    
    language: str = Field(..., description="Response language")
    timestamp: datetime = Field(..., description="Response timestamp")
    
    class Config:
        schema_extra = {
            "example": {
                "artwork_id": "uuid-string",
                "question": "为什么蒙娜丽莎会微笑？",
                "answer": "蒙娜丽莎的微笑是艺术史上最著名的谜题之一...",
                "sources": ["达芬奇传记", "艺术史研究"],
                "confidence": 0.85,
                "conversation_id": "conv-uuid",
                "language": "zh",
                "timestamp": "2024-01-01T12:00:00Z"
            }
        }