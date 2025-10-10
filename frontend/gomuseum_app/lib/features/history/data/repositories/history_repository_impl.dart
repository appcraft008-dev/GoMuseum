import 'package:dartz/dartz.dart';
import 'package:dio/dio.dart';
import '../../../../core/error/failures.dart';
import '../../domain/entities/history_item.dart';
import '../../domain/repositories/history_repository.dart';
import '../datasources/history_remote_datasource.dart';

/// Implementation of history repository
class HistoryRepositoryImpl implements HistoryRepository {
  final HistoryRemoteDataSource remoteDataSource;

  HistoryRepositoryImpl({required this.remoteDataSource});

  @override
  Future<Either<Failure, List<HistoryItem>>> getRecentHistory({
    int limit = 20,
    int offset = 0,
    int? days,
  }) async {
    try {
      final models = await remoteDataSource.getRecentHistory(
        limit: limit,
        offset: offset,
        days: days,
      );

      final entities = models.map((model) => model.toEntity()).toList();
      return Right(entities);
    } on DioException catch (e) {
      if (e.response?.statusCode == 404) {
        return Left(NotFoundFailure('History not found'));
      }
      return Left(ServerFailure(e.message ?? 'Server error'));
    } catch (e) {
      return Left(UnexpectedFailure(e.toString()));
    }
  }

  @override
  Future<Either<Failure, List<HistoryItem>>> searchHistory({
    required String query,
    int limit = 20,
  }) async {
    try {
      final models = await remoteDataSource.searchHistory(
        query: query,
        limit: limit,
      );

      final entities = models.map((model) => model.toEntity()).toList();
      return Right(entities);
    } on DioException catch (e) {
      return Left(ServerFailure(e.message ?? 'Server error'));
    } catch (e) {
      return Left(UnexpectedFailure(e.toString()));
    }
  }

  @override
  Future<Either<Failure, Map<String, dynamic>>> getHistoryStats({
    int days = 30,
  }) async {
    try {
      final stats = await remoteDataSource.getHistoryStats(days: days);
      return Right(stats);
    } on DioException catch (e) {
      return Left(ServerFailure(e.message ?? 'Server error'));
    } catch (e) {
      return Left(UnexpectedFailure(e.toString()));
    }
  }

  @override
  Future<Either<Failure, void>> deleteHistoryItem(String id) async {
    try {
      await remoteDataSource.deleteHistoryItem(id);
      return const Right(null);
    } on DioException catch (e) {
      if (e.response?.statusCode == 404) {
        return Left(NotFoundFailure('History item not found'));
      }
      return Left(ServerFailure(e.message ?? 'Server error'));
    } catch (e) {
      return Left(UnexpectedFailure(e.toString()));
    }
  }
}
