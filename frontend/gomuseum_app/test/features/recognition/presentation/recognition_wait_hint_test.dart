import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gomuseum_app/features/recognition/presentation/widgets/recognition_wait_hint.dart';
import 'package:gomuseum_app/l10n/app_localizations.dart';

void main() {
  testWidgets('hint escalates at 10s and 20s', (tester) async {
    await tester.pumpWidget(const MaterialApp(
      locale: Locale('zh'),
      localizationsDelegates: AppLocalizations.localizationsDelegates,
      supportedLocales: AppLocalizations.supportedLocales,
      home: Scaffold(body: RecognitionWaitHint(style: TextStyle())),
    ));
    await tester.pump();
    expect(find.text('AI 正在比对馆藏与公开艺术数据库'), findsOneWidget);

    await tester.pump(const Duration(seconds: 10));
    expect(find.text('比平时多花了点时间，还在找'), findsOneWidget);

    await tester.pump(const Duration(seconds: 10));
    expect(find.text('可以先切到其他应用，回来时结果还在'), findsOneWidget);
  });

  testWidgets('timers cancelled on dispose (no pending timer error)',
      (tester) async {
    await tester.pumpWidget(const MaterialApp(
      localizationsDelegates: AppLocalizations.localizationsDelegates,
      supportedLocales: AppLocalizations.supportedLocales,
      home: Scaffold(body: RecognitionWaitHint(style: TextStyle())),
    ));
    await tester.pumpWidget(const SizedBox());
  });
}
