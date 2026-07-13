/// 馆藏列表页 — 暖纸手册 §8 CollectionListScreen
///
/// 顶栏：← + 馆名 + 藏品数 + 搜索图标
/// 分类 Tab 横滑：数据来自 A2 GET /museums/{slug} → categories
/// 目录列表行：A3 GET /museums/{slug}/objects 无限滚动
///   每行 = 序号 + 缩略图 + 标题/作者·年代 + content_status 角标
/// content_status=stub → 「待完善」角标
library;

import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:gomuseum_app/core/network/image_request.dart';
import 'package:gomuseum_app/features/content/data/models/museum_detail_model.dart';
import 'package:gomuseum_app/features/content/data/models/object_list_model.dart';
import 'package:gomuseum_app/features/content/presentation/providers/catalog_providers.dart';
import 'package:gomuseum_app/features/content/presentation/providers/object_list_notifier.dart';
import 'package:gomuseum_app/features/guide/presentation/pages/guide_page.dart';
import 'package:gomuseum_app/features/search/presentation/search_results_view.dart';
import 'package:gomuseum_app/features/settings/presentation/providers/language_provider.dart';
import 'package:gomuseum_app/l10n/app_localizations.dart';
import 'package:gomuseum_app/theme/gm_theme_x.dart';
import 'package:gomuseum_app/ui/gm/gm.dart';

class MuseumPage extends ConsumerStatefulWidget {
  const MuseumPage({super.key, required this.slug});

  final String slug;

  @override
  ConsumerState<MuseumPage> createState() => _MuseumPageState();
}

class _MuseumPageState extends ConsumerState<MuseumPage> {
  String _selectedCategory = 'all';
  final ScrollController _scrollController = ScrollController();

  /// 馆内搜索：图标展开搜索框，即时（debounce 300ms）只搜当前馆。
  bool _searching = false;
  String _searchDebounced = '';
  Timer? _searchTimer;

  @override
  void initState() {
    super.initState();
    _scrollController.addListener(_onScroll);
  }

  @override
  void dispose() {
    _searchTimer?.cancel();
    _scrollController.removeListener(_onScroll);
    _scrollController.dispose();
    super.dispose();
  }

  void _toggleSearch() {
    _searchTimer?.cancel();
    setState(() {
      _searching = !_searching;
      _searchDebounced = '';
    });
  }

  void _onSearchChanged(String v) {
    _searchTimer?.cancel();
    final q = v.trim();
    if (q.isEmpty) {
      setState(() => _searchDebounced = '');
      return;
    }
    _searchTimer = Timer(const Duration(milliseconds: 300), () {
      if (mounted) setState(() => _searchDebounced = q);
    });
  }

