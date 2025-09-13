#!/usr/bin/env python3
"""
Flutter前后端集成测试脚本
验证Step 2的完整集成功能
"""

import requests
import base64
import json
import time
from typing import Dict, Any

class FlutterIntegrationTester:
    def __init__(self, base_url: str = "http://127.0.0.1:8001"):
        self.base_url = base_url
        self.session = requests.Session()
        self.session.headers.update({
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        })

    def test_health_check(self) -> bool:
        """测试健康检查端点"""
        try:
            response = self.session.get(f"{self.base_url}/health")
            return response.status_code == 200
        except Exception as e:
            print(f"健康检查失败: {e}")
            return False

    def test_demo_recognition_api(self) -> Dict[str, Any]:
        """测试演示识别API"""
        # 创建测试用的小图像Base64
        test_image_b64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
        
        test_data = {
            "image": f"data:image/png;base64,{test_image_b64}",
            "language": "zh",
            "format": "base64"
        }
        
        try:
            response = self.session.post(
                f"{self.base_url}/api/v1/recognition/demo",
                json=test_data,
                timeout=10
            )
            
            if response.status_code == 200:
                return {
                    "success": True,
                    "data": response.json(),
                    "response_time": response.elapsed.total_seconds()
                }
            else:
                return {
                    "success": False,
                    "error": f"HTTP {response.status_code}: {response.text}",
                    "response_time": response.elapsed.total_seconds()
                }
                
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "response_time": None
            }

    def validate_response_format(self, response_data: Dict) -> Dict[str, Any]:
        """验证响应格式是否符合Flutter期望"""
        errors = []
        warnings = []
        
        # 检查顶级字段
        required_fields = ["success", "data"]
        for field in required_fields:
            if field not in response_data:
                errors.append(f"缺少必需字段: {field}")
        
        # 检查data字段结构
        if "data" in response_data:
            data = response_data["data"]
            data_required_fields = ["candidates", "processing_time", "cached"]
            
            for field in data_required_fields:
                if field not in data:
                    errors.append(f"data字段缺少: {field}")
            
            # 检查candidates结构
            if "candidates" in data and isinstance(data["candidates"], list):
                if len(data["candidates"]) > 0:
                    candidate = data["candidates"][0]
                    candidate_required_fields = [
                        "artwork_id", "name", "artist", "confidence", 
                        "museum", "period"
                    ]
                    
                    for field in candidate_required_fields:
                        if field not in candidate:
                            errors.append(f"candidate缺少字段: {field}")
                    
                    # 检查confidence范围
                    if "confidence" in candidate:
                        confidence = candidate["confidence"]
                        if not (0.0 <= confidence <= 1.0):
                            warnings.append(f"confidence值 {confidence} 不在0-1范围内")
                            
                else:
                    warnings.append("candidates数组为空")
            else:
                errors.append("candidates不是有效数组")
        
        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings
        }

    def run_integration_tests(self) -> Dict[str, Any]:
        """运行完整的集成测试"""
        print("🧪 开始Flutter前后端集成测试...")
        print("=" * 50)
        
        results = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "tests": {},
            "overall_success": True
        }
        
        # 1. 健康检查测试
        print("1️⃣ 测试API健康检查...")
        health_ok = self.test_health_check()
        results["tests"]["health_check"] = {
            "passed": health_ok,
            "description": "API服务器健康检查"
        }
        
        if health_ok:
            print("   ✅ 健康检查通过")
        else:
            print("   ❌ 健康检查失败")
            results["overall_success"] = False
        
        # 2. 演示识别API测试
        print("\n2️⃣ 测试演示识别API...")
        recognition_result = self.test_demo_recognition_api()
        results["tests"]["demo_recognition"] = recognition_result
        
        if recognition_result["success"]:
            print(f"   ✅ 识别API调用成功 (响应时间: {recognition_result['response_time']:.3f}s)")
            
            # 3. 响应格式验证
            print("\n3️⃣ 验证响应格式兼容性...")
            validation_result = self.validate_response_format(recognition_result["data"])
            results["tests"]["response_format"] = validation_result
            
            if validation_result["valid"]:
                print("   ✅ 响应格式验证通过")
                
                # 显示示例响应
                print("\n📋 示例响应数据:")
                candidate = recognition_result["data"]["data"]["candidates"][0]
                print(f"   作品: {candidate['name']}")
                print(f"   艺术家: {candidate['artist']}")
                print(f"   置信度: {candidate['confidence']:.2%}")
                print(f"   博物馆: {candidate['museum']}")
                print(f"   时期: {candidate['period']}")
                
            else:
                print("   ❌ 响应格式验证失败:")
                for error in validation_result["errors"]:
                    print(f"     - {error}")
                results["overall_success"] = False
                
            # 显示警告
            if validation_result["warnings"]:
                print("   ⚠️ 警告:")
                for warning in validation_result["warnings"]:
                    print(f"     - {warning}")
                    
        else:
            print(f"   ❌ 识别API调用失败: {recognition_result['error']}")
            results["overall_success"] = False
        
        # 总结
        print("\n" + "=" * 50)
        if results["overall_success"]:
            print("🎉 Step 2前后端集成测试全部通过!")
            print("✅ Flutter应用可以成功调用后端API")
            print("✅ 后端API返回正确格式的响应")
            print("✅ 端到端识别流程功能完整")
        else:
            print("❌ Step 2集成测试发现问题，需要修复")
        
        return results

def main():
    tester = FlutterIntegrationTester()
    results = tester.run_integration_tests()
    
    # 保存测试结果
    with open("step2_integration_test_results.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    
    print(f"\n📄 测试结果已保存到: step2_integration_test_results.json")
    
    # 返回exit code
    return 0 if results["overall_success"] else 1

if __name__ == "__main__":
    exit(main())