/// 付费墙:**三个触发点共用一个**(语音第二件 / 识别额度耗尽 / AI 问答)。
///
/// 三档强度(避免反复打扰,见 memory monetization-plan):
///   第 2 件点语音     → 轻提示条 `showPaywallHint`
///   同一件再点/点了解 → 完整付费页 `showPaywallSheet`
///   识别额度耗尽      → 完整付费页(强节点)
///
/// ⚠️ 付费墙建在**现场体验**(识别/语音/问答),不建在**内容**——
/// 浏览、搜索、完整文字讲解永远免费,所以这里明说"始终免费"那一行,
/// 让用户知道自己不是被锁在内容外面。
library;

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import 'package:gomuseum_app/features/payment/data/entitlements.dart';

import 'package:gomuseum_app/l10n/app_localizations.dart';
import 'package:gomuseum_app/theme/gm_palette.dart';
import 'package:gomuseum_app/theme/gm_theme_x.dart';
import 'package:gomuseum_app/theme/gm_tokens.dart';
import 'package:gomuseum_app/ui/gm/gm_ticket_button.dart';

/// 轻提示条:第一次撞墙时只轻碰一下,不打断现场体验。
void showPaywallHint(BuildContext context, {VoidCallback? onLearnMore}) {
  final l10n = AppLocalizations.of(context)!;
  ScaffoldMessenger.of(context).showSnackBar(
    SnackBar(
      content: Text(l10n.audioLockedHint),
      duration: const Duration(seconds: 4),
      action: SnackBarAction(
        label: l10n.paywallBuy,
        onPressed: onLearnMore ?? () => showPaywallSheet(context),
      ),
    ),
  );
}

/// 完整付费页。[reason] 仅用于埋点区分是哪一档触发的。
Future<void> showPaywallSheet(
  BuildContext context, {
  String reason = 'unknown',
  VoidCallback? onBuy,
  VoidCallback? onRestore,
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

/// 抽出便于单测(不依赖 showModalBottomSheet)。
class PaywallSheetContent extends ConsumerWidget {
  const PaywallSheetContent({super.key, this.onBuy, this.onRestore});

  final VoidCallback? onBuy;
  final VoidCallback? onRestore;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final gm = context.gm;
    final l10n = AppLocalizations.of(context)!;
    // 游客先登录再买:通票挂账号,游客买了换手机就永久拿不回(后端也会 403 拦)
    final canBuy = ref.watch(entitlementsProvider).value?.canPurchase ?? false;
    return Container(
      decoration: BoxDecoration(
        color: gm.surface,
        borderRadius: const BorderRadius.vertical(top: Radius.circular(4)),
        border: Border.all(color: gm.line),
      ),
      padding: const EdgeInsets.fromLTRB(26, 20, 26, 28),
      child: SafeArea(
        top: false,
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(l10n.paywallTitle,
                style: GmText.serif(size: 22, weight: FontWeight.w700)),
            const SizedBox(height: 12),
            Text(l10n.paywallPitch,
                style: GmText.sans(size: 14, color: gm.sub, height: 1.5)),
            const SizedBox(height: 16),
            // ⭐ 旅游产品的关键承诺:买了不马上开始烧有效期
            _note(gm, l10n.paywallClockNote),
            const SizedBox(height: 8),
            // 让用户知道自己没被锁在内容外面(付费墙在现场体验,不在内容)
            _note(gm, l10n.paywallFreeAlways),
            const SizedBox(height: 22),
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
            if (!canBuy) ...[
              const SizedBox(height: 8),
              Text(l10n.paywallLoginWhy,
                  textAlign: TextAlign.center,
                  style: GmText.sans(size: 11.5, color: gm.faint)),
            ],
            const SizedBox(height: 10),
            Center(
              child: GestureDetector(
                onTap: () {
                  Navigator.of(context).pop();
                  onRestore?.call();
                },
                child: Padding(
                  padding: const EdgeInsets.symmetric(vertical: 8),
                  child: Text(l10n.paywallRestore,
                      style: GmText.sans(size: 13, color: gm.sub)),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _note(GmPalette gm, String text) => Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Padding(
            padding: const EdgeInsets.only(top: 6),
            child: Container(width: 3, height: 3, color: gm.faint),
          ),
          const SizedBox(width: 8),
          Expanded(
            child: Text(text,
                style: GmText.sans(size: 12.5, color: gm.sub, height: 1.45)),
          ),
        ],
      );
}

/// 已购但未开始计时 → 弹确认再激活。返回 true 表示现在已生效、调用方可继续。
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

  final l10n = AppLocalizations.of(context)!;
  final ok = await showDialog<bool>(
    context: context,
    builder: (c) => AlertDialog(
      title: Text(l10n.activateTitle, style: GmText.serif(size: 17)),
      content:
          Text(l10n.activateBody, style: GmText.sans(size: 13, height: 1.5)),
      actions: [
        TextButton(
          onPressed: () => Navigator.of(c).pop(false),
          child: Text(l10n.activateLater),
        ),
        TextButton(
          onPressed: () => Navigator.of(c).pop(true),
          child: Text(l10n.activateConfirm),
        ),
      ],
    ),
  );
  if (ok != true) return false;

  final updated = await activatePass(ref);
  ref.invalidate(entitlementsProvider);
  return updated?.isActive ?? false;
}
