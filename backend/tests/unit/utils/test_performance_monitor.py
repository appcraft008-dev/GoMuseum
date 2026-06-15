"""
Comprehensive Unit tests for Performance Monitor
Tests request performance tracking and metrics calculation with full coverage
"""

import asyncio
import time
from collections import deque
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from app.utils.performance_monitor import (
    PerformanceMonitor,
    get_performance_monitor,
    monitor_performance,
    monitor_sync_performance,
)


class TestPerformanceMonitor:
    """Test suite for PerformanceMonitor class"""

    def test_initialization(self):
        """Test PerformanceMonitor initialization"""
        monitor = PerformanceMonitor(max_history=500)
        assert monitor.max_history == 500
        assert len(monitor.request_times) == 0
        assert isinstance(monitor.request_times, deque)

    def test_default_initialization(self):
        """Test default initialization"""
        monitor = PerformanceMonitor()
        assert monitor.max_history == 1000
        assert len(monitor.request_times) == 0

    def test_tracks_request_duration(self):
        """should_record_request_processing_time"""
        monitor = PerformanceMonitor()

        # Track several request times
        monitor.track_request_time(1.5)
        monitor.track_request_time(2.0)
        monitor.track_request_time(0.5)

        assert len(monitor.request_times) == 3
        assert 1.5 in monitor.request_times
        assert 2.0 in monitor.request_times
        assert 0.5 in monitor.request_times

    def test_records_latency_metric(self):
        """should_store_latency_measurements_for_analysis"""
        monitor = PerformanceMonitor(max_history=3)

        # Add more items than max_history to test deque behavior
        monitor.track_request_time(1.0)
        monitor.track_request_time(2.0)
        monitor.track_request_time(3.0)
        monitor.track_request_time(4.0)  # Should evict 1.0

        assert len(monitor.request_times) == 3
        assert 1.0 not in monitor.request_times
        assert 4.0 in monitor.request_times

    def test_calculates_p95_percentile(self):
        """should_calculate_95th_percentile_response_time"""
        monitor = PerformanceMonitor()

        # Add 100 values from 0.01 to 1.0
        times = [i * 0.01 for i in range(1, 101)]
        for t in times:
            monitor.track_request_time(t)

        p95 = monitor.get_p95_latency()
        expected_p95 = float(np.percentile(times, 95))
        assert abs(p95 - expected_p95) < 0.001

    def test_calculates_p99_percentile(self):
        """should_calculate_99th_percentile_response_time"""
        monitor = PerformanceMonitor()

        # Add 100 values
        times = [i * 0.01 for i in range(1, 101)]
        for t in times:
            monitor.track_request_time(t)

        p99 = monitor.get_p99_latency()
        expected_p99 = float(np.percentile(times, 99))
        assert abs(p99 - expected_p99) < 0.001

    def test_empty_monitor_returns_zero(self):
        """Test that empty monitor returns 0 for all metrics"""
        monitor = PerformanceMonitor()

        assert monitor.get_p95_latency() == 0.0
        assert monitor.get_p99_latency() == 0.0
        assert monitor.get_average_latency() == 0.0
        assert monitor.get_min_latency() == 0.0
        assert monitor.get_max_latency() == 0.0

    def test_calculates_average_latency(self):
        """Test average latency calculation"""
        monitor = PerformanceMonitor()

        times = [1.0, 2.0, 3.0, 4.0, 5.0]
        for t in times:
            monitor.track_request_time(t)

        avg = monitor.get_average_latency()
        expected = sum(times) / len(times)
        assert abs(avg - expected) < 0.001

    def test_tracks_min_max_latency(self):
        """Test min and max latency tracking"""
        monitor = PerformanceMonitor()

        times = [5.0, 1.0, 8.0, 2.0, 6.0]
        for t in times:
            monitor.track_request_time(t)

        assert monitor.get_min_latency() == 1.0
        assert monitor.get_max_latency() == 8.0


