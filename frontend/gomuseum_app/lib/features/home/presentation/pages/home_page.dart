/// GoMuseum 首页 — 暖纸手册定稿（FinalHome）
///
/// 刊头 + 衬线标语 + 门票式识别 CTA + 免费额度提示 + 附近博物馆横滑卡片。
library;

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:gomuseum_app/core/network/image_request.dart';
import 'package:gomuseum_app/features/content/data/models/museum_summary_model.dart';
import 'package:gomuseum_app/features/guide/presentation/pages/guide_page.dart'
    show GuideArgs;
import 'package:gomuseum_app/features/history/presentation/providers/history_providers.dart';
import 'package:gomuseum_app/features/home/data/nearby.dart';
import 'package:gomuseum_app/features/payment/data/entitlements.dart';
import 'package:gomuseum_app/features/payment/data/pass_offer.dart';
import 'package:gomuseum_app/features/payment/presentation/widgets/paywall_sheet.dart'
    show passTitle;
import 'package:gomuseum_app/l10n/app_localizations.dart';
import 'package:gomuseum_app/theme/gm_palette.dart';
import 'package:gomuseum_app/theme/gm_theme_x.dart';
import 'package:gomuseum_app/ui/gm/gm.dart';

class HomePage extends ConsumerStatefulWidget {
  const HomePage({super.key});

  @override
  ConsumerState<HomePage> createState() => _HomePageState();
}

/// 首页横向边距。此前是散落在各处的字面量 26，而 _slogan/_quotaLine 漏了，
/// 于是那两块贴着屏幕边渲染。
const double _pagePadding = 26;

class _HomePageState extends ConsumerState<HomePage> {
  int _cardPage = 0;

  @override
  Widget build(BuildContext context) {
    final gm = context.gm;
    final l10n = AppLocalizations.of(context)!;
    final ent = ref.watch(entitlementsProvider).value;
    final nearbyAsync = ref.watch(nearbyProvider);
    final nearby = nearbyAsync.value;

    return SafeArea(
      bottom: false,
      child: LayoutBuilder(
        builder: (context, constraints) {
          return SingleChildScrollView(
            child: ConstrainedBox(
              constraints: BoxConstraints(minHeight: constraints.maxHeight),
              child: Padding(
                padding: const EdgeInsets.only(top: 16),
                child: Column(
                  children: [
                    _masthead(gm, l10n),
                    const SizedBox(height: 22),
                    _slogan(l10n),
                    Padding(
                      padding: const EdgeInsets.fromLTRB(26, 20, 26, 0),
                      child: GmTicketButton(
                        label: l10n.homeCtaRecognize,
                        icon: GmIcons.camera,
                        trailingIcon: GmIcons.arrowR,
                        fontSize: 18,
                        onTap: () => context.push('/camera'),
                      ),
                    ),
                    const SizedBox(height: 10),
                    _quotaLine(context, gm, l10n, ent),
                    Padding(
                      padding: const EdgeInsets.fromLTRB(26, 24, 26, 0),
                      child: GmSectionHead(
                        number: '01',
                        // 不知道用户在哪就不冒充「附近」(spec 2026-09-29 §一)
                        label: nearby?.mode == NearbyMode.none
                            ? l10n.homeMuseums
                            : l10n.homeNearby,
                        note: l10n.viewAll,
                        onNoteTap: () => context.go('/explore'),
                      ),
                    ),
                    const SizedBox(height: 14),
                    // 只列当前城市的馆:轮播长度不再随全局馆数增长,其余城市交给探索页。
                    // 加载中/失败:留白不塞占位馆(宁缺毋滥);探索页有完整重试入口
                    nearbyAsync.when(
                      loading: () => const SizedBox(height: 250),
                      error: (_, __) => const SizedBox(height: 250),
                      data: (n) {
                        final museums = n.museums;
                        if (museums.length != _cardCount) {
                          WidgetsBinding.instance.addPostFrameCallback(
                            (_) => mounted
                                ? setState(() => _cardCount = museums.length)
                                : null,
                          );
                        }
                        return _museumCards(museums);
                      },
                    ),
                    _pageDots(gm),
                    if (nearby?.mode == NearbyMode.none)
                      _enableLocation(gm, l10n),
                    ..._continueSection(gm, l10n),
                  ],
                ),
              ),
            ),
          );
        },
      ),
    );
  }

