"""
AI服务监控系统

提供Prometheus指标收集、结构化日志和性能监控
"""

import time
import logging
from typing import Dict, Any, Optional, List
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import json
import threading
from functools import wraps

try:
    from prometheus_client import Counter, Histogram, Gauge, Info, start_http_server
    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False
    # 创建空的度量类
    class Counter:
        def __init__(self, *args, **kwargs): pass
        def inc(self, *args, **kwargs): pass
        def labels(self, *args, **kwargs): return self
    
    class Histogram:
        def __init__(self, *args, **kwargs): pass
        def time(self): return self
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def observe(self, *args, **kwargs): pass
        def labels(self, *args, **kwargs): return self
    
    class Gauge:
        def __init__(self, *args, **kwargs): pass
        def set(self, *args, **kwargs): pass
        def inc(self, *args, **kwargs): pass
        def dec(self, *args, **kwargs): pass
        def labels(self, *args, **kwargs): return self
    
    class Info:
        def __init__(self, *args, **kwargs): pass
        def info(self, *args, **kwargs): pass


@dataclass
class MetricSnapshot:
    """指标快照"""
    timestamp: datetime
    requests_total: int
    requests_failed: int
    avg_response_time: float
    active_models: int
    circuit_breaker_trips: int
    cache_hits: int
    cache_misses: int


@dataclass
class PerformanceStats:
    """性能统计"""
    model_name: str
    request_count: int = 0
    total_response_time: float = 0.0
    error_count: int = 0
    success_count: int = 0
    last_request_time: Optional[datetime] = None
    recent_response_times: deque = field(default_factory=lambda: deque(maxlen=100))
    
    @property
    def avg_response_time(self) -> float:
        """平均响应时间"""
        return self.total_response_time / max(1, self.request_count)
    
    @property
    def success_rate(self) -> float:
        """成功率"""
        total = self.success_count + self.error_count
        return self.success_count / max(1, total)
    
    @property
    def recent_avg_response_time(self) -> float:
        """最近100次请求的平均响应时间"""
        if not self.recent_response_times:
            return 0.0
        return sum(self.recent_response_times) / len(self.recent_response_times)


class StructuredLogger:
    """结构化日志器"""
    
    def __init__(self, name: str = "ai_service"):
        self.logger = logging.getLogger(name)
        self._setup_formatter()
    
    def _setup_formatter(self):
        """设置JSON格式化器"""
        formatter = logging.Formatter(
            '{"timestamp": "%(asctime)s", "level": "%(levelname)s", '
            '"logger": "%(name)s", "message": "%(message)s"}'
        )
        
        # 确保有handler
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
            self.logger.setLevel(logging.INFO)
    
    def log_request(self, model_name: str, request_id: str, **kwargs):
        """记录请求日志"""
        log_data = {
            "event": "ai_request",
            "model_name": model_name,
            "request_id": request_id,
            **kwargs
        }
        self.logger.info(json.dumps(log_data))
    
    def log_response(self, model_name: str, request_id: str, 
                    response_time: float, success: bool, **kwargs):
        """记录响应日志"""
        log_data = {
            "event": "ai_response",
            "model_name": model_name,
            "request_id": request_id,
            "response_time": response_time,
            "success": success,
            **kwargs
        }
        self.logger.info(json.dumps(log_data))
    
    def log_error(self, model_name: str, request_id: str, error: str, **kwargs):
        """记录错误日志"""
        log_data = {
            "event": "ai_error",
            "model_name": model_name,
            "request_id": request_id,
            "error": error,
            **kwargs
        }
        self.logger.error(json.dumps(log_data))
    
    def log_circuit_breaker(self, service_name: str, state: str, **kwargs):
        """记录熔断器状态变化"""
        log_data = {
            "event": "circuit_breaker",
            "service_name": service_name,
            "state": state,
            **kwargs
        }
        self.logger.warning(json.dumps(log_data))


