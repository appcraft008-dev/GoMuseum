import time
import psutil
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional, List
from collections import defaultdict, deque
from dataclasses import dataclass, field
import asyncio

from .redis_client import redis_client, get_cache_key
from .logging import get_logger

logger = get_logger(__name__)


@dataclass
class MetricPoint:
    """Individual metric data point"""
    timestamp: datetime
    value: float
    tags: Dict[str, str] = field(default_factory=dict)


@dataclass 
class MetricSeries:
    """Time series of metric points"""
    name: str
    points: deque = field(default_factory=lambda: deque(maxlen=1000))
    
    def add_point(self, value: float, tags: Dict[str, str] = None):
        """Add a metric point"""
        point = MetricPoint(
            timestamp=datetime.now(timezone.utc),
            value=value,
            tags=tags or {}
        )
        self.points.append(point)
    
    def get_latest(self) -> Optional[MetricPoint]:
        """Get latest metric point"""
        return self.points[-1] if self.points else None
    
    def get_average(self, minutes: int = 5) -> float:
        """Get average value over last N minutes"""
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=minutes)
        recent_points = [p for p in self.points if p.timestamp >= cutoff]
        
        if not recent_points:
            return 0.0
        
        return sum(p.value for p in recent_points) / len(recent_points)
    
    def get_sum(self, minutes: int = 5) -> float:
        """Get sum of values over last N minutes"""
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=minutes)
        recent_points = [p for p in self.points if p.timestamp >= cutoff]
        
        return sum(p.value for p in recent_points)


