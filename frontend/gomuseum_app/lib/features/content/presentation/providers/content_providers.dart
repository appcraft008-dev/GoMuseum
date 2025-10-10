import 'package:riverpod_annotation/riverpod_annotation.dart';
import 'package:gomuseum_app/features/content/data/datasources/content_remote_datasource.dart';
import 'package:gomuseum_app/features/content/data/repositories/content_repository_impl.dart';
import 'package:gomuseum_app/features/content/domain/repositories/content_repository.dart';
import 'package:gomuseum_app/features/content/domain/usecases/generate_explanation.dart';
import 'package:gomuseum_app/features/content/domain/usecases/generate_tts_audio.dart';

// 导入Recognition模块的Dio provider以复用
import 'package:gomuseum_app/features/recognition/presentation/providers/recognition_providers.dart';

part 'content_providers.g.dart';

/// 远程数据源Provider
@riverpod
ContentRemoteDataSource contentRemoteDataSource(
    ContentRemoteDataSourceRef ref) {
  // 复用Recognition模块的Dio实例
  return ContentRemoteDataSourceImpl(dio: ref.watch(dioProvider));
}

/// Repository Provider
@riverpod
ContentRepository contentRepository(ContentRepositoryRef ref) {
  return ContentRepositoryImpl(
    remoteDataSource: ref.watch(contentRemoteDataSourceProvider),
  );
}

/// GenerateExplanation UseCase Provider
@riverpod
GenerateExplanation generateExplanationUseCase(
    GenerateExplanationUseCaseRef ref) {
  return GenerateExplanation(
    repository: ref.watch(contentRepositoryProvider),
  );
}

/// GenerateTtsAudio UseCase Provider
@riverpod
GenerateTtsAudio generateTtsAudioUseCase(GenerateTtsAudioUseCaseRef ref) {
  return GenerateTtsAudio(
    repository: ref.watch(contentRepositoryProvider),
  );
}
