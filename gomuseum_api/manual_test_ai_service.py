#!/usr/bin/env python3
"""
AI服务手工测试脚本

用于验证智能模型选择器和AI适配器的功能
"""

import sys
import os
import asyncio
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from app.services.ai_service.model_selector import ModelSelector
from app.services.ai_service.openai_adapter_simple import OpenAIVisionAdapter
from app.services.ai_service.exceptions import ModelNotAvailableError


def print_section(title: str):
    """打印测试区段标题"""
    print("\n" + "="*60)
    print(f" {title}")
    print("="*60)


def create_test_adapters():
    """创建测试用的适配器"""
    print("🚀 创建测试适配器...")
    
    # 创建多个测试适配器（使用假的API密钥）
    adapters = [
        OpenAIVisionAdapter(
            api_key="test-key-1",
            model_name="gpt-4o-mini",
            temperature=0.3,
            max_tokens=500
        ),
        OpenAIVisionAdapter(
            api_key="test-key-2", 
            model_name="gpt-4-vision-preview",
            temperature=0.2,
            max_tokens=800
        ),
        OpenAIVisionAdapter(
            api_key="test-key-3",
            model_name="gpt-4o",
            temperature=0.4,
            max_tokens=600
        )
    ]
    
    print(f"✅ 创建了 {len(adapters)} 个测试适配器")
    return adapters


def test_model_selector_initialization(adapters):
    """测试模型选择器初始化"""
    print_section("测试 1: 模型选择器初始化")
    
    # 测试空初始化
    empty_selector = ModelSelector()
    print(f"空选择器适配器数量: {len(empty_selector._adapters)}")
    
    # 测试带适配器初始化
    selector = ModelSelector(adapters=adapters)
    print(f"选择器适配器数量: {len(selector._adapters)}")
    print(f"提供商: {list(selector._adapters.keys())}")
    
    # 显示所有可用模型
    models = selector.get_available_models()
    print(f"\n📋 可用模型列表:")
    for model in models:
        print(f"  - {model['model_name']} ({model['provider']})")
        print(f"    精度: {model['accuracy']:.2f}")
        print(f"    成本: ${model['pricing']['cost_per_call']:.3f}")
        print(f"    响应时间: {model['average_response_time']:.1f}s")
    
    return selector


def test_strategy_selection(selector):
    """测试不同策略的模型选择"""
    print_section("测试 2: 策略选择")
    
    strategies = ["cost", "accuracy", "speed", "balanced"]
    
    for strategy in strategies:
        try:
            adapter = selector.select_best_model(strategy=strategy)
            print(f"\n🎯 {strategy.upper()} 策略选择:")
            print(f"  选中模型: {adapter.model_name}")
            print(f"  提供商: {adapter.provider_name}")
            print(f"  精度: {adapter.get_accuracy_score():.2f}")
            print(f"  成本: ${adapter.estimate_cost(b'test'):.3f}")
            print(f"  响应时间: {adapter.get_average_response_time():.1f}s")
        except Exception as e:
            print(f"❌ {strategy} 策略失败: {e}")


def test_provider_selection(selector):
    """测试按提供商选择"""
    print_section("测试 3: 按提供商选择")
    
    providers = selector.get_available_providers()
    print(f"可用提供商: {providers}")
    
    for provider in providers:
        try:
            adapter = selector.select_best_model(
                provider=provider, 
                strategy="accuracy"
            )
            print(f"\n🏢 {provider.upper()} 最佳精度模型:")
            print(f"  模型: {adapter.model_name}")
            print(f"  精度: {adapter.get_accuracy_score():.2f}")
        except Exception as e:
            print(f"❌ {provider} 提供商选择失败: {e}")


