import 'package:dartz/dartz.dart';
import '../../../../core/error/failures.dart';
import '../entities/history_item.dart';
import '../repositories/history_repository.dart';

/// Use case for getting recent history
class GetRecentHistory {
  final HistoryRepository repository;

  GetRecentHistory(this.repository);

  Future<Either<Failure, List<HistoryItem>>> call({
    int limit = 20,
    int offset = 0,
    int? days,
  }) async {
    return await repository.getRecentHistory(
      limit: limit,
      offset: offset,
      days: days,
    );
  }
}
