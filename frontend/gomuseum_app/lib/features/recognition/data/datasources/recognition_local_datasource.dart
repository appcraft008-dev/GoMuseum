import 'package:gomuseum_app/core/error/exceptions.dart';
import 'package:gomuseum_app/features/recognition/data/models/recognition_result_model.dart';
import 'package:gomuseum_app/features/recognition/data/datasources/recognition_drift_database.dart';

/// 本地数据源接口
abstract class RecognitionLocalDataSource {
  Future<RecognitionResultModel?> getCachedResult(String imageHash);
  Future<void> cacheResult(String imageHash, RecognitionResultModel result);
}

/// 本地数据源实现
class RecognitionLocalDataSourceImpl implements RecognitionLocalDataSource {
  final AppDatabase database;

  const RecognitionLocalDataSourceImpl({required this.database});

  @override
  Future<RecognitionResultModel?> getCachedResult(String imageHash) async {
    try {
      final data = await database.getRecognitionByHash(imageHash);
      if (data == null) {
        return null;
      }
      return RecognitionResultModel.fromDrift(data);
    } catch (e) {
      throw CacheException('Failed to get cached result: $e');
    }
  }

  @override
  Future<void> cacheResult(
      String imageHash, RecognitionResultModel result) async {
    try {
      await database.insertOrUpdateRecognition(result.toDrift(imageHash));
    } catch (e) {
      throw CacheException('Failed to cache result: $e');
    }
  }
}
