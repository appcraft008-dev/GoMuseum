# 平台特定数据源架构

## 架构图

```
┌─────────────────────────────────────────────────────────────────┐
│                     RecognitionResultModel                       │
│                     (平台无关的数据模型)                         │
│  - fromJson() / toJson()                                         │
│  - 不包含任何平台特定代码                                        │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│              RecognitionLocalDataSource (接口)                   │
│  - getCachedResult()                                             │
│  - cacheResult()                                                 │
│  - deleteCacheByHash()                                           │
└─────────────────────────────────────────────────────────────────┘
                              ↓
                    ┌─────────┴─────────┐
                    ↓                   ↓
┌──────────────────────────┐  ┌──────────────────────────┐
│  原生平台 (iOS/macOS)    │  │      Web 平台            │
├──────────────────────────┤  ├──────────────────────────┤
│ RecognitionLocal         │  │ RecognitionLocal         │
│ DataSourceImpl           │  │ DataSourceImpl           │
│                          │  │                          │
│ + AppDatabase (Drift)    │  │ + Stub 实现              │
│ + dart:ffi ✓            │  │ + 无缓存功能             │
│ + SQLite 本地存储        │  │ + 可扩展为 LocalStorage  │
└──────────────────────────┘  └──────────────────────────┘
```

## 条件导入机制

```dart
// recognition_providers.dart

import 'recognition_local_datasource_impl.dart'      // 默认：原生平台
    if (dart.library.html)                           // 条件：如果是 Web
       'recognition_local_datasource_stub.dart';     // 使用：Web 桩实现

// 编译器自动选择：
// - iOS/macOS/Android: 使用 recognition_local_datasource_impl.dart
// - Web: 使用 recognition_local_datasource_stub.dart
```

## 扩展方法模式

```dart
// recognition_result_model.dart (平台无关)
class RecognitionResultModel {
  // 只有 fromJson / toJson
}

// recognition_result_model_drift_extensions.dart (仅原生平台)
extension RecognitionResultModelDriftExtensions on RecognitionResultModel {
  // Drift 特定方法
  RecognitionResultsCompanion toDrift(String imageHash) { ... }
}

// 使用时：
import 'recognition_result_model_drift_extensions.dart'; // 仅在原生平台导入
result.toDrift(hash); // 扩展方法
```

## 数据流

### 原生平台
```
用户操作
  ↓
Provider
  ↓
UseCase
  ↓
Repository
  ↓
RecognitionLocalDataSourceImpl (原生)
  ↓
AppDatabase (Drift)
  ↓
SQLite 文件
```

### Web 平台
```
用户操作
  ↓
Provider
  ↓
UseCase
  ↓
Repository
  ↓
RecognitionLocalDataSourceImpl (Web)
  ↓
返回 null (不缓存)
```

## 优势

### 1. 清晰的职责分离
- Domain 层：平台无关的业务逻辑
- Data 层：平台特定的实现细节
- Model：纯数据模型

### 2. 易于测试
- Model 可以在所有平台测试
- DataSource 可以 Mock
- 不同平台独立测试

### 3. 易于扩展
- Web 平台可以添加 LocalStorage 实现
- 其他平台可以添加不同的存储策略

### 4. 类型安全
- 接口定义了契约
- 编译器验证实现
- 条件导入在编译时解析

## 最佳实践

### ✅ DO
- 保持 Model 平台无关
- 使用接口定义契约
- 使用条件导入隔离平台代码
- 使用扩展方法添加平台特定功能

### ❌ DON'T
- 在 Model 中直接引用平台特定库
- 在接口中暴露平台特定类型
- 使用运行时平台检查（应使用条件导入）
- 混合平台特定代码和业务逻辑

## 文件组织

```
lib/features/recognition/data/
├── models/
│   ├── recognition_result_model.dart              # 平台无关
│   └── recognition_result_model_drift_extensions.dart  # 原生平台扩展
├── datasources/
│   ├── recognition_local_datasource.dart          # 接口定义
│   ├── recognition_local_datasource_impl.dart     # 原生实现
│   ├── recognition_local_datasource_stub.dart     # Web 实现
│   └── recognition_drift_database.dart            # Drift 配置
└── repositories/
    └── recognition_repository_impl.dart           # 平台无关
```

## 编译产物

### 原生平台 (macOS)
```
recognition_local_datasource_impl.dart  ← 编译
recognition_local_datasource_stub.dart  ← 忽略
```

### Web 平台
```
recognition_local_datasource_impl.dart  ← 忽略
recognition_local_datasource_stub.dart  ← 编译
```

## 总结

这个架构模式通过以下方式解决了跨平台兼容性问题：

1. **接口抽象**：定义统一的契约
2. **条件导入**：编译时选择实现
3. **扩展方法**：隔离平台特定功能
4. **相同类名**：保持 API 一致性

结果是一个清晰、可维护、类型安全的跨平台数据访问层。
