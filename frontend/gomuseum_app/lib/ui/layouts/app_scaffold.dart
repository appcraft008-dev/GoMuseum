/// GoMuseum 统一页面容器组件
///
/// 提供一致的页面布局结构，集成 AppBar 和底部导航
library;

import 'package:flutter/material.dart';
import 'package:gomuseum_app/ui/layouts/app_bar_widget.dart';
import 'package:gomuseum_app/ui/layouts/bottom_navigation_widget.dart';
import 'package:gomuseum_app/theme/colors.dart';
import 'package:gomuseum_app/theme/dimensions.dart';

/// 页面容器配置类
class ScaffoldConfig {
  /// 是否显示 AppBar
  final bool showAppBar;

  /// 是否显示底部导航
  final bool showBottomNav;

  /// 是否启用安全区域
  final bool useSafeArea;

  /// 是否可调整大小以避开键盘
  final bool resizeToAvoidBottomInset;

  /// 背景颜色
  final Color? backgroundColor;

  const ScaffoldConfig({
    this.showAppBar = true,
    this.showBottomNav = false,
    this.useSafeArea = true,
    this.resizeToAvoidBottomInset = true,
    this.backgroundColor,
  });
}

/// 统一的页面容器组件
///
/// 功能特性:
/// - 集成 AppBar 和 BottomNavigationBar
/// - 支持 FloatingActionButton
/// - 支持自定义 body 内容
/// - Material 3.0 样式
///
/// 使用示例:
/// ```dart
/// AppScaffold(
///   title: '博物馆列表',
///   body: MuseumListView(),
///   showBottomNav: true,
///   currentNavIndex: 0,
///   onNavTap: (index) {
///     // 处理导航切换
///   },
/// )
/// ```
class AppScaffold extends StatelessWidget {
  /// 页面标题
  final String? title;

  /// 标题 Widget（优先于 title）
  final Widget? titleWidget;

  /// 页面主体内容
  final Widget body;

  /// 是否显示 AppBar
  final bool showAppBar;

  /// 自定义 AppBar
  final PreferredSizeWidget? appBar;

  /// 是否显示返回按钮
  final bool showBackButton;

  /// AppBar 左侧 Widget
  final Widget? leading;

  /// AppBar 右侧操作按钮
  final List<Widget>? actions;

  /// 是否显示底部导航
  final bool showBottomNav;

  /// 当前导航索引
  final int currentNavIndex;

  /// 导航点击回调
  final ValueChanged<int>? onNavTap;

  /// 自定义底部导航项
  final List<BottomNavItem>? navItems;

  /// 自定义底部导航栏
  final Widget? bottomNavigationBar;

  /// 悬浮操作按钮
  final Widget? floatingActionButton;

  /// 悬浮按钮位置
  final FloatingActionButtonLocation? floatingActionButtonLocation;

  /// 抽屉菜单
  final Widget? drawer;

  /// 右侧抽屉
  final Widget? endDrawer;

  /// 底部 Sheet
  final Widget? bottomSheet;

  /// 背景颜色
  final Color? backgroundColor;

  /// 是否启用安全区域
  final bool useSafeArea;

  /// 是否可调整大小以避开键盘
  final bool resizeToAvoidBottomInset;

  /// AppBar 是否透明
  final bool transparentAppBar;

  /// 是否扩展 body 到 AppBar 下方
  final bool extendBodyBehindAppBar;

  const AppScaffold({
    super.key,
    this.title,
    this.titleWidget,
    required this.body,
    this.showAppBar = true,
    this.appBar,
    this.showBackButton = true,
    this.leading,
    this.actions,
    this.showBottomNav = false,
    this.currentNavIndex = 0,
    this.onNavTap,
    this.navItems,
    this.bottomNavigationBar,
    this.floatingActionButton,
    this.floatingActionButtonLocation,
    this.drawer,
    this.endDrawer,
    this.bottomSheet,
    this.backgroundColor,
    this.useSafeArea = true,
    this.resizeToAvoidBottomInset = true,
    this.transparentAppBar = false,
    this.extendBodyBehindAppBar = false,
  });

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final isDark = theme.brightness == Brightness.dark;

