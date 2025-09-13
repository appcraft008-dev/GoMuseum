"""
GoMuseum API Performance Analyzer
全面的性能分析和基准测试工具
"""

import asyncio
import time
import psutil
import gc
import tracemalloc
import io
import json
import statistics
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Callable, Tuple
from contextlib import asynccontextmanager
import cProfile
import pstats
from functools import wraps
from dataclasses import dataclass, asdict
import numpy as np

from app.core.logging import get_logger
from app.core.redis_client import redis_client
from app.core.database import get_db
from app.core.cache_strategy import cache_manager
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = get_logger(__name__)

# 性能目标配置
PERFORMANCE_TARGETS = {
    "api_response_time": {
        "p50": 50,    # 50ms
        "p95": 200,   # 200ms
        "p99": 500    # 500ms
    },
    "cache": {
        "l1_response_time_ms": 10,
        "l2_response_time_ms": 100,
        "overall_hit_rate": 70,
        "popular_hit_rate": 90
    },
    "database": {
        "connection_pool_size": 20,
        "query_timeout_ms": 1000,
        "slow_query_threshold_ms": 100
    },
    "throughput": {
        "requests_per_second": 1000,
        "concurrent_users": 100
    },
    "memory": {
        "max_memory_mb": 512,
        "max_cache_memory_mb": 100
    }
}


@dataclass
class PerformanceMetrics:
    """性能指标数据类"""
    endpoint: str
    method: str
    response_time_ms: float
    status_code: int
    timestamp: datetime
    memory_usage_mb: float
    cpu_percent: float
    cache_hit: bool = False
    db_queries: int = 0
    db_time_ms: float = 0.0
    ai_model_time_ms: float = 0.0
    error: Optional[str] = None


@dataclass 
class BenchmarkResult:
    """基准测试结果"""
    test_name: str
    duration_seconds: float
    requests_total: int
    requests_per_second: float
    response_times: List[float]
    percentiles: Dict[str, float]
    errors: int
    error_rate: float
    memory_peak_mb: float
    cpu_average_percent: float
    cache_hit_rate: float
    passed: bool
    recommendations: List[str]


