/// 原生平台的本地数据源实现
/// 此文件仅在原生平台(macOS, iOS, Android)导入
import 'package:gomuseum_app/core/error/exceptions.dart';
import 'package:gomuseum_app/features/recognition/data/models/recognition_result_model.dart';
import 'package:gomuseum_app/features/recognition/data/models/recognition_result_model_drift_extensions.dart';
import 'package:gomuseum_app/features/recognition/data/datasources/recognition_local_datasource.dart';
import 'package:gomuseum_app/features/recognition/data/datasources/recognition_drift_database.dart';

/// 本地数据源实现（使用Drift数据库）
class RecognitionLocalDataSourceImpl implements RecognitionLocalDataSource {
  final AppDatabase _database;

  // 懒加载单例
  static RecognitionLocalDataSourceImpl? _instance;

  RecognitionLocalDataSourceImpl._internal(this._database);

  factory RecognitionLocalDataSourceImpl() {
    _instance ??= RecognitionLocalDataSourceImpl._internal(AppDatabase());
    return _instance!;
  }

  @override
  Future<RecognitionResultModel?> getCachedResult(String imageHash) async {
    try {
      final data = await _database.getRecognitionByHash(imageHash);
      if (data == null) {
        return null;
      }
      return RecognitionResultModelDriftConverter.fromDrift(data);
    } catch (e) {
      throw CacheException('Failed to get cached result: $e');
    }
  }

  @override
  Future<void> cacheResult(
      String imageHash, RecognitionResultModel result) async {
    try {
      await _database.insertOrUpdateRecognition(result.toDrift(imageHash));
    } catch (e) {
      throw CacheException('Failed to cache result: $e');
    }
  }

  @override
  Future<void> deleteCacheByHash(String imageHash) async {
    try {
      await (_database.delete(_database.recognitionResults)
            ..where((t) => t.imageHash.equals(imageHash)))
          .go();
    } catch (e) {
      throw CacheException('Failed to delete cache: $e');
    }
  }
}
