/// Apple 登录按钮只在 Apple 平台出现。
///
/// 安卓上它唯一的结果是弹「仅支持 iOS 和 macOS」——必然失败的按钮不该占位。
/// 用 `debugDefaultTargetPlatformOverride` 假装平台,所以这条在任何开发机上
/// 结论都一样(不会因为在 macOS 上跑测试而变绿)。
library;

import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gomuseum_app/features/auth/presentation/login_page.dart';
import 'package:gomuseum_app/l10n/app_localizations.dart';
import 'package:gomuseum_app/theme/app_theme.dart';

Future<void> _pumpLogin(WidgetTester tester) async {
  await tester.pumpWidget(
    ProviderScope(
      child: MaterialApp(
        theme: AppTheme.lightTheme(),
        localizationsDelegates: AppLocalizations.localizationsDelegates,
        supportedLocales: AppLocalizations.supportedLocales,
        locale: const Locale('en'),
        home: const LoginPage(),
      ),
    ),
  );
  await tester.pump();
}

void main() {
  // 复位必须在测试体内完成:flutter_test 自己的 tearDown 会断言
  // foundation 调试变量已还原,它比 main() 里注册的 tearDown 先跑。
  testWidgets('安卓上不显示 Apple 登录', (tester) async {
    debugDefaultTargetPlatformOverride = TargetPlatform.android;
    await _pumpLogin(tester);

    expect(find.text('Sign in with Apple'), findsNothing);
    // Google 仍在 —— 确认不是整块社交登录区没渲染出来
    expect(find.text('Sign in with Google'), findsOneWidget);
    debugDefaultTargetPlatformOverride = null;
  });

  testWidgets('iOS 上 Apple 与 Google 并存', (tester) async {
    debugDefaultTargetPlatformOverride = TargetPlatform.iOS;
    await _pumpLogin(tester);

    expect(find.text('Sign in with Apple'), findsOneWidget);
    expect(find.text('Sign in with Google'), findsOneWidget);
    debugDefaultTargetPlatformOverride = null;
  });

  // 社交登录必须排在邮箱表单之上:邮箱密码是唯一没有找回路径的入口,
  // 谁在最上面决定了多少用户掉进去。顺序回退不会报错、只会静默失效,
  // 所以这条断的是**相对位置**,不是"按钮存在"。
  testWidgets('社交登录在邮箱表单之上,游客仍在最下', (tester) async {
    debugDefaultTargetPlatformOverride = TargetPlatform.android;
    await _pumpLogin(tester);

    final google = tester.getTopLeft(find.text('Sign in with Google')).dy;
    final email = tester.getTopLeft(find.byType(TextFormField).first).dy;
    final guest = tester.getTopLeft(find.text('Continue as guest')).dy;

    expect(google, lessThan(email));
    expect(guest, greaterThan(email));
    debugDefaultTargetPlatformOverride = null;
  });
}
