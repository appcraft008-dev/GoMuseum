/// 暖纸手册原子组件：菱形分隔、目录小节头、发丝线、小标签、开关
///
/// 对应设计稿 `screens-final.jsx` 的 FinDiamond / FinSectionHead 与
/// `gm-shared.jsx` 的 GMHairline / GMEyebrow / Settings Toggle。
library;

import 'package:flutter/material.dart';

import 'package:gomuseum_app/theme/gm_theme_x.dart';
import 'package:gomuseum_app/theme/gm_tokens.dart';

/// 菱形分隔 ◆：两侧 1px 细线 + 中央 4.5px 旋转 45° 赤陶方块
class GmDiamond extends StatelessWidget {
  const GmDiamond({super.key, this.width = 130});

  final double width;

  @override
  Widget build(BuildContext context) {
    final gm = context.gm;
    return SizedBox(
      width: width,
      child: Row(
        children: [
          Expanded(
              child: SizedBox(height: 1, child: ColoredBox(color: gm.faint))),
          const SizedBox(width: 8),
          Transform.rotate(
            angle: 0.785398, // 45°
            child: SizedBox(
              width: 4.5,
              height: 4.5,
              child: ColoredBox(color: gm.accent),
            ),
          ),
          const SizedBox(width: 8),
          Expanded(
              child: SizedBox(height: 1, child: ColoredBox(color: gm.faint))),
        ],
      ),
    );
  }
}

/// 目录编号小节头：`01 ── 标题 ──── 备注`
class GmSectionHead extends StatelessWidget {
  const GmSectionHead({
    super.key,
    required this.number,
    required this.label,
    this.note,
    this.numberColor,
    this.onNoteTap,
  });

  final String number;
  final String label;
  final String? note;

  /// null → 使用 context.gm.accent（主题自适应）
  final Color? numberColor;
  final VoidCallback? onNoteTap;

  @override
  Widget build(BuildContext context) {
    final gm = context.gm;
    final effectiveNumberColor = numberColor ?? gm.accent;
    return Row(
      children: [
        Text(
          number,
          style: GmText.serif(
            size: 13,
            weight: FontWeight.w700,
            color: effectiveNumberColor,
            letterSpacing: 2,
          ),
        ),
        const SizedBox(width: 12),
        Text(
          label,
          style: GmText.sans(
              size: 12,
              letterSpacing: context.gmLetterSpacing(3),
              weight: FontWeight.w600),
        ),
        const SizedBox(width: 12),
        const Expanded(child: GmHairline()),
        if (note != null) ...[
          const SizedBox(width: 12),
          GestureDetector(
            onTap: onNoteTap,
            behavior: HitTestBehavior.opaque,
            child: Text(note!, style: GmText.sans(size: 11.5, color: gm.sub)),
          ),
        ],
      ],
    );
  }
}

/// 发丝线
class GmHairline extends StatelessWidget {
  const GmHairline({super.key, this.color});

  /// null → 使用 context.gm.line（主题自适应）
  final Color? color;

  @override
  Widget build(BuildContext context) {
    final effectiveColor = color ?? context.gm.line;
    return SizedBox(height: 1, child: ColoredBox(color: effectiveColor));
  }
}

/// 小标签（大写、宽字距）
class GmEyebrow extends StatelessWidget {
  const GmEyebrow(this.text, {super.key, this.color});

  final String text;

  /// null → 使用 context.gm.sub（主题自适应）
  final Color? color;

  @override
  Widget build(BuildContext context) {
    final effectiveColor = color ?? context.gm.sub;
    return Text(text.toUpperCase(),
        style: GmText.eyebrow(color: effectiveColor));
  }
}

/// 暖纸开关（40×23）
class GmToggle extends StatelessWidget {
  const GmToggle({super.key, required this.value, this.onChanged});

  final bool value;
  final ValueChanged<bool>? onChanged;

  @override
  Widget build(BuildContext context) {
    final gm = context.gm;
    return GestureDetector(
      onTap: onChanged == null ? null : () => onChanged!(!value),
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 150),
        width: 40,
        height: 23,
        padding: const EdgeInsets.all(2.5),
        alignment: value ? Alignment.centerRight : Alignment.centerLeft,
        decoration: BoxDecoration(
          color: value ? gm.accent : gm.line,
          borderRadius: BorderRadius.circular(999),
        ),
        child: DecoratedBox(
          decoration: BoxDecoration(color: gm.surface, shape: BoxShape.circle),
          child: const SizedBox(width: 18, height: 18),
        ),
      ),
    );
  }
}
