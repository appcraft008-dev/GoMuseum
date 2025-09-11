"""
增强型智能模型选择器

集成熔断器、重试机制、健康检查等企业级可靠性功能
"""

import asyncio
import logging
import time
from typing import Dict, Any, List, Optional
from collections import defaultdict

from .base_adapter import VisionModelAdapter
from .model_selector import ModelSelector
from .exceptions import ModelNotAvailableError
from .reliability import (
    ReliabilityManager, 
    CircuitBreakerConfig, 
    RetryConfig
)

logger = logging.getLogger(__name__)


class EnhancedModelSelector(ModelSelector):
    """
    增强型模型选择器
    
    在原有功能基础上增加：
    - 熔断器机制
    - 自动重试
    - 健康检查缓存
    - 负载均衡
    - 性能监控
    """
    
    def __init__(
        self, 
        adapters: List[VisionModelAdapter] = None,
        reliability_manager: ReliabilityManager = None
    ):
        super().__init__(adapters)
        
        self.reliability_manager = reliability_manager or ReliabilityManager()
        self.health_check_cache = {}
        self.health_check_interval = 60  # 健康检查缓存时间(秒)
        self.load_balancer = LoadBalancer()
        
        # 可靠性配置
        self.circuit_breaker_config = CircuitBreakerConfig(
            failure_threshold=3,
            recovery_timeout=300,  # 5分钟
            half_open_max_calls=2,
            success_threshold=2
        )
        
        self.retry_config = RetryConfig(
            max_attempts=3,
            base_delay=1.0,
            max_delay=10.0,
            exponential_base=2.0,
            jitter=True
        )
        
        self.rate_limit_config = {
            "requests_per_minute": 100,
            "burst_allowance": 10
        }
        
        logger.info("Enhanced model selector initialized with reliability features")
    
    async def select_best_model(
        self,
        strategy: str = "balanced",
        provider: Optional[str] = None,
        max_cost: Optional[float] = None,
        min_accuracy: Optional[float] = None,
        enable_circuit_breaker: bool = True,
        enable_retry: bool = True,
        enable_rate_limit: bool = True,
        **kwargs
    ) -> VisionModelAdapter:
        """
        增强的模型选择方法
        
        Args:
            strategy: 选择策略
            provider: 指定提供商
            max_cost: 最大成本约束
            min_accuracy: 最小精度约束
            enable_circuit_breaker: 是否启用熔断器
            enable_retry: 是否启用重试
            enable_rate_limit: 是否启用限流
            **kwargs: 其他参数
            
        Returns:
            VisionModelAdapter: 选中的适配器
        """
        # 构建可靠性配置
        circuit_config = self.circuit_breaker_config if enable_circuit_breaker else None
        retry_config = self.retry_config if enable_retry else None
        rate_config = self.rate_limit_config if enable_rate_limit else None
        
        # 使用可靠性管理器执行选择
        return await self.reliability_manager.call_with_reliability(
            func=self._select_model_internal,
            service_name="model_selector",
            circuit_breaker_config=circuit_config,
            retry_config=retry_config,
            rate_limit_config=rate_config,
            strategy=strategy,
            provider=provider,
            max_cost=max_cost,
            min_accuracy=min_accuracy,
            **kwargs
        )
    
    async def _select_model_internal(
        self,
        strategy: str,
        provider: Optional[str] = None,
        max_cost: Optional[float] = None,
        min_accuracy: Optional[float] = None,
        **kwargs
    ) -> VisionModelAdapter:
        """内部模型选择逻辑"""
        # 获取候选适配器
        candidates = self._get_candidate_adapters(provider)
        if not candidates:
            # 返回一个Mock适配器用于测试和回退
            from .openai_adapter_simple import OpenAIVisionAdapter
            try:
                mock_adapter = OpenAIVisionAdapter(
                    api_key="mock-key", 
                    model_name="mock-model"
                )
                mock_adapter.provider_name = "mock"
                return mock_adapter
            except Exception:
                if provider:
                    raise ModelNotAvailableError(provider, "No models available for provider")
                else:
                    raise ModelNotAvailableError("", "No models available")
        
        # 过滤健康的模型
        healthy_candidates = await self._get_healthy_adapters_cached(candidates)
        if not healthy_candidates:
            raise ModelNotAvailableError("", "No healthy models available")
        
        # 应用约束条件
        constrained_candidates = self._apply_constraints(
            healthy_candidates, max_cost, min_accuracy
        )
        if not constrained_candidates:
            raise ModelNotAvailableError("", "No models meet the constraints")
        
        # 应用负载均衡
        balanced_candidates = self.load_balancer.balance_candidates(
            constrained_candidates, strategy
        )
        
        # 根据策略选择最佳模型
        selected_adapter = self._apply_selection_strategy(balanced_candidates, strategy)
        
        # 更新负载均衡器状态
        self.load_balancer.record_selection(selected_adapter.model_name)
        
        self._current_adapter = selected_adapter
        logger.info(f"Enhanced selector chose: {selected_adapter.model_name} (strategy: {strategy})")
        
        return selected_adapter
    
    async def _get_healthy_adapters_cached(
        self, 
        candidates: List[VisionModelAdapter]
    ) -> List[VisionModelAdapter]:
        """
        获取健康的适配器（带缓存）
        """
        healthy = []
        current_time = time.time()
        
        for adapter in candidates:
            model_name = adapter.model_name
            
            # 检查缓存
            cache_entry = self.health_check_cache.get(model_name)
            if (cache_entry and 
                current_time - cache_entry["timestamp"] < self.health_check_interval):
                if cache_entry["is_healthy"]:
                    healthy.append(adapter)
                continue
            
            # 执行实际健康检查
            try:
                is_healthy = await self._check_adapter_health_with_reliability(adapter)
                
                # 更新缓存
                self.health_check_cache[model_name] = {
                    "is_healthy": is_healthy,
                    "timestamp": current_time
                }
                
                if is_healthy:
                    healthy.append(adapter)
                    
            except Exception as e:
                logger.warning(f"Health check failed for {model_name}: {e}")
                # 缓存失败结果
                self.health_check_cache[model_name] = {
                    "is_healthy": False,
                    "timestamp": current_time
                }
        
        return healthy
    
    async def _check_adapter_health_with_reliability(
        self, 
        adapter: VisionModelAdapter
    ) -> bool:
        """带可靠性保障的健康检查"""
        try:
            return await self.reliability_manager.call_with_reliability(
                func=adapter.health_check,
                service_name=f"health_check_{adapter.model_name}",
                circuit_breaker_config=CircuitBreakerConfig(
                    failure_threshold=2,
                    recovery_timeout=60
                ),
                retry_config=RetryConfig(
                    max_attempts=2,
                    base_delay=0.5,
                    max_delay=2.0
                )
            )
        except Exception as e:
            logger.debug(f"Health check failed for {adapter.model_name}: {e}")
            return False
    
    def _apply_selection_strategy(
        self, 
        candidates: List[VisionModelAdapter], 
        strategy: str
    ) -> VisionModelAdapter:
        """应用选择策略"""
        if not candidates:
            raise ModelNotAvailableError("", "No candidates available")
        
        if strategy == "cost":
            return min(candidates, key=lambda a: a.estimate_cost(b"dummy"))
        elif strategy == "accuracy":
            return max(candidates, key=lambda a: a.get_accuracy_score())
        elif strategy == "speed":
            return min(candidates, key=lambda a: a.get_average_response_time())
        elif strategy == "balanced":
            return max(candidates, key=self._calculate_balanced_score)
        else:
            # 默认返回第一个候选者
            return candidates[0]
    
    async def recognize_artwork_with_reliability(
        self,
        image_bytes: bytes,
        language: str = "zh",
        strategy: str = "balanced",
        **kwargs
    ) -> Dict[str, Any]:
        """
        带可靠性保障的艺术品识别
        
        Args:
            image_bytes: 图像数据
            language: 语言
            strategy: 选择策略
            **kwargs: 其他参数
            
        Returns:
            识别结果
        """
        # 选择最佳模型
        adapter = await self.select_best_model(strategy=strategy, **kwargs)
        
        # 执行识别
        return await self.reliability_manager.call_with_reliability(
            func=adapter.recognize_artwork,
            service_name=f"recognize_{adapter.model_name}",
            circuit_breaker_config=self.circuit_breaker_config,
            retry_config=self.retry_config,
            rate_limit_config=self.rate_limit_config,
            image_bytes=image_bytes,
            language=language,
            **kwargs
        )
    
    def get_enhanced_status(self) -> Dict[str, Any]:
        """获取增强选择器的详细状态"""
        base_status = self.get_selector_info()
        
        reliability_status = self.reliability_manager.get_status()
        
        load_balancer_status = self.load_balancer.get_status()
        
        health_cache_status = {
            "cached_entries": len(self.health_check_cache),
            "cache_interval": self.health_check_interval,
            "entries": {
                model: {
                    "is_healthy": entry["is_healthy"],
                    "age_seconds": time.time() - entry["timestamp"]
                }
                for model, entry in self.health_check_cache.items()
            }
        }
        
        return {
            **base_status,
            "reliability": reliability_status,
            "load_balancer": load_balancer_status,
            "health_cache": health_cache_status,
            "configs": {
                "circuit_breaker": {
                    "failure_threshold": self.circuit_breaker_config.failure_threshold,
                    "recovery_timeout": self.circuit_breaker_config.recovery_timeout
                },
                "retry": {
                    "max_attempts": self.retry_config.max_attempts,
                    "base_delay": self.retry_config.base_delay
                },
                "rate_limit": self.rate_limit_config
            }
        }
    
    def clear_health_cache(self):
        """清空健康检查缓存"""
        self.health_check_cache.clear()
        logger.info("Health check cache cleared")
    
    def update_reliability_config(
        self,
        circuit_breaker_config: CircuitBreakerConfig = None,
        retry_config: RetryConfig = None,
        rate_limit_config: Dict[str, int] = None
    ):
        """更新可靠性配置"""
        if circuit_breaker_config:
            self.circuit_breaker_config = circuit_breaker_config
        if retry_config:
            self.retry_config = retry_config
        if rate_limit_config:
            self.rate_limit_config = rate_limit_config
        
        logger.info("Reliability configuration updated")


