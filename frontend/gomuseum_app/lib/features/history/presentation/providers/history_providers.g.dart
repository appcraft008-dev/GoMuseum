// GENERATED CODE - DO NOT MODIFY BY HAND

part of 'history_providers.dart';

// **************************************************************************
// RiverpodGenerator
// **************************************************************************

String _$historyDioHash() => r'baa9a7722b4d962909904f26974eace53b5237ce';

/// Dio provider for history module
///
/// Copied from [historyDio].
@ProviderFor(historyDio)
final historyDioProvider = AutoDisposeProvider<Dio>.internal(
  historyDio,
  name: r'historyDioProvider',
  debugGetCreateSourceHash:
      const bool.fromEnvironment('dart.vm.product') ? null : _$historyDioHash,
  dependencies: null,
  allTransitiveDependencies: null,
);

@Deprecated('Will be removed in 3.0. Use Ref instead')
// ignore: unused_element
typedef HistoryDioRef = AutoDisposeProviderRef<Dio>;
String _$historyRemoteDataSourceHash() =>
    r'7b5f2bc6382555a17f21acfbe04366303ceb9dc5';

/// History remote datasource provider
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
String _$historyHash() => r'1e424768357ab91551b747a88a48a0b5c657c293';

/// History provider
///
/// Copied from [History].
@ProviderFor(History)
final historyProvider =
    AutoDisposeNotifierProvider<History, HistoryState>.internal(
  History.new,
  name: r'historyProvider',
  debugGetCreateSourceHash:
      const bool.fromEnvironment('dart.vm.product') ? null : _$historyHash,
  dependencies: null,
  allTransitiveDependencies: null,
);

typedef _$History = AutoDisposeNotifier<HistoryState>;
// ignore_for_file: type=lint
// ignore_for_file: subtype_of_sealed_class, invalid_use_of_internal_member, invalid_use_of_visible_for_testing_member, deprecated_member_use_from_same_package
