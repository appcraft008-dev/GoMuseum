# 布局组件库 (Layouts)

GoMuseum 应用的核心布局组件，提供统一的页面结构和导航体验。

## 📁 文件结构

```
lib/ui/layouts/
├── README.md                      # 本文档
├── USAGE_EXAMPLES.md              # 详细使用示例
├── app_bar_widget.dart            # AppBar 组件
├── app_scaffold.dart              # 页面容器组件
└── bottom_navigation_widget.dart  # 底部导航组件
```

## 🎨 组件清单

### 1. AppBar 组件 (app_bar_widget.dart)

#### CustomAppBar

- **用途**: 标准自定义顶部栏
- **特性**: 支持返回按钮、透明背景、自定义操作按钮
- **适用场景**: 大多数页面

#### GradientAppBar

- **用途**: 渐变背景顶部栏
- **特性**: 支持自定义渐变、白色文字
- **适用场景**: 首页、特殊展示页面

#### SearchAppBar

- **用途**: 搜索顶部栏
- **特性**: 集成搜索输入框、自动聚焦
- **适用场景**: 搜索页面

### 2. 页面容器组件 (app_scaffold.dart)

#### AppScaffold

- **用途**: 标准页面容器
- **特性**: 集成 AppBar 和底部导航、支持 FAB
- **适用场景**: 所有标准页面

#### GradientScaffold

- **用途**: 渐变背景页面
- **特性**: 全屏渐变背景
- **适用场景**: 欢迎页、特殊主题页

#### ScrollableScaffold

- **用途**: 可滚动页面
- **特性**: 下拉刷新、自动滚动
- **适用场景**: 列表页面

#### TabScaffold

- **用途**: 标签页容器
- **特性**: 顶部标签切换
- **适用场景**: 分类内容展示

### 3. 底部导航组件 (bottom_navigation_widget.dart)

#### AppBottomNavigation (推荐)

- **用途**: Material 3 风格底部导航
- **特性**: 现代化设计、流畅动画
- **适用场景**: 主导航

#### ClassicBottomNavigation

- **用途**: Material 2 风格底部导航
- **特性**: 经典样式
- **适用场景**: 需要传统样式时

#### FloatingBottomNavigation

- **用途**: 浮动样式底部导航
- **特性**: 圆角、阴影、边距
- **适用场景**: 现代化应用

## 🚀 快速开始

### 基础页面

```dart
import 'package:gomuseum_app/ui/layouts/app_scaffold.dart';

class MyPage extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return AppScaffold(
      title: '页面标题',
      body: YourContent(),
    );
  }
}
```

### 带底部导航的主页

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
      body: _pages[_currentIndex],
    );
  }

  final _pages = [HomePage(), ExplorePage(), HistoryPage(), SettingsPage()];
}
```

## 📋 默认导航项

底部导航默认包含 4 个导航项：

1. **首页** (Home) - Icons.home_outlined
2. **探索** (Explore) - Icons.explore_outlined
3. **历史** (History) - Icons.history_outlined
4. **设置** (Settings) - Icons.settings_outlined

可通过 `items` 参数自定义导航项。

## 🎨 主题适配

所有组件完全适配应用主题系统：

- ✅ 自动适配亮色/暗色模式
- ✅ 使用 `AppColors` 色彩系统
- ✅ 遵循 `AppDimensions` 间距规范
- ✅ Material Design 3.0 规范

## 📱 响应式支持

组件已考虑响应式设计：

- 自动处理安全区域 (SafeArea)
- 支持键盘避让 (resizeToAvoidBottomInset)
- 适配不同屏幕尺寸

## 🔧 技术特性

### 性能优化

- 使用 `const` 构造函数
- 避免不必要的重建
- 懒加载支持

### 可访问性

- 完整的 Tooltip 支持
- 语义化标签
- 屏幕阅读器友好

### 代码质量

- ✅ 通过 `flutter analyze` 检查
- ✅ 遵循 Dart 代码规范
- ✅ 完整的文档注释

## 📚 更多示例

详细使用示例请参考 [USAGE_EXAMPLES.md](./USAGE_EXAMPLES.md)

## 🛠️ 自定义扩展

### 创建自定义 AppBar

```dart
class MyCustomAppBar extends StatelessWidget implements PreferredSizeWidget {
  @override
  Widget build(BuildContext context) {
    return CustomAppBar(
      // 自定义配置
    );
  }

  @override
  Size get preferredSize => Size.fromHeight(kToolbarHeight);
}
```

### 自定义导航项

```dart
final customNavItems = [
  BottomNavItem(
    icon: Icons.museum,
    label: '博物馆',
  ),
  // 更多自定义项...
];

AppBottomNavigation(
  items: customNavItems,
  currentIndex: _index,
  onTap: _onTap,
)
```

## 📝 注意事项

1. **导入规范**: 始终使用 `package:` 导入
2. **状态管理**: 导航状态建议使用状态管理方案
3. **性能考虑**: 大列表使用 `ListView.builder`
4. **主题一致性**: 避免硬编码颜色和尺寸

## 🔗 相关文档

- [主题系统](../../theme/README.md)
- [组件库](../components/README.md)
- [页面示例](../pages/README.md)

---

**版本**: v1.0  
**更新日期**: 2025-10-10  
**维护者**: GoMuseum Team
