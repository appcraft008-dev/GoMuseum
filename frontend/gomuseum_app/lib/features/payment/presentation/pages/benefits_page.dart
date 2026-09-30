/// 权益页四态(Claude Design `benefits-states.jsx`;态 2/3 已合并为「手里的票」,每张一样大)。
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

import 'package:gomuseum_app/core/router/app_router.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:in_app_purchase/in_app_purchase.dart';

import 'package:gomuseum_app/core/services/iap_service.dart';
import 'package:gomuseum_app/features/payment/data/entitlements.dart';
import 'package:gomuseum_app/features/payment/data/pass_history.dart';
import 'package:gomuseum_app/features/payment/data/pass_offer.dart';
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

/// 支持邮箱。收据冲突时用户唯一的人工出口(见 `_conflictState` 的注释)。
///
/// ⚠️ **必须与 Play Console「商店设置 → 商品详情 → 开发者联系方式 → 电子邮件」
/// 完全一致**。那个地址本来就对所有用户公开(商店页面上就能看到),所以在
/// App 内展示它不构成新增暴露;但两处不一致的话,用户发出来的求助会石沉大海。
///
/// ponytail: 用剪贴板而不是 `mailto:` —— 那需要引入 `url_launcher` 这个
/// **原生插件**,会改动插件树;本项目在 #434 已经被"CI 与出包解析出不同插件树"
/// 坑过一次,而那类问题只有真机能发现。复制地址零依赖、离线可用,
/// 而且把地址直接摆在界面上比藏在 mailto 后面更透明。
const kSupportEmail = 'appcraft008@gmail.com';

class BenefitsPage extends ConsumerStatefulWidget {
  const BenefitsPage({super.key, this.passId});

  /// `?pass=<product_id>`:从馆内进来时只卖**这家馆**的那张票。
  /// null = 不知道在哪家馆(首页/设置)→ 列出 `/me.offers` 的每一张。
  final String? passId;

  @override
  ConsumerState<BenefitsPage> createState() => _BenefitsPageState();
}

class _BenefitsPageState extends ConsumerState<BenefitsPage> {
  late final IapService _iapService;
  bool _isPurchasing = false;
  bool _isRestoring = false;

