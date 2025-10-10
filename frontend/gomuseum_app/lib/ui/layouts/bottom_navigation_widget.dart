/// GoMuseum 底部导航栏组件
///
/// 提供统一的底部导航体验，符合 Material Design 3.0 规范
library;

import 'package:flutter/material.dart';
import 'package:gomuseum_app/theme/colors.dart';
import 'package:gomuseum_app/theme/dimensions.dart';

/// 底部导航项数据模型
class BottomNavItem {
  /// 图标
  final IconData icon;

  /// 选中时的图标（可选，不提供则使用 icon）
  final IconData? selectedIcon;

  /// 标签文本
  final String label;

  /// 路由名称（可选）
  final String? routeName;

  const BottomNavItem({
    required this.icon,
    this.selectedIcon,
    required this.label,
    this.routeName,
  });
}

/// 底部导航栏组件
///
/// 功能特性:
/// - 4个导航项: Home / Explore / History / Settings
/// - 使用 AppColors.primary 作为选中颜色
/// - Material 3.0 样式
/// - 支持页面切换回调
///
/// 使用示例:
/// ```dart
/// AppBottomNavigation(
///   currentIndex: 0,
///   onTap: (index) {
///     setState(() {
///       _currentIndex = index;
///     });
///   },
/// )
/// ```
class AppBottomNavigation extends StatelessWidget {
  /// 当前选中的索引
  final int currentIndex;

  /// 点击回调
  final ValueChanged<int>? onTap;

  /// 是否显示标签
  final bool showLabels;

  /// 自定义导航项（可选，不提供则使用默认的4个导航项）
  final List<BottomNavItem>? items;

  /// 背景颜色
  final Color? backgroundColor;

  /// 选中颜色
  final Color? selectedItemColor;

  /// 未选中颜色
  final Color? unselectedItemColor;

  const AppBottomNavigation({
    super.key,
    required this.currentIndex,
    this.onTap,
    this.showLabels = true,
    this.items,
    this.backgroundColor,
    this.selectedItemColor,
    this.unselectedItemColor,
  });

  /// 默认导航项配置
  static const List<BottomNavItem> defaultItems = [
    BottomNavItem(
      icon: Icons.home_outlined,
      selectedIcon: Icons.home,
      label: '首页',
      routeName: '/home',
    ),
    BottomNavItem(
      icon: Icons.explore_outlined,
      selectedIcon: Icons.explore,
      label: '探索',
      routeName: '/explore',
    ),
    BottomNavItem(
      icon: Icons.history_outlined,
      selectedIcon: Icons.history,
      label: '历史',
      routeName: '/history',
    ),
    BottomNavItem(
      icon: Icons.settings_outlined,
      selectedIcon: Icons.settings,
      label: '设置',
      routeName: '/settings',
    ),
  ];

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final isDark = theme.brightness == Brightness.dark;
    final navItems = items ?? defaultItems;

    return Container(
      decoration: BoxDecoration(
        color: backgroundColor ??
            (isDark ? AppColors.surfaceDark : AppColors.backgroundLight),
        boxShadow: [
          BoxShadow(
            color: isDark ? AppColors.shadowDark : AppColors.shadowLight,
            offset: const Offset(0, -2),
            blurRadius: 8,
          ),
        ],
      ),
      child: SafeArea(
        child: SizedBox(
          height: AppDimensions.bottomNavHeight,
          child: NavigationBar(
            selectedIndex: currentIndex,
            onDestinationSelected: onTap,
            backgroundColor: Colors.transparent,
            elevation: 0,
            labelBehavior: showLabels
                ? NavigationDestinationLabelBehavior.alwaysShow
                : NavigationDestinationLabelBehavior.onlyShowSelected,
            indicatorColor: (selectedItemColor ?? AppColors.primary)
                .withValues(alpha: 0.12),
            destinations: navItems.map((item) {
              return NavigationDestination(
                icon: Icon(item.icon),
                selectedIcon: Icon(item.selectedIcon ?? item.icon),
                label: item.label,
              );
            }).toList(),
          ),
        ),
      ),
    );
  }
}

/// Material 2 风格的底部导航栏
///
/// 使用 BottomNavigationBar 实现，适用于需要经典样式的场景
///
/// 使用示例:
/// ```dart
/// ClassicBottomNavigation(
///   currentIndex: 0,
///   onTap: (index) {
///     setState(() {
///       _currentIndex = index;
///     });
///   },
/// )
/// ```
class ClassicBottomNavigation extends StatelessWidget {
  /// 当前选中的索引
  final int currentIndex;

