/// Auth state provider using Riverpod
import 'package:dio/dio.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:gomuseum_app/core/network/auth_interceptor.dart';
import '../data/auth_repository.dart';
import '../domain/user.dart';

String _resolveBaseUrl() {
  const envUrl = String.fromEnvironment('API_BASE_URL', defaultValue: '');
  if (envUrl.isNotEmpty) {
    return envUrl;
  }

  if (kIsWeb) {
    return 'http://localhost:8000';
  }

  switch (defaultTargetPlatform) {
    case TargetPlatform.android:
      return 'http://10.0.2.2:8000';
    default:
      return 'http://localhost:8000';
  }
}

// Dio provider
final Provider<Dio> dioProvider = Provider<Dio>((ref) {
  final options = BaseOptions(
    baseUrl: _resolveBaseUrl(),
    connectTimeout: const Duration(seconds: 10),
    receiveTimeout: const Duration(seconds: 10),
  );
  final dio = Dio(options);
  dio.interceptors.add(AuthInterceptor(
    refreshDio: Dio(options),
    onAuthFailure: () => ref.invalidate(currentUserProvider),
  ));
  return dio;
});

// Auth repository provider
final Provider<AuthRepository> authRepositoryProvider =
    Provider<AuthRepository>((ref) {
  return AuthRepository(ref.watch(dioProvider));
});

// Current user state
final StateNotifierProvider<AuthNotifier, AsyncValue<User?>>
    currentUserProvider =
    StateNotifierProvider<AuthNotifier, AsyncValue<User?>>((ref) {
  return AuthNotifier(ref.watch(authRepositoryProvider));
});

class AuthNotifier extends StateNotifier<AsyncValue<User?>> {
  final AuthRepository _repository;

  AuthNotifier(this._repository) : super(const AsyncValue.loading()) {
    _loadUser();
  }

  Future<void> _loadUser() async {
    try {
      final user = await _repository.getCurrentUser();
      state = AsyncValue.data(user);
    } catch (e) {
      state = AsyncValue.data(null);
    }
  }

  Future<bool> login(String email, String password) async {
    try {
      state = const AsyncValue.loading();
      final user = await _repository.login(email, password);
      state = AsyncValue.data(user);
      return true;
    } catch (e) {
      state = AsyncValue.error(e, StackTrace.current);
      return false;
    }
  }

  Future<bool> register(String email, String password,
      {String? username}) async {
    try {
      state = const AsyncValue.loading();
      final user =
          await _repository.register(email, password, username: username);
      state = AsyncValue.data(user);
      return true;
    } catch (e) {
      state = AsyncValue.error(e, StackTrace.current);
      return false;
    }
  }

  Future<void> logout() async {
    await _repository.logout();
    state = const AsyncValue.data(null);
  }

  /// 永久删除账号；失败返回 false 并保持登录态
  Future<bool> deleteAccount() async {
    try {
      await _repository.deleteAccount();
      state = const AsyncValue.data(null);
      return true;
    } catch (e) {
      return false;
    }
  }

  /// Login with Google
  Future<bool> loginWithGoogle(String idToken, {String? username}) async {
    try {
      state = const AsyncValue.loading();
      final user =
          await _repository.loginWithGoogle(idToken, username: username);
      state = AsyncValue.data(user);
      return true;
    } catch (e) {
      state = AsyncValue.error(e, StackTrace.current);
      return false;
    }
  }

  /// Login with Apple
  Future<bool> loginWithApple(String idToken, {String? username}) async {
    try {
      state = const AsyncValue.loading();
      final user =
          await _repository.loginWithApple(idToken, username: username);
      state = AsyncValue.data(user);
      return true;
    } catch (e) {
      state = AsyncValue.error(e, StackTrace.current);
      return false;
    }
  }

  /// Login as guest user
  Future<bool> loginAsGuest({String? deviceId}) async {
    try {
      state = const AsyncValue.loading();
      final user = await _repository.loginAsGuest(deviceId: deviceId);
      state = AsyncValue.data(user);
      return true;
    } catch (e) {
      state = AsyncValue.error(e, StackTrace.current);
      return false;
    }
  }
}
