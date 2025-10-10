/// GoMuseum 加载状态组件
///
/// 提供多种加载状态的视觉反馈，包括：
/// - 圆形进度条 (CircularProgressIndicator)
/// - Shimmer 骨架屏效果
/// - 自定义加载动画
/// - 支持加载文本提示
library;

import 'package:flutter/material.dart';
import '../../../theme/colors.dart';
import '../../../theme/dimensions.dart';
import '../../../theme/typography.dart';

/// 加载状态组件
///
/// 使用示例：
/// ```dart
/// // 1. 基础圆形加载
/// AppLoadingWidget()
///
/// // 2. 带提示文字的加载
/// AppLoadingWidget.withText('加载中...')
///
/// // 3. 全屏加载遮罩
/// AppLoadingWidget.fullScreen(message: '正在识别艺术品...')
///
/// // 4. Shimmer 骨架屏
/// AppLoadingWidget.shimmer(
///   width: double.infinity,
///   height: 200,
/// )
/// ```
class AppLoadingWidget extends StatelessWidget {
  /// 加载提示文字
  final String? message;

  /// 是否全屏显示
  final bool isFullScreen;

  /// 加载指示器大小
  final double size;

  /// 加载指示器颜色
  final Color? color;

  const AppLoadingWidget({
    super.key,
    this.message,
    this.isFullScreen = false,
    this.size = 40.0,
    this.color,
  });

  /// 带文字提示的加载组件
  factory AppLoadingWidget.withText(
    String message, {
    Key? key,
    double size = 40.0,
    Color? color,
  }) {
    return AppLoadingWidget(
      key: key,
      message: message,
      size: size,
      color: color,
    );
  }

  /// 全屏加载遮罩
  factory AppLoadingWidget.fullScreen({
    Key? key,
    String? message,
    Color? color,
  }) {
    return AppLoadingWidget(
      key: key,
      message: message,
      isFullScreen: true,
      color: color,
    );
  }

  @override
  Widget build(BuildContext context) {
    final indicatorColor = color ?? AppColors.primary;

    final Widget loadingContent = Column(
      mainAxisSize: MainAxisSize.min,
      mainAxisAlignment: MainAxisAlignment.center,
      children: [
        SizedBox(
          width: size,
          height: size,
          child: CircularProgressIndicator(
            valueColor: AlwaysStoppedAnimation<Color>(indicatorColor),
            strokeWidth: 3.0,
          ),
        ),
        if (message != null) ...[
          SizedBox(height: AppDimensions.spacing16),
          Text(
            message!,
            style: AppTypography.lightTextTheme.bodyMedium?.copyWith(
              color: Theme.of(context).brightness == Brightness.dark
                  ? AppColors.textSecondaryDark
                  : AppColors.textSecondaryLight,
            ),
            textAlign: TextAlign.center,
          ),
        ],
      ],
    );

    if (isFullScreen) {
      return Container(
        color: AppColors.overlayLight,
        child: Center(child: loadingContent),
      );
    }

    return Center(child: loadingContent);
  }
}

/// Shimmer 加载效果组件
///
/// 使用示例：
/// ```dart
/// // 矩形骨架屏
/// ShimmerLoading(
///   width: double.infinity,
///   height: 200,
/// )
///
/// // 圆形骨架屏
/// ShimmerLoading.circle(size: 48)
///
/// // 自定义形状
/// ShimmerLoading.custom(
///   child: YourWidget(),
/// )
/// ```
class ShimmerLoading extends StatefulWidget {
  /// 宽度
  final double? width;

  /// 高度
  final double? height;

  /// 圆角
  final double borderRadius;

  /// 是否为圆形
  final bool isCircle;

  /// 自定义子组件
  final Widget? child;

  const ShimmerLoading({
    super.key,
    this.width,
    this.height,
    this.borderRadius = 8.0,
    this.isCircle = false,
    this.child,
  });

  /// 圆形 Shimmer
  factory ShimmerLoading.circle({
    Key? key,
    required double size,
  }) {
    return ShimmerLoading(
      key: key,
      width: size,
      height: size,
      isCircle: true,
    );
  }

