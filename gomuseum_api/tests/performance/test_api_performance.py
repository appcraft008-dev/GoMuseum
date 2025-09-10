"""
Performance tests for API endpoints
"""
import pytest
import asyncio
import time
import statistics
from httpx import AsyncClient
from concurrent.futures import ThreadPoolExecutor, as_completed
import psutil
import threading
from typing import List, Dict, Any


@pytest.mark.performance
class TestAPIPerformance:
    """Test API response time performance"""
    
    async def test_health_endpoint_performance(self, async_client: AsyncClient, performance_thresholds):
        """Test health endpoint response time"""
        # Warm up
        await async_client.get("/health")
        
        # Measure response times
        response_times = []
        for _ in range(100):
            start_time = time.time()
            response = await async_client.get("/health")
            end_time = time.time()
            
            response_times.append(end_time - start_time)
            assert response.status_code == 200
        
        # Analyze performance
        avg_time = statistics.mean(response_times)
        p95_time = statistics.quantiles(response_times, n=20)[18]  # 95th percentile
        max_time = max(response_times)
        
        print(f"Health endpoint performance:")
        print(f"  Average: {avg_time:.3f}s")
        print(f"  95th percentile: {p95_time:.3f}s")
        print(f"  Maximum: {max_time:.3f}s")
        
        # Assert performance requirements
        assert avg_time < performance_thresholds["api_response_time"]
        assert p95_time < performance_thresholds["api_response_time"] * 2
    
    async def test_auth_login_performance(self, async_client: AsyncClient, test_user, performance_thresholds):
        """Test authentication login performance"""
        login_data = {
            "email": test_user.email,
            "password": "testpassword"
        }
        
        # Warm up
        await async_client.post("/api/v1/auth/login", json=login_data)
        
        # Measure response times
        response_times = []
        for _ in range(50):
            start_time = time.time()
            response = await async_client.post("/api/v1/auth/login", json=login_data)
            end_time = time.time()
            
            response_times.append(end_time - start_time)
            assert response.status_code == 200
        
        # Analyze performance
        avg_time = statistics.mean(response_times)
        p95_time = statistics.quantiles(response_times, n=20)[18]
        
        print(f"Login endpoint performance:")
        print(f"  Average: {avg_time:.3f}s")
        print(f"  95th percentile: {p95_time:.3f}s")
        
        # Auth endpoints may be slower due to password hashing
        assert avg_time < performance_thresholds["api_response_time"] * 5
        assert p95_time < performance_thresholds["api_response_time"] * 10
    
    async def test_user_profile_performance(self, async_client: AsyncClient, auth_headers, performance_thresholds):
        """Test user profile endpoint performance"""
        # Warm up
        await async_client.get("/api/v1/auth/profile", headers=auth_headers)
        
        # Measure response times
        response_times = []
        for _ in range(100):
            start_time = time.time()
            response = await async_client.get("/api/v1/auth/profile", headers=auth_headers)
            end_time = time.time()
            
            response_times.append(end_time - start_time)
            assert response.status_code == 200
        
        # Analyze performance
        avg_time = statistics.mean(response_times)
        p95_time = statistics.quantiles(response_times, n=20)[18]
        
        print(f"Profile endpoint performance:")
        print(f"  Average: {avg_time:.3f}s")
        print(f"  95th percentile: {p95_time:.3f}s")
        
        assert avg_time < performance_thresholds["api_response_time"]
        assert p95_time < performance_thresholds["api_response_time"] * 2


