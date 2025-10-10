/// GoMuseum 空状态组件
///
/// 提供统一的空状态视觉反馈，包括：
/// - 空状态图标和提示文字
/// - 可选操作按钮
/// - 支持多种空状态场景
/// - Material 3.0 设计风格
library;

import 'package:flutter/material.dart';
import '../../../theme/colors.dart';
import '../../../theme/dimensions.dart';
import '../../../theme/typography.dart';

/// 空状态组件
///
/// 使用示例：
/// ```dart
/// // 1. 基础空状态
/// AppEmptyStateWidget(
///   icon: Icons.inbox_outlined,
///   title: '暂无内容',
///   message: '这里还没有任何内容',
/// )
///
/// // 2. 带操作按钮的空状态
/// AppEmptyStateWidget(
///   icon: Icons.search_off,
///   title: '未找到结果',
///   message: '请尝试其他关键词',
///   actionLabel: '清除搜索',
///   onAction: () => clearSearch(),
/// )
///
/// // 3. 空历史记录
/// AppEmptyStateWidget.history(
///   onAction: () => startExploring(),
/// )
///
/// // 4. 空收藏
/// AppEmptyStateWidget.favorites(
///   onAction: () => navigateToDiscover(),
/// )
/// ```
class AppEmptyStateWidget extends StatelessWidget {
  /// 图标
  final IconData icon;

  /// 标题
  final String title;

  /// 描述消息
  final String message;

  /// 操作按钮文本
  final String? actionLabel;

  /// 操作按钮回调
  final VoidCallback? onAction;

  /// 图标大小
  final double iconSize;

  /// 图标颜色
  final Color? iconColor;

  /// 自定义插图组件
  final Widget? illustration;

  const AppEmptyStateWidget({
    super.key,
    required this.icon,
    required this.title,
    required this.message,
    this.actionLabel,
    this.onAction,
    this.iconSize = 80.0,
    this.iconColor,
    this.illustration,
  });

  /// 空历史记录
  factory AppEmptyStateWidget.history({
    Key? key,
    String? actionLabel,
    VoidCallback? onAction,
  }) {
    return AppEmptyStateWidget(
      key: key,
      icon: Icons.history,
      title: '暂无历史记录',
      message: '开始探索艺术品，您的浏览记录将显示在这里',
      actionLabel: actionLabel ?? '开始探索',
      onAction: onAction,
    );
  }

  /// 空收藏
  factory AppEmptyStateWidget.favorites({
    Key? key,
    String? actionLabel,
    VoidCallback? onAction,
  }) {
    return AppEmptyStateWidget(
      key: key,
      icon: Icons.favorite_border,
      title: '暂无收藏',
      message: '收藏喜欢的艺术品，方便随时查看',
      actionLabel: actionLabel ?? '去发现',
      onAction: onAction,
    );
  }

  /// 空搜索结果
  factory AppEmptyStateWidget.searchResults({
    Key? key,
    String? searchQuery,
    VoidCallback? onAction,
  }) {
    return AppEmptyStateWidget(
      key: key,
      icon: Icons.search_off,
      title: '未找到相关内容',
      message:
          searchQuery != null ? '没有找到与 "$searchQuery" 相关的结果' : '请尝试使用其他关键词',
      actionLabel: '清除搜索',
      onAction: onAction,
    );
  }

  /// 空识别结果
  factory AppEmptyStateWidget.noRecognition({
    Key? key,
    VoidCallback? onAction,
  }) {
    return AppEmptyStateWidget(
      key: key,
      icon: Icons.image_not_supported_outlined,
      title: '未能识别',
      message: '请确保照片清晰且包含完整的艺术品',
      actionLabel: '重新拍摄',
      onAction: onAction,
    );
  }

  /// 空通知
  factory AppEmptyStateWidget.notifications({
    Key? key,
  }) {
    return AppEmptyStateWidget(
      key: key,
      icon: Icons.notifications_none,
      title: '暂无通知',
      message: '您的所有通知将显示在这里',
    );
  }

  /// 空内容列表
  factory AppEmptyStateWidget.content({
    Key? key,
    String? contentType,
    VoidCallback? onAction,
  }) {
    return AppEmptyStateWidget(
      key: key,
      icon: Icons.inbox_outlined,
      title: '暂无${contentType ?? "内容"}',
      message: '这里还没有任何${contentType ?? "内容"}',
      actionLabel: onAction != null ? '刷新' : null,
      onAction: onAction,
    );
  }

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    final emptyIconColor = iconColor ??
        (isDark ? AppColors.textSecondaryDark : AppColors.textSecondaryLight);

