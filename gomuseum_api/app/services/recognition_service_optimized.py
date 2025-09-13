"""
Optimized Recognition Service
优化后的识别服务，实现职责分离和性能提升
"""

import asyncio
import hashlib
import uuid
import time
from datetime import datetime
from typing import Optional, Dict, Any, List
from concurrent.futures import ThreadPoolExecutor

from app.core.logging import get_logger
from app.repositories.recognition_repository import RecognitionRepository
from app.services.image_processing.image_processor import ImageProcessor
from app.services.ai_service.enhanced_model_selector import EnhancedModelSelector
from app.core.cache_strategy import cache_manager, CacheStrategy
from app.core.performance_analyzer import monitor_performance
from app.services.ai_service.openai_adapter_simple import OpenAIVisionAdapter

logger = get_logger(__name__)


class OptimizedRecognitionService:
    """优化后的识别服务"""
    
    def __init__(
        self,
        repository: RecognitionRepository,
        image_processor: ImageProcessor,
        model_selector: EnhancedModelSelector,
        ai_monitor: Any,
        cache_manager: Any
    ):
        self.repository = repository
        self.image_processor = image_processor
        self.model_selector = model_selector
        self.ai_monitor = ai_monitor
        self.cache_manager = cache_manager
        
        # AI适配器池
        self._adapters = {}
        self._adapter_pool = {}
        
        # 性能优化配置
        self.confidence_threshold = 0.7
        self.batch_size = 10
        self.max_concurrent_requests = 5
        
        # 线程池用于CPU密集型操作
        self.executor = ThreadPoolExecutor(max_workers=4)
        
        # 初始化适配器
        self._initialize_adapters()
    
    def _initialize_adapters(self):
        """初始化AI适配器池"""
        try:
            from app.services.ai_service.config import get_ai_config
            ai_config = get_ai_config()
            
            for model_name, model_config in ai_config.models.items():
                if model_config.provider == "openai":
                    # 创建适配器池（提高并发能力）
                    adapter_pool = []
                    for i in range(3):  # 每个模型创建3个适配器实例
                        adapter = OpenAIVisionAdapter(
                            api_key=model_config.api_key,
                            model_name=model_config.model_name,
                            max_tokens=model_config.max_tokens,
                            temperature=model_config.temperature
                        )
                        adapter_pool.append(adapter)
                    
                    self._adapter_pool["openai"] = adapter_pool
                    self._adapters["openai"] = adapter_pool[0]  # 默认使用第一个
                    logger.info(f"Initialized {len(adapter_pool)} OpenAI adapters")
                    break
                    
        except Exception as e:
            logger.error(f"Failed to initialize adapters: {e}")
    
    @monitor_performance("recognize_image_optimized")
    async def recognize_image(
        self,
        image_bytes: bytes,
        user_id: str,
        language: str = "zh",
        strategy: str = "balanced",
        constraints: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """主识别方法（优化版）"""
        start_time = time.perf_counter()
        
        # 1. 计算图像哈希（并行）
        image_hash = await self._compute_image_hash_async(image_bytes)
        
        # 2. 检查缓存（L1 -> L2）
        cached_result = await self._check_multi_level_cache(image_hash)
        if cached_result:
            logger.info(f"Cache hit for {image_hash[:8]}, response time: {(time.perf_counter() - start_time) * 1000:.2f}ms")
            return cached_result
        
        # 3. 检查数据库中是否已有结果
        existing_result = await self.repository.get_by_image_hash(image_hash)
        if existing_result and existing_result.status == "completed":
            result = self._format_recognition_result(existing_result)
            # 写入缓存
            await self._cache_result(image_hash, result, existing_result.confidence > 0.8)
            return result
        
        # 4. 创建或获取识别记录
        if not existing_result:
            recognition = await self.repository.create(
                user_id=user_id,
                image_hash=image_hash
            )
        else:
            recognition = existing_result
        
        # 5. 并行执行：图像处理 + 模型选择
        image_task = self._process_image_optimized(image_bytes)
        model_task = self._select_model_optimized(strategy, constraints)
        
        processed_image, selected_model = await asyncio.gather(image_task, model_task)
        
        if not processed_image or not selected_model:
            return self._create_error_response(
                image_hash,
                "Image processing or model selection failed",
                time.perf_counter() - start_time
            )
        
        # 6. 执行AI识别（使用适配器池）
        ai_result = await self._perform_ai_recognition_optimized(
            selected_model,
            processed_image,
            language,
            str(recognition.id)
        )
        
        # 7. 更新数据库记录
        processing_time = time.perf_counter() - start_time
        
        if ai_result.get("success", False):
            await self.repository.update_result(
                recognition_id=recognition.id,
                confidence=ai_result.get("confidence", 0.0),
                candidates=ai_result.get("candidates", []),
                processing_time=processing_time,
                model_used=ai_result.get("model_used", selected_model.model_name),
                cost_usd=ai_result.get("cost_usd", 0.0)
            )
            
            # 异步增加访问计数
            asyncio.create_task(self.repository.increment_access_count(recognition.id))
        
        # 8. 构建响应
        result = {
            "success": ai_result.get("success", False),
            "recognition_id": str(recognition.id),
            "confidence": ai_result.get("confidence", 0.0),
            "processing_time": processing_time * 1000,  # 转换为毫秒
            "candidates": ai_result.get("candidates", []),
            "cached": False,
            "timestamp": datetime.utcnow().isoformat(),
            "image_hash": image_hash,
            "model_used": ai_result.get("model_used", "unknown"),
            "cost_usd": ai_result.get("cost_usd", 0.0)
        }
        
        # 9. 缓存结果（异步）
        if result["success"] and result["confidence"] > self.confidence_threshold:
            asyncio.create_task(
                self._cache_result(image_hash, result, result["confidence"] > 0.85)
            )
        
        logger.info(f"Recognition completed in {processing_time * 1000:.2f}ms, confidence: {result['confidence']:.2f}")
        
        return result
    
    async def _compute_image_hash_async(self, image_bytes: bytes) -> str:
        """异步计算图像哈希"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            self.executor,
            lambda: hashlib.md5(image_bytes).hexdigest()
        )
    
    async def _check_multi_level_cache(self, image_hash: str) -> Optional[Dict[str, Any]]:
        """多级缓存检查"""
        cache_key = f"recognition:result:{image_hash}"
        
        # L1缓存检查（内存）
        result = await self.cache_manager.get(cache_key)
        if result:
            result["cache_level"] = "L1"
            result["cached"] = True
            return result
        
        # L2缓存检查（Redis）会自动晋升到L1
        return None
    
    async def _process_image_optimized(self, image_bytes: bytes) -> Optional[Any]:
        """优化的图像处理"""
        try:
            # 使用线程池处理CPU密集型操作
            loop = asyncio.get_event_loop()
            processed = await loop.run_in_executor(
                self.executor,
                lambda: self.image_processor.process_image_sync(
                    image_data=image_bytes,
                    target_resolution=1024,
                    quality=85
                )
            )
            return processed
        except Exception as e:
            logger.error(f"Image processing failed: {e}")
            return None
    
    async def _select_model_optimized(
        self,
        strategy: str,
        constraints: Optional[Dict[str, Any]]
    ) -> Optional[Any]:
        """优化的模型选择"""
        try:
            return await self.model_selector.select_best_model(
                strategy=strategy,
                max_cost=constraints.get("max_cost") if constraints else None,
                min_accuracy=constraints.get("min_accuracy") if constraints else None
            )
        except Exception as e:
            logger.error(f"Model selection failed: {e}")
            return None
    
    async def _perform_ai_recognition_optimized(
        self,
        selected_model: Any,
        processed_image: Any,
        language: str,
        request_id: str
    ) -> Dict[str, Any]:
        """优化的AI识别（使用适配器池）"""
        # 从适配器池中获取可用适配器
        adapter = self._get_available_adapter(selected_model.provider_name)
        if not adapter:
            return {"success": False, "error": "No adapter available"}
        
        # 开始监控
        self.ai_monitor.record_request_start(selected_model.model_name, request_id)
        
        try:
            # 设置超时
            result = await asyncio.wait_for(
                adapter.recognize_artwork(
                    image_bytes=processed_image.data,
                    language=language
                ),
                timeout=30.0  # 30秒超时
            )
            
            # 记录成功
            self.ai_monitor.record_request_end(
                selected_model.model_name,
                request_id,
                time.perf_counter(),
                True
            )
            
            return result
            
        except asyncio.TimeoutError:
            logger.error(f"AI recognition timeout for request {request_id}")
            self.ai_monitor.record_error(selected_model.model_name, request_id, "Timeout")
            return {"success": False, "error": "Recognition timeout"}
            
        except Exception as e:
            logger.error(f"AI recognition failed: {e}")
            self.ai_monitor.record_error(selected_model.model_name, request_id, str(e))
            return {"success": False, "error": str(e)}
    
    def _get_available_adapter(self, provider: str) -> Optional[Any]:
        """从适配器池获取可用适配器"""
        pool = self._adapter_pool.get(provider, [])
        if not pool:
            return self._adapters.get(provider)
        
        # 简单的轮询策略
        # TODO: 实现更智能的负载均衡
        return pool[hash(time.time()) % len(pool)]
    
    async def _cache_result(
        self,
        image_hash: str,
        result: Dict[str, Any],
        is_popular: bool = False
    ):
        """缓存识别结果"""
        cache_key = f"recognition:result:{image_hash}"
        
        # 根据置信度决定TTL
        if result["confidence"] > 0.9:
            ttl = 7200  # 2小时
        elif result["confidence"] > 0.8:
            ttl = 3600  # 1小时
        else:
            ttl = 1800  # 30分钟
        
        await self.cache_manager.set(
            key=cache_key,
            value=result,
            ttl=ttl,
            strategy=CacheStrategy.WRITE_THROUGH,
            is_popular=is_popular
        )
        
        # 如果是热门内容，标记为热门
        if is_popular:
            self.cache_manager.mark_popular_items([cache_key])
    
    def _format_recognition_result(self, db_result: Any) -> Dict[str, Any]:
        """格式化数据库结果为API响应"""
        return {
            "success": True,
            "recognition_id": str(db_result.id),
            "confidence": db_result.confidence,
            "processing_time": db_result.processing_time * 1000,
            "candidates": [c.to_dict() for c in db_result.candidates],
            "cached": True,
            "timestamp": db_result.completed_at.isoformat() if db_result.completed_at else datetime.utcnow().isoformat(),
            "image_hash": db_result.image_hash,
            "model_used": db_result.model_used,
            "cost_usd": db_result.cost_usd or 0.0
        }
    
    def _create_error_response(
        self,
        image_hash: str,
        error: str,
        processing_time: float
    ) -> Dict[str, Any]:
        """创建错误响应"""
        return {
            "success": False,
            "confidence": 0.0,
            "processing_time": processing_time * 1000,
            "candidates": [],
            "cached": False,
            "timestamp": datetime.utcnow().isoformat(),
            "image_hash": image_hash,
            "error": error
        }
    
    @monitor_performance("batch_recognize_optimized")
    async def batch_recognize(
        self,
        images: List[bytes],
        user_id: str,
        language: str = "zh"
    ) -> List[Dict[str, Any]]:
        """批量识别（优化版）"""
        # 使用信号量限制并发
        semaphore = asyncio.Semaphore(self.max_concurrent_requests)
        
        async def recognize_with_limit(image_bytes: bytes):
            async with semaphore:
                return await self.recognize_image(
                    image_bytes=image_bytes,
                    user_id=user_id,
                    language=language
                )
        
        # 并发执行，但限制并发数
        tasks = [recognize_with_limit(img) for img in images]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 处理异常
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Batch recognition failed for image {i}: {result}")
                processed_results.append(self._create_error_response(
                    image_hash=f"batch_{i}",
                    error=str(result),
                    processing_time=0
                ))
            else:
                processed_results.append(result)
        
        return processed_results
    
    async def warm_cache(self, museum_id: Optional[str] = None):
        """缓存预热"""
        logger.info(f"Starting cache warming for museum: {museum_id or 'all'}")
        
        # 获取热门识别结果
        popular_results = await self.repository.get_popular_recognitions(
            museum_id=museum_id,
            limit=50
        )
        
        # 批量获取完整数据
        image_hashes = [r["image_hash"] for r in popular_results]
        full_results = await self.repository.batch_get_by_hashes(image_hashes)
        
        # 缓存热门结果
        cached_count = 0
        for image_hash, result in full_results.items():
            if result:
                formatted = self._format_recognition_result(result)
                await self._cache_result(image_hash, formatted, is_popular=True)
                cached_count += 1
        
        logger.info(f"Cache warming completed. Cached {cached_count} popular results")
        
        # 设置博物馆上下文
        if museum_id:
            self.cache_manager.set_museum_context(museum_id)
    
    async def get_service_health(self) -> Dict[str, Any]:
        """获取服务健康状态"""
        health = {
            "status": "healthy",
            "adapters": {},
            "cache": {},
            "repository": "connected"
        }
        
        # 检查适配器
        for provider, pool in self._adapter_pool.items():
            health["adapters"][provider] = {
                "pool_size": len(pool),
                "status": "available" if pool else "unavailable"
            }
        
        # 检查缓存
        cache_stats = await self.cache_manager.get_comprehensive_stats()
        health["cache"] = {
            "hit_rate": cache_stats["overall"]["hit_rate_percent"],
            "l1_memory_mb": cache_stats["l1_memory"]["memory_mb"],
            "status": "healthy" if cache_stats["overall"]["hit_rate_percent"] > 50 else "degraded"
        }
        
        # 综合状态
        if not self._adapter_pool or health["cache"]["status"] == "degraded":
            health["status"] = "degraded"
        
        return health
    
    async def cleanup(self):
        """清理资源"""
        logger.info("Cleaning up recognition service resources")
        
        # 关闭线程池
        self.executor.shutdown(wait=False)
        
        # 清理适配器
        self._adapters.clear()
        self._adapter_pool.clear()
        
        logger.info("Recognition service cleanup completed")