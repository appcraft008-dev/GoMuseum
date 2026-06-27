/// GoMuseum 首页 — 暖纸手册定稿（FinalHome）
///
/// 刊头 + 衬线标语 + 门票式识别 CTA + 免费额度提示 + 附近博物馆横滑卡片。
library;

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:gomuseum_app/features/payment/presentation/providers/benefits_provider.dart';
import 'package:gomuseum_app/l10n/app_localizations.dart';
import 'package:gomuseum_app/theme/gm_palette.dart';
import 'package:gomuseum_app/theme/gm_theme_x.dart';
import 'package:gomuseum_app/ui/gm/gm.dart';

/// 附近博物馆种子数据（馆方接口接入前的演示内容）
class _NearbyMuseum {
  const _NearbyMuseum({
    required this.name,
    required this.status,
    required this.meta,
    required this.cover,
    this.topWorks = const [],
    this.topWorksLabel,
  });

  final String name;
  final String status;
  final String meta;
  final GmArtwork cover;
  final List<GmArtwork> topWorks;
  final String? topWorksLabel;
}

const _nearbyMuseums = [
  _NearbyMuseum(
    name: '奥赛博物馆',
    status: '开放中',
    meta: '至 21:45 · 0.8 km · €16',
    cover: GmArt.orsayHall,
    topWorks: [GmArt.rhone, GmArt.self1889, GmArt.bedroom],
    topWorksLabel: '馆藏 Top 3\n星夜 · 自画像 · 卧室',
  ),
  _NearbyMuseum(
    name: '橘园美术馆',
    status: '开放中',
    meta: '至 18:00 · 1.6 km · €12',
    cover: GmArt.plain,
  ),
  _NearbyMuseum(
    name: '卢浮宫',
    status: '开放中',
    meta: '至 18:00 · 1.9 km · €22',
    cover: GmArt.crows,
  ),
];

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
                    _museumCards(),
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
          '${l10n.homePocketGuide} · 巴黎',
          style: GmText.sans(size: 11, letterSpacing: 3, color: gm.sub),
        ),
      ],
    );
  }

  Widget _slogan(AppLocalizations l10n) {
    return Text(
      l10n.homeSlogan,
      textAlign: TextAlign.center,
      style: GmText.serif(size: 27, weight: FontWeight.w700, height: 1.55),
    );
  }

  Widget _quotaLine(GmPalette gm, AppLocalizations l10n, int? quota) {
    return Text(
      l10n.homeFreeLeft(quota?.toString() ?? '—'),
      style: GmText.sans(size: 12, color: gm.sub),
    );
  }

  Widget _museumCards() {
    return SizedBox(
      height: 312,
      child: ListView.separated(
        controller: _cardScrollController,
        scrollDirection: Axis.horizontal,
        padding: const EdgeInsets.only(left: 26, right: 26),
        physics: const _SnapScrollPhysics(itemExtent: _cardExtent),
        itemCount: _nearbyMuseums.length,
        separatorBuilder: (_, __) => const SizedBox(width: 14),
        itemBuilder: (context, index) => Align(
          alignment: Alignment.topCenter,
          child: _MuseumCard(
            museum: _nearbyMuseums[index],
            // 奥赛已有馆包，点击进入馆藏目录
            onTap: index == 0 ? () => context.push('/museum/orsay') : null,
          ),
        ),
      ),
    );
  }

  static const double _cardExtent = 268 + 14;

  late final ScrollController _cardScrollController = ScrollController()
    ..addListener(() {
      final page = (_cardScrollController.offset / _cardExtent)
          .round()
          .clamp(0, _nearbyMuseums.length - 1);
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
          for (var i = 0; i < _nearbyMuseums.length; i++) ...[
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

  final _NearbyMuseum museum;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    final gm = context.gm;
    return GestureDetector(
      onTap: onTap,
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
            Padding(
              padding: const EdgeInsets.fromLTRB(9, 9, 9, 0),
              child: GmInnerImage(
                  image: AssetImage(museum.cover.asset), height: 132),
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
                      Text(
                        museum.name,
                        style: GmText.serif(size: 17, weight: FontWeight.w600),
                      ),
                      const Spacer(),
                      Text(
                        museum.status,
                        style: GmText.sans(
                          size: 11.5,
                          color: gm.accent,
                          weight: FontWeight.w600,
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 5),
                  Text(museum.meta,
                      style: GmText.sans(size: 12, color: gm.sub)),
                  if (museum.topWorks.isNotEmpty) ...[
                    const Padding(
                      padding: EdgeInsets.symmetric(vertical: 11),
                      child: GmHairline(),
                    ),
                    Row(
                      children: [
                        for (final work in museum.topWorks) ...[
                          GmThumb(image: AssetImage(work.asset)),
                          const SizedBox(width: 6),
                        ],
                        const SizedBox(width: 3),
                        Expanded(
                          child: Text(
                            museum.topWorksLabel ?? '',
                            style: GmText.sans(
                                size: 11, color: gm.sub, height: 1.5),
                          ),
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
