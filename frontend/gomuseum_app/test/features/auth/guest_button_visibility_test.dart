/// 登录页的「以游客身份继续」该给谁看。
///
/// 游客到得了登录页只有一种情形：他点了「登录后购买」（通票挂账号，游客不许
/// 直接买）或收据冲突的「换个账号登录」。这时再给他一个「以游客身份继续」，
/// 点了等于原地踏步 —— 还是同一个游客账号、还是买不了票，而他刚刚做的选择
/// 正是要离开这个状态。
library;

import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';
import 'package:gomuseum_app/core/router/app_router.dart';
import 'package:gomuseum_app/features/auth/data/auth_repository.dart';
import 'package:gomuseum_app/features/auth/domain/user.dart';
import 'package:gomuseum_app/features/auth/presentation/auth_provider.dart';
import 'package:gomuseum_app/features/auth/presentation/login_page.dart';
import 'package:gomuseum_app/l10n/app_localizations.dart';

/// 只替掉"当前用户是谁"这一处，页面本身是真的。
class _FakeRepo extends AuthRepository {
  _FakeRepo(this._user) : super(Dio());
  final User? _user;

  @override
  Future<User?> getCurrentUser() async => _user;
}

User _user({required bool isGuest}) => User(
      id: 'u1',
      email: isGuest ? null : 'someone@example.com',
      isActive: true,
      isVerified: !isGuest,
      isGuest: isGuest,
      createdAt: DateTime(2026, 9, 5),
    );

/// 渲染真的登录页。[upgrading] = 这次导航带没带 `?upgrade=1`。
Future<AppLocalizations> _pump(
  WidgetTester tester,
  User? user, {
  required bool upgrading,
}) async {
  await tester.pumpWidget(
    ProviderScope(
      overrides: [
        authRepositoryProvider.overrideWithValue(_FakeRepo(user)),
      ],
      child: MaterialApp(
        localizationsDelegates: const [
          AppLocalizations.delegate,
          GlobalMaterialLocalizations.delegate,
          GlobalWidgetsLocalizations.delegate,
          GlobalCupertinoLocalizations.delegate,
        ],
        locale: const Locale('zh'),
        supportedLocales: AppLocalizations.supportedLocales,
        home: LoginPage(upgrading: upgrading),
      ),
    ),
  );
  await tester.pumpAndSettle();
  return AppLocalizations.of(tester.element(find.byType(LoginPage)))!;
}

void main() {
  testWidgets('主动来转正（?upgrade=1） → 不再显示「以游客身份继续」', (tester) async {
    final l10n = await _pump(tester, _user(isGuest: true), upgrading: true);

    expect(find.text(l10n.authGuestLogin), findsNothing);
    // 它上面那条「或」分隔线也要一起收走，否则页面底下挂着一条什么都不分隔的线
    expect(find.text(l10n.authOr), findsNothing);
  });

  testWidgets('真·未登录 → 游客入口必须还在（这才是它的用武之地）', (tester) async {
    final l10n = await _pump(tester, null, upgrading: false);

    expect(find.text(l10n.authGuestLogin), findsOneWidget);
    expect(find.text(l10n.authOr), findsOneWidget);
  });

  testWidgets('隐藏的只是游客入口，登录手段一个都不能少', (tester) async {
    final l10n = await _pump(tester, _user(isGuest: true), upgrading: true);

    // 游客来这里就是为了转正，把路堵死比多一个按钮糟得多
    expect(find.text(l10n.authLoginButton), findsOneWidget);
    expect(find.text(l10n.authGoogleLogin), findsOneWidget);
    expect(find.text(l10n.authNoAccount), findsOneWidget); // 去注册
    expect(find.text(l10n.authOrWithEmail), findsOneWidget); // 邮箱那条分隔线还在
  });

  testWidgets('没有 upgrade 意图时页面不变形 —— 游客也照常看到游客入口', (tester) async {
    // 冷启动会短暂经过这一页（守卫随后把人送回首页）。那一瞬间页面按
    // 「未登录」的样子渲染就对了，不该因为存着游客会话就少掉一个按钮。
    final l10n = await _pump(tester, _user(isGuest: true), upgrading: false);
    expect(find.text(l10n.authGuestLogin), findsOneWidget);
  });

  testWidgets('走**产品代码里那张路由表**：/login?upgrade=1 → 页面确实收到意图', (tester) async {
    // 前面几条直接 new LoginPage(upgrading: ...)，绕开了「URL → 页面参数」
    // 这道接缝：路由 builder 忘了传，其它全对也照样出问题，而那些测试全绿。
    //
    // ⚠️ 也不能在测试里自己搭一个同样的 GoRoute —— 那测的是测试里写的
    // builder，不是 app_router.dart 里那句（第一版就是这么写的，把
    // 产品代码改成 `upgrading: false` 照样绿）。这里从 `goRouterProvider`
    // **实际构造出来的路由表**里取出 /login 那条，用它的 builder。
    final container = ProviderContainer(overrides: [
      authRepositoryProvider.overrideWithValue(_FakeRepo(_user(isGuest: true))),
    ]);
    addTearDown(container.dispose);

    final loginRoute = container
        .read(goRouterProvider)
        .configuration
        .routes
        .whereType<GoRoute>()
        .firstWhere((r) => r.path == '/login');

    await tester.pumpWidget(UncontrolledProviderScope(
      container: container,
      child: MaterialApp.router(
        routerConfig: GoRouter(
          initialLocation: kLoginToUpgrade,
          // 复用**产品代码里那条 route**（含它的 builder），只换掉外壳路由器，
          // 避开真路由 initialLocation '/' 会把整个首页拉起来。
          routes: [loginRoute],
        ),
        localizationsDelegates: const [
          AppLocalizations.delegate,
          GlobalMaterialLocalizations.delegate,
          GlobalWidgetsLocalizations.delegate,
          GlobalCupertinoLocalizations.delegate,
        ],
        locale: const Locale('zh'),
        supportedLocales: AppLocalizations.supportedLocales,
      ),
    ));
    await tester.pumpAndSettle();

    final l10n = AppLocalizations.of(tester.element(find.byType(LoginPage)))!;
    expect(find.text(l10n.authGuestLogin), findsNothing,
        reason: 'app_router 的 /login builder 没把 upgrade 传给页面');
  });
}
