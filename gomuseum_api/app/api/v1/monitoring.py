from fastapi import APIRouter, Depends, HTTPException, status
from typing import Dict, Any, Optional
from datetime import datetime, timedelta

from app.core.auth import require_enterprise, get_current_user
from app.core.metrics import metrics, start_metrics_collection
from app.core.redis_client import redis_client, get_cache_key
from app.core.database import test_connection
from app.core.logging import get_logger
from app.schemas.common import success_response

router = APIRouter()
logger = get_logger(__name__)


@router.get("/monitoring/health")
async def health_check():
    """Comprehensive health check for monitoring systems"""
    health_status = {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "checks": {}
    }
    
    # Database health
    try:
        db_healthy = test_connection()
        health_status["checks"]["database"] = {
            "status": "healthy" if db_healthy else "unhealthy",
            "response_time_ms": 0  # Could add timing here
        }
    except Exception as e:
        health_status["checks"]["database"] = {
            "status": "unhealthy",
            "error": str(e)
        }
    
    # Redis health
    try:
        if redis_client.redis:
            start_time = datetime.now()
            await redis_client.redis.ping()
            response_time = (datetime.now() - start_time).total_seconds() * 1000
            
            health_status["checks"]["redis"] = {
                "status": "healthy",
                "response_time_ms": response_time
            }
        else:
            health_status["checks"]["redis"] = {
                "status": "disconnected"
            }
    except Exception as e:
        health_status["checks"]["redis"] = {
            "status": "unhealthy",
            "error": str(e)
        }
    
    # Overall status
    unhealthy_checks = [
        check for check in health_status["checks"].values()
        if check.get("status") != "healthy"
    ]
    
    if unhealthy_checks:
        health_status["status"] = "degraded"
        if len(unhealthy_checks) >= 2:
            health_status["status"] = "unhealthy"
    
    return health_status


@router.get("/monitoring/metrics")
async def get_metrics(
    current_user: Optional[Dict[str, Any]] = Depends(get_current_user)
):
    """Get current metrics summary"""
    
    # Basic metrics available to all authenticated users
    if not current_user:
        # Anonymous users get limited metrics
        return success_response({
            "api": {
                "total_requests": metrics.counters.get("api_requests_total", 0),
                "error_rate_percent": 0
            },
            "cache": {
                "hit_rate_percent": metrics.gauges.get("redis_hit_rate_percent", 0)
            }
        })
    
    # Authenticated users get more detailed metrics
    summary = metrics.get_summary()
    
    # Enterprise users get full metrics
    if current_user.get("subscription_type") == "enterprise":
        return success_response(summary)
    
    # Regular users get filtered metrics
    return success_response({
        "api": summary.get("api", {}),
        "cache": summary.get("cache", {}),
        "timestamp": summary.get("timestamp")
    })


@router.get("/monitoring/metrics/detailed")
async def get_detailed_metrics(
    current_user: dict = Depends(require_enterprise)
):
    """Get detailed metrics (enterprise only)"""
    
    summary = metrics.get_summary()
    
    # Add additional detailed information
    detailed = {
        **summary,
        "detailed": {
            "top_endpoints": await _get_top_endpoints(),
            "slow_queries": await _get_slow_queries(),
            "error_breakdown": await _get_error_breakdown(),
            "user_activity": await _get_user_activity_stats()
        }
    }
    
    return success_response(detailed)


@router.get("/monitoring/metrics/history")
async def get_metrics_history(
    current_user: dict = Depends(require_enterprise),
    hours: int = 24
):
    """Get historical metrics data"""
    
    if hours > 168:  # Limit to 1 week
        hours = 168
    
    try:
        # Get historical metrics from Redis
        end_time = int(datetime.now().timestamp())
        start_time = end_time - (hours * 3600)
        
        historical_data = []
        
        # Sample every hour for the requested period
        for timestamp in range(start_time, end_time, 3600):
            key = get_cache_key("metrics", "historical", str(timestamp))
            data = await redis_client.get(key)
            if data:
                historical_data.append(data)
        
        return success_response({
            "period_hours": hours,
            "data_points": len(historical_data),
            "metrics": historical_data
        })
        
    except Exception as e:
        logger.error(f"Failed to get metrics history: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "metrics_error", "message": "Failed to retrieve metrics history"}
        )


@router.post("/monitoring/metrics/reset")
async def reset_metrics(
    current_user: dict = Depends(require_enterprise)
):
    """Reset all metrics counters (enterprise only)"""
    
    metrics.reset_counters()
    
    logger.info(f"Metrics reset by user: {current_user['email']}")
    
    return success_response({"message": "Metrics counters reset successfully"})


