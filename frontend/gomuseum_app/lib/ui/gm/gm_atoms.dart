/// 暖纸手册原子组件：菱形分隔、目录小节头、发丝线、小标签、开关
///
/// 对应设计稿 `screens-final.jsx` 的 FinDiamond / FinSectionHead 与
/// `gm-shared.jsx` 的 GMHairline / GMEyebrow / Settings Toggle。
library;

import 'package:flutter/material.dart';

import 'package:gomuseum_app/theme/gm_tokens.dart';

/// 菱形分隔 ◆：两侧 1px 细线 + 中央 4.5px 旋转 45° 赤陶方块
class GmDiamond extends StatelessWidget {
  const GmDiamond({super.key, this.width = 130});

  final double width;

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: width,
      child: Row(
        children: [
          const Expanded(
              child: SizedBox(
                  height: 1, child: ColoredBox(color: GmColors.faint))),
          const SizedBox(width: 8),
          Transform.rotate(
            angle: 0.785398, // 45°
            child: const SizedBox(
              width: 4.5,
              height: 4.5,
              child: ColoredBox(color: GmColors.accent),
            ),
          ),
          const SizedBox(width: 8),
          const Expanded(
              child: SizedBox(
                  height: 1, child: ColoredBox(color: GmColors.faint))),
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
    this.numberColor = GmColors.accent,
    this.onNoteTap,
  });

  final String number;
  final String label;
  final String? note;
  final Color numberColor;
  final VoidCallback? onNoteTap;

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Text(
          number,
          style: GmText.serif(
            size: 13,
            weight: FontWeight.w700,
            color: numberColor,
            letterSpacing: 2,
          ),
        ),
        const SizedBox(width: 12),
        Text(
          label,
          style:
              GmText.sans(size: 12, letterSpacing: 3, weight: FontWeight.w600),
        ),
        const SizedBox(width: 12),
        const Expanded(child: GmHairline()),
        if (note != null) ...[
          const SizedBox(width: 12),
          GestureDetector(
            onTap: onNoteTap,
            behavior: HitTestBehavior.opaque,
            child: Text(note!,
                style: GmText.sans(size: 11.5, color: GmColors.sub)),
          ),
        ],
      ],
    );
  }
}

/// 发丝线
class GmHairline extends StatelessWidget {
  const GmHairline({super.key, this.color = GmColors.line});

  final Color color;

  @override
  Widget build(BuildContext context) {
    return SizedBox(height: 1, child: ColoredBox(color: color));
  }
}

/// 小标签（大写、宽字距）
class GmEyebrow extends StatelessWidget {
  const GmEyebrow(this.text, {super.key, this.color = GmColors.sub});

  final String text;
  final Color color;

  @override
  Widget build(BuildContext context) {
    return Text(text.toUpperCase(), style: GmText.eyebrow(color: color));
  }
}

/// 暖纸开关（40×23）
class GmToggle extends StatelessWidget {
  const GmToggle({super.key, required this.value, this.onChanged});

  final bool value;
  final ValueChanged<bool>? onChanged;

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onChanged == null ? null : () => onChanged!(!value),
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 150),
        width: 40,
        height: 23,
        padding: const EdgeInsets.all(2.5),
        alignment: value ? Alignment.centerRight : Alignment.centerLeft,
        decoration: BoxDecoration(
          color: value ? GmColors.accent : GmColors.line,
          borderRadius: BorderRadius.circular(999),
        ),
        child: const DecoratedBox(
          decoration:
              BoxDecoration(color: GmColors.surface, shape: BoxShape.circle),
          child: SizedBox(width: 18, height: 18),
        ),
      ),
    );
  }
}
