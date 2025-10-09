"""
TTS Service
Handles text-to-speech audio generation using OpenAI TTS API (Step 2)
"""

import os
import logging
from uuid import uuid4
from datetime import datetime
from typing import Optional

from openai import AsyncOpenAI

from app.schemas.tts import TTSResponse, Voice
from app.services.cache_service import CacheService
from app.core.exceptions import ServiceException
from app.core.config import settings

logger = logging.getLogger(__name__)


class TTSService:
    """Service for managing text-to-speech audio generation"""

    # Supported voices from OpenAI TTS
    SUPPORTED_VOICES = ["alloy", "echo", "fable", "onyx", "nova", "shimmer"]

    # Max text length for OpenAI TTS API
    MAX_TEXT_LENGTH = 4096

    # Cache TTL: 30 days
    CACHE_TTL = 2592000

    def __init__(
        self,
        cache_service: CacheService,
        storage_path: str,
    ):
        """
        Initialize TTS service

        Args:
            cache_service: Cache service for result caching
            storage_path: Local path for storing audio files
        """
        self.cache_service = cache_service
        self.storage_path = storage_path

        logger.info(f"TTSService initialized with storage_path: {storage_path}")

    async def generate_audio(
        self,
        text: str,
        language: str,
        voice: str,
        model: str = "tts-1",
        speed: float = 1.0,
    ) -> TTSResponse:
        """
        Generate audio from text using OpenAI TTS API

        Workflow:
        1. Validate input parameters
        2. Check Redis cache
        3. Call OpenAI TTS API if cache miss
        4. Save audio file to storage
        5. Generate CDN URL
        6. Cache result
        7. Return TTSResponse

        Args:
            text: Text to convert to speech (max 4096 chars)
            language: Target language code
            voice: Voice to use (alloy, echo, fable, onyx, nova, shimmer)
            model: TTS model to use (default: tts-1)
            speed: Speech speed 0.25-4.0 (default: 1.0)

        Returns:
            TTSResponse with audio URL and metadata

        Raises:
            ServiceException: If validation fails or TTS generation fails
        """
        try:
            # 1. Validate input
            logger.info(
                f"Generating audio for text (length={len(text)}, language={language}, voice={voice})"
            )
            self._validate_input(text, voice)

            # 2. Check cache
            cache_key = f"tts:{text[:50]}:{language}:{voice}"
            logger.info(f"Checking cache with key: {cache_key}")

            if self.cache_service and self.cache_service.redis_client:
                try:
                    cached_data = self.cache_service.get(cache_key)
                    if cached_data:
                        logger.info(f"Cache hit for {cache_key}")
                        # Ensure cached flag is set
                        if isinstance(cached_data, dict):
                            cached_data["cached"] = True
                            return TTSResponse(**cached_data)
                except Exception as e:
                    logger.warning(f"Cache lookup failed: {str(e)}")
                    # Continue with TTS generation

            # 3. Call OpenAI TTS API
            logger.info(
                f"No cache hit, calling OpenAI TTS API with voice={voice}, model={model}"
            )
            audio_content = await self._call_openai_tts(
                text=text,
                voice=voice,
                model=model,
                speed=speed,
            )

            # 4. Save audio file
            file_path = self._generate_file_path()
            logger.info(f"Saving audio to file: {file_path}")
            self._save_audio_file(file_path, audio_content)

            # 5. Get file size
            file_size = os.path.getsize(file_path)
            logger.info(f"Audio file saved, size: {file_size} bytes")

            # 6. Generate CDN URL
            audio_url = self._generate_cdn_url(file_path)

            # 7. Create response
            response_data = {
                "id": str(uuid4()),
                "audio_url": audio_url,
                "file_path": file_path,
                "file_size_bytes": file_size,
                "duration_seconds": self._estimate_duration(len(text), speed),
                "voice": voice,
                "model": model,
                "speed": speed,
                "created_at": datetime.now(),
                "cached": False,
            }

            response = TTSResponse(**response_data)

            # 8. Cache result
            self._cache_tts_result(cache_key, response)

            logger.info(f"TTS generation completed successfully")
            return response

        except ServiceException:
            raise
        except Exception as e:
            logger.error(f"TTS generation failed: {str(e)}", exc_info=True)
            raise ServiceException("TTS generation failed", detail=str(e))

    def _validate_input(self, text: str, voice: str) -> None:
        """
        Validate input parameters

        Args:
            text: Text to validate
            voice: Voice to validate

        Raises:
            ServiceException: If validation fails
        """
        # Check text is not empty
        if not text or not text.strip():
            raise ServiceException(
                "Text cannot be empty", detail="Text is required for TTS generation"
            )

        # Check text length
        if len(text) > self.MAX_TEXT_LENGTH:
            raise ServiceException(
                f"Text is too long (limit: {self.MAX_TEXT_LENGTH} characters)",
                detail=f"Text length: {len(text)} characters",
            )

        # Check voice is supported
        if voice not in self.SUPPORTED_VOICES:
            raise ServiceException(
                f"Voice '{voice}' is not supported",
                detail=f"Supported voices: {', '.join(self.SUPPORTED_VOICES)}",
            )

    async def _call_openai_tts(
        self,
        text: str,
        voice: str,
        model: str,
        speed: float,
    ) -> bytes:
        """
        Call OpenAI TTS API to generate audio

        Args:
            text: Text to convert
            voice: Voice to use
            model: TTS model
            speed: Speech speed

        Returns:
            Audio content as bytes

        Raises:
            ServiceException: If API call fails
        """
        try:
            # Initialize OpenAI client on demand to allow testing
            openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

            response = await openai_client.audio.speech.create(
                model=model,
                voice=voice,
                input=text,
                speed=speed,
            )

            return response.content

        except Exception as e:
            logger.error(f"OpenAI TTS API call failed: {str(e)}")
            raise ServiceException("OpenAI TTS API call failed", detail=str(e))

    def _generate_file_path(self) -> str:
        """
        Generate unique file path for audio file

        Returns:
            Full path to audio file (e.g., /tmp/audio/abc123.mp3)
        """
        # Generate unique filename using UUID
        filename = f"{uuid4()}.mp3"
        file_path = os.path.join(self.storage_path, filename)
        return file_path

    def _save_audio_file(self, file_path: str, audio_content: bytes) -> None:
        """
        Save audio content to file

        Args:
            file_path: Path to save the file
            audio_content: Audio data as bytes

        Raises:
            ServiceException: If file save fails
        """
        try:
            # Create directory if it doesn't exist
            os.makedirs(self.storage_path, exist_ok=True)

            # Write audio content to file
            with open(file_path, "wb") as f:
                f.write(audio_content)

        except (IOError, OSError) as e:
            logger.error(f"Failed to save audio file: {str(e)}")
            raise ServiceException("Audio file storage failed", detail=str(e))

    def _generate_cdn_url(self, file_path: str) -> str:
        """
        Generate CDN URL from file path

        Args:
            file_path: Local file path

        Returns:
            Public URL to access the audio file
        """
        # Extract filename from path
        filename = os.path.basename(file_path)

        # Use CDN URL if available, otherwise use local URL
        if settings.CDN_BASE_URL:
            base_url = settings.CDN_BASE_URL.rstrip("/")
        else:
            base_url = settings.AUDIO_BASE_URL.rstrip("/")

        return f"{base_url}/{filename}"

    def _estimate_duration(self, text_length: int, speed: float) -> int:
        """
        Estimate audio duration based on text length and speed

        Args:
            text_length: Length of text in characters
            speed: Speech speed multiplier

        Returns:
            Estimated duration in seconds
        """
        # Average speaking rate: ~150 words/minute = ~2.5 words/second
        # Assume average word length of 5 characters
        words = text_length / 5
        base_duration = words / 2.5  # seconds
        duration = int(base_duration / speed)
        return max(1, duration)  # At least 1 second

    def _cache_tts_result(self, cache_key: str, response: TTSResponse) -> None:
        """
        Cache TTS result in Redis with error handling

        Args:
            cache_key: Redis cache key
            response: TTS response to cache
        """
        if not self.cache_service or not self.cache_service.redis_client:
            logger.debug("Cache service not available, skipping cache write")
            return

        try:
            # Convert to dict for JSON serialization
            data = response.model_dump(mode="json")
            self.cache_service.set(cache_key, data, ttl=self.CACHE_TTL)
            logger.info(
                f"Cached TTS result with key: {cache_key}, TTL: {self.CACHE_TTL}s"
            )
        except Exception as e:
            # Cache failure should not break the flow
            logger.warning(f"Failed to cache TTS result: {str(e)}")

    def get_recommended_voice(self, language: str) -> str:
        """
        Get recommended voice for a given language

        Args:
            language: Language code (en, fr, de, es, it, zh)

        Returns:
            Recommended voice name
        """
        # Language-specific voice recommendations
        voice_recommendations = {
            "en": "alloy",
            "fr": "echo",
            "de": "fable",
            "es": "nova",
            "it": "shimmer",
            "zh": "onyx",
        }

        return voice_recommendations.get(language, "alloy")