class TestPerformanceMonitorMetrics:
    """Test metrics calculation and reporting"""

    def test_tracks_total_request_count(self):
        """should_count_total_processed_requests"""
        monitor = PerformanceMonitor()

        for i in range(5):
            monitor.track_request_time(1.0)

        stats = monitor.get_stats()
        assert stats["total_requests"] == 5

    def test_comprehensive_stats(self):
        """Test comprehensive statistics generation"""
        monitor = PerformanceMonitor()

        times = [1.0, 2.0, 3.0, 4.0, 5.0]
        for t in times:
            monitor.track_request_time(t)

        stats = monitor.get_stats()

        assert stats["total_requests"] == 5
        assert "average_latency" in stats
        assert "p95_latency" in stats
        assert "p99_latency" in stats
        assert "min_latency" in stats
        assert "max_latency" in stats
        assert stats["min_latency"] == 1.0
        assert stats["max_latency"] == 5.0

    def test_empty_stats(self):
        """Test stats when no data is available"""
        monitor = PerformanceMonitor()

        stats = monitor.get_stats()

        assert stats["total_requests"] == 0
        assert stats["average_latency"] == 0.0
        assert stats["p95_latency"] == 0.0
        assert stats["p99_latency"] == 0.0
        assert stats["min_latency"] == 0.0
        assert stats["max_latency"] == 0.0

    def test_clear_stats(self):
        """should_allow_clearing_accumulated_metrics"""
        monitor = PerformanceMonitor()

        # Add some data
        monitor.track_request_time(1.0)
        monitor.track_request_time(2.0)

        assert len(monitor.request_times) == 2

        # Clear stats
        monitor.clear_stats()

        assert len(monitor.request_times) == 0
        stats = monitor.get_stats()
        assert stats["total_requests"] == 0

    def test_performance_threshold_check(self):
        """Test performance threshold validation"""
        monitor = PerformanceMonitor()

        # Add times with some over threshold
        times = [1.0, 2.0, 6.0, 3.0, 7.0]  # 6.0 and 7.0 exceed 5.0 threshold
        for t in times:
            monitor.track_request_time(t)

        result = monitor.check_performance_threshold(threshold=5.0)

        assert result["threshold"] == 5.0
        assert result["violations"] == 2
        assert result["total_requests"] == 5
        assert abs(result["violation_rate"] - 0.4) < 0.001  # 2/5 = 0.4

    def test_threshold_check_empty(self):
        """Test threshold check with no data"""
        monitor = PerformanceMonitor()

        result = monitor.check_performance_threshold()

        assert result["violations"] == 0
        assert result["total_requests"] == 0
        assert result["violation_rate"] == 0.0


class TestPerformanceMonitorGlobal:
    """Test global performance monitor instance"""

    def test_get_performance_monitor_singleton(self):
        """Test that get_performance_monitor returns singleton"""
        monitor1 = get_performance_monitor()
        monitor2 = get_performance_monitor()

        assert monitor1 is monitor2
        assert isinstance(monitor1, PerformanceMonitor)

    def test_global_monitor_persistence(self):
        """Test that global monitor persists data across calls"""
        monitor1 = get_performance_monitor()
        initial_count = monitor1.get_stats()["total_requests"]

        monitor1.track_request_time(1.5)

        monitor2 = get_performance_monitor()
        stats = monitor2.get_stats()

        assert stats["total_requests"] == initial_count + 1


