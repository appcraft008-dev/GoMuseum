/// Simplified auth repository with storage
import 'package:dio/dio.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import '../domain/user.dart';

class AuthRepository {
  final Dio _dio;
  final FlutterSecureStorage _storage = const FlutterSecureStorage();

  static const String _accessTokenKey = 'access_token';
  static const String _refreshTokenKey = 'refresh_token';

  AuthRepository(this._dio);

  /// Login with email and password
  Future<User> login(String email, String password) async {
    final response = await _dio.post(
      '/api/v1/auth/login',
      data: {'email': email, 'password': password},
    );

    await _saveTokens(
      response.data['access_token'],
      response.data['refresh_token'],
    );

    return User.fromJson(response.data['user']);
  }

  /// Register new user
  Future<User> register(String email, String password,
      {String? username}) async {
    final response = await _dio.post(
      '/api/v1/auth/register',
      data: {
        'email': email,
        'password': password,
        if (username != null) 'username': username,
      },
    );

    await _saveTokens(
      response.data['access_token'],
      response.data['refresh_token'],
    );

    return User.fromJson(response.data['user']);
  }

  /// Get current user
  Future<User?> getCurrentUser() async {
    final token = await getAccessToken();
    if (token == null) return null;

    try {
      final response = await _dio.get(
        '/api/v1/auth/me',
        options: Options(headers: {'Authorization': 'Bearer $token'}),
      );
      return User.fromJson(response.data);
    } catch (e) {
      return null;
    }
  }

  /// Logout
  Future<void> logout() async {
    await _storage.deleteAll();
  }

  /// 永久删除账号（GDPR / App Store 要求），成功后清除本地凭证
  Future<void> deleteAccount() async {
    final token = await getAccessToken();
    await _dio.delete(
      '/api/v1/auth/me',
      options: Options(headers: {'Authorization': 'Bearer $token'}),
    );
    await _storage.deleteAll();
  }

  /// Get access token
  Future<String?> getAccessToken() async {
    return await _storage.read(key: _accessTokenKey);
  }

  /// Save tokens
  Future<void> _saveTokens(String accessToken, String refreshToken) async {
    await _storage.write(key: _accessTokenKey, value: accessToken);
    await _storage.write(key: _refreshTokenKey, value: refreshToken);
  }

  /// Check if user is logged in
  Future<bool> isLoggedIn() async {
    final token = await getAccessToken();
    return token != null;
  }

  /// Login with Google
  Future<User> loginWithGoogle(String idToken, {String? username}) async {
    final response = await _dio.post(
      '/api/v1/auth/google',
      data: {
        'id_token': idToken,
        if (username != null) 'username': username,
      },
    );

    await _saveTokens(
      response.data['access_token'],
      response.data['refresh_token'],
    );

    return User.fromJson(response.data['user']);
  }

  /// Login with Apple
  Future<User> loginWithApple(String idToken, {String? username}) async {
    final response = await _dio.post(
      '/api/v1/auth/apple',
      data: {
        'id_token': idToken,
        if (username != null) 'username': username,
      },
    );

    await _saveTokens(
      response.data['access_token'],
      response.data['refresh_token'],
    );

    return User.fromJson(response.data['user']);
  }

  /// Login as guest user（device_id 用于同设备复用游客账号，防止重装刷额度）
  Future<User> loginAsGuest({String? deviceId}) async {
    final response = await _dio.post(
      '/api/v1/auth/guest',
      data: {if (deviceId != null) 'device_id': deviceId},
    );

    await _saveTokens(
      response.data['access_token'],
      response.data['refresh_token'],
    );

    return User.fromJson(response.data['user']);
  }
}
