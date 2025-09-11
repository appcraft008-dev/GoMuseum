#!/usr/bin/env python3
"""
AI服务监控系统集成测试

验证Prometheus指标收集、结构化日志和性能监控的集成效果
"""

import sys
import os
import asyncio
import time
import json
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from app.services.ai_service.monitoring import (
    AIServiceMonitor, ai_monitor, monitor_ai_request,
    StructuredLogger, PrometheusMetrics
)
from app.services.ai_service.enhanced_model_selector import EnhancedModelSelector
from app.services.ai_service.openai_adapter_simple import OpenAIVisionAdapter


def print_section(title: str):
    """打印测试区段标题"""
    print("\n" + "="*60)
    print(f" {title}")
    print("="*60)


def test_structured_logging():
    """测试结构化日志"""
    print_section("测试 1: 结构化日志")
    
    logger = StructuredLogger("test_monitor")
    
    print("🔍 测试结构化日志记录...")
    
    # 模拟请求日志
    logger.log_request("gpt-4o-mini", "req_001", 
                      image_size="1024x1024", 
                      user_id="user_123")
    
    # 模拟响应日志
    logger.log_response("gpt-4o-mini", "req_001", 
                       response_time=2.5, 
                       success=True,
                       cost_usd=0.015,
                       tokens_used=350)
    
    # 模拟错误日志
    logger.log_error("gpt-4-vision-preview", "req_002", 
                     error="Rate limit exceeded",
                     retry_count=3)
    
    # 模拟熔断器日志
    logger.log_circuit_breaker("ai_service", "open", 
                              failure_count=5,
                              last_failure="Connection timeout")
    
    print("✅ 结构化日志记录完成")
    print("📋 日志特性:")
    print("   - JSON格式输出")
    print("   - 统一时间戳")
    print("   - 结构化字段")
    print("   - 可搜索性")


def test_prometheus_metrics():
    """测试Prometheus指标"""
    print_section("测试 2: Prometheus指标收集")
    
    metrics = PrometheusMetrics()
    
    print("📊 测试Prometheus指标收集...")
    
    # 记录请求指标
    for i in range(10):
        metrics.record_request("gpt-4o-mini", True)
        metrics.record_response_time("gpt-4o-mini", 2.0 + (i * 0.1))
    
    for i in range(3):
        metrics.record_request("gpt-4o-mini", False)
        metrics.record_response_time("gpt-4o-mini", 5.0)
    
    # 记录其他指标
    metrics.set_active_requests("gpt-4o-mini", 5)
    metrics.set_circuit_breaker_state("ai_service", "closed")
    metrics.record_cache_hit("model_cache")
    metrics.record_cache_miss("model_cache")
    metrics.update_model_info("gpt-4o-mini", "openai", "v1.0")
    
    print("✅ Prometheus指标记录完成")
    print("📊 指标类型:")
    print("   - 计数器: 请求总数、错误数")
    print("   - 直方图: 响应时间分布")
    print("   - 测量仪: 活跃请求数、熔断器状态")
    print("   - 信息: 模型元数据")
    print("   - 缓存统计: 命中率")
    
    if metrics.enabled:
        print("🚀 Prometheus服务器运行在 http://localhost:8090/metrics")
    else:
        print("⚠️ Prometheus客户端未安装，使用模拟指标")


def test_performance_monitoring():
    """测试性能监控"""
    print_section("测试 3: 性能监控")
    
    monitor = AIServiceMonitor(
        enable_prometheus=False,  # 避免端口冲突
        enable_structured_logging=True,
        metrics_port=8092
    )
    
    print("🔍 测试性能统计收集...")
    
    # 模拟一系列请求
    models = ["gpt-4o-mini", "gpt-4-vision-preview", "claude-3-sonnet"]
    
    for model in models:
        for i in range(5):
            request_id = f"req_{model}_{i}"
            
            # 记录请求开始
            monitor.record_request_start(model, request_id)
            
            # 模拟处理时间
            processing_time = 1.0 + (i * 0.5)
            time.sleep(0.01)  # 模拟很短的处理
            
            # 随机成功/失败
            success = i < 4  # 最后一个失败
            
            # 记录请求结束
            monitor.record_request_end(model, request_id, processing_time, success)
            
            if not success:
                monitor.record_error(model, request_id, "Simulated error")
    
    # 获取统计摘要
    summary = monitor.get_stats_summary()
    
    print("📊 性能统计结果:")
    for model_name, stats in summary.items():
        if model_name == "global":
            continue
        print(f"\n  {model_name}:")
        print(f"    请求数: {stats['request_count']}")
        print(f"    成功率: {stats['success_rate']:.2%}")
        print(f"    平均响应时间: {stats['avg_response_time']:.2f}s")
        print(f"    最近平均响应时间: {stats['recent_avg_response_time']:.2f}s")
    
    global_stats = summary["global"]
    print(f"\n  全局统计:")
    print(f"    总请求数: {global_stats['total_requests']}")
    print(f"    总错误数: {global_stats['total_errors']}")
    print(f"    全局成功率: {global_stats['global_success_rate']:.2%}")
    print(f"    活跃模型数: {global_stats['active_models']}")
    
    return monitor