class TestPerformanceMonitorDecorators:
    """Test performance monitoring decorators"""

    @pytest.mark.asyncio
    async def test_async_decorator(self):
        """Test async performance monitoring decorator"""

        @monitor_performance(threshold=1.0)
        async def test_async_function():
            await asyncio.sleep(0.05)
            return "result"

        # Clear existing stats
        monitor = get_performance_monitor()
        initial_count = monitor.get_stats()["total_requests"]

        result = await test_async_function()

        assert result == "result"
        stats = monitor.get_stats()
        assert stats["total_requests"] == initial_count + 1
        # Should have at least the sleep time
        assert stats["max_latency"] >= 0.05

    def test_sync_decorator(self):
        """Test synchronous performance monitoring decorator"""

        @monitor_sync_performance(threshold=1.0)
        def test_sync_function():
            time.sleep(0.05)
            return "result"

        # Clear existing stats for isolated test
        monitor = get_performance_monitor()
        initial_count = monitor.get_stats()["total_requests"]

        result = test_sync_function()

        assert result == "result"
        stats = monitor.get_stats()
        assert stats["total_requests"] == initial_count + 1

    @pytest.mark.asyncio
    async def test_decorator_with_exception(self):
        """Test that decorator tracks time even when function raises exception"""

        @monitor_performance(threshold=1.0)
        async def failing_function():
            await asyncio.sleep(0.05)
            raise ValueError("Test error")

        monitor = get_performance_monitor()
        initial_count = monitor.get_stats()["total_requests"]

        with pytest.raises(ValueError):
            await failing_function()

        # Should still have tracked the time
        stats = monitor.get_stats()
        assert stats["total_requests"] == initial_count + 1

    def test_sync_decorator_with_exception(self):
        """Test sync decorator with exception"""

        @monitor_sync_performance(threshold=1.0)
        def failing_sync_function():
            time.sleep(0.05)
            raise ValueError("Test error")

        monitor = get_performance_monitor()
        initial_count = monitor.get_stats()["total_requests"]

        with pytest.raises(ValueError):
            failing_sync_function()

        # Should still have tracked the time
        stats = monitor.get_stats()
        assert stats["total_requests"] == initial_count + 1

    @patch("app.utils.performance_monitor.logger")
    @pytest.mark.asyncio
    async def test_decorator_threshold_warning(self, mock_logger):
        """Test that decorator logs warning when threshold exceeded"""

        @monitor_performance(threshold=0.01)  # Very short threshold
        async def slow_function():
            await asyncio.sleep(0.05)  # This will exceed threshold
            return "result"

        await slow_function()

        # Check that warning was logged
        mock_logger.warning.assert_called()
        warning_message = mock_logger.warning.call_args[0][0]
        assert "exceeded" in warning_message
        assert "threshold" in warning_message

    @patch("app.utils.performance_monitor.logger")
    def test_sync_decorator_threshold_warning(self, mock_logger):
        """Test sync decorator threshold warning"""

        @monitor_sync_performance(threshold=0.01)
        def slow_sync_function():
            time.sleep(0.05)
            return "result"

        slow_sync_function()

        # Check that warning was logged
        mock_logger.warning.assert_called()
        warning_message = mock_logger.warning.call_args[0][0]
        assert "exceeded" in warning_message
        assert "threshold" in warning_message

    @patch("app.utils.performance_monitor.logger")
    @pytest.mark.asyncio
    async def test_decorator_info_logging(self, mock_logger):
        """Test that decorator logs info about execution time"""

        @monitor_performance(threshold=1.0)
        async def test_function():
            await asyncio.sleep(0.01)
            return "result"

        await test_function()

        # Check that info was logged
        mock_logger.info.assert_called()
        info_message = mock_logger.info.call_args[0][0]
        assert "took" in info_message
        assert "test_function" in info_message