  void _onScroll() {
    final pos = _scrollController.position;
    if (pos.pixels >= pos.maxScrollExtent - 200) {
      final lang = apiLanguage(ref.read(languageProvider));
      final notifier = ref.read(objectListProvider(
              (slug: widget.slug, category: _selectedCategory, language: lang))
          .notifier);
      final state = ref.read(objectListProvider(
          (slug: widget.slug, category: _selectedCategory, language: lang)));
      if (state.hasMore && !state.loading) {
        notifier.loadMore();
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final gm = context.gm;
    final lang = apiLanguage(ref.watch(languageProvider));
    final detailAsync = ref.watch(museumDetailProvider(widget.slug));

    return Scaffold(
      backgroundColor: gm.bg,
      body: SafeArea(
        child: Column(
          children: [
            // Top bar（搜索态：标题换成搜索框，图标换成关闭）
            _TopBar(
              slug: widget.slug,
              detailAsync: detailAsync,
              lang: lang,
              searching: _searching,
              onSearchToggle: _toggleSearch,
              onQueryChanged: _onSearchChanged,
            ),
            if (_searching)
              Expanded(
                child: _searchDebounced.isEmpty
                    ? const SizedBox.shrink()
                    : SingleChildScrollView(
                        padding: const EdgeInsets.fromLTRB(18, 4, 18, 12),
                        child: SearchResultsView(
                          query: (
                            slug: widget.slug,
                            q: _searchDebounced,
                            lang: lang
                          ),
                          showMuseums: false,
                          fallbackSlug: widget.slug,
                        ),
                      ),
              )
            else ...[
              // Category tabs
              detailAsync.when(
                loading: () => const SizedBox.shrink(),
                error: (_, __) => const SizedBox.shrink(),
                data: (detail) => _CategoryTabs(
                  categories: detail.categories,
                  selected: _selectedCategory,
                  onSelect: (code) {
                    if (code == _selectedCategory) return;
                    setState(() => _selectedCategory = code);
                  },
                ),
              ),
              // Grid
              Expanded(
                child: _ObjectGrid(
                  slug: widget.slug,
                  category: _selectedCategory,
                  scrollController: _scrollController,
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }
}

// ---------------------------------------------------------------------------
// Top bar
// ---------------------------------------------------------------------------
class _TopBar extends StatelessWidget {
  const _TopBar({
    required this.slug,
    required this.detailAsync,
    required this.lang,
    required this.searching,
    required this.onSearchToggle,
    required this.onQueryChanged,
  });

  final String slug;
  final AsyncValue<MuseumDetail> detailAsync;
  final String lang;
  final bool searching;
  final VoidCallback onSearchToggle;
  final ValueChanged<String> onQueryChanged;

  @override
  Widget build(BuildContext context) {
    final gm = context.gm;
    final l10n = AppLocalizations.of(context)!;

    final String museumName;
    final String? countLabel;
    // 双数字行：在线图录 · 档案条目（两者都在时才显示；老后端缺字段 → null 不显示）。
    String? numbersLabel;

    switch (detailAsync) {
      case AsyncData(:final value):
        museumName = value.localizedName(lang);
        final total = value.categories.isEmpty
            ? null
            : value.categories
                .where((c) => c.code == 'all')
                .map((c) => c.count)
                .firstOrNull;
        countLabel = total != null ? l10n.recordedCount(total) : null;
        final catalog = value.catalogCount;
        final archive = value.archiveCount;
        if (catalog != null && archive != null) {
          numbersLabel = l10n.museumCatalogNumbers(catalog, archive);
        }
      case AsyncError():
        museumName = slug;
        countLabel = null;
      case AsyncLoading():
        museumName = '';
        countLabel = null;
      default:
        museumName = slug;
        countLabel = null;
    }

    return Padding(
      padding: const EdgeInsets.fromLTRB(18, 12, 18, 10),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.center,
        children: [
          GestureDetector(
            onTap: () =>
                context.canPop() ? context.pop() : context.go('/explore'),
            behavior: HitTestBehavior.opaque,
            child: GmIcon(GmIcons.back, size: 20, color: gm.ink),
          ),
          Expanded(
            child: searching
                ? Padding(
                    padding: const EdgeInsets.symmetric(horizontal: 12),
                    child: TextField(
                      autofocus: true,
                      style: GmText.sans(size: 14),
                      decoration: InputDecoration(
                        hintText: l10n.searchCityMuseumArtwork,
                        hintStyle: GmText.sans(size: 14, color: gm.faint),
                        border: InputBorder.none,
                        isDense: true,
                      ),
                      onChanged: onQueryChanged,
                    ),
                  )
                : Column(
                    children: [
                      if (museumName.isNotEmpty)
                        Text(
                          museumName,
                          textAlign: TextAlign.center,
                          style: GmText.serif(
                              size: 16,
                              weight: FontWeight.w700,
                              letterSpacing: 0.5),
                        ),
                      if (countLabel != null)
                        Text(
                          countLabel,
                          style: GmText.sans(
                              size: 10, letterSpacing: 1, color: gm.sub),
                        ),
                      if (numbersLabel != null)
                        Text(
                          numbersLabel,
                          textAlign: TextAlign.center,
                          style: GmText.sans(size: 9.5, color: gm.faint),
                        ),
                    ],
                  ),
          ),
          // 搜索开关：展开馆内搜索 / 关闭回到目录
          GestureDetector(
            onTap: onSearchToggle,
            behavior: HitTestBehavior.opaque,
            child: GmIcon(searching ? GmIcons.close : GmIcons.search,
                size: 20, color: gm.ink),
          ),
        ],
      ),
    );
  }
}

// ---------------------------------------------------------------------------
// Category tabs
// ---------------------------------------------------------------------------
class _CategoryTabs extends StatelessWidget {
  const _CategoryTabs({
    required this.categories,
    required this.selected,
    required this.onSelect,
  });

  final List<MuseumCategory> categories;
  final String selected;
  final ValueChanged<String> onSelect;

  @override
  Widget build(BuildContext context) {
    final gm = context.gm;
    final l10n = AppLocalizations.of(context)!;

    // If backend returns no categories, show a single 「全部」 tab.
    // 「all」类目 label 后端未本地化（硬编码中文），前端用 l10n.all 覆盖；
    // 其它类目 label（Painting/Sculpture…）仍待后端按 language 返本地化值。
    final tabs = (categories.isNotEmpty
            ? categories
            : [MuseumCategory(code: 'all', label: l10n.all, count: 0)])
        .map((c) => c.code == 'all'
            ? MuseumCategory(code: c.code, label: l10n.all, count: c.count)
            : c)
        .toList();

    return Container(
      decoration: BoxDecoration(
        border: Border(
          top: BorderSide(color: gm.line),
          bottom: BorderSide(color: gm.line, width: 1.5),
        ),
      ),
      child: SingleChildScrollView(
        scrollDirection: Axis.horizontal,
        child: Row(
          children: [
            for (final cat in tabs)
              GestureDetector(
                onTap: () => onSelect(cat.code),
                behavior: HitTestBehavior.opaque,
                child: _TabItem(
                  cat: cat,
                  active: cat.code == selected,
                ),
              ),
          ],
        ),
      ),
    );
  }
}

class _TabItem extends StatelessWidget {
  const _TabItem({required this.cat, required this.active});

  final MuseumCategory cat;
  final bool active;

  @override
  Widget build(BuildContext context) {
    final gm = context.gm;
    return Container(
      padding: const EdgeInsets.fromLTRB(15, 8, 15, 6),
      decoration: BoxDecoration(
        border: Border(
          bottom: BorderSide(
            color: active ? gm.accent : Colors.transparent,
            width: 2.5,
          ),
        ),
      ),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Text(
            cat.label,
            style: GmText.serif(
              size: 13,
              weight: active ? FontWeight.w700 : FontWeight.w400,
              color: active ? gm.accentDeep : gm.sub,
            ),
          ),
          const SizedBox(height: 2),
          Text(
            '${cat.count}',
            style: GmText.sans(size: 9.5, color: gm.faint),
          ),
        ],
      ),
    );
  }
}

// ---------------------------------------------------------------------------
// 2-col object grid with infinite scroll
// ---------------------------------------------------------------------------
class _ObjectGrid extends ConsumerWidget {
  const _ObjectGrid({
    required this.slug,
    required this.category,
    required this.scrollController,
  });

  final String slug;
  final String category;
  final ScrollController scrollController;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final gm = context.gm;
    final l10n = AppLocalizations.of(context)!;
    final lang = apiLanguage(ref.watch(languageProvider));
    final state = ref.watch(
        objectListProvider((slug: slug, category: category, language: lang)));
    final items = state.items;

    if (items.isEmpty && state.loading) {
      return Center(
        child: CircularProgressIndicator(
          color: gm.accent,
          strokeWidth: 2,
        ),
      );
    }

    if (items.isEmpty && state.error != null) {
      return Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Text(
              l10n.loadFailedRetry,
              style: GmText.sans(size: 13, color: gm.sub),
            ),
            const SizedBox(height: 10),
            GestureDetector(
              onTap: () => ref
                  .read(objectListProvider(
                          (slug: slug, category: category, language: lang))
                      .notifier)
                  .loadInitial(),
              child: Text(
                l10n.retry,
                style: GmText.sans(size: 13, color: gm.accent),
              ),
            ),
          ],
        ),
      );
    }

    if (items.isEmpty && !state.loading) {
      return Center(
        child: Text(
          l10n.noArtworks,
          style: GmText.sans(size: 13, color: gm.sub),
        ),
      );
    }

    return CustomScrollView(
      controller: scrollController,
      slivers: [
        SliverList(
          delegate: SliverChildBuilderDelegate(
            (context, i) => _ObjectRow(
              number: (i + 1).toString().padLeft(2, '0'),
              item: items[i],
              onTap: () => context.push(
                '/guide',
                extra: GuideArgs(
                  slug: slug,
                  qid: items[i].qid,
                ),
              ),
            ),
            childCount: items.length,
          ),
        ),
        SliverToBoxAdapter(
          child: _BottomState(state: state),
        ),
      ],
    );
  }
}

// ---------------------------------------------------------------------------
// 目录列表行：序号 + 缩略图 + 标题/作者·年代 + content_status 角标
// ---------------------------------------------------------------------------
class _ObjectRow extends StatelessWidget {
  const _ObjectRow({
    required this.number,
    required this.item,
    required this.onTap,
  });

  final String number;
  final ObjectListItem item;
  final VoidCallback onTap;

  String get _meta {
    final parts = <String>[
      if (item.artist.isNotEmpty) item.artist,
      if (item.year != null && item.year!.isNotEmpty) item.year!,
    ];
    return parts.join(' · ');
  }

  @override
  Widget build(BuildContext context) {
    final gm = context.gm;
    return GestureDetector(
      onTap: onTap,
      behavior: HitTestBehavior.opaque,
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 11),
        decoration: BoxDecoration(
          border: Border(bottom: BorderSide(color: gm.line)),
        ),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.center,
          children: [
            // 序号（宽度容 4 位数，如 1672 件馆藏；maxLines 防折行）
            SizedBox(
              width: 40,
              child: Text(
                number,
                maxLines: 1,
                softWrap: false,
                overflow: TextOverflow.visible,
                style: GmText.serif(
                  size: 13,
                  color: gm.faint,
                  weight: FontWeight.w700,
                  letterSpacing: 1,
                ),
              ),
            ),
            const SizedBox(width: 10),
            // 缩略图
            _Thumbnail(url: item.thumbnail, size: 52),
            const SizedBox(width: 13),
            // 标题 + 作者·年代
            Expanded(
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    item.title,
                    style: GmText.serif(size: 14.5, weight: FontWeight.w600),
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                  ),
                  if (_meta.isNotEmpty) ...[
                    const SizedBox(height: 3),
                    Text(
                      _meta,
                      style: GmText.sans(size: 11.5, color: gm.sub),
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                    ),
                  ],
                ],
              ),
            ),
            const SizedBox(width: 10),
            // content_status 角标 / 进入箭头
            if (item.isStub)
              const _StubBadge()
            else
              GmIcon(GmIcons.chevR, size: 16, color: gm.faint),
          ],
        ),
      ),
    );
  }
}