  /// 点击回调
  final ValueChanged<int>? onTap;

  /// 自定义导航项
  final List<BottomNavItem>? items;

  /// 背景颜色
  final Color? backgroundColor;

  /// 选中颜色
  final Color? selectedItemColor;

  /// 未选中颜色
  final Color? unselectedItemColor;

  /// 导航栏类型
  final BottomNavigationBarType? type;

  const ClassicBottomNavigation({
    super.key,
    required this.currentIndex,
    this.onTap,
    this.items,
    this.backgroundColor,
    this.selectedItemColor,
    this.unselectedItemColor,
    this.type,
  });

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final isDark = theme.brightness == Brightness.dark;
    final navItems = items ?? AppBottomNavigation.defaultItems;

    return Container(
      decoration: BoxDecoration(
        boxShadow: [
          BoxShadow(
            color: isDark ? AppColors.shadowDark : AppColors.shadowLight,
            offset: const Offset(0, -2),
            blurRadius: 8,
          ),
        ],
      ),
      child: BottomNavigationBar(
        currentIndex: currentIndex,
        onTap: onTap,
        backgroundColor: backgroundColor ??
            (isDark ? AppColors.surfaceDark : AppColors.backgroundLight),
        selectedItemColor: selectedItemColor ?? AppColors.primary,
        unselectedItemColor: unselectedItemColor ??
            (isDark
                ? AppColors.textSecondaryDark
                : AppColors.textSecondaryLight),
        type: type ?? BottomNavigationBarType.fixed,
        elevation: 8,
        selectedFontSize: 12,
        unselectedFontSize: 12,
        items: navItems.map((item) {
          return BottomNavigationBarItem(
            icon: Icon(item.icon, size: AppDimensions.iconSize),
            activeIcon: Icon(item.selectedIcon ?? item.icon,
                size: AppDimensions.iconSize),
            label: item.label,
          );
        }).toList(),
      ),
    );
  }
}

/// 浮动样式的底部导航栏
///
/// 带有圆角和内边距的现代化导航栏样式
///
/// 使用示例:
/// ```dart
/// FloatingBottomNavigation(
///   currentIndex: 0,
///   onTap: (index) {
///     setState(() {
///       _currentIndex = index;
///     });
///   },
/// )
/// ```
class FloatingBottomNavigation extends StatelessWidget {
  /// 当前选中的索引
  final int currentIndex;

  /// 点击回调
  final ValueChanged<int>? onTap;

  /// 自定义导航项
  final List<BottomNavItem>? items;

  /// 背景颜色
  final Color? backgroundColor;

  /// 选中颜色
  final Color? selectedItemColor;

  /// 左右边距
  final double horizontalMargin;

  /// 底部边距
  final double bottomMargin;

  const FloatingBottomNavigation({
    super.key,
    required this.currentIndex,
    this.onTap,
    this.items,
    this.backgroundColor,
    this.selectedItemColor,
    this.horizontalMargin = AppDimensions.spacing16,
    this.bottomMargin = AppDimensions.spacing16,
  });

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final isDark = theme.brightness == Brightness.dark;
    final navItems = items ?? AppBottomNavigation.defaultItems;

    return Padding(
      padding: EdgeInsets.only(
        left: horizontalMargin,
        right: horizontalMargin,
        bottom: bottomMargin,
      ),
      child: Container(
        height: AppDimensions.bottomNavHeight,
        decoration: BoxDecoration(
          color: backgroundColor ??
              (isDark ? AppColors.surfaceDark : AppColors.backgroundLight),
          borderRadius: BorderRadius.circular(AppDimensions.radiusLarge),
          boxShadow: [
            BoxShadow(
              color: isDark ? AppColors.shadowDark : AppColors.shadowLight,
              offset: const Offset(0, 4),
              blurRadius: 12,
              spreadRadius: 0,
            ),
          ],
        ),
        child: NavigationBar(
          selectedIndex: currentIndex,
          onDestinationSelected: onTap,
          backgroundColor: Colors.transparent,
          elevation: 0,
          indicatorColor:
              (selectedItemColor ?? AppColors.primary).withValues(alpha: 0.12),
          destinations: navItems.map((item) {
            return NavigationDestination(
              icon: Icon(item.icon),
              selectedIcon: Icon(item.selectedIcon ?? item.icon),
              label: item.label,
            );
          }).toList(),
        ),
      ),
    );
  }
}
