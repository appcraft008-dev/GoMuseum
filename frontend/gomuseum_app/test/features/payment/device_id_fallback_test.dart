// device_id 是游客身份的钥匙(后端 auth_service.guest_login 按它复用账号)。
// 兜底路径一旦退化成常量,所有设备会被认成同一个用户、共享一份免费额度 ——
// 这正是 androidInfo.id(Build.ID) 造成的那个 bug。
import 'package:flutter_test/flutter_test.dart';
import 'package:gomuseum_app/features/payment/presentation/providers/benefits_provider.dart';

Future<String> _resolveWith(Map<String, String> store) {
  return resolveFallbackDeviceId(
    read: () async => store['k'],
    write: (v) async => store['k'] = v,
  );
}

void main() {
  group('resolveFallbackDeviceId', () {
    test('两台设备各自生成不同的 ID(不会串成同一个身份)', () async {
      final a = await _resolveWith({});
      final b = await _resolveWith({});
      expect(a, isNot(equals(b)));
    });

    test('同一设备再次调用返回同一个 ID(游客账号不会每次重建)', () async {
      final store = <String, String>{};
      final first = await _resolveWith(store);
      final second = await _resolveWith(store);
      expect(second, equals(first));
    });

    test('已存的空串当作没存,重新生成', () async {
      final store = {'k': ''};
      final id = await _resolveWith(store);
      expect(id, isNotEmpty);
      expect(store['k'], equals(id));
    });

    test('生成的 ID 足够长,不是可猜的常量', () async {
      final id = await _resolveWith({});
      expect(id.length, greaterThan(16));
    });
  });
}
