/// GoMuseum 图标按钮组件
library;

import 'package:flutter/material.dart';
import 'package:gomuseum_app/theme/colors.dart';
import 'package:gomuseum_app/theme/dimensions.dart';

/// 图标按钮
class AppIconButton extends StatelessWidget {
  final IconData icon;
  final VoidCallback? onPressed;
  final String? tooltip;
  final double? size;
  final Color? color;
  final bool showBackground;

  const AppIconButton({
    super.key,
    required this.icon,
    this.onPressed,
    this.tooltip,
    this.size,
    this.color,
    this.showBackground = false,
  });

  @override
  Widget build(BuildContext context) {
    final iconButton = IconButton(
      icon: Icon(icon),
      onPressed: onPressed,
      iconSize: size ?? AppDimensions.iconSize,
      color: color ?? AppColors.primary,
      style: showBackground
          ? IconButton.styleFrom(
              backgroundColor: AppColors.primary.withValues(alpha: 0.1),
              shape: const CircleBorder(),
            )
          : null,
    );

    if (tooltip != null) {
      return Tooltip(
        message: tooltip!,
        child: iconButton,
      );
    }
    return iconButton;
  }
}
