"""
Performance Monitoring Dashboard
实时性能监控和可视化
"""

import asyncio
import time
from typing import Dict, Any, List
from datetime import datetime, timedelta
import statistics
import json
from dataclasses import dataclass, asdict
from collections import deque
import psutil
import aiohttp

from app.core.redis_client import redis_client
from app.core.cache_strategy import cache_manager
from app.core.database import engine
from app.core.logging import get_logger
from app.core.metrics import metrics

logger = get_logger(__name__)

@dataclass
class PerformanceMetric:
    """性能指标数据点"""
    timestamp: datetime
    metric_name: str
    value: float
    unit: str
    tags: Dict[str, str] = None

class PerformanceMonitor:
    """性能监控器"""
    
    def __init__(self, window_size: int = 100):
        self.window_size = window_size
        self.metrics_buffer = {
            "response_time": deque(maxlen=window_size),
            "throughput": deque(maxlen=window_size),
            "cache_hit_rate": deque(maxlen=window_size),
            "cpu_usage": deque(maxlen=window_size),
            "memory_usage": deque(maxlen=window_size),
            "db_connections": deque(maxlen=window_size),
            "error_rate": deque(maxlen=window_size)
        }
        
        # 性能阈值
        self.thresholds = {
            "response_time_ms": 200,
            "cache_hit_rate": 70,
            "cpu_usage": 80,
            "memory_usage": 80,
            "error_rate": 1
        }
        
        # 告警状态
        self.alerts = []
        
    async def collect_metrics(self):
        """收集性能指标"""
        try:
            # 1. API响应时间
            response_times = metrics.get_histogram("api_response_time_seconds")
            if response_times:
                avg_response_time = statistics.mean(response_times) * 1000  # Convert to ms
                self.metrics_buffer["response_time"].append(
                    PerformanceMetric(
                        timestamp=datetime.utcnow(),
                        metric_name="response_time",
                        value=avg_response_time,
                        unit="ms"
                    )
                )
            
            # 2. 缓存命中率
            cache_stats = await cache_manager.get_comprehensive_stats()
            hit_rate = cache_stats["overall"]["hit_rate_percent"]
            self.metrics_buffer["cache_hit_rate"].append(
                PerformanceMetric(
                    timestamp=datetime.utcnow(),
                    metric_name="cache_hit_rate",
                    value=hit_rate,
                    unit="%"
                )
            )
            
            # 3. 系统资源使用
            cpu_percent = psutil.cpu_percent(interval=1)
            memory_percent = psutil.virtual_memory().percent
            
            self.metrics_buffer["cpu_usage"].append(
                PerformanceMetric(
                    timestamp=datetime.utcnow(),
                    metric_name="cpu_usage",
                    value=cpu_percent,
                    unit="%"
                )
            )
            
            self.metrics_buffer["memory_usage"].append(
                PerformanceMetric(
                    timestamp=datetime.utcnow(),
                    metric_name="memory_usage",
                    value=memory_percent,
                    unit="%"
                )
            )
            
            # 4. 数据库连接池
            db_pool = engine.pool
            active_connections = db_pool.size() if hasattr(db_pool, 'size') else 0
            self.metrics_buffer["db_connections"].append(
                PerformanceMetric(
                    timestamp=datetime.utcnow(),
                    metric_name="db_connections",
                    value=active_connections,
                    unit="connections"
                )
            )
            
            # 5. 错误率
            total_requests = metrics.get_counter("api_requests_total")
            failed_requests = metrics.get_counter("api_requests_failed")
            error_rate = (failed_requests / total_requests * 100) if total_requests > 0 else 0
            
            self.metrics_buffer["error_rate"].append(
                PerformanceMetric(
                    timestamp=datetime.utcnow(),
                    metric_name="error_rate",
                    value=error_rate,
                    unit="%"
                )
            )
            
            # 检查阈值并生成告警
            await self._check_thresholds()
            
        except Exception as e:
            logger.error(f"Failed to collect metrics: {e}")
    
    async def _check_thresholds(self):
        """检查性能阈值并生成告警"""
        now = datetime.utcnow()
        
        # 响应时间检查
        if self.metrics_buffer["response_time"]:
            latest_response_time = self.metrics_buffer["response_time"][-1].value
            if latest_response_time > self.thresholds["response_time_ms"]:
                self._add_alert(
                    "HIGH_RESPONSE_TIME",
                    f"Response time {latest_response_time:.1f}ms exceeds threshold {self.thresholds['response_time_ms']}ms",
                    "warning"
                )
        
        # 缓存命中率检查
        if self.metrics_buffer["cache_hit_rate"]:
            latest_hit_rate = self.metrics_buffer["cache_hit_rate"][-1].value
            if latest_hit_rate < self.thresholds["cache_hit_rate"]:
                self._add_alert(
                    "LOW_CACHE_HIT_RATE",
                    f"Cache hit rate {latest_hit_rate:.1f}% below threshold {self.thresholds['cache_hit_rate']}%",
                    "warning"
                )
        
        # CPU使用率检查
        if self.metrics_buffer["cpu_usage"]:
            latest_cpu = self.metrics_buffer["cpu_usage"][-1].value
            if latest_cpu > self.thresholds["cpu_usage"]:
                self._add_alert(
                    "HIGH_CPU_USAGE",
                    f"CPU usage {latest_cpu:.1f}% exceeds threshold {self.thresholds['cpu_usage']}%",
                    "critical"
                )
        
        # 内存使用率检查
        if self.metrics_buffer["memory_usage"]:
            latest_memory = self.metrics_buffer["memory_usage"][-1].value
            if latest_memory > self.thresholds["memory_usage"]:
                self._add_alert(
                    "HIGH_MEMORY_USAGE",
                    f"Memory usage {latest_memory:.1f}% exceeds threshold {self.thresholds['memory_usage']}%",
                    "critical"
                )
        
        # 错误率检查
        if self.metrics_buffer["error_rate"]:
            latest_error_rate = self.metrics_buffer["error_rate"][-1].value
            if latest_error_rate > self.thresholds["error_rate"]:
                self._add_alert(
                    "HIGH_ERROR_RATE",
                    f"Error rate {latest_error_rate:.1f}% exceeds threshold {self.thresholds['error_rate']}%",
                    "critical"
                )
    
    def _add_alert(self, alert_type: str, message: str, severity: str):
        """添加告警"""
        alert = {
            "type": alert_type,
            "message": message,
            "severity": severity,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        # 避免重复告警
        if not any(a["type"] == alert_type for a in self.alerts[-10:]):
            self.alerts.append(alert)
            logger.warning(f"Performance alert: {message}")
            
            # 发送告警通知（可以集成webhook、邮件等）
            asyncio.create_task(self._send_alert_notification(alert))
    
    async def _send_alert_notification(self, alert: Dict[str, Any]):
        """发送告警通知"""
        # TODO: 实现告警通知（Slack、邮件、短信等）
        pass
    
    def get_current_metrics(self) -> Dict[str, Any]:
        """获取当前性能指标"""
        current = {}
        
        for metric_name, buffer in self.metrics_buffer.items():
            if buffer:
                latest = buffer[-1]
                values = [m.value for m in buffer]
                
                current[metric_name] = {
                    "current": latest.value,
                    "unit": latest.unit,
                    "timestamp": latest.timestamp.isoformat(),
                    "statistics": {
                        "min": min(values),
                        "max": max(values),
                        "avg": statistics.mean(values),
                        "p50": statistics.median(values),
                        "p95": statistics.quantiles(values, n=20)[18] if len(values) > 20 else max(values),
                        "p99": statistics.quantiles(values, n=100)[98] if len(values) > 100 else max(values)
                    },
                    "trend": self._calculate_trend(values)
                }
        
        return current
    
    def _calculate_trend(self, values: List[float]) -> str:
        """计算趋势（上升、下降、稳定）"""
        if len(values) < 2:
            return "stable"
        
        # 计算最近10个值的趋势
        recent_values = values[-10:]
        if len(recent_values) < 2:
            return "stable"
        
        # 简单线性回归
        n = len(recent_values)
        x_mean = n / 2
        y_mean = sum(recent_values) / n
        
        numerator = sum((i - x_mean) * (y - y_mean) for i, y in enumerate(recent_values))
        denominator = sum((i - x_mean) ** 2 for i in range(n))
        
        if denominator == 0:
            return "stable"
        
        slope = numerator / denominator
        
        # 判断趋势
        if abs(slope) < 0.01:
            return "stable"
        elif slope > 0:
            return "increasing"
        else:
            return "decreasing"
    
    def get_dashboard_data(self) -> Dict[str, Any]:
        """获取仪表板数据"""
        return {
            "metrics": self.get_current_metrics(),
            "alerts": self.alerts[-20:],  # 最近20条告警
            "thresholds": self.thresholds,
            "health_score": self._calculate_health_score(),
            "timestamp": datetime.utcnow().isoformat()
        }
    
    def _calculate_health_score(self) -> float:
        """计算系统健康评分（0-100）"""
        score = 100.0
        
        # 根据各项指标计算扣分
        if self.metrics_buffer["response_time"]:
            latest_rt = self.metrics_buffer["response_time"][-1].value
            if latest_rt > self.thresholds["response_time_ms"]:
                score -= min(20, (latest_rt - self.thresholds["response_time_ms"]) / 10)
        
        if self.metrics_buffer["cache_hit_rate"]:
            latest_hr = self.metrics_buffer["cache_hit_rate"][-1].value
            if latest_hr < self.thresholds["cache_hit_rate"]:
                score -= min(20, (self.thresholds["cache_hit_rate"] - latest_hr) / 2)
        
        if self.metrics_buffer["error_rate"]:
            latest_er = self.metrics_buffer["error_rate"][-1].value
            if latest_er > self.thresholds["error_rate"]:
                score -= min(30, latest_er * 10)
        
        if self.metrics_buffer["cpu_usage"]:
            latest_cpu = self.metrics_buffer["cpu_usage"][-1].value
            if latest_cpu > self.thresholds["cpu_usage"]:
                score -= min(15, (latest_cpu - self.thresholds["cpu_usage"]) / 2)
        
        if self.metrics_buffer["memory_usage"]:
            latest_mem = self.metrics_buffer["memory_usage"][-1].value
            if latest_mem > self.thresholds["memory_usage"]:
                score -= min(15, (latest_mem - self.thresholds["memory_usage"]) / 2)
        
        return max(0, score)

class PerformanceDashboard:
    """性能监控仪表板API"""
    
    def __init__(self):
        self.monitor = PerformanceMonitor()
        self.collection_interval = 10  # 10秒收集一次
        self.collection_task = None
    
    async def start(self):
        """启动监控"""
        self.collection_task = asyncio.create_task(self._collection_loop())
        logger.info("Performance monitoring started")
    
    async def stop(self):
        """停止监控"""
        if self.collection_task:
            self.collection_task.cancel()
            await asyncio.gather(self.collection_task, return_exceptions=True)
        logger.info("Performance monitoring stopped")
    
    async def _collection_loop(self):
        """指标收集循环"""
        while True:
            try:
                await self.monitor.collect_metrics()
                await asyncio.sleep(self.collection_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Collection loop error: {e}")
                await asyncio.sleep(self.collection_interval)
    
    def get_realtime_metrics(self) -> Dict[str, Any]:
        """获取实时指标"""
        return self.monitor.get_dashboard_data()
    
    def get_performance_report(self, duration_hours: int = 1) -> Dict[str, Any]:
        """生成性能报告"""
        metrics = self.monitor.get_current_metrics()
        
        report = {
            "report_time": datetime.utcnow().isoformat(),
            "duration_hours": duration_hours,
            "summary": {
                "health_score": self.monitor._calculate_health_score(),
                "total_alerts": len(self.monitor.alerts),
                "critical_alerts": len([a for a in self.monitor.alerts if a["severity"] == "critical"])
            },
            "metrics_summary": {},
            "recommendations": []
        }
        
        # 生成每个指标的摘要
        for metric_name, metric_data in metrics.items():
            report["metrics_summary"][metric_name] = {
                "current": metric_data["current"],
                "average": metric_data["statistics"]["avg"],
                "p95": metric_data["statistics"]["p95"],
                "trend": metric_data["trend"],
                "unit": metric_data["unit"]
            }
        
        # 生成优化建议
        report["recommendations"] = self._generate_recommendations(metrics)
        
        return report
    
    def _generate_recommendations(self, metrics: Dict[str, Any]) -> List[str]:
        """生成性能优化建议"""
        recommendations = []
        
        # 响应时间优化建议
        if "response_time" in metrics:
            rt_data = metrics["response_time"]
            if rt_data["statistics"]["avg"] > 150:
                recommendations.append(
                    "考虑增加缓存层或优化数据库查询以降低响应时间"
                )
            if rt_data["trend"] == "increasing":
                recommendations.append(
                    "响应时间呈上升趋势，建议检查系统负载和资源使用情况"
                )
        
        # 缓存优化建议
        if "cache_hit_rate" in metrics:
            hr_data = metrics["cache_hit_rate"]
            if hr_data["current"] < 70:
                recommendations.append(
                    "缓存命中率低于目标，建议实施缓存预热策略"
                )
            if hr_data["trend"] == "decreasing":
                recommendations.append(
                    "缓存命中率下降，可能需要调整缓存策略或增加缓存容量"
                )
        
        # 资源使用建议
        if "cpu_usage" in metrics and metrics["cpu_usage"]["current"] > 70:
            recommendations.append(
                "CPU使用率较高，考虑优化算法或增加计算资源"
            )
        
        if "memory_usage" in metrics and metrics["memory_usage"]["current"] > 70:
            recommendations.append(
                "内存使用率较高，建议检查内存泄漏或优化内存使用"
            )
        
        # 错误率建议
        if "error_rate" in metrics and metrics["error_rate"]["current"] > 0.5:
            recommendations.append(
                "错误率偏高，需要检查应用日志并修复潜在问题"
            )
        
        return recommendations

# 全局实例
performance_dashboard = PerformanceDashboard()

# FastAPI路由集成
from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/api/v1/monitoring", tags=["monitoring"])

@router.get("/dashboard")
async def get_dashboard():
    """获取性能监控仪表板数据"""
    return performance_dashboard.get_realtime_metrics()

@router.get("/report")
async def get_performance_report(duration_hours: int = 1):
    """获取性能报告"""
    return performance_dashboard.get_performance_report(duration_hours)

@router.get("/health-score")
async def get_health_score():
    """获取系统健康评分"""
    score = performance_dashboard.monitor._calculate_health_score()
    return {
        "health_score": score,
        "status": "healthy" if score >= 80 else "degraded" if score >= 60 else "critical",
        "timestamp": datetime.utcnow().isoformat()
    }

@router.get("/alerts")
async def get_alerts(limit: int = 20):
    """获取最近的告警"""
    alerts = performance_dashboard.monitor.alerts[-limit:]
    return {
        "alerts": alerts,
        "total": len(alerts),
        "critical": len([a for a in alerts if a["severity"] == "critical"]),
        "warning": len([a for a in alerts if a["severity"] == "warning"])
    }