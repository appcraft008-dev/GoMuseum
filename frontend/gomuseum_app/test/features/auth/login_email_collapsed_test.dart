/// 登录页以 Google/Apple 为主:邮箱表单默认收起成一行链接,点开就地展开;
/// 底部有服务条款/隐私政策同意声明,点词复制链接(不引入 url_launcher)。
library;

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gomuseum_app/features/auth/presentation/login_page.dart';
import 'package:gomuseum_app/features/settings/presentation/pages/settings_page.dart'
    show kPrivacyPolicyUrl;
import 'package:gomuseum_app/l10n/app_localizations.dart';

Future<AppLocalizations> _pump(WidgetTester t, {String lang = 'en'}) async {
  t.view.physicalSize = const Size(400, 1200);
  t.view.devicePixelRatio = 1.0;
  addTearDown(t.view.reset);
  await t.pumpWidget(ProviderScope(
    child: MaterialApp(
      localizationsDelegates: AppLocalizations.localizationsDelegates,
      supportedLocales: AppLocalizations.supportedLocales,
      locale: Locale(lang),
      home: const LoginPage(),
    ),
  ));
  await t.pumpAndSettle();
  return AppLocalizations.of(t.element(find.byType(LoginPage)))!;
}

void main() {
  testWidgets('邮箱表单默认收起,点链接后展开', (t) async {
    final l10n = await _pump(t);
    expect(find.byType(TextFormField), findsNothing);
    expect(find.text(l10n.authLoginButton), findsNothing);

    await t.tap(find.text(l10n.authUseEmail));
    await t.pumpAndSettle();

    expect(find.byType(TextFormField), findsNWidgets(2));
    expect(find.text(l10n.authLoginButton), findsOneWidget);
    expect(find.text(l10n.authUseEmail), findsNothing, reason: '展开后链接让位给表单');
  });

  testWidgets('同意声明:点「隐私政策」复制隐私政策链接', (t) async {
    final copied = <String>[];
    t.binding.defaultBinaryMessenger
        .setMockMethodCallHandler(SystemChannels.platform, (call) async {
      if (call.method == 'Clipboard.setData') {
        copied.add((call.arguments as Map)['text'] as String);
      }
      return null;
    });
    addTearDown(() => t.binding.defaultBinaryMessenger
        .setMockMethodCallHandler(SystemChannels.platform, null));

    final l10n = await _pump(t);
    expect(find.textContaining(l10n.authTermsOfService, findRichText: true),
        findsOneWidget);
    await t.tapOnText(find.textRange.ofSubstring(l10n.authConsentPrivacy));
    await t.pump();
    expect(copied, [kPrivacyPolicyUrl]);
  });

  testWidgets('十种语言的同意声明都拼得出两个可点词(模板没丢占位)', (t) async {
    for (final loc in AppLocalizations.supportedLocales) {
      final l = await AppLocalizations.delegate.load(loc);
      final s = l.authConsent('\u0000T\u0000', '\u0000P\u0000');
      expect(s.contains('\u0000T\u0000') && s.contains('\u0000P\u0000'), isTrue,
          reason: '$loc');
    }
  });
}
