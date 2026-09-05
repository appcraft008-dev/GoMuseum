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

Future<AppLocalizations> _pump(WidgetTester tester, User? user) async {
  await tester.pumpWidget(
    ProviderScope(
      overrides: [
        authRepositoryProvider.overrideWithValue(_FakeRepo(user)),
      ],
      child: const MaterialApp(
        localizationsDelegates: [
          AppLocalizations.delegate,
          GlobalMaterialLocalizations.delegate,
          GlobalWidgetsLocalizations.delegate,
          GlobalCupertinoLocalizations.delegate,
        ],
        locale: Locale('zh'),
        supportedLocales: AppLocalizations.supportedLocales,
        home: LoginPage(),
      ),
    ),
  );
  await tester.pumpAndSettle();
  return AppLocalizations.of(tester.element(find.byType(LoginPage)))!;
}

void main() {
  testWidgets('已经是游客 → 不再显示「以游客身份继续」', (tester) async {
    final l10n = await _pump(tester, _user(isGuest: true));

    expect(find.text(l10n.authGuestLogin), findsNothing);
    // 它上面那条「或」分隔线也要一起收走，否则页面底下挂着一条什么都不分隔的线
    expect(find.text(l10n.authOr), findsNothing);
  });

  testWidgets('真·未登录 → 游客入口必须还在（这才是它的用武之地）', (tester) async {
    final l10n = await _pump(tester, null);

    expect(find.text(l10n.authGuestLogin), findsOneWidget);
    expect(find.text(l10n.authOr), findsOneWidget);
  });

  testWidgets('隐藏的只是游客入口，登录手段一个都不能少', (tester) async {
    final l10n = await _pump(tester, _user(isGuest: true));

    // 游客来这里就是为了转正，把路堵死比多一个按钮糟得多
    expect(find.text(l10n.authLoginButton), findsOneWidget);
    expect(find.text(l10n.authGoogleLogin), findsOneWidget);
    expect(find.text(l10n.authNoAccount), findsOneWidget); // 去注册
    expect(find.text(l10n.authOrWithEmail), findsOneWidget); // 邮箱那条分隔线还在
  });
}
