"""
Refactored Recognition Service
职责单一、高性能的识别服务实现
"""

import asyncio
import time
import uuid
from typing import Optional, Dict, Any, List
from datetime import datetime
import hashlib
import logging

from app.services.ai_service.enhanced_model_selector import EnhancedModelSelector
from app.services.ai_service.openai_adapter_simple import OpenAIVisionAdapter
from app.services.image_processing.image_processor import ImageProcessor
from app.services.ai_service.monitoring import ai_monitor
from app.services.ai_service.config import get_ai_config
from app.core.cache_strategy import mark_popular_items
from app.core.api_performance import cpu_bound, io_bound
from app.core.logging import get_logger
from app.core.metrics import metrics
from app.core.exceptions import ValidationError, InfrastructureException, ExternalServiceException

logger = get_logger(__name__)

class AIModelManager:
    """AI模型管理器 - 负责模型的初始化和选择"""
    
    def __init__(self):
        self.adapters = {}
        self.model_selector = EnhancedModelSelector()
        self._initialize_adapters()
    
    def _initialize_adapters(self):
        """初始化AI适配器"""
        try:
            ai_config = get_ai_config()
            
            for model_name, model_config in ai_config.models.items():
                if model_config.provider == "openai":
                    try:
                        adapter = OpenAIVisionAdapter(
                            api_key=model_config.api_key,
                            model_name=model_config.model_name,
                            max_tokens=model_config.max_tokens,
                            temperature=model_config.temperature
                        )
                        self.adapters["openai"] = adapter
                        logger.info(f"Initialized OpenAI adapter: {model_config.model_name}")
                    except Exception as e:
                        logger.error(f"Failed to initialize OpenAI adapter: {e}")
            
            if not self.adapters:
                logger.warning("No AI adapters initialized")
                # 为演示目的，添加一个模拟适配器
                self._add_mock_adapter()
                
        except Exception as e:
            logger.error(f"Adapter initialization failed: {e}")
    
    def _add_mock_adapter(self):
        """添加模拟适配器用于演示"""
        class MockAdapter:
            async def recognize_artwork(self, image_bytes: bytes, language: str = "zh"):
                """模拟识别结果"""
                return {
                    "success": True,
                    "confidence": 0.85,
                    "artwork_title": "蒙娜丽莎",
                    "artist_name": "莱奥纳多·达·芬奇",
                    "creation_year": "1503-1519",
                    "style": "文艺复兴",
                    "description": "这是一幅世界闻名的肖像画作品，展现了文艺复兴时期的艺术特色。画中人物神秘的微笑和细腻的绘画技法令人印象深刻。",
                    "museum": "卢浮宫博物馆",
                    "location": "法国巴黎",
                    "cultural_significance": "作为世界艺术史上最重要的作品之一，代表了文艺复兴时期艺术的巅峰成就。",
                    "tags": ["文艺复兴", "肖像画", "意大利艺术", "经典作品"],
                    "mock_response": True
                }
        
        self.adapters["mock"] = MockAdapter()
        logger.info("Mock adapter initialized for demonstration purposes")
    
    def get_adapter(self, provider: str):
        """获取指定的适配器"""
        return self.adapters.get(provider)
    
    async def select_best_model(self, strategy: str = "balanced", constraints: Optional[Dict] = None):
        """选择最佳模型"""
        return await self.model_selector.select_best_model(
            strategy=strategy,
            max_cost=constraints.get("max_cost") if constraints else None,
            min_accuracy=constraints.get("min_accuracy") if constraints else None,
            provider=constraints.get("provider") if constraints else None
        )

class ImageProcessingService:
    """图像处理服务 - 负责图像的验证和预处理"""
    
    def __init__(self):
        self.processor = ImageProcessor()
        self.max_image_size = 10 * 1024 * 1024  # 10MB
    
    @cpu_bound
    def validate_image(self, image_bytes: bytes) -> bool:
        """验证图像格式和大小"""
        if len(image_bytes) > self.max_image_size:
            raise ValueError(f"Image too large: {len(image_bytes)} bytes")
        
        # 检查图像格式
        if not image_bytes.startswith((b'\xff\xd8\xff', b'\x89PNG', b'GIF89a', b'GIF87a')):
            raise ValueError("Unsupported image format")
        
        return True
    
    async def process_image(
        self, 
        image_bytes: bytes,
        target_resolution: int = 1024,
        quality: int = 85
    ) -> Any:
        """处理图像"""
        # 验证图像
        await self.validate_image(image_bytes)
        
        # 预处理图像
        processed = await self.processor.process_image(
            image_data=image_bytes,
            target_resolution=target_resolution,
            quality=quality
        )
        
        logger.debug(f"Image processed: {processed.width}x{processed.height}, "
                    f"compression: {processed.compression_ratio:.2f}")
        
        return processed

