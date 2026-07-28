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
class PaywallSheetContent extends StatelessWidget {
  const PaywallSheetContent({super.key, this.onBuy, this.onRestore});

  final VoidCallback? onBuy;
  final VoidCallback? onRestore;

  @override
  Widget build(BuildContext context) {
    final gm = context.gm;
    final l10n = AppLocalizations.of(context)!;
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
              label: l10n.paywallBuy,
              onTap: () {
                Navigator.of(context).pop();
                onBuy?.call();
              },
            ),
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
