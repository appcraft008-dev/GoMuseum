/// 付费墙 + 激活确认:**票据版全链路**(Claude Design `paywall-flow.jsx`)。
///
/// 付费墙**两个**触发点共用一个(语音第二件 / 识别额度耗尽),三档强度
/// 避免反复打扰:
///   第 2 件点语音     → 轻提示条 `showPaywallHint`
///   同一件再点/点了解 → 完整付费页 `showPaywallSheet`
///   识别额度耗尽      → 完整付费页(强节点)
///
/// ⚠️ 这里曾写着第三个触发点「AI 问答」——**那个功能已经下线**
/// (`/chat/ask` 返 503)。付费墙不该承诺一个不存在的能力;
/// 预设问答是免费的,见 `paywallFreeAlways`。
///
/// ⚠️ 付费墙建在**现场体验**(识别/语音/问答),不建在**内容**——
/// 浏览、搜索、完整文字讲解永远免费,所以这里明说"始终免费"那一行,
/// 让用户知道自己不是被锁在内容外面。
///
/// 设计的核心隐喻是一张**票**:购买→激活是一条线,票在确认前始终完整,
/// 撕开只在后端确认成功后原地发生(见 [GmTicket] 的注释)。
library;

import 'package:gomuseum_app/core/router/app_router.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import 'package:gomuseum_app/features/payment/data/entitlements.dart';
import 'package:gomuseum_app/features/payment/data/pass_offer.dart';
import 'package:gomuseum_app/features/payment/data/pass_product.dart';
import 'package:gomuseum_app/features/payment/presentation/widgets/benefits_sections.dart';
import 'package:gomuseum_app/features/payment/presentation/widgets/gm_ticket.dart';

import 'package:gomuseum_app/l10n/app_localizations.dart';
import 'package:gomuseum_app/theme/gm_palette.dart';
import 'package:gomuseum_app/theme/gm_theme_x.dart';
import 'package:gomuseum_app/theme/gm_tokens.dart';
import 'package:gomuseum_app/ui/gm/gm_ticket_button.dart';

/// 一张在售票的票面(标题/卖点/价格全部来自后端下发的 [PassOffer])。
/// 付费墙与权益页共用 —— 两处各拼一份的话,迟早一处还写着「巴黎 7 日」。
GmTicketFace saleTicketFace(
  BuildContext context,
  WidgetRef ref,
  PassOffer offer, {
  bool showPrice = true,
}) {
  final l10n = AppLocalizations.of(context)!;
  return GmTicketFace(
    title: passTitle(l10n, offer.label, offer.days, title: offer.title),
    pitch: passPitch(context, offer.covers),
    price:
        showPrice ? ref.watch(passPriceProvider(offer.productId)).value : '—',
    priceNote: showPrice ? l10n.paywallPriceNote : null,
  );
}

/// 票名。优先用后端拼好的 [title](新票种改名不发版);老后端没给时按
/// 「<范围> <天数> 日通票」自己拼。认不出是哪张票时(历史票)范围留空,
/// 标题退化成「7 日通票」—— 宁可不写地名,也不编一个(巴黎)出来。
String passTitle(AppLocalizations l10n, String label, int days,
        {String? title}) =>
    (title != null && title.isNotEmpty)
        ? title
        : l10n
            .paywallTitle(label, '$days')
            .replaceAll(RegExp(r'\s+'), ' ')
            .replaceAll(RegExp(r'^[\s–-]+|[\s–-]+$'), '')
            .trim();

/// 卖点:「不限次识别,<这张票覆盖的馆>全部语音讲解」。馆名来自后端,
/// 上新馆自动变长;拿不到馆名时用不点名的通用版,绝不回落到写死的四馆。
String passPitch(BuildContext context, List<String> covers) {
  final l10n = AppLocalizations.of(context)!;
  if (covers.isEmpty) return l10n.paywallPitchGeneric;
  return l10n.paywallPitch(
      joinMuseums(covers, Localizations.localeOf(context).languageCode));
}

