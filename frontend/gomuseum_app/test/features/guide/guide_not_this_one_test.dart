// 直判后讲解页的「不是这件?」(10-12 测试复盘 P0-4):
// 直判认错了原先无从纠正,直判准确率也测不出。用户定:不退次数,只上报否定并回相机。
import 'package:cross_file/cross_file.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';
import 'package:gomuseum_app/features/content/data/models/museum_summary_model.dart';
import 'package:gomuseum_app/features/content/presentation/providers/catalog_providers.dart';
import 'package:gomuseum_app/features/must_see/data/must_see_models.dart';
import 'package:gomuseum_app/features/must_see/data/must_see_providers.dart';
import 'package:gomuseum_app/features/content/data/models/object_content_model.dart';
import 'package:gomuseum_app/features/content/data/models/object_list_model.dart';
import 'package:gomuseum_app/features/content/presentation/providers/catalog_providers.dart';
import 'package:gomuseum_app/features/guide/presentation/pages/guide_page.dart';
import 'package:gomuseum_app/features/history/data/datasources/history_remote_datasource.dart';
import 'package:gomuseum_app/features/history/data/models/history_item_model.dart';
import 'package:gomuseum_app/features/history/presentation/providers/history_providers.dart';
import 'package:gomuseum_app/features/payment/data/entitlements.dart';
import 'package:gomuseum_app/features/recognition/data/datasources/recognition_remote_datasource.dart';
import 'package:gomuseum_app/features/recognition/data/models/recognize_response.dart';
import 'package:gomuseum_app/features/recognition/presentation/providers/recognition_providers.dart';
import 'package:gomuseum_app/features/settings/presentation/providers/language_provider.dart';
import 'package:gomuseum_app/l10n/app_localizations.dart';
import 'package:gomuseum_app/theme/app_theme.dart';

class _Ds implements RecognitionRemoteDataSource {
  final rejects = <(String, List<String>)>[];

  @override
  Future<void> reject(
      {required String phash, required List<String> qids}) async {
    rejects.add((phash, qids));
  }

  @override
  Future<void> confirm(
      {required String phash, required String qid, String? source}) async {}

  @override
  Future<RecognizeResponse> recognize({
    String? slug,
    required XFile image,
    required String language,
    String mode = 'artwork',
    String? deviceId,
    String? capture,
  }) =>
      throw UnimplementedError();

  @override
  Future<Never> recognizeArtwork(XFile imageFile) async =>
      throw UnimplementedError();
}

class _History implements HistoryRemoteDataSource {
  @override
  Future<List<HistoryItemModel>> getRecentHistory({
    int limit = 20,
    int offset = 0,
    int? days,
    String? language,
  }) async =>
      [];

  @override
  Future<List<HistoryItemModel>> searchHistory({
    required String query,
    int limit = 20,
    String? language,
  }) async =>
      [];

  @override
  Future<Map<String, dynamic>> getHistoryStats({int days = 30}) async => {};

  @override
  Future<void> deleteHistoryItem(String id) async {}
}

ObjectContent _sample() => const ObjectContent(
      qid: 'Q1',
      category: 'painting',
      language: 'zh',
      status: ContentStatus.ready,
      title: '罗纳河上的星夜',
      images: [],
      facts: ObjectFacts(artist: '梵高', date: '1888'),
      tabs: [
        ObjectTab(
            sectionCode: 'overview',
            label: '通用描述',
            body: '主线讲解正文。',
            hasAudio: false),
      ],
      suggestedQuestions: [],
    );

Future<_Ds> _pump(WidgetTester t,
    {String? rejectPhash,
    bool liveShot = false,
    List<Override> extra = const []}) async {
  final ds = _Ds();
  final router = GoRouter(initialLocation: '/guide', routes: [
    GoRoute(
      path: '/guide',
      builder: (_, __) => GuidePage(
          args: GuideArgs(
              slug: 'orsay',
              qid: 'Q1',
              rejectPhash: rejectPhash,
              liveShot: liveShot)),
    ),
    GoRoute(
        path: '/camera',
        builder: (_, __) => const Scaffold(body: Text('CAMERA'))),
  ]);
  await t.pumpWidget(ProviderScope(
    overrides: [
      objectContentProvider((slug: 'orsay', qid: 'Q1'))
          .overrideWith((ref) => _sample()),
      entitlementsProvider.overrideWith((ref) async => Entitlements.unknown),
      museumEntitlementsProvider
          .overrideWith((ref, _) async => Entitlements.unknown),
      recognitionRemoteDataSourceProvider.overrideWithValue(ds),
      historyRemoteDataSourceProvider.overrideWithValue(_History()),
      resolvedLocaleProvider.overrideWithValue(const Locale('zh')),
      ...extra,
    ],
    child: MaterialApp.router(
      routerConfig: router,
      localizationsDelegates: AppLocalizations.localizationsDelegates,
      supportedLocales: AppLocalizations.supportedLocales,
      locale: const Locale('zh'),
      theme: AppTheme.lightTheme(),
    ),
  ));
  await t.pumpAndSettle();
  return ds;
}

void main() {
  final l10n = lookupAppLocalizations(const Locale('zh'));

  testWidgets('不是直判进来(列表/候选点选)→ 没有入口', (t) async {
    await _pump(t);
    expect(find.text(l10n.guideNotThisOne), findsNothing);
  });

  testWidgets('直判进来 → 点「不是这件?」上报否定并回相机', (t) async {
    final ds = await _pump(t, rejectPhash: 'abc');
    await t.tap(find.text(l10n.guideNotThisOne));
    await t.pumpAndSettle();
    expect(ds.rejects.single.$1, 'abc');
    expect(ds.rejects.single.$2, ['Q1']);
    expect(find.text('CAMERA'), findsOneWidget);
    expect(find.text(l10n.guideNotThisOneNoted), findsOneWidget);
  });

  // --- 必看打卡盖章提示的接线(spec 2026-10-27 §五.6) ---
  List<Override> mustSee() => [
        museumsListProvider.overrideWith((_) async => [
              MuseumSummary.fromJson({'slug': 'orsay', 'must_see_count': 2}),
            ]),
        mustSeeProvider.overrideWith((ref, _) async => MustSeeData(
              items: const [
                MustSeeItem(qid: 'Q1', title: 'A', artist: ''),
                MustSeeItem(qid: 'Q2', title: 'B', artist: ''),
              ],
              checked: {'Q1': DateTime.now()},
              roundStartedAt: DateTime(2026, 10, 27),
              completed: false,
              medals: const [],
            )),
      ];

  testWidgets('快门现场拍进来 → 顶部盖章提示', (t) async {
    await _pump(t, liveShot: true, extra: mustSee());
    expect(find.text('盖章!必看 1 / 2'), findsOneWidget);
    await t.pump(const Duration(seconds: 5));
  });

  testWidgets('不是现场拍(列表/相册)进来 → 没有盖章提示', (t) async {
    await _pump(t, extra: mustSee());
    expect(find.textContaining('盖章'), findsNothing);
  });
}
