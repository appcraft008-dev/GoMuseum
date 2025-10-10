/// GoMuseum 自定义 AppBar 组件
///
/// 提供统一的顶部导航栏样式，支持高度自定义
/// 符合 Material Design 3.0 规范
library;

import 'package:flutter/material.dart';
import 'package:gomuseum_app/theme/colors.dart';
import 'package:gomuseum_app/theme/dimensions.dart';

/// 自定义 AppBar 组件
///
/// 功能特性:
/// - 支持返回按钮/标题/操作按钮
/// - 支持透明背景
/// - Material 3.0 样式
/// - 高度自定义
///
/// 使用示例:
/// ```dart
/// CustomAppBar(
///   title: '博物馆详情',
///   showBackButton: true,
///   actions: [
///     IconButton(
///       icon: Icon(Icons.share),
///       onPressed: () {},
///     ),
///   ],
/// )
/// ```
class CustomAppBar extends StatelessWidget implements PreferredSizeWidget {
  /// 标题文本
  final String? title;

  /// 标题 Widget（优先于 title 使用）
  final Widget? titleWidget;

  /// 是否显示返回按钮
  final bool showBackButton;

  /// 自定义返回按钮
  final Widget? leading;

  /// 右侧操作按钮列表
  final List<Widget>? actions;

  /// 是否使用透明背景
  final bool transparent;

  /// 自定义背景颜色
  final Color? backgroundColor;

  /// 标题是否居中
  final bool centerTitle;

  /// 高度
  final double? elevation;

  /// 返回按钮点击回调
  final VoidCallback? onBackPressed;

  /// AppBar 高度
  final double height;

  const CustomAppBar({
    super.key,
    this.title,
    this.titleWidget,
    this.showBackButton = true,
    this.leading,
    this.actions,
    this.transparent = false,
    this.backgroundColor,
    this.centerTitle = true,
    this.elevation,
    this.onBackPressed,
    this.height = kToolbarHeight,
  });

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final colorScheme = theme.colorScheme;
    final isDark = theme.brightness == Brightness.dark;

    // 确定背景颜色
    final Color effectiveBackgroundColor = transparent
        ? Colors.transparent
        : (backgroundColor ??
            (isDark ? AppColors.surfaceDark : AppColors.backgroundLight));

    // 确定前景颜色（文字/图标颜色）
    final Color foregroundColor = transparent
        ? Colors.white
        : (isDark ? AppColors.textPrimaryDark : AppColors.textPrimaryLight);

    // 构建标题 Widget
    Widget? titleContent;
    if (titleWidget != null) {
      titleContent = titleWidget;
    } else if (title != null) {
      titleContent = Text(
        title!,
        style: theme.textTheme.titleLarge?.copyWith(
          color: foregroundColor,
          fontWeight: FontWeight.w600,
        ),
      );
    }

    // 构建 leading Widget
    Widget? leadingWidget;
    if (leading != null) {
      leadingWidget = leading;
    } else if (showBackButton) {
      leadingWidget = IconButton(
        icon: Icon(
          Icons.arrow_back_ios_new,
          color: foregroundColor,
          size: AppDimensions.iconSize,
        ),
        onPressed: onBackPressed ?? () => Navigator.of(context).pop(),
        tooltip: MaterialLocalizations.of(context).backButtonTooltip,
      );
    }

    return AppBar(
      leading: leadingWidget,
      title: titleContent,
      centerTitle: centerTitle,
      actions: actions,
      backgroundColor: effectiveBackgroundColor,
      foregroundColor: foregroundColor,
      elevation: elevation ?? (transparent ? 0 : 1),
      scrolledUnderElevation: transparent ? 0 : 3,
      toolbarHeight: height,
      // Material 3.0 样式配置
      surfaceTintColor: transparent ? Colors.transparent : colorScheme.primary,
      shadowColor: transparent
          ? Colors.transparent
          : (isDark ? AppColors.shadowDark : AppColors.shadowLight),
    );
  }

  @override
  Size get preferredSize => Size.fromHeight(height);
}

