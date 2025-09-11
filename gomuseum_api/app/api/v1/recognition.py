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
from app.core.error_handler import handle_api_error

router = APIRouter()

# Initialize recognition service
recognition_service = RecognitionService()

class RecognitionRequestModel(BaseModel):
    image: str  # Base64 encoded image
    user_id: Optional[str] = None
    language: str = "zh"

@router.post("/recognition/recognize", response_model=RecognitionResponse)
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
                
                # High-performance recognition with AI integration
                with timer("ai_recognition"):
                    recognition_result = await recognition_service.recognize_image_enhanced(
                        image_bytes=preprocessed_image,
                        image_hash=image_hash,
                        language=request.language,
                        strategy="balanced",  # 使用平衡策略
                        enable_fallback=True
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
                raise handle_api_error(
                    error=e,
                    default_message="图像识别服务暂时不可用，请稍后重试",
                    status_code=500,
                    context={"endpoint": "recognize", "method": "POST"},
                    user_id=request.user_id,
                    request_id=getattr(request, 'request_id', None)
                )

@router.post("/recognition/upload", response_model=RecognitionResponse)
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
        
        # Perform enhanced recognition with AI
        recognition_result = await recognition_service.recognize_image_enhanced(
            image_bytes=image_bytes,
            image_hash=image_hash,
            language=language,
            strategy="balanced",
            enable_fallback=True
        )
        
        # Cache result
        await recognition_service.cache_result(image_hash, recognition_result)
        
        return RecognitionResponse(**recognition_result)
        
    except HTTPException:
        raise
    except Exception as e:
        raise handle_api_error(
            error=e,
            default_message="文件上传识别服务暂时不可用，请稍后重试",
            status_code=500,
            context={"endpoint": "upload", "method": "POST"},
            user_id=user_id,
            request_id=getattr(file, 'request_id', None)
        )

@router.get("/recognition/history/{user_id}")
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

@router.get("/recognition/stats")
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

@router.get("/recognition/health")
async def get_recognition_health(db: Session = Depends(get_db)):
    """获取增强识别服务健康状态"""
    try:
        health_status = await recognition_service.get_enhanced_health_status()
        
        # 如果服务不健康，返回503状态码
        if not health_status.get("healthy", False):
            raise HTTPException(
                status_code=503,
                detail={
                    "message": "Recognition service is unhealthy",
                    "issues": health_status.get("issues", []),
                    "details": health_status
                }
            )
        
        return health_status
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to check health: {str(e)}"
        )

class BatchRecognitionRequest(BaseModel):
    images: List[str]  # List of base64 encoded images
    language: str = "zh"
    strategy: str = "balanced"
    user_id: Optional[str] = None

@router.post("/recognition/batch", response_model=List[RecognitionResponse])
async def batch_recognize_artworks(
    request: BatchRecognitionRequest,
    db: Session = Depends(get_db)
):
    """
    批量识别艺术品
    """
    try:
        # 验证批量请求数量限制
        if len(request.images) > 10:
            raise HTTPException(
                status_code=400,
                detail="Maximum 10 images per batch request"
            )
        
        # 解码所有图像
        image_bytes_list = []
        for i, base64_image in enumerate(request.images):
            try:
                image_bytes = base64.b64decode(base64_image)
                if len(image_bytes) > 10 * 1024 * 1024:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Image {i+1} too large (max 10MB)"
                    )
                image_bytes_list.append(image_bytes)
            except Exception as e:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid image data for image {i+1}: {str(e)}"
                )
        
        # 执行批量识别
        results = await recognition_service.batch_recognize_images(
            images=image_bytes_list,
            strategy=request.strategy,
            language=request.language
        )
        
        # 转换为响应格式
        responses = []
        for result in results:
            try:
                responses.append(RecognitionResponse(**result))
            except Exception as e:
                # 如果转换失败，添加错误响应
                responses.append(RecognitionResponse(
                    success=False,
                    confidence=0.0,
                    candidates=[],
                    processing_time=0.0,
                    cached=False,
                    timestamp="",
                    image_hash="",
                    error=f"Response conversion failed: {str(e)}"
                ))
        
        return responses
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Batch recognition failed: {str(e)}"
        )