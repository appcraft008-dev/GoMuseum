import 'dart:convert';

import 'package:dio/dio.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gomuseum_app/core/network/auth_interceptor.dart';
import 'package:mocktail/mocktail.dart';

/// 造一个 exp=给定秒的假 JWT(只有 payload 段被解析)。
String _jwt(int expEpochSecs) {
  final payload =
      base64Url.encode(utf8.encode(jsonEncode({'exp': expEpochSecs})));
  return 'header.$payload.sig';
}

int _epoch(Duration fromNow) =>
    DateTime.now().toUtc().add(fromNow).millisecondsSinceEpoch ~/ 1000;

class MockDio extends Mock implements Dio {}

class MockStorage extends Mock implements FlutterSecureStorage {}

class MockRequestHandler extends Mock implements RequestInterceptorHandler {}

class MockErrorHandler extends Mock implements ErrorInterceptorHandler {}

void main() {
  late MockDio refreshDio;
  late MockStorage storage;
  late AuthInterceptor interceptor;
  var authFailed = false;

  setUpAll(() {
    registerFallbackValue(RequestOptions(path: '/'));
    registerFallbackValue(
      DioException(requestOptions: RequestOptions(path: '/')),
    );
    registerFallbackValue(
      Response<dynamic>(requestOptions: RequestOptions(path: '/')),
    );
  });

  setUp(() {
    refreshDio = MockDio();
    storage = MockStorage();
    authFailed = false;
    interceptor = AuthInterceptor(
      refreshDio: refreshDio,
      storage: storage,
      onAuthFailure: () => authFailed = true,
    );
  });

  DioException unauthorized(RequestOptions options) => DioException(
        requestOptions: options,
        response: Response(requestOptions: options, statusCode: 401),
      );

  group('onRequest', () {
    test('附加 Bearer token', () async {
      when(() => storage.read(key: 'access_token'))
          .thenAnswer((_) async => 'token-1');
      final options = RequestOptions(path: '/api/v1/history/recent');
      final handler = MockRequestHandler();

      await interceptor.onRequest(options, handler);

      expect(options.headers['Authorization'], 'Bearer token-1');
      verify(() => handler.next(options)).called(1);
    });

    test('无 token 时不附加 Authorization', () async {
      when(() => storage.read(key: 'access_token'))
          .thenAnswer((_) async => null);
      final options = RequestOptions(path: '/api/v1/history/recent');
      final handler = MockRequestHandler();

      await interceptor.onRequest(options, handler);

      expect(options.headers.containsKey('Authorization'), isFalse);
    });

    test('过期令牌先主动刷新再附带(修 multipart 识别串号)', () async {
      when(() => storage.read(key: 'access_token'))
          .thenAnswer((_) async => _jwt(_epoch(const Duration(hours: -1))));
      when(() => storage.read(key: 'refresh_token'))
          .thenAnswer((_) async => 'refresh-1');
      when(() =>
              storage.write(key: any(named: 'key'), value: any(named: 'value')))
          .thenAnswer((_) async {});
      when(() => refreshDio.post<Map<String, dynamic>>(
            '/api/v1/auth/refresh',
            data: {'refresh_token': 'refresh-1'},
          )).thenAnswer((_) async => Response(
            requestOptions: RequestOptions(path: '/api/v1/auth/refresh'),
            statusCode: 200,
            data: {'access_token': 'fresh-access', 'refresh_token': 'fresh-r'},
          ));

      final options = RequestOptions(path: '/api/v1/recognize');
      final handler = MockRequestHandler();
      await interceptor.onRequest(options, handler);

      expect(options.headers['Authorization'], 'Bearer fresh-access');
      verify(() => storage.write(key: 'access_token', value: 'fresh-access'))
          .called(1);
      verify(() => handler.next(options)).called(1);
    });

    test('未过期令牌直接附带,不触发刷新', () async {
      final valid = _jwt(_epoch(const Duration(hours: 1)));
      when(() => storage.read(key: 'access_token'))
          .thenAnswer((_) async => valid);
      final options = RequestOptions(path: '/api/v1/recognize');
      final handler = MockRequestHandler();

      await interceptor.onRequest(options, handler);

      expect(options.headers['Authorization'], 'Bearer $valid');
      verifyNever(() => refreshDio.post<Map<String, dynamic>>(
            any(),
            data: any(named: 'data'),
          ));
    });
  });

  group('onError', () {
    test('非 401 错误直接透传', () async {
      final options = RequestOptions(path: '/api/v1/foo');
      final err = DioException(
        requestOptions: options,
        response: Response(requestOptions: options, statusCode: 500),
      );
      final handler = MockErrorHandler();

      await interceptor.onError(err, handler);

      verify(() => handler.next(err)).called(1);
      verifyNever(() => refreshDio.post<Map<String, dynamic>>(
            any(),
            data: any(named: 'data'),
          ));
    });

    test('401 时刷新 token 并重试原请求', () async {
      when(() => storage.read(key: 'refresh_token'))
          .thenAnswer((_) async => 'refresh-1');
      when(() =>
              storage.write(key: any(named: 'key'), value: any(named: 'value')))
          .thenAnswer((_) async {});

      final refreshOptions = RequestOptions(path: '/api/v1/auth/refresh');
      when(() => refreshDio.post<Map<String, dynamic>>(
            '/api/v1/auth/refresh',
            data: {'refresh_token': 'refresh-1'},
          )).thenAnswer((_) async => Response(
            requestOptions: refreshOptions,
            statusCode: 200,
            data: {
              'access_token': 'new-access',
              'refresh_token': 'new-refresh'
            },
          ));

      final originalOptions = RequestOptions(path: '/api/v1/history/recent');
      final retryResponse = Response<dynamic>(
        requestOptions: originalOptions,
        statusCode: 200,
      );
      when(() => refreshDio.fetch<dynamic>(any()))
          .thenAnswer((_) async => retryResponse);

      final handler = MockErrorHandler();
      await interceptor.onError(unauthorized(originalOptions), handler);

      verify(() => storage.write(key: 'access_token', value: 'new-access'))
          .called(1);
      verify(() => storage.write(key: 'refresh_token', value: 'new-refresh'))
          .called(1);
      expect(originalOptions.headers['Authorization'], 'Bearer new-access');
      verify(() => handler.resolve(retryResponse)).called(1);
      expect(authFailed, isFalse);
    });

    test('刷新失败时清除 token 并触发 onAuthFailure', () async {
      when(() => storage.read(key: 'refresh_token'))
          .thenAnswer((_) async => 'expired');
      when(() => storage.delete(key: any(named: 'key')))
          .thenAnswer((_) async {});
      when(() => refreshDio.post<Map<String, dynamic>>(
            any(),
            data: any(named: 'data'),
          )).thenThrow(DioException(
        requestOptions: RequestOptions(path: '/api/v1/auth/refresh'),
      ));

      final err = unauthorized(RequestOptions(path: '/api/v1/history/recent'));
      final handler = MockErrorHandler();
      await interceptor.onError(err, handler);

      verify(() => storage.delete(key: 'access_token')).called(1);
      verify(() => storage.delete(key: 'refresh_token')).called(1);
      verify(() => handler.next(err)).called(1);
      expect(authFailed, isTrue);
    });

    test('刷新请求自身的 401 不再触发刷新', () async {
      final err = unauthorized(RequestOptions(path: '/api/v1/auth/refresh'));
      final handler = MockErrorHandler();

      await interceptor.onError(err, handler);

      verify(() => handler.next(err)).called(1);
      verifyNever(() => storage.read(key: 'refresh_token'));
    });
  });
}
