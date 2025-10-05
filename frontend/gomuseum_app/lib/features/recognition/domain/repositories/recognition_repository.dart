import 'package:cross_file/cross_file.dart';
import 'package:dartz/dartz.dart';
import '../../../../core/error/failures.dart';
import '../entities/recognition_result.dart';

/// Repository接口(抽象类)
abstract class RecognitionRepository {
  /// 识别艺术品图片
  Future<Either<Failure, RecognitionResult>> recognizeArtwork(XFile imageFile);

  /// 识别艺术品图片（强制跳过缓存）
  Future<Either<Failure, RecognitionResult>> recognizeArtworkForceFresh(
      XFile imageFile);

  /// 根据图片哈希获取缓存结果
  Future<Either<Failure, RecognitionResult?>> getCachedResult(String imageHash);

  /// 清除特定图片哈希的缓存
  Future<Either<Failure, void>> clearCacheByHash(String imageHash);
}
