// 反馈面板的交互约束。提交态写错的代价很具体：
// 失败时把面板关掉 = 用户白填一遍；提交中不禁用 = 双击造重复行，
// 而「第三个人报同一件事就浮上来」那个排序机制会被假热度污染。
import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gomuseum_app/features/auth/presentation/auth_provider.dart';
import 'package:gomuseum_app/features/feedback/presentation/widgets/feedback_sheet.dart';
import 'package:gomuseum_app/features/payment/presentation/providers/benefits_provider.dart';
import 'package:gomuseum_app/l10n/app_localizations.dart';
import 'package:gomuseum_app/ui/gm/gm_ticket_button.dart';

/// 可控的假服务端：记录请求次数，按需要成功/失败/挂起。
class _FakeAdapter implements HttpClientAdapter {
  _FakeAdapter({this.status = 204, this.hang = false});

  final int status;
  final bool hang;
  int calls = 0;

  @override
  void close({bool force = false}) {}

  @override
  Future<ResponseBody> fetch(RequestOptions options,
      Stream<List<int>>? requestStream, Future? cancelFuture) async {
    calls++;
    if (hang) await Future<void>.delayed(const Duration(seconds: 10));
    return ResponseBody.fromString('', status);
  }
}

Widget harness(_FakeAdapter adapter, {required FeedbackScope scope}) {
  final dio =
      Dio(BaseOptions(baseUrl: 'http://x', validateStatus: (_) => true));
  dio.httpClientAdapter = adapter;

  return ProviderScope(
    overrides: [
      dioProvider.overrideWithValue(dio),
      // 真机上它读设备信息；测试里给个定值，免得提交卡在采集这一步。
      deviceIdProvider.overrideWith((ref) async => 'test-device'),
    ],
    child: MaterialApp(
      locale: const Locale('zh'),
      localizationsDelegates: AppLocalizations.localizationsDelegates,
      supportedLocales: AppLocalizations.supportedLocales,
      home: Scaffold(
        body: FeedbackSheetContent(
          scope: scope,
          slug: scope == FeedbackScope.object ? 'petit-palais' : null,
          qid: scope == FeedbackScope.object ? 'Q1' : null,
          language: scope == FeedbackScope.object ? 'zh-hant' : null,
        ),
      ),
    ),
  );
}

GmTicketButton submitButton(WidgetTester t) =>
    t.widget<GmTicketButton>(find.byType(GmTicketButton));

void main() {
  testWidgets('没选 chip 时提交按钮不可点', (t) async {
    await t.pumpWidget(harness(_FakeAdapter(), scope: FeedbackScope.object));
    expect(submitButton(t).onTap, isNull);
  });

  testWidgets('选了 chip 后可提交（对照组）', (t) async {
    // 少了这条，一个永远禁用的按钮也能让上面那条全绿。
    await t.pumpWidget(harness(_FakeAdapter(), scope: FeedbackScope.object));
    await t.tap(find.text('内容有误'));
    await t.pump();
    expect(submitButton(t).onTap, isNotNull);
  });

  testWidgets('提交中按钮禁用 —— 双击不会发两次', (t) async {
    final adapter = _FakeAdapter(hang: true);
    await t.pumpWidget(harness(adapter, scope: FeedbackScope.object));
    await t.tap(find.text('读音奇怪'));
    await t.pump();

    await t.tap(find.byType(GmTicketButton));
    await t.pump(); // setState → submitting

    expect(submitButton(t).busy, isTrue);
    expect(submitButton(t).onTap, isNull, reason: '提交中还能点 → 会造重复行');

    // device_id 采集是个 await，请求要再过一个 microtask 才真正发出。
    await t.pump(Duration.zero);
    expect(adapter.calls, 1);

    // 提交中再点两下，不该产生第二个请求（重复行会污染按人数排序）。
    await t.tap(find.byType(GmTicketButton), warnIfMissed: false);
    await t.tap(find.byType(GmTicketButton), warnIfMissed: false);
    await t.pump(Duration.zero);
    expect(adapter.calls, 1, reason: '双击发出了第二个请求');

    await t.pumpAndSettle(const Duration(seconds: 11));
  });

  testWidgets('提交失败：面板不关、已填文本保留', (t) async {
    await t.pumpWidget(
        harness(_FakeAdapter(status: 500), scope: FeedbackScope.object));
    await t.tap(find.text('内容有误'));
    await t.pump();
    await t.enterText(find.byType(TextField), '年代写错了');
    await t.tap(find.byType(GmTicketButton));
    await t.pumpAndSettle();

    expect(find.byType(FeedbackSheetContent), findsOneWidget);
    expect(find.text('年代写错了'), findsOneWidget, reason: '让用户白填一遍最气人');
    expect(find.text('没能发送，请检查网络'), findsOneWidget);
  });

  testWidgets('App 级显示 App 级选项，不显示藏品级选项', (t) async {
    await t.pumpWidget(harness(_FakeAdapter(), scope: FeedbackScope.app));
    expect(find.text('闪退卡顿'), findsOneWidget);
    expect(find.text('内容有误'), findsNothing);
  });

  testWidgets('两个入口先后打开互不干扰', (t) async {
    // 钉住「草稿用局部 State，不用共享 provider」这个决定。
    // 真被后人改成共享 provider 而忘了按场景重置，这条会红。
    await t.pumpWidget(harness(_FakeAdapter(), scope: FeedbackScope.object));
    await t.tap(find.text('内容有误'));
    await t.pump();
    await t.enterText(find.byType(TextField), '写了一半');
    await t.pump();

    // 先卸载：同类型 widget 原地替换会复用 State，那不是"关掉再打开"。
    // 先卸载：同类型 widget 原地替换会复用 State，那不是"关掉再打开"。
    await t.pumpWidget(const SizedBox.shrink());
    await t.pump();
    await t.pumpWidget(harness(_FakeAdapter(), scope: FeedbackScope.app));
    await t.pumpAndSettle();

    expect(find.text('写了一半'), findsNothing, reason: '上一个入口的草稿漏过来了');
    expect(submitButton(t).onTap, isNull, reason: 'kind 也该是干净的');
  });
}
