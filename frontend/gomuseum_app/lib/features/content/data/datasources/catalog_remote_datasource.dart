// lib/features/content/data/datasources/catalog_remote_datasource.dart
import 'package:dio/dio.dart';
import 'package:gomuseum_app/features/content/data/models/museum_detail_model.dart';
import 'package:gomuseum_app/features/content/data/models/object_content_model.dart';
import 'package:gomuseum_app/features/content/data/models/object_list_model.dart';

/// A2/A3/A5 目录端点数据源。错误不在此层包裹：DioException 透传到 Riverpod FutureProvider（AsyncValue.error），由 UI 呈现错误/重试态。
abstract class CatalogRemoteDataSource {
  Future<MuseumDetail> getMuseumDetail({required String slug, String language});
  Future<ObjectListPage> getObjects({
    required String slug,
    String? category,
    String sort,
    int limit,
    int offset,
  });
  Future<ObjectContent> getObjectContent({
    required String slug,
    required String qid,
    String language,
  });
}

class CatalogRemoteDataSourceImpl implements CatalogRemoteDataSource {
  CatalogRemoteDataSourceImpl({required this.dio});
  final Dio dio;

  @override
  Future<MuseumDetail> getMuseumDetail(
      {required String slug, String language = 'zh'}) async {
    final r = await dio
        .get('/api/v1/museums/$slug', queryParameters: {'language': language});
    return MuseumDetail.fromJson(r.data as Map<String, dynamic>);
  }

  @override
  Future<ObjectListPage> getObjects({
    required String slug,
    String? category,
    String sort = 'popularity',
    int limit = 50,
    int offset = 0,
  }) async {
    final r = await dio.get('/api/v1/museums/$slug/objects', queryParameters: {
      if (category != null && category != 'all') 'category': category,
      'sort': sort,
      'limit': limit,
      'offset': offset,
    });
    return ObjectListPage.fromJson(r.data as Map<String, dynamic>);
  }

  @override
  Future<ObjectContent> getObjectContent({
    required String slug,
    required String qid,
    String language = 'zh',
  }) async {
    final r = await dio.get('/api/v1/museums/$slug/objects/$qid/content',
        queryParameters: {'language': language});
    return ObjectContent.fromJson(r.data as Map<String, dynamic>);
  }
}
