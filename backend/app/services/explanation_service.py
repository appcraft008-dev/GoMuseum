"""
Explanation Service
Main business logic for artwork explanation generation workflow (Step 2)
"""

import hashlib
import json
import logging
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
from datetime import datetime

from app.models.explanation import Explanation
from app.schemas.explanation import ExplanationResponse, Language, DetailLevel
from app.services.ai_service import AIService
from app.services.cache_service import CacheService
from app.core.exceptions import ServiceException, NotFoundException
from app.core.config import settings

logger = logging.getLogger(__name__)


class ExplanationService:
    """Service for managing artwork explanation generation workflow"""

    def __init__(
        self,
        db: Session,
        ai_service: AIService,
        cache_service: CacheService,
        tts_service: Optional[Any] = None,
    ):
        """
        Initialize explanation service

        Args:
            db: Database session
            ai_service: AI service for content generation
            cache_service: Cache service for result caching
            tts_service: TTS service for audio generation (optional)
        """
        self.db = db
        self.ai_service = ai_service
        self.cache_service = cache_service
        self.tts_service = tts_service

    async def generate_explanation(
        self,
        artwork_name: str,
        language: str,
        detail_level: str = "standard",
        recognition_id: Optional[str] = None,
        include_audio: bool = False,
    ) -> ExplanationResponse:
        """
        Main explanation generation workflow:
        1. Validate language
        2. Check Redis cache
        3. Check database
        4. Generate with AI
        5. Store in database
        6. Generate TTS audio (if requested)
        7. Cache in Redis
        8. Return result

        Args:
            artwork_name: Name of the artwork
            language: Target language code (en, fr, de, es, it, zh)
            detail_level: Content detail level (brief, standard, detailed)
            recognition_id: Optional associated recognition result ID
            include_audio: Whether to generate TTS audio (default: False)

        Returns:
            ExplanationResponse with explanation content and optional audio

        Raises:
            ServiceException: If language not supported or generation fails
        """
        try:
            # 1. Validate language
            logger.info(f"Generating explanation for '{artwork_name}' in language '{language}'")
            if language not in settings.SUPPORTED_LANGUAGES:
                raise ServiceException(
                    f"Language '{language}' is not supported",
                    detail=f"Supported languages: {', '.join(settings.SUPPORTED_LANGUAGES)}",
                )

            # 2. Check Redis cache
            cache_key = f"explanation:{artwork_name}:{language}"
            logger.info(f"Checking cache with key: {cache_key}")

            if self.cache_service and self.cache_service.redis_client:
                try:
                    cached_data = self.cache_service.get(cache_key)
                    if cached_data:
                        logger.info(f"Cache hit for {cache_key}")
                        # Ensure cached flag is set
                        if isinstance(cached_data, dict):
                            cached_data["cached"] = True
                            return ExplanationResponse(**cached_data)
                except Exception as e:
                    logger.warning(f"Cache lookup failed: {str(e)}")
                    # Continue with database and AI fallback

            # 3. Check database
            logger.info(f"Checking database for artwork='{artwork_name}', language='{language}'")
            db_result = (
                self.db.query(Explanation)
                .filter(
                    Explanation.artwork_name == artwork_name,
                    Explanation.language == language,
                )
                .first()
            )

            if db_result:
                logger.info(f"Database hit for artwork '{artwork_name}'")

                # Extract metadata safely - use dict to handle mock objects
                response_data = {
                    "id": str(db_result.id),
                    "artwork_name": db_result.artwork_name,
                    "language": db_result.language,
                    "content": db_result.content,
                    "audio_url": None,
                    "audio_duration_seconds": None,
                    "timestamp": datetime.now(),
                    "cached": False,
                    "processing_time_ms": 0,
                    "metadata": {},
                }

                # Safely extract optional fields - check types to avoid MagicMock objects
                audio_url = getattr(db_result, "audio_url", None)
                if isinstance(audio_url, (str, type(None))):
                    response_data["audio_url"] = audio_url

                audio_duration = getattr(db_result, "audio_duration_seconds", None)
                if isinstance(audio_duration, (int, type(None))):
                    response_data["audio_duration_seconds"] = audio_duration

                timestamp = getattr(db_result, "timestamp", None)
                if timestamp is not None and hasattr(timestamp, "isoformat"):  # Check if it's a datetime object
                    response_data["timestamp"] = timestamp

                meta_info = getattr(db_result, "meta_info", None)
                if isinstance(meta_info, dict):
                    response_data["metadata"] = meta_info

                response = ExplanationResponse(**response_data)

                # Update cache
                self._cache_explanation(cache_key, response)
                return response

            # 4. Generate with AI
            logger.info(f"No cache/DB hit, generating with AI for '{artwork_name}'")

            # Get recognition data if recognition_id provided
            recognition_data = None
            if recognition_id:
                recognition_data = self._get_recognition_data(recognition_id)

            # Build prompt
            prompt = self._build_prompt(
                artwork_name=artwork_name,
                language=language,
                detail_level=detail_level,
                recognition_data=recognition_data,
            )

            # Call AI service
            ai_result = await self.ai_service.generate_content(
                prompt=prompt, language=language, detail_level=detail_level
            )

            # 5. Store in database
            logger.info(f"Storing explanation in database for '{artwork_name}'")
            content_hash = self._generate_content_hash(artwork_name, language)

            db_model = Explanation(
                artwork_name=artwork_name,
                language=language,
                content=ai_result["content"],
                content_hash=content_hash,
                meta_info={
                    "detail_level": detail_level,
                    "word_count": ai_result.get("word_count", 0),
                    "recognition_id": recognition_id,
                },
            )

            self.db.add(db_model)
            self.db.commit()
            self.db.refresh(db_model)
            logger.info(f"Saved explanation with ID: {db_model.id}")

            # 6. Generate TTS audio if requested
            audio_url = None
            audio_duration = None
            if include_audio and self.tts_service:
                try:
                    logger.info(f"Generating TTS audio for '{artwork_name}'")
                    tts_result = await self.tts_service.generate_audio(
                        text=ai_result["content"],
                        language=language,
                        voice=self.tts_service.get_recommended_voice(language),
                    )
                    audio_url = tts_result.audio_url
                    audio_duration = tts_result.duration_seconds

                    # Update database with audio info
                    db_model.audio_url = audio_url
                    db_model.audio_duration_seconds = audio_duration
                    self.db.commit()
                    self.db.refresh(db_model)
                    logger.info(f"TTS audio generated: {audio_url}")
                except Exception as e:
                    logger.warning(f"TTS generation failed, continuing without audio: {str(e)}")
                    # Continue without audio - don't fail the whole request

            # 7. Create response from model
            # Use a temporary dict to safely extract attributes
            response_data = {
                "id": str(db_model.id),
                "artwork_name": db_model.artwork_name,
                "language": db_model.language,
                "content": db_model.content,
                "audio_url": db_model.audio_url,  # Use actual value from db_model
                "audio_duration_seconds": db_model.audio_duration_seconds,  # Use actual value
                "timestamp": db_model.timestamp if db_model.timestamp is not None else datetime.now(),
                "cached": False,
                "processing_time_ms": 0,
                "metadata": db_model.meta_info if db_model.meta_info else {},
            }

            response = ExplanationResponse(**response_data)

            # 8. Cache result
            self._cache_explanation(cache_key, response)

            logger.info(f"Explanation generation completed for '{artwork_name}'")
            return response

        except ServiceException:
            raise
        except Exception as e:
            logger.error(f"Explanation generation failed: {str(e)}", exc_info=True)
            self.db.rollback()
            raise ServiceException("Explanation generation failed", detail=str(e))

    def _build_prompt(
        self,
        artwork_name: str,
        language: str,
        detail_level: str,
        recognition_data: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Build AI prompt for explanation generation

        Args:
            artwork_name: Name of the artwork
            language: Target language code
            detail_level: Content detail level
            recognition_data: Optional recognition context data

        Returns:
            Formatted prompt string
        """
        # Language-specific instructions
        language_instructions = {
            "en": "Provide a detailed explanation in English",
            "fr": "Fournir une explication détaillée en français",
            "de": "Geben Sie eine detaillierte Erklärung auf Deutsch",
            "es": "Proporcionar una explicación detallada en español",
            "it": "Fornire una spiegazione dettagliata in italiano",
            "zh": "请用中文提供详细的介绍",
        }

        # Detail level instructions (language-specific)
        if language == "zh":
            detail_instructions = {
                "brief": "请提供简要介绍（2-3句话，50-100字）。",
                "standard": "请提供标准介绍（5-8句话，150-300字）。",
                "detailed": "请提供详细介绍（10句话以上，400-600字）。",
            }
        else:
            detail_instructions = {
                "brief": "Keep the explanation brief (2-3 sentences, 50-100 words).",
                "standard": "Provide a standard explanation (5-8 sentences, 150-300 words).",
                "detailed": "Provide a detailed explanation (10+ sentences, 400-600 words).",
            }

        lang_instruction = language_instructions.get(language, language_instructions["en"])
        detail_instruction = detail_instructions.get(detail_level, detail_instructions["standard"])

        prompt = f"""{lang_instruction} about the artwork "{artwork_name}".

{detail_instruction}

Include information about:
- The artist and creation period
- Historical and cultural context
- Artistic style and techniques
- Significance and impact"""

        # Add recognition context if available
        if recognition_data:
            context = f"""

Additional context from image recognition:
- Artist: {recognition_data.get('artist', 'Unknown')}
- Period: {recognition_data.get('period', 'Unknown')}
- Description: {recognition_data.get('description', 'N/A')}"""
            prompt += context

        # Chinese-specific formatting
        if language == "zh":
            prompt += "\n\n请用简洁、准确的中文进行介绍，适合博物馆游客阅读。"
        elif language == "en":
            prompt += "\n\nWrite in clear, engaging language suitable for museum visitors."

        return prompt

    def _generate_content_hash(self, artwork_name: str, language: str) -> str:
        """
        Generate SHA256 hash for content deduplication

        Args:
            artwork_name: Name of the artwork
            language: Language code

        Returns:
            64-character hex hash string
        """
        content = f"{artwork_name}:{language}"
        hash_obj = hashlib.sha256(content.encode("utf-8"))
        return hash_obj.hexdigest()

    def _get_recognition_data(self, recognition_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve recognition data for context

        Args:
            recognition_id: Recognition result ID

        Returns:
            Dictionary with recognition data or None
        """
        try:
            from app.models.recognition_result import RecognitionResult
            from uuid import UUID

            result_uuid = UUID(recognition_id)
            result = (
                self.db.query(RecognitionResult)
                .filter(RecognitionResult.id == result_uuid)
                .first()
            )

            if result:
                return {
                    "artist": result.artist,
                    "period": result.period,
                    "description": result.description,
                }
        except Exception as e:
            logger.warning(f"Failed to retrieve recognition data: {str(e)}")

        return None

    def _cache_explanation(self, cache_key: str, response: ExplanationResponse) -> None:
        """
        Cache explanation result in Redis with error handling

        Args:
            cache_key: Redis cache key
            response: Explanation response to cache
        """
        if not self.cache_service or not self.cache_service.redis_client:
            logger.debug("Cache service not available, skipping cache write")
            return

        try:
            # Convert to dict for JSON serialization
            data = response.model_dump(mode="json")
            self.cache_service.set(
                cache_key, data, ttl=getattr(settings, "EXPLANATION_CACHE_TTL", 604800)
            )
            logger.info(f"Cached explanation with key: {cache_key}")
        except Exception as e:
            # Cache failure should not break the flow
            logger.warning(f"Failed to cache explanation: {str(e)}")

    def get_explanation_by_id(self, explanation_id: str) -> ExplanationResponse:
        """
        Retrieve explanation by ID

        Args:
            explanation_id: UUID of the explanation

        Returns:
            ExplanationResponse

        Raises:
            NotFoundException: If explanation not found
        """
        try:
            result = self.db.query(Explanation).filter(
                Explanation.id == explanation_id
            ).first()

            if not result:
                raise NotFoundException(f"Explanation not found: {explanation_id}")

            return ExplanationResponse(
                id=str(result.id),
                artwork_name=result.artwork_name,
                language=result.language,
                content=result.content,
                audio_url=result.audio_url,
                audio_duration_seconds=result.audio_duration_seconds,
                timestamp=result.timestamp,
                cached=False,
                processing_time_ms=0,
            )

        except NotFoundException:
            raise
        except Exception as e:
            logger.error(f"Error retrieving explanation: {str(e)}")
            raise ServiceException(f"Failed to retrieve explanation: {str(e)}")

    def get_statistics(self) -> Dict[str, Any]:
        """
        Get explanation generation statistics

        Returns:
            Dictionary with statistics
        """
        try:
            total_explanations = self.db.query(Explanation).count()

            # Count by language
            language_stats = {}
            for lang in settings.SUPPORTED_LANGUAGES:
                count = self.db.query(Explanation).filter(
                    Explanation.language == lang
                ).count()
                language_stats[lang] = count

            return {
                "total_explanations": total_explanations,
                "by_language": language_stats,
            }

        except Exception as e:
            logger.error(f"Error retrieving statistics: {str(e)}")
            raise ServiceException(f"Failed to retrieve statistics: {str(e)}")


def get_explanation_service(
    db: Session,
    ai_service: Optional[AIService] = None,
    cache_service: Optional[CacheService] = None,
    tts_service: Optional[Any] = None,
) -> ExplanationService:
    """
    Factory function to create ExplanationService with dependencies

    Args:
        db: Database session
        ai_service: Optional AI service (creates new if not provided)
        cache_service: Optional cache service (creates new if not provided)
        tts_service: Optional TTS service

    Returns:
        Configured ExplanationService instance
    """
    if ai_service is None:
        from app.services.ai_service import get_ai_service

        ai_service = get_ai_service()

    if cache_service is None:
        cache_service = CacheService()

    return ExplanationService(
        db=db,
        ai_service=ai_service,
        cache_service=cache_service,
        tts_service=tts_service,
    )