/// 轻提示条:第一次撞墙时只轻碰一下,不打断现场体验。
///
/// [onLearnMore] 必填:此前它可选、缺省回落到 `showPaywallSheet(context)`,
/// 而那个 sheet 不带 onBuy —— 用户点"获取通票"只会关掉弹窗、什么都不发生。
/// 改必填是让编译器堵死这条路,不能再"忘了传"。
///
/// [message]:撞墙的**原因**(通票过期 / 这件的免费试听结束)。不给 = 默认提示。
void showPaywallHint(BuildContext context,
    {required VoidCallback onLearnMore, String? message}) {
  final l10n = AppLocalizations.of(context)!;
  // 清队列:`ScaffoldMessenger` 是 **MaterialApp 根上那一个**,提示条会排队挨个
  // 播完。连点几件锁着的作品就攒出一串,而这条提示的本意是"轻碰一下"。
  ScaffoldMessenger.of(context).clearSnackBars();
  ScaffoldMessenger.of(context).showSnackBar(
    SnackBar(
      content: Text(message ?? l10n.audioLockedHint('7')),
      duration: const Duration(seconds: 4),
      // ⚠️ **必须显式写 false,否则 duration 是句空话。**
      // Flutter 的 `SnackBar` 构造器里:`persist = persist ?? action != null`
      // (snack_bar.dart)—— 带 action 的提示条**默认永不自动消失**,计时器到点
      // 后看见 persist 直接 return。2026-09-04 真机撞到:提示条一路飘到权益页
      // 还赖着不走。这跟无障碍设置无关,是无条件的默认值。
      persist: false,
      action: SnackBarAction(
        label: l10n.paywallBuy,
        onPressed: onLearnMore,
      ),
    ),
  );
}

/// 完整付费页。[reason] 仅用于埋点区分是哪一档触发的。
///
/// [onBuy] 必填:曾经它可选,而 `guide_audio_player` 两处调用都没传 ——
/// 按钮点下去只 pop 弹窗,`onBuy?.call()` 静默跳过,付费墙整个是死的
/// (2026-09-02 真机实测撞到,versionCode 12 及之前全部受影响)。
/// 改必填后"忘了传"变成编译错误,不再依赖人记得。
///
/// ⛔ **这里没有「恢复购买」,是有意的。** 通票是消耗型商品,验证成功即被消耗,
/// 之后恢复恒定捞不到东西 —— 对绝大多数人那是个空操作按钮,却摆在主 CTA
/// 正下方。它唯一覆盖的场景(付了钱但后端验证没成功)**机器自己认得出**
/// (Play 有购买 + 后端无权益),已改为权益页自动静默恢复。
/// 手动入口只在权益页底部留一个兜底。
///
/// [offer]:这家馆该买的票(馆包/402 的 `pass`)。null = 不知道在哪家馆 →
/// 列出 `/me.offers` 的每一张。[onBuy] 收到要买的商品 ID(列出多张时为 null,
/// 由权益页让用户挑)。
Future<void> showPaywallSheet(
  BuildContext context, {
  String reason = 'unknown',
  PassOffer? offer,
  required void Function(String? productId) onBuy,
}) {
  final gm = context.gm;
  return showModalBottomSheet<void>(
    context: context,
    isScrollControlled: true,
    backgroundColor: Colors.transparent,
    barrierColor: gm.ink.withValues(alpha: 0.32),
    builder: (_) => PaywallSheetContent(offer: offer, onBuy: onBuy),
  );
}

/// 购买入口统一跳权益页(购买全流程只在那里实现)。带 `?pass=` 就只卖那一张。
String benefitsRoute(String? productId) =>
    productId == null ? '/benefits' : '/benefits?pass=$productId';

/// 弹层外壳:暖纸底、直角(4px)、顶部发丝线。小屏内容超出可滚,CTA 不会被挤出屏幕。
class _PaywallSheetShell extends StatelessWidget {
  const _PaywallSheetShell({required this.children});

