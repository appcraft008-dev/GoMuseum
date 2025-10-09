import 'package:cross_file/cross_file.dart';
import 'package:dartz/dartz.dart';
import 'package:crypto/crypto.dart';
import 'package:gomuseum_app/core/error/exceptions.dart';
import 'package:gomuseum_app/core/error/failures.dart';
import 'package:gomuseum_app/core/network/network_info.dart';
import 'package:gomuseum_app/features/recognition/domain/entities/recognition_result.dart';
import 'package:gomuseum_app/features/recognition/domain/repositories/recognition_repository.dart';
import 'package:gomuseum_app/features/recognition/data/datasources/recognition_local_datasource.dart';
import 'package:gomuseum_app/features/recognition/data/datasources/recognition_remote_datasource.dart';

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
      XFile imageFile) async {
    try {
      // 1. 生成图片哈希
      final imageHash = await _generateImageHash(imageFile);

      // 2. 先查缓存
      try {
        final cachedResult = await localDataSource.getCachedResult(imageHash);
        // 忽略低置信度的缓存结果（可能是之前识别失败的结果）
        if (cachedResult != null && cachedResult.confidence >= 0.3) {
          return Right(cachedResult);
        }
        // 如果缓存结果置信度太低，删除它并重新识别
        if (cachedResult != null && cachedResult.confidence < 0.3) {
          await localDataSource.deleteCacheByHash(imageHash);
        }
      } catch (e) {
        // 缓存失败不影响主流程,继续调用远程API
      }

      // 3. 检查网络连接
      final isConnected = await networkInfo.isConnected;
      if (!isConnected) {
        return const Left(NetworkFailure('No network connection'));
      }

      // 4. 调用远程API（直接传递文件）
      final result = await remoteDataSource.recognizeArtwork(imageFile);

      // 5. 仅当置信度足够高时才存入缓存
      try {
        if (result.confidence >= 0.3) {
          await localDataSource.cacheResult(imageHash, result);
        }
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
  Future<Either<Failure, RecognitionResult>> recognizeArtworkForceFresh(
      XFile imageFile) async {
    try {
      // 1. 生成图片哈希
      final imageHash = await _generateImageHash(imageFile);

      // 2. 先删除旧缓存（如果存在）
      try {
        await _deleteCacheByHash(imageHash);
      } catch (e) {
        // 删除失败不影响主流程
      }

      // 3. 检查网络连接
      final isConnected = await networkInfo.isConnected;
      if (!isConnected) {
        return const Left(NetworkFailure('No network connection'));
      }

      // 4. 直接调用远程API
      final result = await remoteDataSource.recognizeArtwork(imageFile);

      // 5. 仅当置信度足够高时才存入缓存
      try {
        if (result.confidence >= 0.3) {
          await localDataSource.cacheResult(imageHash, result);
        }
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

  @override
  Future<Either<Failure, void>> clearCacheByHash(String imageHash) async {
    try {
      await _deleteCacheByHash(imageHash);
      return const Right(null);
    } on CacheException catch (e) {
      return Left(CacheFailure(e.message));
    } catch (e) {
      return Left(CacheFailure('Failed to clear cache: $e'));
    }
  }

  /// 删除特定哈希的缓存
  Future<void> _deleteCacheByHash(String imageHash) async {
    await localDataSource.deleteCacheByHash(imageHash);
  }

  /// 生成图片哈希
  Future<String> _generateImageHash(XFile imageFile) async {
    final bytes = await imageFile.readAsBytes();
    final digest = sha256.convert(bytes);
    return digest.toString();
  }
}
