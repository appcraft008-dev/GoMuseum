/// 权益页四态(Claude Design `benefits-states.jsx`)。
///
/// ⭐ **已购之后这一页不再是商店**。四态各有主角:
///   未购    → 免费额度 + 功能清单 + 一张待售的票
///   已购未激活 → 「还没开始计时」(主角) + 开始按钮
///   生效中  → 撕开的票 + 到期日 + 已解锁清单 + 购买记录
///   已到期  → 褪色的用过的票 + 恢复后的免费额度 + 再来一张
///
/// 此前这一页无论什么状态都摆着购买按钮 —— 已付费用户进来看到的还是商店,
/// 会以为没买成功(2026-09-02 真机实测导致重复购买)。
///
/// ⚠️ 整页原本是**硬编码中文**的原生 Material,一个 l10n 键都没有。
/// 重做顺带补齐十语 —— App 支持十种语言,这一页却只有中文。
library;

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:in_app_purchase/in_app_purchase.dart';

import 'package:gomuseum_app/core/services/iap_service.dart';
import 'package:gomuseum_app/features/payment/data/entitlements.dart';
import 'package:gomuseum_app/features/payment/data/pass_history.dart';
import 'package:gomuseum_app/features/payment/data/pass_product.dart';
import 'package:gomuseum_app/features/payment/presentation/providers/benefits_provider.dart';
import 'package:gomuseum_app/features/payment/presentation/widgets/benefits_sections.dart';
import 'package:gomuseum_app/features/payment/presentation/widgets/gm_ticket.dart';
import 'package:gomuseum_app/features/payment/presentation/widgets/paywall_sheet.dart';
import 'package:gomuseum_app/l10n/app_localizations.dart';
import 'package:gomuseum_app/theme/gm_palette.dart';
import 'package:gomuseum_app/theme/gm_theme_x.dart';
import 'package:gomuseum_app/theme/gm_tokens.dart';
import 'package:gomuseum_app/ui/gm/gm_icon.dart';
import 'package:gomuseum_app/ui/gm/gm_ticket_button.dart';

class BenefitsPage extends ConsumerStatefulWidget {
  const BenefitsPage({super.key, this.autoRestore = false});

  /// 从付费墙的「恢复购买」进来时为 true:IAP 就绪后自动跑一次恢复,
  /// 免得已购用户落在购买页上以为要再买一次。
  final bool autoRestore;

  @override
  ConsumerState<BenefitsPage> createState() => _BenefitsPageState();
}

class _BenefitsPageState extends ConsumerState<BenefitsPage> {
  late final IapService _iapService;
  bool _isPurchasing = false;

  /// 收据冲突:**不是可重试的失败**,所以它是一个状态而不是一条 SnackBar。
  /// 弹完就消失的提示会让用户反复点购买 —— 而这条路永远走不通。
  bool _conflict = false;

  @override
  void initState() {
    super.initState();
    _iapService = IapService();
    _initializeIap();
  }

  Future<void> _initializeIap() async {
    var success = false;
    try {
      success = await _iapService.initialize(
        onPurchaseUpdated: _handlePurchaseUpdate,
        onError: (error) {
          if (!mounted) return;
          _toast(AppLocalizations.of(context)!.purchaseFailed);
          setState(() => _isPurchasing = false);
        },
      );
    } catch (_) {
      // 商店不可用(无 Play 服务的设备、测试环境)时 isAvailable() 直接抛。
      // 这一页的其余部分**不该跟着死** —— 用户还要在这里看自己的通票状态。
    }
    if (!mounted) return;
    if (success && widget.autoRestore) await _restorePurchases();
  }

  /// 返回值决定 IapService 是否 completePurchase —— 未验证成功绝不 complete,
  /// 否则 Consumable 被消耗掉、用户付了钱永久拿不回来(见 IapService 注释)。
  Future<bool> _handlePurchaseUpdate(PurchaseDetails purchase) async {
    var outcome = VerifyOutcome.failed;
    if (purchase.status == PurchaseStatus.purchased ||
        purchase.status == PurchaseStatus.restored) {
      outcome = await ref
          .read(benefitsStateProvider.notifier)
          .verifyAndUpdateBenefits(purchase);
      ref.invalidate(entitlementsProvider);
      ref.invalidate(passHistoryProvider);

      if (mounted) {
        final l10n = AppLocalizations.of(context)!;
        switch (outcome) {
          case VerifyOutcome.ok:
            _toast(l10n.purchaseSuccess);
          case VerifyOutcome.conflict:
            // 换成整屏说明:重试没有意义,得换账号
            setState(() => _conflict = true);
          case VerifyOutcome.failed:
            _toast(l10n.purchaseVerifyPending);
        }
      }
    }
    if (mounted) setState(() => _isPurchasing = false);
    return outcome == VerifyOutcome.ok;
  }