  /// 没有任何位置信号时的一行入口:点了才请求定位权限 —— 不在启动时弹。
  Widget _enableLocation(GmPalette gm, AppLocalizations l10n) =>
      GestureDetector(
        behavior: HitTestBehavior.opaque,
        onTap: () => requestLocation(ref),
        child: Padding(
          padding: const EdgeInsets.fromLTRB(26, 2, 26, 6),
          child: Row(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              GmIcon(GmIcons.pin, size: 14, color: gm.accent),
              const SizedBox(width: 6),
              Flexible(
                child: Text(l10n.homeEnableLocation,
                    style: GmText.sans(size: 12, color: gm.accent)),
              ),
            ],
          ),
        ),
      );

  /// 02 继续游览:最近识别过的作品(足迹现成数据),点一下回讲解页。
  /// 没有可回去的作品就整节不显示 —— 编号只编码真实内容。
  List<Widget> _continueSection(GmPalette gm, AppLocalizations l10n) {
    final seen = <String>{};
    final items = [
      for (final it in ref.watch(historyProvider).items)
        if (it.hasGuide && seen.add(it.qid!)) it,
    ].take(6).toList();
    if (items.isEmpty) return const [];
    return [
      Padding(
        padding: const EdgeInsets.fromLTRB(26, 18, 26, 0),
        child: GmSectionHead(number: '02', label: l10n.homeContinue),
      ),
      const SizedBox(height: 12),
      SizedBox(
        height: 150,
        child: ListView.separated(
          scrollDirection: Axis.horizontal,
          padding: const EdgeInsets.symmetric(horizontal: 26),
          itemCount: items.length,
          separatorBuilder: (_, __) => const SizedBox(width: 12),
          itemBuilder: (context, i) {
            final it = items[i];
            return GestureDetector(
              onTap: () => context.push(
                '/guide',
                extra: GuideArgs(
                    slug: it.museumSlug, qid: it.qid, imageUrl: it.thumbnail),
              ),
              child: SizedBox(
                width: 104,
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Container(
                      height: 104,
                      width: 104,
                      color: gm.chipBg,
                      child: it.thumbnail != null
                          ? Image.network(it.thumbnail!,
                              fit: BoxFit.cover,
                              headers: kImageRequestHeaders,
                              errorBuilder: (_, __, ___) => const SizedBox())
                          : null,
                    ),
                    const SizedBox(height: 6),
                    Text(it.artworkName,
                        maxLines: 2,
                        overflow: TextOverflow.ellipsis,
                        style: GmText.sans(size: 11.5, height: 1.3)),
                  ],
                ),
              ),
            );
          },
        ),
      ),
      const SizedBox(height: 16),
    ];
  }

  Widget _masthead(GmPalette gm, AppLocalizations l10n) {
    return Column(
      children: [
        Text(
          'GOMUSEUM',
          style:
              GmText.serif(size: 13, letterSpacing: 7, weight: FontWeight.w700),
        ),
        const SizedBox(height: 9),
        const GmDiamond(width: 150),
        const SizedBox(height: 9),
        Text(
          l10n.homePocketGuide,
          style: GmText.sans(
              size: 11,
              letterSpacing: context.gmLetterSpacing(3),
              color: gm.sub),
        ),
      ],
    );
  }

  Widget _slogan(AppLocalizations l10n) {
    // 标语本身带 `\n`（本意 2 行）。法语首行较长、27px 会被迫再折成 3 行；
    // FittedBox.scaleDown 把整块按可用宽度等比缩小到恰好 2 行（英/中已够宽、不缩）。
    // ⚠️ 必须给横向边距：scaleDown 缩到的是**可用宽度**，不留边距就等于缩到
    // 满屏宽、左右零留白贴着屏幕边——法语首页上肉眼可见（同页其它元素都是 26）。
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: _pagePadding),
      child: FittedBox(
        fit: BoxFit.scaleDown,
        child: Text(
          l10n.homeSlogan,
          textAlign: TextAlign.center,
          style: GmText.serif(size: 27, weight: FontWeight.w700, height: 1.55),
        ),
      ),
    );
  }

  // 已购通票/待激活时这条提示不该再说"免费还剩几次"——那对已付费用户是错误信息
  // （见 Entitlements.freeRecognitionsLeft 注释：通票生效期间该字段为 null）。
  // 已到期则退回免费额度文案，与 benefits_page 的 _freeAfterExpiry/_lapsedState
  // 是同一套"到期后当作免费用户看待"的口径，不再单独造一种措辞。
  // 整行做成可点击入口，跳去权益页——这也是免费用户了解"升级"具体是什么的路径。
  Widget _quotaLine(BuildContext context, GmPalette gm, AppLocalizations l10n,
      Entitlements? ent) {
    final text = quotaLineText(l10n, ent, Localizations.localeOf(context));
    return GestureDetector(
      behavior: HitTestBehavior.opaque,
      onTap: () => context.push('/benefits'),
      // 各语言长度差异大（德语/波兰语明显长于中日韩），FittedBox 保证单行不换行，
      // 与上方 _slogan 用同一手法——包括那里的横向边距，同样的理由。
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: _pagePadding),
        child: FittedBox(
          fit: BoxFit.scaleDown,
          child: Text(text, style: GmText.sans(size: 12, color: gm.sub)),
        ),
      ),
    );
  }

  /// 馆卡片走 A1 `GET /museums`(2026-07-26 API 化):上新馆自动出现在首页,
  /// 不再硬编码——此前卢浮宫卡片写死且无 slug,上线后点不动(同橘园 #300 教训)。
  Widget _museumCards(List<MuseumSummary> museums) {
    // 高度贴合内容(最高那张卡),不再写死:写死 344 时卡片下方留一大片空白,
    // 而字号放大/多语言时写死值又可能不够。卡片等高 = 整张卡都可点、无死区。
    // ponytail: 一次建全部卡片(不懒加载);首页只列当前城市的几家馆,够用。
    return SingleChildScrollView(
      key: const Key('home-museum-cards'),
      controller: _cardScrollController,
      scrollDirection: Axis.horizontal,
      padding: const EdgeInsets.only(left: 26, right: 26),
      physics: const _SnapScrollPhysics(itemExtent: _cardExtent),
      child: IntrinsicHeight(
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            for (var i = 0; i < museums.length; i++) ...[
              if (i > 0) const SizedBox(width: 14),
              _MuseumCard(
                museum: museums[i],
                onTap: () => context.push('/museum/${museums[i].slug}'),
              ),
            ],
          ],
        ),
      ),
    );
  }

  static const double _cardExtent = 268 + 14;
  int _cardCount = 0; // 当前馆数(分页点/滚动 clamp 用;API 到达后更新)

  late final ScrollController _cardScrollController = ScrollController()
    ..addListener(() {
      if (_cardCount == 0) return;
      final page = (_cardScrollController.offset / _cardExtent)
          .round()
          .clamp(0, _cardCount - 1);
      if (page != _cardPage) setState(() => _cardPage = page);
    });

  @override
  void dispose() {
    _cardScrollController.dispose();
    super.dispose();
  }

  Widget _pageDots(GmPalette gm) {
    return Padding(
      padding: const EdgeInsets.only(top: 10, bottom: 12),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          for (var i = 0; i < _cardCount; i++) ...[
            if (i > 0) const SizedBox(width: 6),
            AnimatedContainer(
              duration: const Duration(milliseconds: 150),
              width: i == _cardPage ? 16 : 4,
              height: 4,
              decoration: BoxDecoration(
                color: i == _cardPage ? gm.accent : gm.faint,
                borderRadius: BorderRadius.circular(2),
              ),
            ),
          ],
        ],
      ),
    );
  }
}

