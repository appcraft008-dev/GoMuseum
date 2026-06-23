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

  Future<void> loadInitial() async {
    state = const ObjectListState(loading: true);
    await _fetch(0, replace: true);
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
      final merged = replace ? page.items : [...state.items, ...page.items];
      state = state.copyWith(
        items: merged,
        total: page.total,
        loading: false,
        hasMore: merged.length < page.total,
        clearError: true,
      );
    } catch (e) {
      state = state.copyWith(loading: false, error: e);
    }
  }
}

final objectListProvider = StateNotifierProvider.family<
    ObjectListNotifier,
    ObjectListState,
    ({String slug, String category, String language})>((ref, a) {
  final ds = ref.watch(catalogDataSourceProvider);
  return ObjectListNotifier(
      ds: ds, slug: a.slug, category: a.category, language: a.language)
    ..loadInitial();
});
