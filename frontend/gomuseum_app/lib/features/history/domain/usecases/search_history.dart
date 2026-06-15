import 'package:dartz/dartz.dart';
import '../../../../core/error/failures.dart';
import '../entities/history_item.dart';
import '../repositories/history_repository.dart';

/// Use case for searching history
class SearchHistory {
  final HistoryRepository repository;

  SearchHistory(this.repository);

  Future<Either<Failure, List<HistoryItem>>> call({
    required String query,
    int limit = 20,
  }) async {
    if (query.trim().length < 2) {
      return Left(
          ValidationFailure('Search query must be at least 2 characters'));
    }

    return await repository.searchHistory(
      query: query,
      limit: limit,
    );
  }
}
