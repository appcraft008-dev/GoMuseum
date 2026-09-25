// lib/features/content/presentation/providers/object_list_notifier.dart
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:gomuseum_app/features/content/data/datasources/catalog_remote_datasource.dart';
import 'package:gomuseum_app/features/content/data/models/object_list_model.dart';
import 'package:gomuseum_app/features/content/presentation/providers/catalog_providers.dart';

class ObjectListState {
  const ObjectListState({
    this.items = const [],
    this.total = 0,
    this.loading = false,
    this.hasMore = true,
    this.error,
  });

  final List<ObjectListItem> items;
  final int total;
  final bool loading;
  final bool hasMore;
  final Object? error;

  ObjectListState copyWith({
    List<ObjectListItem>? items,
    int? total,
    bool? loading,
    bool? hasMore,
    Object? error,
    bool clearError = false,
  }) =>
      ObjectListState(
        items: items ?? this.items,
        total: total ?? this.total,
        loading: loading ?? this.loading,
        hasMore: hasMore ?? this.hasMore,
        error: clearError ? null : (error ?? this.error),
      );
}

class ObjectListNotifier extends StateNotifier<ObjectListState> {
  ObjectListNotifier(
      {required this.ds,
      required this.slug,
      required this.category,
      required this.language})
      : super(const ObjectListState());

  final CatalogRemoteDataSource ds;
  final String slug;
  final String category;
  final String language;
  static const _limit = 50;

  /// 返回首屏是否拉到了 —— provider 据此决定要不要 keepAlive(只缓存成功结果)。
  Future<bool> loadInitial() async {
    state = const ObjectListState(loading: true);
    await _fetch(0, replace: true);
    return mounted && state.error == null;
  }

  Future<void> loadMore() async {
    if (state.loading || !state.hasMore) return;
    state = state.copyWith(loading: true, clearError: true);
    await _fetch(state.items.length);
  }

  Future<void> _fetch(int offset, {bool replace = false}) async {
    try {
      final page = await ds.getObjects(
          slug: slug,
          category: category,
          limit: _limit,
          offset: offset,
          language: language);
      if (!mounted) return; // autoDispose 后:响应回来时页面可能已退出
      final merged = replace ? page.items : [...state.items, ...page.items];
      state = state.copyWith(
        items: merged,
        total: page.total,
        loading: false,
        hasMore: merged.length < page.total,
        clearError: true,
      );
    } catch (e) {
      if (!mounted) return;
      state = state.copyWith(loading: false, error: e);
    }
  }
}

/// ⚠️ **只缓存成功结果**——`autoDispose` + 首屏拉到了才 `keepAlive`。
/// 理由同 museumDetailProvider(见那里的长注释):不带 autoDispose 的 family 会把
/// 错误态永久钉死,一次网络抖动就让这个 (馆,分类,语言) 再也不发请求,
/// 只有重启 App 能解。成功结果照旧永久驻留,不影响换语言/换分类的缓存命中。
final objectListProvider = StateNotifierProvider.autoDispose.family<
    ObjectListNotifier,
    ObjectListState,
    ({String slug, String category, String language})>((ref, a) {
  final ds = ref.watch(catalogDataSourceProvider);
  final notifier = ObjectListNotifier(
      ds: ds, slug: a.slug, category: a.category, language: a.language);
  // ok 为 false 也涵盖"页面已退出"(notifier 随 provider 一起 dispose),
  // 所以不必再单独盯 provider 的 dispose。
  notifier.loadInitial().then((ok) {
    if (ok) ref.keepAlive();
  });
  return notifier;
});