  final List<Widget> children;

  @override
  Widget build(BuildContext context) {
    final gm = context.gm;
    return Container(
      constraints:
          BoxConstraints(maxHeight: MediaQuery.sizeOf(context).height * 0.92),
      decoration: BoxDecoration(
        color: gm.surface,
        borderRadius: const BorderRadius.vertical(top: Radius.circular(4)),
        border: Border(top: BorderSide(color: gm.line)),
      ),
      padding: const EdgeInsets.fromLTRB(20, 20, 20, 24),
      child: SafeArea(
        top: false,
        child: SingleChildScrollView(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: children,
          ),
        ),
      ),
    );
  }
}

/// 次要动作(恢复购买 / 稍后再说):居中、无边框,不与主 CTA 抢。
class _SecondaryAction extends StatelessWidget {
  const _SecondaryAction({required this.label, required this.onTap});

  final String label;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return Center(
      child: GestureDetector(
        onTap: onTap,
        behavior: HitTestBehavior.opaque,
        child: Padding(
          padding: const EdgeInsets.symmetric(vertical: 8, horizontal: 10),
          child:
              Text(label, style: GmText.sans(size: 13, color: context.gm.sub)),
        ),
      ),
    );
  }
}

/// 屏 1 · 付费页。抽出便于单测(不依赖 showModalBottomSheet)。
class PaywallSheetContent extends ConsumerWidget {
  const PaywallSheetContent({super.key, this.offer, this.onBuy});

  final PassOffer? offer;
  final void Function(String? productId)? onBuy;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final gm = context.gm;
    final l10n = AppLocalizations.of(context)!;
    final ent = ref.watch(entitlementsProvider).value;
    // 游客先登录再买:通票挂账号,游客买了换手机就永久拿不回(后端也会 403 拦)
    final canBuy = ent?.canPurchase ?? false;
    // ⚠️ 权益**读不到**(离线)和**未登录**是两回事。混在一起就会对着一个
    // 已登录、只是断网的用户说「登录后购买」,他照做也没用。
    final unknown = ent != null && !ent.known;
    // 卖哪张票由后端决定:知道在哪家馆就卖那一张,不知道就每张都列出来
    // (不猜"第一张" —— 票多了会卖错)。拿不到任何在售票就说「暂未开售」。
    final offers = offer != null ? [offer!] : (ent?.offers ?? const []);

    if (unknown) return _unknownSheet(context, gm, l10n, ref);

