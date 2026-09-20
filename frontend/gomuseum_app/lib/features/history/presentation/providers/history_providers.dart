import 'package:riverpod_annotation/riverpod_annotation.dart';
import 'package:dio/dio.dart';
import 'package:gomuseum_app/features/recognition/presentation/providers/recognition_providers.dart';
import 'package:gomuseum_app/features/settings/presentation/providers/language_provider.dart';
import '../../data/datasources/history_remote_datasource.dart';
import '../../data/repositories/history_repository_impl.dart';
import '../../domain/repositories/history_repository.dart';
import '../../domain/usecases/get_recent_history.dart';
import '../../domain/usecases/search_history.dart';
import '../../domain/usecases/delete_history_item.dart';
import '../../domain/entities/history_item.dart';

part 'history_providers.g.dart';

/// History remote datasource provider
///
/// 复用 Recognition 模块的平台感知 Dio（Android 模拟器走 10.0.2.2），
/// baseUrl 传相对路径让 Dio 自行拼接宿主地址。
@riverpod
HistoryRemoteDataSource historyRemoteDataSource(
  HistoryRemoteDataSourceRef ref,
) {
  final Dio dio = ref.watch(dioProvider);
  return HistoryRemoteDataSourceImpl(dio: dio, baseUrl: '/api/v1');
}

/// History repository provider
@riverpod
HistoryRepository historyRepository(HistoryRepositoryRef ref) {
  final remoteDataSource = ref.watch(historyRemoteDataSourceProvider);
  return HistoryRepositoryImpl(remoteDataSource: remoteDataSource);
}

/// Get recent history use case provider
@riverpod
GetRecentHistory getRecentHistoryUseCase(GetRecentHistoryUseCaseRef ref) {
  final repository = ref.watch(historyRepositoryProvider);
  return GetRecentHistory(repository);
}

/// Search history use case provider
@riverpod
SearchHistory searchHistoryUseCase(SearchHistoryUseCaseRef ref) {
  final repository = ref.watch(historyRepositoryProvider);
  return SearchHistory(repository);
}

/// Delete history item use case provider
@riverpod
DeleteHistoryItem deleteHistoryItemUseCase(DeleteHistoryItemUseCaseRef ref) {
  final repository = ref.watch(historyRepositoryProvider);
  return DeleteHistoryItem(repository);
}

/// History state
class HistoryState {
  final List<HistoryItem> items;
  final bool isLoading;
  final String? error;
  final bool hasMore;

  const HistoryState({
    this.items = const [],
    this.isLoading = false,
    this.error,
    this.hasMore = true,
  });

  HistoryState copyWith({
    List<HistoryItem>? items,
    bool? isLoading,
    String? error,
    bool? hasMore,
  }) {
    return HistoryState(
      items: items ?? this.items,
      isLoading: isLoading ?? this.isLoading,
      error: error,
      hasMore: hasMore ?? this.hasMore,
    );
  }
}

/// History provider
@riverpod
class History extends _$History {
  /// 发给后端的界面语言。
  ///
  /// **在 `build()` 里 watch,不在方法里 read** —— 两个理由缺一不可:
  /// ① `ref.watch` 只允许在 build 期间调用,方法里调会抛;
  /// ② watch 才能让切语言时这个 Notifier 重建 → 微任务重新拉一遍列表。
  /// 只改后端的话页面不会动:2026-09-20 报告的缺陷有两层,后端拿 `ev.language`
  /// 当显示语言是一层,前端切了语言不重载是另一层。
  ///
  /// 用 `resolvedLocaleProvider` 而不是 `languageProvider`:后者"跟随系统"时是
  /// null,而这里要的是**实际生效**的那个语言。取值一律走 `apiLanguage()`
  /// (繁体要映射成 `zh-hant`)。
  late String _lang;

  @override
  HistoryState build() {
    _lang = apiLanguage(ref.watch(resolvedLocaleProvider));
    // build 返回前 state 未初始化，必须推迟到微任务再加载
    Future.microtask(loadHistory);
    return const HistoryState(isLoading: true);
  }

  Future<void> loadHistory({
    int limit = 20,
    int offset = 0,
    int? days,
  }) async {
    state = state.copyWith(isLoading: true, error: null);

    final useCase = ref.read(getRecentHistoryUseCaseProvider);
    final result = await useCase(
      limit: limit,
      offset: offset,
      days: days,
      language: _lang,
    );

    result.fold(
      (failure) {
        state = state.copyWith(
          isLoading: false,
          error: failure.message,
        );
      },
      (items) {
        state = state.copyWith(
          items: offset == 0 ? items : [...state.items, ...items],
          isLoading: false,
          hasMore: items.length >= limit,
        );
      },
    );
  }

  Future<void> searchHistory(String query) async {
    if (query.trim().isEmpty) {
      await loadHistory();
      return;
    }

    state = state.copyWith(isLoading: true, error: null);

    final useCase = ref.read(searchHistoryUseCaseProvider);
    final result = await useCase(query: query, language: _lang);

    result.fold(
      (failure) {
        state = state.copyWith(
          isLoading: false,
          error: failure.message,
        );
      },
      (items) {
        state = state.copyWith(
          items: items,
          isLoading: false,
          hasMore: false,
        );
      },
    );
  }

  Future<void> deleteItem(String id) async {
    final useCase = ref.read(deleteHistoryItemUseCaseProvider);
    final result = await useCase(id);

    result.fold(
      (failure) {
        state = state.copyWith(error: failure.message);
      },
      (_) {
        // Remove item from list
        final updatedItems =
            state.items.where((item) => item.id != id).toList();
        state = state.copyWith(items: updatedItems);
      },
    );
  }

  Future<void> refresh() async {
    await loadHistory(offset: 0);
  }
}
