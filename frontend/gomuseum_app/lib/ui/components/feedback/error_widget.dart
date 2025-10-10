/// GoMuseum 错误状态组件
///
/// 提供统一的错误状态视觉反馈，包括：
/// - 错误图标和消息
/// - 重试按钮
/// - 可自定义的图标和文字
/// - 支持多种错误场景
library;

import 'package:flutter/material.dart';
import '../../../theme/colors.dart';
import '../../../theme/dimensions.dart';
import '../../../theme/typography.dart';

/// 错误状态组件
///
/// 使用示例：
/// ```dart
/// // 1. 基础错误提示
/// AppErrorWidget(
///   message: '加载失败',
///   onRetry: () => loadData(),
/// )
///
/// // 2. 网络错误
/// AppErrorWidget.network(
///   onRetry: () => fetchData(),
/// )
///
/// // 3. 自定义错误
/// AppErrorWidget.custom(
///   icon: Icons.error_outline,
///   title: '出错了',
///   message: '请稍后重试',
///   onRetry: () => retry(),
/// )
///
/// // 4. 无重试按钮的错误提示
/// AppErrorWidget(
///   message: '此功能暂不可用',
/// )
/// ```
class AppErrorWidget extends StatelessWidget {
  /// 错误图标
  final IconData icon;

  /// 错误标题
  final String? title;

  /// 错误消息
  final String message;

  /// 重试回调
  final VoidCallback? onRetry;

  /// 重试按钮文本
  final String retryText;

  /// 图标大小
  final double iconSize;

  /// 图标颜色
  final Color? iconColor;

  const AppErrorWidget({
    super.key,
    this.icon = Icons.error_outline,
    this.title,
    required this.message,
    this.onRetry,
    this.retryText = '重试',
    this.iconSize = 64.0,
    this.iconColor,
  });

  /// 网络错误
  factory AppErrorWidget.network({
    Key? key,
    VoidCallback? onRetry,
    String? message,
  }) {
    return AppErrorWidget(
      key: key,
      icon: Icons.wifi_off,
      title: '网络连接失败',
      message: message ?? '请检查网络设置后重试',
      onRetry: onRetry,
    );
  }

  /// 服务器错误
  factory AppErrorWidget.server({
    Key? key,
    VoidCallback? onRetry,
    String? message,
  }) {
    return AppErrorWidget(
      key: key,
      icon: Icons.cloud_off,
      title: '服务器错误',
      message: message ?? '服务暂时不可用，请稍后重试',
      onRetry: onRetry,
    );
  }

  /// 权限错误
  factory AppErrorWidget.permission({
    Key? key,
    VoidCallback? onRetry,
    String? message,
  }) {
    return AppErrorWidget(
      key: key,
      icon: Icons.lock_outline,
      title: '权限不足',
      message: message ?? '您没有访问此内容的权限',
      onRetry: onRetry,
      retryText: '返回',
    );
  }

  /// 自定义错误
  factory AppErrorWidget.custom({
    Key? key,
    required IconData icon,
    String? title,
    required String message,
    VoidCallback? onRetry,
    String retryText = '重试',
    double iconSize = 64.0,
    Color? iconColor,
  }) {
    return AppErrorWidget(
      key: key,
      icon: icon,
      title: title,
      message: message,
      onRetry: onRetry,
      retryText: retryText,
      iconSize: iconSize,
      iconColor: iconColor,
    );
  }

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    final errorColor = iconColor ?? AppColors.error;

