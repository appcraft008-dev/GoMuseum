import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gomuseum_app/features/content/data/models/object_content_model.dart';
import 'package:gomuseum_app/features/guide/presentation/widgets/guide_artist_card.dart';
import 'package:gomuseum_app/l10n/app_localizations.dart';
import 'package:gomuseum_app/theme/app_theme.dart';

Widget _wrap(Widget c) => MaterialApp(
      localizationsDelegates: AppLocalizations.localizationsDelegates,
      supportedLocales: AppLocalizations.supportedLocales,
      locale: const Locale('zh'),
      theme: AppTheme.lightTheme(),
      home: Scaffold(body: c),
    );

void main() {
  testWidgets('全字段：姓名/生卒·国籍/代表作/经历都显示', (t) async {
    await t.pumpWidget(_wrap(const GuideArtistCard(
        artist: Artist(
      name: '爱德华·马奈',
      birth: '1832',
      death: '1883',
      nationality: 'France',
      notableWorks: ['Olympia', 'The Fifer'],
      bio: '马奈的经历叙事。',
    ))));
    await t.pumpAndSettle();
    expect(find.text('爱德华·马奈'), findsOneWidget);
    expect(find.text('1832 – 1883 · France'), findsOneWidget);
    expect(find.textContaining('Olympia · The Fifer'), findsOneWidget);
    expect(find.text('马奈的经历叙事。'), findsOneWidget);
  });

  testWidgets('仅 name + bio（其余缺）：不显示空 meta/代表作', (t) async {
    await t.pumpWidget(_wrap(
        const GuideArtistCard(artist: Artist(name: '居斯塔夫·库尔贝', bio: '一段经历'))));
    await t.pumpAndSettle();
    expect(find.text('居斯塔夫·库尔贝'), findsOneWidget);
    expect(find.text('一段经历'), findsOneWidget);
    expect(find.textContaining('代表作'), findsNothing);
    expect(find.textContaining('–'), findsNothing); // 无生卒年行
  });
}
