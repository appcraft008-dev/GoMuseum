# GoMuseum 反馈组件快速入门

## 📦 导入组件

```dart
// 方式1: 导入所有反馈组件（推荐）
import 'package:gomuseum_app/ui/components/feedback/feedback_widgets.dart';

// 方式2: 按需导入
import 'package:gomuseum_app/ui/components/feedback/loading_widget.dart';
import 'package:gomuseum_app/ui/components/feedback/error_widget.dart';
import 'package:gomuseum_app/ui/components/feedback/empty_state_widget.dart';
```

## 🚀 常用场景

### 1. 数据列表加载

```dart
class ArtworkListScreen extends StatelessWidget {
  final bool isLoading;
  final bool hasError;
  final List<Artwork> artworks;

  @override
  Widget build(BuildContext context) {
    // 加载中
    if (isLoading) {
      return ListView.builder(
        itemCount: 5,
        itemBuilder: (_, __) => ListItemShimmer(),
      );
    }

    // 加载失败
    if (hasError) {
      return AppErrorWidget.network(
        onRetry: () => _loadData(),
      );
    }

    // 数据为空
    if (artworks.isEmpty) {
      return AppEmptyStateWidget.content(
        contentType: '艺术品',
        onAction: () => _refresh(),
      );
    }

    // 显示数据
    return ListView.builder(
      itemCount: artworks.length,
      itemBuilder: (context, index) {
        return ArtworkListItem(artworks[index]);
      },
    );
  }
}
```

### 2. 图片识别页面

```dart
class RecognitionScreen extends StatefulWidget {
  @override
  Widget build(BuildContext context) {
    return recognitionState.when(
      loading: () => AppLoadingWidget.fullScreen(
        message: '正在识别艺术品...',
      ),
      error: (error) => AppErrorWidget(
        icon: Icons.image_not_supported,
        message: '识别失败，请重试',
        onRetry: () => _retry(),
      ),
      noResult: () => AppEmptyStateWidget.noRecognition(
        onAction: () => _retakePhoto(),
      ),
      success: (result) => RecognitionResultWidget(result),
    );
  }
}
```

### 3. 历史记录页面

```dart
class HistoryScreen extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    if (historyList.isEmpty) {
      return AppEmptyStateWidget.history(
        onAction: () => Navigator.pushNamed(context, '/explore'),
      );
    }

    return ListView.builder(...);
  }
}
```

### 4. 收藏页面

```dart
class FavoritesScreen extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    if (favorites.isEmpty) {
      return AppEmptyStateWidget.favorites(
        onAction: () => Navigator.pushNamed(context, '/discover'),
      );
    }

    return GridView.builder(...);
  }
}
```

### 5. 搜索结果页面

```dart
class SearchResultsScreen extends StatelessWidget {
  final String query;

  @override
  Widget build(BuildContext context) {
    if (isSearching) {
      return CardShimmer();
    }

    if (results.isEmpty) {
      return AppEmptyStateWidget.searchResults(
        searchQuery: query,
        onAction: () => _clearSearch(),
      );
    }

    return ListView.builder(...);
  }
}
```

## 🎨 定制组件

### 自定义加载组件

```dart
AppLoadingWidget(
  size: 60.0,
  color: Colors.amber,
  message: '自定义加载文字',
)
```

### 自定义错误组件

```dart
AppErrorWidget.custom(
  icon: Icons.warning_amber,
  title: '自定义标题',
  message: '自定义错误消息',
  iconColor: Colors.orange,
  onRetry: () => retry(),
  retryText: '重新加载',
)
```

### 自定义空状态组件

```dart
AppEmptyStateWidget(
  icon: Icons.palette,
  title: '暂无艺术品',
  message: '快去发现更多精彩艺术品吧',
  actionLabel: '立即探索',
  onAction: () => navigate(),
  iconSize: 100.0,
  iconColor: Colors.blue,
)
```

## 🔄 与Riverpod集成

```dart
class ArtworkScreen extends ConsumerWidget {
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
        return ArtworkList(artworks);
      },
      loading: () => AppLoadingWidget.withText('加载中...'),
      error: (error, stack) => AppErrorWidget.network(
        onRetry: () => ref.refresh(artworksProvider),
      ),
    );
  }
}
```

## 💡 最佳实践

### 1. 骨架屏优于转圈加载

```dart
// ❌ 不推荐
if (isLoading) {
  return Center(child: CircularProgressIndicator());
}

// ✅ 推荐
if (isLoading) {
  return ListView.builder(
    itemCount: 3,
    itemBuilder: (_, __) => ListItemShimmer(),
  );
}
```

### 2. 提供明确的错误操作

```dart
// ❌ 不推荐
AppErrorWidget(message: '出错了')

// ✅ 推荐
AppErrorWidget.network(
  message: '网络连接失败，请检查网络设置',
  onRetry: () => reload(),
)
```

### 3. 空状态提供引导操作

```dart
// ❌ 不推荐
AppEmptyStateWidget(
  icon: Icons.inbox,
  title: '空',
  message: '没有数据',
)

// ✅ 推荐
AppEmptyStateWidget.favorites(
  onAction: () => navigateToDiscover(),
)
```

## 🎯 组件选择指南

| 场景         | 推荐组件                              |
| ------------ | ------------------------------------- |
| 页面首次加载 | `AppLoadingWidget.withText()`         |
| 列表加载     | `ListItemShimmer()`                   |
| 卡片加载     | `CardShimmer()`                       |
| 全屏操作     | `AppLoadingWidget.fullScreen()`       |
| 网络错误     | `AppErrorWidget.network()`            |
| 服务器错误   | `AppErrorWidget.server()`             |
| 表单验证错误 | `InlineErrorWidget()`                 |
| 空历史       | `AppEmptyStateWidget.history()`       |
| 空收藏       | `AppEmptyStateWidget.favorites()`     |
| 空搜索       | `AppEmptyStateWidget.searchResults()` |
| 识别失败     | `AppEmptyStateWidget.noRecognition()` |

## 📱 查看完整示例

运行示例页面查看所有组件效果：

```dart
Navigator.push(
  context,
  MaterialPageRoute(
    builder: (_) => FeedbackWidgetsExample(),
  ),
);
```

## 📚 更多文档

- [完整文档](./README.md)
- [实现总结](./IMPLEMENTATION_SUMMARY.md)
- [示例代码](./feedback_widgets_example.dart)