class PerformanceAnalyzer:
    """性能分析器主类"""
    
    def __init__(self):
        self.metrics: List[PerformanceMetrics] = []
        self.profiler = None
        self.memory_tracker = None
        self.baseline_memory = 0
        self.start_time = None
        
    async def start_profiling(self, trace_memory: bool = True):
        """开始性能分析"""
        self.start_time = time.time()
        self.metrics = []
        
        # CPU profiling
        self.profiler = cProfile.Profile()
        self.profiler.enable()
        
        # Memory tracing
        if trace_memory:
            tracemalloc.start()
            self.baseline_memory = self._get_memory_usage()
            
        logger.info("Performance profiling started")
        
    async def stop_profiling(self) -> Dict[str, Any]:
        """停止性能分析并返回结果"""
        if self.profiler:
            self.profiler.disable()
            
        duration = time.time() - self.start_time if self.start_time else 0
        
        # 获取CPU分析结果
        cpu_stats = self._get_cpu_stats()
        
        # 获取内存分析结果
        memory_stats = self._get_memory_stats()
        
        # 停止内存追踪
        if tracemalloc.is_tracing():
            tracemalloc.stop()
            
        # 分析结果
        analysis = self._analyze_metrics()
        
        logger.info(f"Performance profiling stopped. Duration: {duration:.2f}s")
        
        return {
            "duration_seconds": duration,
            "metrics_collected": len(self.metrics),
            "cpu_profile": cpu_stats,
            "memory_profile": memory_stats,
            "analysis": analysis,
            "recommendations": self._generate_recommendations(analysis)
        }
        
    def _get_cpu_stats(self) -> Dict[str, Any]:
        """获取CPU分析统计"""
        if not self.profiler:
            return {}
            
        s = io.StringIO()
        ps = pstats.Stats(self.profiler, stream=s).sort_stats('cumulative')
        ps.print_stats(20)  # Top 20 functions
        
        return {
            "top_functions": s.getvalue(),
            "total_calls": ps.total_calls,
            "total_time": ps.total_tt
        }
        
    def _get_memory_stats(self) -> Dict[str, Any]:
        """获取内存分析统计"""
        current_memory = self._get_memory_usage()
        memory_diff = current_memory - self.baseline_memory
        
        stats = {
            "current_memory_mb": current_memory,
            "baseline_memory_mb": self.baseline_memory,
            "memory_increase_mb": memory_diff,
            "gc_stats": gc.get_stats()
        }
        
        if tracemalloc.is_tracing():
            snapshot = tracemalloc.take_snapshot()
            top_stats = snapshot.statistics('lineno')[:10]
            
            top_memory = []
            for stat in top_stats:
                top_memory.append({
                    "file": stat.traceback.format()[0],
                    "size_mb": stat.size / 1024 / 1024,
                    "count": stat.count
                })
            stats["top_memory_usage"] = top_memory
            
        return stats
        
    def _get_memory_usage(self) -> float:
        """获取当前内存使用量(MB)"""
        process = psutil.Process()
        return process.memory_info().rss / 1024 / 1024
        
    def _analyze_metrics(self) -> Dict[str, Any]:
        """分析收集的性能指标"""
        if not self.metrics:
            return {}
            
        response_times = [m.response_time_ms for m in self.metrics]
        
        return {
            "response_times": {
                "min": min(response_times),
                "max": max(response_times),
                "mean": statistics.mean(response_times),
                "median": statistics.median(response_times),
                "p95": np.percentile(response_times, 95),
                "p99": np.percentile(response_times, 99)
            },
            "cache": {
                "hit_rate": sum(1 for m in self.metrics if m.cache_hit) / len(self.metrics) * 100
            },
            "errors": {
                "count": sum(1 for m in self.metrics if m.error),
                "rate": sum(1 for m in self.metrics if m.error) / len(self.metrics) * 100
            },
            "database": {
                "avg_queries_per_request": statistics.mean([m.db_queries for m in self.metrics]),
                "avg_db_time_ms": statistics.mean([m.db_time_ms for m in self.metrics])
            }
        }
        
    def _generate_recommendations(self, analysis: Dict[str, Any]) -> List[str]:
        """生成性能优化建议"""
        recommendations = []
        
        # 响应时间建议
        if analysis.get("response_times", {}).get("p95", 0) > PERFORMANCE_TARGETS["api_response_time"]["p95"]:
            recommendations.append(
                f"响应时间P95 ({analysis['response_times']['p95']:.0f}ms) 超过目标 "
                f"({PERFORMANCE_TARGETS['api_response_time']['p95']}ms). "
                "建议: 优化慢查询, 增加缓存, 或使用异步处理"
            )
            
        # 缓存建议
        cache_hit_rate = analysis.get("cache", {}).get("hit_rate", 0)
        if cache_hit_rate < PERFORMANCE_TARGETS["cache"]["overall_hit_rate"]:
            recommendations.append(
                f"缓存命中率 ({cache_hit_rate:.1f}%) 低于目标 "
                f"({PERFORMANCE_TARGETS['cache']['overall_hit_rate']}%). "
                "建议: 实施缓存预热, 增加缓存TTL, 或优化缓存键策略"
            )
            
        # 数据库建议
        avg_db_time = analysis.get("database", {}).get("avg_db_time_ms", 0)
        if avg_db_time > PERFORMANCE_TARGETS["database"]["slow_query_threshold_ms"]:
            recommendations.append(
                f"平均数据库查询时间 ({avg_db_time:.0f}ms) 超过阈值 "
                f"({PERFORMANCE_TARGETS['database']['slow_query_threshold_ms']}ms). "
                "建议: 添加索引, 优化查询, 或使用查询缓存"
            )
            
        return recommendations
        
    async def record_metric(self, metric: PerformanceMetrics):
        """记录性能指标"""
        self.metrics.append(metric)
        
        # 同时存储到Redis用于实时监控
        await self._store_metric_to_redis(metric)
        
    async def _store_metric_to_redis(self, metric: PerformanceMetrics):
        """存储指标到Redis"""
        try:
            key = f"metrics:{metric.endpoint}:{metric.timestamp.timestamp()}"
            await redis_client.set(
                key,
                asdict(metric),
                ttl=3600  # 保留1小时
            )
        except Exception as e:
            logger.error(f"Failed to store metric to Redis: {e}")


