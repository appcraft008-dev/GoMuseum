// test/features/content/catalog_remote_datasource_test.dart
import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gomuseum_app/features/content/data/datasources/catalog_remote_datasource.dart';
import 'package:gomuseum_app/features/content/data/models/guide_audio.dart';

class _StubAdapter implements HttpClientAdapter {
  _StubAdapter(this.body, [this.status = 200]);
  final String body;
  final int status;

  /// 最近一次请求的 URI（校验 query 拼装）。
  Uri? lastUri;

  @override
  void close({bool force = false}) {}
  @override
  Future<ResponseBody> fetch(
      RequestOptions o, Stream<List<int>>? r, Future? f) async {
    lastUri = o.uri;
    return ResponseBody.fromString(body, status, headers: {
      Headers.contentTypeHeader: [Headers.jsonContentType]
    });
  }
}

void main() {
  test('getObjects 命中 A3 路径并解析', () async {
    final dio = Dio(BaseOptions(baseUrl: 'http://x'));
    dio.httpClientAdapter = _StubAdapter(
        '{"items":[{"qid":"Q1","title":"t","content_status":"stub"}],"total":1,"limit":50,"offset":0}');
    final ds = CatalogRemoteDataSourceImpl(dio: dio);
    final page = await ds.getObjects(slug: 'orsay', category: 'all', offset: 0);
    expect(page.items.single.qid, 'Q1');
    expect(page.items.single.isStub, isTrue);
  });

  test('getGuideAudio: 200→Ready / 409→Generating / 404→NotReady / 503→Failed',
      () async {
    Future<GuideAudioResult> call(String body, int status) async {
      final dio = Dio(BaseOptions(baseUrl: 'http://x'));
      // 默认 validateStatus：非 2xx 抛 DioException（同生产 dio），datasource 读 statusCode 分流。
      dio.httpClientAdapter = _StubAdapter(body, status);
      return CatalogRemoteDataSourceImpl(dio: dio)
          .getGuideAudio(slug: 'orsay', qid: 'Q1', language: 'zh');
    }

    expect(await call('{"audio_url":"http://r2/a.mp3"}', 200),
        isA<GuideAudioReady>());
    expect(await call('{"reason":"audio_generating"}', 409),
        isA<GuideAudioGenerating>());
    expect(await call('{"reason":"no_published_text"}', 404),
        isA<GuideAudioNotReady>());
    expect(await call('{"reason":"tts_failed"}', 503), isA<GuideAudioFailed>());
  });

  test('getGuideAudio: section=qa 带 qa_sort 进 query', () async {
    final dio = Dio(BaseOptions(baseUrl: 'http://x'));
    final adapter = _StubAdapter('{"audio_url":"http://r2/a.mp3"}');
    dio.httpClientAdapter = adapter;
    await CatalogRemoteDataSourceImpl(dio: dio).getGuideAudio(
        slug: 'orsay', qid: 'Q1', language: 'zh', section: 'qa', qaSort: 3);
    expect(adapter.lastUri!.queryParameters['section'], 'qa');
    expect(adapter.lastUri!.queryParameters['qa_sort'], '3');
  });
}
