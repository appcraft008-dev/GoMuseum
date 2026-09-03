/// 守住白屏事故的根因:**登录失败不许把全局登录态写成 error/null**。
///
/// 复现路径(v15 真机):邮箱已被注册 → register 抛 400 → 旧代码 `state =
/// AsyncValue.error(...)` → 路由 provider 那句 `authState.value` 在 build 期
/// rethrow → release 模式整屏灰、provider 卡死回不来。
library;

import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gomuseum_app/features/auth/data/auth_repository.dart';
import 'package:gomuseum_app/features/auth/domain/user.dart';
import 'package:gomuseum_app/features/auth/presentation/auth_provider.dart';

User _user(String id) => User(
      id: id,
      email: '$id@example.com',
      isActive: true,
      isVerified: true,
      createdAt: DateTime(2026, 1, 1),
    );

class _Repo extends AuthRepository {
  _Repo({this.current}) : super(Dio());

  final User? current;

  @override
  Future<User?> getCurrentUser() async => current;

  @override
  Future<User> login(String email, String password) async =>
      throw DioException.badResponse(
        statusCode: 401,
        requestOptions: RequestOptions(path: '/login'),
        response: Response(
            requestOptions: RequestOptions(path: '/login'), statusCode: 401),
      );

  @override
  Future<User> register(String email, String password, {String? username}) =>
      login(email, password);
}

void main() {
  test('注册失败后登录态不是 error —— .value 不会 rethrow', () async {
    final notifier = AuthNotifier(_Repo());
    await Future<void>.delayed(Duration.zero); // 等构造函数里的 _loadUser

    expect(await notifier.register('taken@example.com', 'pw'), isFalse);
    expect(notifier.state, isNot(isA<AsyncError<User?>>()));
    expect(() => notifier.state.value, returnsNormally);
  });

  test('登录失败不把已有会话踢掉 —— 没登上 ≠ 登出', () async {
    final existing = _user('guest');
    final notifier = AuthNotifier(_Repo(current: existing));
    await Future<void>.delayed(Duration.zero);
    expect(notifier.state.value, existing);

    expect(await notifier.login('x@example.com', 'wrong'), isFalse);
    expect(notifier.state.value, existing);
  });
}
