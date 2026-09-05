/// 认证守卫：谁能去登录页。
///
/// 2026-09-05 真机发现的丢钱洞：游客点「登录后购买」进不去登录页，被守卫
/// 弹回首页 —— 而通票**挂账号**，游客本来就不许直接买，那个按钮的全部意义
/// 就是去转正。结果是**游客永远买不了票**。
/// 更难查的是它的表现：重定向发生在 `push('/login')` 期间，被重定向到 shell
/// 路由 `/` 会渲染成一屏只剩底栏的黑屏，看起来像"页面崩了"而不是"被弹回来了"。
library;

import 'package:flutter_test/flutter_test.dart';
import 'package:gomuseum_app/core/router/app_router.dart';
import 'package:gomuseum_app/features/auth/domain/user.dart';

User _user({required bool isGuest}) => User(
      id: 'u1',
      email: isGuest ? null : 'someone@example.com',
      isActive: true,
      isVerified: !isGuest,
      isGuest: isGuest,
      createdAt: DateTime(2026, 9, 5),
    );

void main() {
  group('主动来换身份的人（?upgrade=1）必须能停在登录页', () {
    test('游客带 upgrade 访问 /login → 放行（转正、进而买票的唯一入口）', () {
      expect(
        authRedirect(
            user: _user(isGuest: true), path: '/login', upgrading: true),
        isNull,
      );
    });

    test('游客带 upgrade 访问 /register → 放行', () {
      expect(
        authRedirect(
            user: _user(isGuest: true), path: '/register', upgrading: true),
        isNull,
      );
    });

    test('正式账号带 upgrade 也放行 —— 收据冲突时要换个账号登录', () {
      expect(
        authRedirect(
            user: _user(isGuest: false), path: '/login', upgrading: true),
        isNull,
      );
    });
  });

  group('🔴 冷启动不能把人卡在登录页（2026-09-05 回归）', () {
    // 时序：AuthNotifier 初始 loading → 守卫第一次跑时 user 还是 null →
    // 弹到 /login；等登录态加载完，守卫重跑。这第二次**必须**把人送回首页。
    // 曾经按「是不是游客」判 → 游客不再被送回去 → 每次开 App 都卡在登录页，
    // 而登录页又刚好藏了游客按钮，等于锁在门外。
    test('游客落在 /login 但没有 upgrade 意图 → 必须送回首页', () {
      expect(authRedirect(user: _user(isGuest: true), path: '/login'), '/');
    });

    test('游客落在 /register 但没有 upgrade 意图 → 必须送回首页', () {
      expect(authRedirect(user: _user(isGuest: true), path: '/register'), '/');
    });

    test('正式账号同理', () {
      expect(authRedirect(user: _user(isGuest: false), path: '/login'), '/');
      expect(authRedirect(user: _user(isGuest: false), path: '/register'), '/');
    });

    test('未登录的人带不带 upgrade 都能停在登录页（否则自己重定向自己）', () {
      expect(authRedirect(user: null, path: '/login'), isNull);
      expect(authRedirect(user: null, path: '/login', upgrading: true), isNull);
    });
  });

  group('未登录仍然要被拦住', () {
    test('未登录访问受保护路由 → 去登录页', () {
      expect(authRedirect(user: null, path: '/benefits'), '/login');
      expect(authRedirect(user: null, path: '/'), '/login');
      expect(authRedirect(user: null, path: '/history'), '/login');
    });

    test('未登录访问登录/注册页 → 放行（否则自己重定向自己）', () {
      expect(authRedirect(user: null, path: '/login'), isNull);
      expect(authRedirect(user: null, path: '/register'), isNull);
    });
  });

  group('受保护路由对已登录者一律放行', () {
    for (final path in [
      '/',
      '/explore',
      '/history',
      '/settings',
      '/benefits'
    ]) {
      test('$path 对正式账号放行', () {
        expect(authRedirect(user: _user(isGuest: false), path: path), isNull);
      });
      test('$path 对游客同样放行（游客能用免费额度）', () {
        expect(authRedirect(user: _user(isGuest: true), path: path), isNull);
      });
    }
  });

  group('is_guest 的解析', () {
    test('老后端不返回该字段 → 当成正式账号，保持旧行为', () {
      final u = User.fromJson({
        'id': 'u1',
        'email': 'a@b.c',
        'is_active': true,
        'is_verified': true,
        'created_at': '2026-09-05T10:00:00',
      });
      expect(u.isGuest, isFalse);
    });

    test('后端返回 true → 认成游客', () {
      final u = User.fromJson({
        'id': 'u1',
        'is_active': true,
        'is_verified': false,
        'is_guest': true,
        'created_at': '2026-09-05T10:00:00',
      });
      expect(u.isGuest, isTrue);
      // 顺带钉住:别退回用 email 是否为空来猜身份 —— 那是拿代理特征认人
      expect(u.email, isNull);
    });
  });
}