@pytest.mark.performance
class TestCachePerformance:
    """Test cache performance"""
    
    async def test_redis_cache_performance(self, mock_redis, performance_thresholds):
        """Test Redis cache response time"""
        response_times = []
        
        # Test SET operations
        for i in range(100):
            start_time = time.time()
            mock_redis.set(f"test_key_{i}", f"test_value_{i}")
            end_time = time.time()
            response_times.append(end_time - start_time)
        
        # Test GET operations
        for i in range(100):
            start_time = time.time()
            mock_redis.get(f"test_key_{i}")
            end_time = time.time()
            response_times.append(end_time - start_time)
        
        avg_time = statistics.mean(response_times)
        p95_time = statistics.quantiles(response_times, n=20)[18]
        
        print(f"Cache performance:")
        print(f"  Average: {avg_time:.6f}s")
        print(f"  95th percentile: {p95_time:.6f}s")
        
        # Cache should be very fast
        assert avg_time < performance_thresholds["cache_response_time"]
    
    async def test_cache_hit_ratio(self, mock_redis):
        """Test cache hit ratio simulation"""
        # Simulate cache operations
        hits = 0
        misses = 0
        
        # Pre-populate cache
        for i in range(50):
            mock_redis.set(f"popular_key_{i}", f"value_{i}")
        
        # Simulate requests with realistic hit/miss ratio
        for _ in range(1000):
            key_id = statistics.randint(0, 100)  # Some keys not in cache
            result = mock_redis.get(f"popular_key_{key_id}")
            
            if result is not None:
                hits += 1
            else:
                misses += 1
                # Cache miss - set the value
                mock_redis.set(f"popular_key_{key_id}", f"value_{key_id}")
        
        hit_ratio = hits / (hits + misses)
        
        print(f"Cache hit ratio: {hit_ratio:.2%}")
        
        # Should have reasonable hit ratio
        assert hit_ratio > 0.3  # At least 30% hit ratio


@pytest.mark.performance
class TestConcurrencyPerformance:
    """Test API performance under concurrent load"""
    
    @pytest.mark.asyncio
    async def test_concurrent_health_checks(self, async_client: AsyncClient, performance_thresholds):
        """Test concurrent health check requests"""
        concurrent_requests = 50
        
        async def make_request():
            start_time = time.time()
            response = await async_client.get("/health")
            end_time = time.time()
            return response.status_code, end_time - start_time
        
        # Execute concurrent requests
        start_time = time.time()
        tasks = [make_request() for _ in range(concurrent_requests)]
        results = await asyncio.gather(*tasks)
        total_time = time.time() - start_time
        
        # Analyze results
        response_codes = [r[0] for r in results]
        response_times = [r[1] for r in results]
        
        success_rate = sum(1 for code in response_codes if code == 200) / len(response_codes)
        avg_response_time = statistics.mean(response_times)
        throughput = concurrent_requests / total_time
        
        print(f"Concurrent performance ({concurrent_requests} requests):")
        print(f"  Success rate: {success_rate:.2%}")
        print(f"  Average response time: {avg_response_time:.3f}s")
        print(f"  Throughput: {throughput:.1f} req/s")
        print(f"  Total time: {total_time:.3f}s")
        
        # Performance assertions
        assert success_rate >= 0.95  # 95% success rate
        assert avg_response_time < performance_thresholds["api_response_time"] * 2
        assert throughput > 10  # At least 10 requests per second
    
    @pytest.mark.asyncio
    async def test_concurrent_authenticated_requests(self, async_client: AsyncClient, auth_headers, performance_thresholds):
        """Test concurrent authenticated requests"""
        concurrent_requests = 20
        
        async def make_authenticated_request():
            start_time = time.time()
            response = await async_client.get("/api/v1/auth/profile", headers=auth_headers)
            end_time = time.time()
            return response.status_code, end_time - start_time
        
        # Execute concurrent requests
        tasks = [make_authenticated_request() for _ in range(concurrent_requests)]
        results = await asyncio.gather(*tasks)
        
        # Analyze results
        response_codes = [r[0] for r in results]
        response_times = [r[1] for r in results]
        
        success_rate = sum(1 for code in response_codes if code == 200) / len(response_codes)
        avg_response_time = statistics.mean(response_times)
        
        print(f"Concurrent authenticated requests performance:")
        print(f"  Success rate: {success_rate:.2%}")
        print(f"  Average response time: {avg_response_time:.3f}s")
        
        assert success_rate >= 0.90  # 90% success rate for auth requests
        assert avg_response_time < performance_thresholds["api_response_time"] * 3


