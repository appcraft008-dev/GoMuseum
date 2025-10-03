import 'dart:io';
import 'dart:convert';
import 'package:dartz/dartz.dart';
import 'package:crypto/crypto.dart';
import '../../../../core/error/exceptions.dart';
import '../../../../core/error/failures.dart';
import '../../../../core/network/network_info.dart';
import '../../domain/entities/recognition_result.dart';
import '../../domain/repositories/recognition_repository.dart';
import '../datasources/recognition_local_datasource.dart';
import '../datasources/recognition_remote_datasource.dart';

/// Repository实现
class RecognitionRepositoryImpl implements RecognitionRepository {
  final RecognitionRemoteDataSource remoteDataSource;
  final RecognitionLocalDataSource localDataSource;
  final NetworkInfo networkInfo;

  const RecognitionRepositoryImpl({
    required this.remoteDataSource,
    required this.localDataSource,
    required this.networkInfo,
  });

  @override
  Future<Either<Failure, RecognitionResult>> recognizeArtwork(
      File imageFile) async {
    try {
      // 1. 生成图片哈希
      final imageHash = await _generateImageHash(imageFile);

      // 2. 先查缓存
      try {
        final cachedResult = await localDataSource.getCachedResult(imageHash);
        if (cachedResult != null) {
          return Right(cachedResult);
        }
      } catch (e) {
        // 缓存失败不影响主流程,继续调用远程API
      }

      // 3. 检查网络连接
      final isConnected = await networkInfo.isConnected;
      if (!isConnected) {
        return const Left(NetworkFailure('No network connection'));
      }

      // 4. 调用远程API
      final base64Image = await _imageToBase64(imageFile);
      final result = await remoteDataSource.recognizeArtwork(base64Image);

      // 5. 存入缓存
      try {
        await localDataSource.cacheResult(imageHash, result);
      } catch (e) {
        // 缓存失败不影响返回结果
      }

      return Right(result);
    } on ValidationException catch (e) {
      return Left(ValidationFailure(e.message));
    } on NetworkException catch (e) {
      return Left(NetworkFailure(e.message));
    } on TimeoutException catch (e) {
      return Left(TimeoutFailure(e.message));
    } on ServerException catch (e) {
      return Left(ServerFailure(e.message));
    } on CacheException catch (e) {
      return Left(CacheFailure(e.message));
    } catch (e) {
      return Left(ServerFailure('Unexpected error: $e'));
    }
  }

  @override
  Future<Either<Failure, RecognitionResult?>> getCachedResult(
      String imageHash) async {
    try {
      final result = await localDataSource.getCachedResult(imageHash);
      return Right(result);
    } on CacheException catch (e) {
      return Left(CacheFailure(e.message));
    } catch (e) {
      return Left(CacheFailure('Failed to get cached result: $e'));
    }
  }

  /// 生成图片哈希
  Future<String> _generateImageHash(File imageFile) async {
    final bytes = await imageFile.readAsBytes();
    final digest = sha256.convert(bytes);
    return digest.toString();
  }

  /// 将图片转换为Base64
  Future<String> _imageToBase64(File imageFile) async {
    final bytes = await imageFile.readAsBytes();
    return base64Encode(bytes);
  }
}
