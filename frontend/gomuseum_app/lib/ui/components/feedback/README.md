# GoMuseum 反馈组件

本目录包含GoMuseum应用的所有反馈状态组件，遵循Material Design 3.0设计规范。

## 📦 组件列表

### 1. 加载状态组件 (`loading_widget.dart`)

提供多种加载状态的视觉反馈。

#### 主要组件：

- **AppLoadingWidget** - 主要加载组件
- **ShimmerLoading** - Shimmer骨架屏效果
- **CardShimmer** - 卡片骨架屏
- **ListItemShimmer** - 列表项骨架屏

#### 使用示例：

```dart
// 基础圆形加载
AppLoadingWidget()

// 带提示文字
AppLoadingWidget.withText('加载中...')

// 全屏加载遮罩
AppLoadingWidget.fullScreen(message: '正在识别艺术品...')

// Shimmer 骨架屏
ShimmerLoading(
  width: double.infinity,
  height: 200,
)

// 圆形骨架屏
ShimmerLoading.circle(size: 48)

// 卡片骨架屏
CardShimmer()

// 列表项骨架屏
ListItemShimmer()
```

### 2. 错误状态组件 (`error_widget.dart`)

提供统一的错误状态视觉反馈。

#### 主要组件：

- **AppErrorWidget** - 主要错误组件
- **InlineErrorWidget** - 内联错误提示
- **ErrorBanner** - 错误横幅

#### 使用示例：

```dart
// 基础错误提示
AppErrorWidget(
  message: '加载失败',
  onRetry: () => loadData(),
)

// 网络错误
AppErrorWidget.network(
  onRetry: () => fetchData(),
)

// 服务器错误
AppErrorWidget.server(
  onRetry: () => retry(),
)

// 权限错误
AppErrorWidget.permission(
  message: '您没有访问此内容的权限',
)

// 内联错误提示 (用于表单验证)
InlineErrorWidget(
  message: '请输入有效的邮箱地址',
)

// 错误横幅 (页面顶部)
ErrorBanner(
  message: '同步失败，部分数据可能已过期',
  onDismiss: () => setState(() => showBanner = false),
  onAction: () => syncData(),
  actionLabel: '立即同步',
)
```

### 3. 空状态组件 (`empty_state_widget.dart`)

提供统一的空状态视觉反馈。

#### 主要组件：

- **AppEmptyStateWidget** - 主要空状态组件
- **EmptyListPlaceholder** - 列表空状态占位符
- **EmptyGridPlaceholder** - 网格空状态占位符

#### 使用示例：

```dart
// 基础空状态
AppEmptyStateWidget(
  icon: Icons.inbox_outlined,
  title: '暂无内容',
  message: '这里还没有任何内容',
)

// 空历史记录
AppEmptyStateWidget.history(
  onAction: () => startExploring(),
)

// 空收藏
AppEmptyStateWidget.favorites(
  onAction: () => navigateToDiscover(),
)

// 空搜索结果
AppEmptyStateWidget.searchResults(
  searchQuery: '莫奈',
  onAction: () => clearSearch(),
)

// 空识别结果
AppEmptyStateWidget.noRecognition(
  onAction: () => retakePhoto(),
)

// 空通知
AppEmptyStateWidget.notifications()

// 列表空状态占位
EmptyListPlaceholder(
  message: '暂无数据',
)

// 网格空状态占位
EmptyGridPlaceholder(
  message: '暂无艺术品',
  onAction: () => refresh(),
  actionLabel: '刷新',
)
```

## 🎨 设计规范

所有组件都遵循GoMuseum的设计系统：

### 颜色使用

- **主色**: `AppColors.primary` (#1E3A8A)
- **错误色**: `AppColors.error` (#EF4444)
- **次要文字**: `AppColors.textSecondary` (亮色: #6B7280, 暗色: #D1D5DB)

### 间距规范

- **小间距**: `AppDimensions.spacing8` (8dp)
- **中间距**: `AppDimensions.spacing16` (16dp)
- **大间距**: `AppDimensions.spacing24` (24dp)

### 字体样式

- **标题**: `AppTypography.headlineMedium`
- **正文**: `AppTypography.bodyMedium`
- **小文字**: `AppTypography.bodySmall`

## 🔄 状态管理集成

这些组件可以轻松与各种状态管理方案集成：

### Riverpod 示例

```dart
class ArtworkListScreen extends ConsumerWidget {
  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final artworksAsync = ref.watch(artworksProvider);

    return artworksAsync.when(
      data: (artworks) {
        if (artworks.isEmpty) {
          return AppEmptyStateWidget.content(
            contentType: '艺术品',
            onAction: () => ref.refresh(artworksProvider),
          );
        }
        return ListView.builder(...);
      },
      loading: () => AppLoadingWidget.withText('加载艺术品列表...'),
      error: (error, stack) => AppErrorWidget.network(
        onRetry: () => ref.refresh(artworksProvider),
      ),
    );
  }
}
```

### 骨架屏最佳实践

```dart
ListView.builder(
  itemCount: isLoading ? 5 : items.length,
  itemBuilder: (context, index) {
    if (isLoading) {
      return ListItemShimmer();
    }
    return YourListItem(items[index]);
  },
)
```

## 📱 响应式设计

所有组件都支持：

- ✅ 亮色模式 / 暗色模式
- ✅ 不同屏幕尺寸
- ✅ Material 3.0 动态颜色

## 🧪 测试

查看 `feedback_widgets_example.dart` 获取完整的使用示例和测试页面。

## 📝 开发指南

### 添加新的反馈组件

1. 创建新的组件文件
2. 使用现有主题系统 (`AppColors`, `AppDimensions`, `AppTypography`)
3. 提供多个工厂构造函数以支持常见场景
4. 添加详细的文档注释和使用示例
5. 更新此README文档

### 代码规范

- 使用 `dart format` 格式化代码
- 运行 `flutter analyze` 检查代码质量
- 添加完整的文档注释
- 提供清晰的使用示例

## 🔗 相关文件

- 主题系统: `lib/theme/`
- 其他UI组件: `lib/ui/components/`
- 示例页面: `feedback_widgets_example.dart`
