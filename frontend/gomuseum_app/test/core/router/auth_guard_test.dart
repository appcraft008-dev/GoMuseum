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
  group('游客必须能到达登录页', () {
    test('游客访问 /login → 放行（这是他转正、进而买票的唯一入口）', () {
      expect(authRedirect(user: _user(isGuest: true), path: '/login'), isNull);
    });

    test('游客访问 /register → 放行', () {
      expect(
          authRedirect(user: _user(isGuest: true), path: '/register'), isNull);
    });
  });

  group('正式账号不该再被送去登录页', () {
    test('已登录用户访问 /login → 回首页', () {
      expect(authRedirect(user: _user(isGuest: false), path: '/login'), '/');
    });

    test('已登录用户访问 /register → 回首页', () {
      expect(authRedirect(user: _user(isGuest: false), path: '/register'), '/');
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
