# GoMuseum Step 3 - UI开发完整实施计划

**目标**: 完成剩余 70% 的 UI 开发工作
**预估时间**: 12小时
**当前进度**: 30% → 100%

---

## 📋 执行清单

### Phase 1: UI 组件库 (4小时)

#### 任务 1.1: 布局组件 (1小时)

```bash
# 调用 flutter-expert agent
创建以下文件:

1. lib/ui/layouts/app_scaffold.dart
   - 统一的页面容器
   - 集成 AppBar 和 BottomNavigationBar
   - 支持 floating action button

2. lib/ui/layouts/bottom_navigation_widget.dart
   - 4个导航项: Home / Explore / History / Settings
   - 使用 AppColors.primary 作为选中颜色
   - Material 3.0 样式

3. lib/ui/layouts/app_bar_widget.dart
   - 自定义 AppBar
   - 返回按钮/标题/操作按钮
   - 透明背景支持
```

#### 任务 1.2: 反馈组件 (1小时)

```bash
# 调用 ui-ux-designer agent
创建以下文件:

1. lib/ui/components/feedback/loading_widget.dart
   - 圆形进度条
   - 骨架屏 (Shimmer效果)
   - 自定义加载动画

2. lib/ui/components/feedback/error_widget.dart
   - 错误图标 + 消息
   - 重试按钮
   - 可自定义图标和文字

3. lib/ui/components/feedback/empty_state_widget.dart
   - 空状态图标 + 提示文字
   - 可选操作按钮
   - 使用 AppColors.textSecondary
```

#### 任务 1.3: 按钮组件 (1小时)

```bash
# 调用 flutter-expert agent
创建以下文件:

1. lib/ui/components/buttons/primary_button.dart
   - ElevatedButton 封装
   - 支持 loading 状态
   - 支持图标 + 文字

2. lib/ui/components/buttons/secondary_button.dart
   - OutlinedButton 封装
   - 边框颜色使用 AppColors.primary

3. lib/ui/components/buttons/icon_button_widget.dart
   - IconButton 封装
   - 圆形背景可选
   - 大小可自定义
```

#### 任务 1.4: 卡片组件 (1小时)

```bash
# 调用 ui-ux-designer agent
创建以下文件:

1. lib/ui/components/cards/artwork_card.dart
   - 图片 + 标题 + 副标题
   - 点击效果
   - Hero 动画支持

2. lib/ui/components/cards/history_card.dart
   - 缩略图 + 信息 + 时间
   - 左滑删除
   - 分组头部支持

3. lib/ui/components/cards/museum_card.dart
   - 博物馆图片 + 名称
   - 地址 + 开放时间
   - 距离标签
```

---

### Phase 2: 核心页面 (6小时)

#### 任务 2.1: 主页 HomePage (1.5小时)

```bash
# 调用 frontend-developer agent

文件: lib/features/home/presentation/pages/home_page.dart

需求:
1. Hero 区域:
   - 大按钮 "扫描艺术品" (占屏幕 40% 高度)
   - 渐变背景 (AppColors.primaryGradient)
   - 相机图标

2. 附近博物馆:
   - 横向滚动列表
   - 使用 MuseumCard 组件
   - 3个卡片宽度 = 70% 屏幕宽度

3. 热门艺术品:
   - 2列网格
   - 使用 ArtworkCard 组件
   - 上拉加载更多

4. 底部导航:
   - 使用 BottomNavigationWidget
   - 当前索引 = 0
```

#### 任务 2.2: 相机页 CameraPage (1.5小时)

```bash
# 调用 frontend-developer agent

文件: lib/features/recognition/presentation/pages/camera_page.dart

需求:
1. 相机预览:
   - 使用 camera 插件
   - 全屏预览
   - 自动对焦

2. 顶部工具栏:
   - 闪光灯开关
   - 关闭按钮

3. 底部控制:
   - 相册按钮 (左)
   - 拍照按钮 (中间，80dp大圆形)
   - 切换相机 (右)

4. 拍照后:
   - 显示预览
   - 确认/重拍按钮
   - 导航到 ResultPage
```

#### 任务 2.3: 结果页 ResultPage (1小时)

