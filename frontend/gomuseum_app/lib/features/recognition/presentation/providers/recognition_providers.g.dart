// GENERATED CODE - DO NOT MODIFY BY HAND

part of 'recognition_providers.dart';

// **************************************************************************
// RiverpodGenerator
// **************************************************************************

String _$dioHash() => r'354d5a3b28c1032f01b7f41f83a57086b97761ad';

/// Dio客户端Provider
///
/// Copied from [dio].
@ProviderFor(dio)
final dioProvider = AutoDisposeProvider<Dio>.internal(
  dio,
  name: r'dioProvider',
  debugGetCreateSourceHash:
      const bool.fromEnvironment('dart.vm.product') ? null : _$dioHash,
  dependencies: null,
  allTransitiveDependencies: null,
);

@Deprecated('Will be removed in 3.0. Use Ref instead')
// ignore: unused_element
typedef DioRef = AutoDisposeProviderRef<Dio>;
String _$networkInfoHash() => r'2bf44e6bdb28d5de63bc0a507b333a33e83758e9';

/// 网络信息Provider
///
/// Copied from [networkInfo].
@ProviderFor(networkInfo)
final networkInfoProvider = AutoDisposeProvider<NetworkInfo>.internal(
  networkInfo,
  name: r'networkInfoProvider',
  debugGetCreateSourceHash:
      const bool.fromEnvironment('dart.vm.product') ? null : _$networkInfoHash,
  dependencies: null,
  allTransitiveDependencies: null,
);

@Deprecated('Will be removed in 3.0. Use Ref instead')
// ignore: unused_element
typedef NetworkInfoRef = AutoDisposeProviderRef<NetworkInfo>;
String _$recognitionRemoteDataSourceHash() =>
    r'a0c6aa8dc380da6663fb69e5c2dfb287b3272f9c';

/// 远程数据源Provider
///
/// Copied from [recognitionRemoteDataSource].
@ProviderFor(recognitionRemoteDataSource)
final recognitionRemoteDataSourceProvider =
    AutoDisposeProvider<RecognitionRemoteDataSource>.internal(
  recognitionRemoteDataSource,
  name: r'recognitionRemoteDataSourceProvider',
  debugGetCreateSourceHash: const bool.fromEnvironment('dart.vm.product')
      ? null
      : _$recognitionRemoteDataSourceHash,
  dependencies: null,
  allTransitiveDependencies: null,
);

@Deprecated('Will be removed in 3.0. Use Ref instead')
// ignore: unused_element
typedef RecognitionRemoteDataSourceRef
    = AutoDisposeProviderRef<RecognitionRemoteDataSource>;
String _$recognitionLocalDataSourceHash() =>
    r'b90781fe377a15acbf43bf4e8c914543265067de';

/// 本地数据源Provider - 根据平台选择实现
///
/// Copied from [recognitionLocalDataSource].
@ProviderFor(recognitionLocalDataSource)
final recognitionLocalDataSourceProvider =
    AutoDisposeProvider<RecognitionLocalDataSource>.internal(
  recognitionLocalDataSource,
  name: r'recognitionLocalDataSourceProvider',
  debugGetCreateSourceHash: const bool.fromEnvironment('dart.vm.product')
      ? null
      : _$recognitionLocalDataSourceHash,
  dependencies: null,
  allTransitiveDependencies: null,
);

@Deprecated('Will be removed in 3.0. Use Ref instead')
// ignore: unused_element
typedef RecognitionLocalDataSourceRef
    = AutoDisposeProviderRef<RecognitionLocalDataSource>;
String _$recognitionRepositoryHash() =>
    r'320814f3edcbd126f2c0e1b43797127274ed9fa5';

/// Repository Provider
///
/// Copied from [recognitionRepository].
@ProviderFor(recognitionRepository)
final recognitionRepositoryProvider =
    AutoDisposeProvider<RecognitionRepository>.internal(
  recognitionRepository,
  name: r'recognitionRepositoryProvider',
  debugGetCreateSourceHash: const bool.fromEnvironment('dart.vm.product')
      ? null
      : _$recognitionRepositoryHash,
  dependencies: null,
  allTransitiveDependencies: null,
);

@Deprecated('Will be removed in 3.0. Use Ref instead')
// ignore: unused_element
typedef RecognitionRepositoryRef
    = AutoDisposeProviderRef<RecognitionRepository>;
String _$recognizeArtworkUseCaseHash() =>
    r'ec2168eee89efcb160a7cf9f1bfd24a294b5b8e8';

/// UseCase Provider
///
/// Copied from [recognizeArtworkUseCase].
@ProviderFor(recognizeArtworkUseCase)
final recognizeArtworkUseCaseProvider =
    AutoDisposeProvider<RecognizeArtwork>.internal(
  recognizeArtworkUseCase,
  name: r'recognizeArtworkUseCaseProvider',
  debugGetCreateSourceHash: const bool.fromEnvironment('dart.vm.product')
      ? null
      : _$recognizeArtworkUseCaseHash,
  dependencies: null,
  allTransitiveDependencies: null,
);

@Deprecated('Will be removed in 3.0. Use Ref instead')
// ignore: unused_element
typedef RecognizeArtworkUseCaseRef = AutoDisposeProviderRef<RecognizeArtwork>;
// ignore_for_file: type=lint
// ignore_for_file: subtype_of_sealed_class, invalid_use_of_internal_member, invalid_use_of_visible_for_testing_member, deprecated_member_use_from_same_package
