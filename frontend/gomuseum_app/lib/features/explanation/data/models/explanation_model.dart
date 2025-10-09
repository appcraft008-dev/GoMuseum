import 'package:gomuseum_app/features/explanation/domain/entities/explanation.dart';

/// Explanation的数据模型（带JSON序列化）
///
/// 该模型用于数据层，负责与后端API和本地存储进行数据交互。
/// 继承自Domain层的Explanation实体，添加JSON序列化/反序列化功能。
class ExplanationModel extends Explanation {
  const ExplanationModel({
    required super.id,
    required super.artworkName,
    required super.language,
    required super.content,
    super.audioUrl,
    super.audioDurationSeconds,
    required super.timestamp,
    required super.cached,
    required super.processingTimeMs,
    required super.metadata,
  });

  /// 从后端API响应JSON创建Model
  ///
  /// 处理snake_case到camelCase的转换，以及嵌套对象的解析。
  ///
  /// 示例JSON:
  /// ```json
  /// {
  ///   "id": "uuid",
  ///   "artwork_name": "Mona Lisa",
  ///   "language": "en",
  ///   "content": "...",
  ///   "audio_url": "http://localhost:8000/audio/xxx.mp3",
  ///   "audio_duration_seconds": 49,
  ///   "timestamp": "2025-10-06T05:26:47",
  ///   "cached": false,
  ///   "processing_time_ms": 0,
  ///   "metadata": {
  ///     "word_count": 85,
  ///     "detail_level": "brief"
  ///   }
  /// }
  /// ```
  factory ExplanationModel.fromJson(Map<String, dynamic> json) {
    return ExplanationModel(
      id: json['id'] as String,
      artworkName: json['artwork_name'] as String,
      language: json['language'] as String,
      content: json['content'] as String,
      audioUrl: json['audio_url'] as String?,
      audioDurationSeconds: json['audio_duration_seconds'] as int?,
      timestamp: DateTime.parse(json['timestamp'] as String),
      cached: json['cached'] as bool,
      processingTimeMs: json['processing_time_ms'] as int,
      metadata: ExplanationMetadataModel.fromJson(
        json['metadata'] as Map<String, dynamic>,
      ),
    );
  }

  /// 转换为JSON（用于本地存储或API请求）
  ///
  /// 输出格式与后端API保持一致（snake_case）
  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'artwork_name': artworkName,
      'language': language,
      'content': content,
      'audio_url': audioUrl,
      'audio_duration_seconds': audioDurationSeconds,
      'timestamp': timestamp.toIso8601String(),
      'cached': cached,
      'processing_time_ms': processingTimeMs,
      'metadata': (metadata as ExplanationMetadataModel).toJson(),
    };
  }

  /// 从Domain Entity创建Model
  ///
  /// 用于将业务实体转换为数据模型，通常在需要持久化或发送数据时使用。
  factory ExplanationModel.fromEntity(Explanation entity) {
    return ExplanationModel(
      id: entity.id,
      artworkName: entity.artworkName,
      language: entity.language,
      content: entity.content,
      audioUrl: entity.audioUrl,
      audioDurationSeconds: entity.audioDurationSeconds,
      timestamp: entity.timestamp,
      cached: entity.cached,
      processingTimeMs: entity.processingTimeMs,
      metadata: ExplanationMetadataModel.fromEntity(entity.metadata),
    );
  }
}

/// ExplanationMetadata的数据模型（带JSON序列化）
class ExplanationMetadataModel extends ExplanationMetadata {
  const ExplanationMetadataModel({
    required super.wordCount,
    required super.detailLevel,
  });

  /// 从JSON创建MetadataModel
  factory ExplanationMetadataModel.fromJson(Map<String, dynamic> json) {
    return ExplanationMetadataModel(
      wordCount: json['word_count'] as int,
      detailLevel: json['detail_level'] as String,
    );
  }

  /// 转换为JSON
  Map<String, dynamic> toJson() {
    return {
      'word_count': wordCount,
      'detail_level': detailLevel,
    };
  }

  /// 从Domain Entity创建MetadataModel
  factory ExplanationMetadataModel.fromEntity(ExplanationMetadata entity) {
    return ExplanationMetadataModel(
      wordCount: entity.wordCount,
      detailLevel: entity.detailLevel,
    );
  }
}
