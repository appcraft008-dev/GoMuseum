/// GoMuseum 首页 — 暖纸手册定稿（FinalHome）
///
/// 刊头 + 衬线标语 + 门票式识别 CTA + 免费额度提示 + 附近博物馆横滑卡片。
library;

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:gomuseum_app/core/network/image_request.dart';
import 'package:gomuseum_app/features/content/data/models/museum_summary_model.dart';
import 'package:gomuseum_app/features/content/presentation/providers/catalog_providers.dart';
import 'package:gomuseum_app/features/payment/presentation/providers/benefits_provider.dart';
import 'package:gomuseum_app/l10n/app_localizations.dart';
import 'package:gomuseum_app/theme/gm_palette.dart';
import 'package:gomuseum_app/theme/gm_theme_x.dart';
import 'package:gomuseum_app/ui/gm/gm.dart';

class HomePage extends ConsumerStatefulWidget {
  const HomePage({super.key});

  @override
  ConsumerState<HomePage> createState() => _HomePageState();
}

class _HomePageState extends ConsumerState<HomePage> {
  int _cardPage = 0;

  @override
  Widget build(BuildContext context) {
    final gm = context.gm;
    final l10n = AppLocalizations.of(context)!;
    final benefits = ref.watch(benefitsStateProvider);
    final quota = benefits.value?.totalQuota;

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
                    _quotaLine(gm, l10n, quota),
                    Padding(
                      padding: const EdgeInsets.fromLTRB(26, 24, 26, 0),
                      child: GmSectionHead(
                        number: '01',
                        label: l10n.homeNearby,
                        note: l10n.viewAll,
                        onNoteTap: () => context.go('/explore'),
                      ),
                    ),
                    const SizedBox(height: 14),
                    // A1 加载中/失败:留白不塞占位馆(宁缺毋滥);探索页有完整重试入口
                    ref.watch(museumsListProvider).when(
                          loading: () => const SizedBox(height: 344),
                          error: (_, __) => const SizedBox(height: 344),
                          data: (museums) {
                            if (museums.length != _cardCount) {
                              WidgetsBinding.instance.addPostFrameCallback(
                                (_) => mounted
                                    ? setState(
                                        () => _cardCount = museums.length)
                                    : null,
                              );
                            }
                            return _museumCards(museums);
                          },
                        ),
                    _pageDots(gm),
                  ],
                ),
              ),
            ),
          );
        },
      ),
    );
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
    return SizedBox(
      width: double.infinity,
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

  Widget _quotaLine(GmPalette gm, AppLocalizations l10n, int? quota) {
    return Text(
      l10n.homeFreeLeft(quota?.toString() ?? '—'),
      style: GmText.sans(size: 12, color: gm.sub),
    );
  }

  /// 馆卡片走 A1 `GET /museums`(2026-07-26 API 化):上新馆自动出现在首页,
  /// 不再硬编码——此前卢浮宫卡片写死且无 slug,上线后点不动(同橘园 #300 教训)。
  Widget _museumCards(List<MuseumSummary> museums) {
    return SizedBox(
      // 留足余量：拉丁衬线行高略高 + 多语言文案，避免卡片底部溢出。
      height: 344,
      child: ListView.separated(
        controller: _cardScrollController,
        scrollDirection: Axis.horizontal,
        padding: const EdgeInsets.only(left: 26, right: 26),
        physics: const _SnapScrollPhysics(itemExtent: _cardExtent),
        itemCount: museums.length,
        separatorBuilder: (_, __) => const SizedBox(width: 14),
        itemBuilder: (context, index) => _MuseumCard(
          museum: museums[index],
          onTap: () => context.push('/museum/${museums[index].slug}'),
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
    // 卡槽高度由 _museumCards 的 SizedBox 撑到 344，但各卡内容高度不一
    // （橘园无 topWorks 行，比奥赛矮 ~60px）。GestureDetector 必须撑满整个
    // 卡槽高度、behavior: opaque，否则矮卡下方的空白卡槽是死区点不到
    // （真机实测反馈：点橘园卡片"没反应"，根因即此）。
    return GestureDetector(
      onTap: onTap,
      behavior: HitTestBehavior.opaque,
      child: SizedBox(
        width: 268,
        height: double.infinity,
        child: Align(
          alignment: Alignment.topCenter,
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
                            child: GmIcon(GmIcons.ticket,
                                size: 36, color: gm.faint),
                          ),
                        )
                      : Center(
                          child:
                              GmIcon(GmIcons.ticket, size: 36, color: gm.faint),
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
                              style: GmText.serif(
                                  size: 17, weight: FontWeight.w600),
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
        ),
      ),
    );
  }
}
