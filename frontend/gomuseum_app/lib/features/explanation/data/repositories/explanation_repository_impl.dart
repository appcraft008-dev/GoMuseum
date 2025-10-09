import 'package:dartz/dartz.dart';
import 'package:gomuseum_app/core/error/exceptions.dart';
import 'package:gomuseum_app/core/error/failures.dart';
import 'package:gomuseum_app/features/explanation/data/datasources/explanation_remote_datasource.dart';
import 'package:gomuseum_app/features/explanation/domain/entities/explanation.dart';
import 'package:gomuseum_app/features/explanation/domain/repositories/explanation_repository.dart';

/// 解释Repository实现
///
/// 实现Domain层的ExplanationRepository接口，负责协调数据源操作。
/// 将DataSource抛出的异常转换为Failure对象，遵循Clean Architecture原则。
class ExplanationRepositoryImpl implements ExplanationRepository {
  final ExplanationRemoteDataSource remoteDataSource;

  const ExplanationRepositoryImpl({
    required this.remoteDataSource,
  });

  @override
  Future<Either<Failure, Explanation>> generateExplanation({
    required String artworkName,
    required String language,
    String detailLevel = 'standard',
    bool includeAudio = false,
    String? recognitionId,
  }) async {
    try {
      final result = await remoteDataSource.generateExplanation(
        artworkName: artworkName,
        language: language,
        detailLevel: detailLevel,
        includeAudio: includeAudio,
        recognitionId: recognitionId,
      );

      return Right(result);
    } on ValidationException catch (e) {
      return Left(ValidationFailure(e.message));
    } on NetworkException catch (e) {
      return Left(NetworkFailure(e.message));
    } on TimeoutException catch (e) {
      return Left(TimeoutFailure(e.message));
    } on NotFoundException catch (e) {
      return Left(NotFoundFailure(e.message));
    } on ServerException catch (e) {
      return Left(ServerFailure(e.message));
    } catch (e) {
      return Left(ServerFailure('Unexpected error: $e'));
    }
  }

  @override
  Future<Either<Failure, Explanation>> getExplanationById(String id) async {
    try {
      final result = await remoteDataSource.getExplanationById(id);

      return Right(result);
    } on NotFoundException catch (e) {
      return Left(NotFoundFailure(e.message));
    } on NetworkException catch (e) {
      return Left(NetworkFailure(e.message));
    } on TimeoutException catch (e) {
      return Left(TimeoutFailure(e.message));
    } on ServerException catch (e) {
      return Left(ServerFailure(e.message));
    } catch (e) {
      return Left(ServerFailure('Unexpected error: $e'));
    }
  }

  @override
  Future<Either<Failure, List<Explanation>>> getExplanationsByArtwork(
    String artworkName,
  ) async {
    try {
      final results = await remoteDataSource.getExplanationsByArtwork(
        artworkName,
      );

      return Right(results);
    } on NetworkException catch (e) {
      return Left(NetworkFailure(e.message));
    } on TimeoutException catch (e) {
      return Left(TimeoutFailure(e.message));
    } on ServerException catch (e) {
      return Left(ServerFailure(e.message));
    } catch (e) {
      return Left(ServerFailure('Unexpected error: $e'));
    }
  }
}
