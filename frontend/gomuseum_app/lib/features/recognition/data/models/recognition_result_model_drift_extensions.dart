/// Drift数据库相关的转换器扩展
/// 此文件仅在原生平台导入，Web平台不会使用
import 'package:gomuseum_app/features/recognition/data/models/recognition_result_model.dart';
import 'package:gomuseum_app/features/recognition/data/datasources/recognition_drift_database.dart';

/// RecognitionResultModel的Drift转换扩展
extension RecognitionResultModelDriftExtensions on RecognitionResultModel {
  /// 转换为Drift Companion对象
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
}

/// Drift数据转换辅助类
class RecognitionResultModelDriftConverter {
  /// 从Drift数据创建Model
  static RecognitionResultModel fromDrift(RecognitionResultData data) {
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
}
