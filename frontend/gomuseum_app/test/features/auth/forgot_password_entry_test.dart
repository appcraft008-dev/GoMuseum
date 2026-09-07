/// 登录页的「忘记密码」入口。
///
/// 在这之前，用邮箱密码注册的人忘了密码就永久登不进去 —— 而通票挂在账号上。
/// 后端那半已经落地（`/auth/password-reset/*`），这里钉的是**前端别把它作废**：
///
///   - 入口存在且点得开（没有入口 = 后端白做）
///   - 发信失败（后端 502/503）**绝不能显示成「已发送」**
///   - 提示语不许承诺「已发到你的邮箱」——后端对查无此邮箱也返 204
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

class _FakeRepo extends AuthRepository {
  _FakeRepo({this.fails = false}) : super(Dio());

  final bool fails;
  final List<String> asked = [];
  String? language;

  @override
  Future<User?> getCurrentUser() async => null;

  @override
  Future<void> requestPasswordReset(String email, {String? language}) async {
    asked.add(email);
    this.language = language;
    if (fails) {
      // 后端在没配 SMTP / 投递失败时返 503 / 502。Dio 把它抛成异常。
      throw DioException(
        requestOptions:
            RequestOptions(path: '/api/v1/auth/password-reset/request'),
        response: Response(
          requestOptions: RequestOptions(path: ''),
          statusCode: 503,
        ),
      );
    }
  }
}

Future<AppLocalizations> _pump(WidgetTester tester, _FakeRepo repo) async {
  tester.view.physicalSize = const Size(400, 1200);
  tester.view.devicePixelRatio = 1.0;
  addTearDown(tester.view.reset);

  await tester.pumpWidget(
    ProviderScope(
      overrides: [authRepositoryProvider.overrideWithValue(repo)],
      child: MaterialApp(
        localizationsDelegates: const [
          AppLocalizations.delegate,
          GlobalMaterialLocalizations.delegate,
          GlobalWidgetsLocalizations.delegate,
          GlobalCupertinoLocalizations.delegate,
        ],
        locale: const Locale('zh'),
        supportedLocales: AppLocalizations.supportedLocales,
        home: const LoginPage(),
      ),
    ),
  );
  await tester.pumpAndSettle();
  return AppLocalizations.of(tester.element(find.byType(LoginPage)))!;
}

/// 打开弹窗、填邮箱、点发送。
Future<void> _submit(
    WidgetTester t, AppLocalizations l10n, String email) async {
  await t.tap(find.text(l10n.authForgotPassword));
  await t.pumpAndSettle();
  await t.enterText(find.byType(TextField).last, email);
  await t.tap(find.text(l10n.authResetSend));
  await t.pumpAndSettle();
}

void main() {
  testWidgets('登录页有「忘记密码」入口', (t) async {
    final l10n = await _pump(t, _FakeRepo());
    expect(find.text(l10n.authForgotPassword), findsOneWidget,
        reason: '没有入口的话，后端那套找回流程用户根本够不着');
  });

  testWidgets('⭐ 入口贴在密码框右下角，不在登录按钮下面', (t) async {
    // 位置不是装饰：会点它的人此刻正卡在密码框上，视线和手指都在那儿。
    // 挪到登录按钮下面看着也"有入口"，但要用户先扫一遍全页才找得到 ——
    // 而这条测试是这个判断唯一的护栏（存在性那条测试挪到哪儿都绿）。
    final l10n = await _pump(t, _FakeRepo());

    final password = t.getRect(find.byType(TextFormField).at(1));
    final link = t.getRect(find.text(l10n.authForgotPassword));
    final loginButton = t.getRect(find.text(l10n.authLoginButton));

    expect(link.top, greaterThan(password.bottom), reason: '要在密码框下方');
    expect(link.bottom, lessThan(loginButton.top), reason: '要在登录按钮上方');
    expect(link.right, closeTo(password.right, 1.0), reason: '右边缘与密码框对齐');
  });

  testWidgets('点开后能填邮箱并发出申请', (t) async {
    final repo = _FakeRepo();
    final l10n = await _pump(t, repo);

    await _submit(t, l10n, 'someone@example.com');

    expect(repo.asked, ['someone@example.com']);
    expect(find.text(l10n.authResetSent), findsOneWidget);
  });

  testWidgets('⭐ 后端说没发出去（503/502）时，绝不能显示成「已发送」', (t) async {
    // 后端特意用 502/503 把"信没发出去"报上来（没配 SMTP、投递失败）。
    // 前端若吞成成功，那份用心就作废了 —— 用户会守着一封永远不来的邮件，
    // 而我们这侧日志干净、监控全绿。
    final repo = _FakeRepo(fails: true);
    final l10n = await _pump(t, repo);

    await _submit(t, l10n, 'someone@example.com');

    expect(find.text(l10n.authResetSent), findsNothing,
        reason: '把发信失败显示成已发送 = 让用户白等');
    expect(find.text(l10n.authResetFailed), findsOneWidget);
  });

  testWidgets('邮箱从上面的登录框带过来，不用再打一遍', (t) async {
    final repo = _FakeRepo();
    final l10n = await _pump(t, repo);

    // 先在登录表单的邮箱框里打字（第一个 TextFormField）
    await t.enterText(find.byType(TextFormField).first, ' typed@example.com ');
    await t.tap(find.text(l10n.authForgotPassword));
    await t.pumpAndSettle();

    await t.tap(find.text(l10n.authResetSend));
    await t.pumpAndSettle();

    expect(repo.asked, ['typed@example.com'], reason: '带过来时要顺手去掉空白');
  });

  testWidgets('邮箱为空时不发请求', (t) async {
    final repo = _FakeRepo();
    final l10n = await _pump(t, repo);

    await t.tap(find.text(l10n.authForgotPassword));
    await t.pumpAndSettle();
    await t.tap(find.text(l10n.authResetSend));
    await t.pumpAndSettle();

    expect(repo.asked, isEmpty);
  });

  testWidgets('邮件语言跟着界面语言走', (t) async {
    final repo = _FakeRepo();
    final l10n = await _pump(t, repo);
    await _submit(t, l10n, 'someone@example.com');
    expect(repo.language, 'zh');
  });

  testWidgets('⭐ 成功提示不许承诺「已发到你的邮箱」', (t) async {
    // 后端对**查无此邮箱**也返 204（否则端点就是账号枚举器）。
    // 所以这句话只能是条件式的「如果这个邮箱注册过…」——
    // 说成「已发送到你的邮箱」是替后端撒一个它没做的保证，
    // 而输错邮箱的人会一直等下去，永远不会想到去检查邮箱拼写。
    final l10n = await _pump(t, _FakeRepo());
    expect(l10n.authResetSent, contains('如果'));
  });
}
