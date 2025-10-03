"""
Recognition Service
Main business logic for artwork recognition workflow
"""

from typing import Optional
from sqlalchemy.orm import Session
from app.models.recognition_result import RecognitionResult
from app.schemas.recognition import RecognitionResponse
from app.services.image_service import ImageService
from app.services.cache_service import CacheService
from app.services.ai_service import AIService
from app.core.exceptions import ServiceException, NotFoundException
import logging
from uuid import UUID

logger = logging.getLogger(__name__)


class RecognitionService:
    """Service for managing artwork recognition workflow"""

    def __init__(
        self,
        db: Session,
        ai_service: AIService,
        cache_service: CacheService,
        image_service: ImageService,
    ):
        """
        Initialize recognition service

        Args:
            db: Database session
            ai_service: AI service for recognition
            cache_service: Cache service for result caching
            image_service: Image processing service
        """
        self.db = db
        self.ai_service = ai_service
        self.cache_service = cache_service
        self.image_service = image_service

    async def recognize_artwork(self, image_data: bytes) -> RecognitionResponse:
        """
        Main recognition workflow:
        1. Validate image
        2. Generate hash
        3. Check cache
        4. Check database
        5. Call AI recognition
        6. Store in database and cache
        7. Return result

        Args:
            image_data: Raw image bytes

        Returns:
            RecognitionResponse with recognition results

        Raises:
            ServiceException: If recognition workflow fails
        """
        try:
            # 1. Validate image
            logger.info("Step 1: Validating image")
            self.image_service.validate_image(image_data)

            # 2. Generate hash
            logger.info("Step 2: Generating image hash")
            image_hash = self.image_service.generate_hash(image_data)
            logger.info(f"Image hash: {image_hash}")

            # 3. Check cache
            logger.info("Step 3: Checking cache")
            cached_result = self.cache_service.get_cached_result(image_hash)
            if cached_result:
                logger.info(f"Cache hit for image_hash={image_hash}")
                return cached_result

            # 4. Check database
            logger.info("Step 4: Checking database")
            db_result = (
                self.db.query(RecognitionResult)
                .filter(RecognitionResult.image_hash == image_hash)
                .first()
            )

            if db_result:
                logger.info(f"Database hit for image_hash={image_hash}")
                response = RecognitionResponse.model_validate(db_result)
                # Update cache
                self.cache_service.cache_result(image_hash, response)
                return response

            # 5. Call AI recognition
            logger.info("Step 5: Calling AI service")
            base64_image = self.image_service.to_base64(image_data)
            ai_result = await self.ai_service.recognize_with_timeout(base64_image)

            # 6. Store in database
            logger.info("Step 6: Storing result in database")
            db_model = RecognitionResult(
                image_hash=image_hash,
                artwork_name=ai_result["artwork_name"],
                artist=ai_result["artist"],
                period=ai_result["period"],
                description=ai_result["description"],
                confidence=ai_result["confidence"],
            )
            self.db.add(db_model)
            self.db.commit()
            self.db.refresh(db_model)
            logger.info(f"Saved recognition result with ID: {db_model.id}")

            # 7. Cache result
            logger.info("Step 7: Caching result")
            response = RecognitionResponse.model_validate(db_model)
            self.cache_service.cache_result(image_hash, response)

            logger.info(
                f"Recognition completed successfully for {ai_result['artwork_name']}"
            )
            return response

        except Exception as e:
            logger.error(f"Recognition failed: {str(e)}", exc_info=True)
            self.db.rollback()
            raise ServiceException("Recognition failed", detail=str(e))

    def get_recognition_by_id(
        self, recognition_id: str
    ) -> Optional[RecognitionResponse]:
        """
        Retrieve recognition result by ID

        Args:
            recognition_id: UUID string of the recognition result

        Returns:
            RecognitionResponse if found

        Raises:
            NotFoundException: If result not found
        """
        try:
            # Convert string to UUID
            result_uuid = UUID(recognition_id)

            result = (
                self.db.query(RecognitionResult)
                .filter(RecognitionResult.id == result_uuid)
                .first()
            )

            if result:
                logger.info(f"Found recognition result: {recognition_id}")
                return RecognitionResponse.model_validate(result)
            else:
                logger.warning(f"Recognition result not found: {recognition_id}")
                raise NotFoundException(
                    "Recognition result not found",
                    detail=f"No result found with ID: {recognition_id}",
                )

        except ValueError:
            logger.error(f"Invalid UUID format: {recognition_id}")
            raise ServiceException(
                "Invalid recognition ID format",
                detail="Recognition ID must be a valid UUID",
            )
        except NotFoundException:
            raise
        except Exception as e:
            logger.error(f"Failed to retrieve recognition result: {str(e)}")
            raise ServiceException(
                "Failed to retrieve recognition result", detail=str(e)
            )

    def get_recent_recognitions(self, limit: int = 10) -> list[RecognitionResponse]:
        """
        Get recent recognition results

        Args:
            limit: Maximum number of results to return

        Returns:
            List of recent RecognitionResponse objects
        """
        try:
            results = (
                self.db.query(RecognitionResult)
                .order_by(RecognitionResult.timestamp.desc())
                .limit(limit)
                .all()
            )

            return [RecognitionResponse.model_validate(r) for r in results]

        except Exception as e:
            logger.error(f"Failed to retrieve recent recognitions: {str(e)}")
            raise ServiceException(
                "Failed to retrieve recent recognitions", detail=str(e)
            )

    def get_statistics(self) -> dict:
        """
        Get recognition statistics

        Returns:
            Dictionary with statistics
        """
        try:
            total_recognitions = self.db.query(RecognitionResult).count()
            avg_confidence = self.db.query(RecognitionResult.confidence).scalar() or 0.0

            cache_stats = self.cache_service.get_cache_stats()

            return {
                "total_recognitions": total_recognitions,
                "average_confidence": avg_confidence,
                "cache_stats": cache_stats,
            }

        except Exception as e:
            logger.error(f"Failed to get statistics: {str(e)}")
            return {
                "total_recognitions": 0,
                "average_confidence": 0.0,
                "cache_stats": {"error": str(e)},
            }


def get_recognition_service(
    db: Session,
    ai_service: Optional[AIService] = None,
    cache_service: Optional[CacheService] = None,
    image_service: Optional[ImageService] = None,
) -> RecognitionService:
    """
    Factory function to create RecognitionService with dependencies

    Args:
        db: Database session
        ai_service: Optional AI service (creates new if not provided)
        cache_service: Optional cache service (creates new if not provided)
        image_service: Optional image service (uses static methods if not provided)

    Returns:
        Configured RecognitionService instance
    """
    if ai_service is None:
        from app.services.ai_service import get_ai_service

        ai_service = get_ai_service()

    if cache_service is None:
        cache_service = CacheService()

    if image_service is None:
        image_service = ImageService()

    return RecognitionService(
        db=db,
        ai_service=ai_service,
        cache_service=cache_service,
        image_service=image_service,
    )
