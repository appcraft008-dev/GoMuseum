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
    final numberStyle = GmText.serif(
      size: 13,
      weight: FontWeight.w700,
      color: numberColor ?? gm.accent,
      letterSpacing: 2,
    );
    final labelStyle = GmText.sans(
        size: 12,
        letterSpacing: context.gmLetterSpacing(3),
        weight: FontWeight.w600);
    final noteStyle = GmText.sans(size: 11.5, color: gm.sub);

    // 标题**不能**是 Row 的 flex 子节点。曾经是 `Flexible(label)` + `Expanded(线)`：
    // 两者 flex 都是 1，而 Expanded 是 tight —— 于是那条装饰线**跟标题平分**剩余
    // 宽度。实测 411dp 宽下「Louvre Museum」需 163 只分到 61 → 显示成「Louvr…」，
    // 「Musées à Paris」需 176 只分到 108 →「Musées à…」。不是文案太长，
    // 是分空间的规则错了。（loose 的 Flexible 少用的那部分也不会回流给线，
    // 而是堆在行尾，所以短标题时 note 还会离右边缘浮着一截。）
    //
    // 要「标题按自身宽度排、线吃掉剩余、note 贴右」，标题就只能是非 flex；
    // 而它一旦是非 flex 就自己不会收缩，上限必须算出来 —— 所以这里量一次
    // 编号与 note 的实际宽度，剩下的给标题，再给线留一小截。
    return LayoutBuilder(
      builder: (context, c) {
        final scaler = MediaQuery.textScalerOf(context);
        double widthOf(String s, TextStyle style) => (TextPainter(
              text: TextSpan(text: s, style: style),
              textDirection: Directionality.of(context),
              textScaler: scaler,
            )..layout())
                .width;

        final fixed = widthOf(number, numberStyle) +
            12 + // 编号与标题之间
            12 + // 标题与线之间
            (note == null ? 0 : widthOf(note!, noteStyle) + 12);
        final maxLabel =
            (c.maxWidth - fixed - _minHairline).clamp(0.0, double.infinity);

        return Row(
          children: [
            Text(number, style: numberStyle),
            const SizedBox(width: 12),
            ConstrainedBox(
              // 上限而非配额：短标题完整显示，只有真的放不下才省略
              //（法语「Aide & Mentions légales」那类）。
              constraints: BoxConstraints(maxWidth: maxLabel),
              child: Text(
                label,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: labelStyle,
              ),
            ),
            const SizedBox(width: 12),
            const Expanded(child: GmHairline()),
            if (note != null) ...[
              const SizedBox(width: 12),
              GestureDetector(
                onTap: onNoteTap,
                behavior: HitTestBehavior.opaque,
                child: Text(note!, style: noteStyle),
              ),
            ],
          ],
        );
      },
    );
  }

  /// 标题再长也给发丝线留这么宽 —— 线是这个栏头的识别特征，缩到 0 就不成形了。
  static const double _minHairline = 16;
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
