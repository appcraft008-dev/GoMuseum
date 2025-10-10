# 布局组件使用指南

本文档展示了如何使用 GoMuseum 的布局组件。

## 1. AppScaffold - 统一页面容器

### 基础用法

```dart
import 'package:gomuseum_app/ui/layouts/app_scaffold.dart';

class MyPage extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return AppScaffold(
      title: '博物馆详情',
      body: Center(child: Text('页面内容')),
    );
  }
}
```

### 带底部导航的页面

```dart
class HomePage extends StatefulWidget {
  @override
  _HomePageState createState() => _HomePageState();
}

class _HomePageState extends State<HomePage> {
  int _currentIndex = 0;

  @override
  Widget build(BuildContext context) {
    return AppScaffold(
      title: '首页',
      showBackButton: false,
      showBottomNav: true,
      currentNavIndex: _currentIndex,
      onNavTap: (index) {
        setState(() {
          _currentIndex = index;
        });
      },
      body: _getPageByIndex(_currentIndex),
    );
  }

  Widget _getPageByIndex(int index) {
    // 根据索引返回不同的页面
    switch (index) {
      case 0:
        return HomeContent();
      case 1:
        return ExploreContent();
      case 2:
        return HistoryContent();
      case 3:
        return SettingsContent();
      default:
        return HomeContent();
    }
  }
}
```

### 带悬浮按钮的页面

```dart
AppScaffold(
  title: '艺术品列表',
  body: ArtworkList(),
  floatingActionButton: FloatingActionButton(
    onPressed: () {
      // 添加艺术品
    },
    child: Icon(Icons.add),
  ),
  floatingActionButtonLocation: FloatingActionButtonLocation.centerFloat,
)
```

## 2. CustomAppBar - 自定义顶部栏

### 基础用法

```dart
import 'package:gomuseum_app/ui/layouts/app_bar_widget.dart';

Scaffold(
  appBar: CustomAppBar(
    title: '博物馆详情',
    showBackButton: true,
  ),
  body: MuseumDetails(),
)
```

### 透明 AppBar（用于图片背景）

```dart
Scaffold(
  extendBodyBehindAppBar: true,
  appBar: CustomAppBar(
    title: '精选展览',
    transparent: true,
    actions: [
      IconButton(
        icon: Icon(Icons.share),
        onPressed: () {},
      ),
    ],
  ),
  body: Stack(
    children: [
      Image.network(
        'https://example.com/header.jpg',
        fit: BoxFit.cover,
        height: 300,
        width: double.infinity,
      ),
      // 其他内容...
    ],
  ),
)
```

### 渐变 AppBar

```dart
import 'package:gomuseum_app/theme/colors.dart';

Scaffold(
  appBar: GradientAppBar(
    title: 'GoMuseum',
    gradient: AppColors.primaryGradient,
    actions: [
      IconButton(
        icon: Icon(Icons.notifications),
        onPressed: () {},
      ),
    ],
  ),
  body: HomePage(),
)
```

### 搜索 AppBar

```dart
class SearchPage extends StatefulWidget {
  @override
  _SearchPageState createState() => _SearchPageState();
}

class _SearchPageState extends State<SearchPage> {
  final TextEditingController _searchController = TextEditingController();

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: SearchAppBar(
        hintText: '搜索博物馆、艺术品...',
        controller: _searchController,
        autofocus: true,
        onSearch: (query) {
          // 执行搜索
          print('搜索: $query');
        },
      ),
      body: SearchResults(),
    );
  }
}
```

## 3. AppBottomNavigation - 底部导航栏

### Material 3 样式（推荐）

```dart
import 'package:gomuseum_app/ui/layouts/bottom_navigation_widget.dart';

class MainPage extends StatefulWidget {
  @override
  _MainPageState createState() => _MainPageState();
}

class _MainPageState extends State<MainPage> {
  int _currentIndex = 0;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: _pages[_currentIndex],
      bottomNavigationBar: AppBottomNavigation(
        currentIndex: _currentIndex,
        onTap: (index) {
          setState(() {
            _currentIndex = index;
          });
        },
      ),
    );
  }

  final List<Widget> _pages = [
    HomePage(),
    ExplorePage(),
    HistoryPage(),
    SettingsPage(),
  ];
}
```

### 经典 Material 2 样式

```dart
bottomNavigationBar: ClassicBottomNavigation(
  currentIndex: _currentIndex,
  onTap: (index) {
    setState(() {
      _currentIndex = index;
    });
  },
  type: BottomNavigationBarType.fixed,
)
```

### 浮动样式导航栏

```dart
bottomNavigationBar: FloatingBottomNavigation(
  currentIndex: _currentIndex,
  onTap: (index) {
    setState(() {
      _currentIndex = index;
    });
  },
  horizontalMargin: 16,
  bottomMargin: 16,
)
```

### 自定义导航项

