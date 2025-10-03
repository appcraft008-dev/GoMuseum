import 'package:dio/dio.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';
import '../../../../core/network/network_info.dart';
import '../../data/datasources/recognition_drift_database.dart';
import '../../data/datasources/recognition_local_datasource.dart';
import '../../data/datasources/recognition_remote_datasource.dart';
import '../../data/repositories/recognition_repository_impl.dart';
import '../../domain/repositories/recognition_repository.dart';
import '../../domain/usecases/recognize_artwork.dart';

part 'recognition_providers.g.dart';

/// Dio客户端Provider
@riverpod
Dio dio(DioRef ref) {
  return Dio(BaseOptions(
    baseUrl: 'http://localhost:8000',
    connectTimeout: const Duration(seconds: 5),
    receiveTimeout: const Duration(seconds: 5),
  ));
}

/// 数据库Provider
@riverpod
AppDatabase appDatabase(AppDatabaseRef ref) {
  return AppDatabase();
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

/// 本地数据源Provider
@riverpod
RecognitionLocalDataSource recognitionLocalDataSource(
    RecognitionLocalDataSourceRef ref) {
  return RecognitionLocalDataSourceImpl(
      database: ref.watch(appDatabaseProvider));
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
