/// 付费墙 + 激活确认:**票据版全链路**(Claude Design `paywall-flow.jsx`)。
///
/// 付费墙三个触发点共用一个(语音第二件 / 识别额度耗尽 / AI 问答),三档强度
/// 避免反复打扰:
///   第 2 件点语音     → 轻提示条 `showPaywallHint`
///   同一件再点/点了解 → 完整付费页 `showPaywallSheet`
///   识别额度耗尽      → 完整付费页(强节点)
///
/// ⚠️ 付费墙建在**现场体验**(识别/语音/问答),不建在**内容**——
/// 浏览、搜索、完整文字讲解永远免费,所以这里明说"始终免费"那一行,
/// 让用户知道自己不是被锁在内容外面。
///
/// 设计的核心隐喻是一张**票**:购买→激活是一条线,票在确认前始终完整,
/// 撕开只在后端确认成功后原地发生(见 [GmTicket] 的注释)。
library;

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import 'package:gomuseum_app/features/payment/data/entitlements.dart';
import 'package:gomuseum_app/features/payment/data/pass_product.dart';
import 'package:gomuseum_app/features/payment/presentation/widgets/benefits_sections.dart';
import 'package:gomuseum_app/features/payment/presentation/widgets/gm_ticket.dart';

import 'package:gomuseum_app/l10n/app_localizations.dart';
import 'package:gomuseum_app/theme/gm_palette.dart';
import 'package:gomuseum_app/theme/gm_theme_x.dart';
import 'package:gomuseum_app/theme/gm_tokens.dart';
import 'package:gomuseum_app/ui/gm/gm_ticket_button.dart';

/// 通票时长。后端按商品算(`pass_duration(entitlement_type)`),前端只在
/// **激活确认页预告结束时刻**时需要它 —— 那一刻权益还没激活,后端没有
/// expires_at 可给。激活成功后一律用后端返回的 `expires_at`,不用这个值。
///
/// ponytail: 目前在售商品只有 paris_pass_7d。真出第二种时长的票时,
/// 这里要改成从后端拿(否则确认页会预告一个错的结束时刻)。
const Duration _kPassDuration = Duration(days: 7);

/// 轻提示条:第一次撞墙时只轻碰一下,不打断现场体验。
///
/// [onLearnMore] 必填:此前它可选、缺省回落到 `showPaywallSheet(context)`,
/// 而那个 sheet 不带 onBuy —— 用户点"获取通票"只会关掉弹窗、什么都不发生。
/// 改必填是让编译器堵死这条路,不能再"忘了传"。
void showPaywallHint(BuildContext context,
    {required VoidCallback onLearnMore}) {
  final l10n = AppLocalizations.of(context)!;
  ScaffoldMessenger.of(context).showSnackBar(
    SnackBar(
      content: Text(l10n.audioLockedHint),
      duration: const Duration(seconds: 4),
      action: SnackBarAction(
        label: l10n.paywallBuy,
        onPressed: onLearnMore,
      ),
    ),
  );
}

/// 完整付费页。[reason] 仅用于埋点区分是哪一档触发的。
///
/// [onBuy]/[onRestore] 必填:曾经它们可选,而 `guide_audio_player` 两处调用都
/// 没传 —— 按钮点下去只 pop 弹窗,`onBuy?.call()` 静默跳过,付费墙整个是死的
/// (2026-09-02 真机实测撞到,versionCode 12 及之前全部受影响)。
/// 改必填后"忘了传"变成编译错误,不再依赖人记得。
Future<void> showPaywallSheet(
  BuildContext context, {
  String reason = 'unknown',
  required VoidCallback onBuy,
  required VoidCallback onRestore,
}) {
  final gm = context.gm;
  return showModalBottomSheet<void>(
    context: context,
    isScrollControlled: true,
    backgroundColor: Colors.transparent,
    barrierColor: gm.ink.withValues(alpha: 0.32),
    builder: (_) => PaywallSheetContent(onBuy: onBuy, onRestore: onRestore),
  );
}

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
  const PaywallSheetContent({super.key, this.onBuy, this.onRestore});

  final VoidCallback? onBuy;
  final VoidCallback? onRestore;

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
    // 拿不到价格就不显示价格块 —— 见 passPriceProvider,绝不显示假金额
    final price = ref.watch(passPriceProvider).value;

    if (unknown) return _unknownSheet(context, gm, l10n, ref);

    return _PaywallSheetShell(
      children: [
        GmTicket(
          stub: _clockClause(context, gm, l10n),
          child: GmTicketFace(
            title: l10n.paywallTitle,
            pitch: l10n.paywallPitch,
            price: price,
            priceNote: l10n.paywallPriceNote,
          ),
        ),
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
        GmTicketButton(
          label: canBuy ? l10n.paywallBuy : l10n.paywallLoginToBuy,
          onTap: () {
            Navigator.of(context).pop();
            if (canBuy) {
              onBuy?.call();
            } else {
              context.push('/login');
            }
          },
        ),
        const SizedBox(height: 3),
        _SecondaryAction(
          label: l10n.paywallRestore,
          onTap: () {
            Navigator.of(context).pop();
            onRestore?.call();
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
          GmTicket(
            stub: const SizedBox(height: 1),
            child: GmTicketFace(
              title: l10n.paywallTitle,
              pitch: l10n.paywallPitch,
              price: '—',
            ),
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
            label: l10n.edgeSeeFree,
            onTap: () => Navigator.of(context).pop(),
          ),
        ],
      );

  /// ⭐ 旅游产品的关键承诺:买了不马上开始烧有效期。
  /// 放在**存根位**(撕下去的那半)——它讲的正是"什么时候撕"。
  Widget _clockClause(
          BuildContext context, GmPalette gm, AppLocalizations l10n) =>
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
          Text(l10n.paywallClockBody,
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
Future<bool> ensurePassActivated(
  BuildContext context,
  WidgetRef ref,
  Entitlements ent,
) async {
  if (ent.isActive) return true;
  if (!ent.isPurchasedNotActivated) return false;

  final ok = await showModalBottomSheet<bool>(
    context: context,
    isScrollControlled: true,
    backgroundColor: Colors.transparent,
    barrierColor: context.gm.ink.withValues(alpha: 0.42),
    builder: (_) => const ActivatePassSheet(),
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
  const ActivatePassSheet({super.key});

  @override
  ConsumerState<ActivatePassSheet> createState() => _ActivatePassSheetState();
}

class _ActivatePassSheetState extends ConsumerState<ActivatePassSheet> {
  ActivateStep _step = ActivateStep.confirm;
  DateTime? _expiresAt;

  /// 确认页预告的结束时刻。在 initState 定一次 —— 每次 build 重算会让
  /// 用户盯着的那个时间一直往后跳。
  late final DateTime _projectedEnd = DateTime.now().add(_kPassDuration);

  Future<void> _activate() async {
    setState(() => _step = ActivateStep.activating);
    final updated = await activatePass(ref);
    ref.invalidate(entitlementsProvider);
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
              torn: torn,
              dim: _step == ActivateStep.activating,
              stub: _stub(gm, l10n),
              child: GmTicketFace(
                title: l10n.paywallTitle,
                pitch: l10n.paywallPitch,
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
          Text(l10n.activateSheetTitle,
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
          Text(l10n.activateFailBody,
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
