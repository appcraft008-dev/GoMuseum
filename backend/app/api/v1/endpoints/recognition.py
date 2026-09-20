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
    ServiceException,
    TimeoutException,
    ValidationException,
)
from app.schemas.recognition import RecognitionResponse
from app.services.ai_service import get_ai_service
from app.services.cache_service import CacheService
from app.services.image_service import ImageService
from app.services.recognition_service import RecognitionService
from app.utils.performance_monitor import monitor_performance

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
    """⛔ 已下线(2026-07-28)。

    裸 GPT 猜测流:**不鉴权、不计费、不接地**,返回的名字不可信且不带 qid。
    交接文档 2026-07-03 就写明"违反接地原则,将下线",一直没摘,结果是一条
    任何人都能无限调用、烧我们 GPT 额度的后门,也绕过识别次数付费墙。
    前端早已改走计费路径 /api/v1/recognize(见 recognition_remote_datasource)。

    保留路由只为给可能还在调它的老客户端一个明确信号,不是静默 404。
    """
    raise HTTPException(
        status_code=410,
        detail={
            "reason": "endpoint_retired",
            "use": "POST /api/v1/recognize",
        },
    )


async def _retired_recognize_artwork(
    image: UploadFile,
    service: RecognitionService,
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


# ⛔ 以下三个端点已删除(2026-09-20 安全审计):
#   GET /recognition/recent?limit=N   —— 无鉴权返回**他人**识别结果,limit 无上限
#   GET /recognition/stats            —— 无鉴权泄漏内部统计与性能指标
#   GET /recognition/recognize/{id}   —— 无鉴权,id 可枚举
# 三个都读 `recognition_results` 表,而该表唯一的写入者是上面这条已经 410 的老路径
# (`recognition_service.py:121`)—— prod 实测 0 行,所以它们今天返回空、不泄漏任何东西。
# 删掉是因为它们是**雷不是洞**:表里一有行就立刻变成泄漏,而不会有人记得这三个还开着。
# 同型的洞修过一次 —— `/history/*` 的"匿名可读可删"。
