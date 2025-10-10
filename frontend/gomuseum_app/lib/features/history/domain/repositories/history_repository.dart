import 'package:dartz/dartz.dart';
import '../../../../core/error/failures.dart';
import '../entities/history_item.dart';

/// History repository interface
abstract class HistoryRepository {
  /// Get recent history items
  Future<Either<Failure, List<HistoryItem>>> getRecentHistory({
    int limit = 20,
    int offset = 0,
    int? days,
  });

  /// Search history by query
  Future<Either<Failure, List<HistoryItem>>> searchHistory({
    required String query,
    int limit = 20,
  });

  /// Get history statistics
  Future<Either<Failure, Map<String, dynamic>>> getHistoryStats({
    int days = 30,
  });

  /// Delete history item
  Future<Either<Failure, void>> deleteHistoryItem(String id);
}