  /// 自定义形状 Shimmer
  factory ShimmerLoading.custom({
    Key? key,
    required Widget child,
  }) {
    return ShimmerLoading(
      key: key,
      child: child,
    );
  }

  @override
  State<ShimmerLoading> createState() => _ShimmerLoadingState();
}

class _ShimmerLoadingState extends State<ShimmerLoading>
    with SingleTickerProviderStateMixin {
  late AnimationController _controller;
  late Animation<double> _animation;

  @override
  void initState() {
    super.initState();
    _controller = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 1500),
    )..repeat();

    _animation = Tween<double>(begin: -2.0, end: 2.0).animate(
      CurvedAnimation(parent: _controller, curve: Curves.easeInOutSine),
    );
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    final baseColor = isDark ? AppColors.surfaceDark : AppColors.surfaceLight;
    final highlightColor = isDark ? AppColors.cardDark : AppColors.dividerLight;

    return AnimatedBuilder(
      animation: _animation,
      builder: (context, child) {
        return Container(
          width: widget.width,
          height: widget.height,
          decoration: BoxDecoration(
            gradient: LinearGradient(
              begin: Alignment.centerLeft,
              end: Alignment.centerRight,
              colors: [
                baseColor,
                highlightColor,
                baseColor,
              ],
              stops: [
                0.0,
                _animation.value.clamp(0.0, 1.0),
                1.0,
              ],
            ),
            borderRadius: widget.isCircle
                ? null
                : BorderRadius.circular(widget.borderRadius),
            shape: widget.isCircle ? BoxShape.circle : BoxShape.rectangle,
          ),
          child: widget.child,
        );
      },
    );
  }
}

/// 卡片骨架屏组件
///
/// 用于列表项、卡片等的骨架屏效果
///
/// 使用示例：
/// ```dart
/// CardShimmer()
/// ```
class CardShimmer extends StatelessWidget {
  const CardShimmer({super.key});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: EdgeInsets.all(AppDimensions.spacing16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // 图片骨架
          ShimmerLoading(
            width: double.infinity,
            height: 200,
            borderRadius: AppDimensions.radiusMedium,
          ),
          SizedBox(height: AppDimensions.spacing12),
          // 标题骨架
          ShimmerLoading(
            width: double.infinity,
            height: 20,
            borderRadius: AppDimensions.radiusSmall,
          ),
          SizedBox(height: AppDimensions.spacing8),
          // 副标题骨架
          ShimmerLoading(
            width: 150,
            height: 16,
            borderRadius: AppDimensions.radiusSmall,
          ),
          SizedBox(height: AppDimensions.spacing12),
          // 内容骨架
          ShimmerLoading(
            width: double.infinity,
            height: 14,
            borderRadius: AppDimensions.radiusSmall,
          ),
          SizedBox(height: AppDimensions.spacing8),
          ShimmerLoading(
            width: double.infinity,
            height: 14,
            borderRadius: AppDimensions.radiusSmall,
          ),
          SizedBox(height: AppDimensions.spacing8),
          ShimmerLoading(
            width: 200,
            height: 14,
            borderRadius: AppDimensions.radiusSmall,
          ),
        ],
      ),
    );
  }
}

/// 列表项骨架屏组件
///
/// 用于列表项的骨架屏效果
///
/// 使用示例：
/// ```dart
/// ListView.builder(
///   itemCount: isLoading ? 5 : items.length,
///   itemBuilder: (context, index) {
///     if (isLoading) return ListItemShimmer();
///     return YourListItem(items[index]);
///   },
/// )
/// ```
class ListItemShimmer extends StatelessWidget {
  const ListItemShimmer({super.key});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: EdgeInsets.symmetric(
        horizontal: AppDimensions.spacing16,
        vertical: AppDimensions.spacing8,
      ),
      child: Row(
        children: [
          // 头像/图标骨架
          ShimmerLoading.circle(size: 48),
          SizedBox(width: AppDimensions.spacing12),
          // 文本骨架
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                ShimmerLoading(
                  width: double.infinity,
                  height: 16,
                  borderRadius: AppDimensions.radiusSmall,
                ),
                SizedBox(height: AppDimensions.spacing8),
                ShimmerLoading(
                  width: 150,
                  height: 14,
                  borderRadius: AppDimensions.radiusSmall,
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}
