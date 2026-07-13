/// 搜索结果视图（探索页全局 + 馆列表页馆域 + 识别兜底 sheet 三处共用）。
///
/// 全局：分区「博物馆」+「藏品」；馆域：仅藏品（showMuseums=false）。
/// 藏品行点击 → 讲解页（slug=obj.museum ?? fallbackSlug，与识别 match 同款导航）；
/// 无图 stub 用 GmInnerImage 类目占位（文字可识别层入口）。
library;

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:gomuseum_app/core/network/image_request.dart';
import 'package:gomuseum_app/features/guide/presentation/pages/guide_page.dart';
import 'package:gomuseum_app/features/search/data/search_api.dart';
import 'package:gomuseum_app/l10n/app_localizations.dart';
import 'package:gomuseum_app/theme/gm_palette.dart';
import 'package:gomuseum_app/theme/gm_theme_x.dart';
import 'package:gomuseum_app/ui/gm/gm.dart';

class SearchResultsView extends ConsumerWidget {
  const SearchResultsView({
    super.key,
    required this.query,
    this.showMuseums = true,
    this.fallbackSlug,
    this.onNavigate,
  });

  final SearchQuery query;
  final bool showMuseums;

  /// 馆域搜索时的归属馆（藏品行 museum 缺失时的导航兜底）。
  final String? fallbackSlug;

  /// 点击结果跳转前的回调（如识别兜底 sheet 里先关闭 sheet）。
  final VoidCallback? onNavigate;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final gm = context.gm;
    final l10n = AppLocalizations.of(context)!;
    final async = ref.watch(searchProvider(query));

    return async.when(
      loading: () => Padding(
        padding: const EdgeInsets.symmetric(vertical: 32),
        child: Center(child: CircularProgressIndicator(color: gm.accent)),
      ),
      error: (_, __) => _hint(gm, l10n.loadFailed),
      data: (res) {
        if (res.isEmpty) return _hint(gm, l10n.searchNoResults);
        return Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            if (showMuseums && res.museums.isNotEmpty) ...[
              _label(gm, l10n.searchMuseumsSection),
              for (final m in res.museums)
                _MuseumHitRow(hit: m, onNavigate: onNavigate),
              const SizedBox(height: 18),
            ],
            if (res.objects.isNotEmpty) ...[
              if (showMuseums) _label(gm, l10n.searchArtworksSection),
              for (final o in res.objects)
                _ObjectHitRow(
                    obj: o, fallbackSlug: fallbackSlug, onNavigate: onNavigate),
            ],
          ],
        );
      },
    );
  }

  Widget _label(GmPalette gm, String text) => Padding(
        padding: const EdgeInsets.only(bottom: 4),
        child: Text(
          text,
          style: GmText.sans(
              size: 11,
              letterSpacing: 1.5,
              color: gm.sub,
              weight: FontWeight.w600),
        ),
      );

  Widget _hint(GmPalette gm, String text) => Padding(
        padding: const EdgeInsets.symmetric(vertical: 28),
        child: Center(
          child: Text(text, style: GmText.sans(size: 12.5, color: gm.sub)),
        ),
      );
}

class _MuseumHitRow extends StatelessWidget {
  const _MuseumHitRow({required this.hit, this.onNavigate});

  final SearchMuseumHit hit;
  final VoidCallback? onNavigate;

  @override
  Widget build(BuildContext context) {
    final gm = context.gm;
    return GestureDetector(
      onTap: () {
        onNavigate?.call();
        context.push('/museum/${hit.slug}');
      },
      behavior: HitTestBehavior.opaque,
      child: Container(
        height: 54,
        decoration:
            BoxDecoration(border: Border(bottom: BorderSide(color: gm.line))),
        child: Row(
          children: [
            GmIcon(GmIcons.ticket, size: 18, color: gm.faint),
            const SizedBox(width: 12),
            Expanded(
              child: Text(hit.name,
                  style: GmText.serif(size: 15, weight: FontWeight.w600)),
            ),
            if (hit.city.isNotEmpty)
              Text(hit.city, style: GmText.sans(size: 11.5, color: gm.sub)),
            const SizedBox(width: 8),
            GmIcon(GmIcons.chevR, size: 17, color: gm.faint),
          ],
        ),
      ),
    );
  }
}

class _ObjectHitRow extends StatelessWidget {
  const _ObjectHitRow({required this.obj, this.fallbackSlug, this.onNavigate});

  final SearchObject obj;
  final String? fallbackSlug;
  final VoidCallback? onNavigate;

  @override
  Widget build(BuildContext context) {
    final gm = context.gm;
    final slug = obj.museum ?? fallbackSlug;
    return GestureDetector(
      onTap: slug == null
          ? null
          : () {
              onNavigate?.call();
              context.push('/guide',
                  extra: GuideArgs(slug: slug, qid: obj.qid));
            },
      behavior: HitTestBehavior.opaque,
      child: Container(
        padding: const EdgeInsets.symmetric(vertical: 8),
        decoration:
            BoxDecoration(border: Border(bottom: BorderSide(color: gm.line))),
        child: Row(
          children: [
            GmInnerImage(
              image: (obj.hasImage && obj.thumbnail != null)
                  ? NetworkImage(sizedImageUrl(obj.thumbnail!, 200),
                      headers: kImageRequestHeaders)
                  : null,
              height: 52,
              width: 52,
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(obj.title,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: GmText.serif(size: 14.5, weight: FontWeight.w600)),
                  const SizedBox(height: 3),
                  Text(
                    [obj.artist, if (obj.year != null) obj.year!]
                        .where((s) => s.isNotEmpty)
                        .join(' · '),
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
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
