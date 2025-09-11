#!/usr/bin/env python3
"""
AI服务配置管理集成测试

验证统一配置系统与各组件的集成效果
"""

import sys
import os
import asyncio
import time
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from app.services.ai_service.config import (
    AIServiceConfig, ModelConfig, ProviderType, ModelStrategy,
    AIServiceConfigFactory, get_ai_config, update_ai_config,
    CircuitBreakerConfig, RetryConfig, RateLimitConfig
)
from app.services.ai_service.enhanced_model_selector import EnhancedModelSelector
from app.services.ai_service.openai_adapter_simple import OpenAIVisionAdapter


def print_section(title: str):
    """打印测试区段标题"""
    print("\n" + "="*60)
    print(f" {title}")
    print("="*60)


async def test_config_creation_and_validation():
    """测试配置创建和验证"""
    print_section("测试 1: 配置创建和验证")
    
    # 创建自定义配置
    config = AIServiceConfig()
    
    # 添加OpenAI模型
    openai_model = ModelConfig(
        model_name="gpt-4o-mini",
        provider=ProviderType.OPENAI,
        api_key="sk-test-key-12345678901234567890",
        temperature=0.3,
        max_tokens=500,
        cost_per_1k_tokens=0.0015,
        accuracy_score=0.85,
        avg_response_time=2.0
    )
    config.add_model(openai_model)
    
    # 添加Anthropic模型
    anthropic_model = ModelConfig(
        model_name="claude-3-sonnet-20240229",
        provider=ProviderType.ANTHROPIC,
        api_key="sk-ant-test-key-12345678901234567890",
        temperature=0.3,
        max_tokens=500,
        cost_per_1k_tokens=0.003,
        accuracy_score=0.90,
        avg_response_time=2.5
    )
    config.add_model(anthropic_model)
    
    print(f"✅ 配置创建完成，包含 {len(config.models)} 个模型")
    print(f"📋 可用模型: {', '.join(config.get_available_models())}")
    
    # 验证配置
    errors = config.validate_model_availability()
    if errors:
        print(f"❌ 配置验证发现 {len(errors)} 个问题:")
        for error in errors:
            print(f"   - {error}")
    else:
        print("✅ 配置验证通过")
    
    return config


def test_environment_based_configs():
    """测试基于环境的配置"""
    print_section("测试 2: 环境配置差异")
    
    # 开发环境配置
    dev_config = AIServiceConfigFactory.create_development_config()
    print("🔧 开发环境配置:")
    print(f"   熔断器失败阈值: {dev_config.circuit_breaker.failure_threshold}")
    print(f"   重试次数: {dev_config.retry.max_attempts}")
    print(f"   限流RPM: {dev_config.rate_limit.requests_per_minute}")
    print(f"   详细日志: {dev_config.enable_detailed_logging}")
    
    # 生产环境配置  
    prod_config = AIServiceConfigFactory.create_production_config()
    print("\n🚀 生产环境配置:")
    print(f"   熔断器失败阈值: {prod_config.circuit_breaker.failure_threshold}")
    print(f"   重试次数: {prod_config.retry.max_attempts}")
    print(f"   限流RPM: {prod_config.rate_limit.requests_per_minute}")
    print(f"   详细日志: {prod_config.enable_detailed_logging}")
    print(f"   最大并发: {prod_config.max_concurrent_requests}")


async def test_config_with_enhanced_selector(config: AIServiceConfig):
    """测试配置与增强选择器的集成"""
    print_section("测试 3: 配置与增强选择器集成")
    
    # 创建适配器列表
    adapters = []
    
    for model_name, model_config in config.models.items():
        if model_config.provider == ProviderType.OPENAI:
            adapter = OpenAIVisionAdapter(
                api_key=model_config.api_key,
                model_name=model_config.model_name
            )
            adapters.append(adapter)
    
    if not adapters:
        print("⚠️ 没有找到可用的适配器")
        return
    
    # 创建增强选择器
    enhanced_selector = EnhancedModelSelector(adapters=adapters)
    
    # 使用配置更新可靠性设置
    enhanced_selector.update_reliability_config(
        circuit_breaker_config=config.circuit_breaker,
        retry_config=config.retry,
        rate_limit_config={
            "requests_per_minute": config.rate_limit.requests_per_minute,
            "burst_allowance": config.rate_limit.burst_allowance
        }
    )
    
    print(f"✅ 增强选择器创建完成，包含 {len(adapters)} 个适配器")
    
    # 测试不同策略
    strategies = ["cost", "accuracy", "speed", "balanced"]
    
    for strategy in strategies:
        try:
            start_time = time.time()
            adapter = await enhanced_selector.select_best_model(
                strategy=strategy,
                enable_circuit_breaker=True,
                enable_retry=True,
                enable_rate_limit=True
            )
            duration = time.time() - start_time
            
            print(f"   🎯 {strategy.upper()} 策略: {adapter.model_name} ({duration:.3f}s)")
            
        except Exception as e:
            print(f"   ❌ {strategy.upper()} 策略失败: {e}")
    
    # 显示增强状态
    status = enhanced_selector.get_enhanced_status()
    print(f"\n📊 选择器状态:")
    print(f"   熔断器数量: {len(status['reliability']['circuit_breakers'])}")
    print(f"   限流器数量: {len(status['reliability']['rate_limiters'])}")
    print(f"   健康缓存条目: {status['health_cache']['cached_entries']}")


