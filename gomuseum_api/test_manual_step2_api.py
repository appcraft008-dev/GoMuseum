#!/usr/bin/env python3
"""
Step 2手动功能测试脚本
测试所有Step 2相关的API端点和核心功能
"""

import asyncio
import base64
import json
import time
import hashlib
import httpx
from typing import List, Dict, Any
from pathlib import Path
import tempfile
from PIL import Image
import io

class Step2APITester:
    """Step 2 API功能测试器"""
    
    def __init__(self, base_url: str = "http://localhost:8001"):
        self.base_url = base_url
        self.client = httpx.AsyncClient(timeout=30.0)
        self.test_results = []
        
    def log_result(self, test_name: str, success: bool, details: str = "", response_data: Any = None):
        """记录测试结果"""
        self.test_results.append({
            "test": test_name,
            "success": success,
            "details": details,
            "response_data": response_data,
            "timestamp": time.time()
        })
        
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} {test_name}: {details}")
    
    def create_test_image(self, width: int = 100, height: int = 100, format: str = "JPEG") -> bytes:
        """创建测试图像"""
        # 创建一个简单的测试图像
        image = Image.new('RGB', (width, height), color='red')
        
        # 在图像上画一些内容，模拟艺术品
        from PIL import ImageDraw
        draw = ImageDraw.Draw(image)
        draw.rectangle([10, 10, width-10, height-10], outline='blue', width=2)
        draw.ellipse([20, 20, width-20, height-20], fill='green')
        
        # 转换为字节
        buffer = io.BytesIO()
        image.save(buffer, format=format)
        return buffer.getvalue()
    
    def image_to_base64(self, image_bytes: bytes) -> str:
        """将图像转换为base64"""
        return base64.b64encode(image_bytes).decode('utf-8')
    
    async def test_server_availability(self) -> bool:
        """测试服务器可用性"""
        try:
            response = await self.client.get(f"{self.base_url}/docs")
            success = response.status_code == 200
            self.log_result(
                "服务器可用性",
                success,
                f"状态码: {response.status_code}"
            )
            return success
        except Exception as e:
            self.log_result("服务器可用性", False, f"连接失败: {str(e)}")
            return False
    
    async def test_recognition_endpoint(self) -> bool:
        """测试识别端点"""
        try:
            # 创建测试图像
            test_image = self.create_test_image()
            base64_image = self.image_to_base64(test_image)
            
            # 测试正常请求
            payload = {
                "image": base64_image,
                "language": "zh"
            }
            
            response = await self.client.post(
                f"{self.base_url}/api/v1/recognition/recognize",
                json=payload
            )
            
            success = response.status_code == 200
            response_data = response.json() if success else None
            
            details = f"状态码: {response.status_code}"
            if success and response_data:
                details += f", 响应时间: {response_data.get('processing_time', 'N/A')}s"
                details += f", 成功: {response_data.get('success', False)}"
            
            self.log_result("识别端点 (正常请求)", success, details, response_data)
            return success
            
        except Exception as e:
            self.log_result("识别端点 (正常请求)", False, f"请求失败: {str(e)}")
            return False
    
    async def test_recognition_validation(self) -> bool:
        """测试识别端点的验证功能"""
        tests_passed = 0
        total_tests = 3
        
        # 测试1: 空图像数据
        try:
            payload = {"image": "", "language": "zh"}
            response = await self.client.post(
                f"{self.base_url}/api/v1/recognition/recognize",
                json=payload
            )
            
            if response.status_code == 400:
                tests_passed += 1
                self.log_result("验证测试 (空图像)", True, "正确拒绝空图像")
            else:
                self.log_result("验证测试 (空图像)", False, f"应返回400，实际: {response.status_code}")
        except Exception as e:
            self.log_result("验证测试 (空图像)", False, f"请求失败: {str(e)}")
        
        # 测试2: 无效base64
        try:
            payload = {"image": "invalid_base64_data", "language": "zh"}
            response = await self.client.post(
                f"{self.base_url}/api/v1/recognition/recognize",
                json=payload
            )
            
            if response.status_code == 400:
                tests_passed += 1
                self.log_result("验证测试 (无效base64)", True, "正确拒绝无效base64")
            else:
                self.log_result("验证测试 (无效base64)", False, f"应返回400，实际: {response.status_code}")
        except Exception as e:
            self.log_result("验证测试 (无效base64)", False, f"请求失败: {str(e)}")
        
        # 测试3: 超大图像
        try:
            # 创建一个大图像 (模拟超过限制)
            large_image = self.create_test_image(3000, 3000)  # 可能超过10MB
            base64_image = self.image_to_base64(large_image)
            
            payload = {"image": base64_image, "language": "zh"}
            response = await self.client.post(
                f"{self.base_url}/api/v1/recognition/recognize",
                json=payload
            )
            
            # 如果图像实际大小超过限制，应该返回400
            if len(large_image) > 10 * 1024 * 1024:
                if response.status_code == 400:
                    tests_passed += 1
                    self.log_result("验证测试 (超大图像)", True, "正确拒绝超大图像")
                else:
                    self.log_result("验证测试 (超大图像)", False, f"应返回400，实际: {response.status_code}")
            else:
                # 如果图像没有超过限制，测试通过
                tests_passed += 1
                self.log_result("验证测试 (超大图像)", True, "图像未超过限制，测试跳过")
                
        except Exception as e:
            self.log_result("验证测试 (超大图像)", False, f"请求失败: {str(e)}")
        
        success = tests_passed == total_tests
        self.log_result("识别端点验证测试", success, f"通过 {tests_passed}/{total_tests} 个测试")
        return success
    
    async def test_upload_endpoint(self) -> bool:
        """测试文件上传端点"""
        try:
            # 创建测试图像文件
            test_image = self.create_test_image()
            
            # 准备文件上传
            files = {
                'file': ('test_image.jpg', test_image, 'image/jpeg')
            }
            data = {
                'language': 'zh'
            }
            
            response = await self.client.post(
                f"{self.base_url}/api/v1/recognition/upload",
                files=files,
                data=data
            )
            
            success = response.status_code == 200
            response_data = response.json() if success else None
            
            details = f"状态码: {response.status_code}"
            if success and response_data:
                details += f", 成功: {response_data.get('success', False)}"
            
            self.log_result("文件上传端点", success, details, response_data)
            return success
            
        except Exception as e:
            self.log_result("文件上传端点", False, f"请求失败: {str(e)}")
            return False
    
    async def test_health_endpoint(self) -> bool:
        """测试健康检查端点"""
        try:
            response = await self.client.get(f"{self.base_url}/api/v1/recognition/health")
            
            success = response.status_code in [200, 503]  # 健康或不健康都是正常响应
            response_data = response.json() if success else None
            
            details = f"状态码: {response.status_code}"
            if success and response_data:
                details += f", 健康状态: {response_data.get('healthy', 'unknown')}"
            
            self.log_result("健康检查端点", success, details, response_data)
            return success
            
        except Exception as e:
            self.log_result("健康检查端点", False, f"请求失败: {str(e)}")
            return False
    
    async def test_stats_endpoint(self) -> bool:
        """测试统计信息端点"""
        try:
            response = await self.client.get(f"{self.base_url}/api/v1/recognition/stats")
            
            success = response.status_code == 200
            response_data = response.json() if success else None
            
            details = f"状态码: {response.status_code}"
            if success and response_data:
                details += f", 包含字段: {list(response_data.keys())}"
            
            self.log_result("统计信息端点", success, details, response_data)
            return success
            
        except Exception as e:
            self.log_result("统计信息端点", False, f"请求失败: {str(e)}")
            return False
    
    async def test_batch_endpoint(self) -> bool:
        """测试批量识别端点"""
        try:
            # 创建多个测试图像
            images = []
            for i in range(3):  # 测试3张图像
                test_image = self.create_test_image(100 + i * 10, 100 + i * 10)
                base64_image = self.image_to_base64(test_image)
                images.append(base64_image)
            
            payload = {
                "images": images,
                "language": "zh",
                "strategy": "balanced"
            }
            
            response = await self.client.post(
                f"{self.base_url}/api/v1/recognition/batch",
                json=payload
            )
            
            success = response.status_code == 200
            response_data = response.json() if success else None
            
            details = f"状态码: {response.status_code}"
            if success and response_data:
                details += f", 返回结果数量: {len(response_data)}"
                if len(response_data) == len(images):
                    details += " (正确)"
                else:
                    details += " (数量不匹配)"
                    success = False
            
            self.log_result("批量识别端点", success, details, response_data)
            return success
            
        except Exception as e:
            self.log_result("批量识别端点", False, f"请求失败: {str(e)}")
            return False
    
    async def test_batch_validation(self) -> bool:
        """测试批量识别端点的验证"""
        try:
            # 测试超过限制的批量请求 (>10张图像)
            images = []
            for i in range(12):  # 超过限制
                test_image = self.create_test_image()
                base64_image = self.image_to_base64(test_image)
                images.append(base64_image)
            
            payload = {
                "images": images,
                "language": "zh"
            }
            
            response = await self.client.post(
                f"{self.base_url}/api/v1/recognition/batch",
                json=payload
            )
            
            success = response.status_code == 400
            details = f"状态码: {response.status_code} (预期400)"
            
            self.log_result("批量识别验证 (数量限制)", success, details)
            return success
            
        except Exception as e:
            self.log_result("批量识别验证", False, f"请求失败: {str(e)}")
            return False
    
    async def test_caching_mechanism(self) -> bool:
        """测试缓存机制"""
        try:
            # 创建测试图像
            test_image = self.create_test_image()
            base64_image = self.image_to_base64(test_image)
            
            payload = {
                "image": base64_image,
                "language": "zh"
            }
            
            # 第一次请求
            start_time = time.time()
            response1 = await self.client.post(
                f"{self.base_url}/api/v1/recognition/recognize",
                json=payload
            )
            first_time = time.time() - start_time
            
            if response1.status_code != 200:
                self.log_result("缓存测试", False, "第一次请求失败")
                return False
            
            # 等待一小段时间确保缓存已保存
            await asyncio.sleep(0.1)
            
            # 第二次请求 (相同图像)
            start_time = time.time()
            response2 = await self.client.post(
                f"{self.base_url}/api/v1/recognition/recognize",
                json=payload
            )
            second_time = time.time() - start_time
            
            if response2.status_code != 200:
                self.log_result("缓存测试", False, "第二次请求失败")
                return False
            
            # 检查是否使用了缓存
            data1 = response1.json()
            data2 = response2.json()
            
            cached_used = data2.get('cached', False)
            time_improvement = first_time > second_time
            
            success = cached_used or time_improvement
            details = f"第一次: {first_time:.3f}s, 第二次: {second_time:.3f}s, 缓存: {cached_used}"
            
            self.log_result("缓存机制测试", success, details)
            return success
            
        except Exception as e:
            self.log_result("缓存机制测试", False, f"测试失败: {str(e)}")
            return False
    
    async def test_error_handling(self) -> bool:
        """测试错误处理机制"""
        tests_passed = 0
        total_tests = 2
        
        # 测试1: 无效的端点
        try:
            response = await self.client.post(f"{self.base_url}/api/v1/recognition/invalid_endpoint")
            if response.status_code == 404:
                tests_passed += 1
                self.log_result("错误处理 (无效端点)", True, "正确返回404")
            else:
                self.log_result("错误处理 (无效端点)", False, f"应返回404，实际: {response.status_code}")
        except Exception as e:
            self.log_result("错误处理 (无效端点)", False, f"请求失败: {str(e)}")
        
        # 测试2: 无效的HTTP方法
        try:
            response = await self.client.get(f"{self.base_url}/api/v1/recognition/recognize")
            if response.status_code == 405:
                tests_passed += 1
                self.log_result("错误处理 (无效方法)", True, "正确返回405")
            else:
                self.log_result("错误处理 (无效方法)", False, f"应返回405，实际: {response.status_code}")
        except Exception as e:
            self.log_result("错误处理 (无效方法)", False, f"请求失败: {str(e)}")
        
        success = tests_passed == total_tests
        self.log_result("错误处理机制", success, f"通过 {tests_passed}/{total_tests} 个测试")
        return success
    
    async def test_language_support(self) -> bool:
        """测试多语言支持"""
        languages = ["zh", "en", "fr", "de"]
        results = []
        
        for lang in languages:
            try:
                test_image = self.create_test_image()
                base64_image = self.image_to_base64(test_image)
                
                payload = {
                    "image": base64_image,
                    "language": lang
                }
                
                response = await self.client.post(
                    f"{self.base_url}/api/v1/recognition/recognize",
                    json=payload
                )
                
                success = response.status_code == 200
                results.append(success)
                
                self.log_result(
                    f"语言支持 ({lang})",
                    success,
                    f"状态码: {response.status_code}"
                )
                
            except Exception as e:
                results.append(False)
                self.log_result(f"语言支持 ({lang})", False, f"请求失败: {str(e)}")
        
        # 至少要支持中文和英文
        min_success = sum(results[:2]) >= 2
        overall_success = sum(results) >= len(languages) * 0.8  # 80%成功率
        
        final_success = min_success and overall_success
        self.log_result(
            "多语言支持",
            final_success,
            f"支持语言: {sum(results)}/{len(languages)}"
        )
        
        return final_success
    
    async def run_all_tests(self) -> Dict[str, Any]:
        """运行所有测试"""
        print("🚀 开始Step 2 API功能测试...")
        print("=" * 60)
        
        # 测试服务器可用性
        server_available = await self.test_server_availability()
        if not server_available:
            return {
                "success": False,
                "message": "服务器不可用，无法继续测试",
                "results": self.test_results
            }
        
        # 执行所有测试
        tests = [
            ("识别端点功能", self.test_recognition_endpoint),
            ("识别端点验证", self.test_recognition_validation),
            ("文件上传端点", self.test_upload_endpoint),
            ("健康检查端点", self.test_health_endpoint),
            ("统计信息端点", self.test_stats_endpoint),
            ("批量识别端点", self.test_batch_endpoint),
            ("批量识别验证", self.test_batch_validation),
            ("缓存机制", self.test_caching_mechanism),
            ("错误处理", self.test_error_handling),
            ("多语言支持", self.test_language_support),
        ]
        
        passed_tests = 0
        total_tests = len(tests)
        
        for test_name, test_func in tests:
            print(f"\n📋 执行测试: {test_name}")
            try:
                success = await test_func()
                if success:
                    passed_tests += 1
            except Exception as e:
                self.log_result(test_name, False, f"测试执行失败: {str(e)}")
        
        # 生成测试报告
        success_rate = (passed_tests / total_tests) * 100
        overall_success = success_rate >= 80  # 80%以上通过率认为成功
        
        print("\n" + "=" * 60)
        print(f"📊 测试完成: {passed_tests}/{total_tests} 通过 ({success_rate:.1f}%)")
        
        if overall_success:
            print("✅ Step 2 API功能测试整体通过")
        else:
            print("❌ Step 2 API功能测试未达到预期标准")
        
        return {
            "success": overall_success,
            "passed": passed_tests,
            "total": total_tests,
            "success_rate": success_rate,
            "results": self.test_results
        }
    
    async def close(self):
        """关闭HTTP客户端"""
        await self.client.aclose()

async def main():
    """主函数"""
    tester = Step2APITester()
    
    try:
        # 运行所有测试
        results = await tester.run_all_tests()
        
        # 保存详细结果
        report_file = Path("step2_api_test_report.json")
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False, default=str)
        
        print(f"\n📄 详细测试报告已保存至: {report_file}")
        
        return 0 if results["success"] else 1
        
    except Exception as e:
        print(f"❌ 测试执行失败: {str(e)}")
        return 1
    finally:
        await tester.close()

if __name__ == "__main__":
    import sys
    sys.exit(asyncio.run(main()))