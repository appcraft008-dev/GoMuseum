/// 额度进度条**画得出来**。
///
/// 2026-09-20 用户截图:权益页「3 / 5 left」下面那根条整根是空的,设置页同一
/// 时刻却有 60% 实色。两页算法一模一样(都是 left/total 左对齐),差别只在
/// 实色块那个 widget ——
///
/// 权益页:`Stack` 的**非定位**子节点拿到的是松约束(0..3),而 `ColoredBox`
/// 自己没有固有尺寸,`RenderProxyBox` 无 child 时取 `constraints.smallest`
/// → **高 0**。颜色对、宽度对、就是没有高度,于是"看不见"。
/// 设置页那根用的是 `Container(height: 3)`,写死了高度所以没事。
///
/// 🔑 这类缺陷截图看得见、`find.byType` 看不见 —— 必须量**尺寸**。
library;

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gomuseum_app/features/payment/presentation/widgets/benefits_sections.dart';
import 'package:gomuseum_app/l10n/app_localizations.dart';
import 'package:gomuseum_app/theme/app_theme.dart';
import 'package:gomuseum_app/theme/gm_palette.dart';

Future<void> _pump(WidgetTester tester, Widget child) async {
  await tester.pumpWidget(MaterialApp(
    theme: AppTheme.lightTheme(),
    localizationsDelegates: AppLocalizations.localizationsDelegates,
    supportedLocales: AppLocalizations.supportedLocales,
    home: Scaffold(body: SizedBox(width: 300, child: child)),
  ));
  await tester.pumpAndSettle();
}

/// 实色(已画出来的那截)。找的是 accent 色的那个 ColoredBox。
final fillFinder = find.byWidgetPredicate(
  (w) => w is ColoredBox && w.color == GmPalette.light.accent,
);

Size _fillSize(WidgetTester tester) {
  expect(fillFinder, findsOneWidget, reason: '实色块必须存在');
  return tester.getSize(fillFinder);
}

void main() {
  testWidgets('权益页额度条的实色块有高度,不是一根看不见的零高条', (tester) async {
    await _pump(tester, const BenQuotaRow(label: '识别', left: 3, total: 5));

    final size = _fillSize(tester);
    expect(size.height, greaterThan(0), reason: '高 0 = 用户看到的是空条');
    expect(size.width, moreOrLessEquals(300 * 3 / 5, epsilon: 0.5),
        reason: '宽度按剩余占比');

    // 靠左对齐:剩余那截从左边起画,用掉的从右边退。
    // (FractionallySizedBox 默认 center,不显式指定就会浮在中间。)
    final track = find.byWidgetPredicate(
      (w) => w is ColoredBox && w.color == GmPalette.light.line,
    );
    expect(tester.getTopLeft(fillFinder).dx, tester.getTopLeft(track).dx);
  });

  testWidgets('额度用光时实色块归零,不残留一截', (tester) async {
    await _pump(tester, const BenQuotaRow(label: '识别', left: 0, total: 5));
    expect(_fillSize(tester).width, 0);
  });

  testWidgets('读不到额度时不画实色块 —— 空条会被读成"用光了"', (tester) async {
    await _pump(tester, const BenQuotaRow(label: '识别'));
    expect(fillFinder, findsNothing);
  });
}
