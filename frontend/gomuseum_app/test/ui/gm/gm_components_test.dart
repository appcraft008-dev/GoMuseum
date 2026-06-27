import 'package:flutter/material.dart';
import 'package:gomuseum_app/l10n/app_localizations.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gomuseum_app/ui/gm/gm.dart';

Widget _wrap(Widget child) => MaterialApp(
    localizationsDelegates: AppLocalizations.localizationsDelegates,
    supportedLocales: AppLocalizations.supportedLocales,
    locale: const Locale('zh'),
    home: Scaffold(body: child));

void main() {
  group('GmNavScan', () {
    testWidgets('渲染 5 个导航项', (tester) async {
      await tester.pumpWidget(_wrap(
        GmNavScan(currentIndex: 0, onTap: (_) {}),
      ));
      for (final label in ['首页', '探索', '识别', '足迹', '设置']) {
        expect(find.text(label), findsOneWidget);
      }
    });

    testWidgets('点击 tab 与中央识别按钮回调对应索引', (tester) async {
      final taps = <int>[];
      await tester.pumpWidget(_wrap(
        GmNavScan(currentIndex: 0, onTap: taps.add),
      ));
      await tester.tap(find.text('探索'));
      await tester.tap(find.text('识别'));
      await tester.tap(find.text('设置'));
      expect(taps, [1, 2, 4]);
    });
  });

  group('GmTicketButton', () {
    testWidgets('渲染文案并响应点击', (tester) async {
      var tapped = false;
      await tester.pumpWidget(_wrap(
        GmTicketButton(
          label: '拍照识别讲解',
          icon: GmIcons.camera,
          onTap: () => tapped = true,
        ),
      ));
      expect(find.text('拍照识别讲解'), findsOneWidget);
      await tester.tap(find.text('拍照识别讲解'));
      expect(tapped, isTrue);
    });
  });

  group('GmSectionHead', () {
    testWidgets('渲染编号、标题与备注', (tester) async {
      var noteTapped = false;
      await tester.pumpWidget(_wrap(
        GmSectionHead(
          number: '01',
          label: '附近博物馆',
          note: '查看全部 →',
          onNoteTap: () => noteTapped = true,
        ),
      ));
      expect(find.text('01'), findsOneWidget);
      expect(find.text('附近博物馆'), findsOneWidget);
      await tester.tap(find.text('查看全部 →'));
      expect(noteTapped, isTrue);
    });
  });

  group('GmToggle', () {
    testWidgets('点击切换值', (tester) async {
      bool? next;
      await tester.pumpWidget(_wrap(
        GmToggle(value: false, onChanged: (v) => next = v),
      ));
      await tester.tap(find.byType(GmToggle));
      expect(next, isTrue);
    });
  });
}