    return Center(
      child: Padding(
        padding: EdgeInsets.all(AppDimensions.spacing24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            // 自定义插图或图标
            if (illustration != null)
              illustration!
            else
              Container(
                padding: EdgeInsets.all(AppDimensions.spacing24),
                decoration: BoxDecoration(
                  color: emptyIconColor.withOpacity(0.1),
                  shape: BoxShape.circle,
                ),
                child: Icon(
                  icon,
                  size: iconSize,
                  color: emptyIconColor,
                ),
              ),

            SizedBox(height: AppDimensions.spacing24),

            // 标题
            Text(
              title,
              style: AppTypography.lightTextTheme.headlineMedium?.copyWith(
                color: isDark
                    ? AppColors.textPrimaryDark
                    : AppColors.textPrimaryLight,
              ),
              textAlign: TextAlign.center,
            ),

            SizedBox(height: AppDimensions.spacing8),

            // 描述
            Text(
              message,
              style: AppTypography.lightTextTheme.bodyMedium?.copyWith(
                color: isDark
                    ? AppColors.textSecondaryDark
                    : AppColors.textSecondaryLight,
              ),
              textAlign: TextAlign.center,
            ),

            // 操作按钮
            if (actionLabel != null && onAction != null) ...[
              SizedBox(height: AppDimensions.spacing24),
              FilledButton.icon(
                onPressed: onAction,
                icon: Icon(_getActionIcon()),
                label: Text(actionLabel!),
                style: FilledButton.styleFrom(
                  backgroundColor: AppColors.primary,
                  foregroundColor: Colors.white,
                  padding: EdgeInsets.symmetric(
                    horizontal: AppDimensions.spacing24,
                    vertical: AppDimensions.spacing12,
                  ),
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(
                      AppDimensions.radiusMedium,
                    ),
                  ),
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }

  /// 根据操作文本获取合适的图标
  IconData _getActionIcon() {
    if (actionLabel == null) return Icons.add;

    final label = actionLabel!.toLowerCase();
    if (label.contains('刷新') || label.contains('重试')) {
      return Icons.refresh;
    } else if (label.contains('搜索') || label.contains('查找')) {
      return Icons.search;
    } else if (label.contains('添加') || label.contains('创建')) {
      return Icons.add;
    } else if (label.contains('探索') || label.contains('发现')) {
      return Icons.explore;
    } else if (label.contains('拍摄') || label.contains('相机')) {
      return Icons.camera_alt;
    } else {
      return Icons.arrow_forward;
    }
  }
}

/// 空状态列表占位组件
///
/// 适用于嵌入到列表中的空状态提示
///
/// 使用示例：
/// ```dart
/// ListView.builder(
///   itemCount: items.isEmpty ? 1 : items.length,
///   itemBuilder: (context, index) {
///     if (items.isEmpty) {
///       return EmptyListPlaceholder(
///         message: '暂无数据',
///       );
///     }
///     return YourListItem(items[index]);
///   },
/// )
/// ```
class EmptyListPlaceholder extends StatelessWidget {
  /// 提示消息
  final String message;

  /// 图标
  final IconData icon;

  /// 高度
  final double? height;

  const EmptyListPlaceholder({
    super.key,
    required this.message,
    this.icon = Icons.inbox_outlined,
    this.height,
  });

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;

    return Container(
      height: height ?? 200,
      alignment: Alignment.center,
      padding: EdgeInsets.all(AppDimensions.spacing24),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(
            icon,
            size: 48.0,
            color: isDark
                ? AppColors.textSecondaryDark
                : AppColors.textSecondaryLight,
          ),
          SizedBox(height: AppDimensions.spacing12),
          Text(
            message,
            style: AppTypography.lightTextTheme.bodyMedium?.copyWith(
              color: isDark
                  ? AppColors.textSecondaryDark
                  : AppColors.textSecondaryLight,
            ),
            textAlign: TextAlign.center,
          ),
        ],
      ),
    );
  }
}

/// 空网格占位组件
///
/// 适用于网格布局的空状态
///
/// 使用示例：
/// ```dart
/// GridView.builder(
///   itemCount: items.isEmpty ? 1 : items.length,
///   gridDelegate: SliverGridDelegateWithFixedCrossAxisCount(
///     crossAxisCount: 2,
///   ),
///   itemBuilder: (context, index) {
///     if (items.isEmpty) {
///       return EmptyGridPlaceholder(
///         message: '暂无艺术品',
///         onAction: () => refresh(),
///       );
///     }
///     return YourGridItem(items[index]);
///   },
/// )
/// ```
class EmptyGridPlaceholder extends StatelessWidget {
  /// 提示消息
  final String message;

  /// 图标
  final IconData icon;

  /// 操作回调
  final VoidCallback? onAction;

  /// 操作按钮文本
  final String? actionLabel;

  const EmptyGridPlaceholder({
    super.key,
    required this.message,
    this.icon = Icons.grid_view,
    this.onAction,
    this.actionLabel,
  });

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;

    return Container(
      alignment: Alignment.center,
      padding: EdgeInsets.all(AppDimensions.spacing16),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(
            icon,
            size: 48.0,
            color: isDark
                ? AppColors.textSecondaryDark
                : AppColors.textSecondaryLight,
          ),
          SizedBox(height: AppDimensions.spacing12),
          Text(
            message,
            style: AppTypography.lightTextTheme.bodySmall?.copyWith(
              color: isDark
                  ? AppColors.textSecondaryDark
                  : AppColors.textSecondaryLight,
            ),
            textAlign: TextAlign.center,
            maxLines: 2,
            overflow: TextOverflow.ellipsis,
          ),
          if (onAction != null && actionLabel != null) ...[
            SizedBox(height: AppDimensions.spacing8),
            TextButton(
              onPressed: onAction,
              style: TextButton.styleFrom(
                foregroundColor: AppColors.primary,
                padding: EdgeInsets.symmetric(
                  horizontal: AppDimensions.spacing12,
                  vertical: AppDimensions.spacing4,
                ),
                minimumSize: Size.zero,
                tapTargetSize: MaterialTapTargetSize.shrinkWrap,
              ),
              child: Text(
                actionLabel!,
                style: AppTypography.lightTextTheme.labelSmall?.copyWith(
                  color: AppColors.primary,
                  fontWeight: FontWeight.bold,
                ),
              ),
            ),
          ],
        ],
      ),
    );
  }
}
