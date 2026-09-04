/// 守住两条 prod 真机实测出来的缺陷(2026-09-04,v15):
///
/// ① **换账号必须重新拉权益**。A 买了通票,退出登录 B(全新账号),权益页照旧
///    显示 A 的「生效中」——后端是干净的(B 库里没有权益行),是前端缓存没失效。
///    后果是丢钱:B 以为自己已有通票,购买入口被藏起来,而音频闸在后端,
///    他也放不出声,两头堵死。
/// ② **后端发的 UTC 必须转本地**再交给 l10n 渲染,否则票面时间比用户的钟
///    慢 2 小时(CEST)。
library;

import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gomuseum_app/features/auth/data/auth_repository.dart';
import 'package:gomuseum_app/features/auth/domain/user.dart';
import 'package:gomuseum_app/features/auth/presentation/auth_provider.dart';
import 'package:gomuseum_app/features/payment/data/entitlements.dart';

User _user(String id) => User(
      id: id,
      email: '$id@example.com',
      isActive: true,
      isVerified: true,
      createdAt: DateTime(2026, 1, 1),
    );

class _Repo extends AuthRepository {
  _Repo(this.current) : super(Dio());

  final User current;

  @override
  Future<User?> getCurrentUser() async => current;

  /// 「登录成另一个账号」——测试里用它切换身份。
  @override
  Future<User> login(String email, String password) async => _user(email);
}

/// 不发真请求,只数调用次数:失败会走 `Entitlements.unknown`,
/// 而我们关心的只是"有没有再去拉一次"。
/// (`Dio` 是带 factory 构造的抽象类,继承不了,所以用组合。)
Dio _countingDio(void Function() onCall) => Dio()
  ..interceptors.add(InterceptorsWrapper(
    onRequest: (options, handler) {
      onCall();
      handler.reject(DioException(requestOptions: options));
    },
  ));

void main() {
  test('换账号后重新拉取权益,不复用上一个账号的缓存', () async {
    var calls = 0;
    final dio = _countingDio(() => calls++);
    final container = ProviderContainer(overrides: [
      dioProvider.overrideWithValue(dio),
      currentUserProvider
          .overrideWith((ref) => AuthNotifier(_Repo(_user('userA')))),
    ]);
    addTearDown(container.dispose);

    // 等构造函数里的 _loadUser 真的落地再读。
    // 不能只 `delayed(Duration.zero)`:第一次 read 才会实例化 notifier、
    // 此时 _loadUser 刚起步,身份还是 null。若在这个空档去读权益,
    // 身份随后从 null 变成 A 会把还在飞的那次请求作废,`.future` 永不完成。
    container.read(currentUserProvider);
    while (container.read(currentUserProvider).valueOrNull == null) {
      await Future<void>.delayed(Duration.zero);
    }

    await container.read(entitlementsProvider.future);
    final afterA = calls;
    expect(afterA, greaterThan(0));

    // 再读一次不该重复请求(缓存本身是对的,我们要保留)
    await container.read(entitlementsProvider.future);
    expect(calls, afterA, reason: '同一账号内应命中缓存');

    // 切到 B
    await container.read(currentUserProvider.notifier).login('userB', 'pw');
    await container.read(entitlementsProvider.future);

    expect(calls, greaterThan(afterA), reason: '换了账号却没重新拉 —— B 会看到 A 的通票');
  });

  test('UTC 时间转成本地,时刻不变', () {
    final ent = Entitlements.fromJson(const {
      'state': 'active',
      'can': {'audio_any': true},
      'expires_at': '2026-09-10T23:07:08.941320+00:00',
    });

    expect(ent.expiresAt, isNotNull);
    expect(ent.expiresAt!.isUtc, isFalse, reason: '没转本地,l10n 会按 UTC 渲染');
    // 只改呈现不改时刻
    expect(
        ent.expiresAt!.toUtc(), DateTime.utc(2026, 9, 10, 23, 7, 8, 941, 320));
  });
}
