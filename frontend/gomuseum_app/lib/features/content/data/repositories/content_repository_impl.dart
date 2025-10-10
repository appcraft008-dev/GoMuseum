import 'package:dartz/dartz.dart';
import 'package:gomuseum_app/core/error/exceptions.dart';
import 'package:gomuseum_app/core/error/failures.dart';
import 'package:gomuseum_app/features/content/data/datasources/content_remote_datasource.dart';
import 'package:gomuseum_app/features/content/domain/entities/explanation.dart';
import 'package:gomuseum_app/features/content/domain/repositories/content_repository.dart';

/// Content Repository实现
class ContentRepositoryImpl implements ContentRepository {
  final ContentRemoteDataSource remoteDataSource;

  const ContentRepositoryImpl({
    required this.remoteDataSource,
  });

  @override
  Future<Either<Failure, Explanation>> generateExplanation({
    required String artworkName,
    required String artist,
    required String period,
    required String language,
    String? description,
  }) async {
    try {
      final result = await remoteDataSource.generateExplanation(
        artworkName: artworkName,
        artist: artist,
        period: period,
        language: language,
        description: description,
      );
      return Right(result);
    } on ServerException catch (e) {
      return Left(ServerFailure(e.message));
    } on NetworkException catch (e) {
      return Left(NetworkFailure(e.message));
    } on TimeoutException catch (e) {
      return Left(TimeoutFailure(e.message));
    } catch (e) {
      return Left(ServerFailure('Unexpected error: $e'));
    }
  }

  @override
  Future<Either<Failure, String>> generateTtsAudio({
    required String text,
    required String language,
    String? voice,
    double? speed,
  }) async {
    try {
      final result = await remoteDataSource.generateTtsAudio(
        text: text,
        language: language,
        voice: voice,
        speed: speed,
      );
      return Right(result);
    } on ServerException catch (e) {
      return Left(ServerFailure(e.message));
    } on NetworkException catch (e) {
      return Left(NetworkFailure(e.message));
    } on TimeoutException catch (e) {
      return Left(TimeoutFailure(e.message));
    } catch (e) {
      return Left(ServerFailure('Unexpected error: $e'));
    }
  }
}
