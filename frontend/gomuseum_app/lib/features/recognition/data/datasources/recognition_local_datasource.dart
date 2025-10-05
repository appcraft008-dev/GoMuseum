import 'package:gomuseum_app/features/recognition/data/models/recognition_result_model.dart';

/// 本地数据源接口
abstract class RecognitionLocalDataSource {
  Future<RecognitionResultModel?> getCachedResult(String imageHash);
  Future<void> cacheResult(String imageHash, RecognitionResultModel result);
  Future<void> deleteCacheByHash(String imageHash);
}
