"""
AI服务可靠性组件

提供熔断器、重试机制、限流器等企业级可靠性保障
"""

import time
import asyncio
import logging
from typing import Any, Callable, Dict, Optional
from enum import Enum
from dataclasses import dataclass, field
from collections import defaultdict
import random

from .exceptions import AIServiceError

logger = logging.getLogger(__name__)


class CircuitBreakerState(Enum):
    """熔断器状态"""
    CLOSED = "closed"      # 正常状态
    OPEN = "open"          # 熔断开启
    HALF_OPEN = "half_open"  # 半开状态


@dataclass
class CircuitBreakerConfig:
    """熔断器配置"""
    failure_threshold: int = 5      # 失败阈值
    recovery_timeout: int = 60      # 恢复超时时间(秒)
    half_open_max_calls: int = 3    # 半开状态最大调用次数
    success_threshold: int = 2      # 半开状态成功阈值


class CircuitBreakerError(AIServiceError):
    """熔断器开启错误"""
    
    def __init__(self, service_name: str, failure_count: int):
        super().__init__(
            message=f"Circuit breaker open for {service_name} (failures: {failure_count})",
            error_code="CIRCUIT_BREAKER_OPEN",
            details={"service_name": service_name, "failure_count": failure_count}
        )
        self.service_name = service_name
        self.failure_count = failure_count


class RetryExhaustedError(AIServiceError):
    """重试次数耗尽错误"""
    
    def __init__(self, attempts: int, last_error: str):
        super().__init__(
            message=f"Retry exhausted after {attempts} attempts: {last_error}",
            error_code="RETRY_EXHAUSTED",
            details={"attempts": attempts, "last_error": last_error}
        )
        self.attempts = attempts
        self.last_error = last_error


class RateLimitExceededError(AIServiceError):
    """限流超出错误"""
    
    def __init__(self, service_name: str, rate_limit: int):
        super().__init__(
            message=f"Rate limit exceeded for {service_name} (limit: {rate_limit}/min)",
            error_code="RATE_LIMIT_EXCEEDED",
            details={"service_name": service_name, "rate_limit": rate_limit}
        )
        self.service_name = service_name
        self.rate_limit = rate_limit


class CircuitBreaker:
    """
    熔断器实现
    
    提供故障快速响应和自动恢复机制
    """
    
    def __init__(self, name: str, config: CircuitBreakerConfig = None):
        self.name = name
        self.config = config or CircuitBreakerConfig()
        
        self.state = CircuitBreakerState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time = None
        self.half_open_calls = 0
        
        logger.info(f"Circuit breaker '{name}' initialized: {self.config}")
    
    async def call(self, func: Callable, *args, **kwargs) -> Any:
        """
        通过熔断器调用函数
        
        Args:
            func: 要调用的函数
            *args, **kwargs: 函数参数
            
        Returns:
            函数执行结果
            
        Raises:
            CircuitBreakerError: 熔断器开启时
        """
        if self.state == CircuitBreakerState.OPEN:
            if self._should_attempt_reset():
                self._transition_to_half_open()
            else:
                raise CircuitBreakerError(self.name, self.failure_count)
        
        if self.state == CircuitBreakerState.HALF_OPEN:
            if self.half_open_calls >= self.config.half_open_max_calls:
                raise CircuitBreakerError(self.name, self.failure_count)
        
        try:
            if self.state == CircuitBreakerState.HALF_OPEN:
                self.half_open_calls += 1
            
            result = await func(*args, **kwargs)
            self._on_success()
            return result
            
        except Exception as e:
            self._on_failure()
            raise
    
    def _should_attempt_reset(self) -> bool:
        """检查是否应该尝试重置熔断器"""
        if self.last_failure_time is None:
            return False
        
        return (time.time() - self.last_failure_time) >= self.config.recovery_timeout
    
    def _transition_to_half_open(self):
        """转换到半开状态"""
        self.state = CircuitBreakerState.HALF_OPEN
        self.half_open_calls = 0
        self.success_count = 0
        logger.info(f"Circuit breaker '{self.name}' transitioned to HALF_OPEN")
    
    def _on_success(self):
        """处理成功调用"""
        if self.state == CircuitBreakerState.HALF_OPEN:
            self.success_count += 1
            if self.success_count >= self.config.success_threshold:
                self._reset()
        elif self.state == CircuitBreakerState.CLOSED:
            self.failure_count = 0
    
    def _on_failure(self):
        """处理失败调用"""
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        if self.state == CircuitBreakerState.HALF_OPEN:
            self._trip()
        elif (self.state == CircuitBreakerState.CLOSED and 
              self.failure_count >= self.config.failure_threshold):
            self._trip()
    
    def _reset(self):
        """重置熔断器到正常状态"""
        self.state = CircuitBreakerState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.half_open_calls = 0
        logger.info(f"Circuit breaker '{self.name}' reset to CLOSED")
    
    def _trip(self):
        """触发熔断器"""
        self.state = CircuitBreakerState.OPEN
        self.half_open_calls = 0
        logger.warning(f"Circuit breaker '{self.name}' tripped to OPEN after {self.failure_count} failures")
    
    def get_state(self) -> Dict[str, Any]:
        """获取熔断器状态信息"""
        return {
            "name": self.name,
            "state": self.state.value,
            "failure_count": self.failure_count,
            "success_count": self.success_count,
            "half_open_calls": self.half_open_calls,
            "last_failure_time": self.last_failure_time,
            "config": {
                "failure_threshold": self.config.failure_threshold,
                "recovery_timeout": self.config.recovery_timeout,
                "half_open_max_calls": self.config.half_open_max_calls,
                "success_threshold": self.config.success_threshold
            }
        }