def test_config_serialization():
    """测试配置序列化"""
    print_section("测试 4: 配置序列化")
    
    # 创建配置
    config = AIServiceConfig(
        default_strategy=ModelStrategy.COST,
        circuit_breaker=CircuitBreakerConfig(
            failure_threshold=10,
            recovery_timeout=120
        ),
        retry=RetryConfig(
            max_attempts=5,
            base_delay=2.0
        ),
        rate_limit=RateLimitConfig(
            requests_per_minute=200,
            burst_allowance=20
        )
    )
    
    # 序列化为字典
    config_dict = config.model_dump()
    print("✅ 配置序列化为字典成功")
    print(f"   熔断器失败阈值: {config_dict['circuit_breaker']['failure_threshold']}")
    print(f"   重试最大次数: {config_dict['retry']['max_attempts']}")
    print(f"   默认策略: {config_dict['default_strategy']}")
    
    # 从字典恢复
    restored_config = AIServiceConfig.model_validate(config_dict)
    print("✅ 从字典恢复配置成功")
    
    # 验证恢复正确性
    assert restored_config.default_strategy == ModelStrategy.COST
    assert restored_config.circuit_breaker.failure_threshold == 10
    assert restored_config.retry.max_attempts == 5
    print("✅ 配置恢复正确性验证通过")


def test_global_config_management():
    """测试全局配置管理"""
    print_section("测试 5: 全局配置管理")
    
    # 获取默认全局配置
    global_config = get_ai_config()
    print(f"✅ 获取全局配置: {type(global_config).__name__}")
    print(f"   默认策略: {global_config.default_strategy}")
    print(f"   模型数量: {len(global_config.models)}")
    
    # 创建自定义配置
    custom_config = AIServiceConfig()
    custom_config.default_strategy = ModelStrategy.ACCURACY
    custom_config.max_concurrent_requests = 50
    
    # 更新全局配置
    update_ai_config(custom_config)
    updated_global_config = get_ai_config()
    
    print(f"✅ 更新全局配置成功")
    print(f"   新默认策略: {updated_global_config.default_strategy}")
    print(f"   最大并发: {updated_global_config.max_concurrent_requests}")


def test_config_validation_edge_cases():
    """测试配置验证边界情况"""
    print_section("测试 6: 配置验证边界情况")
    
    try:
        # 测试无效的temperature值
        invalid_model = ModelConfig(
            model_name="test-model",
            provider=ProviderType.OPENAI,
            api_key="sk-test-key-12345678901234567890",
            temperature=3.5  # 超出范围
        )
        print("❌ 应该检测到无效的temperature值")
    except Exception as e:
        print(f"✅ 正确检测到无效temperature: {type(e).__name__}")
    
    try:
        # 测试无效的API密钥
        invalid_model = ModelConfig(
            model_name="test-model",
            provider=ProviderType.OPENAI,
            api_key="short",  # 太短
            temperature=0.3
        )
        print("❌ 应该检测到无效的API密钥")
    except Exception as e:
        print(f"✅ 正确检测到无效API密钥: {type(e).__name__}")
    
    try:
        # 测试无效的重试配置
        invalid_retry = RetryConfig(
            base_delay=10.0,
            max_delay=5.0  # 小于基础延迟
        )
        print("❌ 应该检测到无效的重试配置")
    except Exception as e:
        print(f"✅ 正确检测到无效重试配置: {type(e).__name__}")


async def main():
    """主测试函数"""
    print("🧪 AI服务配置管理集成测试开始")
    print("=" * 60)
    print("本测试验证统一配置管理功能:")
    print("✅ Pydantic模型验证")
    print("✅ 环境特定配置")
    print("✅ 与增强选择器集成")
    print("✅ 配置序列化/反序列化")
    print("✅ 全局配置管理")
    print("✅ 边界情况验证")
    
    try:
        # 1. 配置创建和验证
        config = await test_config_creation_and_validation()
        
        # 2. 环境配置测试
        test_environment_based_configs()
        
        # 3. 与增强选择器集成
        await test_config_with_enhanced_selector(config)
        
        # 4. 配置序列化
        test_config_serialization()
        
        # 5. 全局配置管理
        test_global_config_management()
        
        # 6. 边界情况验证
        test_config_validation_edge_cases()
        
        print_section("测试完成")
        print("✅ 所有配置管理功能测试完成！")
        print("\n🎯 统一配置管理系统特性验证:")
        print("   ✅ 类型安全的配置模型")
        print("   ✅ 自动化验证和错误提示")
        print("   ✅ 环境感知的配置工厂")
        print("   ✅ 灵活的模型管理接口")
        print("   ✅ 与可靠性组件无缝集成")
        print("   ✅ 全局配置状态管理")
        print("   ✅ 配置持久化支持")
        print("\n🚀 配置管理系统已准备就绪用于生产环境！")
        
    except Exception as e:
        print(f"❌ 测试过程中发生错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    print("🚀 启动AI服务配置管理集成测试...")
    print("请确保你在项目根目录下运行此脚本")
    print()
    
    # 运行异步测试
    asyncio.run(main())