# GoMuseum 按钮组件库

基于 Material 3.0 设计规范的统一按钮组件库，为 GoMuseum 应用提供一致的交互体验。

## 组件列表

### 1. PrimaryButton (主要按钮)

基于 `ElevatedButton` 的主要操作按钮，用于页面中的主要 CTA (Call to Action) 操作。

#### 特性

- ✅ 使用主题主色 (AppColors.primary)
- ✅ 支持 loading 加载状态
- ✅ 支持图标 + 文字组合
- ✅ 完全支持禁用状态
- ✅ Material 3.0 设计规范
- ✅ 可自定义宽度和高度

#### 使用示例

```dart
// 基础用法
PrimaryButton(
  text: '提交',
  onPressed: () => print('提交'),
)

// 带图标
PrimaryButton(
  text: '上传照片',
  icon: Icons.upload,
  onPressed: () => print('上传'),
)

// 加载状态
PrimaryButton(
  text: '处理中...',
  isLoading: true,
  onPressed: null,
)

// 全宽按钮
PrimaryButton(
  text: '继续',
  isFullWidth: true,
  onPressed: () => print('继续'),
)
```

#### 参数说明

| 参数         | 类型          | 必填 | 默认值 | 说明                          |
| ------------ | ------------- | ---- | ------ | ----------------------------- |
| text         | String        | ✅   | -      | 按钮文字                      |
| onPressed    | VoidCallback? | ❌   | null   | 点击回调 (为 null 时按钮禁用) |
| icon         | IconData?     | ❌   | null   | 按钮图标                      |
| isLoading    | bool          | ❌   | false  | 是否处于加载状态              |
| isFullWidth  | bool          | ❌   | false  | 是否全宽 (占满父容器宽度)     |
| width        | double?       | ❌   | null   | 自定义宽度                    |
| height       | double?       | ❌   | 48.0   | 自定义高度                    |
| borderRadius | double?       | ❌   | 12.0   | 按钮圆角半径                  |

---

### 2. SecondaryButton (次要按钮)

基于 `OutlinedButton` 的次要操作按钮，用于页面中的次要或取消类操作。

#### 特性

- ✅ 透明背景 + 主色边框
- ✅ 支持图标 + 文字组合
- ✅ 完全支持禁用状态
- ✅ Material 3.0 设计规范
- ✅ 可自定义宽度和高度
- ✅ 点击时有水波纹效果

#### 使用示例

```dart
// 基础用法
SecondaryButton(
  text: '取消',
  onPressed: () => print('取消'),
)

// 带图标
SecondaryButton(
  text: '查看详情',
  icon: Icons.info_outline,
  onPressed: () => print('查看'),
)

// 自定义边框颜色 (危险操作)
SecondaryButton(
  text: '删除',
  borderColor: AppColors.error,
  textColor: AppColors.error,
  onPressed: () => print('删除'),
)
```

#### 参数说明

| 参数         | 类型          | 必填 | 默认值            | 说明                          |
| ------------ | ------------- | ---- | ----------------- | ----------------------------- |
| text         | String        | ✅   | -                 | 按钮文字                      |
| onPressed    | VoidCallback? | ❌   | null              | 点击回调 (为 null 时按钮禁用) |
| icon         | IconData?     | ❌   | null              | 按钮图标                      |
| isFullWidth  | bool          | ❌   | false             | 是否全宽                      |
| width        | double?       | ❌   | null              | 自定义宽度                    |
| height       | double?       | ❌   | 48.0              | 自定义高度                    |
| borderRadius | double?       | ❌   | 12.0              | 按钮圆角半径                  |
| borderColor  | Color?        | ❌   | AppColors.primary | 边框颜色                      |
| textColor    | Color?        | ❌   | AppColors.primary | 文字颜色                      |
| borderWidth  | double        | ❌   | 1.5               | 边框宽度                      |

---

### 3. IconButtonWidget (图标按钮)

基于 `IconButton` 的图标操作按钮，用于工具栏、导航栏等需要纯图标按钮的场景。

#### 特性

- ✅ 支持圆形背景 (可选)
- ✅ 大小可自定义
- ✅ 支持 Tooltip 提示文字
- ✅ Material 3.0 设计规范
- ✅ 支持多种样式变体
- ✅ 完全支持禁用状态

#### 使用示例

```dart
// 基础用法 (无背景)
IconButtonWidget(
  icon: Icons.favorite_border,
  onPressed: () => print('收藏'),
)

// 带圆形背景
IconButtonWidget(
  icon: Icons.share,
  onPressed: () => print('分享'),
  hasBackground: true,
  backgroundColor: AppColors.primary,
  iconColor: Colors.white,
)

// 带 Tooltip
IconButtonWidget(
  icon: Icons.settings,
  tooltip: '设置',
  onPressed: () => print('设置'),
)

// 不同样式变体
IconButtonWidget(
  icon: Icons.delete,
  variant: IconButtonVariant.danger,
  hasBackground: true,
  onPressed: () => print('删除'),
)
```

#### 参数说明

