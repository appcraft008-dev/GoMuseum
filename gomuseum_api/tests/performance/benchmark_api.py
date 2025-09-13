"""
API Performance Benchmark Tests
测试API端点的性能指标，包括响应时间、吞吐量和并发处理能力
"""

import asyncio
import time
import statistics
from typing import List, Dict, Any
import aiohttp
import hashlib
from dataclasses import dataclass
from datetime import datetime
import json
import random
import os

# Performance targets from architecture requirements
PERFORMANCE_TARGETS = {
    "l1_cache_response_ms": 10,      # L1缓存响应时间 < 10ms
    "l2_cache_response_ms": 100,     # L2缓存响应时间 < 100ms 
    "api_response_ms": 200,          # API响应时间 < 200ms (cache hit)
    "cache_hit_rate": 70,            # 缓存命中率 > 70%
    "popular_hit_rate": 90,          # 热门内容命中率 > 90%
    "concurrent_users": 100,         # 支持100并发用户
    "throughput_rps": 500,           # 吞吐量 > 500 req/s
}

@dataclass
class BenchmarkResult:
    """性能测试结果"""
    endpoint: str
    total_requests: int
    successful_requests: int
    failed_requests: int
    min_response_time: float
    max_response_time: float
    avg_response_time: float
    p50_response_time: float
    p95_response_time: float
    p99_response_time: float
    throughput_rps: float
    cache_hit_rate: float
    error_rate: float
    timestamp: datetime