```bash
# 调用 flutter-expert agent

文件: lib/features/recognition/presentation/pages/result_page.dart

需求:
1. 艺术品图片:
   - Hero 动画
   - 全宽显示
   - 缩放查看

2. 信息卡片:
   - 作品名称 (AppTypography.artworkTitle)
   - 艺术家 (AppTypography.artistName)
   - 时期/年代
   - 置信度 (进度条 + 百分比)

3. 讲解内容:
   - 可展开/收起
   - 占位符: "讲解功能即将推出"
   - TTS 按钮 (禁用状态)

4. 操作按钮:
   - 收藏/分享
```

#### 任务 2.4: 历史页 HistoryPage (1小时)

```bash
# 调用 flutter-expert agent

文件: lib/features/history/presentation/pages/history_page.dart

需求:
1. 顶部筛选:
   - 按日期/按博物馆切换
   - 搜索框

2. 列表展示:
   - 使用 HistoryCard 组件
   - 分组头部 (日期或博物馆名)
   - 左滑删除

3. 空状态:
   - 使用 EmptyStateWidget
   - 图标: Icons.history
   - 提示: "暂无历史记录"

4. 数据源:
   - 从本地 Drift 数据库读取
   - 使用 Riverpod Provider
```

#### 任务 2.5: 探索页 ExplorePage (1小时)

```bash
# 调用 frontend-developer agent

文件: lib/features/explore/presentation/pages/explore_page.dart

需求:
1. 搜索栏:
   - 提示: "搜索博物馆或艺术品"
   - 实时搜索

2. 筛选标签:
   - 城市/博物馆/艺术品
   - Chip 组件

3. 结果列表:
   - 博物馆: MuseumCard
   - 艺术品: ArtworkCard
   - 分页加载

4. 详情跳转:
   - 点击跳转详情页
   - Hero 动画
```

#### 任务 2.6: 设置页 SettingsPage (0.5小时)

```bash
# 调用 flutter-expert agent

文件: lib/features/settings/presentation/pages/settings_page.dart

需求:
1. 账户部分:
   - 用户头像 + 名称
   - 登录/注册按钮

2. 通用设置:
   - 语言选择 (Dropdown)
   - 暗色模式开关 (Switch)
   - 清除缓存

3. 关于:
   - 版本号
   - 许可证
   - 关于我们

4. 功能:
   - 语言切换实时生效
   - 主题切换实时生效
```

---

### Phase 3: 路由和国际化 (1.5小时)

#### 任务 3.1: 路由配置 (0.5小时)

```bash
# 调用 flutter-expert agent

文件: lib/core/router/app_router.dart

使用 go_router:

final goRouter = GoRouter(
  routes: [
    GoRoute(path: '/', builder: (context, state) => HomePage()),
    GoRoute(path: '/camera', builder: (context, state) => CameraPage()),
    GoRoute(path: '/result/:id', builder: (context, state) => ResultPage(...)),
    GoRoute(path: '/explore', builder: (context, state) => ExplorePage()),
    GoRoute(path: '/history', builder: (context, state) => HistoryPage()),
    GoRoute(path: '/settings', builder: (context, state) => SettingsPage()),
  ],
);
```

#### 任务 3.2: 补充国际化 (1小时)

```bash
# 手动创建或使用翻译工具

创建以下文件:
1. lib/l10n/app_fr.arb  (法文)
2. lib/l10n/app_de.arb  (德文)
3. lib/l10n/app_es.arb  (西班牙文)
4. lib/l10n/app_it.arb  (意大利文)

参考 app_en.arb 的结构完整翻译所有字段
```

---

### Phase 4: 主应用入口 (0.5小时)

#### 任务 4.1: 更新 main.dart

```bash
# 调用 flutter-expert agent

文件: lib/main.dart

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'theme/app_theme.dart';
import 'core/router/app_router.dart';
import 'package:flutter_gen/gen_l10n/app_localizations.dart';

void main() {
  runApp(ProviderScope(child: MyApp()));
}

class MyApp extends ConsumerWidget {
  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return MaterialApp.router(
      title: 'GoMuseum',
      theme: AppTheme.lightTheme(),
      darkTheme: AppTheme.darkTheme(),
      routerConfig: goRouter,
      localizationsDelegates: [
        AppLocalizations.delegate,
        GlobalMaterialLocalizations.delegate,
        GlobalWidgetsLocalizations.delegate,
        GlobalCupertinoLocalizations.delegate,
      ],
      supportedLocales: [
        Locale('en'),
        Locale('zh'),
        Locale('fr'),
        Locale('de'),
        Locale('es'),
        Locale('it'),
      ],
    );
  }
}
```

---

### Phase 5: 测试 (1小时)

#### 任务 5.1: Widget 测试

