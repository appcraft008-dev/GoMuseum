/// 门票式按钮：实底圆角 4 + 内层虚线框 + 衬线文字
///
/// 对应设计稿首页「拍照识别讲解」CTA 与识别页「确认，开始讲解」按钮。
library;

import 'package:flutter/material.dart';

import 'package:gomuseum_app/theme/gm_tokens.dart';
import 'package:gomuseum_app/ui/gm/gm_icon.dart';

class GmTicketButton extends StatelessWidget {
  const GmTicketButton({
    super.key,
    required this.label,
    this.icon,
    this.trailingIcon,
    this.onTap,
    this.height = 44,
    this.fontSize = 15,
  });

  final String label;
  final GmIcons? icon;
  final GmIcons? trailingIcon;
  final VoidCallback? onTap;
  final double height;
  final double fontSize;

  @override
  Widget build(BuildContext context) {
    final dashColor = GmColors.ctaInk.withValues(alpha: 0.45);
    return GestureDetector(
      onTap: onTap,
      child: Container(
        decoration: BoxDecoration(
          color: GmColors.ctaBg,
          borderRadius: BorderRadius.circular(4),
        ),
        padding: const EdgeInsets.all(7),
        child: CustomPaint(
          painter: _DashedBorderPainter(color: dashColor),
          child: SizedBox(
            height: height,
            child: Row(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                if (icon != null) ...[
                  GmIcon(icon!, size: fontSize + 8, color: GmColors.ctaInk),
                  const SizedBox(width: 11),
                ],
                Text(
                  label,
                  style: GmText.serif(
                    size: fontSize,
                    weight: FontWeight.w600,
                    color: GmColors.ctaInk,
                    letterSpacing: 1.8,
                  ),
                ),
                if (trailingIcon != null) ...[
                  const SizedBox(width: 11),
                  GmIcon(
                    trailingIcon!,
                    size: fontSize + 3,
                    color: GmColors.ctaInk.withValues(alpha: 0.7),
                  ),
                ],
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class _DashedBorderPainter extends CustomPainter {
  const _DashedBorderPainter({required this.color});

  final Color color;

  @override
  void paint(Canvas canvas, Size size) {
    final paint = Paint()
      ..color = color
      ..style = PaintingStyle.stroke
      ..strokeWidth = 1;
    const dash = 4.0;
    const gap = 3.0;
    final rrect = RRect.fromRectAndRadius(
      Offset.zero & size,
      const Radius.circular(2),
    );
    final path = Path()..addRRect(rrect);
    for (final metric in path.computeMetrics()) {
      var distance = 0.0;
      while (distance < metric.length) {
        canvas.drawPath(
          metric.extractPath(distance, distance + dash),
          paint,
        );
        distance += dash + gap;
      }
    }
  }

  @override
  bool shouldRepaint(_DashedBorderPainter oldDelegate) =>
      color != oldDelegate.color;
}
