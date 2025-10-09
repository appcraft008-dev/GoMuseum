"""
AI Service
Handles communication with OpenAI GPT-4 Vision API for artwork recognition
Multi-tier fallback strategy: GPT-4V → Claude → Manual
"""

import logging
import json
from typing import Dict, Optional
from app.core.config import settings
from app.core.exceptions import AIServiceException, TimeoutException
import asyncio

logger = logging.getLogger(__name__)

# Lazy import to avoid dependency issues if not configured
_openai_client = None
_claude_client = None


def _get_openai_client():
    """Lazy load OpenAI client"""
    global _openai_client
    if _openai_client is None:
        try:
            from openai import AsyncOpenAI
            _openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
            logger.info("OpenAI client initialized")
        except ImportError:
            logger.warning("openai package not installed, falling back to mock")
            _openai_client = None
        except Exception as e:
            logger.error(f"Failed to initialize OpenAI client: {e}")
            _openai_client = None
    return _openai_client


def _get_claude_client():
    """Lazy load Claude client"""
    global _claude_client
    if _claude_client is None:
        try:
            import anthropic
            if settings.ANTHROPIC_API_KEY:
                _claude_client = anthropic.AsyncAnthropic(
                    api_key=settings.ANTHROPIC_API_KEY
                )
                logger.info("Claude client initialized")
        except ImportError:
            logger.warning("anthropic package not installed")
            _claude_client = None
        except Exception as e:
            logger.error(f"Failed to initialize Claude client: {e}")
            _claude_client = None
    return _claude_client


