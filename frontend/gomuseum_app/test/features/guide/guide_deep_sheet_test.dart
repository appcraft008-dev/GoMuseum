import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gomuseum_app/features/content/data/models/object_content_model.dart';
import 'package:gomuseum_app/features/guide/presentation/widgets/guide_deep_sheet.dart';
import 'package:gomuseum_app/l10n/app_localizations.dart';
import 'package:gomuseum_app/theme/app_theme.dart';

void main() {
  testWidgets('抽屉渲染 tab 标签与首个 tab 正文，切换 tab 换正文', (t) async {
    final tabs = [
      const ObjectTab(
          sectionCode: 'artist', label: '作者', body: '作者正文', audioUrl: null),
      const ObjectTab(
          sectionCode: 'analysis', label: '分析', body: '分析正文', audioUrl: null),
    ];
    await t.pumpWidget(MaterialApp(
      localizationsDelegates: AppLocalizations.localizationsDelegates,
      supportedLocales: AppLocalizations.supportedLocales,
      locale: const Locale('zh'),
      theme: AppTheme.lightTheme(),
      home: Scaffold(body: GuideDeepSheetContent(tabs: tabs)),
    ));
    await t.pumpAndSettle();
    expect(find.text('作者'), findsOneWidget);
    expect(find.text('分析'), findsOneWidget);
    expect(find.text('作者正文'), findsOneWidget);
    await t.tap(find.text('分析'));
    await t.pumpAndSettle();
    expect(find.text('分析正文'), findsOneWidget);
  });

  testWidgets('提供 artist → 抽屉首位渲染作者卡，且 tab 仍在', (t) async {
    await t.pumpWidget(MaterialApp(
      localizationsDelegates: AppLocalizations.localizationsDelegates,
      supportedLocales: AppLocalizations.supportedLocales,
      locale: const Locale('zh'),
      theme: AppTheme.lightTheme(),
      home: const Scaffold(
        body: GuideDeepSheetContent(
          tabs: [
            ObjectTab(
                sectionCode: 'analysis',
                label: '分析',
                body: '分析正文',
                audioUrl: null),
          ],
          artist: Artist(name: '马奈', bio: '一段经历'),
        ),
      ),
    ));
    await t.pumpAndSettle();
    expect(find.text('马奈'), findsOneWidget);
    expect(find.text('一段经历'), findsOneWidget);
    expect(find.text('分析'), findsOneWidget);
  });
}
