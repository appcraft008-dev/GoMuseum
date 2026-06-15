import 'dart:io' show Platform;
import 'package:dio/dio.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';
import '../../../../core/network/auth_interceptor.dart';
import '../../../../core/network/network_info.dart';
import '../../data/datasources/recognition_local_datasource.dart';
import '../../data/datasources/recognition_remote_datasource.dart';
import '../../data/repositories/recognition_repository_impl.dart';
import '../../domain/repositories/recognition_repository.dart';
import '../../domain/usecases/recognize_artwork.dart';

// 条件导入：根据平台选择数据源实现
import '../../data/datasources/recognition_local_datasource_impl.dart'
    if (dart.library.html) '../../data/datasources/recognition_local_datasource_stub.dart';

part 'recognition_providers.g.dart';

/// Dio客户端Provider
@riverpod
Dio dio(DioRef ref) {
  // 发布版通过 --dart-define=API_BASE_URL=https://api.gomuseum.app 指定；
  // 未指定时本地开发：Android 模拟器用 10.0.2.2 访问宿主机
  const envUrl = String.fromEnvironment('API_BASE_URL', defaultValue: '');
  String baseUrl = envUrl.isNotEmpty ? envUrl : 'http://localhost:8000';
  if (envUrl.isEmpty) {
    try {
      if (Platform.isAndroid) {
        baseUrl = 'http://10.0.2.2:8000';
      }
    } catch (e) {
      // Web 平台会抛出异常，使用默认 localhost
    }
  }

  final options = BaseOptions(
    baseUrl: baseUrl,
    connectTimeout: const Duration(seconds: 60),
    receiveTimeout: const Duration(seconds: 60),
  );
  final client = Dio(options);
  // 业务请求自动附带 Bearer token，401 时刷新并重试
  client.interceptors.add(AuthInterceptor(refreshDio: Dio(options)));
  return client;
}

/// 网络信息Provider
@riverpod
NetworkInfo networkInfo(NetworkInfoRef ref) {
  return NetworkInfoImpl();
}

/// 远程数据源Provider
@riverpod
RecognitionRemoteDataSource recognitionRemoteDataSource(
    RecognitionRemoteDataSourceRef ref) {
  return RecognitionRemoteDataSourceImpl(dio: ref.watch(dioProvider));
}

/// 本地数据源Provider - 根据平台选择实现
@riverpod
RecognitionLocalDataSource recognitionLocalDataSource(
    RecognitionLocalDataSourceRef ref) {
  // 条件导入会根据平台自动选择正确的实现
  return RecognitionLocalDataSourceImpl();
}

/// Repository Provider
@riverpod
RecognitionRepository recognitionRepository(RecognitionRepositoryRef ref) {
  return RecognitionRepositoryImpl(
    remoteDataSource: ref.watch(recognitionRemoteDataSourceProvider),
    localDataSource: ref.watch(recognitionLocalDataSourceProvider),
    networkInfo: ref.watch(networkInfoProvider),
  );
}

/// UseCase Provider
@riverpod
RecognizeArtwork recognizeArtworkUseCase(RecognizeArtworkUseCaseRef ref) {
  return RecognizeArtwork(repository: ref.watch(recognitionRepositoryProvider));
}
