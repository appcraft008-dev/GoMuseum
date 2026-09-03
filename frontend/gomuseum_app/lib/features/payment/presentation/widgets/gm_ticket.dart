/// 票据外壳:付费→激活整条链路共用的那张「票」。
///
/// 设计来源 Claude Design `paywall-flow.jsx`(票据版全链路)。三段结构:
///   票头(GOMUSEUM · PARIS / 7 JOURS) ┊ 主体(标题+价格+卖点) ┊ 撕线 ┊ 存根位
///
/// 两条设计约束,改的时候别丢:
/// - **价格在主体、不在存根位**。存根是被撕走的那半,价格放上去等于承诺
///   "这块会消失"。
/// - **撕开只在后端确认成功后才发生**。票在确认前始终完整 —— 撕开这个动作
///   必须对应"7×24 小时真的开始跑了",否则用户看到票撕了却没生效。
library;

import 'package:flutter/material.dart';

import 'package:gomuseum_app/theme/gm_palette.dart';
import 'package:gomuseum_app/theme/gm_theme_x.dart';
import 'package:gomuseum_app/theme/gm_tokens.dart';

class GmTicket extends StatelessWidget {
  const GmTicket({
    super.key,
    required this.child,
    this.stub,
    this.torn = 0.0,
    this.dim = false,
  });

  /// 票面主体,通常是 [GmTicketFace]。
  final Widget child;

  /// 存根位。null 时不画撕线 —— 没有存根就没有"可撕"的语义。
  final Widget? stub;

  /// 0 = 完整(整条虚线),1 = 已撕开(中段断掉、只剩左右两截)。
  /// 中间值由调用方用 TweenAnimationBuilder 驱动,做那 200ms 的原地断开。
  final double torn;

  /// 网络确认中把票压暗:告诉用户"这张票正被处理",但**不撕**。
  final bool dim;

  @override
  Widget build(BuildContext context) {
    final gm = context.gm;
    return Opacity(
      opacity: dim ? 0.55 : 1,
      child: DecoratedBox(
        decoration: BoxDecoration(
          color: gm.bg,
          border: Border.all(color: gm.line),
        ),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            _header(context, gm),
            Padding(
              padding: const EdgeInsets.fromLTRB(16, 15, 16, 14),
              child: child,
            ),
            if (stub != null) _tearAndStub(gm),
          ],
        ),
      ),
    );
  }

  /// 票头。GOMUSEUM · PARIS / 7 JOURS 是票面刻印,**不翻译** ——
  /// 它是品牌标记不是文案(纸质门票上的印刷也不会随读者语言变)。
  Widget _header(BuildContext context, GmPalette gm) => Container(
        padding: const EdgeInsets.fromLTRB(16, 9, 16, 8),
        decoration: BoxDecoration(
          border: Border(bottom: BorderSide(color: gm.line)),
        ),
        child: Row(
          children: [
            Text('◆', style: GmText.sans(size: 9, color: gm.accent)),
            const SizedBox(width: 8),
            Text(
              'GOMUSEUM · PARIS',
              style: GmText.sans(
                  size: 9.5,
                  letterSpacing: 2.5,
                  color: gm.sub,
                  weight: FontWeight.w600),
            ),
            const Spacer(),
            Text('7 JOURS',
                style:
                    GmText.sans(size: 9.5, letterSpacing: 1, color: gm.faint)),
          ],
        ),
      );

  /// 撕线 + 存根位。左右两个半圆缺口故意画到票外(Clip.none),
  /// 才有"从纸上剪出来"的感觉;缺口底色取 [GmPalette.surface] —— 它是
  /// 票背后那层弹层的颜色,填别的色就成了贴上去的白点。
  Widget _tearAndStub(GmPalette gm) => Stack(
        clipBehavior: Clip.none,
        children: [
          Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              SizedBox(
                height: 1,
                child: CustomPaint(
                  painter: _TearPainter(
                    intact: gm.line,
                    torn: gm.faint,
                    progress: torn,
                  ),
                ),
              ),
              Padding(
                padding: const EdgeInsets.fromLTRB(16, 12, 16, 13),
                child: stub,
              ),
            ],
          ),
          Positioned(left: -8, top: -7, child: _notch(gm)),
          Positioned(right: -8, top: -7, child: _notch(gm)),
        ],
      );

  Widget _notch(GmPalette gm) => Container(
        width: 14,
        height: 14,
        decoration: BoxDecoration(
          color: gm.surface,
          shape: BoxShape.circle,
          border: Border.all(color: gm.line),
        ),
      );
}

