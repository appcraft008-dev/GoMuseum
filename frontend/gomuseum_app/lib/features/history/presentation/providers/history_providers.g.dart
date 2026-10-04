// GENERATED CODE - DO NOT MODIFY BY HAND

part of 'history_providers.dart';

// **************************************************************************
// RiverpodGenerator
// **************************************************************************

String _$historyRemoteDataSourceHash() =>
    r'c50cdb6281d9f6530dcc8bd09db50e44bb0cc2c8';

/// History remote datasource provider
///
/// 复用 Recognition 模块的平台感知 Dio（Android 模拟器走 10.0.2.2），
/// baseUrl 传相对路径让 Dio 自行拼接宿主地址。
///
/// Copied from [historyRemoteDataSource].
@ProviderFor(historyRemoteDataSource)
final historyRemoteDataSourceProvider =
    AutoDisposeProvider<HistoryRemoteDataSource>.internal(
  historyRemoteDataSource,
  name: r'historyRemoteDataSourceProvider',
  debugGetCreateSourceHash: const bool.fromEnvironment('dart.vm.product')
      ? null
      : _$historyRemoteDataSourceHash,
  dependencies: null,
  allTransitiveDependencies: null,
);

@Deprecated('Will be removed in 3.0. Use Ref instead')
// ignore: unused_element
typedef HistoryRemoteDataSourceRef
    = AutoDisposeProviderRef<HistoryRemoteDataSource>;
String _$historyRepositoryHash() => r'f55f4cf09405906dcf2600018b91ec1a82335760';

/// History repository provider
///
/// Copied from [historyRepository].
@ProviderFor(historyRepository)
final historyRepositoryProvider =
    AutoDisposeProvider<HistoryRepository>.internal(
  historyRepository,
  name: r'historyRepositoryProvider',
  debugGetCreateSourceHash: const bool.fromEnvironment('dart.vm.product')
      ? null
      : _$historyRepositoryHash,
  dependencies: null,
  allTransitiveDependencies: null,
);

@Deprecated('Will be removed in 3.0. Use Ref instead')
// ignore: unused_element
typedef HistoryRepositoryRef = AutoDisposeProviderRef<HistoryRepository>;
String _$getRecentHistoryUseCaseHash() =>
    r'ab34f5f91b42f2188e8372a9cc9d07619ed31f0c';

/// Get recent history use case provider
///
/// Copied from [getRecentHistoryUseCase].
@ProviderFor(getRecentHistoryUseCase)
final getRecentHistoryUseCaseProvider =
    AutoDisposeProvider<GetRecentHistory>.internal(
  getRecentHistoryUseCase,
  name: r'getRecentHistoryUseCaseProvider',
  debugGetCreateSourceHash: const bool.fromEnvironment('dart.vm.product')
      ? null
      : _$getRecentHistoryUseCaseHash,
  dependencies: null,
  allTransitiveDependencies: null,
);

@Deprecated('Will be removed in 3.0. Use Ref instead')
// ignore: unused_element
typedef GetRecentHistoryUseCaseRef = AutoDisposeProviderRef<GetRecentHistory>;
String _$searchHistoryUseCaseHash() =>
    r'f0c750ef1be4be89095f15a783f6994798a3f4f3';

/// Search history use case provider
///
/// Copied from [searchHistoryUseCase].
@ProviderFor(searchHistoryUseCase)
final searchHistoryUseCaseProvider =
    AutoDisposeProvider<SearchHistory>.internal(
  searchHistoryUseCase,
  name: r'searchHistoryUseCaseProvider',
  debugGetCreateSourceHash: const bool.fromEnvironment('dart.vm.product')
      ? null
      : _$searchHistoryUseCaseHash,
  dependencies: null,
  allTransitiveDependencies: null,
);

@Deprecated('Will be removed in 3.0. Use Ref instead')
// ignore: unused_element
typedef SearchHistoryUseCaseRef = AutoDisposeProviderRef<SearchHistory>;
String _$deleteHistoryItemUseCaseHash() =>
    r'20b06873f806886a3e4458c027ed5cb7f1e8f1c3';

/// Delete history item use case provider
///
/// Copied from [deleteHistoryItemUseCase].
@ProviderFor(deleteHistoryItemUseCase)
final deleteHistoryItemUseCaseProvider =
    AutoDisposeProvider<DeleteHistoryItem>.internal(
  deleteHistoryItemUseCase,
  name: r'deleteHistoryItemUseCaseProvider',
  debugGetCreateSourceHash: const bool.fromEnvironment('dart.vm.product')
      ? null
      : _$deleteHistoryItemUseCaseHash,
  dependencies: null,
  allTransitiveDependencies: null,
);

@Deprecated('Will be removed in 3.0. Use Ref instead')
// ignore: unused_element
typedef DeleteHistoryItemUseCaseRef = AutoDisposeProviderRef<DeleteHistoryItem>;
String _$historyHash() => r'c73792ab8d3c57c3ef7d5d77abd10e3313447eac';

/// History provider
///
/// **常驻(keepAlive)**:底部 tab 是普通 ShellRoute,切走页面就卸载;autoDispose 时
/// 整份足迹跟着扔掉,切回来从空列表串行重拉全部页、全程转圈约 2 秒(2026-10-05 真机)。
/// 常驻不会变旧:识别完成会主动 refresh(recognition_provider)、删除就地改 state、
/// 换账号/切语言靠 build 里的 watch 重建,下拉仍可手动刷新。
///
/// Copied from [History].
@ProviderFor(History)
final historyProvider = NotifierProvider<History, HistoryState>.internal(
  History.new,
  name: r'historyProvider',
  debugGetCreateSourceHash:
      const bool.fromEnvironment('dart.vm.product') ? null : _$historyHash,
  dependencies: null,
  allTransitiveDependencies: null,
);

typedef _$History = Notifier<HistoryState>;
// ignore_for_file: type=lint
// ignore_for_file: subtype_of_sealed_class, invalid_use_of_internal_member, invalid_use_of_visible_for_testing_member, deprecated_member_use_from_same_package
