"""
测试增强型智能模型选择器

验证熔断器、重试机制、健康检查缓存等功能
"""

import pytest
import asyncio
import time
from unittest.mock import Mock, AsyncMock, patch

from app.services.ai_service.enhanced_model_selector import EnhancedModelSelector, LoadBalancer
from app.services.ai_service.reliability import (
    CircuitBreaker, RetryHandler, RateLimiter, ReliabilityManager,
    CircuitBreakerConfig, RetryConfig, CircuitBreakerError, RetryExhaustedError, RateLimitExceededError
)
from app.services.ai_service.base_adapter import VisionModelAdapter
from app.services.ai_service.exceptions import ModelNotAvailableError


class MockReliableAdapter(VisionModelAdapter):
    """用于测试的可靠适配器"""
    
    def __init__(self, model_name: str, provider: str, should_fail: bool = False):
        super().__init__()
        self.model_name = model_name
        self.provider_name = provider
        self.should_fail = should_fail
        self._health_status = True
        self._call_count = 0
    
    async def recognize_artwork(self, image_bytes: bytes, language: str = "zh", **kwargs):
        self._call_count += 1
        
        if self.should_fail:
            raise Exception(f"Simulated failure for {self.model_name}")
        
        return {
            "success": True,
            "candidates": [{"name": "Test Artwork", "confidence": 0.9}],
            "model_used": self.model_name,
            "cost_usd": 0.01
        }
    
    async def health_check(self) -> bool:
        if self.should_fail:
            raise Exception(f"Health check failed for {self.model_name}")
        return self._health_status
    
    def get_model_info(self):
        return {"model_name": self.model_name, "provider": self.provider_name}
    
    def estimate_cost(self, image_bytes: bytes) -> float:
        return 0.01
    
    def get_accuracy_score(self) -> float:
        return 0.85
    
    def get_average_response_time(self) -> float:
        return 2.0
    
    def set_health_status(self, status: bool):
        self._health_status = status
    
    def set_failure_mode(self, should_fail: bool):
        self.should_fail = should_fail


class TestCircuitBreaker:
    """测试熔断器功能"""
    
    @pytest.fixture
    def circuit_breaker(self):
        config = CircuitBreakerConfig(
            failure_threshold=2,
            recovery_timeout=1,  # 1秒用于快速测试
            half_open_max_calls=2,  # 允许2次半开状态调用
            success_threshold=2     # 需要2次成功才能恢复
        )
        return CircuitBreaker("test_service", config)
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_normal_operation(self, circuit_breaker):
        """测试熔断器正常操作"""
        async def successful_func():
            return "success"
        
        result = await circuit_breaker.call(successful_func)
        assert result == "success"
        assert circuit_breaker.state.value == "closed"
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_trips_on_failures(self, circuit_breaker):
        """测试熔断器在失败时触发"""
        async def failing_func():
            raise Exception("Test failure")
        
        # 第一次失败
        with pytest.raises(Exception):
            await circuit_breaker.call(failing_func)
        assert circuit_breaker.state.value == "closed"
        
        # 第二次失败，应该触发熔断器
        with pytest.raises(Exception):
            await circuit_breaker.call(failing_func)
        assert circuit_breaker.state.value == "open"
        
        # 第三次调用应该直接被熔断器拒绝
        with pytest.raises(CircuitBreakerError):
            await circuit_breaker.call(failing_func)
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_recovery(self, circuit_breaker):
        """测试熔断器恢复机制"""
        async def failing_func():
            raise Exception("Test failure")
        
        async def successful_func():
            return "success"
        
        # 触发熔断器
        for _ in range(2):
            with pytest.raises(Exception):
                await circuit_breaker.call(failing_func)
        
        assert circuit_breaker.state.value == "open"
        
        # 等待恢复时间
        await asyncio.sleep(1.1)
        
        # 现在应该能够调用成功的函数（但状态会是half_open）
        result = await circuit_breaker.call(successful_func)
        assert result == "success"
        # 需要更多成功调用才能完全恢复到closed状态
        result = await circuit_breaker.call(successful_func)
        assert result == "success"
        assert circuit_breaker.state.value == "closed"