def test_constraints(selector):
    """测试约束条件"""
    print_section("测试 4: 约束条件")
    
    # 测试成本约束
    try:
        adapter = selector.select_best_model(
            strategy="accuracy",
            max_cost=0.02
        )
        print(f"\n💰 成本约束 (≤$0.02):")
        print(f"  选中模型: {adapter.model_name}")
        print(f"  实际成本: ${adapter.estimate_cost(b'test'):.3f}")
        print(f"  精度: {adapter.get_accuracy_score():.2f}")
    except ModelNotAvailableError as e:
        print(f"❌ 成本约束测试失败: {e}")
    
    # 测试精度约束
    try:
        adapter = selector.select_best_model(
            strategy="cost",
            min_accuracy=0.85
        )
        print(f"\n🎯 精度约束 (≥0.85):")
        print(f"  选中模型: {adapter.model_name}")
        print(f"  实际精度: {adapter.get_accuracy_score():.2f}")
        print(f"  成本: ${adapter.estimate_cost(b'test'):.3f}")
    except ModelNotAvailableError as e:
        print(f"❌ 精度约束测试失败: {e}")


def test_model_ranking(selector):
    """测试模型排名"""
    print_section("测试 5: 模型排名")
    
    strategies = ["cost", "accuracy", "speed", "balanced"]
    
    for strategy in strategies:
        ranking = selector.get_model_ranking(strategy=strategy)
        print(f"\n📊 {strategy.upper()} 策略排名:")
        for i, model in enumerate(ranking[:3], 1):  # 只显示前3名
            print(f"  {i}. {model['model_name']}")
            print(f"     分数: {model['score']:.3f}")
            print(f"     精度: {model['accuracy']:.2f}")
            print(f"     成本: ${model['cost']:.3f}")


def test_stats_tracking(selector):
    """测试统计跟踪"""
    print_section("测试 6: 统计跟踪")
    
    # 模拟一些统计数据
    print("📈 模拟使用统计...")
    selector._update_model_stats("gpt-4o-mini", success=True, response_time=1.8)
    selector._update_model_stats("gpt-4o-mini", success=True, response_time=2.1)
    selector._update_model_stats("gpt-4o-mini", success=False, response_time=5.0)
    
    selector._update_model_stats("gpt-4-vision-preview", success=True, response_time=3.2)
    selector._update_model_stats("gpt-4-vision-preview", success=False, response_time=8.0)
    
    # 显示选择器信息
    info = selector.get_selector_info()
    print(f"\n📋 选择器信息:")
    print(f"  总模型数: {info['total_models']}")
    print(f"  提供商: {info['providers']}")
    print(f"  当前模型: {info['current_model']}")
    
    print(f"\n📊 模型统计:")
    for model_name, stats in info['model_stats'].items():
        if stats['total_requests'] > 0:
            print(f"  {model_name}:")
            print(f"    总请求: {stats['total_requests']}")
            print(f"    成功率: {stats['success_rate']:.1%}")
            print(f"    平均响应时间: {stats['average_response_time']:.1f}s")


async def test_adaptive_selection(selector):
    """测试自适应选择"""
    print_section("测试 7: 自适应选择")
    
    try:
        print("🧠 执行自适应选择...")
        adapter = await selector.select_adaptive_model()
        print(f"  选中模型: {adapter.model_name}")
        print(f"  基于历史性能的自适应分数计算")
    except Exception as e:
        print(f"❌ 自适应选择失败: {e}")


async def test_health_check(selector):
    """测试健康检查"""
    print_section("测试 8: 健康检查")
    
    print("🔍 检查模型健康状态...")
    
    # 获取所有适配器并检查健康状态
    for provider, adapters in selector._adapters.items():
        print(f"\n🏢 {provider.upper()} 提供商:")
        for adapter in adapters:
            try:
                is_healthy = await adapter.health_check()
                status = "✅ 健康" if is_healthy else "❌ 不健康"
                print(f"  {adapter.model_name}: {status}")
            except Exception as e:
                print(f"  {adapter.model_name}: ❌ 检查失败 ({e})")


