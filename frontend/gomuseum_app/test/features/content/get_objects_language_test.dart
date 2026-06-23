// test/features/content/get_objects_language_test.dart
import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gomuseum_app/features/content/data/datasources/catalog_remote_datasource.dart';

/// Captures the last RequestOptions so tests can inspect queryParameters.
class _CapturingAdapter implements HttpClientAdapter {
  RequestOptions? captured;

  @override
  void close({bool force = false}) {}

  @override
  Future<ResponseBody> fetch(RequestOptions options,
      Stream<List<int>>? requestStream, Future? cancelFuture) async {
    captured = options;
    const body = '{"items":[],"total":0,"limit":50,"offset":0}';
    return ResponseBody.fromString(body, 200, headers: {
      Headers.contentTypeHeader: [Headers.jsonContentType],
    });
  }
}

void main() {
  test('getObjects 把 language 参数放进请求 query', () async {
    final adapter = _CapturingAdapter();
    final dio = Dio(BaseOptions(baseUrl: 'http://x'));
    dio.httpClientAdapter = adapter;

    final ds = CatalogRemoteDataSourceImpl(dio: dio);
    await ds.getObjects(slug: 'orsay', language: 'en');

    expect(adapter.captured, isNotNull);
    expect(
      adapter.captured!.queryParameters['language'],
      'en',
      reason: 'language query param should be "en"',
    );
  });
}
