"""
Content API Endpoints
Handles AI explanation generation and TTS audio generation
"""

from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from typing import Optional
import logging

from app.services.content_generation_service import get_content_generation_service
from app.services.tts_service import get_tts_service
from app.core.exceptions import AIServiceException

logger = logging.getLogger(__name__)

router = APIRouter()


# Request/Response Models
class ExplanationRequest(BaseModel):
    """Request model for explanation generation"""
    artwork_name: str = Field(..., description="Name of the artwork")
    artist: str = Field(..., description="Artist name")
    period: str = Field(..., description="Historical period")
    language: str = Field(default="en", description="Target language (en, zh, fr, de, es, it)")
    description: Optional[str] = Field(None, description="Optional base description")


class ExplanationResponse(BaseModel):
    """Response model for explanation"""
    title: str
    summary: str
    historical_context: str
    artistic_analysis: str
    cultural_significance: str
    interesting_facts: list[str]
    language: str
    fallback: Optional[bool] = False


class TTSRequest(BaseModel):
    """Request model for TTS generation"""
    text: str = Field(..., description="Text to convert to speech")
    language: str = Field(default="en", description="Language code")
    voice: Optional[str] = Field(None, description="Voice name (optional)")
    speed: float = Field(default=1.0, ge=0.25, le=4.0, description="Speech speed")


class TTSInfoResponse(BaseModel):
    """Response model for TTS metadata"""
    duration_estimate: float
    voice: str
    language: str
    text_hash: str
    size_bytes: int


@router.post("/explanation", response_model=ExplanationResponse)
async def generate_explanation(
    request: ExplanationRequest,
    content_service = Depends(get_content_generation_service)
) -> ExplanationResponse:
    """
    Generate detailed AI explanation for an artwork

    Args:
        request: Explanation generation request with artwork details
        content_service: Content generation service (injected)

    Returns:
        Detailed explanation with historical context, analysis, and facts

    Example:
        ```bash
        curl -X POST "http://localhost:8000/api/v1/content/explanation" \\
             -H "Content-Type: application/json" \\
             -d '{
                   "artwork_name": "Starry Night",
                   "artist": "Vincent van Gogh",
                   "period": "Post-Impressionism",
                   "language": "en"
                 }'
        ```
    """
    logger.info(f"Generating explanation for '{request.artwork_name}' in {request.language}")

    try:
        result = await content_service.generate_explanation(
            artwork_name=request.artwork_name,
            artist=request.artist,
            period=request.period,
            language=request.language,
            description=request.description
        )

        logger.info(f"Explanation generated successfully for '{request.artwork_name}'")

        return ExplanationResponse(
            title=result["title"],
            summary=result["summary"],
            historical_context=result["historical_context"],
            artistic_analysis=result["artistic_analysis"],
            cultural_significance=result["cultural_significance"],
            interesting_facts=result["interesting_facts"],
            language=result["language"],
            fallback=result.get("fallback", False)
        )

    except AIServiceException as e:
        logger.error(f"Content generation failed: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail={"error": "ContentGenerationError", "detail": str(e)}
        )
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={"error": "InternalServerError", "detail": str(e)}
        )


@router.post("/tts/generate", response_class=StreamingResponse)
async def generate_tts_audio(
    request: TTSRequest,
    tts_service = Depends(get_tts_service)
):
    """
    Generate TTS audio from text

    Args:
        request: TTS generation request with text and parameters
        tts_service: TTS service (injected)

    Returns:
        Audio file as streaming response (MP3 format)

    Example:
        ```bash
        curl -X POST "http://localhost:8000/api/v1/content/tts/generate" \\
             -H "Content-Type: application/json" \\
             -d '{
                   "text": "This is a test",
                   "language": "en",
                   "speed": 1.0
                 }' \\
             --output audio.mp3
        ```
    """
    logger.info(f"Generating TTS audio for text (length: {len(request.text)}) in {request.language}")

    try:
        result = await tts_service.generate_audio(
            text=request.text,
            language=request.language,
            voice=request.voice,
            speed=request.speed
        )

        logger.info(f"TTS audio generated: {result['size_bytes']} bytes")

        # Return audio as streaming response
        return StreamingResponse(
            iter([result["audio_data"]]),
            media_type=result["content_type"],
            headers={
                "Content-Disposition": f'attachment; filename="audio_{result["text_hash"]}.mp3"',
                "X-Duration-Estimate": str(result["duration_estimate"]),
                "X-Voice": result["voice"],
                "X-Language": result["language"]
            }
        )

    except AIServiceException as e:
        logger.error(f"TTS generation failed: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail={"error": "TTSGenerationError", "detail": str(e)}
        )
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={"error": "InternalServerError", "detail": str(e)}
        )


@router.post("/tts/info", response_model=TTSInfoResponse)
async def get_tts_info(
    request: TTSRequest,
    tts_service = Depends(get_tts_service)
) -> TTSInfoResponse:
    """
    Get TTS metadata without generating audio (for caching checks)

    Args:
        request: TTS request parameters
        tts_service: TTS service (injected)

    Returns:
        TTS metadata including hash and estimated duration
    """
    logger.info(f"Getting TTS info for text in {request.language}")

    try:
        # Generate hash for caching
        text_hash = tts_service.generate_text_hash(
            text=request.text,
            language=request.language,
            voice=request.voice,
            speed=request.speed
        )

        # Estimate duration
        word_count = len(request.text.split())
        duration_estimate = (word_count / 150) * 60 / request.speed

        # Get voice
        voice_info = tts_service.get_supported_voices(request.language)
        voice = request.voice or voice_info["default_voice"]

        return TTSInfoResponse(
            duration_estimate=duration_estimate,
            voice=voice,
            language=request.language,
            text_hash=text_hash,
            size_bytes=0  # Unknown until generated
        )

    except Exception as e:
        logger.error(f"Error getting TTS info: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail={"error": "InternalServerError", "detail": str(e)}
        )


@router.get("/tts/voices/{language}")
async def get_supported_voices(
    language: str,
    tts_service = Depends(get_tts_service)
):
    """
    Get supported voices for a language

    Args:
        language: Language code (en, zh, fr, de, es, it)
        tts_service: TTS service (injected)

    Returns:
        List of available voices and default voice
    """
    logger.info(f"Getting supported voices for language: {language}")

    try:
        result = tts_service.get_supported_voices(language)
        return result

    except Exception as e:
        logger.error(f"Error getting voices: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail={"error": "InternalServerError", "detail": str(e)}
        )
