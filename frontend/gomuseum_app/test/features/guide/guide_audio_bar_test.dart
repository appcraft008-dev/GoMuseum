import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gomuseum_app/features/guide/presentation/widgets/guide_audio_bar.dart';
import 'package:gomuseum_app/l10n/app_localizations.dart';
import 'package:gomuseum_app/theme/app_theme.dart';

Widget _wrap(Widget child) => MaterialApp(
      localizationsDelegates: AppLocalizations.localizationsDelegates,
      supportedLocales: AppLocalizations.supportedLocales,
      locale: const Locale('zh'),
      theme: AppTheme.lightTheme(),
      home: Scaffold(body: child),
    );

void main() {
  testWidgets('预留态：无 audioUrl 显示"听讲解"，不显示假时长', (t) async {
    await t.pumpWidget(_wrap(const GuideAudioBar(audioUrl: null)));
    await t.pumpAndSettle();
    expect(find.text('听讲解'), findsOneWidget);
    expect(find.textContaining(':'), findsNothing); // 无 4:08 假数据
  });
}
