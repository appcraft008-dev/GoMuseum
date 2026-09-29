/// GoMuseum 探索页 — 暖纸手册定稿（FinalExplore）
///
/// 数据来源：A1 GET /api/v1/museums（museumsListProvider）。
///
/// **一条竖向长列表按城市分段**(spec 2026-09-29-home-nearby-explore-by-city §三):
/// 往下滑自然从一座城市滑到下一座;顶部城市 chips 固定在上方、**跟随滚动位置高亮**,
/// 点 chip 滚到那一段。不做"上下滑 = 切城市" —— 会和列表自身滚动冲突。
/// 城市顺序:当前城市(与首页同一套信号)在前,其余按国家、再按城市。
library;

import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:gomuseum_app/core/network/image_request.dart';
import 'package:gomuseum_app/features/content/data/models/museum_summary_model.dart';
import 'package:gomuseum_app/features/content/presentation/providers/catalog_providers.dart';
import 'package:gomuseum_app/features/home/data/nearby.dart';
import 'package:gomuseum_app/features/search/presentation/search_results_view.dart';
import 'package:gomuseum_app/features/settings/presentation/providers/language_provider.dart';
import 'package:gomuseum_app/l10n/app_localizations.dart';
import 'package:gomuseum_app/theme/gm_palette.dart';
import 'package:gomuseum_app/theme/gm_theme_x.dart';
import 'package:gomuseum_app/ui/gm/gm.dart';

class ExplorePage extends ConsumerStatefulWidget {
  const ExplorePage({super.key});

  @override
  ConsumerState<ExplorePage> createState() => _ExplorePageState();
}

class _ExplorePageState extends ConsumerState<ExplorePage> {
  /// 当前高亮的城市(跟随滚动位置;点 chip 也会改它)。
  String? _active;

  final _scroll = ScrollController();

  /// 每个城市段标题的 key:算滚动位置、点 chip 时滚过去。
  final Map<String, GlobalKey> _sectionKeys = {};

  GlobalKey _keyFor(String city) =>
      _sectionKeys.putIfAbsent(city, () => GlobalKey(debugLabel: city));

  @override
  void initState() {
    super.initState();
    _scroll.addListener(_syncActive);
  }

  /// 滚动时高亮「标题已经滚到顶部附近」的最后一个城市段。
  void _syncActive() {
    final viewport = _scroll.position.context.storageContext.findRenderObject();
    if (viewport is! RenderBox) return;
    final top = viewport.localToGlobal(Offset.zero).dy;
    String? current;
    for (final e in _sectionKeys.entries) {
      final box = e.value.currentContext?.findRenderObject();
      if (box is! RenderBox || !box.attached) continue;
      final y = box.localToGlobal(Offset.zero).dy - top;
      if (y <= 48) current = e.key; // 按插入顺序遍历 = 城市顺序
    }
    current ??= _sectionKeys.keys.firstOrNull;
    // 最后一段往往太短、标题滚不到顶(阿姆斯特丹目前只有一家馆)—— 滚到底就高亮最后一座,
    // 否则用户滑到底也看不到它被选中
    final pos = _scroll.position;
    if (pos.hasContentDimensions && pos.pixels >= pos.maxScrollExtent - 1) {
      current = _sectionKeys.keys.lastOrNull ?? current;
    }
    if (current != null && current != _active) {
      setState(() => _active = current);
    }
  }

  Future<void> _jumpTo(String city) async {
    setState(() => _active = city);
    final ctx = _sectionKeys[city]?.currentContext;
    if (ctx == null) return;
    await Scrollable.ensureVisible(ctx,
        duration: const Duration(milliseconds: 300), curve: Curves.easeOut);
  }

  /// debounce 后的搜索词（非空 → 进入服务端搜索模式，替换馆浏览区）。
  String _debounced = '';
  Timer? _debounceTimer;

  @override
  void dispose() {
    _debounceTimer?.cancel();
    _scroll.dispose();
    super.dispose();
  }

  /// 即时输入 → 300ms debounce 调全局 /search；清空立即回浏览态。
  void _onQueryChanged(String v) {
    _debounceTimer?.cancel();
    final q = v.trim();
    if (q.isEmpty) {
      setState(() => _debounced = '');
      return;
    }
    _debounceTimer = Timer(const Duration(milliseconds: 300), () {
      if (mounted) setState(() => _debounced = q);
    });
  }

  /// 城市去重键用中文城市名（语言无关、稳定），显示时再本地化。
  ///
  /// 顺序:[current](当前城市)在前;其余按**国家**首次出现的顺序、国内再按城市首次出现
  /// 的顺序(列表本身已按 yaml rank 排)。
  List<String> _cities(List<MuseumSummary> all, String? current) {
    final countries = <String>[];
    final byCountry = <String, List<String>>{};
    for (final m in all) {
      if (m.city.isEmpty) continue;
      if (!byCountry.containsKey(m.country)) countries.add(m.country);
      final cs = byCountry.putIfAbsent(m.country, () => []);
      if (!cs.contains(m.city)) cs.add(m.city);
    }
    final ordered = [for (final c in countries) ...byCountry[c]!];
    if (current != null && ordered.remove(current)) ordered.insert(0, current);
    return ordered;
  }

