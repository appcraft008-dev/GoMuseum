from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel
import hashlib
import base64
import time
import asyncio

from app.core.database import get_db
from app.schemas.recognition import RecognitionRequest, RecognitionResponse, CandidateArtwork
from app.services.recognition_service import RecognitionService
from app.core.api_performance import (
    async_cached, cpu_bound, get_optimized_json_response, 
    recognition_optimizer
)
from app.core.metrics import metrics, timer
from app.core.memory_optimization import memory_monitor

router = APIRouter()

# Initialize recognition service
recognition_service = RecognitionService()

class RecognitionRequestModel(BaseModel):
    image: str  # Base64 encoded image
    user_id: Optional[str] = None
    language: str = "zh"

@router.post("/recognize", response_model=RecognitionResponse)
async def recognize_artwork(
    request: RecognitionRequestModel,
    db: Session = Depends(get_db)
):
    """
    High-performance artwork recognition endpoint
    
    Optimized with caching, async processing, memory monitoring, and sub-100ms response time
    """
    async with memory_monitor(threshold_mb=50.0) as profiler:
        with timer("recognition_request"):
            start_time = time.time()
            
            try:
                # Input validation with optimized error handling
                if not request.image:
                    metrics.increment_counter("recognition_validation_errors")
                    raise HTTPException(status_code=400, detail="Image data required")
                
                # Optimized base64 decoding
                try:
                    with timer("base64_decode"):
                        image_bytes = base64.b64decode(request.image)
                except Exception as e:
                    metrics.increment_counter("recognition_decode_errors")
                    raise HTTPException(
                        status_code=400,
                        detail=f"Invalid base64 image data: {str(e)}"
                    )
                
                # Fast image validation
                if len(image_bytes) > 10 * 1024 * 1024:  # 10MB limit
                    metrics.increment_counter("recognition_size_errors")
                    raise HTTPException(status_code=400, detail="Image too large (max 10MB)")
                
                # Optimized hash calculation
                with timer("image_hash"):
                    image_hash = hashlib.sha256(image_bytes).hexdigest()
                
                # High-performance cache lookup
                with timer("cache_lookup"):
                    cached_result = await recognition_optimizer.get_cached_recognition(image_hash)
                    if cached_result:
                        metrics.increment_counter("recognition_cache_hits")
                        response_time = time.time() - start_time
                        metrics.record_histogram("recognition_response_time", response_time)
                        
                        return get_optimized_json_response(
                            RecognitionResponse(**cached_result).dict()
                        )
                
                metrics.increment_counter("recognition_cache_misses")
                
                # Async quota checking
                if request.user_id:
                    with timer("quota_check"):
                        from app.api.v1.user import check_and_consume_quota
                        quota_valid = await asyncio.to_thread(
                            check_and_consume_quota, db, request.user_id
                        )
                        if not quota_valid:
                            metrics.increment_counter("recognition_quota_exceeded")
                            raise HTTPException(
                                status_code=429,
                                detail={
                                    "error": "quota_exceeded",
                                    "message": "Daily free quota exceeded. Please upgrade your subscription."
                                }
                            )
                
                # Optimized image preprocessing
                with timer("image_preprocessing"):
                    preprocessed_image = await recognition_optimizer.preprocess_image_async(image_bytes)
                
                # High-performance recognition
                with timer("ai_recognition"):
                    recognition_result = await recognition_service.recognize_image(
                        image_bytes=preprocessed_image,
                        image_hash=image_hash,
                        language=request.language
                    )
                
                # Async result caching
                asyncio.create_task(
                    recognition_service.cache_result(image_hash, recognition_result)
                )
                
                # Performance metrics
                response_time = time.time() - start_time
                metrics.record_histogram("recognition_response_time", response_time)
                metrics.increment_counter("recognition_success")
                
                # Target: <100ms for 95% of requests
                if response_time > 0.1:
                    metrics.increment_counter("recognition_slow_requests")
                
                return get_optimized_json_response(
                    RecognitionResponse(**recognition_result).dict()
                )
                
            except HTTPException:
                metrics.increment_counter("recognition_http_errors")
                raise
            except Exception as e:
                metrics.increment_counter("recognition_unexpected_errors")
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"Unexpected error in recognition: {e}", exc_info=True)
                raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/recognize/upload", response_model=RecognitionResponse)
async def recognize_artwork_upload(
    file: UploadFile = File(...),
    language: str = "zh",
    user_id: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    Recognize artwork from uploaded file
    
    Alternative endpoint that accepts file upload instead of base64.
    """
    try:
        # Validate file type
        if not file.content_type.startswith('image/'):
            raise HTTPException(
                status_code=400,
                detail="File must be an image"
            )
        
        # Read image bytes
        image_bytes = await file.read()
        
        # Validate file size (10MB limit)
        if len(image_bytes) > 10 * 1024 * 1024:
            raise HTTPException(
                status_code=400,
                detail="Image file too large (max 10MB)"
            )
        
        # Calculate hash
        image_hash = hashlib.sha256(image_bytes).hexdigest()
        
        # Check cache
        cached_result = await recognition_service.get_cached_result(image_hash)
        if cached_result:
            return RecognitionResponse(**cached_result)
        
        # Perform recognition
        recognition_result = await recognition_service.recognize_image(
            image_bytes=image_bytes,
            image_hash=image_hash,
            language=language
        )
        
        # Cache result
        await recognition_service.cache_result(image_hash, recognition_result)
        
        return RecognitionResponse(**recognition_result)
        
    except HTTPException:
        raise
    except Exception as e:
        # Log unexpected errors without exposing details
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Unexpected error in recognition: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/recognize/history/{user_id}")
async def get_user_recognition_history(
    user_id: str,
    limit: int = 20,
    offset: int = 0,
    db: Session = Depends(get_db)
):
    """Get user's recognition history"""
    # TODO: Implement history retrieval
    return {
        "user_id": user_id,
        "total": 0,
        "items": [],
        "limit": limit,
        "offset": offset
    }

@router.get("/recognize/stats")
async def get_recognition_stats(db: Session = Depends(get_db)):
    """Get recognition statistics"""
    try:
        stats = await recognition_service.get_stats()
        return stats
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get stats: {str(e)}"
        )