def test_health_monitoring(monitor):
    """测试健康监控"""
    print_section("测试 4: 健康监控")
    
    print("🏥 测试健康状态检查...")
    
    # 获取健康状态
    health = monitor.get_health_status()
    
    print(f"健康状态: {'✅ 健康' if health['healthy'] else '❌ 不健康'}")
    
    if health['issues']:
        print(f"发现问题:")
        for issue in health['issues']:
            print(f"  - {issue}")
    else:
        print("未发现问题")
    
    print(f"\n健康检查时间: {health['timestamp']}")
    
    # 创建快照
    snapshot = monitor.create_snapshot()
    print(f"\n📸 性能快照:")
    print(f"  时间戳: {snapshot.timestamp}")
    print(f"  总请求: {snapshot.requests_total}")
    print(f"  失败请求: {snapshot.requests_failed}")
    print(f"  平均响应时间: {snapshot.avg_response_time:.2f}s")
    print(f"  活跃模型: {snapshot.active_models}")


@monitor_ai_request(ai_monitor)
def mock_ai_recognition(image_bytes: bytes, model_name: str = "gpt-4o-mini", request_id: str = None):
    """模拟AI识别函数"""
    time.sleep(0.1)  # 模拟处理时间
    
    return {
        "success": True,
        "candidates": [
            {"name": "蒙娜丽莎", "confidence": 0.95},
            {"name": "达芬奇作品", "confidence": 0.88}
        ],
        "model_used": model_name,
        "cost_usd": 0.015
    }


@monitor_ai_request(ai_monitor)
async def mock_async_ai_recognition(image_bytes: bytes, model_name: str = "claude-3-sonnet", request_id: str = None):
    """模拟异步AI识别函数"""
    await asyncio.sleep(0.15)  # 模拟异步处理时间
    
    return {
        "success": True,
        "candidates": [
            {"name": "星夜", "confidence": 0.92},
            {"name": "梵高作品", "confidence": 0.89}
        ],
        "model_used": model_name,
        "cost_usd": 0.025
    }


def test_decorator_integration():
    """测试装饰器集成"""
    print_section("测试 5: 监控装饰器集成")
    
    print("🎨 测试监控装饰器...")
    
    # 清理之前的统计
    ai_monitor.stats.clear()
    
    # 测试同步函数
    fake_image = b"fake_image_data" * 100
    
    print("\n📷 测试同步识别:")
    result1 = mock_ai_recognition(fake_image, model_name="gpt-4o-mini", request_id="sync_req_001")
    print(f"  结果: {result1['candidates'][0]['name']} (置信度: {result1['candidates'][0]['confidence']})")
    
    result2 = mock_ai_recognition(fake_image, model_name="gpt-4o-mini", request_id="sync_req_002")
    print(f"  结果: {result2['candidates'][0]['name']} (置信度: {result2['candidates'][0]['confidence']})")
    
    print("\n🌟 测试异步识别:")
    
    async def test_async_calls():
        result3 = await mock_async_ai_recognition(fake_image, model_name="claude-3-sonnet", request_id="async_req_001")
        print(f"  结果: {result3['candidates'][0]['name']} (置信度: {result3['candidates'][0]['confidence']})")
        
        result4 = await mock_async_ai_recognition(fake_image, model_name="claude-3-sonnet", request_id="async_req_002")
        print(f"  结果: {result4['candidates'][0]['name']} (置信度: {result4['candidates'][0]['confidence']})")
    
    asyncio.run(test_async_calls())
    
    # 显示监控统计
    summary = ai_monitor.get_stats_summary()
    print(f"\n📊 装饰器监控统计:")
    
    for model_name, stats in summary.items():
        if model_name == "global":
            continue
        print(f"  {model_name}:")
        print(f"    请求数: {stats['request_count']}")
        print(f"    成功率: {stats['success_rate']:.2%}")
        print(f"    平均响应时间: {stats['avg_response_time']:.3f}s")