@dataclass
class RetryConfig:
    """重试配置"""
    max_attempts: int = 3           # 最大重试次数
    base_delay: float = 1.0         # 基础延迟(秒)
    max_delay: float = 30.0         # 最大延迟(秒)
    exponential_base: float = 2.0   # 指数退避基数
    jitter: bool = True             # 是否添加抖动
    retryable_exceptions: tuple = (Exception,)  # 可重试的异常类型


class RetryHandler:
    """
    重试处理器
    
    提供指数退避和抖动机制
    """
    
    def __init__(self, config: RetryConfig = None):
        self.config = config or RetryConfig()
    
    async def call(self, func: Callable, *args, **kwargs) -> Any:
        """
        带重试的函数调用
        
        Args:
            func: 要调用的函数
            *args, **kwargs: 函数参数
            
        Returns:
            函数执行结果
            
        Raises:
            RetryExhaustedError: 重试次数耗尽
        """
        last_exception = None
        
        for attempt in range(self.config.max_attempts):
            try:
                result = await func(*args, **kwargs)
                if attempt > 0:
                    logger.info(f"Function succeeded on attempt {attempt + 1}")
                return result
                
            except Exception as e:
                last_exception = e
                
                # 检查是否为可重试异常
                if not isinstance(e, self.config.retryable_exceptions):
                    logger.debug(f"Non-retryable exception: {type(e).__name__}")
                    raise
                
                # 最后一次尝试失败
                if attempt == self.config.max_attempts - 1:
                    break
                
                # 计算延迟时间
                delay = self._calculate_delay(attempt)
                logger.warning(f"Attempt {attempt + 1} failed: {e}. Retrying in {delay:.2f}s")
                
                await asyncio.sleep(delay)
        
        # 所有重试都失败了
        raise RetryExhaustedError(
            attempts=self.config.max_attempts,
            last_error=str(last_exception)
        )
    
    def _calculate_delay(self, attempt: int) -> float:
        """计算重试延迟时间"""
        # 指数退避
        delay = self.config.base_delay * (self.config.exponential_base ** attempt)
        
        # 限制最大延迟
        delay = min(delay, self.config.max_delay)
        
        # 添加抖动避免惊群效应
        if self.config.jitter:
            jitter_range = delay * 0.1  # 10%的抖动
            jitter = random.uniform(-jitter_range, jitter_range)
            delay += jitter
        
        return max(0, delay)