class PrometheusMetrics:
    """Prometheus指标收集器"""
    
    def __init__(self):
        self.enabled = PROMETHEUS_AVAILABLE
        
        if self.enabled:
            # 请求计数器
            self.requests_total = Counter(
                'ai_service_requests_total',
                'Total number of AI service requests',
                ['model_name', 'status']
            )
            
            # 响应时间直方图
            self.response_time = Histogram(
                'ai_service_response_duration_seconds',
                'Response time of AI service requests',
                ['model_name'],
                buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0]
            )
            
            # 活跃连接数
            self.active_requests = Gauge(
                'ai_service_active_requests',
                'Number of active AI service requests',
                ['model_name']
            )
            
            # 熔断器状态
            self.circuit_breaker_state = Gauge(
                'ai_service_circuit_breaker_state',
                'Circuit breaker state (0=closed, 1=open, 2=half_open)',
                ['service_name']
            )
            
            # 缓存命中率
            self.cache_hits = Counter(
                'ai_service_cache_hits_total',
                'Total number of cache hits',
                ['cache_type']
            )
            
            self.cache_misses = Counter(
                'ai_service_cache_misses_total',
                'Total number of cache misses',
                ['cache_type']
            )
            
            # 模型信息
            self.model_info = Info(
                'ai_service_model_info',
                'Information about AI models'
            )
        else:
            # 创建空的度量对象
            self.requests_total = Counter()
            self.response_time = Histogram()
            self.active_requests = Gauge()
            self.circuit_breaker_state = Gauge()
            self.cache_hits = Counter()
            self.cache_misses = Counter()
            self.model_info = Info()
    
    def record_request(self, model_name: str, success: bool):
        """记录请求"""
        if self.enabled:
            status = "success" if success else "error"
            self.requests_total.labels(model_name=model_name, status=status).inc()
    
    def record_response_time(self, model_name: str, duration: float):
        """记录响应时间"""
        if self.enabled:
            self.response_time.labels(model_name=model_name).observe(duration)
    
    def set_active_requests(self, model_name: str, count: int):
        """设置活跃请求数"""
        if self.enabled:
            self.active_requests.labels(model_name=model_name).set(count)
    
    def set_circuit_breaker_state(self, service_name: str, state: str):
        """设置熔断器状态"""
        if self.enabled:
            state_value = {"closed": 0, "open": 1, "half_open": 2}.get(state, 0)
            self.circuit_breaker_state.labels(service_name=service_name).set(state_value)
    
    def record_cache_hit(self, cache_type: str):
        """记录缓存命中"""
        if self.enabled:
            self.cache_hits.labels(cache_type=cache_type).inc()
    
    def record_cache_miss(self, cache_type: str):
        """记录缓存未命中"""
        if self.enabled:
            self.cache_misses.labels(cache_type=cache_type).inc()
    
    def update_model_info(self, model_name: str, provider: str, version: str):
        """更新模型信息"""
        if self.enabled:
            self.model_info.info({
                'model': model_name,
                'provider': provider,
                'version': version
            })


class AIServiceMonitor:
    """AI服务监控器"""
    
    def __init__(self, 
                 enable_prometheus: bool = True,
                 enable_structured_logging: bool = True,
                 metrics_port: int = 8000):
        self.prometheus_enabled = enable_prometheus and PROMETHEUS_AVAILABLE
        self.logging_enabled = enable_structured_logging
        self.metrics_port = metrics_port
        
        # 初始化组件
        self.metrics = PrometheusMetrics() if self.prometheus_enabled else None
        self.logger = StructuredLogger() if self.logging_enabled else None
        
        # 性能统计
        self.stats = defaultdict(PerformanceStats)
        self.lock = threading.Lock()
        
        # 历史快照
        self.snapshots: List[MetricSnapshot] = []
        self.max_snapshots = 1000
        
        # 启动Prometheus服务器
        if self.prometheus_enabled:
            try:
                start_http_server(self.metrics_port)
                print(f"Prometheus metrics server started on port {self.metrics_port}")
            except Exception as e:
                print(f"Failed to start Prometheus server: {e}")
                self.prometheus_enabled = False
    
    def record_request_start(self, model_name: str, request_id: str, **kwargs):
        """记录请求开始"""
        with self.lock:
            if model_name not in self.stats:
                self.stats[model_name] = PerformanceStats(model_name=model_name)
            
            stats = self.stats[model_name]
            stats.request_count += 1
            stats.last_request_time = datetime.utcnow()
        
        if self.metrics:
            self.metrics.set_active_requests(model_name, 1)
        
        if self.logger:
            self.logger.log_request(model_name, request_id, **kwargs)
    
    def record_request_end(self, model_name: str, request_id: str, 
                          duration: float, success: bool, **kwargs):
        """记录请求结束"""
        with self.lock:
            stats = self.stats[model_name]
            stats.total_response_time += duration
            stats.recent_response_times.append(duration)
            
            if success:
                stats.success_count += 1
            else:
                stats.error_count += 1
        
        if self.metrics:
            self.metrics.record_request(model_name, success)
            self.metrics.record_response_time(model_name, duration)
            self.metrics.set_active_requests(model_name, 0)
        
        if self.logger:
            self.logger.log_response(model_name, request_id, duration, success, **kwargs)
    
    def record_error(self, model_name: str, request_id: str, error: str, **kwargs):
        """记录错误"""
        if self.logger:
            self.logger.log_error(model_name, request_id, error, **kwargs)
    
    def record_circuit_breaker_event(self, service_name: str, state: str, **kwargs):
        """记录熔断器事件"""
        if self.metrics:
            self.metrics.set_circuit_breaker_state(service_name, state)
        
        if self.logger:
            self.logger.log_circuit_breaker(service_name, state, **kwargs)
    
    def record_cache_event(self, cache_type: str, hit: bool):
        """记录缓存事件"""
        if self.metrics:
            if hit:
                self.metrics.record_cache_hit(cache_type)
            else:
                self.metrics.record_cache_miss(cache_type)
    
    def update_model_info(self, model_name: str, provider: str, version: str = "latest"):
        """更新模型信息"""
        if self.metrics:
            self.metrics.update_model_info(model_name, provider, version)
    
    def get_stats_summary(self) -> Dict[str, Any]:
        """获取统计摘要"""
        with self.lock:
            summary = {}
            total_requests = 0
            total_errors = 0
            total_response_time = 0.0
            
            for model_name, stats in self.stats.items():
                total_requests += stats.request_count
                total_errors += stats.error_count
                total_response_time += stats.total_response_time
                
                summary[model_name] = {
                    "request_count": stats.request_count,
                    "success_count": stats.success_count,
                    "error_count": stats.error_count,
                    "success_rate": stats.success_rate,
                    "avg_response_time": stats.avg_response_time,
                    "recent_avg_response_time": stats.recent_avg_response_time,
                    "last_request_time": stats.last_request_time.isoformat() if stats.last_request_time else None
                }
            
            # 全局统计
            summary["global"] = {
                "total_requests": total_requests,
                "total_errors": total_errors,
                "global_success_rate": (total_requests - total_errors) / max(1, total_requests),
                "global_avg_response_time": total_response_time / max(1, total_requests),
                "active_models": len(self.stats),
                "prometheus_enabled": self.prometheus_enabled,
                "logging_enabled": self.logging_enabled
            }
            
            return summary
    
    def create_snapshot(self) -> MetricSnapshot:
        """创建指标快照"""
        stats_summary = self.get_stats_summary()
        global_stats = stats_summary["global"]
        
        snapshot = MetricSnapshot(
            timestamp=datetime.utcnow(),
            requests_total=global_stats["total_requests"],
            requests_failed=global_stats["total_errors"],
            avg_response_time=global_stats["global_avg_response_time"],
            active_models=global_stats["active_models"],
            circuit_breaker_trips=0,  # TODO: 实现熔断器统计
            cache_hits=0,  # TODO: 实现缓存统计
            cache_misses=0
        )
        
        # 保存快照
        with self.lock:
            self.snapshots.append(snapshot)
            if len(self.snapshots) > self.max_snapshots:
                self.snapshots.pop(0)
        
        return snapshot
    
    def get_health_status(self) -> Dict[str, Any]:
        """获取健康状态"""
        stats_summary = self.get_stats_summary()
        global_stats = stats_summary["global"]
        
        # 简单的健康检查逻辑
        is_healthy = True
        issues = []
        
        if global_stats["global_success_rate"] < 0.95:
            is_healthy = False
            issues.append("Low success rate")
        
        if global_stats["global_avg_response_time"] > 10.0:
            is_healthy = False
            issues.append("High response time")
        
        return {
            "healthy": is_healthy,
            "issues": issues,
            "stats": global_stats,
            "timestamp": datetime.utcnow().isoformat()
        }


