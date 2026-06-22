// test/theme/dark_smoke_test.dart
//
// 暗色主题冒烟测试：验证 LoginPage 在 ThemeMode.dark 下能正常渲染 Scaffold，
// 不崩溃、不抛出异常。LoginPage 在初始 build 中不调用任何网络/异步 provider，
// 适合在裸 ProviderScope 中验证。
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gomuseum_app/features/auth/presentation/login_page.dart';
import 'package:gomuseum_app/theme/app_theme.dart';

void main() {
  testWidgets('LoginPage 在 dark 模式下渲染 Scaffold，不崩溃', (tester) async {
    await tester.pumpWidget(
      ProviderScope(
        child: MaterialApp(
          theme: AppTheme.lightTheme(),
          darkTheme: AppTheme.darkTheme(),
          themeMode: ThemeMode.dark,
          home: const LoginPage(),
        ),
      ),
    );

    // pump 一帧让 build 完成
    await tester.pump();

    // Scaffold 应已渲染
    final scaffold = find.byType(Scaffold);
    expect(scaffold, findsOneWidget);
  });
}