    // 构建 AppBar
    PreferredSizeWidget? effectiveAppBar;
    if (showAppBar) {
      effectiveAppBar = appBar ??
          CustomAppBar(
            title: title,
            titleWidget: titleWidget,
            showBackButton: showBackButton,
            leading: leading,
            actions: actions,
            transparent: transparentAppBar,
          );
    }

    // 构建底部导航栏
    Widget? effectiveBottomNav;
    if (showBottomNav) {
      effectiveBottomNav = bottomNavigationBar ??
          AppBottomNavigation(
            currentIndex: currentNavIndex,
            onTap: onNavTap,
            items: navItems,
          );
    }

    // 构建 body
    Widget effectiveBody = body;
    if (useSafeArea) {
      effectiveBody = SafeArea(
        child: body,
      );
    }

    return Scaffold(
      appBar: effectiveAppBar,
      body: effectiveBody,
      bottomNavigationBar: effectiveBottomNav,
      floatingActionButton: floatingActionButton,
      floatingActionButtonLocation: floatingActionButtonLocation,
      drawer: drawer,
      endDrawer: endDrawer,
      bottomSheet: bottomSheet,
      backgroundColor: backgroundColor ??
          (isDark ? AppColors.backgroundDark : AppColors.backgroundLight),
      resizeToAvoidBottomInset: resizeToAvoidBottomInset,
      extendBodyBehindAppBar: extendBodyBehindAppBar,
    );
  }
}

/// 带渐变背景的页面容器
///
/// 适用于首页或特殊页面，提供渐变背景效果
///
/// 使用示例:
/// ```dart
/// GradientScaffold(
///   gradient: AppColors.primaryGradient,
///   body: HomeContent(),
/// )
/// ```
class GradientScaffold extends StatelessWidget {
  /// 页面主体内容
  final Widget body;

  /// 渐变背景
  final Gradient gradient;

  /// 是否显示 AppBar
  final bool showAppBar;

  /// 自定义 AppBar
  final PreferredSizeWidget? appBar;

  /// 页面标题
  final String? title;

  /// AppBar 右侧操作
  final List<Widget>? actions;

  /// 是否显示返回按钮
  final bool showBackButton;

  /// 底部导航栏
  final Widget? bottomNavigationBar;

  /// 悬浮操作按钮
  final Widget? floatingActionButton;

  /// 是否启用安全区域
  final bool useSafeArea;

  const GradientScaffold({
    super.key,
    required this.body,
    this.gradient = AppColors.primaryGradient,
    this.showAppBar = true,
    this.appBar,
    this.title,
    this.actions,
    this.showBackButton = false,
    this.bottomNavigationBar,
    this.floatingActionButton,
    this.useSafeArea = true,
  });

  @override
  Widget build(BuildContext context) {
    // 构建 AppBar
    PreferredSizeWidget? effectiveAppBar;
    if (showAppBar) {
      effectiveAppBar = appBar ??
          GradientAppBar(
            title: title,
            gradient: gradient,
            actions: actions,
            showBackButton: showBackButton,
          );
    }

    // 构建 body
    Widget effectiveBody = body;
    if (useSafeArea) {
      effectiveBody = SafeArea(child: body);
    }

    return Scaffold(
      extendBodyBehindAppBar: true,
      appBar: effectiveAppBar,
      body: Container(
        decoration: BoxDecoration(gradient: gradient),
        child: effectiveBody,
      ),
      bottomNavigationBar: bottomNavigationBar,
      floatingActionButton: floatingActionButton,
    );
  }
}

/// 可滚动页面容器
///
/// 带有下拉刷新功能的滚动页面容器
///
/// 使用示例:
/// ```dart
/// ScrollableScaffold(
///   title: '博物馆列表',
///   onRefresh: () async {
///     await loadData();
///   },
///   children: [
///     MuseumCard(),
///     MuseumCard(),
///   ],
/// )
/// ```
class ScrollableScaffold extends StatelessWidget {
  /// 页面标题
  final String? title;