```bash
# 调用 test-automator agent

创建测试文件:

1. test/theme/app_theme_test.dart
   - 测试亮色/暗色主题
   - 测试色彩正确性

2. test/ui/components/buttons/primary_button_test.dart
   - 测试点击事件
   - 测试 loading 状态

3. test/ui/components/cards/artwork_card_test.dart
   - 测试渲染
   - 测试点击跳转

4. test/features/home/presentation/pages/home_page_test.dart
   - 测试页面结构
   - 测试导航

目标: Widget 测试覆盖率 > 75%
```

---

## 🚀 执行指令

### 在新对话中执行以下命令:

```bash
# 1. 调用 flutter-expert agent 创建布局组件
请根据 STEP3_IMPLEMENTATION_PLAN.md 的 Phase 1 - 任务 1.1
创建 app_scaffold.dart, bottom_navigation_widget.dart, app_bar_widget.dart

# 2. 调用 ui-ux-designer agent 创建反馈组件
请根据 STEP3_IMPLEMENTATION_PLAN.md 的 Phase 1 - 任务 1.2
创建 loading_widget.dart, error_widget.dart, empty_state_widget.dart

# 3. 调用 flutter-expert agent 创建按钮组件
请根据 STEP3_IMPLEMENTATION_PLAN.md 的 Phase 1 - 任务 1.3
创建 primary_button.dart, secondary_button.dart, icon_button_widget.dart

# 4. 调用 ui-ux-designer agent 创建卡片组件
请根据 STEP3_IMPLEMENTATION_PLAN.md 的 Phase 1 - 任务 1.4
创建 artwork_card.dart, history_card.dart, museum_card.dart

# 5. 调用 frontend-developer agent 创建所有页面
请根据 STEP3_IMPLEMENTATION_PLAN.md 的 Phase 2
依次创建 6 个核心页面

# 6. 调用 flutter-expert agent 配置路由
请根据 STEP3_IMPLEMENTATION_PLAN.md 的 Phase 3.1
创建 app_router.dart

# 7. 更新 main.dart
请根据 STEP3_IMPLEMENTATION_PLAN.md 的 Phase 4.1
更新主入口文件

# 8. 调用 test-automator agent 创建测试
请根据 STEP3_IMPLEMENTATION_PLAN.md 的 Phase 5
创建 Widget 测试套件

# 9. 运行测试验证
flutter test
flutter analyze
```

---

## 📦 依赖包更新

### pubspec.yaml 需要添加:

```yaml
dependencies:
  flutter:
    sdk: flutter
  flutter_localizations:
    sdk: flutter
  intl: any

  # 状态管理
  flutter_riverpod: ^2.4.0
  riverpod_annotation: ^2.3.0

  # 路由
  go_router: ^13.0.0

  # 相机
  camera: ^0.10.5
  image_picker: ^1.0.5

  # 图片加载
  cached_network_image: ^3.3.0

  # UI组件
  shimmer: ^3.0.0

dev_dependencies:
  flutter_test:
    sdk: flutter
  flutter_lints: ^3.0.0
  build_runner: ^2.4.0
  riverpod_generator: ^2.3.0
  go_router_builder: ^2.4.0

flutter:
  generate: true
  uses-material-design: true
```

---

## ✅ 验收标准

完成后需满足:

1. ✅ 所有 UI 组件正常渲染
2. ✅ 6 个页面导航流畅
3. ✅ 亮色/暗色主题切换正常
4. ✅ 6 种语言切换正常
5. ✅ Widget 测试覆盖率 > 75%
6. ✅ `flutter analyze` 无错误
7. ✅ `flutter test` 全部通过
8. ✅ 在 iOS/Android 模拟器上运行正常

---

## 📝 完成后创建报告

创建 `STEP3_UI_DEVELOPMENT_COMPLETION.md`:

```markdown
# Step 3 完成报告

## 交付清单
- [x] 主题系统 (4个文件)
- [x] UI组件库 (15个组件)
- [x] 6个核心页面
- [x] 国际化 (6种语言)
- [x] 路由配置
- [x] Widget测试 (覆盖率 XX%)

## 文件统计
- Dart文件: XX 个
- 测试文件: XX 个
- 国际化文件: 6 个

## 测试结果
- Widget测试: XX/XX 通过
- 覆盖率: XX%

## 截图
(添加关键页面截图)
```

---

**预计总耗时**: 12小时
**建议分配**: 3个工作日，每天4小时

**祝开发顺利！** 🎉
