import 'package:gomuseum_app/features/recognition/data/datasources/recognition_drift_database.dart';

/// 缓存管理工具类
class CacheManager {
  final AppDatabase database;

  const CacheManager({required this.database});

  /// 清除所有本地缓存
  Future<void> clearAllCache() async {
    await database.deleteAllRecognitions();
  }

  /// 清除特定图片哈希的缓存
  Future<void> clearCacheByHash(String imageHash) async {
    await (database.delete(database.recognitionResults)
          ..where((t) => t.imageHash.equals(imageHash)))
        .go();
  }

  /// 清除所有"Unknown Artwork"的失败记录
  Future<void> clearFailedRecognitions() async {
    await (database.delete(database.recognitionResults)
          ..where((t) => t.artworkName.equals('Unknown Artwork')))
        .go();
  }

  /// 获取缓存统计信息
  Future<Map<String, int>> getCacheStats() async {
    final all = await database.select(database.recognitionResults).get();
    final failed = all.where((r) => r.artworkName == 'Unknown Artwork').length;
    final success = all.length - failed;

    return {
      'total': all.length,
      'success': success,
      'failed': failed,
    };
  }
}
