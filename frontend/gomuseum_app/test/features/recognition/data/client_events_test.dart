// V79 App 侧埋点:没网时攒在本机、下次能发时先补发;失败原因分类。
import 'dart:convert';

import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gomuseum_app/core/error/exceptions.dart';
import 'package:gomuseum_app/features/recognition/data/client_events.dart';
import 'package:shared_preferences/shared_preferences.dart';

class _Adapter implements HttpClientAdapter {
  bool offline = false;
  final sent = <Map<String, dynamic>>[];

  @override
  void close({bool force = false}) {}

  @override
  Future<ResponseBody> fetch(RequestOptions options,
      Stream<List<int>>? requestStream, Future? cancelFuture) async {
    if (offline) {
      throw DioException.connectionError(
          requestOptions: options, reason: 'offline');
    }
    expect(options.path, '/api/v1/recognize/client-event');
    sent.add(jsonDecode(jsonEncode(options.data)) as Map<String, dynamic>);
    return ResponseBody.fromString('', 204);
  }
}

void main() {
  late _Adapter a;
  late Dio dio;
  setUp(() {
    SharedPreferences.setMockInitialValues({});
    a = _Adapter();
    dio = Dio(BaseOptions(baseUrl: 'http://x'))..httpClientAdapter = a;
  });

  test('语音付费墙带作品 qid', () async {
    await reportClientEvent(dio, 'paywall_viewed_from_audio',
        museum: 'louvre', qid: 'Q185255');
    expect(a.sent.single['qid'], 'Q185255');
    expect(a.sent.single['museum'], 'louvre');
  });

  test('在线直接发,带名字/馆/原因/设备', () async {
    await reportClientEvent(dio, 'recognition_failed',
        reason: 'timeout', deviceId: 'd1');
    expect(a.sent.single['name'], 'recognition_failed');
    expect(a.sent.single['reason'], 'timeout');
    expect(a.sent.single['device_id'], 'd1');
    expect(a.sent.single['at'], isA<num>());
  });

  test('没网先攒着,联网后下一次上报前按原时刻补发', () async {
    a.offline = true;
    await reportClientEvent(dio, 'recognition_failed', reason: 'no_network');
    expect(a.sent, isEmpty);
    a.offline = false;
    await reportClientEvent(dio, 'paywall_viewed_from_quota', museum: 'louvre');
    expect(a.sent.map((e) => e['name']),
        ['recognition_failed', 'paywall_viewed_from_quota']);
    expect(a.sent.first['reason'], 'no_network');
    await flushClientEvents(dio); // 已清空,不重发
    expect(a.sent, hasLength(2));
  });

  test('攒的条数有上限(只留最新的)', () async {
    a.offline = true;
    for (var i = 0; i < 30; i++) {
      await reportClientEvent(dio, 'recognition_failed', reason: 'no_network');
    }
    a.offline = false;
    await flushClientEvents(dio);
    expect(a.sent, hasLength(kMaxPendingClientEvents));
  });

  test('失败原因分类', () {
    expect(recognitionFailureReason(const TimeoutException()), 'timeout');
    expect(recognitionFailureReason(const NetworkException()), 'no_network');
    expect(
        recognitionFailureReason(const NetworkException(kGatewayUnavailable)),
        'server');
    expect(recognitionFailureReason(const ServerException('x')), 'server');
    expect(recognitionFailureReason(StateError('x')), 'other');
  });
}