class _Thumbnail extends StatelessWidget {
  const _Thumbnail({required this.url, this.size = 52});

  final String? url;
  final double size;

  @override
  Widget build(BuildContext context) {
    if (url != null) {
      return SizedBox(
        height: size,
        width: size,
        child: Image.network(
          // 列表缩略图仅 52dp：取 ?width=200 缩略图(~14KB,生成更快、更易命中
          // Wikimedia CDN 缓存)而非数十 MB 原图；带合规 UA。
          sizedImageUrl(url!, 200),
          height: size,
          width: size,
          fit: BoxFit.cover,
          cacheWidth: 200,
          headers: kImageRequestHeaders,
          loadingBuilder: (_, child, progress) =>
              progress == null ? child : _Placeholder(size: size),
          errorBuilder: (_, __, ___) => _Placeholder(size: size),
        ),
      );
    }
    return _Placeholder(size: size);
  }
}

class _Placeholder extends StatelessWidget {
  const _Placeholder({this.size = 52});

  final double size;

  @override
  Widget build(BuildContext context) {
    final gm = context.gm;
    return Container(
      height: size,
      width: size,
      color: gm.chipBg,
      child: Center(
        child: GmIcon(GmIcons.photo, size: size * 0.42, color: gm.faint),
      ),
    );
  }
}

