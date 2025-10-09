import 'package:equatable/equatable.dart';

/// 艺术品解释实体（纯业务对象，无依赖）
///
/// 包含AI生成的艺术品解释信息，支持多语言和音频输出。
/// 该实体遵循Clean Architecture原则，不依赖任何框架或外部库（除Equatable）。
class Explanation extends Equatable {
  /// 解释记录的唯一标识符
  final String id;

  /// 艺术品名称
  final String artworkName;

  /// 语言代码（en, fr, de, es, it, zh）
  final String language;

  /// 解释文本内容
  final String content;

  /// 音频文件URL（可选）
  final String? audioUrl;

  /// 音频时长（秒）
  final int? audioDurationSeconds;

  /// 创建时间戳
  final DateTime timestamp;

  /// 是否来自缓存
  final bool cached;

  /// 处理时长（毫秒）
  final int processingTimeMs;

  /// 元数据信息
  final ExplanationMetadata metadata;

  const Explanation({
    required this.id,
    required this.artworkName,
    required this.language,
    required this.content,
    this.audioUrl,
    this.audioDurationSeconds,
    required this.timestamp,
    required this.cached,
    required this.processingTimeMs,
    required this.metadata,
  });

  @override
  List<Object?> get props => [
        id,
        artworkName,
        language,
        content,
        audioUrl,
        audioDurationSeconds,
        timestamp,
        cached,
        processingTimeMs,
        metadata,
      ];

  @override
  String toString() {
    return 'Explanation(id: $id, artworkName: $artworkName, language: $language, '
        'cached: $cached, processingTimeMs: ${processingTimeMs}ms, '
        'audioUrl: ${audioUrl != null ? "available" : "none"})';
  }

  /// 复制实例并修改部分字段
  Explanation copyWith({
    String? id,
    String? artworkName,
    String? language,
    String? content,
    String? audioUrl,
    int? audioDurationSeconds,
    DateTime? timestamp,
    bool? cached,
    int? processingTimeMs,
    ExplanationMetadata? metadata,
  }) {
    return Explanation(
      id: id ?? this.id,
      artworkName: artworkName ?? this.artworkName,
      language: language ?? this.language,
      content: content ?? this.content,
      audioUrl: audioUrl ?? this.audioUrl,
      audioDurationSeconds: audioDurationSeconds ?? this.audioDurationSeconds,
      timestamp: timestamp ?? this.timestamp,
      cached: cached ?? this.cached,
      processingTimeMs: processingTimeMs ?? this.processingTimeMs,
      metadata: metadata ?? this.metadata,
    );
  }
}

/// 解释元数据
///
/// 包含解释的详细统计信息和配置参数。
class ExplanationMetadata extends Equatable {
  /// 字数统计
  final int wordCount;

  /// 详细程度（brief, standard, detailed）
  final String detailLevel;

  const ExplanationMetadata({
    required this.wordCount,
    required this.detailLevel,
  });

  @override
  List<Object?> get props => [wordCount, detailLevel];

  @override
  String toString() {
    return 'ExplanationMetadata(wordCount: $wordCount, detailLevel: $detailLevel)';
  }

  /// 复制实例并修改部分字段
  ExplanationMetadata copyWith({
    int? wordCount,
    String? detailLevel,
  }) {
    return ExplanationMetadata(
      wordCount: wordCount ?? this.wordCount,
      detailLevel: detailLevel ?? this.detailLevel,
    );
  }
}
