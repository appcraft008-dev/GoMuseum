import 'package:dartz/dartz.dart';
import '../../../../core/error/failures.dart';
import '../repositories/history_repository.dart';

/// Use case for deleting a history item
class DeleteHistoryItem {
  final HistoryRepository repository;

  DeleteHistoryItem(this.repository);

  Future<Either<Failure, void>> call(String id) async {
    if (id.trim().isEmpty) {
      return Left(ValidationFailure('History item ID cannot be empty'));
    }

    return await repository.deleteHistoryItem(id);
  }
}
