// 反馈上报的 payload。坐标错了，人就会去修错的那一行 —— 这组测试钉住坐标。
import 'dart:convert';

import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gomuseum_app/features/feedback/data/feedback_repository.dart';

/// 抓住最后一次请求，让测试能检查实际送出去的 body。
class _CapturingAdapter implements HttpClientAdapter {
  _CapturingAdapter({this.status = 204});

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

Map<String, dynamic> bodyOf(_CapturingAdapter a) => a.captured!.data is String
    ? jsonDecode(a.captured!.data as String) as Map<String, dynamic>
    : Map<String, dynamic>.from(a.captured!.data as Map);

(FeedbackRepository, _CapturingAdapter) build({int status = 204}) {
  final adapter = _CapturingAdapter(status: status);
  final dio = Dio(BaseOptions(
    baseUrl: 'http://x',
    // 204/4xx 都当正常返回，由 repository 自己判断
    validateStatus: (_) => true,
  ));
  dio.httpClientAdapter = adapter;
  return (FeedbackRepository(dio), adapter);
}

void main() {
  test('🔴 zh-hant 原样送出，不被降级成 zh', () async {
    // 本组最重要的一条。10 语是 10 份独立内容(独立生成/翻译/音频)，
    // 把 zh-hant 记成 zh，等于让人去改简体那一行 —— 而报错的是繁体。
    final (repo, adapter) = build();
    await repo.submit(
      scope: 'object',
      kind: 'audio_bad',
      museumSlug: 'petit-palais',
      qid: 'Q3937645',
      language: 'zh-hant',
    );

    expect(bodyOf(adapter)['language'], 'zh-hant');
  });

  test('藏品级坐标齐全送出', () async {
    final (repo, adapter) = build();
    await repo.submit(
      scope: 'object',
      kind: 'content_wrong',
      museumSlug: 'petit-palais',
      qid: 'Q3937645',
      language: 'fr',
      text: '  年代写错了  ',
      deviceId: 'dev-1',
    );

    final b = bodyOf(adapter);
    expect(b['scope'], 'object');
    expect(b['kind'], 'content_wrong');
    expect(b['museum_slug'], 'petit-palais');
    expect(b['qid'], 'Q3937645');
    expect(b['text'], '年代写错了', reason: '前后空白应被 trim');
    expect(b['device_id'], 'dev-1');
    expect(b['app_version'], isNotEmpty);
    expect(b['platform'], anyOf('android', 'ios'));
  });

  test('app 级不带 qid/language/museum_slug', () async {
    // 对照组：只测藏品级的话，一个无条件塞满坐标的实现也全绿。
    final (repo, adapter) = build();
    await repo.submit(scope: 'app', kind: 'app_crash', deviceId: 'dev-2');

    final b = bodyOf(adapter);
    expect(b.containsKey('qid'), isFalse);
    expect(b.containsKey('language'), isFalse);
    expect(b.containsKey('museum_slug'), isFalse);
    expect(b['scope'], 'app');
  });

  test('只有空白的文本不送 text 字段', () async {
    final (repo, adapter) = build();
    await repo.submit(scope: 'app', kind: 'other', text: '   ');
    expect(bodyOf(adapter).containsKey('text'), isFalse);
  });

  test('204 算成功', () async {
    final (repo, _) = build(status: 204);
    expect(await repo.submit(scope: 'app', kind: 'other'), isTrue);
  });

  test('服务端拒收算失败(调用方要据此保留用户填的文本)', () async {
    final (repo, _) = build(status: 422);
    expect(await repo.submit(scope: 'app', kind: 'other'), isFalse);
  });

  test('网络异常不抛，返回 false', () async {
    final dio = Dio(BaseOptions(baseUrl: 'http://127.0.0.1:1'));
    final repo = FeedbackRepository(dio);
    expect(await repo.submit(scope: 'app', kind: 'other'), isFalse);
  });
}
