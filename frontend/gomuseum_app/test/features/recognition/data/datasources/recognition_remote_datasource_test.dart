import 'dart:typed_data';

import 'package:cross_file/cross_file.dart';
import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gomuseum_app/features/recognition/data/datasources/recognition_remote_datasource.dart';
import 'package:mocktail/mocktail.dart';

class MockDio extends Mock implements Dio {}

void main() {
  late MockDio dio;
  late RecognitionRemoteDataSourceImpl ds;

  setUpAll(() {
    registerFallbackValue(Options());
  });

  setUp(() {
    dio = MockDio();
    ds = RecognitionRemoteDataSourceImpl(dio: dio);
  });

  Response<dynamic> okResponse() => Response(
        requestOptions: RequestOptions(path: '/api/v1/recognize'),
        statusCode: 200,
        data: {'outcome': 'unrecognized'},
      );

  XFile image() => XFile.fromData(Uint8List.fromList(List<int>.filled(8, 0)),
      name: 'x.jpg', mimeType: 'image/jpeg');

  test('recognize sends device_id in queryParameters when provided', () async {
    when(() => dio.post(any(),
        data: any(named: 'data'),
        queryParameters: any(named: 'queryParameters'),
        options: any(named: 'options'))).thenAnswer((_) async => okResponse());

    await ds.recognize(
        slug: null, image: image(), language: 'en', deviceId: 'dev-123');

    final captured = verify(() => dio.post(any(),
        data: any(named: 'data'),
        queryParameters: captureAny(named: 'queryParameters'),
        options: any(named: 'options'))).captured.single as Map;
    expect(captured['device_id'], 'dev-123');
    expect(captured['language'], 'en');
  });

  test('recognize omits device_id when null (server falls back to Bearer)',
      () async {
    when(() => dio.post(any(),
        data: any(named: 'data'),
        queryParameters: any(named: 'queryParameters'),
        options: any(named: 'options'))).thenAnswer((_) async => okResponse());

    await ds.recognize(slug: null, image: image(), language: 'en');

    final captured = verify(() => dio.post(any(),
        data: any(named: 'data'),
        queryParameters: captureAny(named: 'queryParameters'),
        options: any(named: 'options'))).captured.single as Map;
    expect(captured.containsKey('device_id'), isFalse);
  });

  test('confirm posts phash+qid to /api/v1/recognize/confirm', () async {
    when(() => dio.post(any(),
            data: any(named: 'data'), options: any(named: 'options')))
        .thenAnswer((_) async => Response(
              requestOptions: RequestOptions(path: '/api/v1/recognize/confirm'),
              statusCode: 200,
              data: {'status': 'ok'},
            ));

    await ds.confirm(phash: 'abc123', qid: 'Q1');

    final captured = verify(() => dio.post(
          captureAny(),
          data: captureAny(named: 'data'),
          options: any(named: 'options'),
        )).captured;
    expect(captured[0], '/api/v1/recognize/confirm');
    expect(captured[1], {'phash': 'abc123', 'qid': 'Q1'});
  });

  test('confirm swallows all exceptions (fire-and-forget)', () async {
    when(() => dio.post(any(),
            data: any(named: 'data'), options: any(named: 'options')))
        .thenThrow(DioException(
            requestOptions: RequestOptions(path: '/api/v1/recognize/confirm'),
            type: DioExceptionType.connectionError));

    await expectLater(ds.confirm(phash: 'abc123', qid: 'Q1'), completes);
  });
}