class LoadTester:
    """负载测试工具"""
    
    def __init__(self, analyzer: PerformanceAnalyzer):
        self.analyzer = analyzer
        
    async def run_load_test(
        self,
        test_func: Callable,
        concurrent_users: int = 10,
        duration_seconds: int = 60,
        requests_per_user: Optional[int] = None
    ) -> BenchmarkResult:
        """运行负载测试"""
        logger.info(f"Starting load test: {concurrent_users} users, {duration_seconds}s duration")
        
        start_time = time.time()
        end_time = start_time + duration_seconds
        
        # 启动性能分析
        await self.analyzer.start_profiling()
        
        # 统计数据
        response_times = []
        errors = 0
        requests_completed = 0
        
        async def user_simulation():
            """模拟单个用户行为"""
            nonlocal errors, requests_completed
            
            user_requests = 0
            while time.time() < end_time:
                if requests_per_user and user_requests >= requests_per_user:
                    break
                    
                try:
                    req_start = time.time()
                    await test_func()
                    response_time = (time.time() - req_start) * 1000
                    response_times.append(response_time)
                    requests_completed += 1
                except Exception as e:
                    errors += 1
                    logger.error(f"Load test request failed: {e}")
                    
                user_requests += 1
                
                # 随机延迟模拟真实用户
                await asyncio.sleep(np.random.exponential(0.5))
                
        # 并发执行用户模拟
        tasks = [user_simulation() for _ in range(concurrent_users)]
        await asyncio.gather(*tasks)
        
        # 停止性能分析
        profile_results = await self.analyzer.stop_profiling()
        
        # 计算结果
        actual_duration = time.time() - start_time
        rps = requests_completed / actual_duration if actual_duration > 0 else 0
        
        # 计算百分位数
        percentiles = {}
        if response_times:
            percentiles = {
                "p50": np.percentile(response_times, 50),
                "p95": np.percentile(response_times, 95),
                "p99": np.percentile(response_times, 99)
            }
            
        # 检查是否通过性能目标
        passed = (
            rps >= PERFORMANCE_TARGETS["throughput"]["requests_per_second"] / 10 and
            percentiles.get("p95", float('inf')) <= PERFORMANCE_TARGETS["api_response_time"]["p95"]
        )
        
        result = BenchmarkResult(
            test_name=test_func.__name__,
            duration_seconds=actual_duration,
            requests_total=requests_completed,
            requests_per_second=rps,
            response_times=response_times,
            percentiles=percentiles,
            errors=errors,
            error_rate=errors / max(requests_completed, 1) * 100,
            memory_peak_mb=profile_results["memory_profile"]["current_memory_mb"],
            cpu_average_percent=psutil.cpu_percent(),
            cache_hit_rate=profile_results["analysis"].get("cache", {}).get("hit_rate", 0),
            passed=passed,
            recommendations=profile_results["recommendations"]
        )
        
        logger.info(f"Load test completed: {requests_completed} requests, {rps:.1f} RPS, "
                   f"P95: {percentiles.get('p95', 0):.0f}ms")
        
        return result


