"""
Advanced Cache Warmer and Monitor
高级缓存预热和监控系统
"""

import asyncio
import time
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Set
from collections import defaultdict
import json

from app.core.logging import get_logger
from app.core.cache_strategy import cache_manager, CacheStrategy
from app.core.redis_client import redis_client
from app.core.database import get_db
from app.repositories.recognition_repository import RecognitionRepository
from sqlalchemy import text

logger = get_logger(__name__)


class CacheWarmer:
    """智能缓存预热器"""
    
    def __init__(self):
        self.warming_patterns = {
            "popular_artworks": self._warm_popular_artworks,
            "user_quotas": self._warm_user_quotas,
            "museum_collections": self._warm_museum_collections,
            "recent_recognitions": self._warm_recent_recognitions
        }
        
        # 预热配置
        self.config = {
            "popular_threshold": 10,  # 访问次数阈值
            "recent_hours": 24,  # 最近N小时
            "batch_size": 50,  # 批处理大小
            "max_items": 200,  # 最大预热项数
            "ttl_multiplier": 1.5  # TTL倍数
        }
        
        # 监控数据
        self.stats = {
            "warmed_items": 0,
            "failed_items": 0,
            "last_warm_time": None,
            "warm_duration_ms": 0
        }
        
    async def warm_all(self, patterns: Optional[List[str]] = None):
        """执行全部预热"""
        start_time = time.perf_counter()
        patterns = patterns or list(self.warming_patterns.keys())
        
        logger.info(f"Starting cache warming for patterns: {patterns}")
        
        warmed_total = 0
        failed_total = 0
        
        for pattern in patterns:
            if pattern in self.warming_patterns:
                try:
                    warmed, failed = await self.warming_patterns[pattern]()
                    warmed_total += warmed
                    failed_total += failed
                    logger.info(f"Pattern '{pattern}': warmed {warmed}, failed {failed}")
                except Exception as e:
                    logger.error(f"Failed to warm pattern '{pattern}': {e}")
                    failed_total += 1
        
        # 更新统计
        self.stats["warmed_items"] = warmed_total
        self.stats["failed_items"] = failed_total
        self.stats["last_warm_time"] = datetime.utcnow()
        self.stats["warm_duration_ms"] = (time.perf_counter() - start_time) * 1000
        
        logger.info(f"Cache warming completed in {self.stats['warm_duration_ms']:.2f}ms. "
                   f"Warmed: {warmed_total}, Failed: {failed_total}")
        
        return warmed_total, failed_total
    
    async def _warm_popular_artworks(self) -> tuple[int, int]:
        """预热热门艺术品"""
        warmed = 0
        failed = 0
        
        async for db in get_db():
            repo = RecognitionRepository(db)
            
            # 获取热门识别结果
            popular_items = await repo.get_popular_recognitions(
                limit=self.config["max_items"]
            )
            
            for item in popular_items:
                try:
                    # 获取完整数据
                    recognition = await repo.get_by_image_hash(
                        item["image_hash"],
                        include_candidates=True
                    )
                    
                    if recognition:
                        # 缓存结果
                        cache_key = f"recognition:result:{item['image_hash']}"
                        ttl = int(3600 * self.config["ttl_multiplier"])  # 延长TTL
                        
                        await cache_manager.set(
                            key=cache_key,
                            value=recognition.to_dict(),
                            ttl=ttl,
                            strategy=CacheStrategy.WRITE_THROUGH,
                            is_popular=True
                        )
                        
                        # 标记为热门
                        cache_manager.mark_popular_items([cache_key])
                        warmed += 1
                        
                except Exception as e:
                    logger.error(f"Failed to warm artwork {item.get('image_hash', 'unknown')}: {e}")
                    failed += 1
            
            break  # 只使用一个数据库连接
        
        return warmed, failed
    
    async def _warm_user_quotas(self) -> tuple[int, int]:
        """预热活跃用户配额"""
        warmed = 0
        failed = 0
        
        async for db in get_db():
            # 查找活跃用户
            result = await db.execute(
                text("""
                    SELECT DISTINCT user_id
                    FROM recognition_results
                    WHERE created_at > :cutoff
                    ORDER BY created_at DESC
                    LIMIT :limit
                """),
                {
                    "cutoff": datetime.utcnow() - timedelta(hours=self.config["recent_hours"]),
                    "limit": self.config["max_items"]
                }
            )
            
            for row in result:
                user_id = str(row[0])
                try:
                    # 模拟配额数据
                    quota_data = {
                        "user_id": user_id,
                        "daily_limit": 100,
                        "used_today": 0,
                        "reset_time": (datetime.utcnow() + timedelta(days=1)).isoformat()
                    }
                    
                    cache_key = f"user:quota:{user_id}"
                    await cache_manager.set(
                        key=cache_key,
                        value=quota_data,
                        ttl=3600,
                        strategy=CacheStrategy.WRITE_THROUGH
                    )
                    warmed += 1
                    
                except Exception as e:
                    logger.error(f"Failed to warm user quota for {user_id}: {e}")
                    failed += 1
            
            break
        
        return warmed, failed
    
    async def _warm_museum_collections(self) -> tuple[int, int]:
        """预热博物馆收藏"""
        warmed = 0
        failed = 0
        
        # 热门博物馆列表
        museums = ["louvre", "met", "british_museum", "national_gallery"]
        
        for museum_id in museums:
            try:
                # 模拟博物馆数据
                collection_data = {
                    "museum_id": museum_id,
                    "name": f"{museum_id.replace('_', ' ').title()}",
                    "total_artworks": 1000,
                    "featured_artworks": [],
                    "last_updated": datetime.utcnow().isoformat()
                }
                
                cache_key = f"museum:collection:{museum_id}"
                await cache_manager.set(
                    key=cache_key,
                    value=collection_data,
                    ttl=7200,  # 2小时
                    strategy=CacheStrategy.WRITE_THROUGH,
                    museum_id=museum_id
                )
                
                # 设置博物馆上下文
                cache_manager.set_museum_context(museum_id)
                warmed += 1
                
            except Exception as e:
                logger.error(f"Failed to warm museum collection {museum_id}: {e}")
                failed += 1
        
        return warmed, failed
    
    async def _warm_recent_recognitions(self) -> tuple[int, int]:
        """预热最近的识别结果"""
        warmed = 0
        failed = 0
        
        async for db in get_db():
            repo = RecognitionRepository(db)
            
            # 获取最近24小时的识别结果
            result = await db.execute(
                text("""
                    SELECT id, image_hash
                    FROM recognition_results
                    WHERE created_at > :cutoff
                        AND status = 'completed'
                        AND confidence > 0.7
                    ORDER BY created_at DESC
                    LIMIT :limit
                """),
                {
                    "cutoff": datetime.utcnow() - timedelta(hours=self.config["recent_hours"]),
                    "limit": self.config["batch_size"]
                }
            )
            
            for row in result:
                try:
                    recognition_id = row[0]
                    image_hash = row[1]
                    
                    # 获取完整数据
                    recognition = await repo.get_by_id(recognition_id, include_candidates=True)
                    
                    if recognition:
                        cache_key = f"recognition:result:{image_hash}"
                        await cache_manager.set(
                            key=cache_key,
                            value=recognition.to_dict(),
                            ttl=3600,
                            strategy=CacheStrategy.WRITE_BACK
                        )
                        warmed += 1
                        
                except Exception as e:
                    logger.error(f"Failed to warm recent recognition: {e}")
                    failed += 1
            
            break
        
        return warmed, failed
    
    def get_stats(self) -> Dict[str, Any]:
        """获取预热统计"""
        return {
            **self.stats,
            "config": self.config
        }