```dart
import 'package:gomuseum_app/ui/layouts/bottom_navigation_widget.dart';

final customNavItems = [
  BottomNavItem(
    icon: Icons.museum_outlined,
    selectedIcon: Icons.museum,
    label: '博物馆',
    routeName: '/museums',
  ),
  BottomNavItem(
    icon: Icons.palette_outlined,
    selectedIcon: Icons.palette,
    label: '艺术品',
    routeName: '/artworks',
  ),
  BottomNavItem(
    icon: Icons.person_outline,
    selectedIcon: Icons.person,
    label: '我的',
    routeName: '/profile',
  ),
];

AppBottomNavigation(
  currentIndex: _currentIndex,
  onTap: (index) {
    setState(() {
      _currentIndex = index;
    });
  },
  items: customNavItems,
)
```

## 4. GradientScaffold - 渐变背景页面

```dart
import 'package:gomuseum_app/ui/layouts/app_scaffold.dart';
import 'package:gomuseum_app/theme/colors.dart';

GradientScaffold(
  gradient: AppColors.primaryGradient,
  title: 'GoMuseum',
  showBackButton: false,
  actions: [
    IconButton(
      icon: Icon(Icons.settings),
      onPressed: () {},
    ),
  ],
  body: WelcomePage(),
)
```

## 5. ScrollableScaffold - 可滚动页面

```dart
import 'package:gomuseum_app/ui/layouts/app_scaffold.dart';

ScrollableScaffold(
  title: '博物馆列表',
  onRefresh: () async {
    // 下拉刷新逻辑
    await Future.delayed(Duration(seconds: 2));
  },
  children: [
    MuseumCard(),
    MuseumCard(),
    MuseumCard(),
    // 更多卡片...
  ],
)
```

## 6. TabScaffold - 标签页容器

```dart
import 'package:gomuseum_app/ui/layouts/app_scaffold.dart';

TabScaffold(
  title: '展览',
  tabs: ['进行中', '即将开始', '已结束'],
  tabViews: [
    OngoingExhibitions(),
    UpcomingExhibitions(),
    PastExhibitions(),
  ],
  actions: [
    IconButton(
      icon: Icon(Icons.filter_list),
      onPressed: () {},
    ),
  ],
)
```

## 组件组合示例

### 完整的主页结构

```dart
class MainApp extends StatefulWidget {
  @override
  _MainAppState createState() => _MainAppState();
}

class _MainAppState extends State<MainApp> {
  int _currentIndex = 0;

  @override
  Widget build(BuildContext context) {
    return AppScaffold(
      // 根据当前页面显示不同的标题
      title: _getTitleByIndex(_currentIndex),
      showBackButton: false,
      actions: _getActionsByIndex(_currentIndex),
      showBottomNav: true,
      currentNavIndex: _currentIndex,
      onNavTap: (index) {
        setState(() {
          _currentIndex = index;
        });
      },
      body: _getPageByIndex(_currentIndex),
    );
  }

  String _getTitleByIndex(int index) {
    switch (index) {
      case 0:
        return 'GoMuseum';
      case 1:
        return '探索';
      case 2:
        return '历史记录';
      case 3:
        return '设置';
      default:
        return 'GoMuseum';
    }
  }

  List<Widget>? _getActionsByIndex(int index) {
    if (index == 0) {
      return [
        IconButton(
          icon: Icon(Icons.search),
          onPressed: () {
            // 打开搜索页面
          },
        ),
        IconButton(
          icon: Icon(Icons.notifications_outlined),
          onPressed: () {
            // 打开通知页面
          },
        ),
      ];
    }
    return null;
  }

  Widget _getPageByIndex(int index) {
    // 实现页面切换逻辑
    return Container();
  }
}
```

## 最佳实践

### 1. 统一使用 AppScaffold

建议在整个应用中统一使用 `AppScaffold`，而不是直接使用 `Scaffold`，以保持一致的样式和行为。

### 2. 底部导航的状态管理

对于复杂的应用，建议使用状态管理方案（如 Provider、Riverpod）来管理底部导航的状态。

### 3. 响应式设计

在平板或桌面端，考虑使用侧边导航代替底部导航：

```dart
Widget build(BuildContext context) {
  final isLargeScreen = MediaQuery.of(context).size.width > 600;

  if (isLargeScreen) {
    return Row(
      children: [
        NavigationRail(...),
        Expanded(child: _currentPage),
      ],
    );
  } else {
    return AppScaffold(
      showBottomNav: true,
      body: _currentPage,
    );
  }
}
```

### 4. 性能优化

对于包含大量内容的页面，使用 `ScrollableScaffold` 并结合 `ListView.builder` 实现列表的懒加载。

## 主题定制

所有组件都遵循应用的主题设置，可以通过修改 `lib/theme/` 目录下的文件来自定义样式：

- `colors.dart` - 颜色配置
- `dimensions.dart` - 尺寸和间距
- `typography.dart` - 字体样式
- `app_theme.dart` - 主题配置

## 注意事项

1. **导入路径**: 使用 `package:` 导入，而非相对路径
2. **Material 3**: 所有组件都基于 Material 3.0 设计规范
3. **响应式**: 组件会自动适配亮色/暗色模式
4. **安全区域**: 组件已处理安全区域，无需额外包装 `SafeArea`