class AIService:
    """Service for AI-powered artwork recognition with multi-tier fallback"""

    def __init__(self):
        """Initialize AI service with OpenAI configuration"""
        self.api_key = settings.OPENAI_API_KEY
        self.model = settings.OPENAI_MODEL
        self.timeout = settings.OPENAI_TIMEOUT
        self.strategy_timeout = getattr(settings, "AI_STRATEGY_TIMEOUT", 3)
        self.total_timeout = getattr(settings, "AI_TOTAL_TIMEOUT", 5)
        logger.info(f"AIService initialized with model: {self.model}")

    async def recognize(self, base64_image: str) -> Dict[str, any]:
        """
        Recognize artwork from image using AI with fallback strategies

        Fallback chain:
        1. OpenAI GPT-4V (configurable timeout)
        2. Anthropic Claude Vision (configurable timeout)
        3. Manual fallback (always succeeds)

        Args:
            base64_image: Base64 encoded image string

        Returns:
            Dictionary containing:
                - artwork_name: str
                - artist: str
                - period: str
                - description: str
                - confidence: float (0.0 to 1.0)
                - source: str (openai|claude|manual)

        Raises:
            AIServiceException: If all strategies fail
        """
        logger.info("AIService.recognize() called - trying multi-tier strategies")
        logger.info(f"Using strategy timeout: {self.strategy_timeout}s")

        strategies = [
            ("openai", self._recognize_with_openai, self.strategy_timeout),
            ("claude", self._recognize_with_claude, self.strategy_timeout),
        ]

        for strategy_name, strategy_func, timeout in strategies:
            try:
                logger.info(f"Trying recognition strategy: {strategy_name} with {timeout}s timeout")
                result = await asyncio.wait_for(
                    strategy_func(base64_image), timeout=timeout
                )
                result["source"] = strategy_name
                logger.info(f"Recognition successful with {strategy_name}")
                return result
            except asyncio.TimeoutError:
                logger.warning(
                    f"{strategy_name} strategy timed out after {timeout}s - "
                    f"API call may still be in progress but was interrupted"
                )
                continue
            except Exception as e:
                logger.error(
                    f"{strategy_name} strategy failed: {str(e)}",
                    exc_info=True  # 这会打印完整的堆栈跟踪
                )
                continue

        # All strategies failed, use manual fallback
        logger.warning("All AI strategies failed, using manual fallback")
        return await self._fallback_manual(base64_image)

    async def _recognize_with_openai(self, base64_image: str) -> Dict[str, any]:
        """
        Recognize artwork using OpenAI GPT-4 Vision

        Args:
            base64_image: Base64 encoded image

        Returns:
            Recognition result dictionary
        """
        client = _get_openai_client()
        if client is None:
            raise AIServiceException("OpenAI client not available")

        prompt = """
You are an expert art historian. Analyze this artwork image and provide:
1. Artwork name/title
2. Artist name
3. Historical period/era
4. Detailed description (2-3 sentences)
5. Confidence score (0.0-1.0)

Return ONLY valid JSON in this exact format:
{
    "artwork_name": "...",
    "artist": "...",
    "period": "...",
    "description": "...",
    "confidence": 0.95
}
"""

        try:
            logger.info(f"Calling OpenAI API with model: {self.model}")
            logger.info(f"Image data length: {len(base64_image)} chars")

            response = await client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{base64_image}",
                                    "detail": "high",
                                },
                            },
                        ],
                    }
                ],
                max_tokens=500,
                temperature=0.2,
            )

            logger.info("OpenAI API call completed successfully")

            # Parse JSON response
            content = response.choices[0].message.content
            logger.info(f"OpenAI response content length: {len(content)} chars")
            # Extract JSON from markdown code blocks if present
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()

            result = json.loads(content)

            # Validate required keys
            required_keys = [
                "artwork_name",
                "artist",
                "period",
                "description",
                "confidence",
            ]
            if not all(key in result for key in required_keys):
                raise ValueError("Missing required keys in OpenAI response")

            logger.info(f"OpenAI recognition: {result['artwork_name']}")
            return result

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse OpenAI response as JSON: {e}")
            raise AIServiceException(f"Invalid JSON response from OpenAI: {e}")
        except Exception as e:
            logger.error(f"OpenAI recognition failed: {str(e)}")
            raise AIServiceException(f"OpenAI API error: {str(e)}")

    async def _recognize_with_claude(self, base64_image: str) -> Dict[str, any]:
        """
        Recognize artwork using Anthropic Claude Vision (fallback)

        Args:
            base64_image: Base64 encoded image

        Returns:
            Recognition result dictionary
        """
        client = _get_claude_client()
        if client is None:
            raise AIServiceException("Claude client not available")

        prompt = """
Analyze this artwork and provide JSON output with:
- artwork_name: the title
- artist: creator's name
- period: historical era
- description: 2-3 sentence description
- confidence: score 0.0-1.0

Return only the JSON object, no other text.
"""

        try:
            message = await client.messages.create(
                model=getattr(settings, "ANTHROPIC_MODEL", "claude-3-5-sonnet-20241022"),
                max_tokens=500,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": "image/jpeg",
                                    "data": base64_image,
                                },
                            },
                            {"type": "text", "text": prompt},
                        ],
                    }
                ],
            )

            # Parse Claude response
            content = message.content[0].text
            # Extract JSON from markdown if present
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()

            result = json.loads(content)
            logger.info(f"Claude recognition: {result['artwork_name']}")
            return result

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse Claude response as JSON: {e}")
            raise AIServiceException(f"Invalid JSON response from Claude: {e}")
        except Exception as e:
            logger.error(f"Claude recognition failed: {str(e)}")
            raise AIServiceException(f"Claude API error: {str(e)}")

    async def _fallback_manual(self, base64_image: str) -> Dict[str, any]:
        """
        Manual fallback when all AI strategies fail

        Returns:
            Generic "unknown" result
        """
        return {
            "artwork_name": "Unknown Artwork",
            "artist": "Unknown Artist",
            "period": "Unknown Period",
            "description": (
                "Unable to recognize this artwork automatically. "
                "Please try manual search or contact support for assistance."
            ),
            "confidence": 0.0,
            "source": "manual",
        }

    async def recognize_with_timeout(
        self, base64_image: str, timeout: int = None
    ) -> Dict[str, any]:
        """
        Recognize artwork with timeout protection

        Args:
            base64_image: Base64 encoded image string
            timeout: Timeout in seconds (defaults to settings.OPENAI_TIMEOUT)

        Returns:
            Recognition result dictionary

        Raises:
            TimeoutException: If request exceeds timeout
            AIServiceException: If AI service fails
        """
        if timeout is None:
            timeout = self.timeout

        try:
            result = await asyncio.wait_for(
                self.recognize(base64_image), timeout=timeout
            )
            return result
        except asyncio.TimeoutError:
            logger.error(f"AI recognition timed out after {timeout}s")
            raise TimeoutException(
                f"AI recognition timed out after {timeout}s",
                detail="The artwork recognition request took too long to complete",
            )
        except Exception as e:
            logger.error(f"AI recognition failed: {str(e)}")
            raise AIServiceException("AI recognition failed", detail=str(e))

    def validate_api_key(self) -> bool:
        """
        Validate that OpenAI API key is configured

        Returns:
            True if API key is present
        """
        if not self.api_key:
            logger.warning("OpenAI API key not configured")
            return False
        return True

    async def generate_content(
        self, prompt: str, language: str = "en", detail_level: str = "standard"
    ) -> Dict[str, any]:
        """
        Generate text content using AI (for explanations, descriptions, etc.)

        Args:
            prompt: The prompt for content generation
            language: Target language code
            detail_level: Detail level (brief, standard, detailed)

        Returns:
            Dictionary containing:
                - content: str (generated text)
                - word_count: int
                - source: str (openai|claude|manual)

        Raises:
            AIServiceException: If all strategies fail
        """
        logger.info("AIService.generate_content() called")
        logger.info(f"Language: {language}, Detail level: {detail_level}")

        # Try OpenAI first, then Claude, then fallback
        strategies = [
            ("openai", self._generate_content_with_openai, self.strategy_timeout),
            ("claude", self._generate_content_with_claude, self.strategy_timeout),
        ]

        for strategy_name, strategy_func, timeout in strategies:
            try:
                logger.info(f"Trying content generation with {strategy_name}")
                result = await asyncio.wait_for(
                    strategy_func(prompt, language, detail_level), timeout=timeout
                )
                result["source"] = strategy_name
                logger.info(f"Content generation successful with {strategy_name}")
                return result
            except asyncio.TimeoutError:
                logger.warning(f"{strategy_name} content generation timed out")
                continue
            except Exception as e:
                logger.error(f"{strategy_name} content generation failed: {str(e)}", exc_info=True)
                continue

        # All strategies failed, use fallback
        logger.warning("All content generation strategies failed, using fallback")
        return self._fallback_content_generation(prompt, language)

    async def _generate_content_with_openai(
        self, prompt: str, language: str, detail_level: str
    ) -> Dict[str, any]:
        """
        Generate content using OpenAI GPT-4

        Args:
            prompt: Content generation prompt
            language: Target language
            detail_level: Detail level

        Returns:
            Dictionary with content and metadata
        """
        client = _get_openai_client()
        if client is None:
            raise AIServiceException("OpenAI client not available")

        try:
            logger.info(f"Calling OpenAI for content generation in {language}")

            # Get token limit based on detail level
            max_tokens = getattr(settings, "DETAIL_LEVEL_TOKENS", {}).get(
                detail_level, 500
            )

            response = await client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert art historian providing museum-quality explanations.",
                    },
                    {"role": "user", "content": prompt},
                ],
                max_tokens=max_tokens,
                temperature=0.7,
            )

            content = response.choices[0].message.content.strip()
            word_count = len(content.split())

            logger.info(f"OpenAI content generation successful, {word_count} words")

            return {"content": content, "word_count": word_count}

        except Exception as e:
            logger.error(f"OpenAI content generation failed: {str(e)}")
            raise AIServiceException(f"OpenAI content generation error: {str(e)}")

    async def _generate_content_with_claude(
        self, prompt: str, language: str, detail_level: str
    ) -> Dict[str, any]:
        """
        Generate content using Anthropic Claude

        Args:
            prompt: Content generation prompt
            language: Target language
            detail_level: Detail level

        Returns:
            Dictionary with content and metadata
        """
        client = _get_claude_client()
        if client is None:
            raise AIServiceException("Claude client not available")

        try:
            logger.info(f"Calling Claude for content generation in {language}")

            # Get token limit based on detail level
            max_tokens = getattr(settings, "DETAIL_LEVEL_TOKENS", {}).get(
                detail_level, 500
            )

            message = await client.messages.create(
                model=getattr(settings, "ANTHROPIC_MODEL", "claude-3-5-sonnet-20241022"),
                max_tokens=max_tokens,
                messages=[
                    {
                        "role": "user",
                        "content": f"You are an expert art historian. {prompt}",
                    }
                ],
            )

            content = message.content[0].text.strip()
            word_count = len(content.split())

            logger.info(f"Claude content generation successful, {word_count} words")

            return {"content": content, "word_count": word_count}

        except Exception as e:
            logger.error(f"Claude content generation failed: {str(e)}")
            raise AIServiceException(f"Claude content generation error: {str(e)}")

    def _fallback_content_generation(
        self, prompt: str, language: str
    ) -> Dict[str, any]:
        """
        Fallback content when AI services fail

        Args:
            prompt: Original prompt
            language: Target language

        Returns:
            Generic fallback content
        """
        fallback_messages = {
            "en": "We apologize, but we are currently unable to generate a detailed explanation for this artwork. Please try again later or contact museum staff for assistance.",
            "fr": "Nous nous excusons, mais nous ne pouvons actuellement pas générer une explication détaillée pour cette œuvre. Veuillez réessayer plus tard ou contacter le personnel du musée.",
            "de": "Wir entschuldigen uns, aber wir können derzeit keine detaillierte Erklärung für dieses Kunstwerk erstellen. Bitte versuchen Sie es später erneut oder wenden Sie sich an das Museumspersonal.",
            "es": "Nos disculpamos, pero actualmente no podemos generar una explicación detallada para esta obra de arte. Por favor, inténtelo de nuevo más tarde o contacte al personal del museo.",
            "it": "Ci scusiamo, ma al momento non siamo in grado di generare una spiegazione dettagliata per quest'opera d'arte. Si prega di riprovare più tardi o contattare il personale del museo.",
            "zh": "抱歉，我们目前无法为这件艺术品生成详细说明。请稍后重试或联系博物馆工作人员寻求帮助。",
        }

        content = fallback_messages.get(
            language,
            "Unable to generate explanation. Please try again later.",
        )

        return {"content": content, "word_count": len(content.split()), "source": "fallback"}

    async def health_check(self) -> Dict[str, any]:
        """
        Check if AI service is available

        Returns:
            Dictionary with health status
        """
        return {
            "service": "AIService",
            "status": "ok",
            "model": self.model,
            "api_key_configured": bool(self.api_key),
            "mode": "mock",  # Will be "production" when real implementation is done
        }


# Singleton instance for dependency injection
_ai_service_instance = None


def get_ai_service() -> AIService:
    """
    Get or create AIService singleton instance

    Returns:
        AIService instance
    """
    global _ai_service_instance
    if _ai_service_instance is None:
        _ai_service_instance = AIService()
    return _ai_service_instance