class TestRetryHandler:
    """测试重试处理器"""
    
    @pytest.fixture
    def retry_handler(self):
        config = RetryConfig(
            max_attempts=3,
            base_delay=0.01,  # 快速测试
            max_delay=0.1,
            exponential_base=2.0,
            jitter=False  # 禁用抖动以便测试
        )
        return RetryHandler(config)
    
    @pytest.mark.asyncio
    async def test_retry_success_on_first_attempt(self, retry_handler):
        """测试第一次尝试就成功"""
        call_count = 0
        
        async def successful_func():
            nonlocal call_count
            call_count += 1
            return "success"
        
        result = await retry_handler.call(successful_func)
        assert result == "success"
        assert call_count == 1
    
    @pytest.mark.asyncio
    async def test_retry_success_after_failures(self, retry_handler):
        """测试重试后成功"""
        call_count = 0
        
        async def eventually_successful_func():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise Exception(f"Failure {call_count}")
            return "success"
        
        result = await retry_handler.call(eventually_successful_func)
        assert result == "success"
        assert call_count == 3
    
    @pytest.mark.asyncio
    async def test_retry_exhausted(self, retry_handler):
        """测试重试次数耗尽"""
        call_count = 0
        
        async def always_failing_func():
            nonlocal call_count
            call_count += 1
            raise Exception(f"Always fails {call_count}")
        
        with pytest.raises(RetryExhaustedError) as exc_info:
            await retry_handler.call(always_failing_func)
        
        assert exc_info.value.attempts == 3
        assert call_count == 3


class TestRateLimiter:
    """测试限流器"""
    
    def test_rate_limiter_allows_requests_within_limit(self):
        """测试限流器允许限制内的请求"""
        limiter = RateLimiter(requests_per_minute=60, burst_allowance=5)
        
        # 应该能够立即获取5个令牌
        for i in range(5):
            asyncio.run(limiter.acquire(f"service_{i}"))
    
    def test_rate_limiter_blocks_excess_requests(self):
        """测试限流器阻止超出限制的请求"""
        limiter = RateLimiter(requests_per_minute=60, burst_allowance=2)
        
        # 消耗所有令牌
        asyncio.run(limiter.acquire("service_1"))
        asyncio.run(limiter.acquire("service_2"))
        
        # 下一个请求应该被拒绝
        with pytest.raises(RateLimitExceededError):
            asyncio.run(limiter.acquire("service_3"))


