// GENERATED CODE - DO NOT MODIFY BY HAND

part of 'explanation_providers.dart';

// **************************************************************************
// RiverpodGenerator
// **************************************************************************

String _$dioHash() => r'3779055b262998a19467f2c6b76f144bec26c2dc';

/// Dio客户端Provider
///
/// 提供配置好的HTTP客户端，支持跨平台基础URL配置。
/// Android模拟器使用10.0.2.2访问宿主机，其他平台使用localhost。
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
String _$loggerHash() => r'b9ed25da3f5c1186b5309e3d5575fe3a9b68b39c';

/// Logger实例Provider
///
/// 提供统一的日志记录器，用于调试和错误追踪。
/// 配置为在开发模式下输出详细日志。
///
/// Copied from [logger].
@ProviderFor(logger)
final loggerProvider = AutoDisposeProvider<Logger>.internal(
  logger,
  name: r'loggerProvider',
  debugGetCreateSourceHash:
      const bool.fromEnvironment('dart.vm.product') ? null : _$loggerHash,
  dependencies: null,
  allTransitiveDependencies: null,
);

@Deprecated('Will be removed in 3.0. Use Ref instead')
// ignore: unused_element
typedef LoggerRef = AutoDisposeProviderRef<Logger>;
String _$networkInfoHash() => r'2bf44e6bdb28d5de63bc0a507b333a33e83758e9';

/// 网络信息Provider
///
/// 提供网络连接状态检查功能，用于离线/在线模式切换。
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
String _$explanationRemoteDataSourceHash() =>
    r'ab43a09450a8d7e8350c47bdd2164fa2542a1357';

/// 解释功能远程数据源Provider
///
/// 提供与后端API交互的数据源实例，依赖于Dio客户端和Logger。
///
/// Copied from [explanationRemoteDataSource].
@ProviderFor(explanationRemoteDataSource)
final explanationRemoteDataSourceProvider =
    AutoDisposeProvider<ExplanationRemoteDataSource>.internal(
  explanationRemoteDataSource,
  name: r'explanationRemoteDataSourceProvider',
  debugGetCreateSourceHash: const bool.fromEnvironment('dart.vm.product')
      ? null
      : _$explanationRemoteDataSourceHash,
  dependencies: null,
  allTransitiveDependencies: null,
);

@Deprecated('Will be removed in 3.0. Use Ref instead')
// ignore: unused_element
typedef ExplanationRemoteDataSourceRef
    = AutoDisposeProviderRef<ExplanationRemoteDataSource>;
String _$explanationRepositoryHash() =>
    r'8cb4b91987e78e2c50bfa6a6bc0f8d5629a2c4a6';

/// 解释功能Repository Provider
///
/// 提供数据仓库实例，协调远程数据源。
/// 遵循Clean Architecture的依赖倒置原则。
///
/// Copied from [explanationRepository].
@ProviderFor(explanationRepository)
final explanationRepositoryProvider =
    AutoDisposeProvider<ExplanationRepository>.internal(
  explanationRepository,
  name: r'explanationRepositoryProvider',
  debugGetCreateSourceHash: const bool.fromEnvironment('dart.vm.product')
      ? null
      : _$explanationRepositoryHash,
  dependencies: null,
  allTransitiveDependencies: null,
);

@Deprecated('Will be removed in 3.0. Use Ref instead')
// ignore: unused_element
typedef ExplanationRepositoryRef
    = AutoDisposeProviderRef<ExplanationRepository>;
String _$generateExplanationUseCaseHash() =>
    r'd86d365ecab6bd08c87c5b73c004cb6c2d541ab5';

/// 生成解释UseCase Provider
///
/// 提供核心业务逻辑，用于生成艺术品解释。
/// 在Presentation层通过此Provider调用业务逻辑。
///
/// Copied from [generateExplanationUseCase].
@ProviderFor(generateExplanationUseCase)
final generateExplanationUseCaseProvider =
    AutoDisposeProvider<GenerateExplanation>.internal(
  generateExplanationUseCase,
  name: r'generateExplanationUseCaseProvider',
  debugGetCreateSourceHash: const bool.fromEnvironment('dart.vm.product')
      ? null
      : _$generateExplanationUseCaseHash,
  dependencies: null,
  allTransitiveDependencies: null,
);

@Deprecated('Will be removed in 3.0. Use Ref instead')
// ignore: unused_element
typedef GenerateExplanationUseCaseRef
    = AutoDisposeProviderRef<GenerateExplanation>;
// ignore_for_file: type=lint
// ignore_for_file: subtype_of_sealed_class, invalid_use_of_internal_member, invalid_use_of_visible_for_testing_member, deprecated_member_use_from_same_package
