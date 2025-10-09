import 'dart:io' show Platform;
import 'package:dio/dio.dart';
import 'package:logger/logger.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';
import 'package:gomuseum_app/core/network/network_info.dart';
import 'package:gomuseum_app/features/explanation/data/datasources/explanation_remote_datasource.dart';
import 'package:gomuseum_app/features/explanation/data/datasources/explanation_remote_datasource_impl.dart';
import 'package:gomuseum_app/features/explanation/data/repositories/explanation_repository_impl.dart';
import 'package:gomuseum_app/features/explanation/domain/repositories/explanation_repository.dart';
import 'package:gomuseum_app/features/explanation/domain/usecases/generate_explanation.dart';

part 'explanation_providers.g.dart';

/// Dio客户端Provider
///
/// 提供配置好的HTTP客户端，支持跨平台基础URL配置。
/// Android模拟器使用10.0.2.2访问宿主机，其他平台使用localhost。
@riverpod
Dio dio(DioRef ref) {
  // Android模拟器需要使用10.0.2.2访问宿主机
  String baseUrl = 'http://localhost:8000';
  try {
    if (Platform.isAndroid) {
      baseUrl = 'http://10.0.2.2:8000';
    }
  } catch (e) {
    // Web平台会抛出异常，使用默认localhost
  }

  return Dio(BaseOptions(
    baseUrl: baseUrl,
    connectTimeout: const Duration(seconds: 60),
    receiveTimeout: const Duration(seconds: 60),
    headers: {
      'Content-Type': 'application/json',
      'Accept': 'application/json',
    },
  ));
}

/// Logger实例Provider
///
/// 提供统一的日志记录器，用于调试和错误追踪。
/// 配置为在开发模式下输出详细日志。
@riverpod
Logger logger(LoggerRef ref) {
  return Logger(
    printer: PrettyPrinter(
      methodCount: 2,
      errorMethodCount: 8,
      lineLength: 120,
      colors: true,
      printEmojis: true,
      printTime: true,
    ),
  );
}

/// 网络信息Provider
///
/// 提供网络连接状态检查功能，用于离线/在线模式切换。
@riverpod
NetworkInfo networkInfo(NetworkInfoRef ref) {
  return NetworkInfoImpl();
}

/// 解释功能远程数据源Provider
///
/// 提供与后端API交互的数据源实例，依赖于Dio客户端和Logger。
@riverpod
ExplanationRemoteDataSource explanationRemoteDataSource(
  ExplanationRemoteDataSourceRef ref,
) {
  return ExplanationRemoteDataSourceImpl(
    dio: ref.watch(dioProvider),
    logger: ref.watch(loggerProvider),
  );
}

/// 解释功能Repository Provider
///
/// 提供数据仓库实例，协调远程数据源。
/// 遵循Clean Architecture的依赖倒置原则。
@riverpod
ExplanationRepository explanationRepository(
  ExplanationRepositoryRef ref,
) {
  return ExplanationRepositoryImpl(
    remoteDataSource: ref.watch(explanationRemoteDataSourceProvider),
  );
}

/// 生成解释UseCase Provider
///
/// 提供核心业务逻辑，用于生成艺术品解释。
/// 在Presentation层通过此Provider调用业务逻辑。
@riverpod
GenerateExplanation generateExplanationUseCase(
  GenerateExplanationUseCaseRef ref,
) {
  return GenerateExplanation(
    repository: ref.watch(explanationRepositoryProvider),
  );
}
