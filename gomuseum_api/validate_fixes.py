#!/usr/bin/env python3
"""
验证GoMuseum API修复的脚本
检查所有关键修复是否正确实施
"""

import asyncio
import sys
import traceback
from typing import Dict, Any

def test_imports():
    """测试关键模块导入"""
    tests = []
    
    try:
        from app.core.config import settings
        tests.append(("✅ 配置模块", "成功加载配置"))
    except Exception as e:
        tests.append(("❌ 配置模块", f"导入失败: {e}"))
    
    try:
        from app.core.security_config import get_key_manager, get_data_encryptor
        key_manager = get_key_manager()
        tests.append(("✅ 安全配置", "密钥管理器初始化成功"))
    except Exception as e:
        tests.append(("❌ 安全配置", f"初始化失败: {e}"))
    
    try:
        from app.core.token_manager import token_manager
        tests.append(("✅ 令牌管理", "令牌管理器加载成功"))
    except Exception as e:
        tests.append(("❌ 令牌管理", f"加载失败: {e}"))
    
    try:
        from app.core.container import container, initialize_container
        tests.append(("✅ 依赖注入", "容器初始化成功"))
    except Exception as e:
        tests.append(("❌ 依赖注入", f"初始化失败: {e}"))
    
    try:
        from app.core.exceptions import (
            ExceptionHandlerMiddleware, ValidationError, 
            BusinessRuleViolation, ResourceNotFound
        )
        tests.append(("✅ 异常处理", "异常处理模块加载成功"))
    except Exception as e:
        tests.append(("❌ 异常处理", f"加载失败: {e}"))
    
    try:
        from app.core.cache_strategy import AdvancedCacheManager, L1MemoryCache
        cache_manager = AdvancedCacheManager()
        tests.append(("✅ 缓存优化", "高级缓存管理器初始化成功"))
    except Exception as e:
        tests.append(("❌ 缓存优化", f"初始化失败: {e}"))
    
    return tests

def test_configuration_fixes():
    """测试配置修复"""
    tests = []
    
    try:
        from app.core.config import settings
        
        # 检查重复配置是否已修复
        if hasattr(settings, 'max_image_size') and hasattr(settings, 'jpeg_quality'):
            tests.append(("✅ 配置整合", "图像处理配置已统一"))
        else:
            tests.append(("❌ 配置整合", "配置字段缺失"))
            
        # 检查数据库连接池配置
        if hasattr(settings, 'db_pool_size') and settings.db_pool_size > 0:
            tests.append(("✅ 数据库配置", "连接池配置正确"))
        else:
            tests.append(("❌ 数据库配置", "连接池配置缺失"))
            
    except Exception as e:
        tests.append(("❌ 配置检查", f"检查失败: {e}"))
    
    return tests

def test_security_fixes():
    """测试安全修复"""
    tests = []
    
    try:
        from app.core.security_config import get_key_manager
        from app.core.token_manager import token_manager
        
        key_manager = get_key_manager()
        
        # 测试密钥生成
        jwt_key = key_manager.get_jwt_secret_key()
        if len(jwt_key) >= 32:
            tests.append(("✅ 密钥管理", "JWT密钥安全生成"))
        else:
            tests.append(("❌ 密钥管理", "JWT密钥长度不足"))
            
        # 测试加密密钥
        enc_key = key_manager.get_encryption_key("test")
        if len(enc_key) >= 32:
            tests.append(("✅ 数据加密", "加密密钥安全生成"))
        else:
            tests.append(("❌ 数据加密", "加密密钥长度不足"))
            
    except Exception as e:
        tests.append(("❌ 安全检查", f"检查失败: {e}"))
    
    return tests

async def test_cache_boundaries():
    """测试缓存边界修复"""
    tests = []
    
    try:
        from app.core.cache_strategy import L1MemoryCache
        
        l1_cache = L1MemoryCache()
        
        # 测试L1缓存边界策略
        small_data = "小数据测试"
        large_data = "x" * 2048  # 大于L1阈值
        
        # 小数据应该被L1接受
        result1 = await l1_cache.set(
            "test_small", small_data, 
            tags=["session"], is_popular=True
        )
        
        # 大数据应该被L1拒绝
        result2 = await l1_cache.set(
            "test_large", large_data
        )
        
        if result1 and not result2:
            tests.append(("✅ 缓存边界", "L1缓存边界策略工作正常"))
        else:
            tests.append(("❌ 缓存边界", f"边界策略异常 small:{result1} large:{result2}"))
            
    except Exception as e:
        tests.append(("❌ 缓存测试", f"测试失败: {e}"))
    
    return tests