/// 横滑卡片按整卡宽度吸附
class _SnapScrollPhysics extends ScrollPhysics {
  const _SnapScrollPhysics({required this.itemExtent, super.parent});

  final double itemExtent;

  @override
  _SnapScrollPhysics applyTo(ScrollPhysics? ancestor) =>
      _SnapScrollPhysics(itemExtent: itemExtent, parent: buildParent(ancestor));

  @override
  Simulation? createBallisticSimulation(
      ScrollMetrics position, double velocity) {
    final tolerance = toleranceFor(position);
    if ((velocity.abs() < tolerance.velocity) &&
        (position.pixels % itemExtent).abs() < tolerance.distance) {
      return null;
    }
    var page = position.pixels / itemExtent;
    page = velocity > 0 ? page.ceilToDouble() : page.floorToDouble();
    final target = (page * itemExtent)
        .clamp(position.minScrollExtent, position.maxScrollExtent);
    if (target == position.pixels) return null;
    return ScrollSpringSimulation(spring, position.pixels, target, velocity,
        tolerance: tolerance);
  }
}

class _MuseumCard extends StatelessWidget {
  const _MuseumCard({required this.museum, this.onTap});

  final MuseumSummary museum;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    final gm = context.gm;
    final lang = Localizations.localeOf(context).languageCode;
    final l10n = AppLocalizations.of(context)!;
    // 各卡内容高度不一;_museumCards 的 Row 把它们拉到同高(最高那张),
    // 卡片本体撑满卡槽 → 没有点不到的死区(真机曾反馈"点橘园没反应")。
    return GestureDetector(
      onTap: onTap,
      behavior: HitTestBehavior.opaque,
      child: Container(
        width: 268,
        decoration: BoxDecoration(
          color: gm.surface,
          border: Border.all(color: gm.line),
        ),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // 封面走 A1 cover_image(建筑外观照);无合规封面 → 占位图标
            Container(
              height: 132,
              margin: const EdgeInsets.fromLTRB(9, 9, 9, 0),
              color: gm.chipBg,
              width: double.infinity,
              child: museum.coverImage != null
                  ? Image.network(
                      sizedImageUrl(museum.coverImage!, 600),
                      fit: BoxFit.cover,
                      headers: kImageRequestHeaders,
                      loadingBuilder: (_, child, p) =>
                          p == null ? child : const SizedBox.shrink(),
                      errorBuilder: (_, __, ___) => Center(
                        child:
                            GmIcon(GmIcons.ticket, size: 36, color: gm.faint),
                      ),
                    )
                  : Center(
                      child: GmIcon(GmIcons.ticket, size: 36, color: gm.faint),
                    ),
            ),
            Padding(
              padding: const EdgeInsets.fromLTRB(14, 12, 14, 14),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    crossAxisAlignment: CrossAxisAlignment.baseline,
                    textBaseline: TextBaseline.alphabetic,
                    children: [
                      Expanded(
                        child: Text(
                          museum.localizedName(lang),
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                          style:
                              GmText.serif(size: 17, weight: FontWeight.w600),
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 5),
                  // meta 只写真实有的(城市 + 藏品数)。营业时间/距离/票价属
                  // 易变运营数据,后端不存也不脏补(契约红线),前端不再编造。
                  Text(museum.localizedCity(lang),
                      style: GmText.sans(size: 12, color: gm.sub)),
                  if (museum.artworkCount > 0) ...[
                    const SizedBox(height: 8),
                    Row(
                      children: [
                        GmIcon(GmIcons.ticket, size: 14, color: gm.faint),
                        const SizedBox(width: 5),
                        Text(
                          l10n.artworkCountLabel(museum.artworkCount),
                          style: GmText.sans(size: 12, color: gm.sub),
                        ),
                      ],
                    ),
                  ],
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

/// 首页通票提示。写明**是哪张票**(「巴黎 7 日通票生效中」)—— 同时持巴黎/荷兰票时,
/// 只说「通票生效中」用户分不清;「畅听全馆」也会让人以为荷兰的馆也能听。
/// 票名来自后端 `title`(新票种不发版);老后端没给 passes 时退回不点名的通用文案。
String quotaLineText(AppLocalizations l10n, Entitlements? ent, Locale locale) {
  if (ent == null || !ent.known) {
    return l10n.homeFreeLeft(ent?.freeRecognitionsLeft?.toString() ?? '—');
  }
  String? names(bool Function(OwnedPass) pick) {
    final t = ent.passes
        .where(pick)
        .map((p) => passTitle(l10n, p.label, p.days, title: p.title))
        .toList();
    return t.isEmpty ? null : joinMuseums(t, locale.languageCode);
  }

  if (ent.isActive) {
    final n = names((p) => p.isActive);
    return n == null ? l10n.homePassActive : l10n.homePassActiveNamed(n);
  }
  if (ent.isPurchasedNotActivated) {
    final n = names((p) => p.isPurchasedNotActivated);
    return n == null ? l10n.homePassPending : l10n.homePassPendingNamed(n);
  }
  return l10n.homeFreeLeft(ent.freeRecognitionsLeft?.toString() ?? '—');
}
