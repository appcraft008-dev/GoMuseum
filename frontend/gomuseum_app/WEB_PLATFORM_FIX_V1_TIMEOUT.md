# Web 平台图片识别修复摘要

## 问题描述

Chrome 浏览器中的图片识别功能失败，原因：

1. Web 平台不支持 `dart:io File.exists()` 操作
2. 超时时间太短（5-10秒），无法等待 OpenAI API 响应（需要 20-30 秒）

## 修复内容

### 1. 移除 Web 不兼容的文件操作

**文件**: `lib/features/recognition/domain/usecases/recognize_artwork.dart`

**修改前**:

```dart
Future<Failure?> _validateImage(File imageFile) async {
  // 检查文件是否存在
  if (!await imageFile.exists()) {
    return const ValidationFailure('Image file does not exist');
  }

  // 检查文件大小(<10MB)
  final fileSize = await imageFile.length();
  // ...
}
```

**修改后**:

```dart
Future<Failure?> _validateImage(File imageFile) async {
  try {
    // 读取文件字节（Web 平台跳过 exists() 检查）
    final bytes = await imageFile.readAsBytes();
    if (bytes.isEmpty) {
      return const ValidationFailure('Image file is empty');
    }

    // 检查文件大小(<10MB)
    if (bytes.length > 10 * 1024 * 1024) {
      return const ValidationFailure('Image size exceeds 10MB limit');
    }
    // ...
  } catch (e) {
    return ValidationFailure('Failed to read image file: $e');
  }
}
```

**优化点**:

- ✅ 移除 `imageFile.exists()` 调用（Web 平台不支持）
- ✅ 直接读取字节进行验证
- ✅ 添加 try-catch 错误处理
- ✅ 使用 bytes.length 替代 fileSize

### 2. 增加超时时间到 60 秒

#### 2.1 Dio 客户端超时配置

**文件**: `lib/features/recognition/presentation/providers/recognition_providers.dart`

**修改**:

```dart
@riverpod
Dio dio(DioRef ref) {
  return Dio(BaseOptions(
    baseUrl: 'http://localhost:8000',
    connectTimeout: const Duration(seconds: 60),  // 5 → 60
    receiveTimeout: const Duration(seconds: 60),  // 5 → 60
  ));
}
```

#### 2.2 远程数据源超时配置

**文件**: `lib/features/recognition/data/datasources/recognition_remote_datasource.dart`

**修改**:

```dart
final response = await dio.post(
  '/api/v1/recognition/recognize',
  data: formData,
  options: Options(
    headers: {
      'Accept': 'application/json',
    },
    sendTimeout: const Duration(seconds: 60),    // 10 → 60
    receiveTimeout: const Duration(seconds: 60),  // 10 → 60
  ),
);
```

**修改**:

```dart
if (e.type == DioExceptionType.connectionTimeout ||
    e.type == DioExceptionType.receiveTimeout ||
    e.type == DioExceptionType.sendTimeout) {
  throw const TimeoutException('Request timeout after 60 seconds'); // 5 → 60
}
```

#### 2.3 移除未使用的导入

**文件**: `lib/features/recognition/presentation/providers/recognition_providers.dart`

移除: `import 'package:flutter/foundation.dart' show kIsWeb;`

## 技术细节

### Web 平台文件处理差异

- **macOS/iOS/Android**: 支持完整的 `dart:io` File API
- **Web**: 只支持 `readAsBytes()`，不支持 `exists()`, `length()` 等方法

### 超时时间配置层级

1. **Dio BaseOptions**: 全局默认超时
   - `connectTimeout`: 连接超时
   - `receiveTimeout`: 接收数据超时

2. **Request Options**: 单个请求超时
   - `sendTimeout`: 发送数据超时
   - `receiveTimeout`: 接收数据超时（覆盖全局配置）

### OpenAI API 响应时间

- 图片上传: 1-2 秒
- GPT-4 Vision 分析: 15-25 秒
- 总响应时间: 20-30 秒
- **建议超时**: 60 秒（留有余量）

## 验证步骤

### 1. 热重载应用

在 Chrome 运行的 Flutter 应用中按 `r` 进行热重载：

```bash
# 在运行 flutter run -d chrome 的终端中输入
r
```

### 2. 测试图片识别

1. 点击"选择图片"按钮
2. 选择一张艺术品图片（JPEG/PNG，<10MB）
3. 等待识别结果（最多 60 秒）
4. 验证结果正确显示

### 3. 验证错误处理

- 上传超大文件（>10MB）→ 应显示错误
- 上传非图片文件 → 应显示格式错误
- 网络断开 → 应显示网络错误

## 平台兼容性

| 平台    | File.exists() | readAsBytes() | 修复后状态 |
| ------- | ------------- | ------------- | ---------- |
| macOS   | ✅            | ✅            | ✅ 正常    |
| iOS     | ✅            | ✅            | ✅ 正常    |
| Android | ✅            | ✅            | ✅ 正常    |
| Web     | ❌            | ✅            | ✅ 已修复  |

## 相关文件

修改的文件：

- `lib/features/recognition/domain/usecases/recognize_artwork.dart`
- `lib/features/recognition/presentation/providers/recognition_providers.dart`
- `lib/features/recognition/data/datasources/recognition_remote_datasource.dart`

## 后续优化建议

1. **进度指示器**: 添加上传/识别进度显示
2. **超时提示**: 在 40 秒时显示"正在处理中"提示
3. **缓存优化**: 利用图片哈希缓存识别结果
4. **错误重试**: 超时后允许用户重试

## 修复时间

2025-10-05

## 修复作者

Claude Code (AI Assistant)
