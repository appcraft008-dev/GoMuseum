/// Web平台的本地数据源桩实现
/// 在Web平台上禁用Drift数据库，避免dart:ffi错误
///
/// 注意：此类使用与原生平台相同的类名 RecognitionLocalDataSourceImpl
/// 这样条件导入才能正常工作
library;

import 'package:gomuseum_app/features/recognition/data/models/recognition_result_model.dart';
import 'package:gomuseum_app/features/recognition/data/datasources/recognition_local_datasource.dart';

/// Web平台的空实现，不使用本地数据库
/// 类名与原生平台实现保持一致，通过条件导入选择
class RecognitionLocalDataSourceImpl implements RecognitionLocalDataSource {
  // 工厂构造函数，保持与原生平台API一致
  factory RecognitionLocalDataSourceImpl() {
    return const RecognitionLocalDataSourceImpl._();
  }

  const RecognitionLocalDataSourceImpl._();

  @override
  Future<RecognitionResultModel?> getCachedResult(String imageHash) async {
    // Web平台不支持本地缓存
    return null;
  }

  @override
  Future<void> cacheResult(
      String imageHash, RecognitionResultModel result) async {
    // Web平台不缓存
  }

  @override
  Future<void> deleteCacheByHash(String imageHash) async {
    // Web平台无需删除
  }
}