/// 渐变背景 AppBar
///
/// 带有渐变背景效果的 AppBar，常用于首页或特殊页面
///
/// 使用示例:
/// ```dart
/// GradientAppBar(
///   title: 'GoMuseum',
///   gradient: AppColors.primaryGradient,
/// )
/// ```
class GradientAppBar extends StatelessWidget implements PreferredSizeWidget {
  /// 标题
  final String? title;

  /// 标题 Widget
  final Widget? titleWidget;

  /// 渐变
  final Gradient gradient;

  /// 右侧操作按钮
  final List<Widget>? actions;

  /// 是否显示返回按钮
  final bool showBackButton;

  /// 标题是否居中
  final bool centerTitle;

  /// AppBar 高度
  final double height;

  const GradientAppBar({
    super.key,
    this.title,
    this.titleWidget,
    this.gradient = AppColors.primaryGradient,
    this.actions,
    this.showBackButton = false,
    this.centerTitle = true,
    this.height = kToolbarHeight,
  });

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    // 构建标题 Widget
    Widget? titleContent;
    if (titleWidget != null) {
      titleContent = titleWidget;
    } else if (title != null) {
      titleContent = Text(
        title!,
        style: theme.textTheme.titleLarge?.copyWith(
          color: Colors.white,
          fontWeight: FontWeight.bold,
        ),
      );
    }

    return Container(
      decoration: BoxDecoration(
        gradient: gradient,
      ),
      child: AppBar(
        leading: showBackButton
            ? IconButton(
                icon: const Icon(
                  Icons.arrow_back_ios_new,
                  color: Colors.white,
                  size: AppDimensions.iconSize,
                ),
                onPressed: () => Navigator.of(context).pop(),
              )
            : null,
        title: titleContent,
        centerTitle: centerTitle,
        actions: actions,
        backgroundColor: Colors.transparent,
        foregroundColor: Colors.white,
        elevation: 0,
        scrolledUnderElevation: 0,
        toolbarHeight: height,
      ),
    );
  }

  @override
  Size get preferredSize => Size.fromHeight(height);
}

/// 搜索 AppBar
///
/// 带搜索框的 AppBar，用于搜索场景
///
/// 使用示例:
/// ```dart
/// SearchAppBar(
///   hintText: '搜索博物馆、艺术品...',
///   onSearch: (query) {
///     print('搜索: $query');
///   },
/// )
/// ```
class SearchAppBar extends StatelessWidget implements PreferredSizeWidget {
  /// 搜索提示文本
  final String hintText;

  /// 搜索回调
  final ValueChanged<String>? onSearch;

  /// 搜索输入框控制器
  final TextEditingController? controller;

  /// 是否自动聚焦
  final bool autofocus;

  /// 右侧操作按钮
  final List<Widget>? actions;

  /// AppBar 高度
  final double height;

  const SearchAppBar({
    super.key,
    this.hintText = '搜索...',
    this.onSearch,
    this.controller,
    this.autofocus = false,
    this.actions,
    this.height = kToolbarHeight,
  });

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final isDark = theme.brightness == Brightness.dark;

    return AppBar(
      leading: IconButton(
        icon: const Icon(Icons.arrow_back_ios_new),
        onPressed: () => Navigator.of(context).pop(),
      ),
      title: TextField(
        controller: controller,
        autofocus: autofocus,
        onSubmitted: onSearch,
        style: theme.textTheme.bodyLarge?.copyWith(
          color:
              isDark ? AppColors.textPrimaryDark : AppColors.textPrimaryLight,
        ),
        decoration: InputDecoration(
          hintText: hintText,
          hintStyle: theme.textTheme.bodyLarge?.copyWith(
            color: isDark
                ? AppColors.textSecondaryDark
                : AppColors.textSecondaryLight,
          ),
          border: InputBorder.none,
          contentPadding: EdgeInsets.zero,
        ),
      ),
      actions: actions ??
          [
            if (controller?.text.isNotEmpty ?? false)
              IconButton(
                icon: const Icon(Icons.clear),
                onPressed: () => controller?.clear(),
              ),
          ],
      toolbarHeight: height,
    );
  }

  @override
  Size get preferredSize => Size.fromHeight(height);
}
