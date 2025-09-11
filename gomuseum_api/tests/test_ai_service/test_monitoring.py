"""
测试AI服务监控系统
"""

import pytest
import asyncio
import time
import json
from unittest.mock import patch, MagicMock
from datetime import datetime

from app.services.ai_service.monitoring import (
    AIServiceMonitor, StructuredLogger, PrometheusMetrics,
    PerformanceStats, MetricSnapshot, monitor_ai_request,
    ai_monitor
)


class TestPerformanceStats:
    """测试性能统计"""
    
    def test_performance_stats_initialization(self):
        """测试性能统计初始化"""
        stats = PerformanceStats(model_name="test-model")
        
        assert stats.model_name == "test-model"
        assert stats.request_count == 0
        assert stats.total_response_time == 0.0
        assert stats.error_count == 0
        assert stats.success_count == 0
        assert stats.last_request_time is None
        assert len(stats.recent_response_times) == 0
    
    def test_performance_stats_calculations(self):
        """测试性能统计计算"""
        stats = PerformanceStats(model_name="test-model")
        
        # 添加一些数据
        stats.request_count = 10
        stats.total_response_time = 20.0
        stats.success_count = 8
        stats.error_count = 2
        stats.recent_response_times.extend([1.0, 2.0, 3.0])
        
        assert stats.avg_response_time == 2.0
        assert stats.success_rate == 0.8
        assert stats.recent_avg_response_time == 2.0


class TestStructuredLogger:
    """测试结构化日志器"""
    
    @pytest.fixture
    def logger(self):
        return StructuredLogger("test_logger")
    
    def test_structured_logger_initialization(self, logger):
        """测试结构化日志器初始化"""
        assert logger.logger.name == "test_logger"
        assert len(logger.logger.handlers) > 0
    
    @patch('logging.getLogger')
    def test_log_request(self, mock_get_logger, logger):
        """测试请求日志"""
        mock_logger = MagicMock()
        mock_get_logger.return_value = mock_logger
        
        logger = StructuredLogger("test")
        logger.logger = mock_logger
        
        logger.log_request("gpt-4", "req_123", extra_field="test")
        
        mock_logger.info.assert_called_once()
        call_args = mock_logger.info.call_args[0][0]
        log_data = json.loads(call_args)
        
        assert log_data["event"] == "ai_request"
        assert log_data["model_name"] == "gpt-4"
        assert log_data["request_id"] == "req_123"
        assert log_data["extra_field"] == "test"
    
    @patch('logging.getLogger')
    def test_log_response(self, mock_get_logger, logger):
        """测试响应日志"""
        mock_logger = MagicMock()
        mock_get_logger.return_value = mock_logger
        
        logger = StructuredLogger("test")
        logger.logger = mock_logger
        
        logger.log_response("gpt-4", "req_123", 2.5, True, cost=0.01)
        
        mock_logger.info.assert_called_once()
        call_args = mock_logger.info.call_args[0][0]
        log_data = json.loads(call_args)
        
        assert log_data["event"] == "ai_response"
        assert log_data["model_name"] == "gpt-4"
        assert log_data["response_time"] == 2.5
        assert log_data["success"] is True
        assert log_data["cost"] == 0.01
    
    @patch('logging.getLogger')
    def test_log_error(self, mock_get_logger, logger):
        """测试错误日志"""
        mock_logger = MagicMock()
        mock_get_logger.return_value = mock_logger
        
        logger = StructuredLogger("test")
        logger.logger = mock_logger
        
        logger.log_error("gpt-4", "req_123", "Connection timeout")
        
        mock_logger.error.assert_called_once()
        call_args = mock_logger.error.call_args[0][0]
        log_data = json.loads(call_args)
        
        assert log_data["event"] == "ai_error"
        assert log_data["error"] == "Connection timeout"


