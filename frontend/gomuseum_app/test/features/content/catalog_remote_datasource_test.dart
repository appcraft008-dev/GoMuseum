// test/features/content/catalog_remote_datasource_test.dart
import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gomuseum_app/features/content/data/datasources/catalog_remote_datasource.dart';

class _StubAdapter implements HttpClientAdapter {
  _StubAdapter(this.body);
  final String body;
  @override
  void close({bool force = false}) {}
  @override
  Future<ResponseBody> fetch(
          RequestOptions o, Stream<List<int>>? r, Future? f) async =>
      ResponseBody.fromString(body, 200, headers: {
        Headers.contentTypeHeader: [Headers.jsonContentType]
      });
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
}
