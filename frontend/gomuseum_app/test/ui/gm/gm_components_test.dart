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

  group('GmSectionHead 的宽度分配', () {
    // 真实字体来自 google_fonts(运行时下载),测试里拿不到,所以下面一律断言
    // **同一字体内的关系**(渲染宽 vs 自身所需宽、右边缘 vs 行右边缘),
    // 不写绝对像素——换了字体这些断言依然成立。
    const rowWidth = 411.0; // 常见手机逻辑宽度

    Widget head(String label, {String? note}) => _wrap(SizedBox(
        width: rowWidth,
        child: GmSectionHead(number: '01', label: label, note: note)));

    /// 同 style 下这段文字**不受限**时需要多宽
    Future<double> needsWidth(WidgetTester t, String s) async {
      await t.pumpWidget(_wrap(Align(
          alignment: Alignment.centerLeft,
          child: Text(s,
              maxLines: 1,
              style: GmText.sans(
                  size: 12, letterSpacing: 3, weight: FontWeight.w600)))));
      return t.getSize(find.text(s)).width;
    }

    testWidgets('放得下的标题不该被截断', (tester) async {
      // 回归点:那条**装饰用**的发丝线曾是 Expanded(tight),与标题的
      // Flexible(loose) flex 都是 1 → 平分剩余宽度,于是标题拿不到自己需要的
      // 那点。真机上「Musées à Paris」显示成「Musées à…」、
      // 「Louvre Museum」显示成「Louvr…」。
      // 换回平分的实现这条必红:标题只能拿到约一半。
      const label = 'Musées à Paris';
      final needs = await needsWidth(tester, label);
      await tester.pumpWidget(head(label, note: '→'));
      expect(tester.getSize(find.text(label)).width, needs);
    });

    testWidgets('备注贴住行右边缘,不随标题长短浮动', (tester) async {
      // 同一个根因的另一面:loose 的 Flexible 少用的宽度**不会**回流给发丝线,
      // 而是堆在行尾 → 标题越短,备注离右边缘越远(探索页截图里可见)。
      const note = '4 museums';
      await tester.pumpWidget(head('Paris', note: note));
      expect(tester.getRect(find.text(note)).right, rowWidth);
    });

    testWidgets('标题真的放不下时省略,而不是把备注挤出屏幕', (tester) async {
      // 修上一条时一度矫枉过正:标题改成非 flex 后自己不再收缩,
      // 长标题 + 长备注直接 RenderFlex overflowed。pump 不抛异常即通过。
      await tester.pumpWidget(head(
          'Aide & Mentions légales et politique de confidentialité',
          note: 'Yesterday · 3 works'));
      expect(tester.takeException(), isNull);
      expect(find.text('Yesterday · 3 works'), findsOneWidget);
    });

    testWidgets('备注仍可点击', (tester) async {
      // 重排这个 Row 时我一度把 note 的 GestureDetector 删掉了,
      // 那是首页「全部查看 →」的入口。
      var tapped = 0;
      await tester.pumpWidget(_wrap(SizedBox(
          width: rowWidth,
          child: GmSectionHead(
              number: '01',
              label: 'Paris',
              note: '全部查看',
              onNoteTap: () => tapped++))));
      await tester.tap(find.text('全部查看'));
      expect(tapped, 1);
    });
  });
}
