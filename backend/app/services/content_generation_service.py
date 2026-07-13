"""
Content Generation Service
Handles AI-powered artwork explanation generation in multiple languages
Uses OpenAI GPT-4 for creating rich, contextual content
"""

import asyncio
import json
import logging
from typing import Dict, Optional

from app.core.config import settings
from app.core.exceptions import AIServiceException

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
            logger.info("OpenAI client initialized for content generation")
        except ImportError:
            logger.warning("openai package not installed")
            _openai_client = None
        except Exception as e:
            logger.error(f"Failed to initialize OpenAI client: {e}")
            _openai_client = None
    return _openai_client


# Multi-language prompt templates
PROMPT_TEMPLATES = {
    "en": {
        "system": "You are an expert art historian and museum guide. Provide engaging, informative explanations about artworks.",
        "user": """Create a detailed explanation for this artwork:
- Artwork: {artwork_name}
- Artist: {artist}
- Period: {period}

Provide a comprehensive explanation including:
1. Historical context and significance
2. Artistic techniques and style
3. Cultural impact and legacy
4. Interesting facts or stories

Return ONLY valid JSON in this format:
{{
    "title": "{artwork_name}",
    "summary": "Brief 1-2 sentence overview",
    "historical_context": "3-4 sentences about historical background",
    "artistic_analysis": "3-4 sentences about artistic techniques and style",
    "cultural_significance": "2-3 sentences about cultural impact",
    "interesting_facts": ["fact 1", "fact 2", "fact 3"]
}}""",
    },
    "zh": {
        "system": "你是一位专业的艺术史学家和博物馆导览员。请用中文提供引人入胜、富有信息量的艺术品讲解。",
        "user": """为以下艺术品创建详细的讲解：
- 作品名称：{artwork_name}
- 艺术家：{artist}
- 时期：{period}

请提供全面的讲解，包括：
1. 历史背景和重要性
2. 艺术技法和风格
3. 文化影响和传承
4. 有趣的事实或故事

仅返回有效的JSON格式：
{{
    "title": "{artwork_name}",
    "summary": "简短的1-2句概述",
    "historical_context": "3-4句关于历史背景的描述",
    "artistic_analysis": "3-4句关于艺术技法和风格的分析",
    "cultural_significance": "2-3句关于文化影响的说明",
    "interesting_facts": ["趣事1", "趣事2", "趣事3"]
}}""",
    },
    "fr": {
        "system": "Vous êtes un historien d'art expert et un guide de musée. Fournissez des explications captivantes et informatives sur les œuvres d'art.",
        "user": """Créez une explication détaillée pour cette œuvre d'art :
- Œuvre : {artwork_name}
- Artiste : {artist}
- Période : {period}

Fournissez une explication complète incluant :
1. Contexte historique et signification
2. Techniques artistiques et style
3. Impact culturel et héritage
4. Faits intéressants ou histoires

Retournez UNIQUEMENT un JSON valide dans ce format :
{{
    "title": "{artwork_name}",
    "summary": "Aperçu bref de 1-2 phrases",
    "historical_context": "3-4 phrases sur le contexte historique",
    "artistic_analysis": "3-4 phrases sur les techniques et le style artistiques",
    "cultural_significance": "2-3 phrases sur l'impact culturel",
    "interesting_facts": ["fait 1", "fait 2", "fait 3"]
}}""",
    },
    "de": {
        "system": "Sie sind ein Experte für Kunstgeschichte und Museumsführer. Bieten Sie fesselnde und informative Erklärungen zu Kunstwerken.",
        "user": """Erstellen Sie eine detaillierte Erklärung für dieses Kunstwerk:
- Kunstwerk: {artwork_name}
- Künstler: {artist}
- Periode: {period}

Bieten Sie eine umfassende Erklärung einschließlich:
1. Historischer Kontext und Bedeutung
2. Künstlerische Techniken und Stil
3. Kulturelle Auswirkungen und Vermächtnis
4. Interessante Fakten oder Geschichten

Geben Sie NUR gültiges JSON in diesem Format zurück:
{{
    "title": "{artwork_name}",
    "summary": "Kurzer Überblick in 1-2 Sätzen",
    "historical_context": "3-4 Sätze über den historischen Hintergrund",
    "artistic_analysis": "3-4 Sätze über künstlerische Techniken und Stil",
    "cultural_significance": "2-3 Sätze über kulturelle Bedeutung",
    "interesting_facts": ["Fakt 1", "Fakt 2", "Fakt 3"]
}}""",
    },
    "es": {
        "system": "Eres un experto historiador de arte y guía de museo. Proporciona explicaciones atractivas e informativas sobre obras de arte.",
        "user": """Crea una explicación detallada para esta obra de arte:
- Obra: {artwork_name}
- Artista: {artist}
- Período: {period}

Proporciona una explicación completa que incluya:
1. Contexto histórico y significado
2. Técnicas artísticas y estilo
3. Impacto cultural y legado
4. Hechos interesantes o historias

Devuelve SOLO JSON válido en este formato:
{{
    "title": "{artwork_name}",
    "summary": "Resumen breve de 1-2 oraciones",
    "historical_context": "3-4 oraciones sobre el contexto histórico",
    "artistic_analysis": "3-4 oraciones sobre técnicas y estilo artísticos",
    "cultural_significance": "2-3 oraciones sobre el impacto cultural",
    "interesting_facts": ["hecho 1", "hecho 2", "hecho 3"]
}}""",
    },
    "it": {
        "system": "Sei un esperto storico dell'arte e guida museale. Fornisci spiegazioni coinvolgenti e informative sulle opere d'arte.",
        "user": """Crea una spiegazione dettagliata per quest'opera d'arte:
- Opera: {artwork_name}
- Artista: {artist}
- Periodo: {period}

Fornisci una spiegazione completa che includa:
1. Contesto storico e significato
2. Tecniche artistiche e stile
3. Impatto culturale ed eredità
4. Fatti interessanti o storie

Restituisci SOLO JSON valido in questo formato:
{{
    "title": "{artwork_name}",
    "summary": "Panoramica breve di 1-2 frasi",
    "historical_context": "3-4 frasi sul contesto storico",
    "artistic_analysis": "3-4 frasi su tecniche e stile artistici",
    "cultural_significance": "2-3 frasi sull'impatto culturale",
    "interesting_facts": ["fatto 1", "fatto 2", "fatto 3"]
}}""",
    },
}


