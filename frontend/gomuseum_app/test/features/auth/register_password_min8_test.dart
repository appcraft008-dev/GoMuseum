/// 注册密码至少 8 位 —— 与网页重置密码页(后端 `new_password` min_length=8)一致。
///
/// 2026-10-24 前 App 注册只要 6 位,用户用 7 位注册、忘了密码去网页重置时
/// 却被要求 8 位,同一个账号两套规则。
library;

import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gomuseum_app/features/auth/data/auth_repository.dart';
import 'package:gomuseum_app/features/auth/domain/user.dart';
import 'package:gomuseum_app/features/auth/presentation/auth_provider.dart';
import 'package:gomuseum_app/features/auth/presentation/register_page.dart';
import 'package:gomuseum_app/l10n/app_localizations.dart';

class _FakeRepo extends AuthRepository {
  _FakeRepo() : super(Dio());

  final List<String> registered = [];

  @override
  Future<User?> getCurrentUser() async => null;

  @override
  Future<User> register(String email, String password,
      {String? username}) async {
    registered.add(password);
    throw Exception('offline'); // 只看校验放没放行,不走后续导航
  }
}

Future<_FakeRepo> _pump(WidgetTester tester) async {
  final repo = _FakeRepo();
  tester.view.physicalSize = const Size(400, 1200);
  tester.view.devicePixelRatio = 1.0;
  addTearDown(tester.view.reset);
  await tester.pumpWidget(
    ProviderScope(
      overrides: [authRepositoryProvider.overrideWithValue(repo)],
      child: const MaterialApp(
        localizationsDelegates: [
          AppLocalizations.delegate,
          GlobalMaterialLocalizations.delegate,
          GlobalWidgetsLocalizations.delegate,
          GlobalCupertinoLocalizations.delegate,
        ],
        locale: Locale('zh'),
        supportedLocales: AppLocalizations.supportedLocales,
        home: RegisterPage(),
      ),
    ),
  );
  await tester.pumpAndSettle();
  return repo;
}

Future<_FakeRepo> _submit(WidgetTester tester, String password) async {
  final repo = await _pump(tester);
  final fields = find.byType(TextFormField);
  await tester.enterText(fields.at(0), 'a@test.com');
  await tester.enterText(fields.at(2), password);
  await tester.enterText(fields.at(3), password);
  await tester.tap(find.text('注 册'));
  await tester.pump();
  return repo;
}

void main() {
  testWidgets('7 位密码被拦下并提示至少 8 位', (tester) async {
    final repo = await _submit(tester, '1234567');
    expect(find.text('密码至少 8 位'), findsOneWidget);
    expect(repo.registered, isEmpty);
  });

  testWidgets('8 位密码不报长度错误', (tester) async {
    final repo = await _submit(tester, '12345678');
    expect(find.text('密码至少 8 位'), findsNothing);
    expect(repo.registered, ['12345678']);
    await tester.pumpAndSettle(const Duration(seconds: 5)); // 等失败提示条消失
  });

  testWidgets('输入时就提示不足 8 位，不用等点注册', (tester) async {
    await _pump(tester);
    final password = find.byType(TextFormField).at(2);
    await tester.enterText(password, '1234567');
    await tester.pump();
    expect(find.text('密码至少 8 位'), findsOneWidget);

    await tester.enterText(password, '12345678');
    await tester.pump();
    expect(find.text('密码至少 8 位'), findsNothing);
  });
}