    return _PaywallSheetShell(
      children: [
        if (offers.isEmpty) BenNotice(head: l10n.passNotOnSale, body: ''),
        for (final o in offers) ...[
          GmTicket(
            stamp: o.stampText,
            days: o.days,
            stub: _clockClause(context, gm, l10n, o.days),
            child: saleTicketFace(context, ref, o),
          ),
          const SizedBox(height: 10),
        ],
        // 未登录:说清"为什么要先登录",而不是只把按钮换个字
        if (!canBuy)
          BenNotice(
            head: l10n.edgeSignedOutHead,
            body: l10n.edgeSignedOutBody,
          ),
        const SizedBox(height: 13),
        // 让用户知道自己没被锁在内容外面(付费墙在现场体验,不在内容)
        Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Padding(
              padding: const EdgeInsets.only(top: 2),
              child: Text('◆', style: GmText.sans(size: 11, color: gm.accent)),
            ),
            const SizedBox(width: 8),
            Expanded(
              child: Text(l10n.paywallFreeAlways,
                  style: GmText.sans(size: 12.5, color: gm.sub, height: 1.6)),
            ),
          ],
        ),
        const SizedBox(height: 18),
        if (offers.isNotEmpty)
          GmTicketButton(
            label: canBuy ? l10n.paywallBuy : l10n.paywallLoginToBuy,
            onTap: () {
              Navigator.of(context).pop();
              if (canBuy) {
                onBuy?.call(offers.length == 1 ? offers.first.productId : null);
              } else {
                context.push(kLoginToUpgrade);
              }
            },
          ),
      ],
    );
  }

  /// 权益读不到(离线)。**不说"登录后购买"** —— 用户可能早就登录了,
  /// 只是网络断了;也不发起购买 —— 读不到已有权益就买,等于诱导重复购买。
  ///
  /// 用「—」价格 + 空存根表达"未知",而不是把整张票压暗:压暗看起来像
  /// "这张票有问题",实际是我们这边看不见。
  Widget _unknownSheet(BuildContext context, GmPalette gm,
          AppLocalizations l10n, WidgetRef ref) =>
      _PaywallSheetShell(
        children: [
          if (offer != null)
            GmTicket(
              stamp: offer!.stampText,
              days: offer!.days,
              stub: const SizedBox(height: 1),
              child: saleTicketFace(context, ref, offer!, showPrice: false),
            ),
          BenNotice(
            head: l10n.edgeUnknownHead,
            body: l10n.edgeUnknownBody,
            note: l10n.edgeUnknownNote,
          ),
          const SizedBox(height: 18),
          GmTicketButton(
            label: l10n.retry,
            onTap: () => ref.invalidate(entitlementsProvider),
          ),
          const SizedBox(height: 3),
          _SecondaryAction(
            label: l10n.activateLater,
            onTap: () => Navigator.of(context).pop(),
          ),
        ],
      );

  /// ⭐ 旅游产品的关键承诺:买了不马上开始烧有效期。
  /// 放在**存根位**(撕下去的那半)——它讲的正是"什么时候撕"。
  Widget _clockClause(BuildContext context, GmPalette gm, AppLocalizations l10n,
          int days) =>
      Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(l10n.paywallClockHead,
              style: GmText.serif(
                  size: 14.5,
                  weight: FontWeight.w700,
                  color: gm.accentDeep,
                  height: 1.4)),
          const SizedBox(height: 4),
          Text(l10n.paywallClockBody('$days'),
              style: GmText.sans(size: 12, color: gm.sub, height: 1.6)),
          const SizedBox(height: 4),
          // ⚠️ **合规必需,不是装饰**:后端 `ACTIVATION_WINDOW` 会真的作废
          // 30 天未激活的票。没收已付的款必须在**购买前**告知 ——
          // 这一行和那段代码是一对,删掉任何一半都不成立。
          Text(l10n.paywallLapseNote,
              style: GmText.sans(size: 11.5, color: gm.faint, height: 1.6)),
        ],
      );
}

/// 已购但未开始计时 → 弹激活确认。返回 true 表示现在已生效、调用方可继续。
///
/// **绝不静默激活**:旅游产品用户常提前几天买,误触一次就烧掉整张票 = 差评来源。
/// 反过来,不做这一步同样致命——通票会永远停在 purchased_not_activated,
/// `can.audio_any` 恒 false,用户付了钱依然被拦(此前正是如此)。
///
/// [museum]:在馆内时必传(按馆激活,只动覆盖这家馆的票)。[offer] 是这家馆在售的
/// 票,用来认出手里哪一张是它。**不在馆内且手里不止一张未激活票时不弹**:
/// 猜错一张就是替用户烧掉另一个国家的 7 天 —— 让他到那家馆用的时候再激活。
Future<bool> ensurePassActivated(
  BuildContext context,
  WidgetRef ref,
  Entitlements ent, {
  String? museum,
  PassOffer? offer,
}) async {
  if (ent.isActive) return true;
  if (!ent.isPurchasedNotActivated) return false;

  final pending = ent.passes.where((p) => p.isPurchasedNotActivated).toList();
  OwnedPass? target;
  if (offer != null) {
    target = pending.where((p) => p.productId == offer.productId).firstOrNull;
  }
  target ??= pending.length == 1 ? pending.first : null;
  if (museum == null && target == null) return false;

  final ok = await showModalBottomSheet<bool>(
    context: context,
    isScrollControlled: true,
    backgroundColor: Colors.transparent,
    barrierColor: context.gm.ink.withValues(alpha: 0.42),
    builder: (_) => ActivatePassSheet(
      museum: museum,
      label: target?.label ?? offer?.label ?? '',
      title: target?.title ?? offer?.title,
      days: target?.days ?? offer?.days ?? 7,
    ),
  );
  return ok ?? false;
}

