import 'package:dartz/dartz.dart';
import 'package:gomuseum_app/core/error/failures.dart';
import 'package:gomuseum_app/features/content/domain/repositories/content_repository.dart';

/// 生成TTS音频的UseCase
class GenerateTtsAudio {
  final ContentRepository repository;

  const GenerateTtsAudio({required this.repository});

  /// 执行生成TTS音频
  ///
  /// [params] - 包含TTS参数的对象
  /// 返回音频文件的URL或路径
  Future<Either<Failure, String>> call(GenerateTtsAudioParams params) async {
    // 1. 验证输入参数
    final validationResult = _validateParams(params);
    if (validationResult != null) {
      return Left(validationResult);
    }

    // 2. 调用Repository生成音频
    return await repository.generateTtsAudio(
      text: params.text,
      language: params.language,
      voice: params.voice,
      speed: params.speed,
    );
  }

  /// 验证输入参数
  Failure? _validateParams(GenerateTtsAudioParams params) {
    if (params.text.trim().isEmpty) {
      return const ValidationFailure('Text cannot be empty');
    }
    if (params.language.trim().isEmpty) {
      return const ValidationFailure('Language cannot be empty');
    }
    // 验证语言代码格式(2-3个字母)
    if (!RegExp(r'^[a-z]{2,3}$').hasMatch(params.language.toLowerCase())) {
      return const ValidationFailure('Invalid language code format');
    }
    // 验证播放速度范围(如果提供)
    if (params.speed != null && (params.speed! < 0.5 || params.speed! > 2.0)) {
      return const ValidationFailure('Speed must be between 0.5 and 2.0');
    }
    return null;
  }
}

/// 生成TTS音频的参数类
class GenerateTtsAudioParams {
  final String text;
  final String language;
  final String? voice;
  final double? speed;

  const GenerateTtsAudioParams({
    required this.text,
    required this.language,
    this.voice,
    this.speed,
  });
}
