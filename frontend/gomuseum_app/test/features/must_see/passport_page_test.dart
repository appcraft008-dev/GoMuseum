// 必看护照页(spec 2026-10-27 必看打卡 §五.6;样稿 docs/superpowers/specs/2026-10-27-must-see-mockups/)
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';
import 'package:gomuseum_app/features/must_see/data/must_see_models.dart';
import 'package:gomuseum_app/features/must_see/data/must_see_providers.dart';
import 'package:gomuseum_app/features/must_see/presentation/passport_page.dart';
import 'package:gomuseum_app/l10n/app_localizations.dart';

MustSeeItem _it(String q, {MustSeeLocation? loc}) =>
    MustSeeItem(qid: q, title: 'T$q', artist: 'A', location: loc);

MustSeeData _data({
  bool withLoc = true,
  Set<String> checked = const {'Q1'},
  bool completed = false,
  List<MustSeeMedal> medals = const [],
}) {
  const denon1 = MustSeeLocation(wing: 'Denon', level: 1, room: '711');
  const sully0 = MustSeeLocation(wing: 'Sully', level: 0, room: '345');
  final items = withLoc
      ? [_it('Q1', loc: denon1), _it('Q2', loc: sully0), _it('Q3')]
      : [_it('Q1'), _it('Q2'), _it('Q3')];
  return MustSeeData(
    items: items,
    checked: {for (final q in checked) q: DateTime(2026, 10, 27, 11)},
    roundStartedAt: checked.isEmpty ? null : DateTime(2026, 10, 27, 11),
    completed: completed,
    medals: medals,
  );
}

late List<String> _pushed;

Widget _wrap(MustSeeData d) {
  _pushed = [];
  final router = GoRouter(routes: [
    GoRoute(
        path: '/',
        builder: (_, __) => const Scaffold(
            body: MustSeePassport(slug: 'louvre', museumName: '卢浮宫'))),
    GoRoute(
        path: '/guide',
        builder: (_, s) {
          _pushed.add('guide');
          return const Scaffold(body: Text('GUIDE'));
        }),
  ]);
  return ProviderScope(
    overrides: [mustSeeProvider.overrideWith((ref, slug) async => d)],
    child: MaterialApp.router(
      locale: const Locale('zh'),
      localizationsDelegates: AppLocalizations.localizationsDelegates,
      supportedLocales: AppLocalizations.supportedLocales,
      routerConfig: router,
    ),
  );
}

Future<void> _pump(WidgetTester t, MustSeeData d) async {
  t.view.physicalSize = const Size(720, 3200);
  t.view.devicePixelRatio = 2;
  addTearDown(t.view.reset);
  await t.pumpWidget(_wrap(d));
  await t.pump();
  await t.pump(const Duration(milliseconds: 50));
}

void main() {
  testWidgets('标题、进度、已盖日期签与未盖序号', (t) async {
    await _pump(t, _data());
    expect(find.text('卢浮宫 · 必看'), findsOneWidget);
    expect(find.textContaining('已盖 1 / 3 枚章'), findsOneWidget);
    expect(find.text('10·27'), findsOneWidget); // Q1 已盖
    expect(find.text('2'), findsOneWidget); // Q2 未盖 → 序号
    expect(find.text('3'), findsOneWidget);
    expect(find.text('本轮已完成 ✓'), findsNothing);
  });

  testWidgets('按 (wing, level) 分组,无位置的归最后「暂无展厅信息」', (t) async {
    await _pump(t, _data());
    final denon = t.getTopLeft(find.text('Denon · 1 层')).dy;
    final sully = t.getTopLeft(find.text('Sully · 0 层')).dy;
    final none = t.getTopLeft(find.text('暂无展厅信息')).dy;
    expect(denon < sully && sully < none, isTrue);
    expect(find.text('711 厅'), findsOneWidget);
  });

  testWidgets('整馆都没有位置 → 不出组名', (t) async {
    await _pump(t, _data(withLoc: false));
    expect(find.text('暂无展厅信息'), findsNothing);
  });

  testWidgets('打满 → 本轮已完成 + 完成大章 + 分享', (t) async {
    await _pump(t, _data(checked: {'Q1', 'Q2', 'Q3'}, completed: true));
    expect(find.text('本轮已完成 ✓'), findsOneWidget);
    expect(find.byKey(const Key('passport-seal')), findsOneWidget);
    expect(find.text('分享这一页'), findsOneWidget);
  });

  testWidgets('没有勋章 → 不显示「我的勋章」', (t) async {
    await _pump(t, _data());
    expect(find.text('我的勋章'), findsNothing);
  });

  testWidgets('有勋章 → 「我的勋章」+ 每枚年月', (t) async {
    await _pump(
        t,
        _data(medals: [
          MustSeeMedal(completedAt: DateTime(2025, 6, 1), count: 12),
          MustSeeMedal(completedAt: DateTime(2024, 8, 3), count: 12),
        ]));
    expect(find.text('我的勋章'), findsOneWidget);
    expect(find.text('2025-06'), findsOneWidget);
    expect(find.text('2024-08'), findsOneWidget);
  });

  testWidgets('点章位进讲解页', (t) async {
    await _pump(t, _data());
    await t.tap(find.text('TQ2'));
    await t.pumpAndSettle();
    expect(_pushed, ['guide']);
  });
}