class ContentGenerationService:
    """Service for generating AI-powered artwork explanations"""

    def __init__(self):
        """Initialize content generation service"""
        self.api_key = settings.OPENAI_API_KEY
        # 默认 mini(排雷:此端点前端未调用+无接地,曾默认 gpt-4≈mini 的 50 倍成本)
        self.model = getattr(settings, "OPENAI_CONTENT_MODEL", "gpt-4o-mini")
        self.timeout = getattr(settings, "CONTENT_GENERATION_TIMEOUT", 10)
        logger.info(f"ContentGenerationService initialized with model: {self.model}")

    async def generate_explanation(
        self,
        artwork_name: str,
        artist: str,
        period: str,
        language: str = "en",
        description: Optional[str] = None,
    ) -> Dict[str, any]:
        """
        Generate detailed explanation for an artwork

        Args:
            artwork_name: Name of the artwork
            artist: Artist name
            period: Historical period
            language: Target language (en, zh, fr, de, es, it)
            description: Optional base description from recognition

        Returns:
            Dictionary containing:
                - title: Artwork title
                - summary: Brief overview
                - historical_context: Historical background
                - artistic_analysis: Artistic techniques and style
                - cultural_significance: Cultural impact
                - interesting_facts: List of interesting facts
                - language: Language code
                - generated_at: Timestamp

        Raises:
            AIServiceException: If generation fails
        """
        logger.info(f"Generating explanation for '{artwork_name}' in {language}")

        # Validate language
        if language not in PROMPT_TEMPLATES:
            logger.warning(f"Unsupported language {language}, falling back to English")
            language = "en"

        client = _get_openai_client()
        if client is None:
            # Return fallback content
            return self._generate_fallback(artwork_name, artist, period, language)

        try:
            template = PROMPT_TEMPLATES[language]
            system_prompt = template["system"]
            user_prompt = template["user"].format(
                artwork_name=artwork_name, artist=artist, period=period
            )

            # Add base description if available
            if description:
                user_prompt = f"{user_prompt}\n\nBase description: {description}"

            logger.info(f"Calling OpenAI API for content generation in {language}")

            response = await asyncio.wait_for(
                client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    max_tokens=1500,
                    temperature=0.7,
                ),
                timeout=self.timeout,
            )

            # Parse response
            content = response.choices[0].message.content

            # Extract JSON from markdown if present
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()

            result = json.loads(content)

            # Add metadata
            result["language"] = language
            result["generated_at"] = asyncio.get_event_loop().time()

            logger.info(f"Successfully generated explanation for '{artwork_name}'")
            return result

        except asyncio.TimeoutError:
            logger.error(f"Content generation timed out after {self.timeout}s")
            return self._generate_fallback(artwork_name, artist, period, language)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse response as JSON: {e}")
            return self._generate_fallback(artwork_name, artist, period, language)
        except Exception as e:
            logger.error(f"Content generation failed: {str(e)}")
            return self._generate_fallback(artwork_name, artist, period, language)

    def _generate_fallback(
        self, artwork_name: str, artist: str, period: str, language: str
    ) -> Dict[str, any]:
        """Generate fallback content when AI is unavailable"""
        fallback_texts = {
            "en": {
                "summary": f"A notable artwork from the {period} period by {artist}.",
                "historical_context": f"This artwork was created during the {period}, a significant era in art history.",
                "artistic_analysis": "This piece showcases the characteristic style and techniques of its time.",
                "cultural_significance": "This artwork has contributed to the cultural heritage and artistic tradition.",
                "interesting_facts": [
                    f"Created by {artist}",
                    f"Belongs to the {period} period",
                    "Recognized as a significant work in art history",
                ],
            },
            "zh": {
                "summary": f"{artist}创作于{period}时期的著名艺术品。",
                "historical_context": f"这件作品创作于{period}，这是艺术史上的重要时期。",
                "artistic_analysis": "这件作品展现了其时代特有的风格和技法。",
                "cultural_significance": "这件作品为文化遗产和艺术传统做出了贡献。",
                "interesting_facts": [
                    f"由{artist}创作",
                    f"属于{period}时期",
                    "被认为是艺术史上的重要作品",
                ],
            },
        }

        # Default to English if language not in fallback
        texts = fallback_texts.get(language, fallback_texts["en"])

        return {
            "title": artwork_name,
            "summary": texts["summary"],
            "historical_context": texts["historical_context"],
            "artistic_analysis": texts["artistic_analysis"],
            "cultural_significance": texts["cultural_significance"],
            "interesting_facts": texts["interesting_facts"],
            "language": language,
            "generated_at": asyncio.get_event_loop().time(),
            "fallback": True,
        }


# Singleton instance
_content_service_instance = None


def get_content_generation_service() -> ContentGenerationService:
    """
    Get or create ContentGenerationService singleton instance

    Returns:
        ContentGenerationService instance
    """
    global _content_service_instance
    if _content_service_instance is None:
        _content_service_instance = ContentGenerationService()
    return _content_service_instance