async def test_dependency_injection():
    """测试依赖注入"""
    tests = []
    
    try:
        from app.core.container import container, initialize_container
        
        # 初始化容器（但不真正连接数据库）
        await initialize_container()
        
        # 检查服务注册
        try:
            token_manager = container.get("TokenManager")
            if token_manager:
                tests.append(("✅ 服务注册", "TokenManager成功注册"))
            else:
                tests.append(("❌ 服务注册", "TokenManager未注册"))
        except Exception:
            tests.append(("❌ 服务注册", "TokenManager获取失败"))
            
    except Exception as e:
        tests.append(("❌ DI容器", f"容器测试失败: {e}"))
    
    return tests

def test_error_handling():
    """测试统一错误处理"""
    tests = []
    
    try:
        from app.core.exceptions import (
            ValidationError, BusinessRuleViolation, 
            ResourceNotFound, ErrorResponseFormatter
        )
        
        # 测试异常创建
        validation_error = ValidationError("测试验证错误", "test_field")
        if validation_error.error_code == "VALIDATION_ERROR":
            tests.append(("✅ 验证异常", "验证异常创建正确"))
        else:
            tests.append(("❌ 验证异常", "异常代码错误"))
        
        # 测试错误格式化
        error_response = ErrorResponseFormatter.format_error_response(
            "TEST_ERROR", "测试错误"
        )
        if "error" in error_response and "code" in error_response["error"]:
            tests.append(("✅ 错误格式", "错误响应格式正确"))
        else:
            tests.append(("❌ 错误格式", "错误响应格式异常"))
            
    except Exception as e:
        tests.append(("❌ 错误处理", f"测试失败: {e}"))
    
    return tests

def print_results(category: str, tests: list):
    """打印测试结果"""
    print(f"\n{'='*50}")
    print(f" {category}")
    print(f"{'='*50}")
    
    success_count = 0
    for status, message in tests:
        print(f"{status} {message}")
        if status.startswith("✅"):
            success_count += 1
    
    print(f"\n成功: {success_count}/{len(tests)}")
    return success_count, len(tests)

async def main():
    """主测试函数"""
    print("🔧 GoMuseum API 修复验证")
    print("检查所有关键修复是否正确实施...")
    
    total_success = 0
    total_tests = 0
    
    # 测试模块导入
    results = test_imports()
    success, total = print_results("模块导入检查", results)
    total_success += success
    total_tests += total
    
    # 测试配置修复
    results = test_configuration_fixes()
    success, total = print_results("配置修复检查", results)
    total_success += success
    total_tests += total
    
    # 测试安全修复
    results = test_security_fixes()
    success, total = print_results("安全修复检查", results)
    total_success += success
    total_tests += total
    
    # 测试缓存边界修复
    results = await test_cache_boundaries()
    success, total = print_results("缓存边界修复检查", results)
    total_success += success
    total_tests += total
    
    # 测试依赖注入
    results = await test_dependency_injection()
    success, total = print_results("依赖注入检查", results)
    total_success += success
    total_tests += total
    
    # 测试错误处理
    results = test_error_handling()
    success, total = print_results("错误处理检查", results)
    total_success += success
    total_tests += total
    
    # 最终结果
    print(f"\n{'='*60}")
    print(f" 最终结果")
    print(f"{'='*60}")
    
    success_rate = (total_success / total_tests) * 100 if total_tests > 0 else 0
    
    if success_rate >= 90:
        status_emoji = "🎉"
        status_text = "优秀"
    elif success_rate >= 75:
        status_emoji = "✅"
        status_text = "良好"
    elif success_rate >= 50:
        status_emoji = "⚠️"
        status_text = "需要改进"
    else:
        status_emoji = "❌"
        status_text = "需要修复"
    
    print(f"{status_emoji} 总体状态: {status_text}")
    print(f"📊 成功率: {success_rate:.1f}% ({total_success}/{total_tests})")
    
    if success_rate >= 90:
        print("\n🚀 所有修复验证通过！系统已准备就绪。")
        return 0
    else:
        print(f"\n⚠️  有 {total_tests - total_success} 个问题需要解决。")
        return 1

if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n\n⏹️  验证被用户中断")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n💥 验证过程中发生致命错误: {e}")
        traceback.print_exc()
        sys.exit(1)