class MetricsCollector:
    """Centralized metrics collection and storage"""
    
    def __init__(self):
        self.metrics: Dict[str, MetricSeries] = {}
        self.counters: Dict[str, int] = defaultdict(int)
        self.gauges: Dict[str, float] = {}
        self.histograms: Dict[str, List[float]] = defaultdict(list)
        self.timers: Dict[str, deque] = defaultdict(lambda: deque(maxlen=1000))
        
        # Performance tracking
        self.request_durations: Dict[str, deque] = defaultdict(lambda: deque(maxlen=100))
        self.error_counts: Dict[str, int] = defaultdict(int)
        
        # System metrics
        self.system_metrics = {
            "cpu_percent": MetricSeries("cpu_percent"),
            "memory_percent": MetricSeries("memory_percent"),
            "disk_usage_percent": MetricSeries("disk_usage_percent"),
            "active_connections": MetricSeries("active_connections"),
        }
    
    def increment_counter(self, name: str, value: int = 1, tags: Dict[str, str] = None):
        """Increment a counter metric"""
        self.counters[name] += value
        
        # Also store as time series
        if name not in self.metrics:
            self.metrics[name] = MetricSeries(name)
        self.metrics[name].add_point(self.counters[name], tags)
        
        logger.debug(f"Counter incremented: {name} = {self.counters[name]}")
    
    def set_gauge(self, name: str, value: float, tags: Dict[str, str] = None):
        """Set a gauge metric value"""
        self.gauges[name] = value
        
        # Also store as time series
        if name not in self.metrics:
            self.metrics[name] = MetricSeries(name)
        self.metrics[name].add_point(value, tags)
        
        logger.debug(f"Gauge set: {name} = {value}")
    
    def record_histogram(self, name: str, value: float, tags: Dict[str, str] = None):
        """Record a histogram value"""
        self.histograms[name].append(value)
        
        # Keep only recent values
        if len(self.histograms[name]) > 1000:
            self.histograms[name] = self.histograms[name][-1000:]
        
        # Also store as time series
        if name not in self.metrics:
            self.metrics[name] = MetricSeries(name)
        self.metrics[name].add_point(value, tags)
    
    def record_timer(self, name: str, duration: float, tags: Dict[str, str] = None):
        """Record a timer value (in seconds)"""
        self.timers[name].append(duration)
        self.record_histogram(f"{name}_duration", duration, tags)
    
    def track_request(self, endpoint: str, method: str, duration: float, status_code: int):
        """Track API request metrics"""
        # Request duration
        key = f"{method}_{endpoint}"
        self.request_durations[key].append(duration)
        
        # Request count
        self.increment_counter("api_requests_total", tags={
            "method": method,
            "endpoint": endpoint,
            "status": str(status_code)
        })
        
        # Error count
        if status_code >= 400:
            self.increment_counter("api_errors_total", tags={
                "method": method,
                "endpoint": endpoint,
                "status": str(status_code)
            })
        
        # Response time histogram
        self.record_histogram("api_request_duration", duration, tags={
            "method": method,
            "endpoint": endpoint
        })
    
    def track_database_query(self, query_type: str, duration: float, success: bool):
        """Track database query metrics"""
        self.record_timer(f"db_query_{query_type}", duration)
        
        self.increment_counter("db_queries_total", tags={
            "type": query_type,
            "success": str(success).lower()
        })
        
        if not success:
            self.increment_counter("db_errors_total", tags={"type": query_type})
    
    def track_cache_operation(self, operation: str, hit: bool = None):
        """Track cache operation metrics"""
        self.increment_counter(f"cache_{operation}_total")
        
        if hit is not None:
            if hit:
                self.increment_counter("cache_hits_total")
            else:
                self.increment_counter("cache_misses_total")
    
    def track_quota_usage(self, user_id: str, remaining_quota: int, total_quota: int):
        """Track user quota usage"""
        usage_percent = ((total_quota - remaining_quota) / total_quota) * 100
        
        self.set_gauge("user_quota_usage_percent", usage_percent, tags={
            "user_id": user_id
        })
        
        self.set_gauge("user_quota_remaining", remaining_quota, tags={
            "user_id": user_id
        })
    
    async def collect_system_metrics(self):
        """Collect system-level metrics"""
        try:
            # CPU usage
            cpu_percent = psutil.cpu_percent(interval=1)
            self.system_metrics["cpu_percent"].add_point(cpu_percent)
            
            # Memory usage
            memory = psutil.virtual_memory()
            self.system_metrics["memory_percent"].add_point(memory.percent)
            
            # Disk usage
            disk = psutil.disk_usage('/')
            disk_percent = (disk.used / disk.total) * 100
            self.system_metrics["disk_usage_percent"].add_point(disk_percent)
            
            # Network connections (active)
            connections = len(psutil.net_connections(kind='inet'))
            self.system_metrics["active_connections"].add_point(connections)
            
            logger.debug(f"System metrics collected - CPU: {cpu_percent}%, Memory: {memory.percent}%")
            
        except Exception as e:
            logger.error(f"Failed to collect system metrics: {e}")
    
    async def collect_redis_metrics(self):
        """Collect Redis-specific metrics"""
        try:
            if redis_client.redis:
                info = await redis_client.get_stats()
                
                # Redis memory usage
                used_memory = info.get("used_memory", "0B")
                if used_memory != "0B":
                    # Parse memory value (assumes format like "1.08M")
                    memory_str = used_memory.replace("B", "")
                    if "M" in memory_str:
                        memory_mb = float(memory_str.replace("M", ""))
                        self.set_gauge("redis_memory_usage_mb", memory_mb)
                
                # Redis hit/miss ratio
                hits = info.get("keyspace_hits", 0)
                misses = info.get("keyspace_misses", 0)
                total = hits + misses
                hit_rate = (hits / total * 100) if total > 0 else 0
                
                self.set_gauge("redis_hit_rate_percent", hit_rate)
                self.set_gauge("redis_connected_clients", info.get("connected_clients", 0))
                
        except Exception as e:
            logger.error(f"Failed to collect Redis metrics: {e}")
    
    def get_summary(self) -> Dict[str, Any]:
        """Get metrics summary"""
        summary = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "counters": dict(self.counters),
            "gauges": dict(self.gauges),
            "system": {},
            "api": {},
            "database": {},
            "cache": {}
        }
        
        # System metrics summary
        for name, series in self.system_metrics.items():
            latest = series.get_latest()
            if latest:
                summary["system"][name] = {
                    "current": latest.value,
                    "average_5m": series.get_average(5),
                    "timestamp": latest.timestamp.isoformat()
                }
        
        # API metrics summary
        total_requests = self.counters.get("api_requests_total", 0)
        total_errors = self.counters.get("api_errors_total", 0)
        error_rate = (total_errors / total_requests * 100) if total_requests > 0 else 0
        
        summary["api"] = {
            "total_requests": total_requests,
            "total_errors": total_errors,
            "error_rate_percent": error_rate,
            "avg_response_time": self._get_avg_response_time()
        }
        
        # Database metrics summary
        summary["database"] = {
            "total_queries": self.counters.get("db_queries_total", 0),
            "total_errors": self.counters.get("db_errors_total", 0)
        }
        
        # Cache metrics summary
        cache_hits = self.counters.get("cache_hits_total", 0)
        cache_misses = self.counters.get("cache_misses_total", 0)
        cache_total = cache_hits + cache_misses
        cache_hit_rate = (cache_hits / cache_total * 100) if cache_total > 0 else 0
        
        summary["cache"] = {
            "hits": cache_hits,
            "misses": cache_misses,
            "hit_rate_percent": cache_hit_rate
        }
        
        return summary
    
    def _get_avg_response_time(self) -> float:
        """Calculate average response time across all endpoints"""
        all_durations = []
        for durations in self.request_durations.values():
            all_durations.extend(durations)
        
        return sum(all_durations) / len(all_durations) if all_durations else 0.0
    
    async def persist_metrics(self):
        """Persist current metrics to Redis"""
        try:
            summary = self.get_summary()
            key = get_cache_key("metrics", "summary")
            await redis_client.set(key, summary, ttl=3600)  # Keep for 1 hour
            
            # Also store historical data with timestamp
            historical_key = get_cache_key("metrics", "historical", str(int(time.time())))
            await redis_client.set(historical_key, summary, ttl=86400 * 7)  # Keep for 7 days
            
        except Exception as e:
            logger.error(f"Failed to persist metrics: {e}")
    
    def reset_counters(self):
        """Reset all counters (useful for testing)"""
        self.counters.clear()
        self.metrics.clear()
        self.histograms.clear()
        self.timers.clear()
        self.request_durations.clear()
        self.error_counts.clear()
        
        logger.info("Metrics counters reset")