class TestPrometheusMetrics:
    """测试Prometheus指标"""
    
    def test_prometheus_metrics_initialization(self):
        """测试Prometheus指标初始化"""
        metrics = PrometheusMetrics()
        
        # 验证基本属性存在
        assert hasattr(metrics, 'requests_total')
        assert hasattr(metrics, 'response_time')
        assert hasattr(metrics, 'active_requests')
        assert hasattr(metrics, 'circuit_breaker_state')
        assert hasattr(metrics, 'cache_hits')
        assert hasattr(metrics, 'cache_misses')
        assert hasattr(metrics, 'model_info')
    
    def test_record_request(self):
        """测试记录请求"""
        metrics = PrometheusMetrics()
        
        # 这些方法应该不抛异常
        metrics.record_request("gpt-4", True)
        metrics.record_request("gpt-4", False)
    
    def test_record_response_time(self):
        """测试记录响应时间"""
        metrics = PrometheusMetrics()
        
        metrics.record_response_time("gpt-4", 2.5)
    
    def test_set_circuit_breaker_state(self):
        """测试设置熔断器状态"""
        metrics = PrometheusMetrics()
        
        metrics.set_circuit_breaker_state("ai_service", "closed")
        metrics.set_circuit_breaker_state("ai_service", "open")
        metrics.set_circuit_breaker_state("ai_service", "half_open")
    
    def test_cache_operations(self):
        """测试缓存操作"""
        metrics = PrometheusMetrics()
        
        metrics.record_cache_hit("model_cache")
        metrics.record_cache_miss("model_cache")


class TestAIServiceMonitor:
    """测试AI服务监控器"""
    
    @pytest.fixture
    def monitor(self):
        return AIServiceMonitor(
            enable_prometheus=False,  # 避免端口冲突
            enable_structured_logging=True,
            metrics_port=8091
        )
    
    def test_monitor_initialization(self, monitor):
        """测试监控器初始化"""
        assert monitor.logging_enabled is True
        assert monitor.prometheus_enabled is False
        assert monitor.logger is not None
        assert len(monitor.stats) == 0
        assert len(monitor.snapshots) == 0
    
    def test_record_request_lifecycle(self, monitor):
        """测试请求生命周期记录"""
        model_name = "gpt-4"
        request_id = "req_123"
        
        # 记录请求开始
        monitor.record_request_start(model_name, request_id)
        
        assert model_name in monitor.stats
        stats = monitor.stats[model_name]
        assert stats.request_count == 1
        assert stats.last_request_time is not None
        
        # 记录请求结束
        monitor.record_request_end(model_name, request_id, 2.5, True)
        
        assert stats.success_count == 1
        assert stats.error_count == 0
        assert stats.total_response_time == 2.5
        assert len(stats.recent_response_times) == 1
        assert stats.recent_response_times[0] == 2.5
    
    def test_record_error(self, monitor):
        """测试错误记录"""
        model_name = "gpt-4"
        request_id = "req_123"
        
        monitor.record_request_start(model_name, request_id)
        monitor.record_request_end(model_name, request_id, 1.0, False)
        monitor.record_error(model_name, request_id, "API Error")
        
        stats = monitor.stats[model_name]
        assert stats.error_count == 1
        assert stats.success_count == 0
    
    def test_circuit_breaker_event(self, monitor):
        """测试熔断器事件"""
        monitor.record_circuit_breaker_event("ai_service", "open", failure_count=5)
        # 不应该抛异常
    
    def test_cache_event(self, monitor):
        """测试缓存事件"""
        monitor.record_cache_event("model_cache", True)  # 命中
        monitor.record_cache_event("model_cache", False)  # 未命中
        # 不应该抛异常
    
    def test_stats_summary(self, monitor):
        """测试统计摘要"""
        # 添加一些测试数据
        monitor.record_request_start("gpt-4", "req_1")
        monitor.record_request_end("gpt-4", "req_1", 2.0, True)
        
        monitor.record_request_start("claude-3", "req_2")
        monitor.record_request_end("claude-3", "req_2", 1.5, False)
        
        summary = monitor.get_stats_summary()
        
        assert "gpt-4" in summary
        assert "claude-3" in summary
        assert "global" in summary
        
        gpt4_stats = summary["gpt-4"]
        assert gpt4_stats["request_count"] == 1
        assert gpt4_stats["success_count"] == 1
        assert gpt4_stats["error_count"] == 0
        assert gpt4_stats["success_rate"] == 1.0
        assert gpt4_stats["avg_response_time"] == 2.0
        
        claude_stats = summary["claude-3"]
        assert claude_stats["request_count"] == 1
        assert claude_stats["success_count"] == 0
        assert claude_stats["error_count"] == 1
        assert claude_stats["success_rate"] == 0.0
        
        global_stats = summary["global"]
        assert global_stats["total_requests"] == 2
        assert global_stats["total_errors"] == 1
        assert global_stats["global_success_rate"] == 0.5
        assert global_stats["active_models"] == 2
    
    def test_create_snapshot(self, monitor):
        """测试创建快照"""
        # 添加一些数据
        monitor.record_request_start("gpt-4", "req_1")
        monitor.record_request_end("gpt-4", "req_1", 2.0, True)
        
        snapshot = monitor.create_snapshot()
        
        assert isinstance(snapshot, MetricSnapshot)
        assert snapshot.requests_total == 1
        assert snapshot.requests_failed == 0
        assert snapshot.avg_response_time == 2.0
        assert snapshot.active_models == 1
        
        # 验证快照被保存
        assert len(monitor.snapshots) == 1
        assert monitor.snapshots[0] == snapshot
    
    def test_health_status(self, monitor):
        """测试健康状态"""
        # 测试健康状态
        monitor.record_request_start("gpt-4", "req_1")
        monitor.record_request_end("gpt-4", "req_1", 1.0, True)
        
        health = monitor.get_health_status()
        
        assert "healthy" in health
        assert "issues" in health
        assert "stats" in health
        assert "timestamp" in health
        assert health["healthy"] is True
        assert len(health["issues"]) == 0
        
        # 测试不健康状态 - 添加大量错误
        for i in range(10):
            monitor.record_request_start("gpt-4", f"req_{i}")
            monitor.record_request_end("gpt-4", f"req_{i}", 1.0, False)
        
        health = monitor.get_health_status()
        assert health["healthy"] is False
        assert len(health["issues"]) > 0