  /// Play 回放过来的购买计数。用来回答"这次恢复到底捞到东西没有" ——
  /// 光看 restorePurchases() 有没有抛异常是答不出来的,它不抛也可能一无所获。
  int _restoredSeen = 0;

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
    if (success) await _autoRestoreIfNoPass();
  }

  /// **无票才自动跑一次恢复,且全程静默** —— 只有真捞到东西才出声。
  ///
  /// 「Play 说你买过 + 后端说你没有权益」是**机器自己认得出来**的状态,
  /// 不该让用户先看懂「恢复购买」这个词、再自己判断该不该点。原来它是付费墙上
  /// 主 CTA 正下方的一条链接,而对买成功过的人它恒定是空操作(消耗型商品验证
  /// 成功即被消耗)—— 等于把异常路径摆在了主路径旁边。
  ///
  /// 已有票的人不跑:没有可恢复的东西,白白多一次 Play 查询。
  /// 权益读不到(离线)也不跑:那时验证注定失败,只会白弹一条"稍后重试"。
  Future<void> _autoRestoreIfNoPass() async {
    final ent = await ref.read(entitlementsProvider.future);
    if (!mounted) return;
    if (!ent.known || ent.isActive || ent.isPurchasedNotActivated) return;
    await _restorePurchases(silent: true);
  }

  /// 返回值决定 IapService 是否 completePurchase —— 未验证成功绝不 complete,
  /// 否则 Consumable 被消耗掉、用户付了钱永久拿不回来(见 IapService 注释)。
  Future<bool> _handlePurchaseUpdate(PurchaseDetails purchase) async {
    var outcome = VerifyOutcome.failed;
    if (purchase.status == PurchaseStatus.purchased ||
        purchase.status == PurchaseStatus.restored) {
      if (purchase.status == PurchaseStatus.restored) _restoredSeen++;
      outcome = await ref
          .read(benefitsStateProvider.notifier)
          .verifyAndUpdateBenefits(purchase);
      ref.invalidate(entitlementsProvider);
      ref.invalidate(passHistoryProvider);

      if (mounted) {
        final l10n = AppLocalizations.of(context)!;
        switch (outcome) {
          case VerifyOutcome.ok:
            // 恢复和刚付完钱要分开说:自动恢复后冒出「购买成功」,
            // 用户会以为又被扣了一次钱。
            _toast(purchase.status == PurchaseStatus.restored
                ? l10n.restoreSucceeded
                : l10n.purchaseSuccess);
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

  Future<void> _buy(String productId) async {
    setState(() => _isPurchasing = true);
    // 商品 ID 来自后端下发的票 —— 前端不认识任何一张具体的票
    final ok = await _iapService.purchaseProduct(productId);
    if (!ok && mounted) {
      _toast(AppLocalizations.of(context)!.purchaseFailed);
      setState(() => _isPurchasing = false);
    }
  }

  /// 恢复购买。**必须自己说话** —— 成功路径的反馈完全来自 Play 回放购买时的
  /// [_handlePurchaseUpdate];而通票是消耗型商品,验证成功后就被 completePurchase
  /// 消耗掉,**已消耗的购买不在 restorePurchases 列表里**。也就是说对一个买成功
  /// 过的人,这里恒定什么都捞不到 —— 那是最常见的情况,却也正是原来完全静默的
  /// 情况:不转圈、不提示,用户分不清"正在恢复""没有可恢复的""失败了"。
  ///
  /// 这个入口真正的用武之地只有一个:**付了钱但后端验证没成功**的窗口
  /// (购买还挂在 Play 名下没被消耗)。2026-09-02 那次 androidpublisher API
  /// 没启用就是这种局面。
  Future<void> _restorePurchases({bool silent = false}) async {
    if (_isRestoring) return;
    final seenBefore = _restoredSeen;
    setState(() => _isRestoring = true);
    try {
      await _iapService.restorePurchases();
      // Play 是通过 purchaseStream 异步回放的,restorePurchases() 返回时
      // 东西还没到。给它一个窗口再判断"什么都没来"。
      await Future<void>.delayed(const Duration(seconds: 3));
      if (!silent && mounted && _restoredSeen == seenBefore) {
        _toast(AppLocalizations.of(context)!.restoreNothingFound);
      }
    } catch (_) {
      if (!silent && mounted) {
        _toast(AppLocalizations.of(context)!.purchaseFailed);
      }
    } finally {
      if (mounted) setState(() => _isRestoring = false);
    }
  }

  /// 恢复期间按钮的文案:哑着比说错强,但什么都不说最差。
  ///
  /// ⚠️ `paywallRestore` 现在是**「已付款但没拿到通票？」而不是「恢复购买」**,
  /// 别改回术语。"恢复购买"是商店行话,普通用户读不出它什么时候该点;而这个入口
  /// 恰恰只在上面那一个场景有用,不如直接把场景写在标签上。同理 `restoreNothingFound`
  /// 说的是「没有找到未完成的付款」——跟着标签的口径走,而不是"没有可恢复的购买"。
  String _restoreLabel(AppLocalizations l10n) =>
      _isRestoring ? l10n.restoreInProgress : l10n.paywallRestore;

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
            // 这里曾有一个无标签的 ↻ 恢复购买:图标形态最难被读懂,
            // 又和下拉刷新(RefreshIndicator)撞在一起。恢复已自动化,
            // 手动兜底只在页面底部留一处。占位保持标题居中。
            const SizedBox(width: 20),
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
    if (ent.isActive || ent.isPurchasedNotActivated) {
      return _heldState(gm, l10n, ent);
    }
    if (ent.isExpired) {
      // 用过的那张票要有完整起止才画得出存根;拿不到历史就退回未购态,
      // 不去编一张票出来。
      final history = ref.watch(passHistoryProvider).value;
      final used = history?.where((r) => r.hasRunItsCourse).firstOrNull;
      if (used != null) return _freeAfterExpiry(gm, l10n, ent, used);
      // **买了却从没激活、窗口过了作废** —— 与"7 天用完"是两种经历。
      // 曾经只认前者,这类票被整个过滤掉、页面退回未购态:用户付了钱、
      // 票被作废,界面却表现得像他从没买过(真机实测)。撞契约 I20 ——
      // 事前在售票上披露了「30 天失效」,事后却什么都不说。
      final lapsed = history?.where((r) => r.lapsedUnactivated).firstOrNull;
      if (lapsed != null) return _lapsedState(gm, l10n, ent, lapsed);
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
        left: left,
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
      ..._saleSection(l10n, ent),
      const SizedBox(height: 3),
      BenSecondaryAction(label: _restoreLabel(l10n), onTap: _restorePurchases),
    ];
  }

  // ── 态 2/3 · 手里有票(生效中 / 未激活,可能不止一张)──
  //
  // ⚠️ 这里曾经只有**一个主票位**:谁生效就放大谁,其余的票缩成一行小字。
  // 持两张票时真机实测两种误读(2026-09-29):先买巴黎后买荷兰 → 荷兰那张只剩
  // 「到期日待填」一行,像付了钱没拿到东西;激活荷兰后它顶掉主位 → 仍在有效期的
  // 巴黎票反倒成了小字。所以**每张票一样大**,每张票自己写清管哪里、什么状态。
  //
  // 也不再有全局的「已解锁 · 识别不限次」:按 D7 不限次只在票覆盖的馆里,
  // 两张票时那样写就是错的。票面卖点已经写了这张票解锁什么。
  List<Widget> _heldState(
      GmPalette gm, AppLocalizations l10n, Entitlements ent) {
    final held = _held(ent);
    final pending = held.where((p) => p.isPurchasedNotActivated).toList();
    return [
      for (final p in held) ...[
        const SizedBox(height: 16),
        _heldTicket(gm, l10n, p),
      ],
      // 一张都没生效时才讲「还没开始计时」并给开始按钮。已有生效的票时不给:
      // 不带馆的 /activate 会先认到那张生效的票,按了什么都不会发生。
      if (!ent.isActive && pending.isNotEmpty) ...[
        BenNotice(
          head: l10n.benefitsNotStartedHead,
          body: l10n.benefitsNotStartedBody('${pending.first.days}'),
          // 30 天不激活会作废 —— 后端 ACTIVATION_WINDOW 真的会没收,必须说
          note: l10n.paywallLapseNote,
        ),
        // 不止一张未激活票时不放「开始」:不知道用户要撕哪张,猜错一张就是替他
        // 烧掉另一个国家的 7 天。到那家馆用的时候按馆激活(ensurePassActivated)。
        if (pending.length == 1) ...[
          const SizedBox(height: 18),
          GmTicketButton(
              label: l10n.benefitsStartNow('${pending.first.days}'),
              onTap: _activate),
          Padding(
            padding: const EdgeInsets.only(top: 11),
            child: Text(l10n.benefitsStartNowNote,
                textAlign: TextAlign.center,
                style: GmText.sans(size: 11.5, color: gm.faint)),
          ),
        ],
      ],
      // 手里的票管不到的馆,识别仍走免费额度(D7)。还有没握在手里的票在售
      // = 还有票外的馆 —— ponytail: 用在售票代替"未覆盖的馆",够准且不用再要数据。
      if (_sellable(ent).isNotEmpty) ...[
        const SizedBox(height: 8),
        BenQuotaRow(
          label: l10n.benefitsOtherMuseumsRecognition,
          left: ent.freeRecognitionsLeft,
          total: ent.freeRecognitionsTotal,
        ),
      ],
      ..._moreToBuy(l10n, ent),
      ..._purchaseRecords(gm, l10n, ent),
    ];
  }

  /// 手里的票:生效中的在前、先到期的最前(最该先用掉);未激活的随后、先作废的在前。
  /// 老后端不给 passes → 按总状态退回一张无名票(标题「7 日通票」,不编地名)。
  List<OwnedPass> _held(Entitlements ent) {
    int by(DateTime? a, DateTime? b) =>
        (a ?? DateTime(9999)).compareTo(b ?? DateTime(9999));
    final active = ent.passes.where((p) => p.isActive).toList()
      ..sort((a, b) => by(a.expiresAt, b.expiresAt));
    final pending = ent.passes.where((p) => p.isPurchasedNotActivated).toList()
      ..sort((a, b) => by(a.activateBy, b.activateBy));
    final held = [...active, ...pending];
    if (held.isNotEmpty) return held;
    return [
      OwnedPass(
        productId: '',
        label: '',
        days: 7,
        state: ent.state,
        expiresAt: ent.expiresAt,
        activateBy: ent.activateBy,
      ),
    ];
  }

  Widget _heldTicket(GmPalette gm, AppLocalizations l10n, OwnedPass p) {
    final exp = p.expiresAt;
    final Widget stub;
    if (p.isActive) {
      stub = exp == null
          // 契约:可缺字段不裸取。active 却没有 expires_at 是后端异常,
          // 显示 "—" 而不是编一个日期。
          ? GmTicketStubLine(label: l10n.ticketValidUntil, value: '—')
          : BenStubDate(
              label: l10n.ticketValidUntil,
              value: l10n.ticketDateTime(exp, exp),
              trailing: l10n.ticketDaysLeft(
                  (exp.difference(DateTime.now()).inHours / 24)
                      .ceil()
                      .clamp(0, 999)),
            );
    } else {
      stub = Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          GmTicketStubLine(
              label: l10n.benefitsPassNotActivated,
              value: l10n.benefitsPassStartsOnFirstUse),
          if (p.activateBy != null)
            Padding(
              padding: const EdgeInsets.only(top: 6),
              child: Text(l10n.benefitsPassVoidAfter(p.activateBy!),
                  style: GmText.sans(size: 11, color: gm.faint)),
            ),
        ],
      );
    }
    return GmTicket(
      stamp: p.label.toUpperCase(),
      days: p.days,
      // 撕开 = 开始用了;未激活的票保持完整
      torn: p.isActive ? 1 : 0,
      stub: stub,
      child: GmTicketFace(
        title: passTitle(l10n, p.label, p.days, title: p.title),
        pitch: passPitch(context, _coversOf(pid: p.productId)),
        paidLabel: l10n.ticketPaid,
      ),
    );
  }

  // ── 态 4 · 已到期 ──
  // ── 态 4b · 买了没激活,窗口过了作废 ──
  //
  // 与 4 的区别全在**措辞**:他一天都没用过,说「7 天已经用完」是睁眼说瞎话。
  // 存根位也不能写"结束于" —— 这张票从来没有过到期日,写购买日才是真的。
  List<Widget> _lapsedState(GmPalette gm, AppLocalizations l10n,
      Entitlements ent, PassRecord lapsed) {
    final total = ent.freeRecognitionsTotal;
    final left = ent.freeRecognitionsLeft;
    final bought = lapsed.purchasedAt;
    return [
      const SizedBox(height: 14),
      GmTicket(
        stamp: _stampFor(ent, lapsed.productId),
        days: _daysOf(lapsed),
        // 不撕:撕开的语义是"用过了"。这张没被用过,只是作废了 —— 戳说明一切。
        faded: true,
        voidStamp: l10n.ticketVoid,
        stub: bought == null
            ? null
            : BenStubDate(
                label: l10n.benefitsBoughtOn,
                value: l10n.ticketDateTime(bought, bought),
                muted: true,
              ),
        // 不写 pitch:见 GmTicketFace.pitch
        child: GmTicketFace(
          title: _titleFor(l10n, ent, lapsed.productId, _daysOf(lapsed)),
          paidLabel: l10n.ticketPaid,
        ),
      ),
      Padding(
        padding: const EdgeInsets.only(top: 14),
        child: Text(
          l10n.benefitsLapsedHead,
          style: GmText.serif(size: 17, weight: FontWeight.w700),
        ),
      ),
      Padding(
        padding: const EdgeInsets.only(top: 6),
        child: Text(l10n.benefitsLapsedBody,
            style: GmText.sans(size: 12.5, color: gm.sub, height: 1.7)),
      ),
      BenSectionHead(l10n.benefitsSecCurrentQuota),
      BenQuotaRow(
        label: l10n.benefitsRecognition,
        left: left,
        total: total,
      ),
      BenSectionHead(l10n.benefitsSecBuyAnother),
      ..._saleSection(l10n, ent),
      const SizedBox(height: 20),
      BenSecondaryAction(label: _restoreLabel(l10n), onTap: _restorePurchases),
    ];
  }

  List<Widget> _freeAfterExpiry(
      GmPalette gm, AppLocalizations l10n, Entitlements ent, PassRecord used) {
    final total = ent.freeRecognitionsTotal;
    final left = ent.freeRecognitionsLeft;
    return [
      const SizedBox(height: 14),
      GmTicket(
        stamp: _stampFor(ent, used.productId),
        days: _daysOf(used),
        torn: 1,
        faded: true,
        // 撕线 + 褪色都太轻了(见 GmTicket.voidStamp 的说明):真机上这张票
        // 和下面在售的那张像双胞胎。作废戳是这一态唯一一眼能读出来的信号。
        voidStamp: l10n.ticketVoid,
        stub: BenStubDate(
          label: l10n.benefitsEndedAt,
          value: l10n.ticketDateTime(used.expiresAt!, used.expiresAt!),
          muted: true,
        ),
        // 不写 pitch:见 GmTicketFace.pitch
        child: GmTicketFace(
          title: _titleFor(l10n, ent, used.productId, _daysOf(used)),
          paidLabel: l10n.ticketPaid,
        ),
      ),
      Padding(
        padding: const EdgeInsets.only(top: 12),
        child: Text(l10n.benefitsExpiredBody('${_daysOf(used)}'),
            style: GmText.sans(size: 12.5, color: gm.sub, height: 1.7)),
      ),
      BenSectionHead(l10n.benefitsSecCurrentQuota),
      BenQuotaRow(
        label: l10n.benefitsRecognition,
        left: left,
        total: total,
      ),
      BenSectionHead(l10n.benefitsSecBuyAnother),
      ..._saleSection(l10n, ent),
      const SizedBox(height: 3),
      BenSecondaryAction(label: _restoreLabel(l10n), onTap: _restorePurchases),
    ];
  }

  // ── 边 1 · 权益读不到(离线)──
  // ⚠️ 绝不能说「登录后购买」:用户可能已登录,只是网络断了。
  List<Widget> _unknownState(GmPalette gm, AppLocalizations l10n) => [
        // 读不到权益就读不到在售的票 —— 不画票,也绝不编一张默认的(巴黎)票出来
        const SizedBox(height: 4),
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
          label: l10n.activateLater,
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
          stamp: _conflictOffer?.stampText ?? '',
          days: _conflictOffer?.days ?? 7,
          faded: true,
          // ⚠️ 设计稿在存根位写了对方邮箱(v···@gmail.com)。**不显示** ——
          // 那是别人的账号标识,后端也没给(409 只回 reason)。
          // 泄露他人邮箱换不来任何用户能用上的信息。
          stub: GmTicketStubLine(
            label: l10n.edgeConflictBound,
            value: l10n.edgeConflictOther,
          ),
          child: GmTicketFace(
            title: passTitle(
                l10n, _conflictOffer?.label ?? '', _conflictOffer?.days ?? 7,
                title: _conflictOffer?.title),
            paidLabel: l10n.ticketPaid,
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
            context.push(kLoginToUpgrade);
          },
        ),
        const SizedBox(height: 3),
        // ⚠️ 这个出口**是必需的,不是装饰**:票面不显示对方邮箱(隐私),
        // 用户很可能根本不知道该登哪个账号 —— 没有这条路他就彻底卡住。
        // 所以这里必须给出一个能真正联系上人的地址,不能是「即将推出」。
        BenSecondaryAction(
          label: '${l10n.edgeContactSupport} · $kSupportEmail',
          onTap: () async {
            await Clipboard.setData(const ClipboardData(text: kSupportEmail));
            if (mounted) _toast(l10n.edgeSupportCopied(kSupportEmail));
          },
        ),
      ];

  // ── 共用零件 ──

  /// 这一页该卖哪几张票。`?pass=` 给了就只卖那一张;否则 `/me.offers` 全列
  /// (不猜"第一张")。已经握在手里的票不再卖 —— 生效中/待激活时再买一张同样的票
  /// 只会让用户付两次钱。
  List<PassOffer> _sellable(Entitlements ent) {
    final held = ent.passes.map((p) => p.productId).toSet();
    return ent.offers
        .where((o) => widget.passId == null || o.productId == widget.passId)
        .where((o) => !held.contains(o.productId))
        .toList();
  }

  /// 售票区:每张在售票一张票面 + 一个购买按钮。一张都没有 → 「暂未开售」。
  List<Widget> _saleSection(AppLocalizations l10n, Entitlements ent) {
    final offers = _sellable(ent);
    if (offers.isEmpty) {
      return [BenNotice(head: l10n.passNotOnSale, body: '')];
    }
    return [
      for (final o in offers) ...[
        const SizedBox(height: 10),
        GmTicket(
          stamp: o.stampText,
          days: o.days,
          stub: _clockStub(l10n, o.days),
          child: saleTicketFace(context, ref, o),
        ),
        const SizedBox(height: 18),
        _buyCta(l10n, ent, o),
      ],
    ];
  }

  /// 生效中/待激活时,还有别的票可买(例如持巴黎票、从荷兰的馆点进来)。
  List<Widget> _moreToBuy(AppLocalizations l10n, Entitlements ent) {
    if (_sellable(ent).isEmpty) return const [];
    return [
      BenSectionHead(l10n.benefitsSecBuyAnother),
      ..._saleSection(l10n, ent),
    ];
  }

  Widget _clockStub(AppLocalizations l10n, int days) => Column(
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
          Text(l10n.paywallClockBody('$days'),
              style: GmText.sans(size: 12, color: context.gm.sub, height: 1.6)),
          const SizedBox(height: 6),
          // 合规:后端真会作废未激活的票,购买前必须告知(见 ACTIVATION_WINDOW)
          Text(l10n.paywallLapseNote,
              style:
                  GmText.sans(size: 11, color: context.gm.faint, height: 1.55)),
        ],
      );

  /// 买票前必须登录:通票挂账号,游客买了换手机就永久拿不回。
  ///
  /// ⚠️ busy **只看购买中**,不看 IAP 是否初始化完。挂上 `_isLoading` 会让
  /// 按钮在商店还没连上时一直转圈 —— 用户盯着一个转圈的「获取通票」,
  /// 不知道在等什么;商店真没就绪时 `_buy()` 自己会给出提示。
  Widget _buyCta(AppLocalizations l10n, Entitlements ent, PassOffer offer) =>
      GmTicketButton(
        label: ent.canPurchase ? l10n.paywallBuy : l10n.paywallLoginToBuy,
        busy: _isPurchasing,
        onTap: ent.canPurchase
            ? () => _buy(offer.productId)
            : () => context.push(kLoginToUpgrade),
      );

  /// 某张票覆盖的馆名:从在售票里找(已放出的馆,本地化)。找不到 → 空(用通用卖点)。
  List<String> _coversOf({Entitlements? ent, required String pid}) {
    final e = ent ?? ref.read(entitlementsProvider).value;
    return e?.offers.where((o) => o.productId == pid).firstOrNull?.covers ??
        const [];
  }

  /// 历史票的范围名:手里的票或在售票里认得出就用,认不出就留空(不编)。
  String _labelFor(Entitlements ent, String pid) =>
      ent.passes.where((p) => p.productId == pid).firstOrNull?.label ??
      ent.offers.where((o) => o.productId == pid).firstOrNull?.label ??
      '';

  String _stampFor(Entitlements ent, String pid) =>
      _labelFor(ent, pid).toUpperCase();

  String _titleFor(
          AppLocalizations l10n, Entitlements ent, String pid, int days) =>
      passTitle(l10n, _labelFor(ent, pid), days,
          title: ent.passes
                  .where((p) => p.productId == pid)
                  .firstOrNull
                  ?.title ??
              ent.offers.where((o) => o.productId == pid).firstOrNull?.title);

  /// 一张历史票管几天:有起止就按起止算,算不出退回 7。
  int _daysOf(PassRecord r) {
    final a = r.activatedAt, e = r.expiresAt;
    if (a == null || e == null) return 7;
    final d = (e.difference(a).inHours / 24).round();
    return d > 0 ? d : 7;
  }

  /// 收据冲突页那张票:不知道是哪张,用唯一在售的那张(多张时不画名字)。
  PassOffer? get _conflictOffer {
    final offers = ref.read(entitlementsProvider).value?.offers ?? const [];
    return offers.length == 1 ? offers.first : null;
  }

  List<Widget> _features(
    AppLocalizations l10n, {
    required bool unlocked,
  }) {
    final needs = l10n.benefitsNeedsPass;
    return [
      BenFeatureLine(
          label: l10n.benefitsFeatBrowse, on: true, needsPassLabel: needs),
      BenFeatureLine(
          label: l10n.benefitsFeatPresetQa, on: true, needsPassLabel: needs),
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

  /// 购买记录。⚠️ **没有金额** —— `purchases.amount` 后端从来没写过,
  /// 而拿商店当前售价顶替是错的:那是"现在卖多少"不是"当时付了多少"。
  List<Widget> _purchaseRecords(
      GmPalette gm, AppLocalizations l10n, Entitlements ent) {
    final rows = ref.watch(passHistoryProvider).value ?? const <PassRecord>[];
    final withDate = rows.where((r) => r.purchasedAt != null).toList();
    if (withDate.isEmpty) return const [];
    return [
      BenSectionHead(l10n.benefitsSecPurchases),
      for (final r in withDate)
        Padding(
          padding: const EdgeInsets.symmetric(vertical: 11),
          child: Text(
            '${l10n.benefitsDateOnly(r.purchasedAt!)} · ${_titleFor(l10n, ent, r.productId, _daysOf(r))}',
            style: GmText.sans(size: 12.5, color: gm.sub),
          ),
        ),
    ];
  }
}