def monitor_ai_request(monitor: AIServiceMonitor):
    """AI请求监控装饰器"""
    def decorator(func):
        import inspect
        
        # 获取函数签名
        sig = inspect.signature(func)
        param_names = list(sig.parameters.keys())
        
        def extract_params(*args, **kwargs):
            """从args和kwargs中提取参数"""
            # 将args绑定到参数名
            bound_args = {}
            for i, arg in enumerate(args):
                if i < len(param_names):
                    bound_args[param_names[i]] = arg
            
            # 合并kwargs
            bound_args.update(kwargs)
            
            model_name = bound_args.get('model_name', 'unknown')
            request_id = bound_args.get('request_id', f"req_{int(time.time() * 1000)}")
            
            return model_name, request_id
        
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            model_name, request_id = extract_params(*args, **kwargs)
            
            # 记录请求开始
            start_time = time.time()
            monitor.record_request_start(model_name, request_id)
            
            try:
                result = await func(*args, **kwargs)
                duration = time.time() - start_time
                monitor.record_request_end(model_name, request_id, duration, True)
                return result
                
            except Exception as e:
                duration = time.time() - start_time
                monitor.record_request_end(model_name, request_id, duration, False)
                monitor.record_error(model_name, request_id, str(e))
                raise
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            model_name, request_id = extract_params(*args, **kwargs)
            
            # 记录请求开始
            start_time = time.time()
            monitor.record_request_start(model_name, request_id)
            
            try:
                result = func(*args, **kwargs)
                duration = time.time() - start_time
                monitor.record_request_end(model_name, request_id, duration, True)
                return result
                
            except Exception as e:
                duration = time.time() - start_time
                monitor.record_request_end(model_name, request_id, duration, False)
                monitor.record_error(model_name, request_id, str(e))
                raise
        
        # 根据函数类型返回对应的包装器
        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator


# 全局监控实例
ai_monitor = AIServiceMonitor(
    enable_prometheus=True,
    enable_structured_logging=True,
    metrics_port=8090  # 避免与主应用端口冲突
)