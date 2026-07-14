/// 认证拦截器：自动附加 Bearer token，401 时用 refresh token 换新并重试。
///
/// 基于 QueuedInterceptorsWrapper —— 并发 401 会排队，避免重复刷新。
library;

import 'dart:convert';

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
      var token = await _storage.read(key: _accessTokenKey);
      // 令牌已过期 → 主动刷新再附带。关键:识别是 multipart(FormData 单次性),且
      // /recognize 令牌失效时后端不 401 而降级 device_id → onError 的反应式刷新永不触发;
      // 过期令牌会让识别悄悄计费到匿名/别账号(串号)。这里 pre-flight 刷新根除该路径。
      if (token != null &&
          !options.path.contains(_refreshPath) &&
          _isTokenExpired(token)) {
        token = await _refreshAccessToken() ?? token;
      }
      if (token != null) {
        options.headers['Authorization'] = 'Bearer $token';
      }
    }
    handler.next(options);
  }

  /// JWT `exp` 已到(留 30s 余量)?解析失败按未过期处理,交给 onError 反应式刷新兜底。
  bool _isTokenExpired(String token) {
    try {
      final parts = token.split('.');
      if (parts.length != 3) return false;
      final payload = jsonDecode(
          utf8.decode(base64Url.decode(base64Url.normalize(parts[1]))));
      final exp = (payload as Map)['exp'];
      if (exp is! int) return false;
      final expiry =
          DateTime.fromMillisecondsSinceEpoch(exp * 1000, isUtc: true);
      return DateTime.now()
          .toUtc()
          .isAfter(expiry.subtract(const Duration(seconds: 30)));
    } catch (_) {
      return false;
    }
  }

  /// 用 refresh token 换新 access token 并落库;失败返回 null(不抛,调用方回退旧值)。
  Future<String?> _refreshAccessToken() async {
    final refreshToken = await _storage.read(key: _refreshTokenKey);
    if (refreshToken == null) return null;
    try {
      final resp = await _refreshDio.post<Map<String, dynamic>>(
        _refreshPath,
        data: {'refresh_token': refreshToken},
      );
      final data = resp.data ?? const {};
      final newAccess = data['access_token'] as String?;
      if (newAccess == null) return null;
      await _storage.write(key: _accessTokenKey, value: newAccess);
      final newRefresh = data['refresh_token'] as String?;
      if (newRefresh != null) {
        await _storage.write(key: _refreshTokenKey, value: newRefresh);
      }
      return newAccess;
    } catch (_) {
      return null;
    }
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
