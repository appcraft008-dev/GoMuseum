#!/usr/bin/env python3
"""
API连接测试脚本
测试OpenAI和Claude API是否可用
"""

import asyncio
import sys
import base64
from pathlib import Path

# 测试图片(1x1像素的PNG,Base64编码)
TEST_IMAGE_BASE64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="


async def test_openai():
    """测试OpenAI API连接"""
    print("\n" + "="*60)
    print("🧪 测试 OpenAI GPT-4V 连接")
    print("="*60)

    try:
        from app.services.ai_service import AIService

        service = AIService()

        print(f"Model: {service.model}")
        print(f"API Key: {service.api_key[:20]}...")
        print("\n发送测试请求...")

        result = await service._recognize_with_openai(TEST_IMAGE_BASE64)

        print("\n✅ OpenAI API 连接成功!")
        print(f"识别结果:")
        print(f"  作品名称: {result.get('artwork_name', 'N/A')}")
        print(f"  艺术家: {result.get('artist', 'N/A')}")
        print(f"  时期: {result.get('period', 'N/A')}")
        print(f"  置信度: {result.get('confidence', 0):.2%}")

        return True

    except ImportError as e:
        print(f"\n❌ 缺少依赖包: {e}")
        print("请运行: pip install openai")
        return False

    except Exception as e:
        print(f"\n❌ OpenAI API 测试失败: {e}")
        print(f"错误类型: {type(e).__name__}")
        return False


async def test_claude():
    """测试Claude API连接"""
    print("\n" + "="*60)
    print("🧪 测试 Anthropic Claude Vision 连接")
    print("="*60)

    try:
        from app.services.ai_service import AIService
        from app.core.config import settings

        if not settings.ANTHROPIC_API_KEY:
            print("⚠️  Claude API Key未配置,跳过测试")
            return None

        service = AIService()

        print(f"Model: {getattr(settings, 'ANTHROPIC_MODEL', 'claude-3-5-sonnet-20241022')}")
        print(f"API Key: {settings.ANTHROPIC_API_KEY[:20]}...")
        print("\n发送测试请求...")

        result = await service._recognize_with_claude(TEST_IMAGE_BASE64)

        print("\n✅ Claude API 连接成功!")
        print(f"识别结果:")
        print(f"  作品名称: {result.get('artwork_name', 'N/A')}")
        print(f"  艺术家: {result.get('artist', 'N/A')}")
        print(f"  时期: {result.get('period', 'N/A')}")
        print(f"  置信度: {result.get('confidence', 0):.2%}")

        return True

    except ImportError as e:
        print(f"\n❌ 缺少依赖包: {e}")
        print("请运行: pip install anthropic")
        return False

    except Exception as e:
        print(f"\n❌ Claude API 测试失败: {e}")
        print(f"错误类型: {type(e).__name__}")
        return False


async def test_fallback_strategy():
    """测试完整的fallback策略"""
    print("\n" + "="*60)
    print("🧪 测试完整的AI识别流程(含Fallback)")
    print("="*60)

    try:
        from app.services.ai_service import AIService

        service = AIService()

        print("\n发送识别请求...")
        print("策略链: OpenAI GPT-4V → Claude Vision → Manual Fallback")

        result = await service.recognize(TEST_IMAGE_BASE64)

        print(f"\n✅ AI识别成功!")
        print(f"  使用策略: {result.get('source', 'unknown')}")
        print(f"  作品名称: {result.get('artwork_name', 'N/A')}")
        print(f"  艺术家: {result.get('artist', 'N/A')}")
        print(f"  时期: {result.get('period', 'N/A')}")
        print(f"  描述: {result.get('description', 'N/A')[:100]}...")
        print(f"  置信度: {result.get('confidence', 0):.2%}")

        return True

    except Exception as e:
        print(f"\n❌ AI识别测试失败: {e}")
        return False


async def main():
    """主测试流程"""
    print("\n" + "="*60)
    print("🚀 GoMuseum AI Service API连接测试")
    print("="*60)

    results = {}

    # 测试OpenAI
    results['openai'] = await test_openai()

    # 测试Claude
    await asyncio.sleep(1)  # 避免API速率限制
    results['claude'] = await test_claude()

    # 测试完整流程
    await asyncio.sleep(1)
    results['fallback'] = await test_fallback_strategy()

    # 总结
    print("\n" + "="*60)
    print("📊 测试结果总结")
    print("="*60)

    openai_status = "✅ 通过" if results['openai'] else "❌ 失败"
    claude_status = "✅ 通过" if results['claude'] else ("⚠️  跳过" if results['claude'] is None else "❌ 失败")
    fallback_status = "✅ 通过" if results['fallback'] else "❌ 失败"

    print(f"OpenAI GPT-4V:      {openai_status}")
    print(f"Claude Vision:       {claude_status}")
    print(f"Fallback策略:        {fallback_status}")

    # 判断整体状态
    if results['openai'] and results['fallback']:
        print("\n🎉 所有测试通过!AI识别功能已就绪!")
        return 0
    elif results['fallback']:
        print("\n⚠️  部分测试失败,但Fallback策略可用,系统可以运行")
        return 0
    else:
        print("\n❌ 测试失败,请检查API配置和网络连接")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
