/// 认证拦截器：自动附加 Bearer token，401 时用 refresh token 换新并重试。
///
/// 基于 QueuedInterceptorsWrapper —— 并发 401 会排队，避免重复刷新。
library;

import 'package:dio/dio.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';

class AuthInterceptor extends QueuedInterceptorsWrapper {
  AuthInterceptor({
    required Dio refreshDio,
    FlutterSecureStorage? storage,
    this.onAuthFailure,
  })  : _refreshDio = refreshDio,
        _storage = storage ?? const FlutterSecureStorage();

  /// 专用于刷新与重试的裸 Dio（不挂本拦截器，避免递归）
  final Dio _refreshDio;
  final FlutterSecureStorage _storage;

  /// 刷新失败（refresh token 失效）时回调，用于触发登出跳转
  final void Function()? onAuthFailure;

  static const _accessTokenKey = 'access_token';
  static const _refreshTokenKey = 'refresh_token';
  static const _refreshPath = '/api/v1/auth/refresh';

  @override
  Future<void> onRequest(
    RequestOptions options,
    RequestInterceptorHandler handler,
  ) async {
    if (!options.headers.containsKey('Authorization')) {
      final token = await _storage.read(key: _accessTokenKey);
      if (token != null) {
        options.headers['Authorization'] = 'Bearer $token';
      }
    }
    handler.next(options);
  }

  @override
  Future<void> onError(
    DioException err,
    ErrorInterceptorHandler handler,
  ) async {
    final isUnauthorized = err.response?.statusCode == 401;
    final isRefreshCall = err.requestOptions.path.contains(_refreshPath);
    if (!isUnauthorized || isRefreshCall) {
      return handler.next(err);
    }

    final refreshToken = await _storage.read(key: _refreshTokenKey);
    if (refreshToken == null) {
      onAuthFailure?.call();
      return handler.next(err);
    }

    try {
      final refreshResponse = await _refreshDio.post<Map<String, dynamic>>(
        _refreshPath,
        data: {'refresh_token': refreshToken},
      );
      final data = refreshResponse.data ?? const {};
      final newAccess = data['access_token'] as String?;
      if (newAccess == null) {
        throw DioException(
          requestOptions: refreshResponse.requestOptions,
          message: 'Refresh response missing access_token',
        );
      }
      await _storage.write(key: _accessTokenKey, value: newAccess);
      final newRefresh = data['refresh_token'] as String?;
      if (newRefresh != null) {
        await _storage.write(key: _refreshTokenKey, value: newRefresh);
      }

      final retryOptions = err.requestOptions
        ..headers['Authorization'] = 'Bearer $newAccess';
      final retryResponse = await _refreshDio.fetch<dynamic>(retryOptions);
      return handler.resolve(retryResponse);
    } catch (_) {
      await _storage.delete(key: _accessTokenKey);
      await _storage.delete(key: _refreshTokenKey);
      onAuthFailure?.call();
      return handler.next(err);
    }
  }
}