@pytest.mark.performance
class TestMemoryPerformance:
    """Test memory usage performance"""
    
    def test_memory_usage_baseline(self, performance_thresholds):
        """Test baseline memory usage"""
        process = psutil.Process()
        memory_info = process.memory_info()
        
        print(f"Memory usage:")
        print(f"  RSS: {memory_info.rss / 1024 / 1024:.1f} MB")
        print(f"  VMS: {memory_info.vms / 1024 / 1024:.1f} MB")
        
        # Memory usage should be reasonable
        assert memory_info.rss < performance_thresholds["memory_usage"]
    
    async def test_memory_usage_under_load(self, async_client: AsyncClient, performance_thresholds):
        """Test memory usage under API load"""
        process = psutil.Process()
        initial_memory = process.memory_info().rss
        
        # Generate load
        tasks = []
        for _ in range(100):
            tasks.append(async_client.get("/health"))
        
        await asyncio.gather(*tasks)
        
        final_memory = process.memory_info().rss
        memory_increase = final_memory - initial_memory
        
        print(f"Memory usage under load:")
        print(f"  Initial: {initial_memory / 1024 / 1024:.1f} MB")
        print(f"  Final: {final_memory / 1024 / 1024:.1f} MB")
        print(f"  Increase: {memory_increase / 1024 / 1024:.1f} MB")
        
        # Memory increase should be reasonable
        assert memory_increase < 50 * 1024 * 1024  # Less than 50MB increase
        assert final_memory < performance_thresholds["memory_usage"]


@pytest.mark.performance
class TestDatabasePerformance:
    """Test database operation performance"""
    
    async def test_user_query_performance(self, db_session, performance_thresholds):
        """Test user database query performance"""
        from app.models.user import User
        
        response_times = []
        
        # Test multiple queries
        for _ in range(50):
            start_time = time.time()
            user = db_session.query(User).first()
            end_time = time.time()
            
            response_times.append(end_time - start_time)
        
        avg_time = statistics.mean(response_times)
        p95_time = statistics.quantiles(response_times, n=20)[18]
        
        print(f"Database query performance:")
        print(f"  Average: {avg_time:.6f}s")
        print(f"  95th percentile: {p95_time:.6f}s")
        
        assert avg_time < performance_thresholds["db_query_time"]
        assert p95_time < performance_thresholds["db_query_time"] * 2
    
    async def test_user_creation_performance(self, db_session, performance_thresholds):
        """Test user creation performance"""
        from app.models.user import User
        from app.core.auth import get_password_hash
        
        response_times = []
        
        # Test user creation
        for i in range(20):
            start_time = time.time()
            
            user = User(
                email=f"perftest{i}@example.com",
                username=f"perfuser{i}",
                password_hash=get_password_hash("testpassword"),
                is_active=True
            )
            db_session.add(user)
            db_session.commit()
            
            end_time = time.time()
            response_times.append(end_time - start_time)
            
            # Clean up
            db_session.delete(user)
            db_session.commit()
        
        avg_time = statistics.mean(response_times)
        
        print(f"User creation performance:")
        print(f"  Average: {avg_time:.3f}s")
        
        # User creation includes password hashing, so it can be slower
        assert avg_time < 1.0  # Less than 1 second