/// 激活链路的四态(屏 2–5)。抽成公开类便于单测。
///
/// 状态机就是这张票的物理过程:
///   confirm(票完整,存根位空) → activating(票压暗,**不撕**)
///     → done(原地撕开,存根位填入到期日) / failed(票纹丝不动)
enum ActivateStep { confirm, activating, done, failed }

class ActivatePassSheet extends ConsumerStatefulWidget {
  const ActivatePassSheet({
    super.key,
    this.museum,
    required this.label,
    this.title,
    required this.days,
  });

  /// 在哪家馆激活(按馆激活,见 [activatePass])。
  final String? museum;

  /// 要激活的那张票的范围名与天数(来自后端,不写死)。
  final String label;
  final String? title;
  final int days;

  @override
  ConsumerState<ActivatePassSheet> createState() => _ActivatePassSheetState();
}

class _ActivatePassSheetState extends ConsumerState<ActivatePassSheet> {
  ActivateStep _step = ActivateStep.confirm;
  DateTime? _expiresAt;

  /// 确认页预告的结束时刻。在 initState 定一次 —— 每次 build 重算会让
  /// 用户盯着的那个时间一直往后跳。
  ///
  /// 天数取自这张票(后端下发),不是常量 —— 1 日票会预告错的结束时刻。
  late final DateTime _projectedEnd =
      DateTime.now().add(Duration(days: widget.days));

