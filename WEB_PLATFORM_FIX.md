# Web 平台兼容性修复文档

## 问题描述

Chrome 浏览器启动失败，出现 `dart:ffi` 不可用的错误：

```
Error: Dart library 'dart:ffi' is not available on this platform.
```

### 问题根源

`RecognitionResultModel` 直接导入了 `recognition_drift_database.dart`，该文件依赖 `dart:ffi`，而 `dart:ffi` 在 Web 平台不可用。

导入链：

```
recognition_result_model.dart
  → recognition_drift_database.dart
    → dart:ffi (Web 平台不支持)
```

## 解决方案

### 1. 移除模型中的平台特定依赖

**文件**: `/lib/features/recognition/data/models/recognition_result_model.dart`

**修改内容**:

- 移除了对 `recognition_drift_database.dart` 的导入
- 删除了 `toDrift()` 和 `fromDrift()` 方法
- 保留了平台无关的 `fromJson()` 和 `toJson()` 方法

**原因**: 数据模型应该是平台无关的，不应该依赖任何平台特定的类型。

### 2. 创建平台特定的转换器扩展

**新文件**: `/lib/features/recognition/data/models/recognition_result_model_drift_extensions.dart`

**内容**:

- 为 `RecognitionResultModel` 添加扩展方法 `toDrift()`
- 创建转换辅助类 `RecognitionResultModelDriftConverter`
- 实现 `fromDrift()` 静态方法

**优点**:

- 将 Drift 依赖隔离到扩展文件中
- 仅在原生平台导入此文件
- Web 平台完全不会编译这些代码

### 3. 重构本地数据源架构

#### 3.1 抽取接口定义

**文件**: `/lib/features/recognition/data/datasources/recognition_local_datasource.dart`

只保留接口定义，移除所有实现代码：

```dart
abstract class RecognitionLocalDataSource {
  Future<RecognitionResultModel?> getCachedResult(String imageHash);
  Future<void> cacheResult(String imageHash, RecognitionResultModel result);
  Future<void> deleteCacheByHash(String imageHash);
}
```

#### 3.2 创建原生平台实现

**新文件**: `/lib/features/recognition/data/datasources/recognition_local_datasource_impl.dart`

**特点**:

- 导入 Drift 数据库和转换器扩展
- 使用单例模式管理 AppDatabase
- 实现完整的本地缓存功能
- **仅在原生平台编译**

#### 3.3 更新 Web 平台桩实现

**文件**: `/lib/features/recognition/data/datasources/recognition_local_datasource_stub.dart`

**关键修改**:

- 类名改为 `RecognitionLocalDataSourceImpl`（与原生平台保持一致）
- 实现空方法，不进行任何缓存操作
- **仅在 Web 平台编译**

### 4. 使用条件导入

**文件**: `/lib/features/recognition/presentation/providers/recognition_providers.dart`

**条件导入语句**:

```dart
import '../../data/datasources/recognition_local_datasource_impl.dart'
    if (dart.library.html) '../../data/datasources/recognition_local_datasource_stub.dart';
```

**工作原理**:

- 在原生平台：导入 `recognition_local_datasource_impl.dart`
- 在 Web 平台：导入 `recognition_local_datasource_stub.dart`
- 两个文件都导出相同的类名 `RecognitionLocalDataSourceImpl`
- Provider 代码保持一致：`return RecognitionLocalDataSourceImpl();`

## 验证结果

### 1. Web 平台

```bash
flutter build web --release
```

**结果**: ✅ 构建成功

```
✓ Built build/web
```

### 2. macOS 平台

```bash
flutter build macos --debug
```

**结果**: ✅ 构建成功

```
✓ Built build/macos/Build/Products/Debug/gomuseum_app.app
```

### 3. 代码分析

```bash
flutter analyze
```

**结果**: ✅ 无严重错误（仅有测试文件中的未使用变量警告）

## 文件结构