/// 撕线:未撕时整条虚线,撕开后只剩左右各 34%、中段是空的。
class _TearPainter extends CustomPainter {
  const _TearPainter({
    required this.intact,
    required this.torn,
    required this.progress,
  });

  final Color intact;
  final Color torn;
  final double progress;

  static const double _dash = 4;
  static const double _gap = 3;

  @override
  void paint(Canvas canvas, Size size) {
    if (progress < 1) {
      _dashes(canvas, 0, size.width,
          intact.withValues(alpha: intact.a * (1 - progress)));
    }
    if (progress > 0) {
      final end = size.width * 0.34;
      final color = torn.withValues(alpha: torn.a * progress);
      _dashes(canvas, 0, end, color);
      _dashes(canvas, size.width - end, size.width, color);
    }
  }

  void _dashes(Canvas canvas, double from, double to, Color color) {
    final paint = Paint()
      ..color = color
      ..strokeWidth = 1;
    for (var x = from; x < to; x += _dash + _gap) {
      canvas.drawLine(
          Offset(x, 0.5), Offset((x + _dash).clamp(from, to), 0.5), paint);
    }
  }

  @override
  bool shouldRepaint(_TearPainter old) =>
      old.progress != progress || old.intact != intact || old.torn != torn;
}

/// 票面主体:标题 + 价格(同区) + 卖点。
class GmTicketFace extends StatelessWidget {
  const GmTicketFace({
    super.key,
    required this.title,
    required this.pitch,
    this.price,
    this.priceNote,
    this.paidLabel,
  });

  final String title;
  final String pitch;

  /// Play 返回的**本地化**价格串。拿不到就整块不显示 —— 见 passPriceProvider,
  /// 宁可不显示价格,也不显示一个在当地是错的金额。
  final String? price;

  /// 未购时的价格注解(「一次性 · 非订阅」)。
  final String? priceNote;

  /// 已购后价格降级成收据:小字、faint 色,注解换成「已付」。
  final String? paidLabel;

  bool get _paid => paidLabel != null;

  @override
  Widget build(BuildContext context) {
    final gm = context.gm;
    return Column(
      mainAxisSize: MainAxisSize.min,
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Expanded(
              child: Text(
                title,
                style: GmText.serif(
                  size: 21,
                  weight: FontWeight.w700,
                  height: 1.25,
                  letterSpacing: context.gmLetterSpacing(0.5),
                ),
              ),
            ),
            if (price != null) ...[
              const SizedBox(width: 12),
              Padding(
                // 已付时价格是 14px,顶对齐会浮在 21px 标题上方,压下来对齐基线
                padding: EdgeInsets.only(top: _paid ? 5 : 0),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.end,
                  children: [
                    Text(
                      price!,
                      style: GmText.serif(
                        size: _paid ? 14 : 21,
                        weight: FontWeight.w700,
                        color: _paid ? gm.faint : gm.ink,
                        letterSpacing: 0.5,
                      ),
                    ),
                    if (paidLabel != null || priceNote != null)
                      Padding(
                        padding: const EdgeInsets.only(top: 2),
                        child: Text(paidLabel ?? priceNote!,
                            style: GmText.sans(size: 10, color: gm.faint)),
                      ),
                  ],
                ),
              ),
            ],
          ],
        ),
        const SizedBox(height: 10),
        Text(pitch,
            style: GmText.sans(size: 12.5, color: gm.sub, height: 1.65)),
      ],
    );
  }
}

/// 存根位「标签 ──── 值」的通用排法(激活前:存根/到期日待填、未撕开)。
class GmTicketStubLine extends StatelessWidget {
  const GmTicketStubLine({super.key, required this.label, required this.value});

  final String label;
  final String value;

  @override
  Widget build(BuildContext context) {
    final gm = context.gm;
    return Row(
      children: [
        Text(label, style: GmText.sans(size: 10, color: gm.faint)),
        const SizedBox(width: 9),
        Expanded(
          child: SizedBox(height: 1, child: ColoredBox(color: gm.line)),
        ),
        const SizedBox(width: 9),
        Flexible(
          child: Text(
            value,
            textAlign: TextAlign.right,
            style: GmText.sans(size: 11, color: gm.faint)
                .copyWith(fontStyle: FontStyle.italic),
          ),
        ),
      ],
    );
  }
}