  Future<void> _activate() async {
    setState(() => _step = ActivateStep.activating);
    final updated = await activatePass(ref, museum: widget.museum);
    invalidateEntitlements(ref);
    if (!mounted) return;
    setState(() {
      if (updated?.isActive == true) {
        _step = ActivateStep.done;
        _expiresAt = updated!.expiresAt;
      } else {
        // 票没被使用 —— activate 幂等且失败不改状态,可以放心重试
        _step = ActivateStep.failed;
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    final gm = context.gm;
    final l10n = AppLocalizations.of(context)!;
    final done = _step == ActivateStep.done;

    return PopScope(
      // 确认中不许返回:此刻后端可能已经开始计时,关掉弹层会让调用方
      // 当成"用户选了稍后",而票其实已经撕开了。
      canPop: _step != ActivateStep.activating,
      child: _PaywallSheetShell(
        children: [
          ..._head(gm, l10n),
          const SizedBox(height: 15),
          // 撕开是**原地**发生的 200ms:不做全屏过渡 —— 用户正站在画前,
          // 全屏动画挡路。
          TweenAnimationBuilder<double>(
            tween: Tween(begin: 0, end: done ? 1 : 0),
            duration: const Duration(milliseconds: 200),
            builder: (_, torn, __) => GmTicket(
              stamp: widget.label.toUpperCase(),
              days: widget.days,
              torn: torn,
              dim: _step == ActivateStep.activating,
              stub: _stub(gm, l10n),
              child: GmTicketFace(
                title: passTitle(l10n, widget.label, widget.days,
                    title: widget.title),
                paidLabel: l10n.ticketPaid,
              ),
            ),
          ),
          ..._foot(gm, l10n),
        ],
      ),
    );
  }

  List<Widget> _head(GmPalette gm, AppLocalizations l10n) {
    switch (_step) {
      case ActivateStep.confirm:
      case ActivateStep.activating:
        return [
          Text(l10n.activateSheetTitle('${widget.days}'),
              style: GmText.serif(
                  size: 18,
                  weight: FontWeight.w700,
                  letterSpacing: context.gmLetterSpacing(0.5))),
          const SizedBox(height: 7),
          Text(l10n.activateSheetBody(_projectedEnd, _projectedEnd),
              style: GmText.sans(size: 13, color: gm.sub, height: 1.7)),
        ];
      case ActivateStep.done:
        return [
          Row(
            children: [
              Text('◆', style: GmText.sans(size: 13, color: gm.accent)),
              const SizedBox(width: 9),
              Text(l10n.activateDoneTitle,
                  style: GmText.serif(size: 18, weight: FontWeight.w700)),
            ],
          ),
        ];
      case ActivateStep.failed:
        return [
          Text(l10n.activateFailTitle,
              style: GmText.serif(size: 18, weight: FontWeight.w700)),
          const SizedBox(height: 7),
          Text(l10n.activateFailBody('${widget.days}'),
              style: GmText.sans(size: 13, color: gm.sub, height: 1.7)),
        ];
    }
  }

  /// 存根位。激活前是**空的**(只有一条"到期日待填"的横线),
  /// 激活后填入到期日 —— 撕开这个动作因此有了实际产物。
  Widget _stub(GmPalette gm, AppLocalizations l10n) {
    switch (_step) {
      case ActivateStep.confirm:
      case ActivateStep.activating:
        return GmTicketStubLine(
            label: l10n.ticketStub, value: l10n.ticketStubPending);
      case ActivateStep.failed:
        return GmTicketStubLine(
            label: l10n.ticketStub, value: l10n.ticketStubUntorn);
      case ActivateStep.done:
        final exp = _expiresAt;
        // 契约:可缺字段不裸取。active 却没有 expires_at 是后端异常,
        // 这里显示 "—" 而不是编一个日期出来。
        if (exp == null) {
          return GmTicketStubLine(label: l10n.ticketValidUntil, value: '—');
        }
        final daysLeft =
            (exp.difference(DateTime.now()).inHours / 24).ceil().clamp(0, 999);
        return Row(
          children: [
            Text(l10n.ticketValidUntil,
                style: GmText.sans(size: 10, color: gm.faint)),
            const SizedBox(width: 10),
            Flexible(
              child: Text(
                l10n.ticketDateTime(exp, exp),
                style: GmText.serif(
                    size: 15,
                    weight: FontWeight.w700,
                    color: gm.accentDeep,
                    letterSpacing: 0.5),
              ),
            ),
            const SizedBox(width: 10),
            Text(l10n.ticketDaysLeft(daysLeft),
                style: GmText.sans(size: 10.5, color: gm.faint)),
          ],
        );
    }
  }

  List<Widget> _foot(GmPalette gm, AppLocalizations l10n) {
    switch (_step) {
      case ActivateStep.confirm:
        return [
          const SizedBox(height: 18),
          GmTicketButton(label: l10n.activateTear, onTap: _activate),
          const SizedBox(height: 3),
          _SecondaryAction(
            label: l10n.activateLater,
            onTap: () => Navigator.of(context).pop(false),
          ),
        ];
      case ActivateStep.activating:
        return [
          const SizedBox(height: 18),
          GmTicketButton(label: l10n.activateWaiting, busy: true),
          const SizedBox(height: 12),
          Text(l10n.activateWaitingNote,
              textAlign: TextAlign.center,
              style: GmText.sans(size: 11.5, color: gm.faint)),
        ];
      case ActivateStep.done:
        return [
          const SizedBox(height: 13),
          Text(l10n.activateDoneBody,
              style: GmText.sans(size: 12.5, color: gm.sub, height: 1.65)),
          const SizedBox(height: 18),
          GmTicketButton(
            label: l10n.activateDoneCta,
            onTap: () => Navigator.of(context).pop(true),
          ),
        ];
      case ActivateStep.failed:
        return [
          const SizedBox(height: 18),
          GmTicketButton(label: l10n.activateRetry, onTap: _activate),
          const SizedBox(height: 3),
          _SecondaryAction(
            label: l10n.activateLater,
            onTap: () => Navigator.of(context).pop(false),
          ),
        ];
    }
  }
}