  /// cityZh → 当前语言城市名（取该城市首个馆的本地化城市名）。
  String _cityLabel(String cityZh, List<MuseumSummary> all, String lang) {
    for (final m in all) {
      if (m.city == cityZh) return m.localizedCity(lang);
    }
    return cityZh;
  }

  @override
  Widget build(BuildContext context) {
    final gm = context.gm;
    final l10n = AppLocalizations.of(context)!;
    final lang = apiLanguage(ref.watch(resolvedLocaleProvider));
    final async = ref.watch(museumsListProvider);

    return SafeArea(
      bottom: false,
      child: async.when(
        loading: () => _scaffold(
          gm,
          body: Center(
            child: CircularProgressIndicator(color: gm.accent),
          ),
        ),
        error: (e, _) => _scaffold(
          gm,
          body: Center(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                Text(l10n.loadFailed,
                    style: GmText.sans(size: 14, color: gm.sub)),
                const SizedBox(height: 12),
                GestureDetector(
                  onTap: () => ref.invalidate(museumsListProvider),
                  child: Container(
                    padding: const EdgeInsets.symmetric(
                        horizontal: 20, vertical: 10),
                    decoration: BoxDecoration(
                      color: gm.ctaBg,
                    ),
                    child: Text(l10n.retry,
                        style: GmText.sans(size: 13, color: gm.ctaInk)),
                  ),
                ),
              ],
            ),
          ),
        ),
        data: (all) {
          final cities = _cities(all, ref.watch(nearbyProvider).value?.cityKey);
          // 段落只保留当前还存在的城市的 key(馆列表变了不留死 key)
          _sectionKeys.removeWhere((k, _) => !cities.contains(k));
          for (final c in cities) {
            _keyFor(c);
          }
          final active = _active ?? cities.firstOrNull;
          return _scaffold(
            gm,
            body: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                // ── 固定区:刊头 + 搜索 + 城市 chips(不随列表滚走)──
                Padding(
                  padding: const EdgeInsets.fromLTRB(26, 16, 26, 12),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Center(
                        child: Column(
                          children: [
                            Text(
                              l10n.exploreTitle,
                              style: GmText.serif(
                                  size: 21,
                                  weight: FontWeight.w700,
                                  letterSpacing: context.gmLetterSpacing(4)),
                            ),
                            const SizedBox(height: 8),
                            const GmDiamond(width: 110),
                          ],
                        ),
                      ),
                      const SizedBox(height: 14),
                      _searchBox(gm, l10n),
                      if (_debounced.isEmpty) ...[
                        const SizedBox(height: 12),
                        _cityChips(gm, cities, all, lang, active),
                      ],
                    ],
                  ),
                ),
                Expanded(
                  child: _debounced.isNotEmpty
                      // 有输入 → 全局搜索分区结果替换馆浏览
                      ? SingleChildScrollView(
                          padding: const EdgeInsets.fromLTRB(26, 10, 26, 12),
                          child: SearchResultsView(
                            query: (slug: null, q: _debounced, lang: lang),
                            showMuseums: true,
                          ),
                        )
                      : all.isEmpty
                          ? Center(
                              child: Text(l10n.noMuseums,
                                  style:
                                      GmText.sans(size: 12.5, color: gm.sub)),
                            )
                          : SingleChildScrollView(
                              controller: _scroll,
                              padding:
                                  const EdgeInsets.fromLTRB(26, 10, 26, 24),
                              child: Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  for (var ci = 0; ci < cities.length; ci++)
                                    ..._citySection(
                                        gm, l10n, lang, all, cities[ci], ci),
                                ],
                              ),
                            ),
                ),
              ],
            ),
          );
        },
      ),
    );
  }

  /// 一座城市的一段:标题(编号 = 城市序号)+ 首馆大卡 + 其余列表行。
  List<Widget> _citySection(GmPalette gm, AppLocalizations l10n, String lang,
      List<MuseumSummary> all, String city, int index) {
    final museums = all.where((m) => m.city == city).toList();
    return [
      if (index > 0) const SizedBox(height: 26),
      KeyedSubtree(
        key: _keyFor(city),
        child: GmSectionHead(
          number: (index + 1).toString().padLeft(2, '0'),
          label: _cityLabel(city, all, lang),
          note: l10n.museumCount(museums.length),
        ),
      ),
      const SizedBox(height: 13),
      _featureCard(gm, l10n, lang, museums.first),
      for (var i = 1; i < museums.length; i++)
        _listRow(gm, (i + 1).toString().padLeft(2, '0'), lang, museums[i]),
    ];
  }

  Widget _scaffold(GmPalette gm, {required Widget body}) {
    return ColoredBox(color: gm.bg, child: body);
  }

  Widget _searchBox(GmPalette gm, AppLocalizations l10n) {
    return Container(
      height: 46,
      padding: const EdgeInsets.symmetric(horizontal: 16),
      decoration: BoxDecoration(
        color: gm.surface,
        border: Border.all(color: gm.line),
      ),
      child: Row(
        children: [
          GmIcon(GmIcons.search, size: 18, color: gm.faint),
          const SizedBox(width: 10),
          Expanded(
            child: TextField(
              style: GmText.sans(size: 13.5),
              decoration: InputDecoration(
                hintText: l10n.searchCityMuseumArtwork,
                hintStyle: GmText.sans(size: 13.5, color: gm.faint),
                border: InputBorder.none,
                isDense: true,
              ),
              onChanged: _onQueryChanged,
            ),
          ),
        ],
      ),
    );
  }

  Widget _cityChips(GmPalette gm, List<String> cities, List<MuseumSummary> all,
      String lang, String? active) {
    return SingleChildScrollView(
      scrollDirection: Axis.horizontal,
      child: Row(
        children: [
          for (final city in cities) ...[
            GestureDetector(
              onTap: () => _jumpTo(city),
              child: Container(
                padding:
                    const EdgeInsets.symmetric(horizontal: 15, vertical: 7),
                decoration: BoxDecoration(
                  color: city == active ? gm.ctaBg : Colors.transparent,
                  border: Border.all(
                    color: city == active ? gm.ctaBg : gm.line,
                  ),
                ),
                child: Text(
                  _cityLabel(city, all, lang),
                  style: GmText.sans(
                    size: 12.5,
                    color: city == active ? gm.ctaInk : gm.sub,
                  ),
                ),
              ),
            ),
            const SizedBox(width: 8),
          ],
        ],
      ),
    );
  }

  Widget _featureCard(
      GmPalette gm, AppLocalizations l10n, String lang, MuseumSummary museum) {
    return GestureDetector(
      onTap: () => context.push('/museum/${museum.slug}'),
      child: Container(
        decoration: BoxDecoration(
          color: gm.surface,
          border: Border.all(color: gm.line),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // 封面(A1 cover_image，2026-07-20 加法字段；无合规封面 → 占位图标)
            Container(
              height: 124,
              margin: const EdgeInsets.fromLTRB(9, 9, 9, 0),
              color: gm.chipBg,
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
                          style:
                              GmText.serif(size: 17, weight: FontWeight.w600),
                        ),
                      ),
                      if (museum.city.isNotEmpty)
                        Text(
                          museum.localizedCity(lang),
                          style: GmText.sans(
                              size: 11.5,
                              color: gm.accent,
                              weight: FontWeight.w600),
                        ),
                    ],
                  ),
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
                  const Padding(
                    padding: EdgeInsets.symmetric(vertical: 11),
                    child: GmHairline(),
                  ),
                  // 页脚只留"可点进去"的箭头。这里原本还显示 museum.country——
                  // 而那是 ISO 国家码,直接把 "FR" 摆给用户看;就算本地化成「法国」
                  // 也是废话:卡片上方已经有城市名,section 头也写着城市。
                  Align(
                    alignment: Alignment.centerRight,
                    child: GmIcon(GmIcons.chevR, size: 17, color: gm.faint),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _listRow(
      GmPalette gm, String number, String lang, MuseumSummary museum) {
    return GestureDetector(
      onTap: () => context.push('/museum/${museum.slug}'),
      child: Container(
        height: 58,
        decoration: BoxDecoration(
          border: Border(bottom: BorderSide(color: gm.line)),
        ),
        child: Row(
          children: [
            Text(
              number,
              style: GmText.serif(
                  size: 13,
                  color: gm.faint,
                  weight: FontWeight.w700,
                  letterSpacing: 2),
            ),
            const SizedBox(width: 12),
            // 缩略图：与首馆大卡一致的视觉待遇(此前只有首馆有图，其余纯文字行)。
            ClipRect(
              child: SizedBox(
                width: 40,
                height: 40,
                child: museum.coverImage != null
                    ? Image.network(
                        sizedImageUrl(museum.coverImage!, 120),
                        fit: BoxFit.cover,
                        headers: kImageRequestHeaders,
                        errorBuilder: (_, __, ___) => ColoredBox(
                          color: gm.chipBg,
                          child: Center(
                              child: GmIcon(GmIcons.ticket,
                                  size: 16, color: gm.faint)),
                        ),
                      )
                    : ColoredBox(
                        color: gm.chipBg,
                        child: Center(
                            child: GmIcon(GmIcons.ticket,
                                size: 16, color: gm.faint)),
                      ),
              ),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(museum.localizedName(lang),
                      style: GmText.serif(size: 15, weight: FontWeight.w600)),
                  const SizedBox(height: 3),
                  Text(
                    museum.city.isNotEmpty
                        ? museum.localizedCity(lang)
                        : museum.country,
                    style: GmText.sans(size: 11.5, color: gm.sub),
                  ),
                ],
              ),
            ),
            GmIcon(GmIcons.chevR, size: 17, color: gm.faint),
          ],
        ),
      ),
    );
  }
}
