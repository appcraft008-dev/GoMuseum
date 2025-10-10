import 'package:dartz/dartz.dart';
import 'package:gomuseum_app/core/error/failures.dart';
import 'package:gomuseum_app/features/content/domain/entities/explanation.dart';
import 'package:gomuseum_app/features/content/domain/repositories/content_repository.dart';

/// 生成艺术品讲解的UseCase
class GenerateExplanation {
  final ContentRepository repository;

  const GenerateExplanation({required this.repository});

  /// 执行生成讲解
  ///
  /// [params] - 包含艺术品信息的参数对象
  Future<Either<Failure, Explanation>> call(
      GenerateExplanationParams params) async {
    // 1. 验证输入参数
    final validationResult = _validateParams(params);
    if (validationResult != null) {
      return Left(validationResult);
    }

    // 2. 调用Repository生成讲解
    return await repository.generateExplanation(
      artworkName: params.artworkName,
      artist: params.artist,
      period: params.period,
      language: params.language,
      description: params.description,
    );
  }

  /// 验证输入参数
  Failure? _validateParams(GenerateExplanationParams params) {
    if (params.artworkName.trim().isEmpty) {
      return const ValidationFailure('Artwork name cannot be empty');
    }
    if (params.artist.trim().isEmpty) {
      return const ValidationFailure('Artist name cannot be empty');
    }
    if (params.period.trim().isEmpty) {
      return const ValidationFailure('Period cannot be empty');
    }
    if (params.language.trim().isEmpty) {
      return const ValidationFailure('Language cannot be empty');
    }
    // 验证语言代码格式(2-3个字母)
    if (!RegExp(r'^[a-z]{2,3}$').hasMatch(params.language.toLowerCase())) {
      return const ValidationFailure('Invalid language code format');
    }
    return null;
  }
}

/// 生成讲解的参数类
class GenerateExplanationParams {
  final String artworkName;
  final String artist;
  final String period;
  final String language;
  final String? description;

  const GenerateExplanationParams({
    required this.artworkName,
    required this.artist,
    required this.period,
    required this.language,
    this.description,
  });
}
