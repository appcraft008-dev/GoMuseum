#!/usr/bin/env python3
"""
测试OpenAI API调用
用于验证修复后的AI服务是否能正常工作
"""
import asyncio
import base64
import sys
from pathlib import Path

# 添加backend到路径
sys.path.insert(0, str(Path(__file__).parent / "backend"))

from app.services.ai_service import AIService


async def test_openai_api():
    """测试OpenAI API调用"""

    # 创建一个简单的测试图片（1x1 红色像素的PNG）
    # 这是一个合法的PNG文件的base64编码
    test_image_base64 = (
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8DwHwAFBQIAX8jx0gAAAABJRU5ErkJggg=="
    )

    print("=" * 80)
    print("OpenAI API 调用测试")
    print("=" * 80)

    ai_service = AIService()

    print(f"\n配置信息:")
    print(f"  - 模型: {ai_service.model}")
    print(f"  - API Key 已配置: {bool(ai_service.api_key)}")
    print(f"  - API Key 前缀: {ai_service.api_key[:15]}..." if ai_service.api_key else "  - API Key: 未配置")
    print(f"  - 策略超时: {ai_service.strategy_timeout}s")
    print(f"  - OpenAI超时: {ai_service.timeout}s")
    print(f"  - 总超时: {ai_service.total_timeout}s")

    print("\n开始调用OpenAI API...")
    print("注意: 这可能需要10-30秒，取决于网络和API响应速度\n")

    try:
        result = await ai_service.recognize(test_image_base64)

        print("\n" + "=" * 80)
        print("✅ 成功!")
        print("=" * 80)
        print(f"\n识别结果:")
        print(f"  - 艺术品名称: {result['artwork_name']}")
        print(f"  - 艺术家: {result['artist']}")
        print(f"  - 时期: {result['period']}")
        print(f"  - 描述: {result['description']}")
        print(f"  - 置信度: {result['confidence']}")
        print(f"  - 来源: {result['source']}")

    except Exception as e:
        print("\n" + "=" * 80)
        print("❌ 失败!")
        print("=" * 80)
        print(f"\n错误信息: {str(e)}")
        print(f"错误类型: {type(e).__name__}")
        import traceback
        print("\n完整堆栈跟踪:")
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_openai_api())