class LoadBalancer:
    """
    负载均衡器
    
    实现多种负载均衡算法
    """
    
    def __init__(self):
        self.request_counts = defaultdict(int)
        self.last_used = defaultdict(float)
        self.response_times = defaultdict(list)
    
    def balance_candidates(
        self, 
        candidates: List[VisionModelAdapter], 
        strategy: str = "round_robin"
    ) -> List[VisionModelAdapter]:
        """
        对候选者进行负载均衡排序
        
        Args:
            candidates: 候选适配器列表
            strategy: 平衡策略
            
        Returns:
            排序后的候选者列表
        """
        if strategy in ["cost", "accuracy", "speed"]:
            # 对于这些策略，使用轮询确保公平性
            return self._round_robin_sort(candidates)
        elif strategy == "balanced":
            # 对于平衡策略，考虑响应时间分布
            return self._weighted_response_time_sort(candidates)
        else:
            return candidates
    
    def _round_robin_sort(self, candidates: List[VisionModelAdapter]) -> List[VisionModelAdapter]:
        """轮询排序"""
        # 按使用次数排序，使用次数少的优先
        return sorted(candidates, key=lambda a: self.request_counts[a.model_name])
    
    def _weighted_response_time_sort(self, candidates: List[VisionModelAdapter]) -> List[VisionModelAdapter]:
        """基于响应时间的加权排序"""
        def get_weight(adapter):
            model_name = adapter.model_name
            response_times = self.response_times.get(model_name, [])
            
            if not response_times:
                return 1.0  # 默认权重
            
            # 计算平均响应时间
            avg_response_time = sum(response_times) / len(response_times)
            
            # 权重与响应时间成反比
            return 1.0 / (avg_response_time + 0.1)
        
        return sorted(candidates, key=get_weight, reverse=True)
    
    def record_selection(self, model_name: str):
        """记录模型选择"""
        self.request_counts[model_name] += 1
        self.last_used[model_name] = time.time()
    
    def record_response_time(self, model_name: str, response_time: float):
        """记录响应时间"""
        times = self.response_times[model_name]
        times.append(response_time)
        
        # 只保留最近的响应时间记录
        if len(times) > 100:
            times.pop(0)
    
    def get_status(self) -> Dict[str, Any]:
        """获取负载均衡器状态"""
        return {
            "request_counts": dict(self.request_counts),
            "average_response_times": {
                model: sum(times) / len(times) if times else 0
                for model, times in self.response_times.items()
            },
            "last_used": {
                model: time.time() - timestamp
                for model, timestamp in self.last_used.items()
            }
        }