// 讲解页盖章提示(spec 2026-10-27 必看打卡 §五.6):几秒后自动收起,点了也不跳。
import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gomuseum_app/features/content/data/models/museum_summary_model.dart';
import 'package:gomuseum_app/features/content/presentation/providers/catalog_providers.dart';
import 'package:gomuseum_app/features/must_see/data/must_see_models.dart';
import 'package:gomuseum_app/features/must_see/data/must_see_providers.dart';
import 'package:gomuseum_app/features/must_see/presentation/stamp_toast.dart';
import 'package:gomuseum_app/l10n/app_localizations.dart';

const _loc = MustSeeLocation(wing: 'Denon', level: 1, room: '700');

MustSeeData _d(
        {Set<String> checked = const {'Q6'},
        bool completed = false,
        DateTime? at}) =>
    MustSeeData(
      items: [
        for (var i = 1; i <= 12; i++)
          MustSeeItem(
              qid: 'Q$i',
              title: 'T$i',
              artist: '',
              location: i == 6 ? _loc : null),
      ],
      checked: {for (final q in checked) q: at ?? DateTime.now()},
      roundStartedAt: DateTime(2026, 10, 27),
      completed: completed,
      medals: const [],
    );

class _Host extends ConsumerStatefulWidget {
  const _Host({required this.qid, this.pending, this.live = true});
  final String qid;
  final Future<void>? pending;
  final bool live;

  @override
  ConsumerState<_Host> createState() => _HostState();
}

class _HostState extends ConsumerState<_Host> {
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!widget.live) return;
      unawaited(maybeShowStampToast(context, ref,
          slug: 'louvre', qid: widget.qid, pendingConfirm: widget.pending));
    });
  }

  @override
  Widget build(BuildContext context) =>
      const Scaffold(body: Center(child: Text('GUIDE BODY')));
}

late int requests;

Future<void> _pump(WidgetTester t,
    {String qid = 'Q6',
    MustSeeData? data,
    int count = 12,
    Future<void>? pending,
    bool live = true}) async {
  requests = 0;
  final container = ProviderContainer(overrides: [
    museumsListProvider.overrideWith((_) async => [
          MuseumSummary.fromJson({'slug': 'louvre', 'must_see_count': count}),
        ]),
    mustSeeProvider.overrideWith((ref, slug) async {
      requests++;
      return data ?? _d();
    }),
  ]);
  addTearDown(container.dispose);
  await container.read(museumsListProvider.future);
  await t.pumpWidget(UncontrolledProviderScope(
    container: container,
    child: MaterialApp(
      locale: const Locale('zh'),
      localizationsDelegates: AppLocalizations.localizationsDelegates,
      supportedLocales: AppLocalizations.supportedLocales,
      home: _Host(qid: qid, pending: pending, live: live),
    ),
  ));
  await t.pump();
  await t.pump(const Duration(milliseconds: 50));
}

void main() {
  testWidgets('命中清单里的一件 → 盖章提示带厅号,约 4 秒后消失', (t) async {
    await _pump(t);
    expect(find.text('盖章!必看 1 / 12'), findsOneWidget);
    expect(find.textContaining('700 厅'), findsOneWidget);
    await t.pump(const Duration(seconds: 5));
    expect(find.text('盖章!必看 1 / 12'), findsNothing);
  });

  testWidgets('点提示不跳转(路由栈不变)', (t) async {
    await _pump(t);
    await t.tap(find.text('盖章!必看 1 / 12'), warnIfMissed: false);
    await t.pump();
    expect(find.text('GUIDE BODY'), findsOneWidget);
    await t.pump(const Duration(seconds: 5));
  });

  testWidgets('打满 → 必看完成 12 / 12', (t) async {
    await _pump(t,
        data: _d(
            checked: {for (var i = 1; i <= 12; i++) 'Q$i'}, completed: true));
    expect(find.text('必看完成 12 / 12'), findsOneWidget);
    await t.pump(const Duration(seconds: 5));
  });

  testWidgets('候选确认没提交完之前不请求,完成后才请求', (t) async {
    final c = Completer<void>();
    await _pump(t, pending: c.future);
    expect(requests, 0);
    c.complete();
    await t.pump();
    await t.pump(const Duration(milliseconds: 50));
    expect(requests, 1);
    expect(find.text('盖章!必看 1 / 12'), findsOneWidget);
    await t.pump(const Duration(seconds: 5));
  });

  testWidgets('不是快门现场拍 / 馆没有必看 → 不请求不显示', (t) async {
    await _pump(t, live: false);
    expect(requests, 0);
    await _pump(t, count: 0);
    expect(requests, 0);
    expect(find.textContaining('盖章'), findsNothing);
  });

  testWidgets('这件不在清单或不在本轮打卡里 → 不显示', (t) async {
    await _pump(t, qid: 'Q99');
    expect(find.textContaining('盖章'), findsNothing);
    await _pump(t, qid: 'Q7');
    expect(find.textContaining('盖章'), findsNothing);
  });

  testWidgets('重拍已盖过的件(打卡在 10 分钟前)→ 不再弹', (t) async {
    await _pump(t,
        data: _d(at: DateTime.now().subtract(const Duration(days: 1))));
    expect(find.textContaining('盖章'), findsNothing);
  });

  testWidgets('离开讲解页 → 提示立刻收起,不留在上一页', (t) async {
    requests = 0;
    final container = ProviderContainer(overrides: [
      museumsListProvider.overrideWith((_) async => [
            MuseumSummary.fromJson({'slug': 'louvre', 'must_see_count': 12}),
          ]),
      mustSeeProvider.overrideWith((ref, slug) async => _d()),
    ]);
    addTearDown(container.dispose);
    await container.read(museumsListProvider.future);
    final nav = GlobalKey<NavigatorState>();
    await t.pumpWidget(UncontrolledProviderScope(
      container: container,
      child: MaterialApp(
        navigatorKey: nav,
        locale: const Locale('zh'),
        localizationsDelegates: AppLocalizations.localizationsDelegates,
        supportedLocales: AppLocalizations.supportedLocales,
        home: const Scaffold(body: Text('PREV PAGE')),
      ),
    ));
    nav.currentState!
        .push(MaterialPageRoute(builder: (_) => const _Host(qid: 'Q6')));
    await t.pumpAndSettle(const Duration(milliseconds: 50));
    expect(find.text('盖章!必看 1 / 12'), findsOneWidget);
    nav.currentState!.pop();
    for (var i = 0; i < 6; i++) {
      await t.pump(const Duration(milliseconds: 200)); // 退场动画 + 一次检查
    }
    expect(find.text('PREV PAGE'), findsOneWidget);
    expect(find.text('盖章!必看 1 / 12'), findsNothing);
    await t.pump(const Duration(seconds: 5));
  });
}
