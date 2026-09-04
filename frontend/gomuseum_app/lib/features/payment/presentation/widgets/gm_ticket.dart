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
    this.faded = false,
    this.voidStamp,
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

  /// 用过的票:去掉大部分饱和度。**和 [dim] 不是一回事** —— dim 说的是
  /// "正在处理中",faded 说的是"这张已经作废了",两者会同时出现在权益页上,
  /// 挤成一个参数就分不出"在转圈"和"已过期"。
  ///
  /// ⚠️ **单靠它读不出"作废"**,必须配 [voidStamp]。见那里的说明。
  final bool faded;

  /// 作废戳的文案(如「已结束」)。非空时在票面上斜盖一枚半透明印记。
  ///
  /// 为什么需要它:[faded] 是个**减法**信号 —— 把饱和度降到 40%。而这套暖纸
  /// 配色本来就几乎没有饱和度可减(bg 8%→3%、line 16%→6%,肉眼无差),
  /// 整个"作废"信号最后只落在那个 9px 的 accent ◆ 上。真机实测:作废票和
  /// 在售票并排放着像双胞胎,得读文字才分得清。
  ///
  /// 减法减不出来就得用加法 —— 一个明确说"作废"的正向标记。纸质票据本来
  /// 就有这个词汇:用过的票会被盖戳。
  final String? voidStamp;

  @override
  Widget build(BuildContext context) {
    final gm = context.gm;
    Widget ticket = DecoratedBox(
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
    );
    if (faded) {
      ticket = ColorFiltered(
        colorFilter: const ColorFilter.matrix(_desaturate),
        child: ticket,
      );
    }
    if (voidStamp != null) {
      // ⚠️ 戳必须盖在 ColorFiltered **外面**:放进去会被一起去饱和,
      // 那就又变回一个看不见的信号了。层次上也对 —— 票是旧的,
      // 墨是后来盖上去的。
      ticket = Stack(
        alignment: Alignment.center,
        children: [ticket, _stamp(gm)],
      );
    }
    return Opacity(opacity: dim ? 0.55 : 1, child: ticket);
  }

  /// 斜盖的作废戳。用 [GmPalette.accentDeep] 而不是 accent:后者是购买 CTA 的
  /// 颜色,拿来说"作废"会串味;accentDeep 是它的深墨版,读起来像印泥而不像按钮。
  /// 也不用 error 红 —— 通票到期是正常结束,不是出错。
  Widget _stamp(GmPalette gm) => IgnorePointer(
        child: Transform.rotate(
          angle: -0.17, // ≈ -10°,手盖上去的角度
          child: Container(
            padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 6),
            decoration: BoxDecoration(
              border: Border.all(
                color: gm.accentDeep.withValues(alpha: 0.5),
                width: 2,
              ),
            ),
            // 德语 ABGELAUFEN 之类的长词在窄屏上会顶出票面
            child: FittedBox(
              fit: BoxFit.scaleDown,
              child: Text(
                voidStamp!,
                maxLines: 1,
                style: GmText.sans(
                  size: 17,
                  weight: FontWeight.w700,
                  letterSpacing: 3,
                  color: gm.accentDeep.withValues(alpha: 0.62),
                ),
              ),
            ),
          ),
        ),
      );

  /// 饱和度降到 0.4 的标准亮度矩阵(Rec. 601 权重)。
  /// 缺口用的是 `gm.surface`,和票背后那层同色,所以跟着一起褪也不露馅。
  static const List<double> _desaturate = <double>[
    0.7126, 0.2848, 0.0426, 0, 0, //
    0.1278, 0.8696, 0.0426, 0, 0, //
    0.1278, 0.2848, 0.6174, 0, 0, //
    0, 0, 0, 1, 0, //
  ];

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

  /// 已购后的付款标记(「已付」),渲染成一枚**不带数字**的描边徽章。
  ///
  /// ⚠️ **已购之后绝不显示金额**。曾经这里画过「已付 €7.99」,而那个数字来自
  /// 商店的**当前售价** —— 涨一次价,老用户的票面就在宣称他付了一个他没付过的
  /// 金额。真实已付金额后端没落库(`purchases.amount` 恒 NULL)。
  ///
  /// 但也不能什么都不显示:用户需要看到"这张票付过钱了"。所以留字不留数 ——
  /// 价格只出现在**购买前**(那时是商店实时价,真实)。
  final String? paidLabel;

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
            if (paidLabel != null) ...[
              const SizedBox(width: 12),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                decoration: BoxDecoration(border: Border.all(color: gm.line)),
                child: Text(
                  paidLabel!,
                  style: GmText.sans(
                      size: 11, color: gm.faint, letterSpacing: 1.5),
                ),
              ),
            ] else if (price != null) ...[
              const SizedBox(width: 12),
              Column(
                crossAxisAlignment: CrossAxisAlignment.end,
                children: [
                  Text(
                    price!,
                    style: GmText.serif(
                      size: 21,
                      weight: FontWeight.w700,
                      color: gm.ink,
                      letterSpacing: 0.5,
                    ),
                  ),
                  if (priceNote != null)
                    Padding(
                      padding: const EdgeInsets.only(top: 2),
                      child: Text(priceNote!,
                          style: GmText.sans(size: 10, color: gm.faint)),
                    ),
                ],
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