@router.get("/monitoring/alerts")
async def get_alerts(
    current_user: dict = Depends(require_enterprise)
):
    """Get current system alerts based on metrics"""
    
    alerts = []
    summary = metrics.get_summary()
    
    # Check system metrics for alerts
    system_metrics = summary.get("system", {})
    
    # CPU usage alert
    cpu_current = system_metrics.get("cpu_percent", {}).get("current", 0)
    if cpu_current > 80:
        alerts.append({
            "severity": "warning" if cpu_current < 90 else "critical",
            "metric": "cpu_usage",
            "message": f"High CPU usage: {cpu_current:.1f}%",
            "value": cpu_current,
            "threshold": 80
        })
    
    # Memory usage alert
    memory_current = system_metrics.get("memory_percent", {}).get("current", 0)
    if memory_current > 85:
        alerts.append({
            "severity": "warning" if memory_current < 95 else "critical",
            "metric": "memory_usage",
            "message": f"High memory usage: {memory_current:.1f}%",
            "value": memory_current,
            "threshold": 85
        })
    
    # Error rate alert
    api_metrics = summary.get("api", {})
    error_rate = api_metrics.get("error_rate_percent", 0)
    if error_rate > 5:
        alerts.append({
            "severity": "warning" if error_rate < 10 else "critical",
            "metric": "error_rate",
            "message": f"High error rate: {error_rate:.1f}%",
            "value": error_rate,
            "threshold": 5
        })
    
    # Cache hit rate alert
    cache_metrics = summary.get("cache", {})
    hit_rate = cache_metrics.get("hit_rate_percent", 100)
    if hit_rate < 70:
        alerts.append({
            "severity": "warning",
            "metric": "cache_hit_rate",
            "message": f"Low cache hit rate: {hit_rate:.1f}%",
            "value": hit_rate,
            "threshold": 70
        })
    
    return success_response({
        "alerts": alerts,
        "total_alerts": len(alerts),
        "critical_count": len([a for a in alerts if a["severity"] == "critical"]),
        "warning_count": len([a for a in alerts if a["severity"] == "warning"])
    })


@router.get("/monitoring/performance")
async def get_performance_metrics(
    current_user: dict = Depends(require_enterprise)
):
    """Get performance-specific metrics"""
    
    performance_data = {
        "response_times": {
            "api_avg_ms": metrics._get_avg_response_time() * 1000,
            "p95_ms": await _get_percentile_response_time(95),
            "p99_ms": await _get_percentile_response_time(99)
        },
        "throughput": {
            "requests_per_minute": await _get_requests_per_minute(),
            "recognition_requests_per_hour": await _get_recognition_requests_per_hour()
        },
        "database": {
            "avg_query_time_ms": await _get_avg_db_query_time(),
            "slow_query_count": await _get_slow_query_count()
        },
        "cache": {
            "hit_rate_percent": metrics.gauges.get("redis_hit_rate_percent", 0),
            "memory_usage_mb": metrics.gauges.get("redis_memory_usage_mb", 0)
        }
    }
    
    return success_response(performance_data)


# Helper functions for detailed metrics
async def _get_top_endpoints() -> list:
    """Get top API endpoints by request count"""
    # This would require more sophisticated tracking
    # For now, return mock data
    return [
        {"endpoint": "/api/v1/recognize", "requests": 150, "avg_time_ms": 250},
        {"endpoint": "/api/v1/user/quota", "requests": 89, "avg_time_ms": 45},
        {"endpoint": "/health", "requests": 45, "avg_time_ms": 12}
    ]


async def _get_slow_queries() -> list:
    """Get slow database queries"""
    # This would require query monitoring integration
    return []


async def _get_error_breakdown() -> dict:
    """Get error breakdown by type and endpoint"""
    return {
        "400": metrics.counters.get("api_errors_400", 0),
        "401": metrics.counters.get("api_errors_401", 0),
        "403": metrics.counters.get("api_errors_403", 0),
        "404": metrics.counters.get("api_errors_404", 0),
        "500": metrics.counters.get("api_errors_500", 0)
    }


async def _get_user_activity_stats() -> dict:
    """Get user activity statistics"""
    return {
        "active_users_today": await _count_active_users(24),
        "active_users_week": await _count_active_users(168),
        "quota_usage_avg": await _get_average_quota_usage()
    }


async def _count_active_users(hours: int) -> int:
    """Count active users in the last N hours"""
    # This would require user activity tracking
    return 0


async def _get_average_quota_usage() -> float:
    """Get average quota usage across all users"""
    # This would require user quota tracking
    return 0.0


async def _get_percentile_response_time(percentile: int) -> float:
    """Get percentile response time"""
    all_durations = []
    for durations in metrics.request_durations.values():
        all_durations.extend(durations)
    
    if not all_durations:
        return 0.0
    
    all_durations.sort()
    index = int(len(all_durations) * percentile / 100)
    return all_durations[min(index, len(all_durations) - 1)] * 1000  # Convert to ms


async def _get_requests_per_minute() -> float:
    """Get requests per minute rate"""
    total_requests = metrics.counters.get("api_requests_total", 0)
    # This is a simplified calculation - would need time window tracking
    return total_requests / 60.0  # Assume running for 1 hour


async def _get_recognition_requests_per_hour() -> float:
    """Get recognition requests per hour"""
    # This would need specific tracking for recognition endpoints
    return 0.0


async def _get_avg_db_query_time() -> float:
    """Get average database query time"""
    # This would need database query time tracking
    return 0.0


async def _get_slow_query_count() -> int:
    """Get count of slow queries"""
    # This would need slow query tracking
    return 0