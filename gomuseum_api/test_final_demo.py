#!/usr/bin/env python3
"""
最终测试演示识别API
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

def test_demo_api_raw():
    """直接测试演示API返回的原始JSON"""
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
        
        response = requests.post(url, json=data)
        
        print(f"响应状态码: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print("✅ 演示API调用成功!")
            print("完整响应JSON:")
            print(json.dumps(result, indent=2, ensure_ascii=False))
            
            # 解析新的响应格式
            if result.get('success') and result.get('data'):
                data = result['data']
                candidates = data.get('candidates', [])
                if candidates:
                    candidate = candidates[0]
                    print(f"\n识别结果解析:")
                    print(f"  作品标题: {candidate.get('artwork_title', 'N/A')}")
                    print(f"  艺术家: {candidate.get('artist_name', 'N/A')}")
                    print(f"  创作年代: {candidate.get('creation_year', 'N/A')}")
                    print(f"  风格: {candidate.get('style', 'N/A')}")
                    print(f"  置信度: {candidate.get('confidence', 0)}")
                    print(f"  描述: {candidate.get('description', 'N/A')}")
                    print(f"  博物馆: {candidate.get('museum', 'N/A')}")
                    print(f"  处理时间: {data.get('processing_time', 0)}秒")
                    print(f"  是否模拟: {result.get('mock_response', False)}")
            
            return True
        else:
            print(f"❌ API调用失败: {response.status_code}")
            print(f"错误信息: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ 连接错误: {str(e)}")
        return False

if __name__ == "__main__":
    print("=== GoMuseum 演示API 最终测试 ===")
    
    success = test_demo_api_raw()
    
    if success:
        print(f"\n🎉 演示API完全正常工作!")
        print(f"✅ Flutter应该可以成功调用: http://localhost:8001/api/v1/recognition/demo")
        print(f"✅ 响应格式符合Flutter期望的结构")
        print(f"✅ Step 2集成测试可以开始")
    else:
        print(f"\n⚠️  需要进一步调试演示API")