import 'package:dartz/dartz.dart';
import 'package:equatable/equatable.dart';
import 'package:gomuseum_app/core/error/failures.dart';
import 'package:gomuseum_app/features/explanation/domain/entities/explanation.dart';
import 'package:gomuseum_app/features/explanation/domain/repositories/explanation_repository.dart';

/// 生成艺术品解释的UseCase业务逻辑
///
/// 负责调用Repository生成AI解释，并进行必要的参数验证。
/// 遵循Clean Architecture的单一职责原则。
class GenerateExplanation {
  final ExplanationRepository repository;

  const GenerateExplanation({required this.repository});

  /// 执行解释生成
  ///
  /// [params] 包含生成解释所需的所有参数
  ///
  /// 返回 [Either<Failure, Explanation>]：
  /// - Left(Failure)：参数验证失败或API请求失败
  /// - Right(Explanation)：生成成功，返回解释实体
  Future<Either<Failure, Explanation>> call(
    GenerateExplanationParams params,
  ) async {
    // 1. 验证参数
    final validationResult = _validateParams(params);
    if (validationResult != null) {
      return Left(validationResult);
    }

    // 2. 调用Repository生成解释
    return await repository.generateExplanation(
      artworkName: params.artworkName,
      language: params.language,
      detailLevel: params.detailLevel,
      includeAudio: params.includeAudio,
      recognitionId: params.recognitionId,
    );
  }

  /// 验证参数有效性
  ///
  /// 返回 [Failure?]：
  /// - null：参数有效
  /// - ValidationFailure：参数无效，包含错误信息
  Failure? _validateParams(GenerateExplanationParams params) {
    // 验证艺术品名称
    if (params.artworkName.trim().isEmpty) {
      return const ValidationFailure('Artwork name cannot be empty');
    }

    // 验证语言代码
    const supportedLanguages = ['en', 'fr', 'de', 'es', 'it', 'zh'];
    if (!supportedLanguages.contains(params.language)) {
      return ValidationFailure(
        'Unsupported language: ${params.language}. '
        'Supported languages: ${supportedLanguages.join(", ")}',
      );
    }

    // 验证详细程度
    const supportedDetailLevels = ['brief', 'standard', 'detailed'];
    if (!supportedDetailLevels.contains(params.detailLevel)) {
      return ValidationFailure(
        'Unsupported detail level: ${params.detailLevel}. '
        'Supported levels: ${supportedDetailLevels.join(", ")}',
      );
    }

    return null;
  }
}

/// 生成解释的参数封装
///
/// 使用Equatable实现值比较，便于测试和状态管理。
class GenerateExplanationParams extends Equatable {
  /// 艺术品名称（必需）
  final String artworkName;

  /// 语言代码（必需）：en, fr, de, es, it, zh
  final String language;

  /// 详细程度（可选，默认'standard'）：brief, standard, detailed
  final String detailLevel;

  /// 是否生成音频（可选，默认false）
  final bool includeAudio;

  /// 关联的识别记录ID（可选）
  final String? recognitionId;

  const GenerateExplanationParams({
    required this.artworkName,
    required this.language,
    this.detailLevel = 'standard',
    this.includeAudio = false,
    this.recognitionId,
  });

  @override
  List<Object?> get props => [
        artworkName,
        language,
        detailLevel,
        includeAudio,
        recognitionId,
      ];

  @override
  String toString() {
    return 'GenerateExplanationParams('
        'artworkName: $artworkName, '
        'language: $language, '
        'detailLevel: $detailLevel, '
        'includeAudio: $includeAudio, '
        'recognitionId: $recognitionId)';
  }

  /// 复制实例并修改部分字段
  GenerateExplanationParams copyWith({
    String? artworkName,
    String? language,
    String? detailLevel,
    bool? includeAudio,
    String? recognitionId,
  }) {
    return GenerateExplanationParams(
      artworkName: artworkName ?? this.artworkName,
      language: language ?? this.language,
      detailLevel: detailLevel ?? this.detailLevel,
      includeAudio: includeAudio ?? this.includeAudio,
      recognitionId: recognitionId ?? this.recognitionId,
    );
  }
}
