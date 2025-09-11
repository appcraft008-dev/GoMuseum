#!/usr/bin/env python3
"""
GoMuseum Step 2 全面功能测试
测试覆盖：
1. API功能测试
2. 图像处理测试  
3. 集成测试
4. 安全性测试
5. 性能测试
"""

import asyncio
import aiohttp
import base64
import json
import time
import uuid
import hashlib
import subprocess
import sys
import os
from pathlib import Path
from PIL import Image
import io
from typing import Dict, List, Any, Optional
import concurrent.futures

class GoMuseumTester:
    def __init__(self, base_url: str = "http://127.0.0.1:8001"):
        self.base_url = base_url
        self.session = None
        self.test_results = []
        self.failed_tests = []
        
    async def setup(self):
        """测试环境准备"""
        self.session = aiohttp.ClientSession()
        
    async def teardown(self):
        """测试环境清理"""
        if self.session:
            await self.session.close()

    def create_test_image(self, width: int = 200, height: int = 200, format: str = "JPEG") -> bytes:
        """创建测试图片"""
        image = Image.new('RGB', (width, height), color='red')
        buffer = io.BytesIO()
        image.save(buffer, format=format)
        return buffer.getvalue()

    def image_to_base64(self, image_bytes: bytes) -> str:
        """将图片转换为base64"""
        return base64.b64encode(image_bytes).decode('utf-8')

    async def test_api_health_check(self) -> bool:
        """测试健康检查端点"""
        print("🔍 测试健康检查端点...")
        try:
            async with self.session.get(f"{self.base_url}/api/v1/recognition/health") as response:
                if response.status == 200:
                    data = await response.json()
                    print(f"✅ 健康检查通过: {data}")
                    return True
                else:
                    print(f"❌ 健康检查失败: HTTP {response.status}")
                    return False
        except Exception as e:
            print(f"❌ 健康检查异常: {e}")
            return False

    async def test_single_image_recognition(self) -> bool:
        """测试单张图片识别API"""
        print("🔍 测试单张图片识别API...")
        try:
            # 创建测试图片
            image_bytes = self.create_test_image()
            base64_image = self.image_to_base64(image_bytes)
            
            # 发送识别请求
            payload = {
                "image": base64_image,
                "format": "JPEG"
            }
            
            async with self.session.post(
                f"{self.base_url}/api/v1/recognition/recognize",
                json=payload
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    print(f"✅ 单张图片识别成功")
                    # 从candidates中获取第一个结果
                    candidates = data.get('candidates', [])
                    if candidates:
                        first_result = candidates[0]
                        print(f"   - 识别结果: {first_result.get('name', 'N/A')}")
                        print(f"   - 艺术家: {first_result.get('artist', 'N/A')}")
                        print(f"   - 博物馆: {first_result.get('museum', 'N/A')}")
                    print(f"   - 整体置信度: {data.get('confidence', 'N/A')}")
                    print(f"   - 处理时间: {data.get('processing_time', 'N/A')}s")
                    print(f"   - 缓存状态: {'命中' if data.get('cached', False) else '未命中'}")
                    return True
                else:
                    error_text = await response.text()
                    print(f"❌ 单张图片识别失败: HTTP {response.status} - {error_text}")
                    return False
        except Exception as e:
            print(f"❌ 单张图片识别异常: {e}")
            return False

    async def test_batch_recognition(self) -> bool:
        """测试批量识别API"""
        print("🔍 测试批量识别API...")
        try:
            # 创建多张测试图片（API期望的是字符串列表）
            images = []
            for i in range(3):
                image_bytes = self.create_test_image(width=100+i*50, height=100+i*50)
                base64_image = self.image_to_base64(image_bytes)
                images.append(base64_image)  # 直接添加base64字符串
            
            payload = {"images": images}
            
            async with self.session.post(
                f"{self.base_url}/api/v1/recognition/batch",
                json=payload
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    print(f"✅ 批量识别成功")
                    print(f"   - 处理图片数量: {len(data)}")
                    # 计算总处理时间
                    total_time = sum(result.get('processing_time', 0) for result in data)
                    print(f"   - 总处理时间: {total_time:.3f}s")
                    return True
                else:
                    error_text = await response.text()
                    print(f"❌ 批量识别失败: HTTP {response.status} - {error_text}")
                    return False
        except Exception as e:
            print(f"❌ 批量识别异常: {e}")
            return False

    async def test_api_response_format(self) -> bool:
        """测试API响应格式验证"""
        print("🔍 测试API响应格式...")
        try:
            image_bytes = self.create_test_image()
            base64_image = self.image_to_base64(image_bytes)
            
            payload = {
                "image": base64_image
            }
            
            async with self.session.post(
                f"{self.base_url}/api/v1/recognition/recognize",
                json=payload
            ) as response:
                data = await response.json()
                
                # 验证响应格式（基于实际API返回的字段）
                required_fields = ['success', 'confidence', 'processing_time', 'candidates', 'cached', 'timestamp', 'image_hash']
                missing_fields = [field for field in required_fields if field not in data]
                
                if missing_fields:
                    print(f"❌ API响应格式错误，缺少字段: {missing_fields}")
                    print(f"   实际返回字段: {list(data.keys())}")
                    return False
                    
                # 验证candidates字段结构
                candidates = data.get('candidates', [])
                if candidates:
                    candidate = candidates[0]
                    candidate_fields = ['name', 'artist', 'confidence', 'museum']
                    missing_candidate_fields = [field for field in candidate_fields if field not in candidate]
                    
                    if missing_candidate_fields:
                        print(f"❌ 识别候选项格式错误，缺少字段: {missing_candidate_fields}")
                        print(f"   实际候选项字段: {list(candidate.keys())}")
                        return False
                
                print("✅ API响应格式验证通过")
                print(f"   - 成功标志: {data.get('success')}")
                print(f"   - 置信度: {data.get('confidence')}")
                print(f"   - 候选项数量: {len(candidates)}")
                return True
                
        except Exception as e:
            print(f"❌ API响应格式验证异常: {e}")
            return False

    async def test_cache_mechanism(self) -> bool:
        """测试缓存机制"""
        print("🔍 测试缓存机制...")
        try:
            # 使用相同的图片进行两次识别
            image_bytes = self.create_test_image()
            base64_image = self.image_to_base64(image_bytes)
            
            payload = {
                "image": base64_image
            }
            
            # 第一次请求
            start_time = time.time()
            async with self.session.post(
                f"{self.base_url}/api/v1/recognition/recognize",
                json=payload
            ) as response:
                first_response = await response.json()
                first_time = time.time() - start_time
            
            # 第二次请求（应该命中缓存）
            start_time = time.time()
            async with self.session.post(
                f"{self.base_url}/api/v1/recognition/recognize",
                json=payload
            ) as response:
                second_response = await response.json()
                second_time = time.time() - start_time
            
            # 检查缓存状态字段
            first_cached = first_response.get('cached', False)
            second_cached = second_response.get('cached', False) 
            
            # 验证缓存机制：
            # 1. 检查cached字段
            # 2. 检查响应时间
            if second_cached or (second_time < first_time * 0.9):
                print(f"✅ 缓存机制工作正常")
                print(f"   - 首次请求: {first_time:.3f}s (cached: {first_cached})")
                print(f"   - 第二次请求: {second_time:.3f}s (cached: {second_cached})")
                if second_time < first_time:
                    print(f"   - 性能提升: {((first_time - second_time) / first_time * 100):.1f}%")
                print(f"   - 图片哈希: {first_response.get('image_hash', 'N/A')[:8]}...")
                return True
            else:
                print(f"❌ 缓存机制可能未生效")
                print(f"   - 首次请求: {first_time:.3f}s (cached: {first_cached})")
                print(f"   - 第二次请求: {second_time:.3f}s (cached: {second_cached})")
                return False
                
        except Exception as e:
            print(f"❌ 缓存机制测试异常: {e}")
            return False

    async def test_image_processing(self) -> bool:
        """测试图像处理功能"""
        print("🔍 测试图像处理功能...")
        try:
            # 测试不同格式和尺寸的图片
            test_cases = [
                {"width": 50, "height": 50, "format": "JPEG"},
                {"width": 1000, "height": 1000, "format": "JPEG"},
                {"width": 200, "height": 300, "format": "PNG"},
            ]
            
            for i, case in enumerate(test_cases):
                print(f"   测试用例 {i+1}: {case['width']}x{case['height']} {case['format']}")
                
                # 创建指定格式的图片
                image = Image.new('RGB', (case['width'], case['height']), color='blue')
                buffer = io.BytesIO()
                image.save(buffer, format=case['format'])
                image_bytes = buffer.getvalue()
                base64_image = self.image_to_base64(image_bytes)
                
                payload = {
                    "image": base64_image,
                    "format": case['format']
                }
                
                async with self.session.post(
                    f"{self.base_url}/api/v1/recognition/recognize",
                    json=payload
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        print(f"     ✅ 处理成功: {data.get('processing_time', 'N/A')}s")
                    else:
                        print(f"     ❌ 处理失败: HTTP {response.status}")
                        return False
            
            print("✅ 图像处理功能测试通过")
            return True
            
        except Exception as e:
            print(f"❌ 图像处理功能测试异常: {e}")
            return False

    async def test_error_handling(self) -> bool:
        """测试错误处理"""
        print("🔍 测试错误处理...")
        test_passed = True
        
        # 测试无效的base64
        try:
            payload = {"image": "invalid_base64", "format": "JPEG"}
            async with self.session.post(
                f"{self.base_url}/api/v1/recognition/recognize",
                json=payload
            ) as response:
                if response.status in [400, 422]:
                    print("   ✅ 无效base64处理正确")
                else:
                    print(f"   ❌ 无效base64未正确处理: HTTP {response.status}")
                    test_passed = False
        except Exception as e:
            print(f"   ❌ 无效base64测试异常: {e}")
            test_passed = False
        
        # 测试缺少必需字段
        try:
            payload = {"format": "JPEG"}  # 缺少image字段
            async with self.session.post(
                f"{self.base_url}/api/v1/recognition/recognize",
                json=payload
            ) as response:
                if response.status in [400, 422]:
                    print("   ✅ 缺少字段处理正确")
                else:
                    print(f"   ❌ 缺少字段未正确处理: HTTP {response.status}")
                    test_passed = False
        except Exception as e:
            print(f"   ❌ 缺少字段测试异常: {e}")
            test_passed = False
        
        # 测试超大图片
        try:
            # 创建一个很大的图片
            large_image = self.create_test_image(width=5000, height=5000)
            base64_image = self.image_to_base64(large_image)
            
            payload = {"image": base64_image, "format": "JPEG"}
            async with self.session.post(
                f"{self.base_url}/api/v1/recognition/recognize",
                json=payload
            ) as response:
                # 应该能处理或者返回适当的错误
                if response.status in [200, 413, 422]:
                    print("   ✅ 超大图片处理正确")
                else:
                    print(f"   ❌ 超大图片处理异常: HTTP {response.status}")
                    test_passed = False
        except Exception as e:
            print(f"   ❌ 超大图片测试异常: {e}")
            test_passed = False
        
        if test_passed:
            print("✅ 错误处理测试通过")
        else:
            print("❌ 错误处理测试失败")
        
        return test_passed

    async def test_performance(self) -> bool:
        """测试性能"""
        print("🔍 测试API性能...")
        try:
            # 并发测试
            image_bytes = self.create_test_image()
            base64_image = self.image_to_base64(image_bytes)
            
            payload = {
                "image": base64_image,
                "format": "JPEG"
            }
            
            async def single_request():
                async with self.session.post(
                    f"{self.base_url}/api/v1/recognition/recognize",
                    json=payload
                ) as response:
                    return response.status == 200
            
            # 执行并发请求
            start_time = time.time()
            tasks = [single_request() for _ in range(10)]
            results = await asyncio.gather(*tasks)
            end_time = time.time()
            
            success_rate = sum(results) / len(results) * 100
            total_time = end_time - start_time
            avg_time = total_time / len(results)
            
            print(f"   - 并发请求数: {len(results)}")
            print(f"   - 成功率: {success_rate:.1f}%")
            print(f"   - 总耗时: {total_time:.3f}s")
            print(f"   - 平均响应时间: {avg_time:.3f}s")
            
            if success_rate >= 90 and avg_time < 2.0:
                print("✅ 性能测试通过")
                return True
            else:
                print("❌ 性能测试未达标")
                return False
                
        except Exception as e:
            print(f"❌ 性能测试异常: {e}")
            return False

    async def test_flutter_app_integration(self) -> bool:
        """测试Flutter应用集成（检查应用文件结构）"""
        print("🔍 测试Flutter应用集成...")
        try:
            app_path = Path("gomuseum_app")
            
            # 检查关键文件是否存在（基于实际DDD架构）
            key_files = [
                "pubspec.yaml",
                "lib/main.dart",
                "lib/core/config/api_config.dart",
                "lib/features/recognition/data/datasources/recognition_api.dart",
                "lib/features/recognition/data/models/recognition_response_model.dart",
            ]
            
            missing_files = []
            existing_files = []
            for file in key_files:
                if not (app_path / file).exists():
                    missing_files.append(file)
                else:
                    existing_files.append(file)
            
            print(f"   - 存在的关键文件数量: {len(existing_files)}/{len(key_files)}")
            
            # 检查pubspec.yaml配置
            pubspec_path = app_path / "pubspec.yaml"
            if pubspec_path.exists():
                with open(pubspec_path, 'r', encoding='utf-8') as f:
                    pubspec_content = f.read()
                    required_deps = ['camera', 'http']  # 简化依赖检查
                    missing_deps = [dep for dep in required_deps if dep not in pubspec_content]
                    
                    if missing_deps:
                        print(f"   ⚠️  Flutter应用缺少依赖: {missing_deps}")
                    else:
                        print(f"   ✅ 必要依赖检查通过")
            
            # 检查lib目录结构
            lib_path = app_path / "lib"
            if lib_path.exists():
                dart_files = list(lib_path.rglob("*.dart"))
                print(f"   - Dart文件总数: {len(dart_files)}")
                
                # 检查关键功能模块
                features_path = lib_path / "features"
                if features_path.exists():
                    feature_dirs = [d.name for d in features_path.iterdir() if d.is_dir()]
                    print(f"   - 功能模块: {feature_dirs}")
                
                if len(dart_files) >= 10:  # 至少有基本的文件结构
                    print("✅ Flutter应用集成检查通过")
                    return True
                else:
                    print("❌ Flutter应用文件结构不完整")
                    return False
            else:
                print("❌ Flutter应用lib目录不存在")
                return False
            
        except Exception as e:
            print(f"❌ Flutter应用集成测试异常: {e}")
            return False

    async def test_security(self) -> bool:
        """测试安全性"""
        print("🔍 测试安全性...")
        test_passed = True
        
        # 测试SQL注入防护
        try:
            malicious_payload = {
                "image": "'; DROP TABLE users; --",
                "format": "JPEG"
            }
            async with self.session.post(
                f"{self.base_url}/api/v1/recognition/recognize",
                json=malicious_payload
            ) as response:
                if response.status in [400, 422]:
                    print("   ✅ SQL注入防护正常")
                else:
                    print(f"   ❌ SQL注入防护可能存在问题: HTTP {response.status}")
                    test_passed = False
        except Exception as e:
            print(f"   ❌ SQL注入测试异常: {e}")
            test_passed = False
        
        # 测试超长输入
        try:
            very_long_string = "A" * 10000
            payload = {
                "image": very_long_string
            }
            async with self.session.post(
                f"{self.base_url}/api/v1/recognition/recognize",
                json=payload
            ) as response:
                # 检查响应
                if response.status in [400, 413, 422]:
                    print("   ✅ 超长输入防护正常（拒绝请求）")
                elif response.status == 200:
                    # 如果返回200，检查是否有错误信息
                    data = await response.json()
                    if not data.get('success', True):
                        print("   ✅ 超长输入防护正常（返回错误）")
                    else:
                        # 检查响应内容，如果是无效的base64，应该在处理中被捕获
                        print(f"   ⚠️  超长输入被处理但未拒绝，检查详细响应")
                        print(f"      响应成功标志: {data.get('success', False)}")
                        if data.get('success', False):
                            print("   ❌ 超长无效输入未被正确拒绝")
                            test_passed = False
                        else:
                            print("   ✅ 超长输入虽返回200但标记为失败")
                else:
                    print(f"   ❌ 超长输入处理异常: HTTP {response.status}")
                    test_passed = False
        except Exception as e:
            print(f"   ❌ 超长输入测试异常: {e}")
            test_passed = False
        
        if test_passed:
            print("✅ 安全性测试通过")
        else:
            print("❌ 安全性测试失败")
        
        return test_passed

    async def run_all_tests(self) -> Dict[str, Any]:
        """运行所有测试"""
        print("🚀 开始GoMuseum Step 2全面功能测试\n")
        print("=" * 60)
        
        await self.setup()
        
        test_suite = [
            ("健康检查", self.test_api_health_check),
            ("单张图片识别", self.test_single_image_recognition),
            ("批量识别", self.test_batch_recognition),
            ("API响应格式", self.test_api_response_format),
            ("缓存机制", self.test_cache_mechanism),
            ("图像处理", self.test_image_processing),
            ("错误处理", self.test_error_handling),
            ("性能测试", self.test_performance),
            ("Flutter集成", self.test_flutter_app_integration),
            ("安全性测试", self.test_security)
        ]
        
        results = {}
        passed = 0
        total = len(test_suite)
        
        for test_name, test_func in test_suite:
            print(f"\n📝 {test_name}")
            print("-" * 40)
            
            try:
                result = await test_func()
                results[test_name] = result
                if result:
                    passed += 1
                else:
                    self.failed_tests.append(test_name)
            except Exception as e:
                print(f"❌ {test_name}测试异常: {e}")
                results[test_name] = False
                self.failed_tests.append(test_name)
        
        await self.teardown()
        
        # 生成测试报告
        print("\n" + "=" * 60)
        print("📊 测试结果汇总")
        print("=" * 60)
        
        for test_name, result in results.items():
            status = "✅ 通过" if result else "❌ 失败"
            print(f"{test_name}: {status}")
        
        print(f"\n总体结果: {passed}/{total} 测试通过")
        success_rate = (passed / total) * 100
        print(f"成功率: {success_rate:.1f}%")
        
        if self.failed_tests:
            print(f"\n⚠️  失败的测试: {', '.join(self.failed_tests)}")
        
        # 判断整体测试结果
        overall_status = "通过" if success_rate >= 80 else "失败"
        print(f"\n🎯 整体测试状态: {overall_status}")
        
        return {
            "total_tests": total,
            "passed_tests": passed,
            "failed_tests": len(self.failed_tests),
            "success_rate": success_rate,
            "failed_test_names": self.failed_tests,
            "overall_status": overall_status,
            "detailed_results": results
        }

async def main():
    """主函数"""
    # 检查API服务是否运行
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get("http://127.0.0.1:8001/api/v1/recognition/health") as response:
                if response.status != 200:
                    print("❌ API服务未运行在端口8001，请先启动服务")
                    return
    except Exception:
        print("❌ 无法连接到API服务，请确保服务在端口8001运行")
        return
    
    # 运行测试
    tester = GoMuseumTester()
    results = await tester.run_all_tests()
    
    # 保存详细测试报告
    report_path = "step2_test_report.json"
    with open(report_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    
    print(f"\n📄 详细测试报告已保存到: {report_path}")
    
    # 返回退出码
    return 0 if results['overall_status'] == '通过' else 1

if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n❌ 测试被用户中断")
        sys.exit(1)
    except Exception as e:
        print(f"❌ 测试运行异常: {e}")
        sys.exit(1)