@pytest.mark.performance
class TestSystemPerformance:
    """Test overall system performance"""
    
    def test_cpu_usage_monitoring(self, performance_thresholds):
        """Test CPU usage monitoring"""
        # Monitor CPU usage over a short period
        cpu_percentages = []
        
        for _ in range(10):
            cpu_percent = psutil.cpu_percent(interval=0.1)
            cpu_percentages.append(cpu_percent)
        
        avg_cpu = statistics.mean(cpu_percentages)
        max_cpu = max(cpu_percentages)
        
        print(f"CPU usage:")
        print(f"  Average: {avg_cpu:.1f}%")
        print(f"  Maximum: {max_cpu:.1f}%")
        
        # CPU usage should be reasonable
        assert avg_cpu < performance_thresholds["cpu_usage"]
    
    def test_disk_io_performance(self):
        """Test disk I/O performance"""
        disk_io_start = psutil.disk_io_counters()
        
        # Simulate some file operations
        import tempfile
        import os
        
        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            temp_file.write(b"Performance test data" * 1000)
            temp_file.flush()
            temp_path = temp_file.name
        
        # Read the file
        with open(temp_path, 'rb') as f:
            data = f.read()
        
        # Clean up
        os.unlink(temp_path)
        
        disk_io_end = psutil.disk_io_counters()
        
        read_bytes = disk_io_end.read_bytes - disk_io_start.read_bytes
        write_bytes = disk_io_end.write_bytes - disk_io_start.write_bytes
        
        print(f"Disk I/O:")
        print(f"  Read: {read_bytes} bytes")
        print(f"  Write: {write_bytes} bytes")
        
        # Basic sanity check
        assert read_bytes >= 0
        assert write_bytes >= 0
    
    async def test_response_time_distribution(self, async_client: AsyncClient):
        """Test response time distribution analysis"""
        response_times = []
        
        # Collect response times
        for _ in range(200):
            start_time = time.time()
            await async_client.get("/health")
            end_time = time.time()
            response_times.append(end_time - start_time)
        
        # Calculate distribution statistics
        response_times.sort()
        percentiles = {
            "p50": response_times[len(response_times) // 2],
            "p75": response_times[int(len(response_times) * 0.75)],
            "p90": response_times[int(len(response_times) * 0.90)],
            "p95": response_times[int(len(response_times) * 0.95)],
            "p99": response_times[int(len(response_times) * 0.99)]
        }
        
        print(f"Response time distribution:")
        for p, value in percentiles.items():
            print(f"  {p}: {value:.3f}s")
        
        # Performance assertions
        assert percentiles["p95"] < 0.2  # 95% of requests under 200ms
        assert percentiles["p99"] < 0.5  # 99% of requests under 500ms


@pytest.mark.performance
@pytest.mark.slow
class TestLoadTesting:
    """Load testing scenarios"""
    
    async def test_sustained_load(self, async_client: AsyncClient, load_test_config):
        """Test sustained load over time"""
        concurrent_users = load_test_config["concurrent_users"]
        test_duration = 30  # 30 seconds for testing
        
        results = {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "response_times": []
        }
        
        async def user_simulation():
            """Simulate a single user's behavior"""
            end_time = time.time() + test_duration
            
            while time.time() < end_time:
                try:
                    start_time = time.time()
                    response = await async_client.get("/health")
                    response_time = time.time() - start_time
                    
                    results["total_requests"] += 1
                    results["response_times"].append(response_time)
                    
                    if response.status_code == 200:
                        results["successful_requests"] += 1
                    else:
                        results["failed_requests"] += 1
                    
                    # Simulate user think time
                    await asyncio.sleep(0.1)
                
                except Exception as e:
                    results["failed_requests"] += 1
        
        # Run concurrent user simulations
        start_time = time.time()
        tasks = [user_simulation() for _ in range(min(concurrent_users, 10))]  # Limit for tests
        await asyncio.gather(*tasks)
        total_time = time.time() - start_time
        
        # Analyze results
        success_rate = results["successful_requests"] / max(results["total_requests"], 1)
        avg_response_time = statistics.mean(results["response_times"]) if results["response_times"] else 0
        throughput = results["total_requests"] / total_time
        
        print(f"Load test results:")
        print(f"  Duration: {total_time:.1f}s")
        print(f"  Total requests: {results['total_requests']}")
        print(f"  Success rate: {success_rate:.2%}")
        print(f"  Average response time: {avg_response_time:.3f}s")
        print(f"  Throughput: {throughput:.1f} req/s")
        
        # Performance assertions
        assert success_rate >= 0.95  # 95% success rate
        assert avg_response_time < 0.5  # Average response time under 500ms
        assert throughput > 5  # At least 5 requests per second