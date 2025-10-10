import 'package:dio/dio.dart';
import '../models/history_item_model.dart';

/// Remote datasource for history data
abstract class HistoryRemoteDataSource {
  Future<List<HistoryItemModel>> getRecentHistory({
    int limit = 20,
    int offset = 0,
    int? days,
  });

  Future<List<HistoryItemModel>> searchHistory({
    required String query,
    int limit = 20,
  });

  Future<Map<String, dynamic>> getHistoryStats({int days = 30});

  Future<void> deleteHistoryItem(String id);
}

/// Implementation of history remote datasource
class HistoryRemoteDataSourceImpl implements HistoryRemoteDataSource {
  final Dio dio;
  final String baseUrl;

  HistoryRemoteDataSourceImpl({
    required this.dio,
    this.baseUrl = 'http://localhost:8000/api/v1',
  });

  @override
  Future<List<HistoryItemModel>> getRecentHistory({
    int limit = 20,
    int offset = 0,
    int? days,
  }) async {
    final queryParams = {
      'limit': limit,
      'offset': offset,
      if (days != null) 'days': days,
    };

    final response = await dio.get(
      '$baseUrl/history/recent',
      queryParameters: queryParams,
    );

    if (response.statusCode == 200) {
      final List<dynamic> data = response.data as List<dynamic>;
      return data.map((json) => HistoryItemModel.fromJson(json)).toList();
    } else {
      throw DioException(
        requestOptions: response.requestOptions,
        response: response,
        message: 'Failed to fetch history',
      );
    }
  }

  @override
  Future<List<HistoryItemModel>> searchHistory({
    required String query,
    int limit = 20,
  }) async {
    final response = await dio.get(
      '$baseUrl/history/search',
      queryParameters: {
        'query': query,
        'limit': limit,
      },
    );

    if (response.statusCode == 200) {
      final List<dynamic> data = response.data as List<dynamic>;
      return data.map((json) => HistoryItemModel.fromJson(json)).toList();
    } else {
      throw DioException(
        requestOptions: response.requestOptions,
        response: response,
        message: 'Failed to search history',
      );
    }
  }

  @override
  Future<Map<String, dynamic>> getHistoryStats({int days = 30}) async {
    final response = await dio.get(
      '$baseUrl/history/stats',
      queryParameters: {'days': days},
    );

    if (response.statusCode == 200) {
      return response.data as Map<String, dynamic>;
    } else {
      throw DioException(
        requestOptions: response.requestOptions,
        response: response,
        message: 'Failed to fetch history stats',
      );
    }
  }

  @override
  Future<void> deleteHistoryItem(String id) async {
    final response = await dio.delete('$baseUrl/history/$id');

    if (response.statusCode != 200) {
      throw DioException(
        requestOptions: response.requestOptions,
        response: response,
        message: 'Failed to delete history item',
      );
    }
  }
}