class TestMonitorDecorator:
    """测试监控装饰器"""
    
    @pytest.fixture
    def test_monitor(self):
        return AIServiceMonitor(
            enable_prometheus=False,
            enable_structured_logging=False
        )
    
    def test_sync_function_decorator(self, test_monitor):
        """测试同步函数装饰器"""
        @monitor_ai_request(test_monitor)
        def test_function(model_name="test-model", request_id="test-req"):
            time.sleep(0.1)
            return "success"
        
        # 显式传递参数
        result = test_function(model_name="test-model", request_id="test-req")
        
        assert result == "success"
        assert "test-model" in test_monitor.stats
        stats = test_monitor.stats["test-model"]
        assert stats.request_count == 1
        assert stats.success_count == 1
        assert stats.error_count == 0
    
    def test_sync_function_decorator_with_error(self, test_monitor):
        """测试同步函数装饰器错误处理"""
        @monitor_ai_request(test_monitor)
        def test_function(model_name="test-model", request_id="test-req"):
            raise ValueError("Test error")
        
        with pytest.raises(ValueError):
            test_function(model_name="test-model", request_id="test-req")
        
        stats = test_monitor.stats["test-model"]
        assert stats.request_count == 1
        assert stats.success_count == 0
        assert stats.error_count == 1
    
    @pytest.mark.asyncio
    async def test_async_function_decorator(self, test_monitor):
        """测试异步函数装饰器"""
        @monitor_ai_request(test_monitor)
        async def test_async_function(model_name="async-model", request_id="async-req"):
            await asyncio.sleep(0.1)
            return "async success"
        
        result = await test_async_function(model_name="async-model", request_id="async-req")
        
        assert result == "async success"
        assert "async-model" in test_monitor.stats
        stats = test_monitor.stats["async-model"]
        assert stats.request_count == 1
        assert stats.success_count == 1
        assert stats.error_count == 0
    
    @pytest.mark.asyncio
    async def test_async_function_decorator_with_error(self, test_monitor):
        """测试异步函数装饰器错误处理"""
        @monitor_ai_request(test_monitor)
        async def test_async_function(model_name="async-model", request_id="async-req"):
            raise RuntimeError("Async test error")
        
        with pytest.raises(RuntimeError):
            await test_async_function(model_name="async-model", request_id="async-req")
        
        stats = test_monitor.stats["async-model"]
        assert stats.request_count == 1
        assert stats.success_count == 0
        assert stats.error_count == 1


class TestGlobalMonitor:
    """测试全局监控实例"""
    
    def test_global_monitor_exists(self):
        """测试全局监控实例存在"""
        assert ai_monitor is not None
        assert isinstance(ai_monitor, AIServiceMonitor)
    
    def test_global_monitor_functionality(self):
        """测试全局监控实例功能"""
        # 清理之前的数据
        ai_monitor.stats.clear()
        
        ai_monitor.record_request_start("global-test", "req_global")
        ai_monitor.record_request_end("global-test", "req_global", 1.0, True)
        
        assert "global-test" in ai_monitor.stats
        stats = ai_monitor.stats["global-test"]
        assert stats.request_count == 1
        assert stats.success_count == 1