import 'dart:io';
import 'package:dartz/dartz.dart';
import '../../../../core/error/failures.dart';
import '../entities/recognition_result.dart';

/// Repository接口(抽象类)
abstract class RecognitionRepository {
  /// 识别艺术品图片
  Future<Either<Failure, RecognitionResult>> recognizeArtwork(File imageFile);

  /// 根据图片哈希获取缓存结果
  Future<Either<Failure, RecognitionResult?>> getCachedResult(String imageHash);
}
