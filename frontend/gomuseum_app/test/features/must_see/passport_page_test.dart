// 必看护照页(spec 2026-10-27 必看打卡 §五.6;样稿 docs/superpowers/specs/2026-10-27-must-see-mockups/)
import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';
import 'package:gomuseum_app/features/auth/data/auth_repository.dart';
import 'package:gomuseum_app/features/auth/domain/user.dart';
import 'package:gomuseum_app/features/auth/presentation/auth_provider.dart';
import 'package:gomuseum_app/features/must_see/data/must_see_models.dart';
import 'package:gomuseum_app/features/must_see/data/must_see_providers.dart';
import 'package:gomuseum_app/features/must_see/presentation/passport_page.dart';
import 'package:gomuseum_app/l10n/app_localizations.dart';
import 'package:share_plus/share_plus.dart';

MustSeeItem _it(String q, {MustSeeLocation? loc, String? thumb}) => MustSeeItem(
    qid: q, title: 'T$q', artist: 'A', location: loc, thumbnail: thumb);

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

class _LoggedOut extends AuthNotifier {
  _LoggedOut(super.repository) {
    state = const AsyncValue.data(null);
  }
}

class _LoggedIn extends AuthNotifier {
  _LoggedIn(super.repository) {
    state = AsyncValue.data(User(
      id: 'u1',
      email: 'a@b.c',
      username: 'a',
      isActive: true,
      isVerified: true,
      createdAt: DateTime.utc(2026, 9, 1),
    ));
  }
}

late List<String> _pushed;

Widget _wrap(MustSeeData d, {bool? loggedIn = true}) {
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
    overrides: [
      mustSeeProvider.overrideWith((ref, slug) async => d),
      if (loggedIn != null)
        currentUserProvider.overrideWith((ref) => loggedIn
            ? _LoggedIn(AuthRepository(Dio()))
            : _LoggedOut(AuthRepository(Dio()))),
    ],
    child: MaterialApp.router(
      locale: const Locale('zh'),
      localizationsDelegates: AppLocalizations.localizationsDelegates,
      supportedLocales: AppLocalizations.supportedLocales,
      routerConfig: router,
    ),
  );
}

Future<void> _pump(WidgetTester t, MustSeeData d,
    {bool? loggedIn = true}) async {
  t.view.physicalSize = const Size(720, 3200);
  t.view.devicePixelRatio = 2;
  addTearDown(t.view.reset);
  await t.pumpWidget(_wrap(d, loggedIn: loggedIn));
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
    final denon = t.getTopLeft(find.text('Denon · 2 楼')).dy;
    final sully = t.getTopLeft(find.text('Sully · 1 楼')).dy;
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

  testWidgets('未登录 → 提示登录后拍照才能盖章(审查 I3)', (t) async {
    await _pump(t, _data(checked: const {}), loggedIn: false);
    expect(find.text('登录后,在馆里拍照就能盖章'), findsOneWidget);
  });

  testWidgets('已登录 → 不出登录提示', (t) async {
    await _pump(t, _data());
    expect(find.text('登录后,在馆里拍照就能盖章'), findsNothing);
  });

  testWidgets('编号按屏幕上从上到下的顺序,不按清单顺序(小皇宫 2,3,4,5,1,6 的 bug)', (t) async {
    const denon1 = MustSeeLocation(wing: 'Denon', level: 1);
    const sully0 = MustSeeLocation(wing: 'Sully', level: 0);
    // 清单顺序:Q1 Denon、Q2 Sully、Q3 无位置、Q4 Denon → 显示分组 Denon[Q1,Q4] Sully[Q2] 无[Q3]
    await _pump(
        t,
        MustSeeData(
          items: [
            _it('Q1', loc: denon1),
            _it('Q2', loc: sully0),
            _it('Q3'),
            _it('Q4', loc: denon1),
          ],
          checked: const {},
          roundStartedAt: null,
          completed: false,
          medals: const [],
        ));
    Offset at(String s) => t.getCenter(find.text(s));
    // 每个编号就在它那件作品的正上方
    for (final (n, q) in [('1', 'Q1'), ('2', 'Q4'), ('3', 'Q2'), ('4', 'Q3')]) {
      expect((at(n).dx - at('T$q').dx).abs() < 2, isTrue, reason: '$n ↔ $q');
      expect(at(n).dy < at('T$q').dy, isTrue);
      expect(at('T$q').dy - at(n).dy < 90, isTrue, reason: '$n ↔ $q 同一格');
    }
  });

  testWidgets('没盖的章位:有图 → 淡灰作品图 + 角标编号;没图 → 只有编号', (t) async {
    await _pump(
        t,
        MustSeeData(
          items: [_it('Q1', thumb: 'https://x/a.jpg'), _it('Q2')],
          checked: const {},
          roundStartedAt: null,
          completed: false,
          medals: const [],
        ));
    expect(find.byKey(const Key('slot-ghost-Q1')), findsOneWidget);
    expect(find.byKey(const Key('slot-ghost-Q2')), findsNothing);
    expect(find.text('1'), findsOneWidget);
    expect(find.text('2'), findsOneWidget);
  });

  testWidgets('分享:发护照卡截图(不含完成大章)+ 文字 + Play 链接 + 网站', (t) async {
    ShareParams? sent;
    passportShareSend = (p) async => sent = p;
    addTearDown(() => passportShareSend = defaultPassportShareSend);
    await _pump(t, _data(checked: {'Q1', 'Q2', 'Q3'}, completed: true));
    await t.runAsync(() async {
      await t.tap(find.text('分享这一页'));
      for (var i = 0; i < 50 && sent == null; i++) {
        await Future<void>.delayed(const Duration(milliseconds: 20));
      }
    });
    expect(sent, isNotNull);
    expect(sent!.files, hasLength(1));
    expect(sent!.files!.single.mimeType, 'image/png');
    expect(
        sent!.text,
        contains(
            'https://play.google.com/store/apps/details?id=com.gomuseum.app'));
    expect(sent!.text, contains('https://gomuseum.app/'));
    // 截的是卡片本身;完成大章是叠在卡片外面的一层,不在截图范围里
    expect(
        find.descendant(
            of: find.byKey(const Key('passport-card')),
            matching: find.byKey(const Key('passport-seal'))),
        findsNothing);
  });
}