class CacheMonitor:
    """缓存监控器"""
    
    def __init__(self):
        self.metrics = defaultdict(lambda: defaultdict(int))
        self.alert_thresholds = {
            "hit_rate_min": 60,  # 最低命中率
            "response_time_max_ms": 100,  # 最大响应时间
            "memory_usage_max_mb": 100,  # 最大内存使用
            "eviction_rate_max": 20  # 最大驱逐率
        }
        self.alerts: List[Dict[str, Any]] = []
        
    async def collect_metrics(self):
        """收集缓存指标"""
        try:
            # 获取缓存统计
            stats = await cache_manager.get_comprehensive_stats()
            
            # 记录指标
            timestamp = datetime.utcnow()
            self.metrics[timestamp]["hit_rate"] = stats["overall"]["hit_rate_percent"]
            self.metrics[timestamp]["l1_hit_rate"] = stats["l1_memory"]["hit_rate_percent"]
            self.metrics[timestamp]["l2_hit_rate"] = stats["l2_redis"]["hit_rate_percent"]
            self.metrics[timestamp]["memory_mb"] = stats["l1_memory"]["memory_mb"]
            self.metrics[timestamp]["total_requests"] = stats["overall"]["total_requests"]
            
            # 检查告警条件
            await self._check_alerts(stats)
            
            # 清理旧数据（保留1小时）
            cutoff = datetime.utcnow() - timedelta(hours=1)
            self.metrics = defaultdict(
                lambda: defaultdict(int),
                {k: v for k, v in self.metrics.items() if k > cutoff}
            )
            
        except Exception as e:
            logger.error(f"Failed to collect cache metrics: {e}")
    
    async def _check_alerts(self, stats: Dict[str, Any]):
        """检查告警条件"""
        alerts = []
        
        # 命中率告警
        hit_rate = stats["overall"]["hit_rate_percent"]
        if hit_rate < self.alert_thresholds["hit_rate_min"]:
            alerts.append({
                "level": "WARNING",
                "type": "LOW_HIT_RATE",
                "message": f"Cache hit rate ({hit_rate:.1f}%) below threshold ({self.alert_thresholds['hit_rate_min']}%)",
                "value": hit_rate,
                "threshold": self.alert_thresholds["hit_rate_min"]
            })
        
        # 内存告警
        memory_mb = stats["l1_memory"]["memory_mb"]
        if memory_mb > self.alert_thresholds["memory_usage_max_mb"]:
            alerts.append({
                "level": "WARNING",
                "type": "HIGH_MEMORY",
                "message": f"L1 cache memory ({memory_mb:.1f}MB) exceeds limit ({self.alert_thresholds['memory_usage_max_mb']}MB)",
                "value": memory_mb,
                "threshold": self.alert_thresholds["memory_usage_max_mb"]
            })
        
        # 记录告警
        if alerts:
            for alert in alerts:
                alert["timestamp"] = datetime.utcnow().isoformat()
                self.alerts.append(alert)
                logger.warning(f"Cache alert: {alert['message']}")
        
        # 清理旧告警（保留最近100条）
        if len(self.alerts) > 100:
            self.alerts = self.alerts[-100:]
    
    async def analyze_patterns(self) -> Dict[str, Any]:
        """分析缓存访问模式"""
        if not self.metrics:
            return {"message": "No metrics available"}
        
        # 计算趋势
        timestamps = sorted(self.metrics.keys())
        recent_metrics = [self.metrics[ts] for ts in timestamps[-10:]]  # 最近10个数据点
        
        if len(recent_metrics) < 2:
            return {"message": "Insufficient data for pattern analysis"}
        
        # 计算平均值和趋势
        avg_hit_rate = sum(m["hit_rate"] for m in recent_metrics) / len(recent_metrics)
        hit_rate_trend = recent_metrics[-1]["hit_rate"] - recent_metrics[0]["hit_rate"]
        
        avg_memory = sum(m["memory_mb"] for m in recent_metrics) / len(recent_metrics)
        memory_trend = recent_metrics[-1]["memory_mb"] - recent_metrics[0]["memory_mb"]
        
        return {
            "average_hit_rate": avg_hit_rate,
            "hit_rate_trend": "increasing" if hit_rate_trend > 0 else "decreasing",
            "hit_rate_change": hit_rate_trend,
            "average_memory_mb": avg_memory,
            "memory_trend": "increasing" if memory_trend > 0 else "decreasing",
            "memory_change_mb": memory_trend,
            "data_points": len(recent_metrics),
            "recommendations": self._generate_recommendations(avg_hit_rate, avg_memory, hit_rate_trend)
        }
    
    def _generate_recommendations(
        self,
        avg_hit_rate: float,
        avg_memory: float,
        hit_rate_trend: float
    ) -> List[str]:
        """生成优化建议"""
        recommendations = []
        
        if avg_hit_rate < 70:
            recommendations.append("考虑增加缓存预热频率或扩大预热范围")
            
        if avg_hit_rate < 50:
            recommendations.append("检查缓存键策略，可能存在缓存未命中的模式")
            
        if hit_rate_trend < -5:
            recommendations.append("缓存命中率下降明显，建议检查访问模式变化")
            
        if avg_memory > 80:
            recommendations.append("L1缓存内存使用较高，考虑调整驱逐策略或增加内存限制")
            
        if not recommendations:
            recommendations.append("缓存性能良好，保持当前配置")
            
        return recommendations
    
    def get_alerts(self, level: Optional[str] = None) -> List[Dict[str, Any]]:
        """获取告警"""
        if level:
            return [a for a in self.alerts if a["level"] == level]
        return self.alerts
    
    def clear_alerts(self):
        """清除告警"""
        self.alerts.clear()


