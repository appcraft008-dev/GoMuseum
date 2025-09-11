# AI服务手工测试指南

## 📋 测试概述

本指南帮助你手工验证GoMuseum项目的AI服务功能，包括智能模型选择器和AI适配器的各项功能。

## 🚀 快速开始

### 1. 运行自动化手工测试

```bash
cd /Users/hongyang/Projects/GoMuseum/gomuseum_api
python3 manual_test_ai_service.py
```

这个脚本会自动执行10个测试场景，验证所有核心功能。

### 2. 测试结果验证

确保看到以下成功指标：
- ✅ 所有策略选择正常工作
- ✅ 模型排名按预期排序
- ✅ 约束条件正确生效
- ✅ 错误处理正确捕获异常
- ✅ 健康检查状态正常

## 🧪 详细测试场景

### 测试1: 模型选择器初始化
**目的**: 验证模型选择器能正确初始化和管理适配器

**预期结果**:
```
空选择器适配器数量: 0
选择器适配器数量: 1  
提供商: ['openai']
```

**验证要点**:
- 可用模型列表显示3个模型
- 每个模型都有精度、成本、响应时间信息

### 测试2: 策略选择
**目的**: 验证4种选择策略正确工作

**预期结果**:
- COST策略 → 选择 gpt-4o-mini (最便宜)
- ACCURACY策略 → 选择 gpt-4-vision-preview (最高精度)
- SPEED策略 → 选择 gpt-4o-mini (最快响应)
- BALANCED策略 → 选择综合分数最高的模型

### 测试3: 按提供商选择
**目的**: 验证能按指定提供商筛选模型

**预期结果**:
```
可用提供商: ['openai']
OPENAI 最佳精度模型: gpt-4-vision-preview
```

### 测试4: 约束条件
**目的**: 验证成本和精度约束正确生效

**预期结果**:
- 成本约束 ≤$0.02 → 选择符合条件的模型
- 精度约束 ≥0.85 → 选择高精度模型

### 测试5: 模型排名
**目的**: 验证各策略下的模型排名正确

**验证要点**:
- COST排名：按成本效益降序
- ACCURACY排名：按精度降序
- SPEED排名：按响应速度排序
- BALANCED排名：按综合分数降序

### 测试6: 统计跟踪
**目的**: 验证模型使用统计正确记录

**预期结果**:
```
模型统计:
  gpt-4o-mini:
    总请求: 3
    成功率: 66.7%
    平均响应时间: 3.0s
```

### 测试7: 自适应选择
**目的**: 验证基于历史性能的智能选择

**预期结果**: 
- 成功执行自适应选择
- 基于统计数据选择最优模型

### 测试8: 健康检查
**目的**: 验证模型健康状态检查

**预期结果**:
```
OPENAI 提供商:
  gpt-4o-mini: ✅ 健康
  gpt-4-vision-preview: ✅ 健康
  gpt-4o: ✅ 健康
```

### 测试9: 错误处理
**目的**: 验证各种错误情况正确处理

**预期结果**:
- ✅ 正确捕获无效策略错误
- ✅ 正确捕获无效提供商错误
- ✅ 正确捕获无模型可用错误

### 测试10: 模拟艺术品识别
**目的**: 验证端到端的艺术品识别流程

**预期结果**:
```
识别结果:
  成功: False (因为是模拟数据)
  处理时间: 0.00s
  使用模型: gpt-4o-mini
  成本: $0.0000
```

## 🔧 手动测试步骤

如果你想进行更深入的手动测试，可以按以下步骤：

### 1. 创建测试环境

```python
from app.services.ai_service.model_selector import ModelSelector
from app.services.ai_service.openai_adapter_simple import OpenAIVisionAdapter

# 创建适配器
adapter = OpenAIVisionAdapter(api_key="test-key", model_name="gpt-4o-mini")

# 创建选择器
selector = ModelSelector(adapters=[adapter])
```

### 2. 测试基本功能

```python
# 获取可用模型
models = selector.get_available_models()
print("可用模型:", [m['model_name'] for m in models])

# 测试策略选择
cost_model = selector.select_best_model(strategy="cost")
print("成本优先:", cost_model.model_name)

accuracy_model = selector.select_best_model(strategy="accuracy")
print("精度优先:", accuracy_model.model_name)
```

### 3. 测试约束条件

```python
# 成本约束
try:
    model = selector.select_best_model(strategy="accuracy", max_cost=0.02)
    print("成本约束成功:", model.model_name)
except Exception as e:
    print("成本约束失败:", e)

# 精度约束
try:
    model = selector.select_best_model(strategy="cost", min_accuracy=0.85)
    print("精度约束成功:", model.model_name)
except Exception as e:
    print("精度约束失败:", e)
```

### 4. 测试统计功能

```python
# 更新统计
selector._update_model_stats("gpt-4o-mini", success=True, response_time=2.5)
selector._update_model_stats("gpt-4o-mini", success=False, response_time=5.0)

# 查看统计
info = selector.get_selector_info()
print("统计信息:", info['model_stats'])
```

## 🐛 常见问题排查

### 问题1: 模块导入错误
**症状**: `ModuleNotFoundError: No module named 'app'`
**解决**: 确保在项目根目录运行测试脚本

### 问题2: 测试失败
**症状**: 某些测试断言失败
**解决**: 
1. 检查是否修改了模型配置
2. 确认测试数据是否正确
3. 查看错误日志定位问题

### 问题3: 异步测试问题
**症状**: `RuntimeError: This event loop is already running`
**解决**: 确保在正确的异步上下文中运行测试

## 📊 性能基准

正常情况下的预期性能指标：

| 测试项目 | 预期时间 | 说明 |
|---------|---------|------|
| 模型选择器初始化 | < 100ms | 快速初始化 |
| 策略选择 | < 50ms | 策略算法高效 |
| 约束条件筛选 | < 30ms | 过滤算法优化 |
| 模型排名计算 | < 100ms | 排序算法稳定 |
| 健康检查 | < 500ms | 模拟检查快速 |

## ✅ 验收标准

手工测试通过的标准：

1. **功能完整性**: 所有10个测试场景都成功执行
2. **错误处理**: 异常情况得到正确处理
3. **性能表现**: 响应时间在预期范围内
4. **数据准确性**: 选择结果符合策略逻辑
5. **日志完整**: 关键操作有清晰的日志输出

## 🔄 持续测试

建议定期运行手工测试：

1. **开发期间**: 每次代码修改后运行
2. **集成测试**: 合并代码前验证
3. **部署前**: 生产环境部署前最终确认
4. **监控验证**: 生产环境定期健康检查

## 📞 获取帮助

如果在测试过程中遇到问题：

1. 检查本指南的常见问题部分
2. 查看代码注释和文档
3. 运行单元测试确认基础功能
4. 查看应用日志获取详细错误信息

---

**测试完成后，你应该对AI服务的以下功能有信心**：
- ✅ 智能模型选择策略
- ✅ 多提供商支持架构  
- ✅ 约束条件和过滤机制
- ✅ 统计跟踪和性能监控
- ✅ 错误处理和异常恢复
- ✅ 健康检查和故障转移