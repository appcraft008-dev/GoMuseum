#!/usr/bin/env python3
"""
GoMuseum API完整测试脚本
测试所有主要API端点的功能
"""

import requests
import base64
import json
import time
from typing import Optional

class GoMuseumAPITester:
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.session = requests.Session()
        self.user_id: Optional[str] = None
        
    def print_section(self, title: str):
        print(f"\n{'='*50}")
        print(f"🧪 {title}")
        print('='*50)
        
    def print_result(self, test_name: str, response: requests.Response):
        status = "✅ PASS" if 200 <= response.status_code < 300 else "❌ FAIL"
        print(f"{status} {test_name} - Status: {response.status_code}")
        
        try:
            data = response.json()
            print(json.dumps(data, indent=2, ensure_ascii=False))
        except:
            print(f"Response: {response.text}")
            
    def test_health_checks(self):
        """测试健康检查端点"""
        self.print_section("Health Checks")
        
        # 基础健康检查
        response = self.session.get(f"{self.base_url}/health")
        self.print_result("Basic Health Check", response)
        
        # 详细健康检查
        response = self.session.get(f"{self.base_url}/health/detailed")
        self.print_result("Detailed Health Check", response)
        
        # 就绪检查
        response = self.session.get(f"{self.base_url}/health/ready")
        self.print_result("Readiness Check", response)
        
        # 存活检查
        response = self.session.get(f"{self.base_url}/health/live")
        self.print_result("Liveness Check", response)
        
    def test_user_management(self):
        """测试用户管理功能"""
        self.print_section("User Management")
        
        # 1. 创建用户
        user_data = {
            "email": f"test_{int(time.time())}@example.com",
            "username": f"testuser_{int(time.time())}",
            "language": "zh"
        }
        
        response = self.session.post(f"{self.base_url}/api/v1/user", json=user_data)
        self.print_result("Create User", response)
        
        if response.status_code == 200:
            self.user_id = response.json().get('id')
            print(f"📝 User ID saved: {self.user_id}")
            
            # 2. 获取用户信息
            response = self.session.get(f"{self.base_url}/api/v1/user/{self.user_id}")
            self.print_result("Get User Info", response)
            
            # 3. 查询用户配额
            response = self.session.get(f"{self.base_url}/api/v1/user/{self.user_id}/quota")
            self.print_result("Get User Quota", response)
            
            # 4. 更新用户信息
            update_data = {
                "username": f"updated_user_{int(time.time())}",
                "language": "en"
            }
            response = self.session.put(f"{self.base_url}/api/v1/user/{self.user_id}", json=update_data)
            self.print_result("Update User", response)
            
    def test_image_recognition(self):
        """测试图片识别功能"""
        if not self.user_id:
            print("❌ No user ID available, skipping recognition tests")
            return
            
        self.print_section("Image Recognition")
        
        # 1. 创建测试图片数据
        test_images = [
            "Small test image",
            "Another test image with different content",
            "Third test image for caching test"
        ]
        
        for i, image_content in enumerate(test_images, 1):
            image_b64 = base64.b64encode(image_content.encode()).decode()
            
            recognition_data = {
                "image": image_b64,
                "language": "zh",
                "user_id": self.user_id
            }
            
            response = self.session.post(f"{self.base_url}/api/v1/recognize", json=recognition_data)
            self.print_result(f"Image Recognition {i}", response)
            
            # 测试缓存 - 重复同一个图片
            if i == 1:
                print("\n🔄 Testing Cache - Same Image Again:")
                response = self.session.post(f"{self.base_url}/api/v1/recognize", json=recognition_data)
                self.print_result("Cached Recognition", response)
                
        # 2. 获取识别统计
        response = self.session.get(f"{self.base_url}/api/v1/recognize/stats")
        self.print_result("Recognition Statistics", response)
        
        # 3. 获取用户识别历史
        response = self.session.get(f"{self.base_url}/api/v1/recognize/history/{self.user_id}")
        self.print_result("User Recognition History", response)
        
    def test_artwork_interactions(self):
        """测试艺术品交互功能"""
        self.print_section("Artwork Interactions")
        
        # 使用mock数据中的艺术品ID
        artwork_id = "mock-uuid-1"
        
        # 1. 生成解释
        explanation_data = {
            "language": "zh",
            "style": "detailed",
            "user_id": self.user_id
        }
        
        response = self.session.post(f"{self.base_url}/api/v1/artwork/{artwork_id}/explanation", 
                                   json=explanation_data)
        self.print_result("Generate Explanation", response)
        
        # 2. 获取缓存的解释
        response = self.session.get(f"{self.base_url}/api/v1/artwork/{artwork_id}/explanation?language=zh")
        self.print_result("Get Cached Explanation", response)
        
        # 3. 与艺术品聊天
        response = self.session.post(f"{self.base_url}/api/v1/artwork/{artwork_id}/chat?question=这幅画的历史背景是什么？&language=zh&user_id={self.user_id}")
        self.print_result("Chat with Artwork", response)
        
    def test_quota_consumption(self):
        """测试配额消费"""
        if not self.user_id:
            print("❌ No user ID available, skipping quota tests")
            return
            
        self.print_section("Quota Consumption")
        
        # 查看当前配额
        response = self.session.get(f"{self.base_url}/api/v1/user/{self.user_id}/quota")
        self.print_result("Current Quota", response)
        
        if response.status_code == 200:
            quota_info = response.json()
            current_quota = quota_info.get('free_quota', 0)
            
            # 消费配额
            response = self.session.post(f"{self.base_url}/api/v1/user/{self.user_id}/consume-quota")
            self.print_result("Consume Quota", response)
            
            # 再次查看配额
            response = self.session.get(f"{self.base_url}/api/v1/user/{self.user_id}/quota")
            self.print_result("Quota After Consumption", response)
            
    def test_api_documentation(self):
        """测试API文档"""
        self.print_section("API Documentation")
        
        # OpenAPI规范
        response = self.session.get(f"{self.base_url}/openapi.json")
        self.print_result("OpenAPI Specification", response)
        
        # 文档页面
        response = self.session.get(f"{self.base_url}/docs")
        print(f"✅ Documentation Page - Status: {response.status_code}")
        print(f"Content-Type: {response.headers.get('content-type')}")
        
    def run_all_tests(self):
        """运行所有测试"""
        print("🚀 GoMuseum API Complete Test Suite")
        print(f"🔗 Base URL: {self.base_url}")
        
        try:
            self.test_health_checks()
            self.test_user_management()
            self.test_image_recognition()
            self.test_artwork_interactions()
            self.test_quota_consumption()
            self.test_api_documentation()
            
            print(f"\n{'='*50}")
            print("🎉 All tests completed!")
            print('='*50)
            
        except Exception as e:
            print(f"\n❌ Test suite failed with error: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    # 运行测试
    tester = GoMuseumAPITester()
    tester.run_all_tests()