class RateLimiter:
    """
    令牌桶限流器
    
    控制API调用频率
    """
    
    def __init__(self, requests_per_minute: int = 60, burst_allowance: int = 10):
        self.requests_per_minute = requests_per_minute
        self.burst_allowance = burst_allowance
        
        # 令牌桶参数
        self.tokens = float(burst_allowance)
        self.last_update = time.time()
        self.token_rate = requests_per_minute / 60.0  # 每秒添加的令牌数
    
    async def acquire(self, service_name: str = "unknown") -> bool:
        """
        获取令牌
        
        Args:
            service_name: 服务名称
            
        Returns:
            bool: 是否成功获取令牌
            
        Raises:
            RateLimitExceededError: 限流超出
        """
        current_time = time.time()
        
        # 更新令牌桶
        time_passed = current_time - self.last_update
        self.tokens += time_passed * self.token_rate
        self.tokens = min(self.tokens, self.burst_allowance)  # 不能超过桶容量
        self.last_update = current_time
        
        # 检查是否有令牌可用
        if self.tokens >= 1.0:
            self.tokens -= 1.0
            return True
        else:
            raise RateLimitExceededError(service_name, self.requests_per_minute)
    
    def get_status(self) -> Dict[str, Any]:
        """获取限流器状态"""
        return {
            "requests_per_minute": self.requests_per_minute,
            "burst_allowance": self.burst_allowance,
            "available_tokens": int(self.tokens),
            "token_rate": self.token_rate
        }


class ReliabilityManager:
    """
    可靠性管理器
    
    统一管理熔断器、重试和限流
    """
    
    def __init__(self):
        self.circuit_breakers: Dict[str, CircuitBreaker] = {}
        self.rate_limiters: Dict[str, RateLimiter] = {}
        self.retry_handler = RetryHandler()
    
    def get_circuit_breaker(self, name: str, config: CircuitBreakerConfig = None) -> CircuitBreaker:
        """获取或创建熔断器"""
        if name not in self.circuit_breakers:
            self.circuit_breakers[name] = CircuitBreaker(name, config)
        return self.circuit_breakers[name]
    
    def get_rate_limiter(self, name: str, requests_per_minute: int = 60, 
                        burst_allowance: int = 10) -> RateLimiter:
        """获取或创建限流器"""
        if name not in self.rate_limiters:
            self.rate_limiters[name] = RateLimiter(requests_per_minute, burst_allowance)
        return self.rate_limiters[name]
    
    async def call_with_reliability(
        self, 
        func: Callable,
        service_name: str,
        circuit_breaker_config: CircuitBreakerConfig = None,
        retry_config: RetryConfig = None,
        rate_limit_config: Dict[str, int] = None,
        *args, 
        **kwargs
    ) -> Any:
        """
        带可靠性保障的函数调用
        
        Args:
            func: 要调用的函数
            service_name: 服务名称
            circuit_breaker_config: 熔断器配置
            retry_config: 重试配置
            rate_limit_config: 限流配置 {"requests_per_minute": 60, "burst_allowance": 10}
            *args, **kwargs: 函数参数
            
        Returns:
            函数执行结果
        """
        # 应用限流
        if rate_limit_config:
            rate_limiter = self.get_rate_limiter(
                service_name, 
                rate_limit_config.get("requests_per_minute", 60),
                rate_limit_config.get("burst_allowance", 10)
            )
            await rate_limiter.acquire(service_name)
        
        # 获取熔断器
        circuit_breaker = self.get_circuit_breaker(service_name, circuit_breaker_config)
        
        # 配置重试处理器
        if retry_config:
            retry_handler = RetryHandler(retry_config)
        else:
            retry_handler = self.retry_handler
        
        # 定义包装函数
        async def wrapped_func():
            return await circuit_breaker.call(func, *args, **kwargs)
        
        # 执行带重试的调用
        return await retry_handler.call(wrapped_func)
    
    def get_status(self) -> Dict[str, Any]:
        """获取所有组件状态"""
        return {
            "circuit_breakers": {
                name: breaker.get_state() 
                for name, breaker in self.circuit_breakers.items()
            },
            "rate_limiters": {
                name: limiter.get_status()
                for name, limiter in self.rate_limiters.items()
            }
        }


# 全局实例
reliability_manager = ReliabilityManager()