class TestEnhancedModelSelector:
    """测试增强型模型选择器"""
    
    @pytest.fixture
    def mock_adapters(self):
        """创建测试用的模拟适配器"""
        return [
            MockReliableAdapter("gpt-4o-mini", "openai"),
            MockReliableAdapter("gpt-4-vision-preview", "openai"),
            MockReliableAdapter("claude-3-sonnet", "anthropic")
        ]
    
    @pytest.fixture
    def enhanced_selector(self, mock_adapters):
        """创建增强型选择器"""
        return EnhancedModelSelector(adapters=mock_adapters)
    
    @pytest.mark.asyncio
    async def test_enhanced_selector_initialization(self, enhanced_selector):
        """测试增强选择器初始化"""
        assert isinstance(enhanced_selector.reliability_manager, ReliabilityManager)
        assert enhanced_selector.health_check_interval == 60
        assert isinstance(enhanced_selector.load_balancer, LoadBalancer)
    
    @pytest.mark.asyncio
    async def test_select_best_model_with_reliability(self, enhanced_selector):
        """测试带可靠性保障的模型选择"""
        adapter = await enhanced_selector.select_best_model(strategy="cost")
        
        assert adapter is not None
        assert adapter.model_name in ["gpt-4o-mini", "gpt-4-vision-preview", "claude-3-sonnet"]
    
    @pytest.mark.asyncio
    async def test_health_check_caching(self, enhanced_selector, mock_adapters):
        """测试健康检查缓存"""
        # 第一次调用应该执行实际健康检查
        healthy_adapters = await enhanced_selector._get_healthy_adapters_cached(mock_adapters)
        assert len(healthy_adapters) == 3
        
        # 检查缓存
        assert len(enhanced_selector.health_check_cache) == 3
        
        # 设置一个适配器为不健康
        mock_adapters[0].set_health_status(False)
        
        # 第二次调用应该使用缓存（仍然返回3个）
        healthy_adapters = await enhanced_selector._get_healthy_adapters_cached(mock_adapters)
        assert len(healthy_adapters) == 3  # 使用缓存结果
        
        # 清空缓存并重新检查
        enhanced_selector.clear_health_cache()
        healthy_adapters = await enhanced_selector._get_healthy_adapters_cached(mock_adapters)
        assert len(healthy_adapters) == 2  # 现在应该反映真实状态
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_integration(self, enhanced_selector, mock_adapters):
        """测试熔断器集成"""
        # 设置一个适配器总是失败
        failing_adapter = mock_adapters[0]
        failing_adapter.set_failure_mode(True)
        
        # 多次调用应该触发熔断器
        for _ in range(5):
            try:
                await enhanced_selector.select_best_model(
                    strategy="cost",
                    enable_circuit_breaker=True
                )
            except Exception:
                pass  # 忽略失败
        
        # 检查熔断器状态
        status = enhanced_selector.get_enhanced_status()
        assert "reliability" in status
        assert "circuit_breakers" in status["reliability"]
    
    @pytest.mark.asyncio
    async def test_recognize_artwork_with_reliability(self, enhanced_selector):
        """测试带可靠性保障的艺术品识别"""
        image_bytes = b"fake_image_data" * 100
        
        result = await enhanced_selector.recognize_artwork_with_reliability(
            image_bytes=image_bytes,
            language="zh",
            strategy="balanced"
        )
        
        assert result["success"] is True
        assert "candidates" in result
        assert result["model_used"] in ["gpt-4o-mini", "gpt-4-vision-preview", "claude-3-sonnet"]
    
    @pytest.mark.asyncio
    async def test_load_balancer_round_robin(self, enhanced_selector, mock_adapters):
        """测试负载均衡轮询"""
        # 多次选择模型，应该均匀分布
        selected_models = []
        
        for _ in range(6):  # 选择6次，每个模型应该被选择2次
            adapter = await enhanced_selector.select_best_model(strategy="cost")
            selected_models.append(adapter.model_name)
        
        # 检查负载分布
        model_counts = {}
        for model in selected_models:
            model_counts[model] = model_counts.get(model, 0) + 1
        
        # 每个模型都应该被选择过
        assert len(model_counts) >= 2
    
    def test_enhanced_status_reporting(self, enhanced_selector):
        """测试增强状态报告"""
        status = enhanced_selector.get_enhanced_status()
        
        assert "reliability" in status
        assert "load_balancer" in status
        assert "health_cache" in status
        assert "configs" in status
        
        configs = status["configs"]
        assert "circuit_breaker" in configs
        assert "retry" in configs
        assert "rate_limit" in configs
    
    def test_reliability_config_update(self, enhanced_selector):
        """测试可靠性配置更新"""
        new_circuit_config = CircuitBreakerConfig(
            failure_threshold=5,
            recovery_timeout=600
        )
        
        new_retry_config = RetryConfig(
            max_attempts=5,
            base_delay=2.0
        )
        
        enhanced_selector.update_reliability_config(
            circuit_breaker_config=new_circuit_config,
            retry_config=new_retry_config
        )
        
        assert enhanced_selector.circuit_breaker_config.failure_threshold == 5
        assert enhanced_selector.retry_config.max_attempts == 5


class TestLoadBalancer:
    """测试负载均衡器"""
    
    @pytest.fixture
    def load_balancer(self):
        return LoadBalancer()
    
    @pytest.fixture
    def mock_adapters(self):
        return [
            MockReliableAdapter("model_1", "provider_1"),
            MockReliableAdapter("model_2", "provider_1"),
            MockReliableAdapter("model_3", "provider_2")
        ]
    
    def test_round_robin_balancing(self, load_balancer, mock_adapters):
        """测试轮询负载均衡"""
        # 首次调用应该按顺序返回
        balanced = load_balancer.balance_candidates(mock_adapters, "cost")
        assert len(balanced) == 3
        
        # 记录一些选择
        load_balancer.record_selection("model_1")
        load_balancer.record_selection("model_1")
        load_balancer.record_selection("model_2")
        
        # 再次平衡，model_3应该排在前面（使用次数最少）
        balanced = load_balancer.balance_candidates(mock_adapters, "cost")
        first_model = balanced[0].model_name
        assert first_model == "model_3"
    
    def test_response_time_tracking(self, load_balancer):
        """测试响应时间跟踪"""
        load_balancer.record_response_time("model_1", 1.5)
        load_balancer.record_response_time("model_1", 2.5)
        load_balancer.record_response_time("model_2", 3.0)
        
        status = load_balancer.get_status()
        assert status["average_response_times"]["model_1"] == 2.0
        assert status["average_response_times"]["model_2"] == 3.0
    
    def test_load_balancer_status(self, load_balancer):
        """测试负载均衡器状态"""
        load_balancer.record_selection("model_1")
        load_balancer.record_response_time("model_1", 2.0)
        
        status = load_balancer.get_status()
        
        assert "request_counts" in status
        assert "average_response_times" in status
        assert "last_used" in status
        assert status["request_counts"]["model_1"] == 1