class DatabasePerformanceAnalyzer:
    """数据库性能分析器"""
    
    def __init__(self):
        self.slow_queries: List[Dict[str, Any]] = []
        
    async def analyze_slow_queries(self, db: AsyncSession) -> Dict[str, Any]:
        """分析慢查询"""
        try:
            # PostgreSQL慢查询分析
            result = await db.execute(
                text("""
                    SELECT 
                        query,
                        calls,
                        total_time,
                        mean_time,
                        max_time
                    FROM pg_stat_statements
                    WHERE mean_time > :threshold
                    ORDER BY mean_time DESC
                    LIMIT 20
                """),
                {"threshold": PERFORMANCE_TARGETS["database"]["slow_query_threshold_ms"]}
            )
            
            slow_queries = []
            for row in result:
                slow_queries.append({
                    "query": row[0][:100],  # 截断长查询
                    "calls": row[1],
                    "total_time_ms": row[2],
                    "mean_time_ms": row[3],
                    "max_time_ms": row[4]
                })
                
            return {
                "slow_queries": slow_queries,
                "recommendations": self._generate_db_recommendations(slow_queries)
            }
            
        except Exception as e:
            logger.error(f"Failed to analyze slow queries: {e}")
            return {"error": str(e)}
            
    async def check_connection_pool(self, db: AsyncSession) -> Dict[str, Any]:
        """检查连接池状态"""
        try:
            result = await db.execute(
                text("""
                    SELECT 
                        count(*) as total_connections,
                        count(*) FILTER (WHERE state = 'active') as active,
                        count(*) FILTER (WHERE state = 'idle') as idle,
                        count(*) FILTER (WHERE state = 'idle in transaction') as idle_in_transaction
                    FROM pg_stat_activity
                    WHERE datname = current_database()
                """)
            )
            
            row = result.first()
            return {
                "total_connections": row[0],
                "active": row[1],
                "idle": row[2],
                "idle_in_transaction": row[3],
                "pool_utilization": row[1] / PERFORMANCE_TARGETS["database"]["connection_pool_size"] * 100
            }
            
        except Exception as e:
            logger.error(f"Failed to check connection pool: {e}")
            return {"error": str(e)}
            
    async def analyze_table_performance(self, db: AsyncSession) -> Dict[str, Any]:
        """分析表性能"""
        try:
            # 查找缺失索引
            result = await db.execute(
                text("""
                    SELECT 
                        schemaname,
                        tablename,
                        attname,
                        n_distinct,
                        correlation
                    FROM pg_stats
                    WHERE schemaname = 'public'
                    AND n_distinct > 100
                    AND correlation < 0.1
                    ORDER BY n_distinct DESC
                    LIMIT 10
                """)
            )
            
            missing_indexes = []
            for row in result:
                missing_indexes.append({
                    "table": f"{row[0]}.{row[1]}",
                    "column": row[2],
                    "distinct_values": row[3],
                    "correlation": row[4]
                })
                
            return {
                "potential_missing_indexes": missing_indexes,
                "recommendations": [
                    f"Consider adding index on {item['table']}.{item['column']}"
                    for item in missing_indexes
                ]
            }
            
        except Exception as e:
            logger.error(f"Failed to analyze table performance: {e}")
            return {"error": str(e)}
            
    def _generate_db_recommendations(self, slow_queries: List[Dict]) -> List[str]:
        """生成数据库优化建议"""
        recommendations = []
        
        for query in slow_queries[:5]:  # Top 5 慢查询
            if query["mean_time_ms"] > 500:
                recommendations.append(
                    f"优化查询 (平均{query['mean_time_ms']:.0f}ms): "
                    f"{query['query'][:50]}..."
                )
                
        return recommendations


