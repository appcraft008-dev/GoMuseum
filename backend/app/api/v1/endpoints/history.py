"""
History API Endpoints
Handles user recognition history and footprints
"""

import logging
from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import and_, desc
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.recognition_result import RecognitionResult
from app.schemas.recognition import RecognitionResponse

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/recent", response_model=List[RecognitionResponse])
async def get_recent_history(
    limit: int = Query(default=20, le=100, description="Maximum number of results"),
    offset: int = Query(default=0, ge=0, description="Number of results to skip"),
    days: Optional[int] = Query(default=None, description="Filter by last N days"),
    db: Session = Depends(get_db),
) -> List[RecognitionResponse]:
    """
    Get recent recognition history

    Args:
        limit: Maximum number of results (max 100)
        offset: Pagination offset
        days: Optional filter for last N days
        db: Database session (injected)

    Returns:
        List of recognition results ordered by timestamp (newest first)

    Example:
        ```bash
        curl -X GET "http://localhost:8000/api/v1/history/recent?limit=10&days=7"
        ```
    """
    logger.info(f"Fetching recent history: limit={limit}, offset={offset}, days={days}")

    try:
        query = db.query(RecognitionResult)

        # Filter by date range if specified
        if days:
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            query = query.filter(RecognitionResult.timestamp >= cutoff_date)

        # Order by timestamp descending (newest first)
        query = query.order_by(desc(RecognitionResult.timestamp))

        # Apply pagination
        results = query.offset(offset).limit(limit).all()

        logger.info(f"Retrieved {len(results)} history records")

        return [
            RecognitionResponse(
                id=str(result.id),
                artwork_name=result.artwork_name,
                artist=result.artist,
                period=result.period,
                description=result.description,
                confidence=result.confidence,
                timestamp=result.timestamp,
            )
            for result in results
        ]

    except Exception as e:
        logger.error(f"Error retrieving history: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500, detail={"error": "InternalServerError", "detail": str(e)}
        )


@router.get("/search", response_model=List[RecognitionResponse])
async def search_history(
    query: str = Query(..., min_length=2, description="Search query"),
    limit: int = Query(default=20, le=100),
    db: Session = Depends(get_db),
) -> List[RecognitionResponse]:
    """
    Search recognition history

    Searches in artwork_name, artist, and period fields

    Args:
        query: Search query string
        limit: Maximum number of results
        db: Database session (injected)

    Returns:
        Matching recognition results

    Example:
        ```bash
        curl -X GET "http://localhost:8000/api/v1/history/search?query=van%20gogh"
        ```
    """
    logger.info(f"Searching history with query: '{query}'")

    try:
        search_term = f"%{query.lower()}%"

        results = (
            db.query(RecognitionResult)
            .filter(
                and_(
                    (RecognitionResult.artwork_name.ilike(search_term))
                    | (RecognitionResult.artist.ilike(search_term))
                    | (RecognitionResult.period.ilike(search_term))
                )
            )
            .order_by(desc(RecognitionResult.timestamp))
            .limit(limit)
            .all()
        )

        logger.info(f"Found {len(results)} matching records")

        return [
            RecognitionResponse(
                id=str(result.id),
                artwork_name=result.artwork_name,
                artist=result.artist,
                period=result.period,
                description=result.description,
                confidence=result.confidence,
                timestamp=result.timestamp,
            )
            for result in results
        ]

    except Exception as e:
        logger.error(f"Error searching history: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500, detail={"error": "InternalServerError", "detail": str(e)}
        )


@router.get("/stats")
async def get_history_stats(
    days: Optional[int] = Query(default=30, description="Time period in days"),
    db: Session = Depends(get_db),
):
    """
    Get history statistics

    Args:
        days: Time period for statistics (default 30 days)
        db: Database session (injected)

    Returns:
        Statistics including total recognitions, unique artworks, etc.

    Example:
        ```bash
        curl -X GET "http://localhost:8000/api/v1/history/stats?days=30"
        ```
    """
    logger.info(f"Fetching history statistics for last {days} days")

    try:
        cutoff_date = datetime.utcnow() - timedelta(days=days)

        # Total recognitions
        total_recognitions = (
            db.query(RecognitionResult)
            .filter(RecognitionResult.timestamp >= cutoff_date)
            .count()
        )

        # Unique artworks
        unique_artworks = (
            db.query(RecognitionResult.artwork_name)
            .filter(RecognitionResult.timestamp >= cutoff_date)
            .distinct()
            .count()
        )

        # Unique artists
        unique_artists = (
            db.query(RecognitionResult.artist)
            .filter(RecognitionResult.timestamp >= cutoff_date)
            .distinct()
            .count()
        )

        # Average confidence
        avg_confidence = (
            db.query(func.avg(RecognitionResult.confidence))
            .filter(RecognitionResult.timestamp >= cutoff_date)
            .scalar()
        ) or 0.0

        logger.info(f"Statistics: {total_recognitions} total, {unique_artworks} unique")

        return {
            "period_days": days,
            "total_recognitions": total_recognitions,
            "unique_artworks": unique_artworks,
            "unique_artists": unique_artists,
            "average_confidence": round(avg_confidence, 3),
            "period_start": cutoff_date.isoformat(),
            "period_end": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        logger.error(f"Error getting statistics: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500, detail={"error": "InternalServerError", "detail": str(e)}
        )


@router.delete("/{recognition_id}")
async def delete_history_item(recognition_id: str, db: Session = Depends(get_db)):
    """
    Delete a specific recognition from history

    Args:
        recognition_id: UUID of the recognition to delete
        db: Database session (injected)

    Returns:
        Success message

    Example:
        ```bash
        curl -X DELETE "http://localhost:8000/api/v1/history/550e8400-e29b-41d4-a716-446655440000"
        ```
    """
    logger.info(f"Deleting history item: {recognition_id}")

    try:
        result = (
            db.query(RecognitionResult)
            .filter(RecognitionResult.id == recognition_id)
            .first()
        )

        if not result:
            raise HTTPException(
                status_code=404,
                detail={
                    "error": "NotFound",
                    "detail": f"Recognition {recognition_id} not found",
                },
            )

        db.delete(result)
        db.commit()

        logger.info(f"Deleted recognition: {recognition_id}")

        return {
            "success": True,
            "message": f"Recognition {recognition_id} deleted successfully",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting history item: {str(e)}", exc_info=True)
        db.rollback()
        raise HTTPException(
            status_code=500, detail={"error": "InternalServerError", "detail": str(e)}
        )


# Import func for average calculation
from sqlalchemy import func
