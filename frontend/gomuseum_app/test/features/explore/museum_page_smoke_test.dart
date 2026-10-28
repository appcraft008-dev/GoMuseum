// test/features/explore/museum_page_smoke_test.dart
//
// Widget smoke test for MuseumPage. Overrides catalogDataSourceProvider with a
// fake datasource that returns canned data — one stub item + one ready item.
// Asserts the grid renders and find.text('待完善') appears for the stub card.

import 'package:flutter/material.dart';
import 'package:gomuseum_app/l10n/app_localizations.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gomuseum_app/features/content/data/datasources/catalog_remote_datasource.dart';
import 'package:gomuseum_app/features/content/data/models/guide_audio.dart';
import 'package:gomuseum_app/features/content/data/models/museum_detail_model.dart';
import 'package:gomuseum_app/features/content/data/models/object_content_model.dart';
import 'package:gomuseum_app/features/content/data/models/object_list_model.dart';
import 'package:gomuseum_app/features/content/presentation/providers/catalog_providers.dart';
import 'package:gomuseum_app/features/content/data/models/museum_summary_model.dart';
import 'package:gomuseum_app/features/explore/presentation/pages/museum_page.dart';
import 'package:gomuseum_app/features/must_see/data/must_see_models.dart';
import 'package:gomuseum_app/features/must_see/data/must_see_providers.dart';
import 'package:shared_preferences/shared_preferences.dart';

// ---------------------------------------------------------------------------
// Fake datasource
// ---------------------------------------------------------------------------
class _FakeCatalogDs implements CatalogRemoteDataSource {
  /// 为 null 时构造馆包 description/opening_hours/official_url 全空，
  /// 触发「介绍生成中」占位分支；否则用真实字段测试正常渲染。
  _FakeCatalogDs({this.withIntro = true});
  final bool withIntro;

  @override
  Future<MuseumDetail> getMuseumDetail(
      {required String slug, String language = 'zh'}) async {
    return MuseumDetail.fromJson({
      'slug': 'orsay',
      'name': '奥赛博物馆',
      'city': '巴黎',
      'country': 'FR',
      if (withIntro) ...{
        'description': '奥赛坐落在一座1900年的火车站里，收藏印象派与后印象派杰作，'
            '是巴黎最受欢迎的博物馆之一，见证了艺术从学院派走向现代的转折。',
        'opening_hours': '周二–周日 9:30–18:00',
        'official_url': 'https://www.musee-orsay.fr',
        'cover_image': 'https://r2/cover_large.jpg',
        'cover_credit': 'Jane Doe · CC BY-SA 4.0',
      },
      'categories': [
        {'code': 'all', 'label': '全部', 'count': 2},
        {'code': 'painting', 'label': '绘画', 'count': 1},
      ],
    });
  }

  @override
  Future<ObjectListPage> getObjects({
    required String slug,
    String? category,
    String sort = 'popularity',
    int limit = 50,
    int offset = 0,
    String language = 'zh',
  }) async {
    return ObjectListPage(
      items: [
        const ObjectListItem(
          qid: 'Q1',
          title: '在阿尔勒的卧室',
          artist: '文森特·梵高',
          year: '1889',
          thumbnail: null,
          status: ContentStatus.stub, // should show 「待完善」
        ),
        const ObjectListItem(
          qid: 'Q2',
          title: '自画像',
          artist: '文森特·梵高',
          year: '1889',
          thumbnail: null,
          status: ContentStatus.ready,
        ),
      ],
      total: 2,
      limit: 50,
      offset: 0,
    );
  }

  @override
  Future<ObjectContent> getObjectContent({
    required String slug,
    required String qid,
    String language = 'zh',
  }) async =>
      throw UnimplementedError();

  @override
  Future<GuideAudioResult> getGuideAudio({
    required String slug,
    required String qid,
    required String language,
    String section = 'guide',
    int? qaSort,
  }) async =>
      const GuideAudioFailed();

  @override
  String audioStreamUrl(
          {required String slug,
          required String qid,
          required String language,
          String section = 'guide'}) =>
      'http://x/stream';
}

