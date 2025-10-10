"""
TTS (Text-to-Speech) Service
Handles audio generation from text using OpenAI TTS API
Supports multiple languages and voice options
"""

import logging
import hashlib
from typing import Dict, Optional, BinaryIO
from app.core.config import settings
from app.core.exceptions import AIServiceException
import asyncio
import io

logger = logging.getLogger(__name__)

# Lazy import OpenAI
_openai_client = None


def _get_openai_client():
    """Lazy load OpenAI client"""
    global _openai_client
    if _openai_client is None:
        try:
            from openai import AsyncOpenAI
            _openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
            logger.info("OpenAI client initialized for TTS")
        except ImportError:
            logger.warning("openai package not installed")
            _openai_client = None
        except Exception as e:
            logger.error(f"Failed to initialize OpenAI client: {e}")
            _openai_client = None
    return _openai_client


# Voice mapping for different languages
VOICE_MAPPING = {
    "en": {
        "default": "alloy",
        "options": ["alloy", "echo", "fable", "onyx", "nova", "shimmer"]
    },
    "zh": {
        "default": "nova",  # Nova works well for Chinese
        "options": ["nova", "shimmer", "alloy"]
    },
    "fr": {
        "default": "shimmer",
        "options": ["shimmer", "alloy", "nova"]
    },
    "de": {
        "default": "echo",
        "options": ["echo", "alloy", "onyx"]
    },
    "es": {
        "default": "nova",
        "options": ["nova", "shimmer", "alloy"]
    },
    "it": {
        "default": "alloy",
        "options": ["alloy", "shimmer", "nova"]
    }
}


class TTSService:
    """Service for text-to-speech audio generation"""

    def __init__(self):
        """Initialize TTS service"""
        self.api_key = settings.OPENAI_API_KEY
        self.model = getattr(settings, "OPENAI_TTS_MODEL", "tts-1")
        self.timeout = getattr(settings, "TTS_GENERATION_TIMEOUT", 30)
        logger.info(f"TTSService initialized with model: {self.model}")

    async def generate_audio(
        self,
        text: str,
        language: str = "en",
        voice: Optional[str] = None,
        speed: float = 1.0
    ) -> Dict[str, any]:
        """
        Generate audio from text using OpenAI TTS

        Args:
            text: Text content to convert to speech
            language: Target language (en, zh, fr, de, es, it)
            voice: Voice name (optional, will use default for language)
            speed: Speech speed (0.25 to 4.0, default 1.0)

        Returns:
            Dictionary containing:
                - audio_data: Audio file bytes
                - content_type: MIME type (audio/mpeg)
                - duration_estimate: Estimated duration in seconds
                - voice: Voice used
                - language: Language code
                - text_hash: Hash of input text for caching

        Raises:
            AIServiceException: If generation fails
        """
        logger.info(f"Generating TTS audio for text (length: {len(text)}) in {language}")

        # Validate language and get voice
        if language not in VOICE_MAPPING:
            logger.warning(f"Unsupported language {language}, falling back to English")
            language = "en"

        if voice is None:
            voice = VOICE_MAPPING[language]["default"]
        elif voice not in VOICE_MAPPING[language]["options"]:
            logger.warning(f"Voice {voice} not recommended for {language}, using default")
            voice = VOICE_MAPPING[language]["default"]

        # Validate speed
        if not 0.25 <= speed <= 4.0:
            logger.warning(f"Invalid speed {speed}, using 1.0")
            speed = 1.0

        # Generate text hash for caching
        text_hash = hashlib.sha256(
            f"{text}:{language}:{voice}:{speed}".encode()
        ).hexdigest()[:16]

        client = _get_openai_client()
        if client is None:
            raise AIServiceException("OpenAI client not available for TTS")

        try:
            logger.info(f"Calling OpenAI TTS API with voice={voice}, speed={speed}")

            # Generate audio
            response = await asyncio.wait_for(
                client.audio.speech.create(
                    model=self.model,
                    voice=voice,
                    input=text,
                    speed=speed,
                    response_format="mp3"
                ),
                timeout=self.timeout
            )

            # Read audio data
            audio_data = b""
            async for chunk in response.iter_bytes(chunk_size=8192):
                audio_data += chunk

            # Estimate duration (rough estimate: ~150 words per minute at speed 1.0)
            word_count = len(text.split())
            duration_estimate = (word_count / 150) * 60 / speed

            logger.info(
                f"Successfully generated TTS audio: "
                f"{len(audio_data)} bytes, ~{duration_estimate:.1f}s"
            )

            return {
                "audio_data": audio_data,
                "content_type": "audio/mpeg",
                "duration_estimate": duration_estimate,
                "voice": voice,
                "language": language,
                "text_hash": text_hash,
                "size_bytes": len(audio_data)
            }

        except asyncio.TimeoutError:
            logger.error(f"TTS generation timed out after {self.timeout}s")
            raise AIServiceException(
                f"TTS generation timed out after {self.timeout}s"
            )
        except Exception as e:
            logger.error(f"TTS generation failed: {str(e)}")
            raise AIServiceException(f"TTS generation failed: {str(e)}")

    async def generate_audio_stream(
        self,
        text: str,
        language: str = "en",
        voice: Optional[str] = None,
        speed: float = 1.0
    ):
        """
        Generate audio stream (for real-time streaming)

        Args:
            text: Text to convert
            language: Target language
            voice: Voice name
            speed: Speech speed

        Yields:
            Audio data chunks
        """
        logger.info(f"Generating TTS audio stream for text in {language}")

        # Validate parameters
        if language not in VOICE_MAPPING:
            language = "en"

        if voice is None:
            voice = VOICE_MAPPING[language]["default"]

        if not 0.25 <= speed <= 4.0:
            speed = 1.0

        client = _get_openai_client()
        if client is None:
            raise AIServiceException("OpenAI client not available for TTS")

        try:
            response = await client.audio.speech.create(
                model=self.model,
                voice=voice,
                input=text,
                speed=speed,
                response_format="mp3"
            )

            # Stream audio chunks
            async for chunk in response.iter_bytes(chunk_size=4096):
                yield chunk

            logger.info("TTS audio stream completed")

        except Exception as e:
            logger.error(f"TTS streaming failed: {str(e)}")
            raise AIServiceException(f"TTS streaming failed: {str(e)}")

    def get_supported_voices(self, language: str = "en") -> Dict[str, any]:
        """
        Get list of supported voices for a language

        Args:
            language: Language code

        Returns:
            Dictionary with default voice and available options
        """
        if language not in VOICE_MAPPING:
            language = "en"

        return {
            "language": language,
            "default_voice": VOICE_MAPPING[language]["default"],
            "available_voices": VOICE_MAPPING[language]["options"]
        }

    def generate_text_hash(
        self,
        text: str,
        language: str = "en",
        voice: Optional[str] = None,
        speed: float = 1.0
    ) -> str:
        """
        Generate cache key hash for text+params

        Args:
            text: Input text
            language: Language code
            voice: Voice name
            speed: Speed value

        Returns:
            Hash string for caching
        """
        if voice is None:
            voice = VOICE_MAPPING.get(language, VOICE_MAPPING["en"])["default"]

        return hashlib.sha256(
            f"{text}:{language}:{voice}:{speed}".encode()
        ).hexdigest()[:16]


# Singleton instance
_tts_service_instance = None


def get_tts_service() -> TTSService:
    """
    Get or create TTSService singleton instance

    Returns:
        TTSService instance
    """
    global _tts_service_instance
    if _tts_service_instance is None:
        _tts_service_instance = TTSService()
    return _tts_service_instance