class RecognitionService:
    """
    重构后的识别服务 - 使用依赖注入
    职责：协调识别流程，不包含数据访问和缓存管理
    """
    
    def __init__(self, artwork_repository=None, recognition_repository=None, cache_manager=None):
        # 依赖注入
        self.artwork_repository = artwork_repository
        self.recognition_repository = recognition_repository  
        self.cache_manager = cache_manager
        
        # 服务组件
        self.model_manager = AIModelManager()
        self.image_service = ImageProcessingService()
        self.confidence_threshold = 0.7
        
        # 性能监控
        self.request_counter = 0
        self.cache_hits = 0
        self.cache_misses = 0
    
    async def recognize_artwork(
        self,
        image_bytes: bytes,
        image_hash: str,
        language: str = "zh",
        strategy: str = "balanced",
        constraints: Optional[Dict[str, Any]] = None,
        enable_fallback: bool = True
    ) -> Dict[str, Any]:
        """
        识别艺术品
        优化：分离关注点，提升性能
        """
        start_time = time.perf_counter()
        request_id = str(uuid.uuid4())
        
        try:
            # 1. 尝试从缓存获取（通过Repository）
            if not self.recognition_repository:
                raise InfrastructureException("Recognition repository not injected")
                
            cached_result = await self.recognition_repository.get_recognition_result(image_hash)
            if cached_result:
                self.cache_hits += 1
                metrics.increment_counter("recognition_cache_hits")
                
                # 记录响应时间
                response_time = (time.perf_counter() - start_time) * 1000
                metrics.record_histogram("recognition_response_time_ms", response_time)
                
                # 检查L1缓存性能目标
                if response_time < 10:
                    metrics.increment_counter("recognition_l1_hits")
                
                cached_result["response_time_ms"] = response_time
                return cached_result
            
            self.cache_misses += 1
            metrics.increment_counter("recognition_cache_misses")
            
            # 2. 处理图像
            processed_image = await self.image_service.process_image(image_bytes)
            
            # 3. 选择最佳模型
            selected_model = await self.model_manager.select_best_model(strategy, constraints)
            
            # 4. 执行AI识别
            recognition_result = await self._perform_recognition(
                selected_model,
                processed_image,
                language,
                request_id
            )
            
            # 5. 处理识别结果
            if recognition_result["success"]:
                # 保存到数据库和缓存
                await self.repository.save_recognition_result(
                    image_hash=image_hash,
                    result_data=recognition_result,
                    confidence=recognition_result["confidence"],
                    model_used=recognition_result["model_used"],
                    processing_time=time.perf_counter() - start_time
                )
                
                # 标记热门内容
                if recognition_result["confidence"] > 0.9:
                    mark_popular_items([f"recognition:{image_hash}"])
            
            # 6. 如果失败且启用回退，尝试其他模型
            elif enable_fallback and len(self.model_manager.adapters) > 1:
                recognition_result = await self._try_fallback_models(
                    selected_model,
                    processed_image,
                    language,
                    request_id
                )
            
            # 记录最终响应时间
            response_time = (time.perf_counter() - start_time) * 1000
            recognition_result["response_time_ms"] = response_time
            
            metrics.record_histogram("recognition_response_time_ms", response_time)
            
            return recognition_result
            
        except Exception as e:
            logger.error(f"Recognition failed: {e}")
            
            return {
                "success": False,
                "error": str(e),
                "confidence": 0.0,
                "candidates": [],
                "response_time_ms": (time.perf_counter() - start_time) * 1000,
                "timestamp": datetime.utcnow().isoformat()
            }
    
    async def _perform_recognition(
        self,
        selected_model,
        processed_image,
        language: str,
        request_id: str
    ) -> Dict[str, Any]:
        """执行AI识别"""
        adapter = self.model_manager.get_adapter(selected_model.provider_name)
        
        if not adapter:
            return {
                "success": False,
                "error": f"No adapter for provider: {selected_model.provider_name}"
            }
        
        # 开始监控
        ai_monitor.record_request_start(selected_model.model_name, request_id)
        
        try:
            result = await adapter.recognize_artwork(
                image_bytes=processed_image.data,
                language=language
            )
            
            # 记录成功
            ai_monitor.record_request_end(
                selected_model.model_name,
                request_id,
                time.perf_counter(),
                result.get("success", False)
            )
            
            return {
                "success": result.get("success", False),
                "confidence": result.get("confidence", 0.0),
                "candidates": result.get("candidates", []),
                "model_used": selected_model.model_name,
                "cost_usd": result.get("cost_usd", 0.0),
                "description": result.get("description", ""),
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            # 记录错误
            ai_monitor.record_error(selected_model.model_name, request_id, str(e))
            
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _try_fallback_models(
        self,
        failed_model,
        processed_image,
        language: str,
        request_id: str
    ) -> Dict[str, Any]:
        """尝试回退模型"""
        for provider, adapter in self.model_manager.adapters.items():
            if provider != failed_model.provider_name:
                try:
                    logger.info(f"Trying fallback model: {provider}")
                    
                    result = await adapter.recognize_artwork(
                        image_bytes=processed_image.data,
                        language=language
                    )
                    
                    if result.get("success", False):
                        return {
                            "success": True,
                            "confidence": result.get("confidence", 0.0),
                            "candidates": result.get("candidates", []),
                            "model_used": f"fallback-{provider}",
                            "fallback_used": True,
                            "timestamp": datetime.utcnow().isoformat()
                        }
                        
                except Exception as e:
                    logger.error(f"Fallback model {provider} failed: {e}")
        
        return {
            "success": False,
            "error": "All models failed"
        }
    
    async def batch_recognize(
        self,
        images: List[bytes],
        strategy: str = "balanced",
        language: str = "zh",
        batch_size: int = 10
    ) -> List[Dict[str, Any]]:
        """
        批量识别图像
        优化：批处理和并发执行
        """
        results = []
        
        # 分批处理
        for i in range(0, len(images), batch_size):
            batch = images[i:i+batch_size]
            
            # 并发处理批次
            tasks = []
            for image_bytes in batch:
                image_hash = hashlib.md5(image_bytes).hexdigest()
                task = self.recognize_artwork(
                    image_bytes=image_bytes,
                    image_hash=image_hash,
                    language=language,
                    strategy=strategy
                )
                tasks.append(task)
            
            # 等待批次完成
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # 处理结果
            for result in batch_results:
                if isinstance(result, Exception):
                    results.append({
                        "success": False,
                        "error": str(result),
                        "confidence": 0.0,
                        "candidates": []
                    })
                else:
                    results.append(result)
        
        return results
    
    async def warm_cache(self, popular_image_hashes: List[str]):
        """
        预热缓存
        提前加载热门内容到缓存
        """
        logger.info(f"Warming cache with {len(popular_image_hashes)} popular images")
        
        # 批量获取识别结果
        results = await self.repository.batch_get_recognition_results(popular_image_hashes)
        
        # 标记为热门内容
        cache_keys = [f"recognition:{hash}" for hash in popular_image_hashes]
        mark_popular_items(cache_keys)
        
        logger.info(f"Cache warmed with {len(results)} results")
        
        return len(results)
    
    async def get_performance_stats(self) -> Dict[str, Any]:
        """获取性能统计"""
        total_requests = self.cache_hits + self.cache_misses
        hit_rate = (self.cache_hits / total_requests * 100) if total_requests > 0 else 0
        
        # 获取Repository统计
        repo_stats = await self.repository.get_recognition_stats()
        
        # 获取缓存性能
        cache_stats = await cache_manager.get_comprehensive_stats()
        
        return {
            "service_stats": {
                "total_requests": total_requests,
                "cache_hits": self.cache_hits,
                "cache_misses": self.cache_misses,
                "hit_rate": hit_rate,
                "meets_target": hit_rate >= 70  # 70%命中率目标
            },
            "repository_stats": repo_stats,
            "cache_performance": cache_stats,
            "model_availability": {
                provider: adapter is not None 
                for provider, adapter in self.model_manager.adapters.items()
            }
        }
    
    async def health_check(self) -> Dict[str, Any]:
        """健康检查"""
        health = {
            "healthy": True,
            "components": {},
            "timestamp": datetime.utcnow().isoformat()
        }
        
        # 检查AI模型
        for provider, adapter in self.model_manager.adapters.items():
            try:
                adapter_health = await adapter.health_check()
                health["components"][f"ai_{provider}"] = {
                    "status": "healthy" if adapter_health else "unhealthy"
                }
                if not adapter_health:
                    health["healthy"] = False
            except Exception as e:
                health["components"][f"ai_{provider}"] = {
                    "status": "error",
                    "error": str(e)
                }
                health["healthy"] = False
        
        # 检查图像处理
        try:
            # 简单测试
            test_image = bytes([0xFF, 0xD8, 0xFF, 0xE0] + [0] * 100)
            await self.image_service.validate_image(test_image)
            health["components"]["image_processing"] = {"status": "healthy"}
        except Exception as e:
            health["components"]["image_processing"] = {
                "status": "error",
                "error": str(e)
            }
            health["healthy"] = False
        
        # 检查缓存性能
        cache_perf = cache_manager.get_performance_status()
        health["components"]["cache"] = {
            "status": "healthy" if cache_perf["targets_met"]["overall"] else "degraded",
            "hit_rate": cache_perf["overall_hit_rate"]
        }
        
        return health

# 全局实例
recognition_service = RecognitionService()