import 'package:riverpod_annotation/riverpod_annotation.dart';
import 'package:dio/dio.dart';
import 'package:gomuseum_app/features/auth/presentation/auth_provider.dart'
    show currentUserProvider;
import 'package:gomuseum_app/features/recognition/presentation/providers/recognition_providers.dart';
import 'package:gomuseum_app/features/settings/presentation/providers/language_provider.dart';
import '../../data/datasources/history_remote_datasource.dart';
import '../../data/repositories/history_repository_impl.dart';
import '../../domain/repositories/history_repository.dart';
import '../../domain/usecases/get_recent_history.dart';
import '../../domain/usecases/search_history.dart';
import '../../domain/usecases/delete_history_item.dart';
import '../../domain/entities/history_item.dart';
import 'package:gomuseum_app/features/history/presentation/footprint_visit.dart';

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
///
/// **常驻(keepAlive)**:底部 tab 是普通 ShellRoute,切走页面就卸载;autoDispose 时
/// 整份足迹跟着扔掉,切回来从空列表串行重拉全部页、全程转圈约 2 秒(2026-10-05 真机)。
/// 常驻不会变旧:识别完成会主动 pullLatest(recognition_provider)、删除就地改 state、
/// 换账号/切语言靠 build 里的 watch 重建,下拉仍可手动刷新。
@Riverpod(keepAlive: true)
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

  static const _firstPage = 50;

  /// 每次 [loadHistory] 自增;续拉回来发现不是最新一轮就丢弃结果。
  int _gen = 0;

  /// 本轮加载期间删掉的足迹:续拉合并时别让它复活。
  final _removed = <String>{};

  @override
  HistoryState build() {
    _lang = apiLanguage(ref.watch(resolvedLocaleProvider));
    // 足迹是 per-user 数据:换账号必须重拉。首页「继续游览」常驻持有这份缓存,
    // 不依赖账号的话会给 B 显示 A 看过的作品(同 #692 那类缺陷)。
    ref.watch(currentUserProvider.select((u) => u.valueOrNull?.id));
    // build 返回前 state 未初始化，必须推迟到微任务再加载
    Future.microtask(loadHistory);
    return const HistoryState(isLoading: true);
  }

  /// 拉**全部**足迹。页面没有「加载更多」,只拉第一页 = 永远只看得到最近 20 条
  /// (2026-10-02 真机:识别 160+ 条只显示 20 件),统计行的件数/天数也跟着错。
  ///
  /// 首个请求只拉 [_firstPage] 条,列表为空时拿到就显示(足迹页 + 首页「继续游览」),
  /// 其余每页 100(后端 `limit` 上限 `le=100`)在后台续拉接在后面;`hasMore` 为真 =
  /// 还没拉完,统计行据此暂不显示。801 条串行 9 个请求全程转圈 4–5 秒(2026-10-11 真机)。
  /// 已有列表时(识别后刷新/下拉)整份拉完再换,不先缩回 50 条。
  /// ponytail: 仍是拉全量,上万条了改成滚动到底再拉 + 后端给总数。
  Future<void> loadHistory({int? days}) async {
    const page = 100;
    final gen = ++_gen;
    _removed.clear();
    final progressive = state.items.isEmpty;
    state = state.copyWith(isLoading: true, error: null);

    final useCase = ref.read(getRecentHistoryUseCaseProvider);
    final all = <HistoryItem>[];
    var limit = _firstPage;
    // 页数封顶:后端分页一旦不前进(offset 被忽略),无上限会无限请求
    for (var p = 0; p < 20; p++) {
      final result = await useCase(
        limit: limit,
        offset: all.length,
        days: days,
        language: _lang,
      );
      if (gen != _gen) return; // 已被更新的一次加载取代(刷新/切语言/换账号)
      var got = 0;
      final failure = result.fold((f) => f, (items) {
        all.addAll(items);
        got = items.length;
        return null;
      });
      if (failure != null) {
        state = state.copyWith(isLoading: false, error: failure.message);
        return;
      }
      if (got < limit) break;
      if (progressive) {
        state = state.copyWith(items: _kept(all), hasMore: true);
      }
      limit = page;
    }
    state = state.copyWith(items: _kept(all), isLoading: false, hasMore: false);
    // 续拉途中删过:服务端列表前移,在途那页的 offset 会错位漏一条 → 整份再对一遍
    if (_removed.isNotEmpty) await loadHistory(days: days);
  }

  List<HistoryItem> _kept(List<HistoryItem> all) => [
        for (final i in all)
          if (!_removed.contains(i.id)) i
      ];

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

  /// 删一条足迹。列表按「一次参观内同一件只列一次」去重显示,所以要连带删掉
  /// 被藏起来的同参观重复条 —— 否则旧的那条立刻顶上来,看起来像没删掉。
  Future<void> deleteItem(String id) async {
    final useCase = ref.read(deleteHistoryItemUseCaseProvider);
    final target = state.items.where((i) => i.id == id).firstOrNull;
    final ids = target == null
        ? [id]
        : sameVisitDuplicates(state.items, target).map((i) => i.id).toList();

    for (final one in ids) {
      final result = await useCase(one);
      final failure = result.fold((f) => f, (_) => null);
      if (failure != null) {
        state = state.copyWith(error: failure.message);
        return;
      }
      _removed.add(one);
      state = state.copyWith(
          items: state.items.where((item) => item.id != one).toList());
    }
  }

  Future<void> refresh() async {
    await loadHistory();
  }

  /// 识别命中/确认后用:只拉最新一页,没见过的插到最前。原先每次识别都整份重拉
  /// (~900 条 9 个请求),10-12 统计占 App 全部 API 请求 37%、一天 53.5MB。
  /// 列表还在加载/续拉时走整份加载:在途那轮可能没带上新条目,混着插会错位。
  Future<void> pullLatest() async {
    if (state.isLoading || state.hasMore || state.items.isEmpty) {
      return loadHistory();
    }
    final gen = _gen;
    final result = await ref.read(getRecentHistoryUseCaseProvider)(
        limit: 20, language: _lang);
    if (gen != _gen) return; // 期间有整份加载,以它为准
    result.fold((_) {}, (latest) {
      final have = {for (final i in state.items) i.id};
      final fresh = [
        for (final i in latest)
          if (!have.contains(i.id) && !_removed.contains(i.id)) i
      ];
      if (fresh.isNotEmpty) {
        state = state.copyWith(items: [...fresh, ...state.items]);
      }
    });
  }
}
