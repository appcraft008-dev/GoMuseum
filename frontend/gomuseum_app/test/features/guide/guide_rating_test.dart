// 讲解末尾 👍/👎(V78,10-31 用户定)。钉的是:重复点同一个不重复计数、
// 选择按件×语言记在本机、👎 要拉起反馈面板、👍 只说谢谢。
import 'dart:convert';

import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gomuseum_app/features/auth/presentation/auth_provider.dart';
import 'package:gomuseum_app/features/guide/presentation/widgets/guide_rating.dart';
import 'package:gomuseum_app/features/payment/presentation/providers/benefits_provider.dart';
import 'package:gomuseum_app/l10n/app_localizations.dart';
import 'package:shared_preferences/shared_preferences.dart';

class _Adapter implements HttpClientAdapter {
  final List<RequestOptions> calls = [];

  @override
  void close({bool force = false}) {}

  @override
  Future<ResponseBody> fetch(RequestOptions options,
      Stream<List<int>>? requestStream, Future? cancelFuture) async {
    calls.add(options);
    return ResponseBody.fromString('', 204);
  }
}

final zh = lookupAppLocalizations(const Locale('zh'));

Future<_Adapter> _pump(WidgetTester t, {String language = 'es'}) async {
  final a = _Adapter();
  final dio = Dio(BaseOptions(baseUrl: 'http://x'))..httpClientAdapter = a;
  await t.pumpWidget(ProviderScope(
    overrides: [
      dioProvider.overrideWithValue(dio),
      deviceIdProvider.overrideWith((ref) async => 'd'),
    ],
    child: MaterialApp(
      locale: const Locale('zh'),
      localizationsDelegates: AppLocalizations.localizationsDelegates,
      supportedLocales: AppLocalizations.supportedLocales,
      home: Scaffold(
          body: GuideRating(slug: 'orsay', qid: 'Q1', language: language)),
    ),
  ));
  await t.pumpAndSettle();
  return a;
}

List<String> _rated(_Adapter a) => [
      for (final c in a.calls)
        if (c.path.endsWith('/rated'))
          (jsonDecode(jsonEncode(c.data)) as Map)['value'] as String
    ];

void main() {
  setUp(() => SharedPreferences.setMockInitialValues({}));

  testWidgets('显示问句和两个键,读屏认得出', (t) async {
    await _pump(t);
    expect(find.text(zh.guideRateQuestion), findsOneWidget);
    expect(find.bySemanticsLabel(zh.guideRateUp), findsOneWidget);
    expect(find.bySemanticsLabel(zh.guideRateDown), findsOneWidget);
  });

  testWidgets('👍 → 报 up、说谢谢、不弹面板;再点一次不重复报', (t) async {
    final a = await _pump(t);
    await t.tap(find.bySemanticsLabel(zh.guideRateUp));
    await t.pumpAndSettle();
    expect(_rated(a), ['up']);
    expect(a.calls.single.path, '/api/v1/museums/orsay/objects/Q1/rated');
    expect(find.text(zh.fbThanks), findsOneWidget);
    expect(find.text(zh.fbTitleObject), findsNothing);
    await t.tap(find.bySemanticsLabel(zh.guideRateUp));
    await t.pumpAndSettle();
    expect(_rated(a), ['up']);
  });

  testWidgets('👎 → 报 down 并拉起反馈面板,面板里有新增的两类', (t) async {
    final a = await _pump(t);
    await t.tap(find.bySemanticsLabel(zh.guideRateDown));
    await t.pumpAndSettle();
    expect(_rated(a), ['down']);
    expect(find.text(zh.fbTitleObject), findsOneWidget);
    expect(find.text(zh.fbInfoWrong), findsOneWidget);
    expect(find.text(zh.fbTooShallow), findsOneWidget);
  });

  testWidgets('改主意(👍→👎)再报一条', (t) async {
    final a = await _pump(t);
    await t.tap(find.bySemanticsLabel(zh.guideRateUp));
    await t.pumpAndSettle();
    await t.tap(find.bySemanticsLabel(zh.guideRateDown));
    await t.pumpAndSettle();
    expect(_rated(a), ['up', 'down']);
  });

  testWidgets('本机记住按件×语言的选择:重进后点同一个不再报', (t) async {
    SharedPreferences.setMockInitialValues({'guide_rating:Q1:es': 'up'});
    final a = await _pump(t);
    await t.tap(find.bySemanticsLabel(zh.guideRateUp));
    await t.pumpAndSettle();
    expect(_rated(a), isEmpty);
  });

  testWidgets('换语言是另一份内容,单独记', (t) async {
    SharedPreferences.setMockInitialValues({'guide_rating:Q1:es': 'up'});
    final a = await _pump(t, language: 'fr');
    await t.tap(find.bySemanticsLabel(zh.guideRateUp));
    await t.pumpAndSettle();
    expect(_rated(a), ['up']);
  });
}