class _StubBadge extends StatelessWidget {
  const _StubBadge();

  @override
  Widget build(BuildContext context) {
    final gm = context.gm;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 5, vertical: 2),
      color: gm.chipBg,
      child: Text(
        AppLocalizations.of(context)!.toBeRefined,
        style: GmText.sans(size: 9.5, color: gm.sub),
      ),
    );
  }
}

// ---------------------------------------------------------------------------
// Bottom state: loading spinner or done state
// ---------------------------------------------------------------------------
class _BottomState extends StatelessWidget {
  const _BottomState({required this.state});

  final ObjectListState state;

  @override
  Widget build(BuildContext context) {
    final gm = context.gm;
    final l10n = AppLocalizations.of(context)!;
    if (state.loading) {
      return Padding(
        padding: const EdgeInsets.symmetric(vertical: 20),
        child: Column(
          children: [
            SizedBox(
              width: 22,
              height: 22,
              child: CircularProgressIndicator(
                strokeWidth: 2,
                color: gm.accent,
              ),
            ),
            const SizedBox(height: 8),
            Text(
              l10n.loadingShown(state.items.length, state.total),
              style: GmText.sans(size: 11, color: gm.sub),
            ),
          ],
        ),
      );
    }
    if (!state.hasMore && state.items.isNotEmpty) {
      return Padding(
        padding: const EdgeInsets.fromLTRB(14, 16, 14, 24),
        child: Column(
          children: [
            const GmDiamond(width: 160),
            const SizedBox(height: 8),
            Text(
              l10n.allLoaded(state.total),
              style: GmText.sans(size: 11.5, color: gm.faint),
            ),
          ],
        ),
      );
    }
    return const SizedBox(height: 20);
  }
}