class CachePerformanceAnalyzer:
    """缓存性能分析器"""
    
    async def analyze_cache_performance(self) -> Dict[str, Any]:
        """分析缓存性能"""
        # 获取缓存统计
        cache_stats = await cache_manager.get_comprehensive_stats()
        
        analysis = {
            "current_performance": {
                "overall_hit_rate": cache_stats["overall"]["hit_rate_percent"],
                "l1_hit_rate": cache_stats["l1_memory"]["hit_rate_percent"],
                "l2_hit_rate": cache_stats["l2_redis"]["hit_rate_percent"],
                "popular_hit_rate": cache_stats["popular_items"]["hit_rate_percent"]
            },
            "targets": PERFORMANCE_TARGETS["cache"],
            "gaps": {},
            "recommendations": []
        }
        
        # 计算与目标的差距
        if cache_stats["overall"]["hit_rate_percent"] < PERFORMANCE_TARGETS["cache"]["overall_hit_rate"]:
            gap = PERFORMANCE_TARGETS["cache"]["overall_hit_rate"] - cache_stats["overall"]["hit_rate_percent"]
            analysis["gaps"]["overall_hit_rate"] = gap
            analysis["recommendations"].append(
                f"整体缓存命中率需提升 {gap:.1f}% 达到目标 {PERFORMANCE_TARGETS['cache']['overall_hit_rate']}%"
            )
            
        if cache_stats["popular_items"]["hit_rate_percent"] < PERFORMANCE_TARGETS["cache"]["popular_hit_rate"]:
            gap = PERFORMANCE_TARGETS["cache"]["popular_hit_rate"] - cache_stats["popular_items"]["hit_rate_percent"]
            analysis["gaps"]["popular_hit_rate"] = gap
            analysis["recommendations"].append(
                f"热门内容命中率需提升 {gap:.1f}% 达到目标 {PERFORMANCE_TARGETS['cache']['popular_hit_rate']}%"
            )
            
        # 内存使用分析
        l1_memory_usage = cache_stats["l1_memory"]["memory_mb"]
        if l1_memory_usage > PERFORMANCE_TARGETS["memory"]["max_cache_memory_mb"]:
            analysis["recommendations"].append(
                f"L1缓存内存使用 ({l1_memory_usage:.1f}MB) 超过限制 "
                f"({PERFORMANCE_TARGETS['memory']['max_cache_memory_mb']}MB)"
            )
            
        return analysis
        
    async def test_cache_response_times(self, iterations: int = 100) -> Dict[str, Any]:
        """测试缓存响应时间"""
        l1_times = []
        l2_times = []
        
        # 测试数据
        test_key = f"perf_test_{time.time()}"
        test_value = {"data": "x" * 1000}  # 1KB数据
        
        # 预热L2缓存
        await redis_client.set(f"cache:{test_key}", test_value, ttl=60)
        
        for _ in range(iterations):
            # 测试L1缓存
            await cache_manager.l1_cache.set(test_key, test_value, ttl=60)
            
            start = time.perf_counter()
            await cache_manager.l1_cache.get(test_key)
            l1_times.append((time.perf_counter() - start) * 1000)
            
            # 测试L2缓存
            start = time.perf_counter()
            await redis_client.get(f"cache:{test_key}")
            l2_times.append((time.perf_counter() - start) * 1000)
            
        return {
            "l1_cache": {
                "avg_ms": statistics.mean(l1_times),
                "p95_ms": np.percentile(l1_times, 95),
                "p99_ms": np.percentile(l1_times, 99),
                "meets_target": statistics.mean(l1_times) <= PERFORMANCE_TARGETS["cache"]["l1_response_time_ms"]
            },
            "l2_cache": {
                "avg_ms": statistics.mean(l2_times),
                "p95_ms": np.percentile(l2_times, 95),
                "p99_ms": np.percentile(l2_times, 99),
                "meets_target": statistics.mean(l2_times) <= PERFORMANCE_TARGETS["cache"]["l2_response_time_ms"]
            }
        }


