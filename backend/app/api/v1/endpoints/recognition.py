"""
Recognition API Endpoints
Handles artwork recognition HTTP requests
"""

import logging

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Response,
    UploadFile,
)
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.exceptions import (
    NotFoundException,
    ServiceException,
    TimeoutException,
    ValidationException,
)
from app.schemas.recognition import RecognitionResponse
from app.services.ai_service import get_ai_service
from app.services.cache_service import CacheService
from app.services.image_service import ImageService
from app.services.recognition_service import RecognitionService
from app.utils.performance_monitor import get_performance_monitor, monitor_performance

logger = logging.getLogger(__name__)

router = APIRouter()


def get_recognition_service_dependency(
    db: Session = Depends(get_db),
) -> RecognitionService:
    """
    Dependency injection for RecognitionService

    Args:
        db: Database session from dependency

    Returns:
        Configured RecognitionService instance
    """
    ai_service = get_ai_service()
    cache_service = CacheService()
    image_service = ImageService()

    return RecognitionService(
        db=db,
        ai_service=ai_service,
        cache_service=cache_service,
        image_service=image_service,
    )


@router.post("/recognize", response_model=RecognitionResponse)
@monitor_performance(threshold=5.0)
async def recognize_artwork(
    image: UploadFile = File(..., description="Image file (JPEG/PNG, <10MB)"),
    service: RecognitionService = Depends(get_recognition_service_dependency),
    response: Response = None,
) -> RecognitionResponse:
    """
    Recognize artwork from uploaded image

    Args:
        image: Uploaded image file (JPEG or PNG, max 10MB)
        service: Recognition service (injected)
        response: HTTP response object (injected)

    Returns:
        RecognitionResponse with artwork details and confidence score

    Raises:
        HTTPException: Various HTTP error codes based on failure type
            - 400: Invalid image format or size
            - 500: Internal server error
            - 504: Request timeout

    Example:
        ```bash
        curl -X POST "http://localhost:8000/api/v1/recognition/recognize" \\
             -F "image=@artwork.jpg"
        ```
    """
    logger.info(f"Received recognition request for file: {image.filename}")

    try:
        # 1. Validate content type
        if image.content_type not in ["image/jpeg", "image/png"]:
            raise ValidationException(
                "Invalid image format",
                detail=(
                    f"Content-Type must be image/jpeg or image/png, "
                    f"got {image.content_type}"
                ),
            )

        # 2. Read image data
        image_data = await image.read()
        logger.info(f"Read {len(image_data)} bytes from uploaded file")

        # 3. Call recognition service
        result = await service.recognize_artwork(image_data)

        # 4. Add cache status header
        if response:
            # Check if this was a cache hit by looking at timing
            # (In production, RecognitionService should return cache status)
            response.headers["X-Cache-Status"] = "MISS"  # Default to MISS

        logger.info(f"Recognition successful: {result.artwork_name}")
        return result

    except ValidationException as e:
        logger.warning(f"Validation error: {e.message}")
        raise HTTPException(
            status_code=400,
            detail={"error": "ValidationError", "detail": e.detail or e.message},
        )

    except TimeoutException as e:
        logger.error(f"Timeout error: {e.message}")
        raise HTTPException(
            status_code=504,
            detail={"error": "TimeoutError", "detail": e.detail or e.message},
        )

    except ServiceException as e:
        logger.error(f"Service error: {e.message}")
        raise HTTPException(
            status_code=500,
            detail={"error": "ServiceError", "detail": e.detail or e.message},
        )

    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500, detail={"error": "InternalServerError", "detail": str(e)}
        )


@router.get("/recognize/{recognition_id}", response_model=RecognitionResponse)
async def get_recognition_result(
    recognition_id: str,
    service: RecognitionService = Depends(get_recognition_service_dependency),
) -> RecognitionResponse:
    """
    Retrieve recognition result by ID

    Args:
        recognition_id: UUID of the recognition result
        service: Recognition service (injected)

    Returns:
        RecognitionResponse with artwork details

    Raises:
        HTTPException: 404 if not found, 500 for other errors

    Example:
        ```bash
        curl -X GET "http://localhost:8000/api/v1/recognition/recognize/
        550e8400-e29b-41d4-a716-446655440000"
        ```
    """
    logger.info(f"Retrieving recognition result: {recognition_id}")

    try:
        result = service.get_recognition_by_id(recognition_id)
        logger.info(f"Found recognition result: {result.artwork_name}")
        return result

    except NotFoundException as e:
        logger.warning(f"Recognition result not found: {recognition_id}")
        raise HTTPException(
            status_code=404,
            detail={"error": "NotFound", "detail": e.detail or e.message},
        )

    except ServiceException as e:
        logger.error(f"Service error: {e.message}")
        raise HTTPException(
            status_code=500,
            detail={"error": "ServiceError", "detail": e.detail or e.message},
        )

    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500, detail={"error": "InternalServerError", "detail": str(e)}
        )


@router.get("/stats")
async def get_recognition_stats(
    service: RecognitionService = Depends(get_recognition_service_dependency),
) -> dict:
    """
    Get recognition and performance statistics

    Args:
        service: Recognition service (injected)

    Returns:
        Dictionary with statistics

    Example:
        ```bash
        curl -X GET "http://localhost:8000/api/v1/recognition/stats"
        ```
    """
    logger.info("Retrieving recognition statistics")

    try:
        # Get recognition statistics
        recognition_stats = service.get_statistics()

        # Get performance statistics
        perf_monitor = get_performance_monitor()
        performance_stats = perf_monitor.get_stats()

        return {"recognition": recognition_stats, "performance": performance_stats}

    except Exception as e:
        logger.error(f"Error retrieving stats: {str(e)}")
        raise HTTPException(
            status_code=500, detail={"error": "InternalServerError", "detail": str(e)}
        )


@router.get("/recent")
async def get_recent_recognitions(
    limit: int = 10,
    service: RecognitionService = Depends(get_recognition_service_dependency),
) -> list[RecognitionResponse]:
    """
    Get recent recognition results

    Args:
        limit: Maximum number of results to return (default: 10)
        service: Recognition service (injected)

    Returns:
        List of recent RecognitionResponse objects

    Example:
        ```bash
        curl -X GET "http://localhost:8000/api/v1/recognition/recent?limit=5"
        ```
    """
    logger.info(f"Retrieving {limit} recent recognitions")

    try:
        results = service.get_recent_recognitions(limit=limit)
        logger.info(f"Retrieved {len(results)} recent recognitions")
        return results

    except Exception as e:
        logger.error(f"Error retrieving recent recognitions: {str(e)}")
        raise HTTPException(
            status_code=500, detail={"error": "InternalServerError", "detail": str(e)}
        )