  /// 自定义 AppBar
  final PreferredSizeWidget? appBar;

  /// 子组件列表
  final List<Widget> children;

  /// 下拉刷新回调
  final Future<void> Function()? onRefresh;

  /// 是否显示返回按钮
  final bool showBackButton;

  /// AppBar 右侧操作
  final List<Widget>? actions;

  /// 底部导航栏
  final Widget? bottomNavigationBar;

  /// 内边距
  final EdgeInsets? padding;

  /// 背景颜色
  final Color? backgroundColor;

  /// 滚动控制器
  final ScrollController? controller;

  const ScrollableScaffold({
    super.key,
    this.title,
    this.appBar,
    required this.children,
    this.onRefresh,
    this.showBackButton = true,
    this.actions,
    this.bottomNavigationBar,
    this.padding,
    this.backgroundColor,
    this.controller,
  });

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final isDark = theme.brightness == Brightness.dark;

    // 构建滚动内容
    Widget scrollContent = ListView(
      controller: controller,
      padding:
          padding ?? const EdgeInsets.all(AppDimensions.pageHorizontalPadding),
      children: children,
    );

    // 如果有刷新回调，包裹 RefreshIndicator
    if (onRefresh != null) {
      scrollContent = RefreshIndicator(
        onRefresh: onRefresh!,
        color: AppColors.primary,
        child: scrollContent,
      );
    }

    return AppScaffold(
      title: title,
      appBar: appBar,
      showBackButton: showBackButton,
      actions: actions,
      body: scrollContent,
      bottomNavigationBar: bottomNavigationBar,
      backgroundColor: backgroundColor ??
          (isDark ? AppColors.backgroundDark : AppColors.backgroundLight),
    );
  }
}

/// 标签页容器
///
/// 支持顶部标签切换的页面容器
///
/// 使用示例:
/// ```dart
/// TabScaffold(
///   title: '展览',
///   tabs: ['进行中', '即将开始', '已结束'],
///   tabViews: [
///     OngoingExhibitions(),
///     UpcomingExhibitions(),
///     PastExhibitions(),
///   ],
/// )
/// ```
class TabScaffold extends StatelessWidget {
  /// 页面标题
  final String? title;

  /// 标签列表
  final List<String> tabs;

  /// 标签对应的视图
  final List<Widget> tabViews;

  /// 是否显示返回按钮
  final bool showBackButton;

  /// AppBar 右侧操作
  final List<Widget>? actions;

  /// 底部导航栏
  final Widget? bottomNavigationBar;

  /// 标签控制器
  final TabController? controller;

  /// 标签指示器颜色
  final Color? indicatorColor;

  const TabScaffold({
    super.key,
    this.title,
    required this.tabs,
    required this.tabViews,
    this.showBackButton = true,
    this.actions,
    this.bottomNavigationBar,
    this.controller,
    this.indicatorColor,
  }) : assert(tabs.length == tabViews.length, '标签数量必须与视图数量相同');

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return DefaultTabController(
      length: tabs.length,
      child: AppScaffold(
        title: title,
        showBackButton: showBackButton,
        actions: actions,
        appBar: PreferredSize(
          preferredSize: const Size.fromHeight(kToolbarHeight + 48),
          child: Column(
            children: [
              CustomAppBar(
                title: title,
                showBackButton: showBackButton,
                actions: actions,
              ),
              TabBar(
                controller: controller,
                tabs: tabs.map((tab) => Tab(text: tab)).toList(),
                indicatorColor: indicatorColor ?? AppColors.primary,
                labelColor: theme.colorScheme.primary,
                unselectedLabelColor: theme.textTheme.bodyMedium?.color,
              ),
            ],
          ),
        ),
        body: TabBarView(
          controller: controller,
          children: tabViews,
        ),
        bottomNavigationBar: bottomNavigationBar,
      ),
    );
  }
}
