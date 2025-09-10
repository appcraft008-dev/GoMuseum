#!/usr/bin/env python3
"""
GoMuseum API Performance Test Suite
Tests the optimized API performance to ensure 95% requests complete in <100ms
"""

import asyncio
import aiohttp
import time
import statistics
import json
from typing import List, Dict, Any
from dataclasses import dataclass
import base64
import concurrent.futures

@dataclass
class PerformanceResult:
    """Performance test results"""
    endpoint: str
    total_requests: int
    successful_requests: int
    failed_requests: int
    avg_response_time: float
    p95_response_time: float
    p99_response_time: float
    min_response_time: float
    max_response_time: float
    requests_per_second: float
    errors: List[str]

class APIPerformanceTester:
    """API performance testing utility"""
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.results = []
    
    async def test_endpoint_performance(
        self,
        endpoint: str,
        method: str = "GET",
        payload: Dict[str, Any] = None,
        headers: Dict[str, str] = None,
        concurrent_requests: int = 100,
        total_requests: int = 1000
    ) -> PerformanceResult:
        """Test endpoint performance with concurrent requests"""
        
        print(f"🚀 Testing {endpoint} with {total_requests} requests ({concurrent_requests} concurrent)")
        
        response_times = []
        errors = []
        successful_requests = 0
        failed_requests = 0
        
        start_time = time.time()
        
        # Create semaphore to limit concurrent requests
        semaphore = asyncio.Semaphore(concurrent_requests)
        
        async def make_request(session: aiohttp.ClientSession) -> float:
            """Make a single request and return response time"""
            nonlocal successful_requests, failed_requests
            
            async with semaphore:
                request_start = time.time()
                try:
                    url = f"{self.base_url}{endpoint}"
                    
                    if method.upper() == "GET":
                        async with session.get(url, headers=headers) as response:
                            await response.text()
                            if response.status == 200:
                                successful_requests += 1
                            else:
                                failed_requests += 1
                                errors.append(f"HTTP {response.status}")
                    
                    elif method.upper() == "POST":
                        async with session.post(url, json=payload, headers=headers) as response:
                            await response.text()
                            if response.status in [200, 201]:
                                successful_requests += 1
                            else:
                                failed_requests += 1
                                errors.append(f"HTTP {response.status}")
                    
                    request_time = time.time() - request_start
                    return request_time
                    
                except Exception as e:
                    failed_requests += 1
                    errors.append(str(e))
                    return time.time() - request_start
        
        # Execute all requests concurrently
        connector = aiohttp.TCPConnector(limit=200, limit_per_host=200)
        async with aiohttp.ClientSession(connector=connector) as session:
            tasks = [make_request(session) for _ in range(total_requests)]
            response_times = await asyncio.gather(*tasks)
        
        total_time = time.time() - start_time
        
        # Calculate statistics
        response_times = [t for t in response_times if t > 0]
        
        if response_times:
            avg_time = statistics.mean(response_times)
            p95_time = statistics.quantiles(response_times, n=20)[18]  # 95th percentile
            p99_time = statistics.quantiles(response_times, n=100)[98]  # 99th percentile
            min_time = min(response_times)
            max_time = max(response_times)
        else:
            avg_time = p95_time = p99_time = min_time = max_time = 0
        
        requests_per_second = total_requests / total_time if total_time > 0 else 0
        
        result = PerformanceResult(
            endpoint=endpoint,
            total_requests=total_requests,
            successful_requests=successful_requests,
            failed_requests=failed_requests,
            avg_response_time=avg_time * 1000,  # Convert to ms
            p95_response_time=p95_time * 1000,
            p99_response_time=p99_time * 1000,
            min_response_time=min_time * 1000,
            max_response_time=max_time * 1000,
            requests_per_second=requests_per_second,
            errors=list(set(errors))  # Unique errors
        )
        
        self.results.append(result)
        return result
    
    def print_results(self, result: PerformanceResult):
        """Print formatted test results"""
        print(f"\n📊 Performance Results for {result.endpoint}")
        print("=" * 60)
        print(f"Total Requests:     {result.total_requests}")
        print(f"Successful:         {result.successful_requests}")
        print(f"Failed:             {result.failed_requests}")
        print(f"Success Rate:       {result.successful_requests/result.total_requests*100:.1f}%")
        print(f"Requests/Second:    {result.requests_per_second:.1f}")
        print()
        print("Response Times (ms):")
        print(f"  Average:          {result.avg_response_time:.1f}ms")
        print(f"  95th Percentile:  {result.p95_response_time:.1f}ms")
        print(f"  99th Percentile:  {result.p99_response_time:.1f}ms")
        print(f"  Minimum:          {result.min_response_time:.1f}ms")
        print(f"  Maximum:          {result.max_response_time:.1f}ms")
        
        # Check performance targets
        if result.p95_response_time < 100:
            print(f"✅ PASS: 95% requests < 100ms ({result.p95_response_time:.1f}ms)")
        else:
            print(f"❌ FAIL: 95% requests >= 100ms ({result.p95_response_time:.1f}ms)")
        
        if result.errors:
            print(f"\nErrors: {result.errors}")
        
        print("=" * 60)
    
    async def run_comprehensive_tests(self):
        """Run comprehensive performance tests"""
        print("🔥 Starting GoMuseum API Performance Tests")
        print("Target: 95% of requests should complete in <100ms")
        print()
        
        # Test 1: Health endpoint (should be very fast)
        result = await self.test_endpoint_performance(
            endpoint="/health",
            method="GET",
            concurrent_requests=50,
            total_requests=500
        )
        self.print_results(result)
        
        # Test 2: User quota endpoint
        result = await self.test_endpoint_performance(
            endpoint="/api/v1/user/quota/test-user-id",
            method="GET",
            concurrent_requests=30,
            total_requests=300
        )
        self.print_results(result)
        
        # Test 3: Museums listing
        result = await self.test_endpoint_performance(
            endpoint="/api/v1/museums",
            method="GET",
            concurrent_requests=40,
            total_requests=400
        )
        self.print_results(result)
        
        # Test 4: Monitoring metrics
        result = await self.test_endpoint_performance(
            endpoint="/api/v1/monitoring/metrics",
            method="GET",
            concurrent_requests=20,
            total_requests=200
        )
        self.print_results(result)
        
        # Test 5: Recognition endpoint (with mock data)
        # Create a small base64 test image
        test_image = base64.b64encode(b"fake_image_data_for_testing").decode()
        recognition_payload = {
            "image": test_image,
            "language": "zh"
        }
        
        result = await self.test_endpoint_performance(
            endpoint="/api/v1/recognize",
            method="POST",
            payload=recognition_payload,
            concurrent_requests=10,
            total_requests=100
        )
        self.print_results(result)
        
        # Summary
        self.print_summary()
    
    def print_summary(self):
        """Print overall performance summary"""
        print("\n🎯 PERFORMANCE SUMMARY")
        print("=" * 60)
        
        passed_tests = 0
        total_tests = len(self.results)
        
        for result in self.results:
            target_met = result.p95_response_time < 100
            status = "✅ PASS" if target_met else "❌ FAIL"
            print(f"{status} {result.endpoint}: {result.p95_response_time:.1f}ms (P95)")
            
            if target_met:
                passed_tests += 1
        
        print()
        print(f"Overall Score: {passed_tests}/{total_tests} tests passed")
        
        if passed_tests == total_tests:
            print("🏆 EXCELLENT! All endpoints meet the <100ms P95 target!")
        elif passed_tests >= total_tests * 0.8:
            print("👍 GOOD! Most endpoints meet the performance target.")
        else:
            print("⚠️  NEEDS IMPROVEMENT! Several endpoints are too slow.")
        
        print("=" * 60)

async def main():
    """Main test execution"""
    tester = APIPerformanceTester()
    
    print("Waiting for API to be ready...")
    await asyncio.sleep(2)
    
    try:
        await tester.run_comprehensive_tests()
    except Exception as e:
        print(f"❌ Test execution failed: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    import sys
    sys.exit(asyncio.run(main()))