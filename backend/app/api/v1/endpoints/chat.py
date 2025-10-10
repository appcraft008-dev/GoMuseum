"""
Chat API Endpoints
Handles voice Q&A and conversational interactions about artworks
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import Optional
import logging

from app.services.ai_service import get_ai_service
from app.core.exceptions import AIServiceException

logger = logging.getLogger(__name__)

router = APIRouter()


# Request/Response Models
class ChatRequest(BaseModel):
    """Request model for chat/Q&A"""
    question: str = Field(..., description="User's question about the artwork")
    artwork_id: Optional[str] = Field(None, description="ID of the artwork being discussed")
    context: Optional[str] = Field(None, description="Additional context about the artwork")
    language: str = Field(default="en", description="Response language")
    conversation_history: Optional[list[dict]] = Field(None, description="Previous conversation messages")


class ChatResponse(BaseModel):
    """Response model for chat"""
    answer: str = Field(..., description="AI-generated answer")
    confidence: float = Field(..., description="Confidence score 0.0-1.0")
    language: str = Field(..., description="Response language")
    sources: Optional[list[str]] = Field(None, description="Information sources referenced")


@router.post("/ask", response_model=ChatResponse)
async def ask_question(
    request: ChatRequest,
    ai_service = Depends(get_ai_service)
) -> ChatResponse:
    """
    Ask a question about an artwork or art in general

    This endpoint powers the voice Q&A feature, allowing users to ask
    questions about artworks and receive conversational AI responses.

    Args:
        request: Chat request with question and context
        ai_service: AI service (injected)

    Returns:
        AI-generated answer with confidence score

    Example:
        ```bash
        curl -X POST "http://localhost:8000/api/v1/chat/ask" \\
             -H "Content-Type: application/json" \\
             -d '{
                   "question": "What techniques did Van Gogh use?",
                   "context": "The Starry Night painting",
                   "language": "en"
                 }'
        ```
    """
    logger.info(f"Processing question: '{request.question[:50]}...' in {request.language}")

    try:
        # Build conversation prompt
        system_prompt = _build_system_prompt(request.language)
        user_message = _build_user_message(request)

        # Get OpenAI client from AI service
        from openai import AsyncOpenAI
        from app.core.config import settings

        client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

        # Build messages
        messages = [{"role": "system", "content": system_prompt}]

        # Add conversation history if provided
        if request.conversation_history:
            messages.extend(request.conversation_history)

        messages.append({"role": "user", "content": user_message})

        # Call OpenAI for conversational response
        response = await client.chat.completions.create(
            model=getattr(settings, "OPENAI_CHAT_MODEL", "gpt-4"),
            messages=messages,
            max_tokens=500,
            temperature=0.7,
        )

        answer = response.choices[0].message.content

        # Estimate confidence based on response characteristics
        confidence = _estimate_confidence(answer)

        logger.info(f"Generated answer (length: {len(answer)})")

        return ChatResponse(
            answer=answer,
            confidence=confidence,
            language=request.language,
            sources=None  # Could be enhanced with RAG in future
        )

    except Exception as e:
        logger.error(f"Chat request failed: {str(e)}", exc_info=True)

        # Return fallback response
        return ChatResponse(
            answer=_get_fallback_answer(request.language),
            confidence=0.3,
            language=request.language,
            sources=None
        )


def _build_system_prompt(language: str) -> str:
    """Build system prompt based on language"""
    prompts = {
        "en": """You are a knowledgeable and friendly museum guide assistant.
Answer questions about artworks, artists, art history, and techniques in a conversational,
engaging manner. Keep responses concise (2-4 sentences) but informative.
If you don't know something, admit it honestly rather than guessing.""",

        "zh": """你是一位知识渊博且友好的博物馆导览助手。
以对话式、引人入胜的方式回答关于艺术品、艺术家、艺术史和技法的问题。
保持回答简洁（2-4句话）但信息丰富。如果不确定某事，请诚实承认，而不是猜测。""",

        "fr": """Vous êtes un assistant de guide de musée compétent et amical.
Répondez aux questions sur les œuvres d'art, les artistes, l'histoire de l'art et
les techniques de manière conversationnelle et engageante.
Gardez les réponses concises (2-4 phrases) mais informatives.""",

        "de": """Sie sind ein sachkundiger und freundlicher Museumsführer-Assistent.
Beantworten Sie Fragen zu Kunstwerken, Künstlern, Kunstgeschichte und Techniken
auf gesprächige und ansprechende Weise. Halten Sie Antworten prägnant (2-4 Sätze),
aber informativ.""",

        "es": """Eres un asistente de guía de museo conocedor y amigable.
Responde preguntas sobre obras de arte, artistas, historia del arte y técnicas
de manera conversacional y atractiva. Mantén las respuestas concisas (2-4 oraciones)
pero informativas.""",

        "it": """Sei un assistente guida museale esperto e amichevole.
Rispondi alle domande su opere d'arte, artisti, storia dell'arte e tecniche
in modo conversazionale e coinvolgente. Mantieni le risposte concise (2-4 frasi)
ma informative."""
    }

    return prompts.get(language, prompts["en"])


def _build_user_message(request: ChatRequest) -> str:
    """Build user message with context"""
    message = request.question

    if request.context:
        message = f"Context: {request.context}\n\nQuestion: {message}"

    if request.artwork_id:
        message = f"[Artwork ID: {request.artwork_id}]\n{message}"

    return message


def _estimate_confidence(answer: str) -> float:
    """
    Estimate confidence score based on answer characteristics

    Simple heuristic: longer, more detailed answers = higher confidence
    """
    length = len(answer)

    if length < 50:
        return 0.5
    elif length < 150:
        return 0.7
    elif length < 300:
        return 0.85
    else:
        return 0.9


def _get_fallback_answer(language: str) -> str:
    """Get fallback answer when AI fails"""
    fallbacks = {
        "en": "I'm sorry, I'm having trouble answering that question right now. Please try rephrasing or ask a different question.",
        "zh": "抱歉，我现在无法回答这个问题。请尝试换个方式提问或询问其他问题。",
        "fr": "Désolé, j'ai du mal à répondre à cette question pour le moment. Veuillez reformuler ou poser une autre question.",
        "de": "Entschuldigung, ich habe derzeit Schwierigkeiten, diese Frage zu beantworten. Bitte umformulieren oder eine andere Frage stellen.",
        "es": "Lo siento, tengo problemas para responder esa pregunta ahora. Por favor, reformule o haga otra pregunta.",
        "it": "Mi dispiace, sto avendo difficoltà a rispondere a quella domanda ora. Per favore riformula o fai un'altra domanda."
    }

    return fallbacks.get(language, fallbacks["en"])


@router.get("/health")
async def health_check():
    """Check if chat service is available"""
    return {
        "service": "ChatAPI",
        "status": "ok",
        "capabilities": ["text_qa", "voice_qa", "multi_language"]
    }
