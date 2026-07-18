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
import 'package:gomuseum_app/features/explore/presentation/pages/museum_page.dart';

// ---------------------------------------------------------------------------
// Fake datasource
// ---------------------------------------------------------------------------
class _FakeCatalogDs implements CatalogRemoteDataSource {
  @override
  Future<MuseumDetail> getMuseumDetail(
      {required String slug, String language = 'zh'}) async {
    return MuseumDetail.fromJson({
      'slug': 'orsay',
      'name': '奥赛博物馆',
      'city': '巴黎',
      'country': 'FR',
      'description': '奥赛坐落在一座1900年的火车站里，收藏印象派与后印象派杰作，'
          '是巴黎最受欢迎的博物馆之一，见证了艺术从学院派走向现代的转折。',
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
Widget _wrap() => ProviderScope(
      overrides: [
        catalogDataSourceProvider.overrideWithValue(_FakeCatalogDs()),
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
  testWidgets('MuseumPage 渲染网格 + 「待完善」角标出现在 stub 卡', (tester) async {
    await tester.pumpWidget(_wrap());

    // Allow async providers to resolve
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 100));

    // Museum name should appear in the top bar
    expect(find.text('奥赛博物馆'), findsOneWidget);

    // Category tabs should show
    expect(find.text('全部'), findsWidgets);

    // Cards should be rendered
    expect(find.text('在阿尔勒的卧室'), findsOneWidget);
    expect(find.text('自画像'), findsOneWidget);

    // stub badge should appear for the first card
    expect(find.text('待完善'), findsOneWidget);
  });

  testWidgets('MuseumPage: 馆介绍 hero 出现，点▾展开', (tester) async {
    await tester.pumpWidget(_wrap());
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 100));

    // 介绍卡文字（默认收起，仍在树中，只是 maxLines 裁剪）+ 折叠指示 ▾
    expect(find.textContaining('奥赛坐落在一座1900年的火车站里'), findsOneWidget);
    expect(find.text('▾'), findsOneWidget);
    expect(find.text('▴'), findsNothing);

    // 点一下 → 展开（指示变 ▴）
    await tester.tap(find.text('▾'));
    await tester.pump();
    expect(find.text('▴'), findsOneWidget);
    expect(find.text('▾'), findsNothing);
  });
}
