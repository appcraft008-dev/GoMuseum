import 'package:dartz/dartz.dart';
import 'package:gomuseum_app/core/error/failures.dart';
import 'package:gomuseum_app/features/content/domain/entities/explanation.dart';

/// Content Repository接口(抽象类)
abstract class ContentRepository {
  /// 生成艺术品讲解
  ///
  /// [artworkName] - 艺术品名称
  /// [artist] - 艺术家
  /// [period] - 时期
  /// [language] - 语言代码(如: en, zh, ja)
  /// [description] - 可选的额外描述信息
  Future<Either<Failure, Explanation>> generateExplanation({
    required String artworkName,
    required String artist,
    required String period,
    required String language,
    String? description,
  });

  /// 生成TTS音频
  ///
  /// [text] - 要转换为语音的文本
  /// [language] - 语言代码
  /// [voice] - 可选的语音类型
  /// [speed] - 可选的播放速度
  /// 返回音频文件的URL或路径
  Future<Either<Failure, String>> generateTtsAudio({
    required String text,
    required String language,
    String? voice,
    double? speed,
  });
}
