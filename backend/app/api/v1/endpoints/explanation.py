"""
Explanation API Endpoints
Handles artwork explanation generation HTTP requests (Step 2)
"""

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session
import logging

from app.schemas.explanation import (
    ExplanationRequest,
    ExplanationResponse,
    ExplanationError,
)
from app.services.explanation_service import ExplanationService
from app.services.ai_service import get_ai_service
from app.services.cache_service import CacheService
from app.core.database import get_db
from app.core.exceptions import (
    ServiceException,
    NotFoundException,
)
from app.utils.performance_monitor import monitor_performance

logger = logging.getLogger(__name__)

router = APIRouter()


def get_explanation_service_dependency(
    db: Session = Depends(get_db),
) -> ExplanationService:
    """
    Dependency injection for ExplanationService

    Args:
        db: Database session from dependency

    Returns:
        Configured ExplanationService instance
    """
    from app.services.tts_service import TTSService
    from app.core.config import settings
    import os

    ai_service = get_ai_service()
    cache_service = CacheService()

    # Use local storage path for development
    storage_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), "storage", "audio")
    tts_service = TTSService(
        cache_service=cache_service,
        storage_path=storage_path,
    )

    return ExplanationService(
        db=db,
        ai_service=ai_service,
        cache_service=cache_service,
        tts_service=tts_service,
    )


@router.post("/generate", response_model=ExplanationResponse)
@monitor_performance(threshold=5.0)
async def generate_explanation(
    request: ExplanationRequest,
    service: ExplanationService = Depends(get_explanation_service_dependency),
    response: Response = None,
) -> ExplanationResponse:
    """
    Generate artwork explanation content

    Args:
        request: Explanation generation request
        service: Explanation service (injected)
        response: HTTP response object (injected)

    Returns:
        ExplanationResponse with generated content

    Raises:
        HTTPException: Various HTTP error codes based on failure type
            - 400: Invalid request (unsupported language, etc.)
            - 404: Artwork not found
            - 500: Internal server error
            - 504: Request timeout

    Example:
        ```bash
        curl -X POST "http://localhost:8000/api/v1/explanation/generate" \\
             -H "Content-Type: application/json" \\
             -d '{
               "artwork_name": "Mona Lisa",
               "language": "en",
               "detail_level": "standard"
             }'
        ```
    """
    logger.info(
        f"Received explanation request for: {request.artwork_name} "
        f"(language: {request.language})"
    )

    try:
        # Generate explanation
        result = await service.generate_explanation(
            artwork_name=request.artwork_name,
            language=request.language,
            detail_level=request.detail_level,
            recognition_id=request.recognition_id,
            include_audio=request.include_audio,
        )

        # Add cache status header
        if response:
            cache_status = "HIT" if result.cached else "MISS"
            response.headers["X-Cache-Status"] = cache_status

        logger.info(f"Explanation generated successfully: {result.id}")
        return result

    except ServiceException as e:
        logger.error(f"Service error: {e.message}")
        # Check if it's an unsupported language error
        if "not supported" in e.message.lower():
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "UnsupportedLanguage",
                    "detail": e.detail or e.message,
                },
            )
        raise HTTPException(
            status_code=500,
            detail={"error": "ServiceError", "detail": e.detail or e.message},
        )

    except NotFoundException as e:
        logger.warning(f"Artwork not found: {request.artwork_name}")
        raise HTTPException(
            status_code=404,
            detail={"error": "NotFound", "detail": e.detail or e.message},
        )

    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500, detail={"error": "InternalServerError", "detail": str(e)}
        )


@router.get("/{explanation_id}", response_model=ExplanationResponse)
async def get_explanation(
    explanation_id: str,
    service: ExplanationService = Depends(get_explanation_service_dependency),
) -> ExplanationResponse:
    """
    Retrieve explanation by ID

    Args:
        explanation_id: UUID of the explanation
        service: Explanation service (injected)

    Returns:
        ExplanationResponse with content

    Raises:
        HTTPException: 404 if not found, 500 for other errors

    Example:
        ```bash
        curl -X GET "http://localhost:8000/api/v1/explanation/550e8400-e29b-41d4-a716-446655440000"
        ```
    """
    logger.info(f"Retrieving explanation: {explanation_id}")

    try:
        result = service.get_explanation_by_id(explanation_id)
        logger.info(f"Found explanation: {result.artwork_name}")
        return result

    except NotFoundException as e:
        logger.warning(f"Explanation not found: {explanation_id}")
        raise HTTPException(
            status_code=404,
            detail={"error": "NotFound", "detail": e.detail or e.message},
        )

    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500, detail={"error": "InternalServerError", "detail": str(e)}
        )


@router.get("/stats")
async def get_explanation_stats(
    service: ExplanationService = Depends(get_explanation_service_dependency),
) -> dict:
    """
    Get explanation generation statistics

    Args:
        service: Explanation service (injected)

    Returns:
        Dictionary with statistics

    Example:
        ```bash
        curl -X GET "http://localhost:8000/api/v1/explanation/stats"
        ```
    """
    logger.info("Retrieving explanation statistics")

    try:
        stats = service.get_statistics()
        return {"explanation": stats}

    except Exception as e:
        logger.error(f"Error retrieving stats: {str(e)}")
        raise HTTPException(
            status_code=500, detail={"error": "InternalServerError", "detail": str(e)}
        )
