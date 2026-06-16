"""
Content API Endpoints
Handles AI explanation generation and TTS audio generation
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.core.database import SessionLocal
from app.core.exceptions import AIServiceException
from app.services.content_generation_service import get_content_generation_service
from app.services.content_repo import (
    get_section_audio_key,
    persist_explanation,
    persist_section_audio,
)
from app.services.storage import get_object_storage
from app.services.tts_service import get_tts_service

logger = logging.getLogger(__name__)

router = APIRouter()


# Request/Response Models
class ExplanationRequest(BaseModel):
    """Request model for explanation generation"""

    artwork_name: str = Field(..., description="Name of the artwork")
    artist: str = Field(..., description="Artist name")
    period: str = Field(..., description="Historical period")
    language: str = Field(
        default="en", description="Target language (en, zh, fr, de, es, it)"
    )
    description: Optional[str] = Field(None, description="Optional base description")
    qid: Optional[str] = Field(
        None, description="Wikidata QID；提供时把讲解永久落库到 object_content_section"
    )


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
    qid: Optional[str] = Field(
        None,
        description="Wikidata QID；与 section_code 同时提供时音频落库并返回 audio_url",
    )
    section_code: Optional[str] = Field(
        None, description="内容段落 code（如 overview）；section 模式必填"
    )


class TTSInfoResponse(BaseModel):
    """Response model for TTS metadata"""

    duration_estimate: float
    voice: str
    language: str
    text_hash: str
    size_bytes: int


class AudioUrlResponse(BaseModel):
    """section 模式 TTS 响应：音频已落库，返回 R2 URL"""

    audio_url: str
    cached: bool


@router.post("/explanation", response_model=ExplanationResponse)
async def generate_explanation(
    request: ExplanationRequest, content_service=Depends(get_content_generation_service)
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
    logger.info(
        f"Generating explanation for '{request.artwork_name}' in {request.language}"
    )

    try:
        result = await content_service.generate_explanation(
            artwork_name=request.artwork_name,
            artist=request.artist,
            period=request.period,
            language=request.language,
            description=request.description,
        )

        logger.info(f"Explanation generated successfully for '{request.artwork_name}'")

        # 讲解永久落库（best-effort）：提供了 qid 且非兜底结果时写入 DB；
        # 失败仅告警，绝不影响已成功生成的用户响应。
        if request.qid and not result.get("fallback"):
            db = SessionLocal()
            try:
                persist_explanation(
                    db, request.qid, request.language, result, model="gpt-4o-mini"
                )
            except Exception as persist_err:  # noqa: BLE001
                logger.warning(
                    f"persist_explanation failed for qid={request.qid}: {persist_err}"
                )
            finally:
                db.close()

        return ExplanationResponse(
            title=result["title"],
            summary=result["summary"],
            historical_context=result["historical_context"],
            artistic_analysis=result["artistic_analysis"],
            cultural_significance=result["cultural_significance"],
            interesting_facts=result["interesting_facts"],
            language=result["language"],
            fallback=result.get("fallback", False),
        )

    except AIServiceException as e:
        logger.error(f"Content generation failed: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail={"error": "ContentGenerationError", "detail": str(e)},
        )
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500, detail={"error": "InternalServerError", "detail": str(e)}
        )


@router.post("/tts/generate")
async def generate_tts_audio(request: TTSRequest, tts_service=Depends(get_tts_service)):
    """
    Generate TTS audio from text

    Args:
        request: TTS generation request with text and parameters
        tts_service: TTS service (injected)

    Returns:
        - section 模式（带 qid + section_code）：JSON {audio_url, cached}，音频已落库 R2。
        - ad-hoc 模式（无 qid/section_code）：mp3 流式响应。

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
    # section 模式：qid + section_code 同时存在 → 落库 R2 + 返回 audio_url（懒写复用）
    if request.qid and request.section_code:
        db = SessionLocal()
        try:
            storage = get_object_storage()
            existing = get_section_audio_key(
                db, request.qid, request.language, request.section_code
            )
            if existing:
                return AudioUrlResponse(
                    audio_url=storage.public_url(existing), cached=True
                )
            # section 模式刻意只生成规范版（默认 voice + speed 1.0），忽略 voice/speed：
            # audio_key 不编码 voice/speed，否则同一 section 会产生多份音频、缓存键冲突。
            result = await tts_service.generate_audio(
                text=request.text, language=request.language
            )
            key = persist_section_audio(
                db,
                request.qid,
                request.language,
                request.section_code,
                result["audio_data"],
                storage,
            )
            if key is None:
                raise HTTPException(
                    status_code=404,
                    detail={"error": "ObjectNotFound", "qid": request.qid},
                )
            return AudioUrlResponse(audio_url=storage.public_url(key), cached=False)
        finally:
            db.close()

    logger.info(
        f"Generating TTS audio for text (length: {len(request.text)}) in {request.language}"
    )

    try:
        result = await tts_service.generate_audio(
            text=request.text,
            language=request.language,
            voice=request.voice,
            speed=request.speed,
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
                "X-Language": result["language"],
            },
        )

    except AIServiceException as e:
        logger.error(f"TTS generation failed: {str(e)}")
        raise HTTPException(
            status_code=500, detail={"error": "TTSGenerationError", "detail": str(e)}
        )
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500, detail={"error": "InternalServerError", "detail": str(e)}
        )


@router.post("/tts/info", response_model=TTSInfoResponse)
async def get_tts_info(
    request: TTSRequest, tts_service=Depends(get_tts_service)
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
            speed=request.speed,
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
            size_bytes=0,  # Unknown until generated
        )

    except Exception as e:
        logger.error(f"Error getting TTS info: {str(e)}")
        raise HTTPException(
            status_code=500, detail={"error": "InternalServerError", "detail": str(e)}
        )


@router.get("/tts/voices/{language}")
async def get_supported_voices(language: str, tts_service=Depends(get_tts_service)):
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
            status_code=500, detail={"error": "InternalServerError", "detail": str(e)}
        )
