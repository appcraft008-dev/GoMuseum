import asyncio
import hashlib
import json
import uuid
import io
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
import time
import logging

from app.core.config import settings
from app.core.redis_client import redis_client, get_cache_key
from app.schemas.recognition import CandidateArtwork
from app.services.ai_service.enhanced_model_selector import EnhancedModelSelector
from app.services.ai_service.openai_adapter_simple import OpenAIVisionAdapter
from app.services.image_processing.image_processor import ImageProcessor, ImageValidationError, ImageProcessingError
from app.services.ai_service.monitoring import ai_monitor
from app.services.ai_service.config import get_ai_config
from PIL import Image

logger = logging.getLogger(__name__)

class RecognitionService:
    def __init__(self):
        self.cache_ttl = settings.cache_ttl
        self.confidence_threshold = 0.7
        
        # 初始化AI服务组件
        self.image_processor = ImageProcessor()
        self.model_selector = EnhancedModelSelector()
        self.ai_monitor = ai_monitor
        self._adapters = {}
        
        # 初始化适配器
        self._initialize_adapters()
    
    def _initialize_adapters(self):
        """初始化AI适配器"""
        try:
            ai_config = get_ai_config()
            
            # 遍历所有配置的模型并初始化对应的适配器
            for model_name, model_config in ai_config.models.items():
                if model_config.provider == "openai":
                    try:
                        openai_adapter = OpenAIVisionAdapter(
                            api_key=model_config.api_key,
                            model_name=model_config.model_name,
                            max_tokens=model_config.max_tokens,
                            temperature=model_config.temperature
                        )
                        self._adapters["openai"] = openai_adapter
                        logger.info(f"OpenAI adapter initialized with model: {model_config.model_name}")
                        break  # 只初始化第一个OpenAI模型
                    except Exception as e:
                        logger.error(f"Failed to initialize OpenAI adapter: {e}")
                        
                # 可以在这里添加其他提供商的适配器
                # elif model_config.provider == "anthropic":
                #     try:
                #         claude_adapter = ClaudeAdapter(...)
                #         self._adapters["anthropic"] = claude_adapter
                #     except Exception as e:
                #         logger.error(f"Failed to initialize Claude adapter: {e}")
            
            logger.info(f"Initialized {len(self._adapters)} AI adapters")
            
            # 如果没有初始化任何适配器，记录警告
            if not self._adapters:
                logger.warning("No AI adapters initialized. Recognition will fall back to mock responses.")
            
        except Exception as e:
            logger.error(f"Failed to initialize adapters: {e}")
    
    def register_adapter(self, provider: str, adapter):
        """注册新的AI适配器"""
        self._adapters[provider] = adapter
        logger.info(f"Registered adapter for provider: {provider}")
        
    async def get_cached_result(self, image_hash: str) -> Optional[Dict[str, Any]]:
        """Get recognition result from cache"""
        cache_key = get_cache_key("recognition", image_hash)
        
        try:
            cached_data = await redis_client.get(cache_key)
            if cached_data:
                # Update cache statistics
                await self._update_cache_stats("hit")
                logger.info(f"Cache HIT for image {image_hash[:8]}")
                
                # Mark as cached and return
                cached_data["cached"] = True
                return cached_data
                
        except Exception as e:
            logger.error(f"Cache GET error: {e}")
            
        await self._update_cache_stats("miss")
        logger.info(f"Cache MISS for image {image_hash[:8]}")
        return None
    
    async def cache_result(self, image_hash: str, result: Dict[str, Any]) -> bool:
        """Cache recognition result"""
        cache_key = get_cache_key("recognition", image_hash)
        
        try:
            # Remove cached flag before caching
            cache_data = result.copy()
            cache_data.pop("cached", None)
            
            success = await redis_client.set(cache_key, cache_data, ttl=self.cache_ttl)
            if success:
                logger.info(f"Cached result for image {image_hash[:8]}")
            return success
            
        except Exception as e:
            logger.error(f"Cache SET error: {e}")
            return False
    
    async def recognize_image(
        self,
        image_bytes: bytes,
        image_hash: str,
        language: str = "zh"
    ) -> Dict[str, Any]:
        """
        Recognize artwork in image
        
        This is the main recognition method that will be implemented
        with AI models in Step 2. For now, returns mock data.
        """
        start_time = time.time()
        
        try:
            # TODO: Implement actual AI recognition
            # For now, return mock data to test the infrastructure
            
            await asyncio.sleep(0.5)  # Simulate processing time
            
            mock_result = {
                "success": True,
                "confidence": 0.85,
                "processing_time": time.time() - start_time,
                "candidates": [
                    {
                        "artwork_id": "mock-uuid-1",
                        "name": "蒙娜丽莎" if language == "zh" else "Mona Lisa",
                        "artist": "列奥纳多·达芬奇" if language == "zh" else "Leonardo da Vinci",
                        "confidence": 0.85,
                        "museum": "卢浮宫" if language == "zh" else "Louvre Museum",
                        "period": "1503-1519",
                        "image_url": None
                    }
                ],
                "cached": False,
                "timestamp": datetime.utcnow().isoformat(),
                "image_hash": image_hash,
                "model_used": "mock-model"
            }
            
            logger.info(f"Recognition completed for image {image_hash[:8]} in {mock_result['processing_time']:.2f}s")
            return mock_result
            
        except Exception as e:
            logger.error(f"Recognition failed for image {image_hash[:8]}: {e}")
            
            return {
                "success": False,
                "confidence": 0.0,
                "processing_time": time.time() - start_time,
                "candidates": [],
                "cached": False,
                "timestamp": datetime.utcnow().isoformat(),
                "image_hash": image_hash,
                "error": str(e)
            }
    
    async def _check_cache_and_fallback(
        self, 
        image_hash: str, 
        image_bytes: bytes, 
        language: str
    ) -> Optional[Dict[str, Any]]:
        """检查缓存，如果没有适配器则回退到模拟识别"""
        # 首先检查缓存（无论有没有适配器）
        cached_result = await self.get_cached_result(image_hash)
        if cached_result:
            return cached_result
        
        # 如果没有适配器，使用mock识别但要支持缓存
        if not self._adapters:
            logger.info("No AI adapters available, using mock recognition with caching")
            mock_result = await self.recognize_image(image_bytes, image_hash, language)
            # 缓存mock结果
            if mock_result.get("success", False):
                await self.cache_result(image_hash, mock_result)
            return mock_result
        
        return None
    
    async def _validate_and_preprocess_image(
        self, 
        image_bytes: bytes, 
        image_hash: str, 
        start_time: float
    ) -> Dict[str, Any]:
        """验证和预处理图像"""
        try:
            processed_image = await self.image_processor.process_image(
                image_data=image_bytes,
                target_resolution=1024,
                quality=85
            )
            logger.info(f"Image processed: {processed_image.width}x{processed_image.height}, "
                       f"compression: {processed_image.compression_ratio:.2f}")
            return {"success": True, "data": processed_image}
        except (ImageValidationError, ImageProcessingError) as e:
            logger.error(f"Image processing failed: {e}")
            return {
                "success": False,
                "confidence": 0.0,
                "processing_time": time.time() - start_time,
                "candidates": [],
                "cached": False,
                "timestamp": datetime.utcnow().isoformat(),
                "image_hash": image_hash,
                "error": f"Image processing failed: {str(e)}"
            }
    
    async def _select_optimal_model(
        self, 
        strategy: str, 
        constraints: Optional[Dict[str, Any]], 
        image_hash: str, 
        start_time: float
    ) -> Dict[str, Any]:
        """选择最优AI模型"""
        try:
            select_kwargs = {"strategy": strategy}
            if constraints:
                if "max_cost" in constraints:
                    select_kwargs["max_cost"] = constraints["max_cost"]
                if "min_accuracy" in constraints:
                    select_kwargs["min_accuracy"] = constraints["min_accuracy"]
                if "provider" in constraints:
                    select_kwargs["provider"] = constraints["provider"]
            
            selected_model = await self.model_selector.select_best_model(**select_kwargs)
            logger.info(f"Selected model: {selected_model.model_name} (provider: {selected_model.provider_name})")
            return {"success": True, "model": selected_model}
        except Exception as e:
            logger.error(f"Model selection failed: {e}")
            return {
                "success": False,
                "confidence": 0.0,
                "processing_time": time.time() - start_time,
                "candidates": [],
                "cached": False,
                "timestamp": datetime.utcnow().isoformat(),
                "image_hash": image_hash,
                "error": f"Model selection failed: {str(e)}"
            }
    
    async def _perform_ai_recognition(
        self, 
        selected_model, 
        processed_image, 
        language: str, 
        request_id: str, 
        image_hash: str, 
        start_time: float
    ) -> Dict[str, Any]:
        """执行AI识别"""
        adapter = self._adapters.get(selected_model.provider_name)
        if not adapter:
            logger.info(f"No adapter available for provider: {selected_model.provider_name}, falling back to mock recognition")
            return {"success": False, "fallback_needed": True}
        
        # 开始监控
        self.ai_monitor.record_request_start(selected_model.model_name, request_id)
        
        try:
            ai_result = await adapter.recognize_artwork(
                image_bytes=processed_image.data,
                language=language
            )
            
            processing_time = time.time() - start_time
            
            # 记录成功
            self.ai_monitor.record_request_end(
                selected_model.model_name, 
                request_id, 
                processing_time, 
                ai_result.get("success", False)
            )
            
            # 构建响应
            result = {
                "success": ai_result.get("success", False),
                "confidence": ai_result.get("confidence", 0.0),
                "processing_time": processing_time,
                "candidates": ai_result.get("candidates", []),
                "cached": False,
                "timestamp": datetime.utcnow().isoformat(),
                "image_hash": image_hash,
                "model_used": ai_result.get("model_used", selected_model.model_name),
                "cost_usd": ai_result.get("cost_usd", 0.0),
                "description": ai_result.get("description", "")
            }
            
            # 缓存结果
            if result["success"] and result["confidence"] > self.confidence_threshold:
                await self.cache_result(image_hash, result)
            
            logger.info(f"Recognition completed for image {image_hash[:8]} in {processing_time:.2f}s, "
                       f"confidence: {result['confidence']:.2f}")
            
            return result
            
        except Exception as e:
            processing_time = time.time() - start_time
            error_msg = str(e)
            
            # 记录错误
            self.ai_monitor.record_request_end(selected_model.model_name, request_id, processing_time, False)
            self.ai_monitor.record_error(selected_model.model_name, request_id, error_msg)
            
            logger.error(f"AI recognition failed: {error_msg}")
            
            return {
                "success": False,
                "error_msg": error_msg,
                "model": selected_model,
                "processed_image": processed_image,
                "fallback_needed": True
            }
    
    async def _try_fallback_recognition(
        self, 
        selected_model, 
        processed_image, 
        language: str, 
        start_time: float, 
        image_hash: str
    ) -> Optional[Dict[str, Any]]:
        """尝试回退模型识别"""
        fallback_providers = [p for p in self._adapters.keys() if p != selected_model.provider_name]
        if not fallback_providers:
            return None
        
        fallback_provider = fallback_providers[0]
        fallback_adapter = self._adapters[fallback_provider]
        
        try:
            fallback_result = await fallback_adapter.recognize_artwork(
                image_bytes=processed_image.data,
                language=language
            )
            
            if fallback_result.get("success", False):
                logger.info(f"Fallback model successful: {fallback_provider}")
                return {
                    "success": True,
                    "confidence": fallback_result.get("confidence", 0.0),
                    "processing_time": time.time() - start_time,
                    "candidates": fallback_result.get("candidates", []),
                    "cached": False,
                    "timestamp": datetime.utcnow().isoformat(),
                    "image_hash": image_hash,
                    "model_used": fallback_result.get("model_used", f"fallback-{fallback_provider}"),
                    "cost_usd": fallback_result.get("cost_usd", 0.0),
                    "description": fallback_result.get("description", ""),
                    "fallback_used": True
                }
        except Exception as fallback_error:
            logger.error(f"Fallback model also failed: {fallback_error}")
        
        return None
    
    async def recognize_image_enhanced(
        self,
        image_bytes: bytes,
        image_hash: str,
        language: str = "zh",
        strategy: str = "balanced",
        constraints: Optional[Dict[str, Any]] = None,
        enable_fallback: bool = True
    ) -> Dict[str, Any]:
        """
        增强的图像识别方法
        集成AI适配器、图像处理和监控功能
        """
        start_time = time.time()
        request_id = str(uuid.uuid4())
        
        try:
            # 1. 检查缓存和回退
            cache_result = await self._check_cache_and_fallback(image_hash, image_bytes, language)
            if cache_result:
                return cache_result
            
            # 2. 图像预处理和验证
            image_result = await self._validate_and_preprocess_image(image_bytes, image_hash, start_time)
            if not image_result["success"]:
                return image_result
            processed_image = image_result["data"]
            
            # 3. 模型选择
            model_result = await self._select_optimal_model(strategy, constraints, image_hash, start_time)
            if not model_result["success"]:
                return model_result
            selected_model = model_result["model"]
            
            # 4. AI识别
            recognition_result = await self._perform_ai_recognition(
                selected_model, processed_image, language, request_id, image_hash, start_time
            )
            
            # 如果主要识别成功，直接返回
            if recognition_result["success"]:
                return recognition_result
            
            # 5. 尝试回退识别
            if enable_fallback and recognition_result.get("fallback_needed", False) and len(self._adapters) > 1:
                logger.info("Attempting fallback model...")
                fallback_result = await self._try_fallback_recognition(
                    selected_model, processed_image, language, start_time, image_hash
                )
                if fallback_result:
                    return fallback_result
            
            # 6. 所有方法都失败，返回错误
            processing_time = time.time() - start_time
            return {
                "success": False,
                "confidence": 0.0,
                "processing_time": processing_time,
                "candidates": [],
                "cached": False,
                "timestamp": datetime.utcnow().isoformat(),
                "image_hash": image_hash,
                "error": recognition_result.get("error_msg", "Recognition failed"),
                "model_used": selected_model.model_name if 'selected_model' in locals() else "unknown"
            }
                
        except Exception as e:
            processing_time = time.time() - start_time
            logger.error(f"Recognition service error: {e}")
            
            return {
                "success": False,
                "confidence": 0.0,
                "processing_time": processing_time,
                "candidates": [],
                "cached": False,
                "timestamp": datetime.utcnow().isoformat(),
                "image_hash": image_hash,
                "error": f"Service error: {str(e)}"
            }
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get recognition service statistics"""
        try:
            # Get cache statistics
            cache_hits = await redis_client.get(get_cache_key("stats", "cache_hits")) or 0
            cache_misses = await redis_client.get(get_cache_key("stats", "cache_misses")) or 0
            
            total_requests = cache_hits + cache_misses
            hit_rate = (cache_hits / total_requests * 100) if total_requests > 0 else 0
            
            # Get Redis stats
            redis_stats = await redis_client.get_stats()
            
            return {
                "cache_statistics": {
                    "hits": cache_hits,
                    "misses": cache_misses,
                    "hit_rate": f"{hit_rate:.1f}%",
                    "total_requests": total_requests
                },
                "redis_statistics": redis_stats,
                "service_status": "operational",
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to get stats: {e}")
            return {
                "error": str(e),
                "service_status": "degraded",
                "timestamp": datetime.utcnow().isoformat()
            }
    
    async def _update_cache_stats(self, event: str):
        """Update cache statistics"""
        try:
            cache_key = get_cache_key("stats", f"cache_{event}s")
            await redis_client.increment(cache_key)
        except Exception as e:
            logger.error(f"Failed to update cache stats: {e}")
    
    def _validate_image(self, image_bytes: bytes) -> bool:
        """Validate image format and size"""
        if len(image_bytes) > settings.max_image_size:
            raise ValueError(f"Image too large: {len(image_bytes)} bytes (max: {settings.max_image_size})")
        
        # Basic image format validation
        if not image_bytes.startswith((b'\xff\xd8\xff', b'\x89PNG', b'GIF89a', b'GIF87a')):
            raise ValueError("Unsupported image format")
        
        return True
    
    async def batch_recognize_images(
        self, 
        images: List[bytes],
        strategy: str = "balanced",
        language: str = "zh"
    ) -> List[Dict[str, Any]]:
        """批量识别图像"""
        tasks = []
        
        for image_bytes in images:
            image_hash = hashlib.md5(image_bytes).hexdigest()
            task = self.recognize_image_enhanced(
                image_bytes=image_bytes,
                image_hash=image_hash,
                language=language,
                strategy=strategy
            )
            tasks.append(task)
        
        # 并发执行识别任务
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 处理结果，过滤异常
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Batch recognition failed for image {i}: {result}")
                processed_results.append({
                    "success": False,
                    "error": str(result),
                    "confidence": 0.0,
                    "candidates": [],
                    "processing_time": 0.0,
                    "timestamp": datetime.utcnow().isoformat()
                })
            else:
                processed_results.append(result)
        
        return processed_results
    
    async def get_enhanced_health_status(self) -> Dict[str, Any]:
        """获取增强的健康状态检查"""
        health_status = {
            "healthy": True,
            "issues": [],
            "timestamp": datetime.utcnow().isoformat(),
            "adapters": {},
            "image_processor": {"status": "unknown"},
            "model_selector": {"status": "unknown"},
            "monitoring": {"status": "unknown"}
        }
        
        try:
            # 检查AI适配器健康状态
            for provider, adapter in self._adapters.items():
                try:
                    adapter_health = await adapter.health_check()
                    health_status["adapters"][provider] = {
                        "status": "healthy" if adapter_health else "unhealthy",
                        "available": adapter_health
                    }
                    if not adapter_health:
                        health_status["healthy"] = False
                        health_status["issues"].append(f"Adapter {provider} is unhealthy")
                except Exception as e:
                    health_status["adapters"][provider] = {
                        "status": "error",
                        "error": str(e)
                    }
                    health_status["healthy"] = False
                    health_status["issues"].append(f"Adapter {provider} health check failed: {str(e)}")
            
            # 检查图像处理器
            try:
                # 创建一个小的测试图像
                test_img = Image.new('RGB', (50, 50), color='red')
                buf = io.BytesIO()
                test_img.save(buf, format='JPEG')
                test_bytes = buf.getvalue()
                
                await self.image_processor.process_image(test_bytes)
                health_status["image_processor"]["status"] = "healthy"
            except Exception as e:
                health_status["image_processor"] = {
                    "status": "error",
                    "error": str(e)
                }
                health_status["healthy"] = False
                health_status["issues"].append(f"Image processor error: {str(e)}")
            
            # 检查模型选择器
            try:
                await self.model_selector.select_best_model()
                health_status["model_selector"]["status"] = "healthy"
            except Exception as e:
                health_status["model_selector"] = {
                    "status": "error", 
                    "error": str(e)
                }
                health_status["healthy"] = False
                health_status["issues"].append(f"Model selector error: {str(e)}")
            
            # 检查监控系统
            try:
                monitor_health = self.ai_monitor.get_health_status()
                health_status["monitoring"] = {
                    "status": "healthy" if monitor_health.get("healthy", False) else "degraded",
                    "details": monitor_health
                }
                if not monitor_health.get("healthy", False):
                    health_status["issues"].extend(monitor_health.get("issues", []))
            except Exception as e:
                health_status["monitoring"] = {
                    "status": "error",
                    "error": str(e)
                }
                health_status["issues"].append(f"Monitoring system error: {str(e)}")
            
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            health_status["healthy"] = False
            health_status["issues"].append(f"Health check system error: {str(e)}")
        
        return health_status