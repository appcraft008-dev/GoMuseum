#!/usr/bin/env python3
"""
测试演示识别API的脚本
"""
import requests
import base64
from PIL import Image, ImageDraw
import io
import json

def create_test_image():
    """创建一个简单的测试图片"""
    # 创建一个简单的测试图片 (200x200 像素)
    img = Image.new('RGB', (200, 200), color='white')
    draw = ImageDraw.Draw(img)
    
    # 画一个简单的蒙娜丽莎脸部轮廓
    draw.rectangle([50, 60, 150, 140], outline='black', width=2)
    draw.ellipse([70, 80, 90, 100], fill='black')  # 左眼
    draw.ellipse([110, 80, 130, 100], fill='black')  # 右眼
    draw.arc([80, 110, 120, 130], 0, 180, fill='black', width=2)  # 嘴巴
    draw.text((60, 170), "Test Art", fill='black')
    
    # 转换为base64
    buffer = io.BytesIO()
    img.save(buffer, format='PNG')
    image_data = buffer.getvalue()
    base64_image = base64.b64encode(image_data).decode('utf-8')
    
    return base64_image

def test_demo_recognition_api():
    """测试演示识别API"""
    url = "http://localhost:8001/api/v1/recognition/demo"
    
    # 创建测试图片
    base64_image = create_test_image()
    
    # 准备请求数据
    data = {
        "image": base64_image,
        "format": "base64",
        "language": "zh"
    }
    
    try:
        print("正在测试演示识别API...")
        print(f"请求URL: {url}")
        print(f"图片大小: {len(base64_image)} 字符")
        
        response = requests.post(url, json=data)
        
        print(f"响应状态码: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print("✅ 演示API调用成功!")
            print(f"识别结果:")
            print(f"  作品标题: {result.get('artwork_title', 'N/A')}")
            print(f"  艺术家: {result.get('artist_name', 'N/A')}")
            print(f"  创作年代: {result.get('creation_year', 'N/A')}")
            print(f"  风格: {result.get('style', 'N/A')}")
            print(f"  置信度: {result.get('confidence', 0)}")
            print(f"  描述: {result.get('description', 'N/A')}")
            print(f"  博物馆: {result.get('museum', 'N/A')}")
            print(f"  是否模拟: {result.get('mock_response', False)}")
            return True
        else:
            print(f"❌ API调用失败: {response.status_code}")
            print(f"错误信息: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ 连接错误: {str(e)}")
        return False

def test_demo_health():
    """测试演示API健康检查"""
    url = "http://localhost:8001/api/v1/recognition/demo-health"
    
    try:
        response = requests.get(url)
        if response.status_code == 200:
            print("✅ 演示API健康检查通过")
            print(f"响应: {response.json()}")
            return True
        else:
            print(f"❌ 演示API健康检查失败: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ 演示API连接错误: {str(e)}")
        return False

def test_original_api():
    """测试原来的识别API是否仍有问题"""
    url = "http://localhost:8001/api/v1/recognition/recognize"
    
    base64_image = create_test_image()
    data = {
        "image": base64_image,
        "format": "base64"
    }
    
    try:
        print("测试原始识别API...")
        response = requests.post(url, json=data)
        if response.status_code == 200:
            print("✅ 原始API也正常工作了!")
            return True
        else:
            print(f"❌ 原始API仍有问题: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ 原始API连接错误: {str(e)}")
        return False

if __name__ == "__main__":
    print("=== GoMuseum 演示API 测试 ===")
    
    # 先测试演示API健康检查
    print("\n1. 测试演示API健康检查...")
    health_ok = test_demo_health()
    
    # 测试演示识别API
    print("\n2. 测试演示识别API...")
    demo_ok = test_demo_recognition_api()
    
    # 测试原始API (看看是否修复了)
    print("\n3. 测试原始识别API...")
    original_ok = test_original_api()
    
    print(f"\n=== 测试总结 ===")
    print(f"演示API健康检查: {'✅ 通过' if health_ok else '❌ 失败'}")
    print(f"演示识别API: {'✅ 通过' if demo_ok else '❌ 失败'}")
    print(f"原始识别API: {'✅ 通过' if original_ok else '❌ 失败'}")
    
    if demo_ok:
        print(f"\n🎉 演示API正常工作! 可以用于Step 2的Flutter集成测试。")
        print(f"Flutter应该调用: http://localhost:8001/api/v1/recognition/demo")
    else:
        print(f"\n⚠️  演示API有问题，需要进一步调试。")