def test_error_handling(selector):
    """测试错误处理"""
    print_section("测试 9: 错误处理")
    
    # 测试无效策略
    try:
        selector.select_best_model(strategy="invalid_strategy")
        print("❌ 应该抛出无效策略错误")
    except ValueError as e:
        print(f"✅ 正确捕获无效策略错误: {e}")
    
    # 测试无效提供商
    try:
        selector.select_best_model(provider="invalid_provider")
        print("❌ 应该抛出无效提供商错误")
    except ModelNotAvailableError as e:
        print(f"✅ 正确捕获无效提供商错误: {e}")
    
    # 测试空选择器
    empty_selector = ModelSelector()
    try:
        empty_selector.select_best_model()
        print("❌ 应该抛出无模型可用错误")
    except ModelNotAvailableError as e:
        print(f"✅ 正确捕获无模型可用错误: {e}")


async def test_artwork_recognition_simulation(selector):
    """模拟艺术品识别测试"""
    print_section("测试 10: 模拟艺术品识别")
    
    # 创建模拟图像数据
    fake_image_data = b"fake_image_data_for_testing" * 100  # 模拟图像字节
    
    print(f"📸 模拟图像数据大小: {len(fake_image_data)} 字节")
    
    # 选择最佳模型进行识别
    adapter = selector.select_best_model(strategy="balanced")
    print(f"🎯 选择模型: {adapter.model_name}")
    
    try:
        # 执行艺术品识别
        result = await adapter.recognize_artwork(
            image_bytes=fake_image_data,
            language="zh"
        )
        
        print(f"\n🎨 识别结果:")
        print(f"  成功: {result['success']}")
        print(f"  处理时间: {result['processing_time']:.2f}s")
        print(f"  使用模型: {result['model_used']}")
        print(f"  成本: ${result['cost_usd']:.4f}")
        
        if result['candidates']:
            candidate = result['candidates'][0]
            print(f"  识别结果:")
            print(f"    作品名称: {candidate['name']}")
            print(f"    艺术家: {candidate['artist']}")
            print(f"    置信度: {candidate['confidence']:.2f}")
        
    except Exception as e:
        print(f"❌ 艺术品识别失败: {e}")


async def main():
    """主测试函数"""
    print("🧪 AI服务手工测试开始")
    print("=" * 60)
    
    try:
        # 1. 创建测试适配器
        adapters = create_test_adapters()
        
        # 2. 测试模型选择器初始化
        selector = test_model_selector_initialization(adapters)
        
        # 3. 测试策略选择
        test_strategy_selection(selector)
        
        # 4. 测试按提供商选择
        test_provider_selection(selector)
        
        # 5. 测试约束条件
        test_constraints(selector)
        
        # 6. 测试模型排名
        test_model_ranking(selector)
        
        # 7. 测试统计跟踪
        test_stats_tracking(selector)
        
        # 8. 测试自适应选择
        await test_adaptive_selection(selector)
        
        # 9. 测试健康检查
        await test_health_check(selector)
        
        # 10. 测试错误处理
        test_error_handling(selector)
        
        # 11. 模拟艺术品识别
        await test_artwork_recognition_simulation(selector)
        
        print_section("测试完成")
        print("✅ 所有手工测试完成！")
        print("📋 测试涵盖了:")
        print("   - 模型选择器初始化和配置")
        print("   - 多种选择策略 (成本/精度/速度/平衡)")
        print("   - 提供商筛选")
        print("   - 约束条件 (成本/精度限制)")
        print("   - 模型排名")
        print("   - 统计跟踪")
        print("   - 自适应选择")
        print("   - 健康检查")
        print("   - 错误处理")
        print("   - 模拟艺术品识别")
        
    except Exception as e:
        print(f"❌ 测试过程中发生错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    print("🚀 启动AI服务手工测试...")
    print("请确保你在项目根目录下运行此脚本")
    print()
    
    # 运行异步测试
    asyncio.run(main())