    return Center(
      child: Padding(
        padding: EdgeInsets.all(AppDimensions.spacing24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            // 错误图标
            Container(
              padding: EdgeInsets.all(AppDimensions.spacing16),
              decoration: BoxDecoration(
                color: errorColor.withOpacity(0.1),
                shape: BoxShape.circle,
              ),
              child: Icon(
                icon,
                size: iconSize,
                color: errorColor,
              ),
            ),
            SizedBox(height: AppDimensions.spacing24),

            // 错误标题
            if (title != null) ...[
              Text(
                title!,
                style: AppTypography.lightTextTheme.headlineMedium?.copyWith(
                  color: isDark
                      ? AppColors.textPrimaryDark
                      : AppColors.textPrimaryLight,
                ),
                textAlign: TextAlign.center,
              ),
              SizedBox(height: AppDimensions.spacing8),
            ],

            // 错误消息
            Text(
              message,
              style: AppTypography.lightTextTheme.bodyMedium?.copyWith(
                color: isDark
                    ? AppColors.textSecondaryDark
                    : AppColors.textSecondaryLight,
              ),
              textAlign: TextAlign.center,
            ),

            // 重试按钮
            if (onRetry != null) ...[
              SizedBox(height: AppDimensions.spacing24),
              ElevatedButton.icon(
                onPressed: onRetry,
                icon: Icon(Icons.refresh),
                label: Text(retryText),
                style: ElevatedButton.styleFrom(
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
}

/// 内联错误提示组件
///
/// 适用于表单验证、小范围错误提示等场景
///
/// 使用示例：
/// ```dart
/// InlineErrorWidget(
///   message: '请输入有效的邮箱地址',
/// )
/// ```
class InlineErrorWidget extends StatelessWidget {
  /// 错误消息
  final String message;

  /// 错误图标
  final IconData icon;

  /// 是否显示图标
  final bool showIcon;

  const InlineErrorWidget({
    super.key,
    required this.message,
    this.icon = Icons.error_outline,
    this.showIcon = true,
  });

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;

    return Container(
      padding: EdgeInsets.symmetric(
        horizontal: AppDimensions.spacing12,
        vertical: AppDimensions.spacing8,
      ),
      decoration: BoxDecoration(
        color: AppColors.error.withOpacity(0.1),
        borderRadius: BorderRadius.circular(AppDimensions.radiusSmall),
        border: Border.all(
          color: AppColors.error.withOpacity(0.3),
          width: 1.0,
        ),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          if (showIcon) ...[
            Icon(
              icon,
              size: 16.0,
              color: AppColors.error,
            ),
            SizedBox(width: AppDimensions.spacing8),
          ],
          Flexible(
            child: Text(
              message,
              style: AppTypography.lightTextTheme.bodySmall?.copyWith(
                color: AppColors.error,
              ),
            ),
          ),
        ],
      ),
    );
  }
}

/// 错误横幅组件
///
/// 适用于页面顶部的错误提示条
///
/// 使用示例：
/// ```dart
/// ErrorBanner(
///   message: '同步失败，部分数据可能已过期',
///   onDismiss: () => setState(() => showBanner = false),
///   onAction: () => syncData(),
///   actionLabel: '立即同步',
/// )
/// ```
class ErrorBanner extends StatelessWidget {
  /// 错误消息
  final String message;

  /// 关闭回调
  final VoidCallback? onDismiss;

  /// 操作回调
  final VoidCallback? onAction;

  /// 操作按钮文本
  final String? actionLabel;

  /// 图标
  final IconData icon;

  const ErrorBanner({
    super.key,
    required this.message,
    this.onDismiss,
    this.onAction,
    this.actionLabel,
    this.icon = Icons.warning_amber,
  });

  @override
  Widget build(BuildContext context) {
    return Material(
      color: AppColors.error,
      elevation: 4.0,
      child: SafeArea(
        bottom: false,
        child: Padding(
          padding: EdgeInsets.symmetric(
            horizontal: AppDimensions.spacing16,
            vertical: AppDimensions.spacing12,
          ),
          child: Row(
            children: [
              // 图标
              Icon(
                icon,
                color: Colors.white,
                size: 20.0,
              ),
              SizedBox(width: AppDimensions.spacing12),

              // 消息
              Expanded(
                child: Text(
                  message,
                  style: AppTypography.lightTextTheme.bodySmall?.copyWith(
                    color: Colors.white,
                  ),
                ),
              ),

              // 操作按钮
              if (onAction != null && actionLabel != null) ...[
                SizedBox(width: AppDimensions.spacing8),
                TextButton(
                  onPressed: onAction,
                  style: TextButton.styleFrom(
                    foregroundColor: Colors.white,
                    padding: EdgeInsets.symmetric(
                      horizontal: AppDimensions.spacing12,
                      vertical: AppDimensions.spacing4,
                    ),
                    minimumSize: Size.zero,
                    tapTargetSize: MaterialTapTargetSize.shrinkWrap,
                  ),
                  child: Text(
                    actionLabel!,
                    style: AppTypography.lightTextTheme.labelMedium?.copyWith(
                      color: Colors.white,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                ),
              ],

              // 关闭按钮
              if (onDismiss != null) ...[
                SizedBox(width: AppDimensions.spacing4),
                IconButton(
                  icon: Icon(Icons.close, size: 18.0),
                  color: Colors.white,
                  onPressed: onDismiss,
                  padding: EdgeInsets.zero,
                  constraints: BoxConstraints(),
                  splashRadius: 18.0,
                ),
              ],
            ],
          ),
        ),
      ),
    );
  }
}