class TestPerformanceMonitorP95Validation:
    """Test P95 latency validation against SLA"""

    def test_p95_latency_validation(self):
        """should_validate_that_p95_latency_meets_5_second_sla"""
        monitor = PerformanceMonitor()

        # Add times mostly under 5s but some over
        for _ in range(90):
            monitor.track_request_time(2.0)  # Fast requests
        for _ in range(10):
            monitor.track_request_time(6.0)  # Slow requests

        p95 = monitor.get_p95_latency()
        # P95 should be around 6.0 since 10% are slow
        assert p95 > 5.0  # Violates 5s SLA

    def test_identifies_slow_requests(self):
        """should_identify_requests_that_exceed_performance_threshold"""
        monitor = PerformanceMonitor()

        times = [1.0, 2.0, 8.0, 3.0, 9.0, 1.5]  # 8.0 and 9.0 are slow
        for t in times:
            monitor.track_request_time(t)

        result = monitor.check_performance_threshold(threshold=5.0)

        assert result["violations"] == 2
        assert abs(result["violation_rate"] - (2 / 6)) < 0.001

    def test_generates_performance_report(self):
        """should_create_comprehensive_performance_analysis_report"""
        monitor = PerformanceMonitor()

        # Add various request times
        times = [0.5, 1.0, 1.5, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0]
        for t in times:
            monitor.track_request_time(t)

        stats = monitor.get_stats()
        threshold_check = monitor.check_performance_threshold(5.0)

        # Verify comprehensive report data
        assert "total_requests" in stats
        assert "average_latency" in stats
        assert "p95_latency" in stats
        assert "p99_latency" in stats
        assert "min_latency" in stats
        assert "max_latency" in stats

        assert "violations" in threshold_check
        assert "violation_rate" in threshold_check
        assert "threshold" in threshold_check

    def test_p95_under_threshold(self):
        """Test P95 latency under 5 second threshold"""
        monitor = PerformanceMonitor()

        # Add all fast requests
        for _ in range(100):
            monitor.track_request_time(2.0)  # All under 5s

        p95 = monitor.get_p95_latency()
        assert p95 <= 5.0  # Meets SLA


class TestPerformanceMonitorEdgeCases:
    """Test edge cases and error conditions"""

    def test_single_request(self):
        """Test behavior with single request"""
        monitor = PerformanceMonitor()
        monitor.track_request_time(2.5)

        stats = monitor.get_stats()
        assert stats["total_requests"] == 1
        assert stats["average_latency"] == 2.5
        assert stats["min_latency"] == 2.5
        assert stats["max_latency"] == 2.5
        assert stats["p95_latency"] == 2.5
        assert stats["p99_latency"] == 2.5

    def test_zero_threshold(self):
        """Test threshold check with zero threshold"""
        monitor = PerformanceMonitor()
        monitor.track_request_time(0.1)
        monitor.track_request_time(0.2)

        result = monitor.check_performance_threshold(threshold=0.0)
        assert result["violations"] == 2  # All exceed 0
        assert result["violation_rate"] == 1.0

    def test_very_large_values(self):
        """Test with very large latency values"""
        monitor = PerformanceMonitor()
        monitor.track_request_time(1000.0)
        monitor.track_request_time(2000.0)

        stats = monitor.get_stats()
        assert stats["max_latency"] == 2000.0
        assert stats["average_latency"] == 1500.0

    def test_negative_threshold(self):
        """Test negative threshold (should work but not very useful)"""
        monitor = PerformanceMonitor()
        monitor.track_request_time(1.0)

        result = monitor.check_performance_threshold(threshold=-1.0)
        assert result["violations"] == 1
        assert result["violation_rate"] == 1.0

    @patch("app.utils.performance_monitor.logger")
    def test_track_request_time_debug_logging(self, mock_logger):
        """Test debug logging in track_request_time"""
        monitor = PerformanceMonitor()
        monitor.track_request_time(1.5)

        # Should log debug message about tracking
        mock_logger.debug.assert_called_once()
        debug_message = mock_logger.debug.call_args[0][0]
        assert "Tracked request time" in debug_message
        assert "1.500s" in debug_message

    @patch("app.utils.performance_monitor.logger")
    def test_clear_stats_logging(self, mock_logger):
        """Test info logging in clear_stats"""
        monitor = PerformanceMonitor()
        monitor.track_request_time(1.0)
        monitor.clear_stats()

        # Should log info message about clearing
        mock_logger.info.assert_called_once()
        info_message = mock_logger.info.call_args[0][0]
        assert "Performance statistics cleared" in info_message