// ---------------------------------------------------------------------------
// Test helper
// ---------------------------------------------------------------------------
Widget _wrap({bool withIntro = true}) => ProviderScope(
      overrides: [
        catalogDataSourceProvider
            .overrideWithValue(_FakeCatalogDs(withIntro: withIntro)),
        // 馆页同步读馆列表决定有没有「必看」tab;不 override 会发真请求
        museumsListProvider.overrideWith((_) async => const <MuseumSummary>[]),
      ],
      child: const MaterialApp(
        localizationsDelegates: AppLocalizations.localizationsDelegates,
        supportedLocales: AppLocalizations.supportedLocales,
        locale: const Locale('zh'),
        home: MuseumPage(slug: 'orsay'),
      ),
    );

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------
void main() {
  setUp(() => SharedPreferences.setMockInitialValues({}));

  testWidgets('藏品目录：默认大图网格，点切换 → 列表并记在本机', (tester) async {
    await tester.pumpWidget(_wrap());
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 100));

    expect(find.byType(SliverGrid), findsOneWidget);
    expect(find.text('01'), findsNothing); // 序号只在列表行里
    expect(find.text('待完善'), findsOneWidget); // 网格里 stub 角标照样在

    await tester.tap(find.bySemanticsLabel('列表显示'));
    await tester.pump();
    expect(find.byType(SliverGrid), findsNothing);
    expect(find.text('01'), findsOneWidget);
    final prefs = await SharedPreferences.getInstance();
    expect(prefs.getBool('collection_grid_view'), isFalse);
  });

  testWidgets('藏品目录：本机记过「列表」→ 进馆直接是列表', (tester) async {
    SharedPreferences.setMockInitialValues({'collection_grid_view': false});
    await tester.pumpWidget(_wrap());
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 100));

    expect(find.byType(SliverGrid), findsNothing);
    expect(find.text('01'), findsOneWidget);
    expect(find.bySemanticsLabel('大图显示'), findsOneWidget);
  });

  testWidgets('MuseumPage：默认停在「藏品」tab，切到「封面」才见介绍', (tester) async {
    await tester.pumpWidget(_wrap());
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 100));

    // Museum name should appear in the top bar
    expect(find.text('奥赛博物馆'), findsOneWidget);

    // 顶层 tab 栏：封面 / 藏品(默认选中)
    expect(find.text('封面'), findsOneWidget);
    expect(find.text('藏品'), findsOneWidget);

    // 默认在「藏品」tab：网格/分类 tab 直接可见，无需切换
    expect(find.text('全部'), findsWidgets);
    expect(find.text('在阿尔勒的卧室'), findsOneWidget);
    expect(find.text('自画像'), findsOneWidget);

    // stub badge should appear for the first card
    expect(find.text('待完善'), findsOneWidget);

    // 「封面」tab 内容尚未出现（TabBarView 惰性构建其它页）
    expect(find.textContaining('奥赛坐落在一座1900年的火车站里'), findsNothing);

    // 切到「封面」tab
    await tester.tap(find.text('封面'));
    await tester.pumpAndSettle();

    expect(find.textContaining('奥赛坐落在一座1900年的火车站里'), findsOneWidget);
  });

  testWidgets('MuseumPage：「封面」tab 显示完整介绍(不折叠) + 开放时间/官网', (tester) async {
    await tester.pumpWidget(_wrap());
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 100));

    // 切到「封面」tab（默认在「藏品」tab）
    await tester.tap(find.text('封面'));
    await tester.pumpAndSettle();

    // 完整介绍全文可见（不再折叠/无 ▾ 展开交互——本身独占一屏）
    expect(find.textContaining('奥赛坐落在一座1900年的火车站里'), findsOneWidget);
    expect(find.text('▾'), findsNothing);

    // 死数据(openingHours/officialUrl)现在有地方显示了
    expect(find.text('开放时间'), findsOneWidget);
    expect(find.textContaining('9:30–18:00'), findsOneWidget);
    expect(find.text('官方网站'), findsOneWidget);
    expect(find.textContaining('musee-orsay.fr'), findsOneWidget);
    // 封面署名(Commons 建筑照公开展示须署名)
    expect(find.text('Jane Doe · CC BY-SA 4.0'), findsOneWidget);
  });

  testWidgets(
      'MuseumPage：description/opening_hours/official_url 全缺 → 「介绍生成中」占位',
      (tester) async {
    await tester.pumpWidget(_wrap(withIntro: false));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 100));

    // 切到「封面」tab（默认在「藏品」tab）
    await tester.tap(find.text('封面'));
    await tester.pumpAndSettle();

    expect(find.text('馆方介绍生成中，敬请期待'), findsOneWidget);
    expect(find.text('开放时间'), findsNothing);
  });

  // --- 必看 tab(spec 2026-10-27 必看打卡 §五.6) ---

  Future<int> pumpWithMustSee(WidgetTester tester, {required int count}) async {
    var requests = 0;
    final container = ProviderContainer(overrides: [
      catalogDataSourceProvider.overrideWithValue(_FakeCatalogDs()),
      museumsListProvider.overrideWith((_) async => [
            MuseumSummary.fromJson(
                {'slug': 'orsay', 'name': '奥赛博物馆', 'must_see_count': count}),
          ]),
      mustSeeProvider.overrideWith((ref, slug) async {
        requests++;
        return const MustSeeData(
          items: [MustSeeItem(qid: 'Q1', title: '奥林匹亚', artist: '马奈')],
          checked: {},
          roundStartedAt: null,
          completed: false,
          medals: [],
        );
      }),
    ]);
    addTearDown(container.dispose);
    // 真机上馆列表在首页就已拉到缓存里;这里先把它解析完,模拟「进馆页时已在缓存」
    await container.read(museumsListProvider.future);
    await tester.pumpWidget(UncontrolledProviderScope(
      container: container,
      child: const MaterialApp(
        localizationsDelegates: AppLocalizations.localizationsDelegates,
        supportedLocales: AppLocalizations.supportedLocales,
        locale: Locale('zh'),
        home: MuseumPage(slug: 'orsay'),
      ),
    ));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 100));
    return requests;
  }

  testWidgets('有必看清单 → 封面/必看/藏品,默认停在「必看」', (tester) async {
    await pumpWithMustSee(tester, count: 12);
    expect(find.text('封面'), findsOneWidget);
    expect(find.text('必看'), findsOneWidget);
    expect(find.text('藏品'), findsOneWidget);
    expect(find.text('奥赛博物馆 · 必看'), findsOneWidget); // 护照页标题
    expect(find.text('在阿尔勒的卧室'), findsNothing); // 藏品页没在前台
  });

  testWidgets('必看件数为 0 → 不出「必看」tab,默认「藏品」', (tester) async {
    await pumpWithMustSee(tester, count: 0);
    expect(find.text('必看'), findsNothing);
    expect(find.text('在阿尔勒的卧室'), findsOneWidget);
  });

  testWidgets('切走再切回「必看」会重新拉进度', (tester) async {
    var n = 0;
    final container = ProviderContainer(overrides: [
      catalogDataSourceProvider.overrideWithValue(_FakeCatalogDs()),
      museumsListProvider.overrideWith((_) async => [
            MuseumSummary.fromJson(
                {'slug': 'orsay', 'name': '奥赛博物馆', 'must_see_count': 1}),
          ]),
      mustSeeProvider.overrideWith((ref, slug) async {
        n++;
        return const MustSeeData(
            items: [],
            checked: {},
            roundStartedAt: null,
            completed: false,
            medals: []);
      }),
    ]);
    addTearDown(container.dispose);
    await container.read(museumsListProvider.future);
    await tester.pumpWidget(UncontrolledProviderScope(
      container: container,
      child: const MaterialApp(
        localizationsDelegates: AppLocalizations.localizationsDelegates,
        supportedLocales: AppLocalizations.supportedLocales,
        locale: Locale('zh'),
        home: MuseumPage(slug: 'orsay'),
      ),
    ));
    await tester.pumpAndSettle();
    final first = n;
    await tester.tap(find.text('藏品'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('必看'));
    await tester.pumpAndSettle();
    expect(n, greaterThan(first));
  });
}
