/// Simplified auth repository with storage
import 'dart:convert';

import 'package:dio/dio.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import '../domain/user.dart';

class AuthRepository {
  final Dio _dio;
  final FlutterSecureStorage _storage = const FlutterSecureStorage();

  static const String _accessTokenKey = 'access_token';
  static const String _refreshTokenKey = 'refresh_token';

  /// 上次成功拿到的用户档案。存它只为一件事:**离线时不把用户当成登出**。
  /// 见 [getCurrentUser]。
  static const String _userKey = 'user_profile';

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

    return _persist(response.data['user'] as Map<String, dynamic>);
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

    return _persist(response.data['user'] as Map<String, dynamic>);
  }

  /// 当前用户。**「连不上服务器」不等于「没登录」。**
  ///
  /// 曾经这里 `catch (e) { return null; }` 吞掉一切异常,于是断网时
  /// `currentUserProvider` 拿到 null、路由判定未登录、把人踢到登录页 ——
  /// 令牌明明好好躺在 secure storage 里,只是没法去服务器确认一下。
  ///
  /// 这在一个**博物馆导览** App 上尤其伤:馆内地下展厅、石墙、境外漫游,
  /// 没信号是常态。用户看到登录页不会理解成"网络不好",会理解成"我被登出了",
  /// 接着担心刚买的通票还在不在,甚至重新登录、重新购买。
  ///
  /// 所以按**服务器怎么说**分流:
  /// - 401/403 —— 服务器明确不认这个令牌(AuthInterceptor 已经试过刷新)→ 真的按未登录处理
  /// - 其余(连不上/超时/DNS/5xx)—— 我们**不知道**令牌还认不认 → 保住上次的身份
  Future<User?> getCurrentUser() async {
    final token = await getAccessToken();
    if (token == null) return null;

    try {
      final response = await _dio.get(
        '/api/v1/auth/me',
        options: Options(headers: {'Authorization': 'Bearer $token'}),
      );
      return _persist(response.data as Map<String, dynamic>);
    } on DioException catch (e) {
      final status = e.response?.statusCode;
      if (status == 401 || status == 403) return null;
      return _cachedUser();
    } catch (_) {
      return null;
    }
  }

  /// 解析并落盘,返回实体。落盘失败不该连累登录本身。
  Future<User> _persist(Map<String, dynamic> json) async {
    final user = User.fromJson(json);
    try {
      await _storage.write(key: _userKey, value: jsonEncode(json));
    } catch (_) {
      // 存不下就算了 —— 只是离线体验退化,不影响这次登录
    }
    return user;
  }

  /// 上次成功拿到的身份。解析不了就当没有:契约变更后留下的脏缓存
  /// 不该把 App 卡在一个解析不出来的身份上。
  Future<User?> _cachedUser() async {
    try {
      final raw = await _storage.read(key: _userKey);
      if (raw == null) return null;
      return User.fromJson(jsonDecode(raw) as Map<String, dynamic>);
    } catch (_) {
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

    return _persist(response.data['user'] as Map<String, dynamic>);
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

    return _persist(response.data['user'] as Map<String, dynamic>);
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

    return _persist(response.data['user'] as Map<String, dynamic>);
  }
}