# 装饰器：性能监控
def monitor_performance(endpoint: str = None):
    """性能监控装饰器"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            start_time = time.perf_counter()
            memory_before = psutil.Process().memory_info().rss / 1024 / 1024
            
            try:
                result = await func(*args, **kwargs)
                
                # 记录性能指标
                elapsed_ms = (time.perf_counter() - start_time) * 1000
                memory_after = psutil.Process().memory_info().rss / 1024 / 1024
                
                metric = PerformanceMetrics(
                    endpoint=endpoint or func.__name__,
                    method="ASYNC",
                    response_time_ms=elapsed_ms,
                    status_code=200,
                    timestamp=datetime.now(),
                    memory_usage_mb=memory_after - memory_before,
                    cpu_percent=psutil.cpu_percent()
                )
                
                # 异步记录，不阻塞主流程
                asyncio.create_task(performance_analyzer.record_metric(metric))
                
                # 慢请求警告
                if elapsed_ms > PERFORMANCE_TARGETS["api_response_time"]["p95"]:
                    logger.warning(f"Slow request detected: {endpoint} took {elapsed_ms:.0f}ms")
                    
                return result
                
            except Exception as e:
                logger.error(f"Error in {func.__name__}: {e}")
                raise
                
        return wrapper
    return decorator


# 全局性能分析器实例
performance_analyzer = PerformanceAnalyzer()
load_tester = LoadTester(performance_analyzer)
db_analyzer = DatabasePerformanceAnalyzer()
cache_analyzer = CachePerformanceAnalyzer()


# 性能分析API
async def run_performance_analysis() -> Dict[str, Any]:
    """运行完整的性能分析"""
    logger.info("Starting comprehensive performance analysis...")
    
    results = {
        "timestamp": datetime.now().isoformat(),
        "cache_performance": await cache_analyzer.analyze_cache_performance(),
        "cache_response_times": await cache_analyzer.test_cache_response_times(),
        "recommendations": []
    }
    
    # 数据库性能分析
    async for db in get_db():
        results["database"] = {
            "connection_pool": await db_analyzer.check_connection_pool(db),
            "slow_queries": await db_analyzer.analyze_slow_queries(db),
            "table_performance": await db_analyzer.analyze_table_performance(db)
        }
        
    # 汇总建议
    all_recommendations = []
    all_recommendations.extend(results["cache_performance"].get("recommendations", []))
    all_recommendations.extend(results.get("database", {}).get("slow_queries", {}).get("recommendations", []))
    all_recommendations.extend(results.get("database", {}).get("table_performance", {}).get("recommendations", []))
    
    results["recommendations"] = all_recommendations
    results["performance_score"] = calculate_performance_score(results)
    
    logger.info(f"Performance analysis completed. Score: {results['performance_score']}/100")
    
    return results


def calculate_performance_score(analysis: Dict[str, Any]) -> int:
    """计算综合性能评分 (0-100)"""
    score = 100
    
    # 缓存命中率评分 (30分)
    cache_hit_rate = analysis.get("cache_performance", {}).get("current_performance", {}).get("overall_hit_rate", 0)
    cache_target = PERFORMANCE_TARGETS["cache"]["overall_hit_rate"]
    cache_score = min(30, (cache_hit_rate / cache_target) * 30)
    score = score - 30 + cache_score
    
    # 响应时间评分 (30分)
    l1_meets = analysis.get("cache_response_times", {}).get("l1_cache", {}).get("meets_target", False)
    l2_meets = analysis.get("cache_response_times", {}).get("l2_cache", {}).get("meets_target", False)
    response_score = (15 if l1_meets else 0) + (15 if l2_meets else 0)
    score = score - 30 + response_score
    
    # 数据库性能评分 (20分)
    pool_util = analysis.get("database", {}).get("connection_pool", {}).get("pool_utilization", 100)
    db_score = min(20, (1 - pool_util / 100) * 20) if pool_util < 80 else 0
    score = score - 20 + db_score
    
    # 错误率评分 (20分)
    # 暂时给满分，因为没有错误率数据
    error_score = 20
    score = score - 20 + error_score
    
    return max(0, min(100, int(score)))