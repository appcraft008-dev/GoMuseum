# Web 平台测试验证清单

## 修复验证 (Chrome)

### ✅ 前置条件

- [ ] 后端服务已启动 (`docker-compose up -d` 或 `cd backend && poetry run uvicorn app.main:app`)
- [ ] 后端运行在 `http://localhost:8000`
- [ ] 已安装 Chrome 浏览器

### 🚀 启动应用

**方式 1: 使用脚本**

```bash
cd /Users/hongyang/Projects/GoMuseum/frontend/gomuseum_app
./scripts/run_chrome.sh
```

**方式 2: 手动启动**

```bash
cd /Users/hongyang/Projects/GoMuseum/frontend/gomuseum_app
flutter run -d chrome --web-port=8080
```

### 📋 功能测试

#### 测试 1: 正常图片识别

- [ ] 点击"选择图片"按钮
- [ ] 选择测试图片（`Pictures-for-test/2222.jpg`）
- [ ] 图片上传成功
- [ ] 等待识别结果（20-30 秒）
- [ ] 显示识别结果：
  - [ ] 艺术品名称
  - [ ] 艺术家
  - [ ] 创作年代
  - [ ] 描述信息

**预期**: ✅ 成功识别，无超时错误

#### 测试 2: 文件大小验证

- [ ] 选择大文件（>10MB）
- [ ] 显示错误提示："Image size exceeds 10MB limit"

**预期**: ✅ 显示文件大小错误

#### 测试 3: 文件格式验证

- [ ] 选择非图片文件（.txt, .pdf, .docx）
- [ ] 显示错误提示："Unsupported image format"

**预期**: ✅ 显示格式错误

#### 测试 4: 超时处理

- [ ] 关闭后端服务
- [ ] 选择图片上传
- [ ] 等待 60 秒
- [ ] 显示超时错误："Request timeout after 60 seconds"

**预期**: ✅ 在 60 秒后显示超时错误（不是 5 秒）

#### 测试 5: 缓存功能

- [ ] 上传图片 A，等待识别结果
- [ ] 再次上传同一张图片 A
- [ ] 快速返回结果（使用缓存）

**预期**: ✅ 第二次识别速度明显加快

### 🔍 控制台检查

打开 Chrome DevTools (F12)，检查：

#### Console 标签

- [ ] 无 `DartError: Unsupported operation: _Namespace` 错误
- [ ] 无 `imageFile.exists()` 相关错误
- [ ] 正常显示日志（如有）

#### Network 标签

- [ ] POST `/api/v1/recognition/recognize` 请求
- [ ] 请求状态: 200 OK
- [ ] 响应时间: 20-30 秒
- [ ] 响应内容: JSON 格式的识别结果

### 🐛 已知问题检查

#### 问题 1: File.exists() 错误 (已修复)

**修复前错误**:

```
DartError: Unsupported operation: _Namespace
at imageFile.exists()
in recognize_artwork.dart:41
```

**验证**:

- [ ] Console 中无此错误
- [ ] 图片上传正常

#### 问题 2: 超时错误 (已修复)

**修复前错误**:

```
TimeoutException: Request timeout after 5 seconds
```

**验证**:

- [ ] 识别过程可以超过 5 秒
- [ ] 最多等待 60 秒
- [ ] 正常返回识别结果

### 🎯 性能验证

#### 超时配置检查

- [ ] Dio connectTimeout: 60 秒 ✅
- [ ] Dio receiveTimeout: 60 秒 ✅
- [ ] Request sendTimeout: 60 秒 ✅
- [ ] Request receiveTimeout: 60 秒 ✅

#### 响应时间测试

| 操作     | 预期时间 | 实际时间 | 状态 |
| -------- | -------- | -------- | ---- |
| 选择图片 | < 1s     | \_\_\_   | ⬜   |
| 上传图片 | 1-2s     | \_\_\_   | ⬜   |
| AI 识别  | 15-25s   | \_\_\_   | ⬜   |
| 总耗时   | 20-30s   | \_\_\_   | ⬜   |
| 缓存命中 | < 1s     | \_\_\_   | ⬜   |

### 📱 跨平台验证

| 平台          | 启动命令                | 状态 | 备注               |
| ------------- | ----------------------- | ---- | ------------------ |
| Chrome        | `flutter run -d chrome` | ⬜   | 主要测试平台       |
| macOS         | `flutter run -d macos`  | ⬜   | 确保未破坏原有功能 |
| iOS Simulator | `flutter run -d ios`    | ⬜   | 可选               |

### ✅ 验收标准

**必须全部通过**:

- [ ] Chrome 可以正常选择图片
- [ ] 图片上传成功
- [ ] 识别结果在 60 秒内返回
- [ ] 无 Web 平台不兼容错误
- [ ] 文件大小/格式验证正常
- [ ] 错误提示友好清晰
- [ ] macOS 平台功能不受影响

### 🚨 回退方案

如果测试失败，可以回退代码：

```bash
git checkout HEAD -- lib/features/recognition/domain/usecases/recognize_artwork.dart
git checkout HEAD -- lib/features/recognition/presentation/providers/recognition_providers.dart
git checkout HEAD -- lib/features/recognition/data/datasources/recognition_remote_datasource.dart
flutter run -d chrome
```

### 📝 测试记录

**测试人员**: ******\_\_\_******
**测试时间**: ******\_\_\_******
**Flutter 版本**: `flutter --version`
**Chrome 版本**: `chrome://version`

**测试结果**:

- 通过测试数: \_\_\_ / 5
- 失败测试数: \_\_\_
- 总体评价: ⬜ 通过 ⬜ 失败

**问题记录**:

```
1.
2.
3.
```

**备注**:

```

```

---

## 热重载说明

在 Flutter 应用运行时，修改代码后可以使用热重载：

**热重载 (Hot Reload)**:

- 按键: `r`
- 用途: 快速应用代码更改，保留应用状态
- 适用: UI 更改、业务逻辑调整

**热重启 (Hot Restart)**:

- 按键: `R`
- 用途: 完全重启应用，清除所有状态
- 适用: 状态管理更改、依赖注入更改

**退出**:

- 按键: `q`
- 用途: 停止 Flutter 应用

## 相关文档

- [WEB_PLATFORM_FIX.md](WEB_PLATFORM_FIX.md) - 修复详细说明
- [CACHE_FIX_README.md](../../CACHE_FIX_README.md) - 缓存功能说明
