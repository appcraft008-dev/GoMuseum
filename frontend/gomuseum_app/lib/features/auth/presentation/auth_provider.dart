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
    // 30s:馆内蜂窝网/弱 WiFi 下 10s 太紧——真机反馈"卢浮宫经常加载失败"。
    // 根因是旧版下载 5MB 馆包超时(已由 artworks=false 修掉),但识别/懒生成
    // 等接口本就可能慢,给足余量;连接超时保持 10s(连不上要快速失败)。
    receiveTimeout: const Duration(seconds: 30),
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

  /// 一次登录尝试。**失败绝不改动 [state]** —— 这是白屏事故的根因所在:
  ///
  /// 曾经失败时写 `state = AsyncValue.error(...)`,而 `AsyncError.value` 在
  /// Riverpod 里是**会 rethrow 的**;路由 provider 里那句 `authState.value`
  /// 于是在 build 期抛出 → release 模式下 ErrorWidget 是一整块灰,而且
  /// provider 卡在 error 态再也回不来 —— 邮箱重复、密码打错这种日常失败,
  /// 用户拿到的是一个必须杀进程的死 App。
  ///
  /// 语义上也本该如此:**没登上 ≠ 登出**。失败信息由返回值 false 交给页面弹
  /// toast,不需要污染全局登录态(尤其游客升级失败时不该把游客也踢掉)。
  Future<bool> _attempt(Future<User> Function() run) async {
    try {
      state = AsyncValue.data(await run());
      return true;
    } catch (_) {
      return false;
    }
  }

  Future<bool> login(String email, String password) =>
      _attempt(() => _repository.login(email, password));

  Future<bool> register(String email, String password, {String? username}) =>
      _attempt(() => _repository.register(email, password, username: username));

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
  Future<bool> loginWithGoogle(String idToken, {String? username}) =>
      _attempt(() => _repository.loginWithGoogle(idToken, username: username));

  /// Login with Apple
  Future<bool> loginWithApple(String idToken, {String? username}) =>
      _attempt(() => _repository.loginWithApple(idToken, username: username));

  /// Login as guest user
  Future<bool> loginAsGuest({String? deviceId}) =>
      _attempt(() => _repository.loginAsGuest(deviceId: deviceId));
}