class AdaptiveCacheOptimizer:
    """自适应缓存优化器"""
    
    def __init__(self, warmer: CacheWarmer, monitor: CacheMonitor):
        self.warmer = warmer
        self.monitor = monitor
        self.optimization_history = []
        
    async def optimize(self):
        """执行自适应优化"""
        logger.info("Starting adaptive cache optimization")
        
        # 收集当前指标
        await self.monitor.collect_metrics()
        
        # 分析模式
        pattern_analysis = await self.monitor.analyze_patterns()
        
        # 根据分析结果调整策略
        if pattern_analysis.get("average_hit_rate", 100) < 60:
            # 命中率低，执行预热
            logger.info("Low hit rate detected, performing cache warming")
            await self.warmer.warm_all()
            
        elif pattern_analysis.get("hit_rate_trend") == "decreasing":
            # 命中率下降，预热最近数据
            logger.info("Decreasing hit rate trend, warming recent data")
            await self.warmer.warm_all(["recent_recognitions"])
            
        # 记录优化历史
        self.optimization_history.append({
            "timestamp": datetime.utcnow().isoformat(),
            "analysis": pattern_analysis,
            "actions": ["warm_all"] if pattern_analysis.get("average_hit_rate", 100) < 60 else []
        })
        
        # 保留最近100条历史
        if len(self.optimization_history) > 100:
            self.optimization_history = self.optimization_history[-100:]
        
        logger.info("Adaptive cache optimization completed")
    
    def get_optimization_history(self) -> List[Dict[str, Any]]:
        """获取优化历史"""
        return self.optimization_history