# Global metrics collector instance
metrics = MetricsCollector()


# Metrics collection task
async def start_metrics_collection():
    """Start background metrics collection"""
    logger.info("Starting metrics collection")
    
    while True:
        try:
            # Collect system metrics every 30 seconds
            await metrics.collect_system_metrics()
            await metrics.collect_redis_metrics()
            
            # Persist metrics every 5 minutes
            if int(time.time()) % 300 == 0:  # Every 5 minutes
                await metrics.persist_metrics()
            
            await asyncio.sleep(30)
            
        except Exception as e:
            logger.error(f"Metrics collection error: {e}")
            await asyncio.sleep(60)  # Wait longer on error


# Convenience functions
def track_api_request(endpoint: str, method: str, duration: float, status_code: int):
    """Track API request - convenience function"""
    metrics.track_request(endpoint, method, duration, status_code)


def track_db_query(query_type: str, duration: float, success: bool = True):
    """Track database query - convenience function"""
    metrics.track_database_query(query_type, duration, success)


def track_cache_hit():
    """Track cache hit - convenience function"""
    metrics.track_cache_operation("get", hit=True)


def track_cache_miss():
    """Track cache miss - convenience function"""
    metrics.track_cache_operation("get", hit=False)


def increment_counter(name: str, value: int = 1, tags: Dict[str, str] = None):
    """Increment counter - convenience function"""
    metrics.increment_counter(name, value, tags)


def set_gauge(name: str, value: float, tags: Dict[str, str] = None):
    """Set gauge - convenience function"""
    metrics.set_gauge(name, value, tags)


# Timing context manager
class timer:
    """Context manager for timing operations"""
    
    def __init__(self, metric_name: str, tags: Dict[str, str] = None):
        self.metric_name = metric_name
        self.tags = tags or {}
        self.start_time = None
    
    def __enter__(self):
        self.start_time = time.time()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.start_time:
            duration = time.time() - self.start_time
            metrics.record_timer(self.metric_name, duration, self.tags)


# Decorator for timing functions
def timed(metric_name: str = None, tags: Dict[str, str] = None):
    """Decorator to time function execution"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            name = metric_name or f"{func.__module__}.{func.__name__}"
            with timer(name, tags):
                return func(*args, **kwargs)
        return wrapper
    return decorator