| 参数            | 类型              | 必填 | 默认值   | 说明                                      |
| --------------- | ----------------- | ---- | -------- | ----------------------------------------- |
| icon            | IconData          | ✅   | -        | 图标                                      |
| onPressed       | VoidCallback?     | ❌   | null     | 点击回调 (为 null 时按钮禁用)             |
| hasBackground   | bool              | ❌   | false    | 是否显示圆形背景                          |
| backgroundColor | Color?            | ❌   | null     | 背景颜色 (仅在 hasBackground=true 时有效) |
| iconColor       | Color?            | ❌   | null     | 图标颜色                                  |
| size            | double?           | ❌   | 40.0     | 按钮整体尺寸 (宽高相等)                   |
| iconSize        | double?           | ❌   | 24.0     | 图标大小                                  |
| tooltip         | String?           | ❌   | null     | Tooltip 提示文字                          |
| variant         | IconButtonVariant | ❌   | standard | 样式变体                                  |

#### 样式变体 (IconButtonVariant)

- `standard` - 标准样式 (默认)
- `primary` - 主色样式
- `secondary` - 辅色样式
- `success` - 成功样式 (绿色)
- `danger` - 危险样式 (红色)
- `warning` - 警告样式 (橙色)
- `info` - 信息样式 (蓝色)

---

## 常见用法组合

### 对话框底部按钮

```dart
Row(
  children: [
    Expanded(
      child: SecondaryButton(
        text: '取消',
        onPressed: () => Navigator.pop(context),
      ),
    ),
    const SizedBox(width: 12),
    Expanded(
      child: PrimaryButton(
        text: '确认',
        onPressed: () => _handleConfirm(),
      ),
    ),
  ],
)
```

### 工具栏图标按钮组

```dart
Row(
  children: [
    IconButtonWidget(
      icon: Icons.favorite_border,
      tooltip: '收藏',
      onPressed: () => _handleFavorite(),
    ),
    IconButtonWidget(
      icon: Icons.share,
      tooltip: '分享',
      onPressed: () => _handleShare(),
    ),
    IconButtonWidget(
      icon: Icons.more_vert,
      tooltip: '更多',
      onPressed: () => _showMoreOptions(),
    ),
  ],
)
```

### 加载状态按钮

```dart
PrimaryButton(
  text: _isSubmitting ? '提交中...' : '提交',
  isLoading: _isSubmitting,
  onPressed: _isSubmitting ? null : _handleSubmit,
)
```

---

## 导入方式

```dart
// 方式 1: 导入整个按钮库
import 'package:gomuseum_app/ui/components/buttons/buttons.dart';

// 方式 2: 单独导入特定按钮
import 'package:gomuseum_app/ui/components/buttons/primary_button.dart';
import 'package:gomuseum_app/ui/components/buttons/secondary_button.dart';
import 'package:gomuseum_app/ui/components/buttons/icon_button_widget.dart';
```

---

## 示例演示

查看完整的组件示例演示页面：

```dart
import 'package:gomuseum_app/ui/components/buttons/example/buttons_showcase.dart';

// 在应用中导航到演示页面
Navigator.push(
  context,
  MaterialPageRoute(builder: (context) => const ButtonsShowcase()),
);
```

---

## 设计规范

所有按钮组件遵循以下设计规范：

- **字体**: Roboto (AppTypography.button)
- **主色**: #1E3A8A (AppColors.primary)
- **辅色**: #F59E0B (AppColors.secondary)
- **按钮高度**: 48dp (AppDimensions.buttonHeight)
- **圆角半径**: 12dp (AppDimensions.radiusMedium)
- **图标尺寸**: 24dp (AppDimensions.iconSize)
- **内边距**: 水平 24dp，垂直 12dp
- **Material 版本**: Material 3.0

---

## 最佳实践

### ✅ 推荐

- 每个页面最多使用 1-2 个主要按钮 (PrimaryButton)
- 使用次要按钮 (SecondaryButton) 表示取消或返回操作
- 为图标按钮添加 Tooltip 提示文字，提升可访问性
- 禁用状态时将 onPressed 设为 null
- 使用 isLoading 参数显示加载状态，避免重复提交

### ❌ 避免

- 不要在同一行放置多个主要按钮
- 不要使用纯文本颜色区分按钮重要性
- 不要在加载状态时保留 onPressed 回调
- 不要随意修改按钮的默认尺寸和样式

---

## 技术要求

- Flutter SDK: >= 3.0.0
- Dart SDK: >= 3.0.0
- Material 版本: Material 3.0 (useMaterial3: true)

---

## 文件结构

```
lib/ui/components/buttons/
├── buttons.dart                  # 统一导出文件
├── primary_button.dart          # 主要按钮组件
├── secondary_button.dart        # 次要按钮组件
├── icon_button_widget.dart      # 图标按钮组件
├── example/
│   └── buttons_showcase.dart    # 组件展示示例
└── README.md                    # 本文档
```

---

## 更新日志

### v1.0.0 (2025-10-10)

- ✨ 初始版本发布
- ✅ 创建 PrimaryButton 组件
- ✅ 创建 SecondaryButton 组件
- ✅ 创建 IconButtonWidget 组件
- ✅ 添加完整文档和示例
- ✅ 通过 Flutter Analyze 检查

---

## 联系方式

如有问题或建议，请联系 GoMuseum 开发团队。
