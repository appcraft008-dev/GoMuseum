"""
Locust Load Testing Script for GoMuseum API
使用 Locust 进行高并发负载测试

运行方式:
1. 安装: pip install locust
2. 运行: locust -f locustfile.py --host http://localhost:8000
3. 访问: http://localhost:8089
"""

from locust import HttpUser, task, between, events
from locust.env import Environment
from locust.stats import stats_printer, stats_history
from locust.log import setup_logging
import time
import random
import hashlib
import json
import logging
from typing import Dict, Any
import gevent

# Setup logging
setup_logging("INFO", None)
logger = logging.getLogger(__name__)

# Performance thresholds
PERFORMANCE_THRESHOLDS = {
    "max_response_time_ms": 200,     # 最大响应时间
    "max_error_rate": 0.01,          # 最大错误率 1%
    "min_throughput_rps": 500,       # 最小吞吐量
    "target_cache_hit_rate": 0.7,    # 目标缓存命中率
}

class GoMuseumUser(HttpUser):
    """模拟GoMuseum API用户行为"""
    
    # 用户思考时间（请求之间的间隔）
    wait_time = between(0.5, 2.0)
    
    def on_start(self):
        """用户开始时的初始化"""
        self.user_id = f"user_{random.randint(1000, 9999)}"
        self.image_cache = []  # 缓存一些图像用于重复识别
        self.museum_id = None
        self.auth_token = None
        
        # 模拟用户登录
        self.login()
        
        # 预生成一些测试图像
        self.prepare_test_images()
    
    def login(self):
        """模拟用户登录"""
        response = self.client.post(
            "/api/v1/auth/login",
            json={
                "email": f"{self.user_id}@test.com",
                "password": "test123"
            },
            catch_response=True
        )
        
        if response.status_code == 200:
            data = response.json()
            self.auth_token = data.get("access_token")
            response.success()
        else:
            response.failure(f"Login failed: {response.status_code}")
    
    def prepare_test_images(self):
        """准备测试图像"""
        # 生成10个不同的测试图像数据
        for i in range(10):
            image_data = self._generate_image_data(seed=i)
            self.image_cache.append(image_data)
    
    def _generate_image_data(self, seed: int = None) -> bytes:
        """生成模拟图像数据"""
        if seed is not None:
            random.seed(seed)
        
        # 生成100KB-500KB的随机数据模拟图像
        size = random.randint(100_000, 500_000)
        data = bytes(random.randint(0, 255) for _ in range(size))
        
        # 重置随机种子
        random.seed()
        return data
    
    @task(40)
    def recognize_new_image(self):
        """识别新图像（模拟缓存未命中）"""
        # 生成新的图像数据
        image_data = self._generate_image_data()
        
        with self.client.post(
            "/api/v1/recognize",
            files={"file": ("test.jpg", image_data, "image/jpeg")},
            headers=self._get_headers(),
            catch_response=True,
            name="/api/v1/recognize (new)"
        ) as response:
            if response.status_code == 200:
                data = response.json()
                
                # 检查响应时间
                if response.elapsed.total_seconds() * 1000 > PERFORMANCE_THRESHOLDS["max_response_time_ms"]:
                    response.failure(f"Response too slow: {response.elapsed.total_seconds()*1000:.1f}ms")
                else:
                    response.success()
                    
                # 记录缓存状态
                if data.get("cached"):
                    events.request_success.fire(
                        request_type="CACHE",
                        name="cache_hit",
                        response_time=1,
                        response_length=0
                    )
            else:
                response.failure(f"Recognition failed: {response.status_code}")
    
    @task(30)
    def recognize_cached_image(self):
        """识别缓存图像（模拟缓存命中）"""
        if not self.image_cache:
            self.prepare_test_images()
        
        # 使用缓存的图像
        image_data = random.choice(self.image_cache)
        
        with self.client.post(
            "/api/v1/recognize",
            files={"file": ("cached.jpg", image_data, "image/jpeg")},
            headers=self._get_headers(),
            catch_response=True,
            name="/api/v1/recognize (cached)"
        ) as response:
            if response.status_code == 200:
                data = response.json()
                
                # 缓存命中应该更快
                expected_time = 50 if data.get("cached") else PERFORMANCE_THRESHOLDS["max_response_time_ms"]
                
                if response.elapsed.total_seconds() * 1000 > expected_time:
                    response.failure(f"Response too slow for cached: {response.elapsed.total_seconds()*1000:.1f}ms")
                else:
                    response.success()
            else:
                response.failure(f"Recognition failed: {response.status_code}")
    
    @task(10)
    def get_popular_artworks(self):
        """获取热门艺术品"""
        with self.client.get(
            "/api/v1/artworks/popular",
            params={"limit": 20, "offset": 0},
            headers=self._get_headers(),
            catch_response=True
        ) as response:
            if response.status_code == 200:
                data = response.json()
                
                # 这个端点应该很快（使用了物化视图）
                if response.elapsed.total_seconds() * 1000 > 100:
                    response.failure(f"Popular artworks too slow: {response.elapsed.total_seconds()*1000:.1f}ms")
                else:
                    response.success()
            else:
                response.failure(f"Failed to get popular artworks: {response.status_code}")
    
    @task(10)
    def search_artworks(self):
        """搜索艺术品"""
        search_terms = ["Mona Lisa", "Van Gogh", "Picasso", "Renaissance", "Modern Art"]
        query = random.choice(search_terms)
        
        with self.client.get(
            "/api/v1/artworks/search",
            params={"q": query, "limit": 10},
            headers=self._get_headers(),
            catch_response=True
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Search failed: {response.status_code}")
    
    @task(5)
    def get_user_profile(self):
        """获取用户信息"""
        with self.client.get(
            "/api/v1/user/profile",
            headers=self._get_headers(),
            catch_response=True
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Failed to get profile: {response.status_code}")
    
    @task(5)
    def get_museums(self):
        """获取博物馆列表"""
        with self.client.get(
            "/api/v1/museums",
            params={"limit": 20},
            headers=self._get_headers(),
            catch_response=True
        ) as response:
            if response.status_code == 200:
                data = response.json()
                if data and len(data) > 0:
                    # 记住一个博物馆ID用于后续请求
                    self.museum_id = data[0].get("id")
                response.success()
            else:
                response.failure(f"Failed to get museums: {response.status_code}")
    
    def _get_headers(self) -> Dict[str, str]:
        """获取请求头"""
        headers = {}
        if self.auth_token:
            headers["Authorization"] = f"Bearer {self.auth_token}"
        return headers

class StressTestUser(HttpUser):
    """压力测试用户 - 产生最大负载"""
    
    wait_time = between(0.1, 0.5)  # 更短的等待时间
    
    @task
    def stress_recognition(self):
        """持续压力测试识别接口"""
        # 每次都用新图像，测试最坏情况
        image_data = bytes(random.randint(0, 255) for _ in range(200_000))
        
        self.client.post(
            "/api/v1/recognize",
            files={"file": ("stress.jpg", image_data, "image/jpeg")},
            name="/api/v1/recognize (stress)"
        )

class AdminMonitoringUser(HttpUser):
    """管理员监控用户 - 定期检查系统状态"""
    
    wait_time = between(5, 10)
    
    @task
    def check_health(self):
        """健康检查"""
        response = self.client.get("/api/v1/health")
        if response.status_code != 200:
            logger.error(f"Health check failed: {response.status_code}")
    
    @task
    def check_metrics(self):
        """获取性能指标"""
        response = self.client.get("/api/v1/monitoring/metrics")
        if response.status_code == 200:
            data = response.json()
            
            # 检查关键指标
            cache_hit_rate = data.get("cache_hit_rate", 0)
            if cache_hit_rate < PERFORMANCE_THRESHOLDS["target_cache_hit_rate"] * 100:
                logger.warning(f"Cache hit rate low: {cache_hit_rate}%")
            
            # 记录当前性能
            logger.info(f"Current metrics: {json.dumps(data, indent=2)}")

@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    """测试开始时的初始化"""
    print("=" * 80)
    print("GoMuseum API Load Test Starting")
    print(f"Target host: {environment.host}")
    print(f"Performance thresholds: {json.dumps(PERFORMANCE_THRESHOLDS, indent=2)}")
    print("=" * 80)

@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    """测试结束时的报告"""
    print("\n" + "=" * 80)
    print("GoMuseum API Load Test Results")
    print("=" * 80)
    
    # 计算统计数据
    total_requests = environment.stats.total.num_requests
    total_failures = environment.stats.total.num_failures
    
    if total_requests > 0:
        error_rate = total_failures / total_requests
        avg_response_time = environment.stats.total.avg_response_time
        rps = environment.stats.total.current_rps
        
        print(f"Total Requests: {total_requests}")
        print(f"Total Failures: {total_failures}")
        print(f"Error Rate: {error_rate*100:.2f}%")
        print(f"Average Response Time: {avg_response_time:.1f}ms")
        print(f"Requests Per Second: {rps:.1f}")
        
        # 检查是否满足性能阈值
        print("\nPerformance Threshold Checks:")
        
        if avg_response_time <= PERFORMANCE_THRESHOLDS["max_response_time_ms"]:
            print(f"✅ Response Time: {avg_response_time:.1f}ms <= {PERFORMANCE_THRESHOLDS['max_response_time_ms']}ms")
        else:
            print(f"❌ Response Time: {avg_response_time:.1f}ms > {PERFORMANCE_THRESHOLDS['max_response_time_ms']}ms")
        
        if error_rate <= PERFORMANCE_THRESHOLDS["max_error_rate"]:
            print(f"✅ Error Rate: {error_rate*100:.2f}% <= {PERFORMANCE_THRESHOLDS['max_error_rate']*100}%")
        else:
            print(f"❌ Error Rate: {error_rate*100:.2f}% > {PERFORMANCE_THRESHOLDS['max_error_rate']*100}%")
        
        if rps >= PERFORMANCE_THRESHOLDS["min_throughput_rps"]:
            print(f"✅ Throughput: {rps:.1f} req/s >= {PERFORMANCE_THRESHOLDS['min_throughput_rps']} req/s")
        else:
            print(f"❌ Throughput: {rps:.1f} req/s < {PERFORMANCE_THRESHOLDS['min_throughput_rps']} req/s")
    
    print("=" * 80)

# 自定义报告器
class PerformanceReporter:
    """性能报告生成器"""
    
    @staticmethod
    def generate_html_report(stats, output_file="load_test_report.html"):
        """生成HTML格式的测试报告"""
        html = f"""
        <html>
        <head>
            <title>GoMuseum API Load Test Report</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                h1 {{ color: #333; }}
                table {{ border-collapse: collapse; width: 100%; }}
                th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
                th {{ background-color: #4CAF50; color: white; }}
                .pass {{ color: green; }}
                .fail {{ color: red; }}
            </style>
        </head>
        <body>
            <h1>GoMuseum API Load Test Report</h1>
            <h2>Test Summary</h2>
            <table>
                <tr><th>Metric</th><th>Value</th><th>Status</th></tr>
                <tr>
                    <td>Total Requests</td>
                    <td>{stats.total.num_requests}</td>
                    <td>-</td>
                </tr>
                <tr>
                    <td>Total Failures</td>
                    <td>{stats.total.num_failures}</td>
                    <td class="{'pass' if stats.total.num_failures == 0 else 'fail'}">
                        {'PASS' if stats.total.num_failures == 0 else 'FAIL'}
                    </td>
                </tr>
                <tr>
                    <td>Average Response Time</td>
                    <td>{stats.total.avg_response_time:.1f}ms</td>
                    <td class="{'pass' if stats.total.avg_response_time <= 200 else 'fail'}">
                        {'PASS' if stats.total.avg_response_time <= 200 else 'FAIL'}
                    </td>
                </tr>
                <tr>
                    <td>Requests Per Second</td>
                    <td>{stats.total.current_rps:.1f}</td>
                    <td class="{'pass' if stats.total.current_rps >= 500 else 'fail'}">
                        {'PASS' if stats.total.current_rps >= 500 else 'FAIL'}
                    </td>
                </tr>
            </table>
            
            <h2>Endpoint Statistics</h2>
            <table>
                <tr>
                    <th>Endpoint</th>
                    <th>Requests</th>
                    <th>Failures</th>
                    <th>Avg (ms)</th>
                    <th>Min (ms)</th>
                    <th>Max (ms)</th>
                    <th>P95 (ms)</th>
                    <th>P99 (ms)</th>
                </tr>
        """
        
        for key, entry in stats.entries.items():
            html += f"""
                <tr>
                    <td>{entry.name}</td>
                    <td>{entry.num_requests}</td>
                    <td>{entry.num_failures}</td>
                    <td>{entry.avg_response_time:.1f}</td>
                    <td>{entry.min_response_time:.1f}</td>
                    <td>{entry.max_response_time:.1f}</td>
                    <td>{entry.get_response_time_percentile(0.95):.1f}</td>
                    <td>{entry.get_response_time_percentile(0.99):.1f}</td>
                </tr>
            """
        
        html += """
            </table>
        </body>
        </html>
        """
        
        with open(output_file, 'w') as f:
            f.write(html)
        
        print(f"HTML report saved to {output_file}")

if __name__ == "__main__":
    # 可以直接运行进行简单测试
    from locust import run_single_user
    run_single_user(GoMuseumUser())