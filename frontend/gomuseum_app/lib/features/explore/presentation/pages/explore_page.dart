/// GoMuseum 探索页 — 暖纸手册定稿（FinalExplore）
///
/// 数据来源：A1 GET /api/v1/museums（museumsListProvider）。
/// 城市 chips 由返回数据 city 去重生成；搜索为客户端 name/city 过滤。
library;

import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:gomuseum_app/features/content/data/models/museum_summary_model.dart';
import 'package:gomuseum_app/features/content/presentation/providers/catalog_providers.dart';
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
  /// 当前选中城市；null 表示「全部」（初始未选定，由数据首城市驱动）。
  String? _city;

  /// debounce 后的搜索词（非空 → 进入服务端搜索模式，替换馆浏览区）。
  String _debounced = '';
  Timer? _debounceTimer;

  @override
  void dispose() {
    _debounceTimer?.cancel();
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
  List<String> _cities(List<MuseumSummary> all) {
    final seen = <String>{};
    return [
      for (final m in all)
        if (m.city.isNotEmpty && seen.add(m.city)) m.city,
    ];
  }

  /// cityZh → 当前语言城市名（取该城市首个馆的本地化城市名）。
  String _cityLabel(String cityZh, List<MuseumSummary> all, String lang) {
    for (final m in all) {
      if (m.city == cityZh) return m.localizedCity(lang);
    }
    return cityZh;
  }

  /// 浏览态按城市过滤（搜索改走服务端 /search，不再客户端过滤馆名）。
  List<MuseumSummary> _filtered(List<MuseumSummary> all) {
    final city = _city;
    return city != null ? all.where((m) => m.city == city).toList() : all;
  }

  @override
  Widget build(BuildContext context) {
    final gm = context.gm;
    final l10n = AppLocalizations.of(context)!;
    final lang = apiLanguage(ref.watch(languageProvider));
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
          final cities = _cities(all);
          // 首次数据到达时设置默认城市
          if (_city == null && cities.isNotEmpty) {
            // use post-frame callback to avoid setState during build
            WidgetsBinding.instance.addPostFrameCallback((_) {
              if (mounted && _city == null) {
                setState(() => _city = cities.first);
              }
            });
          }
          final museums = _filtered(all);
          return _scaffold(
            gm,
            body: SingleChildScrollView(
              padding: const EdgeInsets.fromLTRB(26, 16, 26, 12),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  // ── 刊头 ──────────────────────────────────────────
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
                  const SizedBox(height: 12),
                  _cityChips(gm, cities, all, lang),
                  const SizedBox(height: 22),
                  // 有输入 → 全局搜索分区结果；空 → 正常馆浏览。
                  if (_debounced.isNotEmpty)
                    SearchResultsView(
                      query: (slug: null, q: _debounced, lang: lang),
                      showMuseums: true,
                    )
                  else ...[
                    GmSectionHead(
                      number: '01',
                      label: _city != null
                          ? _cityLabel(_city!, all, lang)
                          : l10n.all,
                      note: l10n.museumCount(museums.length),
                    ),
                    if (museums.isEmpty)
                      Padding(
                        padding: const EdgeInsets.symmetric(vertical: 28),
                        child: Center(
                          child: Text(
                            all.isEmpty
                                ? l10n.noMuseums
                                : l10n.noMatchedMuseums,
                            style: GmText.sans(size: 12.5, color: gm.sub),
                          ),
                        ),
                      )
                    else ...[
                      // 首馆用大卡，其余用列表行
                      const SizedBox(height: 13),
                      _featureCard(gm, l10n, lang, museums.first),
                      for (var i = 1; i < museums.length; i++)
                        _listRow(gm, (i + 1).toString().padLeft(2, '0'), lang,
                            museums[i]),
                    ],
                  ],
                ],
              ),
            ),
          );
        },
      ),
    );
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

  Widget _cityChips(
      GmPalette gm, List<String> cities, List<MuseumSummary> all, String lang) {
    return SingleChildScrollView(
      scrollDirection: Axis.horizontal,
      child: Row(
        children: [
          for (final city in cities) ...[
            GestureDetector(
              onTap: () => setState(() => _city = city),
              child: Container(
                padding:
                    const EdgeInsets.symmetric(horizontal: 15, vertical: 7),
                decoration: BoxDecoration(
                  color: city == _city ? gm.ctaBg : Colors.transparent,
                  border: Border.all(
                    color: city == _city ? gm.ctaBg : gm.line,
                  ),
                ),
                child: Text(
                  _cityLabel(city, all, lang),
                  style: GmText.sans(
                    size: 12.5,
                    color: city == _city ? gm.ctaInk : gm.sub,
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
            // 占位封面（无网络图片来源于 A1，故用颜色块）
            Container(
              height: 124,
              margin: const EdgeInsets.fromLTRB(9, 9, 9, 0),
              color: gm.chipBg,
              child: Center(
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
                  Row(
                    children: [
                      Text(
                        museum.country.isNotEmpty
                            ? museum.country
                            : museum.localizedCity(lang),
                        style: GmText.sans(size: 11, color: gm.sub),
                      ),
                      const Spacer(),
                      GmIcon(GmIcons.chevR, size: 17, color: gm.faint),
                    ],
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
            const SizedBox(width: 14),
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
