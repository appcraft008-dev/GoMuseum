// lib/features/content/data/datasources/catalog_remote_datasource.dart
import 'package:dio/dio.dart';
import 'package:gomuseum_app/features/content/data/models/guide_audio.dart';
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
    String language,
  });
  Future<ObjectContent> getObjectContent({
    required String slug,
    required String qid,
    String language,
  });

  /// 段落 TTS 懒生成：点播放触发。200→就绪，409→生成中(重试)，404→文字未生成，503/其它→失败。
  /// [section] guide/深度模块 section_code/qa/artist_bio；section=qa 时须传 [qaSort]。
  Future<GuideAudioResult> getGuideAudio({
    required String slug,
    required String qid,
    required String language,
    String section,
    int? qaSort,
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
    String language = 'zh',
  }) async {
    final r = await dio.get('/api/v1/museums/$slug/objects', queryParameters: {
      if (category != null && category != 'all') 'category': category,
      'sort': sort,
      'limit': limit,
      'offset': offset,
      'language': language,
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

  @override
  Future<GuideAudioResult> getGuideAudio({
    required String slug,
    required String qid,
    required String language,
    String section = 'guide',
    int? qaSort,
  }) async {
    try {
      final r = await dio.get('/api/v1/museums/$slug/objects/$qid/audio',
          // 同步生成 3-8s：receiveTimeout ≥30s，别把生成中当超时失败。
          options: Options(receiveTimeout: const Duration(seconds: 35)),
          queryParameters: {
            'language': language,
            'section': section,
            if (qaSort != null) 'qa_sort': qaSort,
          });
      final url = (r.data as Map)['audio_url'] as String?;
      if (url != null && url.isNotEmpty) return GuideAudioReady(url);
      return const GuideAudioFailed();
    } on DioException catch (e) {
      // 409 = 撞段级锁正在生成（非错误，调用方等一下重试）；
      // 404 = 该语言文字未生成（非错误）；其余（503 等）= 失败可重试。
      final code = e.response?.statusCode;
      if (code == 409) return const GuideAudioGenerating();
      if (code == 404) return const GuideAudioNotReady();
      return const GuideAudioFailed();
    } catch (_) {
      return const GuideAudioFailed();
    }
  }
}