  void _toast(String msg) =>
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(msg)));

  Future<void> _buy() async {
    setState(() => _isPurchasing = true);
    final ok = await _iapService.purchaseProduct(IapService.kParisPass7d);
    if (!ok && mounted) {
      _toast(AppLocalizations.of(context)!.purchaseFailed);
      setState(() => _isPurchasing = false);
    }
  }

  Future<void> _restorePurchases() async {
    try {
      await _iapService.restorePurchases();
    } catch (_) {
      if (mounted) _toast(AppLocalizations.of(context)!.purchaseFailed);
    }
  }

  Future<void> _activate() async {
    final ent = ref.read(entitlementsProvider).value;
    if (ent == null) return;
    await ensurePassActivated(context, ref, ent);
  }

  @override
  void dispose() {
    _iapService.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final gm = context.gm;
    final l10n = AppLocalizations.of(context)!;
    final entAsync = ref.watch(entitlementsProvider);
    final ent = entAsync.value;
    final purchased =
        ent != null && (ent.isActive || ent.isPurchasedNotActivated);

    return Scaffold(
      backgroundColor: gm.surface,
      body: SafeArea(
        child: Column(
          children: [
            _topBar(
                gm, l10n, purchased ? l10n.benefitsMyPass : l10n.viewBenefits),
            Expanded(
              child: RefreshIndicator(
                onRefresh: () async {
                  ref.invalidate(entitlementsProvider);
                  ref.invalidate(passHistoryProvider);
                  await ref.read(benefitsStateProvider.notifier).refresh();
                },
                child: ListView(
                  padding: const EdgeInsets.fromLTRB(20, 0, 20, 24),
                  children: _body(gm, l10n, entAsync, ent),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _topBar(GmPalette gm, AppLocalizations l10n, String title) =>
      Container(
        padding: const EdgeInsets.fromLTRB(18, 12, 18, 11),
        decoration: BoxDecoration(
          border: Border(bottom: BorderSide(color: gm.line)),
        ),
        child: Row(
          children: [
            GestureDetector(
              behavior: HitTestBehavior.opaque,
              onTap: () => Navigator.of(context).maybePop(),
              child: GmIcon(GmIcons.back, size: 20, color: gm.ink),
            ),
            Expanded(
              child: Text(
                title,
                textAlign: TextAlign.center,
                style: GmText.serif(
                    size: 15,
                    weight: FontWeight.w700,
                    letterSpacing: context.gmLetterSpacing(0.5)),
              ),
            ),
            GestureDetector(
              behavior: HitTestBehavior.opaque,
              onTap: _restorePurchases,
              child: Text('↻', style: GmText.sans(size: 15, color: gm.faint)),
            ),
          ],
        ),
      );

  List<Widget> _body(
    GmPalette gm,
    AppLocalizations l10n,
    AsyncValue<Entitlements> entAsync,
    Entitlements? ent,
  ) {
    if (_conflict) return _conflictState(gm, l10n);
    if (entAsync.isLoading && ent == null) {
      return [
        const Padding(
          padding: EdgeInsets.only(top: 60),
          child: Center(child: CircularProgressIndicator()),
        ),
      ];
    }
    // ⚠️ `Entitlements.unknown` **不是 null** —— 它是离线回退,state 恰好是
    // not_purchased。少判一个 known,断网的已购用户就会看到一个购买页。
    if (ent == null || !ent.known) return _unknownState(gm, l10n);
    if (ent.isActive) return _activeState(gm, l10n, ent);
    if (ent.isPurchasedNotActivated) return _unactivatedState(gm, l10n, ent);
    if (ent.isExpired) {
      // 用过的那张票要有完整起止才画得出存根;拿不到历史就退回未购态,
      // 不去编一张票出来。
      final used = ref
          .watch(passHistoryProvider)
          .value
          ?.where((r) => r.hasRunItsCourse)
          .firstOrNull;
      if (used != null) return _freeAfterExpiry(gm, l10n, ent, used);
    }
    return _freeState(gm, l10n, ent);
  }

  // ── 态 1 · 免费用户(未购)──
  List<Widget> _freeState(
      GmPalette gm, AppLocalizations l10n, Entitlements ent) {
    final total = ent.freeRecognitionsTotal;
    final left = ent.freeRecognitionsLeft;
    return [
      BenSectionHead(l10n.benefitsSecFreeQuota),
      BenQuotaRow(
        label: l10n.benefitsRecognition,
        // 后端给的是**剩余**,进度条要的是已用 —— 这里换算,别把剩余画成已用
        used: (total != null && left != null)
            ? (total - left).clamp(0, total)
            : null,
        total: total,
      ),
      Padding(
        padding: const EdgeInsets.only(top: 7),
        child: Text(l10n.benefitsFreeAudioNote,
            style: GmText.sans(size: 11.5, color: gm.faint, height: 1.6)),
      ),
      BenSectionHead(l10n.benefitsSecFeatures),
      const SizedBox(height: 4),
      ..._features(l10n, unlocked: false),
      BenSectionHead(l10n.benefitsSecBuyable),
      const SizedBox(height: 10),
      _saleTicket(l10n),
      const SizedBox(height: 18),
      _buyCta(l10n, ent),
      const SizedBox(height: 3),
      BenSecondaryAction(label: l10n.paywallRestore, onTap: _restorePurchases),
    ];
  }

  // ── 态 2 · 已购未激活:主角是「还没开始计时」──
  List<Widget> _unactivatedState(
      GmPalette gm, AppLocalizations l10n, Entitlements ent) {
    return [
      const SizedBox(height: 16),
      GmTicket(
        stub: GmTicketStubLine(
            label: l10n.ticketStub, value: l10n.ticketStubPending),
        child: GmTicketFace(
          title: l10n.paywallTitle,
          pitch: l10n.paywallPitch,
        ),
      ),
      BenNotice(
        head: l10n.benefitsNotStartedHead,
        body: l10n.benefitsNotStartedBody,
        // 30 天不激活会作废 —— 后端 ACTIVATION_WINDOW 真的会没收,必须说
        note: l10n.paywallLapseNote,
      ),
      // 已经买了,截止日期就不是抽象的了:告诉他具体哪天前要激活
      if (ent.activateBy != null)
        Padding(
          padding: const EdgeInsets.only(top: 8),
          child: Text(
            l10n.ticketDateTime(ent.activateBy!, ent.activateBy!),
            style: GmText.serif(
                size: 13, weight: FontWeight.w700, color: gm.accentDeep),
          ),
        ),
      BenSectionHead(l10n.benefitsSecIncluded),
      const SizedBox(height: 4),
      ..._features(l10n, unlocked: true, onlyPaid: true),
      _museumsLine(gm, l10n),
      const SizedBox(height: 18),
      GmTicketButton(label: l10n.benefitsStartNow, onTap: _activate),
      Padding(
        padding: const EdgeInsets.only(top: 11),
        child: Text(l10n.benefitsStartNowNote,
            textAlign: TextAlign.center,
            style: GmText.sans(size: 11.5, color: gm.faint)),
      ),
    ];
  }

  // ── 态 3 · 生效中 ──
  List<Widget> _activeState(
      GmPalette gm, AppLocalizations l10n, Entitlements ent) {
    final exp = ent.expiresAt;
    final daysLeft = exp == null
        ? null
        : (exp.difference(DateTime.now()).inHours / 24).ceil().clamp(0, 999);
    return [
      const SizedBox(height: 16),
      GmTicket(
        torn: 1,
        stub: exp == null
            // 契约:可缺字段不裸取。active 却没有 expires_at 是后端异常,
            // 显示 "—" 而不是编一个日期。
            ? GmTicketStubLine(label: l10n.ticketValidUntil, value: '—')
            : BenStubDate(
                label: l10n.ticketValidUntil,
                value: l10n.ticketDateTime(exp, exp),
                trailing: l10n.ticketDaysLeft(daysLeft!),
              ),
        child: GmTicketFace(
          title: l10n.paywallTitle,
          pitch: l10n.paywallPitch,
        ),
      ),
      BenSectionHead(l10n.benefitsSecUnlocked),
      BenQuotaRow(
        label: l10n.benefitsRecognition,
        unlimitedLabel: l10n.unlimited,
      ),
      const SizedBox(height: 6),
      ..._features(l10n, unlocked: true, onlyPaid: true, skipRecognition: true),
      _museumsLine(gm, l10n),
      ..._purchaseRecords(gm, l10n),
    ];
  }

  // ── 态 4 · 已到期 ──
  List<Widget> _freeAfterExpiry(
      GmPalette gm, AppLocalizations l10n, Entitlements ent, PassRecord used) {
    final total = ent.freeRecognitionsTotal;
    final left = ent.freeRecognitionsLeft;
    return [
      const SizedBox(height: 14),
      GmTicket(
        torn: 1,
        faded: true,
        stub: BenStubDate(
          label: l10n.benefitsEndedAt,
          value: l10n.ticketDateTime(used.expiresAt!, used.expiresAt!),
          muted: true,
        ),
        child: GmTicketFace(
          title: l10n.paywallTitle,
          pitch: l10n.paywallPitch,
        ),
      ),
      Padding(
        padding: const EdgeInsets.only(top: 12),
        child: Text(l10n.benefitsExpiredBody,
            style: GmText.sans(size: 12.5, color: gm.sub, height: 1.7)),
      ),
      BenSectionHead(l10n.benefitsSecCurrentQuota),
      BenQuotaRow(
        label: l10n.benefitsRecognition,
        used: (total != null && left != null)
            ? (total - left).clamp(0, total)
            : null,
        total: total,
      ),
      BenSectionHead(l10n.benefitsSecBuyAnother),
      const SizedBox(height: 10),
      _saleTicket(l10n),
      const SizedBox(height: 18),
      _buyCta(l10n, ent),
      const SizedBox(height: 3),
      BenSecondaryAction(label: l10n.paywallRestore, onTap: _restorePurchases),
    ];
  }

  // ── 边 1 · 权益读不到(离线)──
  // ⚠️ 绝不能说「登录后购买」:用户可能已登录,只是网络断了。
  List<Widget> _unknownState(GmPalette gm, AppLocalizations l10n) => [
        const SizedBox(height: 16),
        GmTicket(
          // 空存根 + 「—」价格来表达"读不到",而不是叠一层透明度
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
        BenSecondaryAction(
          label: l10n.edgeSeeFree,
          onTap: () => Navigator.of(context).maybePop(),
        ),
      ];

  // ── 边 3 · 收据冲突 ──
  // ⚠️ 重试永远不会成功,所以这里没有「再试一次」。
  List<Widget> _conflictState(GmPalette gm, AppLocalizations l10n) => [
        const SizedBox(height: 16),
        Text(l10n.edgeConflictTitle,
            style: GmText.serif(
                size: 18,
                weight: FontWeight.w700,
                height: 1.35,
                letterSpacing: context.gmLetterSpacing(0.5))),
        Padding(
          padding: const EdgeInsets.only(top: 8),
          child: Text(l10n.edgeConflictBody,
              style: GmText.sans(size: 13, color: gm.sub, height: 1.75)),
        ),
        const SizedBox(height: 15),
        GmTicket(
          faded: true,
          // ⚠️ 设计稿在存根位写了对方邮箱(v···@gmail.com)。**不显示** ——
          // 那是别人的账号标识,后端也没给(409 只回 reason)。
          // 泄露他人邮箱换不来任何用户能用上的信息。
          stub: GmTicketStubLine(
            label: l10n.edgeConflictBound,
            value: l10n.edgeConflictOther,
          ),
          child: GmTicketFace(
            title: l10n.paywallTitle,
            pitch: l10n.paywallPitch,
          ),
        ),
        Padding(
          padding: const EdgeInsets.only(top: 14),
          child: Text(l10n.edgeConflictHelp,
              style: GmText.sans(size: 12, color: gm.faint, height: 1.7)),
        ),
        const SizedBox(height: 18),
        GmTicketButton(
          label: l10n.edgeSwitchAccount,
          onTap: () {
            setState(() => _conflict = false);
            context.push('/login');
          },
        ),
        const SizedBox(height: 3),
        BenSecondaryAction(
          label: l10n.edgeContactSupport,
          onTap: () => _toast(l10n.featureComingSoon(l10n.edgeContactSupport)),
        ),
      ];

  // ── 共用零件 ──

  Widget _saleTicket(AppLocalizations l10n) => GmTicket(
        stub: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(l10n.paywallClockHead,
                style: GmText.serif(
                    size: 13.5,
                    weight: FontWeight.w700,
                    color: context.gm.accentDeep,
                    height: 1.4)),
            const SizedBox(height: 4),
            Text(l10n.paywallClockBody,
                style:
                    GmText.sans(size: 12, color: context.gm.sub, height: 1.6)),
            const SizedBox(height: 6),
            // 合规:后端真会作废未激活的票,购买前必须告知(见 ACTIVATION_WINDOW)
            Text(l10n.paywallLapseNote,
                style: GmText.sans(
                    size: 11, color: context.gm.faint, height: 1.55)),
          ],
        ),
        child: GmTicketFace(
          title: l10n.paywallTitle,
          pitch: l10n.paywallPitch,
          price: ref.watch(passPriceProvider).value,
          priceNote: l10n.paywallPriceNote,
        ),
      );

  /// 买票前必须登录:通票挂账号,游客买了换手机就永久拿不回。
  ///
  /// ⚠️ busy **只看购买中**,不看 IAP 是否初始化完。挂上 `_isLoading` 会让
  /// 按钮在商店还没连上时一直转圈 —— 用户盯着一个转圈的「获取通票」,
  /// 不知道在等什么;商店真没就绪时 `_buy()` 自己会给出提示。
  Widget _buyCta(AppLocalizations l10n, Entitlements ent) => GmTicketButton(
        label: ent.canPurchase ? l10n.paywallBuy : l10n.paywallLoginToBuy,
        busy: _isPurchasing,
        onTap: ent.canPurchase ? _buy : () => context.push('/login'),
      );

  List<Widget> _features(
    AppLocalizations l10n, {
    required bool unlocked,
    bool onlyPaid = false,
    bool skipRecognition = false,
  }) {
    final needs = l10n.benefitsNeedsPass;
    return [
      if (!onlyPaid)
        BenFeatureLine(
            label: l10n.benefitsFeatBrowse, on: true, needsPassLabel: needs),
      if (!onlyPaid)
        BenFeatureLine(
            label: l10n.benefitsFeatPresetQa, on: true, needsPassLabel: needs),
      if (!skipRecognition)
        BenFeatureLine(
            label: l10n.benefitsFeatRecognition,
            on: unlocked,
            needsPassLabel: needs),
      BenFeatureLine(
          label: l10n.benefitsFeatAllAudio,
          on: unlocked,
          needsPassLabel: needs),
      BenFeatureLine(
          label: l10n.benefitsFeatDeepAudio,
          on: unlocked,
          needsPassLabel: needs),
    ];
  }

  Widget _museumsLine(GmPalette gm, AppLocalizations l10n) => Padding(
        padding: const EdgeInsets.only(top: 11),
        child: Text(l10n.benefitsMuseums,
            style: GmText.sans(size: 11.5, color: gm.faint, height: 1.6)),
      );

  /// 购买记录。⚠️ **没有金额** —— `purchases.amount` 后端从来没写过,
  /// 而拿商店当前售价顶替是错的:那是"现在卖多少"不是"当时付了多少"。
  List<Widget> _purchaseRecords(GmPalette gm, AppLocalizations l10n) {
    final rows = ref.watch(passHistoryProvider).value ?? const <PassRecord>[];
    final withDate = rows.where((r) => r.purchasedAt != null).toList();
    if (withDate.isEmpty) return const [];
    return [
      BenSectionHead(l10n.benefitsSecPurchases),
      for (final r in withDate)
        Padding(
          padding: const EdgeInsets.symmetric(vertical: 11),
          child: Text(
            '${l10n.benefitsDateOnly(r.purchasedAt!)} · ${l10n.paywallTitle}',
            style: GmText.sans(size: 12.5, color: gm.sub),
          ),
        ),
    ];
  }
}
