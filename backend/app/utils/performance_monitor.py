"""
Performance Monitor
Tracks and monitors API request performance metrics
"""

import logging
import time
from collections import deque
from functools import wraps
from typing import Callable

import numpy as np

logger = logging.getLogger(__name__)


class PerformanceMonitor:
    """Monitor and track performance metrics for requests"""

    def __init__(self, max_history: int = 1000):
        """
        Initialize performance monitor

        Args:
            max_history: Maximum number of request times to keep in memory
        """
        self.request_times: deque = deque(maxlen=max_history)
        self.max_history = max_history

    def track_request_time(self, duration: float) -> None:
        """
        Record request time

        Args:
            duration: Request duration in seconds
        """
        self.request_times.append(duration)
        logger.debug(f"Tracked request time: {duration:.3f}s")

    def get_p95_latency(self) -> float:
        """
        Calculate P95 latency

        Returns:
            P95 latency in seconds (0.0 if no data)
        """
        if not self.request_times:
            return 0.0
        return float(np.percentile(list(self.request_times), 95))

    def get_p99_latency(self) -> float:
        """
        Calculate P99 latency

        Returns:
            P99 latency in seconds (0.0 if no data)
        """
        if not self.request_times:
            return 0.0
        return float(np.percentile(list(self.request_times), 99))

    def get_average_latency(self) -> float:
        """
        Calculate average latency

        Returns:
            Average latency in seconds (0.0 if no data)
        """
        if not self.request_times:
            return 0.0
        return sum(self.request_times) / len(self.request_times)

    def get_min_latency(self) -> float:
        """
        Get minimum latency

        Returns:
            Minimum latency in seconds (0.0 if no data)
        """
        if not self.request_times:
            return 0.0
        return min(self.request_times)

    def get_max_latency(self) -> float:
        """
        Get maximum latency

        Returns:
            Maximum latency in seconds (0.0 if no data)
        """
        if not self.request_times:
            return 0.0
        return max(self.request_times)

    def get_stats(self) -> dict:
        """
        Get comprehensive performance statistics

        Returns:
            Dictionary containing all performance metrics
        """
        if not self.request_times:
            return {
                "total_requests": 0,
                "average_latency": 0.0,
                "p95_latency": 0.0,
                "p99_latency": 0.0,
                "min_latency": 0.0,
                "max_latency": 0.0,
            }

        return {
            "total_requests": len(self.request_times),
            "average_latency": self.get_average_latency(),
            "p95_latency": self.get_p95_latency(),
            "p99_latency": self.get_p99_latency(),
            "min_latency": self.get_min_latency(),
            "max_latency": self.get_max_latency(),
        }

    def clear_stats(self) -> None:
        """Clear all stored statistics"""
        self.request_times.clear()
        logger.info("Performance statistics cleared")

    def check_performance_threshold(self, threshold: float = 5.0) -> dict:
        """
        Check if any requests exceeded the performance threshold

        Args:
            threshold: Performance threshold in seconds

        Returns:
            Dictionary with threshold check results
        """
        if not self.request_times:
            return {
                "threshold": threshold,
                "violations": 0,
                "total_requests": 0,
                "violation_rate": 0.0,
            }

        violations = sum(1 for t in self.request_times if t > threshold)
        total = len(self.request_times)
        violation_rate = violations / total if total > 0 else 0.0

        return {
            "threshold": threshold,
            "violations": violations,
            "total_requests": total,
            "violation_rate": violation_rate,
        }


# Global performance monitor instance
_performance_monitor = PerformanceMonitor()


def get_performance_monitor() -> PerformanceMonitor:
    """
    Get global performance monitor instance

    Returns:
        PerformanceMonitor singleton instance
    """
    return _performance_monitor


def monitor_performance(threshold: float = 5.0):
    """
    Decorator to monitor async function performance

    Args:
        threshold: Warning threshold in seconds

    Example:
        @monitor_performance(threshold=5.0)
        async def my_function():
            pass
    """

    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = await func(*args, **kwargs)
                return result
            finally:
                duration = time.time() - start_time
                logger.info(f"{func.__name__} took {duration:.3f}s")

                # Track in global monitor
                monitor = get_performance_monitor()
                monitor.track_request_time(duration)

                # Log warning if threshold exceeded
                if duration > threshold:
                    logger.warning(
                        f"{func.__name__} exceeded {threshold}s threshold: "
                        f"{duration:.3f}s"
                    )

        return wrapper

    return decorator


def monitor_sync_performance(threshold: float = 5.0):
    """
    Decorator to monitor synchronous function performance

    Args:
        threshold: Warning threshold in seconds

    Example:
        @monitor_sync_performance(threshold=5.0)
        def my_function():
            pass
    """

    def decorator(func: Callable):
        @wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                return result
            finally:
                duration = time.time() - start_time
                logger.info(f"{func.__name__} took {duration:.3f}s")

                # Track in global monitor
                monitor = get_performance_monitor()
                monitor.track_request_time(duration)

                # Log warning if threshold exceeded
                if duration > threshold:
                    logger.warning(
                        f"{func.__name__} exceeded {threshold}s threshold: "
                        f"{duration:.3f}s"
                    )

        return wrapper

    return decorator