```
lib/features/recognition/data/
├── models/
│   ├── recognition_result_model.dart              # 平台无关的数据模型
│   └── recognition_result_model_drift_extensions.dart  # Drift 转换器(仅原生平台)
└── datasources/
    ├── recognition_local_datasource.dart          # 接口定义
    ├── recognition_local_datasource_impl.dart     # 原生平台实现
    └── recognition_local_datasource_stub.dart     # Web 平台桩实现
```

## 技术要点

### 1. 条件导入 (Conditional Imports)

Dart 支持基于平台的条件导入：

```dart
import 'native_impl.dart' if (dart.library.html) 'web_impl.dart';
```

- `dart.library.html` 在 Web 平台存在
- 在原生平台不存在，使用默认导入

### 2. 相同类名策略

两个平台实现必须使用相同的类名，这样：

- Provider 代码不需要平台判断
- 编译器自动选择正确的实现
- 类型系统保持一致

### 3. 扩展方法隔离

使用扩展方法将平台特定功能隔离：

```dart
extension RecognitionResultModelDriftExtensions on RecognitionResultModel {
  RecognitionResultsCompanion toDrift(String imageHash) { ... }
}
```

好处：

- 模型类保持纯净
- 扩展文件可以有平台依赖
- 只在需要时导入

## 最佳实践

### 1. 分层架构

```
Entity (Domain) ← 平台无关
  ↓
Model (Data)    ← 平台无关
  ↓
Extensions      ← 平台特定（可选导入）
  ↓
DataSource      ← 平台特定实现
```

### 2. 依赖方向

- Domain 层不依赖任何平台
- Data 层模型不依赖数据库
- 转换逻辑使用扩展或辅助类
- DataSource 实现可以有平台依赖

### 3. 测试策略

- 模型类可以在所有平台测试
- DataSource 需要平台特定测试
- 使用 Mock 隔离平台依赖

## 遇到的问题及解决

### 问题 1: 条件导入语法错误

**错误**: `Method not found: 'RecognitionLocalDataSourceImpl'`

**原因**: Web 平台的桩实现类名为 `RecognitionLocalDataSourceStub`

**解决**: 将桩实现的类名改为 `RecognitionLocalDataSourceImpl`

### 问题 2: 单例创建差异

**问题**: 原生平台需要 AppDatabase 实例，Web 平台不需要

**解决**:

- 原生平台：使用工厂构造函数 + 单例模式
- Web 平台：使用私有构造函数 + 工厂方法
- 两者都支持无参构造 `RecognitionLocalDataSourceImpl()`

## 后续优化建议

### 1. 添加 Web 平台缓存

可以为 Web 平台实现基于 LocalStorage 或 IndexedDB 的缓存：

```dart
// recognition_local_datasource_stub.dart
import 'dart:html' as html;

class RecognitionLocalDataSourceImpl implements RecognitionLocalDataSource {
  @override
  Future<RecognitionResultModel?> getCachedResult(String imageHash) async {
    final json = html.window.localStorage[imageHash];
    if (json != null) {
      return RecognitionResultModel.fromJson(jsonDecode(json));
    }
    return null;
  }
  // ...
}
```

### 2. 统一测试

创建平台无关的测试用例：

```dart
// recognition_local_datasource_contract_test.dart
void runLocalDataSourceTests(RecognitionLocalDataSource dataSource) {
  test('should cache and retrieve result', () async {
    // 测试逻辑
  });
}

// 在不同平台运行相同测试
```

### 3. 性能监控

添加平台特定的性能指标：

- 原生平台：监控 Drift 查询时间
- Web 平台：监控 LocalStorage 访问时间

## 总结

通过以下策略成功解决了 Web 平台兼容性问题：

1. ✅ 保持数据模型平台无关
2. ✅ 使用扩展方法隔离平台特定代码
3. ✅ 条件导入实现平台特定实现
4. ✅ 统一接口，不同实现
5. ✅ 验证所有平台都能成功编译

**修复时间**: 2025-10-05

**影响范围**: Recognition 功能模块的本地缓存层

**测试平台**: Web (Chrome), macOS