class APIBenchmark:
    """API性能基准测试"""
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.session = None
        self.results = []
        
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def benchmark_recognition_endpoint(
        self, 
        num_requests: int = 100,
        concurrent: int = 10,
        use_same_image: bool = False
    ) -> BenchmarkResult:
        """测试图像识别端点性能"""
        
        print(f"\n📊 Testing Recognition Endpoint")
        print(f"   Requests: {num_requests}, Concurrent: {concurrent}")
        
        # 准备测试图像
        test_images = []
        if use_same_image:
            # 使用相同图像测试缓存性能
            image_data = self._generate_test_image()
            test_images = [image_data] * num_requests
        else:
            # 使用不同图像测试真实场景
            test_images = [self._generate_test_image(i) for i in range(num_requests)]
        
        # 执行基准测试
        start_time = time.time()
        tasks = []
        
        for i in range(num_requests):
            task = self._test_recognition(test_images[i % len(test_images)])
            tasks.append(task)
            
            # 控制并发
            if len(tasks) >= concurrent:
                results = await asyncio.gather(*tasks, return_exceptions=True)
                tasks = []
        
        # 处理剩余任务
        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
        
        total_time = time.time() - start_time
        
        # 分析结果
        response_times = []
        cache_hits = 0
        errors = 0
        
        for result in results:
            if isinstance(result, Exception):
                errors += 1
            else:
                response_times.append(result['response_time'])
                if result.get('cached', False):
                    cache_hits += 1
        
        # 计算统计数据
        if response_times:
            response_times.sort()
            
            result = BenchmarkResult(
                endpoint="/api/v1/recognize",
                total_requests=num_requests,
                successful_requests=len(response_times),
                failed_requests=errors,
                min_response_time=min(response_times) * 1000,  # Convert to ms
                max_response_time=max(response_times) * 1000,
                avg_response_time=statistics.mean(response_times) * 1000,
                p50_response_time=response_times[len(response_times)//2] * 1000,
                p95_response_time=response_times[int(len(response_times)*0.95)] * 1000,
                p99_response_time=response_times[int(len(response_times)*0.99)] * 1000,
                throughput_rps=num_requests / total_time,
                cache_hit_rate=(cache_hits / len(response_times)) * 100,
                error_rate=(errors / num_requests) * 100,
                timestamp=datetime.now()
            )
            
            self.results.append(result)
            return result
        else:
            raise Exception("All requests failed")
    
    async def _test_recognition(self, image_data: bytes) -> Dict[str, Any]:
        """测试单个识别请求"""
        url = f"{self.base_url}/api/v1/recognize"
        
        start_time = time.time()
        
        try:
            data = aiohttp.FormData()
            data.add_field('file', image_data, filename='test.jpg', content_type='image/jpeg')
            
            async with self.session.post(url, data=data) as response:
                response_time = time.time() - start_time
                
                if response.status == 200:
                    result = await response.json()
                    return {
                        'success': True,
                        'response_time': response_time,
                        'cached': result.get('cached', False),
                        'confidence': result.get('confidence', 0)
                    }
                else:
                    return {
                        'success': False,
                        'response_time': response_time,
                        'error': f"HTTP {response.status}"
                    }
                    
        except Exception as e:
            return {
                'success': False,
                'response_time': time.time() - start_time,
                'error': str(e)
            }
    
    async def benchmark_cache_performance(self) -> Dict[str, Any]:
        """测试缓存性能"""
        
        print(f"\n📊 Testing Cache Performance")
        
        # 预热缓存
        print("   Warming up cache...")
        warm_up_images = [self._generate_test_image(i) for i in range(10)]
        for img in warm_up_images:
            await self._test_recognition(img)
        
        # 测试缓存命中率
        print("   Testing cache hit rate...")
        
        # 第一轮：新图像（缓存未命中）
        cold_result = await self.benchmark_recognition_endpoint(
            num_requests=50,
            concurrent=5,
            use_same_image=False
        )
        
        # 第二轮：相同图像（缓存命中）
        warm_result = await self.benchmark_recognition_endpoint(
            num_requests=50,
            concurrent=5,
            use_same_image=True
        )
        
        # 第三轮：混合场景
        mixed_images = []
        for i in range(100):
            if i % 3 == 0:  # 33% new images
                mixed_images.append(self._generate_test_image(1000 + i))
            else:  # 67% repeated images
                mixed_images.append(warm_up_images[i % len(warm_up_images)])
        
        mixed_result = await self.benchmark_recognition_endpoint(
            num_requests=100,
            concurrent=10,
            use_same_image=False
        )
        
        return {
            "cold_cache": self._format_result(cold_result),
            "warm_cache": self._format_result(warm_result),
            "mixed_scenario": self._format_result(mixed_result),
            "performance_improvement": {
                "response_time_reduction": f"{((cold_result.avg_response_time - warm_result.avg_response_time) / cold_result.avg_response_time * 100):.1f}%",
                "cache_effectiveness": warm_result.cache_hit_rate
            }
        }
    
    async def benchmark_concurrent_load(self) -> Dict[str, Any]:
        """测试并发负载"""
        
        print(f"\n📊 Testing Concurrent Load")
        
        concurrent_levels = [1, 5, 10, 20, 50, 100]
        results = {}
        
        for concurrent in concurrent_levels:
            print(f"   Testing {concurrent} concurrent users...")
            
            result = await self.benchmark_recognition_endpoint(
                num_requests=100,
                concurrent=concurrent,
                use_same_image=False
            )
            
            results[f"{concurrent}_users"] = {
                "avg_response_time_ms": result.avg_response_time,
                "p95_response_time_ms": result.p95_response_time,
                "throughput_rps": result.throughput_rps,
                "error_rate": result.error_rate
            }
            
            # 检查是否满足性能目标
            if result.avg_response_time > PERFORMANCE_TARGETS["api_response_ms"]:
                print(f"   ⚠️  Response time {result.avg_response_time:.1f}ms exceeds target {PERFORMANCE_TARGETS['api_response_ms']}ms")
        
        return results
    
    async def benchmark_database_queries(self) -> Dict[str, Any]:
        """测试数据库查询性能"""
        
        print(f"\n📊 Testing Database Query Performance")
        
        endpoints = [
            ("/api/v1/artworks/popular", "Popular Artworks"),
            ("/api/v1/museums", "Museums List"),
            ("/api/v1/user/profile", "User Profile"),
        ]
        
        results = {}
        
        for endpoint, name in endpoints:
            print(f"   Testing {name}...")
            
            response_times = []
            for _ in range(50):
                start_time = time.time()
                
                try:
                    async with self.session.get(f"{self.base_url}{endpoint}") as response:
                        if response.status == 200:
                            await response.json()
                        response_times.append(time.time() - start_time)
                except Exception as e:
                    print(f"   Error: {e}")
            
            if response_times:
                results[name] = {
                    "min_ms": min(response_times) * 1000,
                    "avg_ms": statistics.mean(response_times) * 1000,
                    "max_ms": max(response_times) * 1000,
                    "p95_ms": sorted(response_times)[int(len(response_times)*0.95)] * 1000
                }
        
        return results
    
    def _generate_test_image(self, seed: int = None) -> bytes:
        """生成测试图像数据"""
        # 简单的测试图像生成（实际应使用真实图像）
        if seed is not None:
            random.seed(seed)
        
        # 生成随机字节作为模拟图像
        size = random.randint(100_000, 500_000)  # 100KB - 500KB
        return bytes(random.randint(0, 255) for _ in range(size))
    
    def _format_result(self, result: BenchmarkResult) -> Dict[str, Any]:
        """格式化测试结果"""
        return {
            "response_times": {
                "min_ms": result.min_response_time,
                "avg_ms": result.avg_response_time,
                "p50_ms": result.p50_response_time,
                "p95_ms": result.p95_response_time,
                "p99_ms": result.p99_response_time,
                "max_ms": result.max_response_time,
            },
            "throughput_rps": result.throughput_rps,
            "cache_hit_rate": result.cache_hit_rate,
            "error_rate": result.error_rate,
            "success_rate": (result.successful_requests / result.total_requests) * 100
        }
    
    def generate_report(self) -> str:
        """生成性能测试报告"""
        
        report = []
        report.append("=" * 80)
        report.append("API PERFORMANCE BENCHMARK REPORT")
        report.append("=" * 80)
        report.append(f"Timestamp: {datetime.now().isoformat()}")
        report.append(f"Base URL: {self.base_url}")
        report.append("")
        
        # Performance Targets
        report.append("PERFORMANCE TARGETS:")
        report.append("-" * 40)
        for key, value in PERFORMANCE_TARGETS.items():
            report.append(f"  {key}: {value}")
        report.append("")
        
        # Test Results
        report.append("TEST RESULTS:")
        report.append("-" * 40)
        
        for result in self.results:
            report.append(f"\nEndpoint: {result.endpoint}")
            report.append(f"  Total Requests: {result.total_requests}")
            report.append(f"  Successful: {result.successful_requests}")
            report.append(f"  Failed: {result.failed_requests}")
            report.append(f"  Error Rate: {result.error_rate:.1f}%")
            report.append(f"  Cache Hit Rate: {result.cache_hit_rate:.1f}%")
            report.append(f"  Throughput: {result.throughput_rps:.1f} req/s")
            report.append(f"  Response Times (ms):")
            report.append(f"    Min: {result.min_response_time:.1f}")
            report.append(f"    Avg: {result.avg_response_time:.1f}")
            report.append(f"    P50: {result.p50_response_time:.1f}")
            report.append(f"    P95: {result.p95_response_time:.1f}")
            report.append(f"    P99: {result.p99_response_time:.1f}")
            report.append(f"    Max: {result.max_response_time:.1f}")
            
            # Check against targets
            report.append(f"  Target Compliance:")
            
            if result.avg_response_time <= PERFORMANCE_TARGETS["api_response_ms"]:
                report.append(f"    ✅ Response Time: {result.avg_response_time:.1f}ms <= {PERFORMANCE_TARGETS['api_response_ms']}ms")
            else:
                report.append(f"    ❌ Response Time: {result.avg_response_time:.1f}ms > {PERFORMANCE_TARGETS['api_response_ms']}ms")
            
            if result.cache_hit_rate >= PERFORMANCE_TARGETS["cache_hit_rate"]:
                report.append(f"    ✅ Cache Hit Rate: {result.cache_hit_rate:.1f}% >= {PERFORMANCE_TARGETS['cache_hit_rate']}%")
            else:
                report.append(f"    ❌ Cache Hit Rate: {result.cache_hit_rate:.1f}% < {PERFORMANCE_TARGETS['cache_hit_rate']}%")
            
            if result.throughput_rps >= PERFORMANCE_TARGETS["throughput_rps"]:
                report.append(f"    ✅ Throughput: {result.throughput_rps:.1f} req/s >= {PERFORMANCE_TARGETS['throughput_rps']} req/s")
            else:
                report.append(f"    ❌ Throughput: {result.throughput_rps:.1f} req/s < {PERFORMANCE_TARGETS['throughput_rps']} req/s")
        
        report.append("")
        report.append("=" * 80)
        
        return "\n".join(report)

async def main():
    """运行性能基准测试"""
    
    async with APIBenchmark() as benchmark:
        
        # 1. 测试缓存性能
        cache_results = await benchmark.benchmark_cache_performance()
        print("\n📈 Cache Performance Results:")
        print(json.dumps(cache_results, indent=2))
        
        # 2. 测试并发负载
        concurrent_results = await benchmark.benchmark_concurrent_load()
        print("\n📈 Concurrent Load Results:")
        print(json.dumps(concurrent_results, indent=2))
        
        # 3. 测试数据库查询
        db_results = await benchmark.benchmark_database_queries()
        print("\n📈 Database Query Results:")
        print(json.dumps(db_results, indent=2))
        
        # 4. 生成报告
        report = benchmark.generate_report()
        print("\n" + report)
        
        # 保存报告
        report_file = f"benchmark_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        with open(report_file, 'w') as f:
            f.write(report)
        print(f"\n✅ Report saved to {report_file}")

if __name__ == "__main__":
    asyncio.run(main())