import 'dart:convert';

import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gomuseum_app/features/guide/data/content_viewed.dart';

class _Adapter implements HttpClientAdapter {
  _Adapter(this.status);
  final int status;
  RequestOptions? captured;

  @override
  void close({bool force = false}) {}

  @override
  Future<ResponseBody> fetch(RequestOptions options,
      Stream<List<int>>? requestStream, Future? cancelFuture) async {
    captured = options;
    return ResponseBody.fromString('', status);
  }
}

Dio _dio(_Adapter a) =>
    Dio(BaseOptions(baseUrl: 'http://x'))..httpClientAdapter = a;

void main() {
  test('进讲解页报一次 content_viewed,带入口', () async {
    final a = _Adapter(204);
    await reportContentViewed(_dio(a),
        slug: 'orsay', qid: 'Q1', entry: GuideEntry.search);
    expect(a.captured!.method, 'POST');
    expect(a.captured!.path, '/api/v1/museums/orsay/objects/Q1/viewed');
    expect(jsonDecode(jsonEncode(a.captured!.data)), {'from': 'search'});
  });

  test('埋点失败不抛(不能连累讲解页)', () async {
    final a = _Adapter(500);
    await reportContentViewed(_dio(a),
        slug: 'orsay', qid: 'Q1', entry: GuideEntry.link);
  });
}
