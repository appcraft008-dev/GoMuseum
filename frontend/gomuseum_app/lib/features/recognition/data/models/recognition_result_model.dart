import 'package:gomuseum_app/features/recognition/domain/entities/recognition_result.dart';
import 'package:gomuseum_app/features/recognition/data/datasources/recognition_drift_database.dart';

/// RecognitionResult的数据模型(带JSON序列化)
class RecognitionResultModel extends RecognitionResult {
  const RecognitionResultModel({
    required super.id,
    required super.artworkName,
    required super.artist,
    required super.period,
    required super.description,
    required super.confidence,
    required super.timestamp,
  });

  /// 从JSON创建
  factory RecognitionResultModel.fromJson(Map<String, dynamic> json) {
    return RecognitionResultModel(
      id: json['id'] as String,
      artworkName: json['artwork_name'] as String,
      artist: json['artist'] as String,
      period: json['period'] as String,
      description: json['description'] as String,
      confidence: (json['confidence'] as num).toDouble(),
      timestamp: DateTime.parse(json['timestamp'] as String),
    );
  }

  /// 转换为JSON
  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'artwork_name': artworkName,
      'artist': artist,
      'period': period,
      'description': description,
      'confidence': confidence,
      'timestamp': timestamp.toIso8601String(),
    };
  }

  /// 从Drift数据创建
  factory RecognitionResultModel.fromDrift(RecognitionResultData data) {
    return RecognitionResultModel(
      id: data.id,
      artworkName: data.artworkName,
      artist: data.artist,
      period: data.period,
      description: data.description,
      confidence: data.confidence,
      timestamp: data.timestamp,
    );
  }

  /// 转换为Drift数据
  RecognitionResultsCompanion toDrift(String imageHash) {
    return RecognitionResultsCompanion.insert(
      imageHash: imageHash,
      id: id,
      artworkName: artworkName,
      artist: artist,
      period: period,
      description: description,
      confidence: confidence,
      timestamp: timestamp,
    );
  }

  /// 从Entity创建Model
  factory RecognitionResultModel.fromEntity(RecognitionResult entity) {
    return RecognitionResultModel(
      id: entity.id,
      artworkName: entity.artworkName,
      artist: entity.artist,
      period: entity.period,
      description: entity.description,
      confidence: entity.confidence,
      timestamp: entity.timestamp,
    );
  }
}
