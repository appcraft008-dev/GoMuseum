#!/usr/bin/env python3
"""
测试识别API的脚本
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

def test_recognition_api():
    """测试识别API"""
    url = "http://localhost:8001/api/v1/recognition/recognize"
    
    # 创建测试图片
    base64_image = create_test_image()
    
    # 准备请求数据
    data = {
        "image": base64_image,
        "format": "base64"
    }
    
    try:
        print("正在测试识别API...")
        print(f"请求URL: {url}")
        print(f"图片大小: {len(base64_image)} 字符")
        
        response = requests.post(url, json=data)
        
        print(f"响应状态码: {response.status_code}")
        print(f"响应头: {dict(response.headers)}")
        
        if response.status_code == 200:
            result = response.json()
            print("✅ API调用成功!")
            print(f"响应数据: {json.dumps(result, indent=2, ensure_ascii=False)}")
        else:
            print(f"❌ API调用失败: {response.status_code}")
            print(f"错误信息: {response.text}")
            
    except Exception as e:
        print(f"❌ 连接错误: {str(e)}")

def test_health_check():
    """测试健康检查"""
    url = "http://localhost:8001/health"
    
    try:
        response = requests.get(url)
        if response.status_code == 200:
            print("✅ 健康检查通过")
            print(f"响应: {response.json()}")
        else:
            print(f"❌ 健康检查失败: {response.status_code}")
    except Exception as e:
        print(f"❌ 健康检查连接错误: {str(e)}")

if __name__ == "__main__":
    print("=== GoMuseum API 测试 ===")
    
    # 先测试健康检查
    print("\n1. 测试健康检查...")
    test_health_check()
    
    # 再测试识别API
    print("\n2. 测试识别API...")
    test_recognition_api()
    
    print("\n=== 测试完成 ===")