# 全局实例
cache_warmer = CacheWarmer()
cache_monitor = CacheMonitor()
cache_optimizer = AdaptiveCacheOptimizer(cache_warmer, cache_monitor)


# 后台任务
async def periodic_cache_warming():
    """定期缓存预热任务"""
    while True:
        try:
            await cache_warmer.warm_all()
            await asyncio.sleep(3600)  # 每小时执行一次
        except Exception as e:
            logger.error(f"Periodic cache warming failed: {e}")
            await asyncio.sleep(1800)  # 失败后30分钟重试


async def periodic_cache_monitoring():
    """定期缓存监控任务"""
    while True:
        try:
            await cache_monitor.collect_metrics()
            await asyncio.sleep(60)  # 每分钟收集一次
        except Exception as e:
            logger.error(f"Periodic cache monitoring failed: {e}")
            await asyncio.sleep(30)


async def periodic_cache_optimization():
    """定期缓存优化任务"""
    while True:
        try:
            await cache_optimizer.optimize()
            await asyncio.sleep(1800)  # 每30分钟优化一次
        except Exception as e:
            logger.error(f"Periodic cache optimization failed: {e}")
            await asyncio.sleep(900)  # 失败后15分钟重试


# 启动函数
async def start_cache_management():
    """启动缓存管理系统"""
    logger.info("Starting cache management system")
    
    # 初始预热
    await cache_warmer.warm_all()
    
    # 启动后台任务
    tasks = [
        asyncio.create_task(periodic_cache_warming()),
        asyncio.create_task(periodic_cache_monitoring()),
        asyncio.create_task(periodic_cache_optimization())
    ]
    
    logger.info("Cache management system started with 3 background tasks")
    
    return tasks