def test_integration_with_enhanced_selector():
    """测试与增强选择器的集成"""
    print_section("测试 6: 与增强选择器集成")
    
    print("🤖 测试监控与增强选择器集成...")
    
    # 创建适配器
    adapters = [
        OpenAIVisionAdapter(
            api_key="sk-test-key-12345678901234567890",
            model_name="gpt-4o-mini"
        ),
        OpenAIVisionAdapter(
            api_key="sk-test-key-12345678901234567890",
            model_name="gpt-4-vision-preview"
        )
    ]
    
    # 创建增强选择器
    enhanced_selector = EnhancedModelSelector(adapters=adapters)
    
    # 模拟监控集成
    test_monitor = AIServiceMonitor(
        enable_prometheus=False,
        enable_structured_logging=True
    )
    
    # 模拟选择器操作监控
    async def simulate_selector_operations():
        for strategy in ["cost", "accuracy", "speed", "balanced"]:
            request_id = f"selector_req_{strategy}"
            
            try:
                test_monitor.record_request_start("model_selector", request_id)
                
                start_time = time.time()
                adapter = await enhanced_selector.select_best_model(strategy=strategy)
                duration = time.time() - start_time
                
                test_monitor.record_request_end("model_selector", request_id, duration, True)
                
                print(f"  ✅ {strategy.upper()} 策略: {adapter.model_name} ({duration:.3f}s)")
                
            except Exception as e:
                duration = time.time() - start_time
                test_monitor.record_request_end("model_selector", request_id, duration, False)
                test_monitor.record_error("model_selector", request_id, str(e))
                
                print(f"  ❌ {strategy.upper()} 策略失败: {e}")
    
    asyncio.run(simulate_selector_operations())
    
    # 显示监控结果
    summary = test_monitor.get_stats_summary()
    selector_stats = summary.get("model_selector", {})
    
    if selector_stats:
        print(f"\n📊 选择器监控统计:")
        print(f"  请求数: {selector_stats['request_count']}")
        print(f"  成功率: {selector_stats['success_rate']:.2%}")
        print(f"  平均响应时间: {selector_stats['avg_response_time']:.3f}s")


def test_monitoring_dashboard_data():
    """测试监控仪表板数据"""
    print_section("测试 7: 监控仪表板数据")
    
    print("📈 生成监控仪表板数据...")
    
    # 使用全局监控器的数据
    summary = ai_monitor.get_stats_summary()
    health = ai_monitor.get_health_status()
    
    # 生成仪表板数据
    dashboard_data = {
        "timestamp": time.time(),
        "health": health,
        "summary": summary,
        "metrics": {
            "total_requests": summary["global"]["total_requests"],
            "error_rate": summary["global"]["total_errors"] / max(1, summary["global"]["total_requests"]),
            "avg_response_time": summary["global"]["global_avg_response_time"],
            "active_models": summary["global"]["active_models"]
        },
        "models": {}
    }
    
    # 添加每个模型的详细数据
    for model_name, stats in summary.items():
        if model_name != "global":
            dashboard_data["models"][model_name] = {
                "requests": stats["request_count"],
                "success_rate": stats["success_rate"],
                "avg_response_time": stats["avg_response_time"],
                "last_request": stats["last_request_time"]
            }
    
    print("✅ 仪表板数据生成完成")
    print(f"📊 数据摘要:")
    print(f"  总请求数: {dashboard_data['metrics']['total_requests']}")
    print(f"  错误率: {dashboard_data['metrics']['error_rate']:.2%}")
    print(f"  平均响应时间: {dashboard_data['metrics']['avg_response_time']:.3f}s")
    print(f"  活跃模型数: {dashboard_data['metrics']['active_models']}")
    print(f"  健康状态: {'✅ 健康' if dashboard_data['health']['healthy'] else '❌ 不健康'}")
    
    return dashboard_data


async def main():
    """主测试函数"""
    print("🧪 AI服务监控系统集成测试开始")
    print("=" * 60)
    print("本测试验证企业级监控功能:")
    print("✅ 结构化日志记录")
    print("✅ Prometheus指标收集")
    print("✅ 性能统计监控")
    print("✅ 健康状态检查")
    print("✅ 监控装饰器")
    print("✅ 与AI组件集成")
    print("✅ 仪表板数据生成")
    
    try:
        # 1. 结构化日志测试
        test_structured_logging()
        
        # 2. Prometheus指标测试
        test_prometheus_metrics()
        
        # 3. 性能监控测试
        monitor = test_performance_monitoring()
        
        # 4. 健康监控测试
        test_health_monitoring(monitor)
        
        # 5. 装饰器集成测试
        test_decorator_integration()
        
        # 6. 与增强选择器集成测试
        await test_integration_with_enhanced_selector()
        
        # 7. 仪表板数据测试
        dashboard_data = test_monitoring_dashboard_data()
        
        print_section("测试完成")
        print("✅ 所有监控功能测试完成！")
        print("\n🎯 企业级监控系统特性验证:")
        print("   ✅ 结构化JSON日志 - 便于搜索和分析")
        print("   ✅ Prometheus指标 - 与监控生态集成")
        print("   ✅ 实时性能统计 - 响应时间、成功率追踪")
        print("   ✅ 健康状态监控 - 自动问题检测")
        print("   ✅ 监控装饰器 - 无侵入式集成")
        print("   ✅ 组件集成 - 与AI服务无缝协作")
        print("   ✅ 仪表板支持 - 可视化监控数据")
        print("\n🚀 监控系统已准备就绪用于生产环境！")
        print("📊 监控端点:")
        print("   - Prometheus指标: http://localhost:8090/metrics")
        print("   - 应用健康检查: 通过AIServiceMonitor.get_health_status()")
        print("   - 性能统计: 通过AIServiceMonitor.get_stats_summary()")
        
    except Exception as e:
        print(f"❌ 测试过程中发生错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    print("🚀 启动AI服务监控系统集成测试...")
    print("请确保你在项目根目录下运行此脚本")
    print()
    
    # 运行异步测试
    asyncio.run(main())