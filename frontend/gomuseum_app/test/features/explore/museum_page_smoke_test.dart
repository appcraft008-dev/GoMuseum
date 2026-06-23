// test/features/explore/museum_page_smoke_test.dart
//
// Widget smoke test for MuseumPage. Overrides catalogDataSourceProvider with a
// fake datasource that returns canned data — one stub item + one ready item.
// Asserts the grid renders and find.text('待完善') appears for the stub card.

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gomuseum_app/features/content/data/datasources/catalog_remote_datasource.dart';
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
}

// ---------------------------------------------------------------------------
// Test helper
// ---------------------------------------------------------------------------
Widget _wrap() => ProviderScope(
      overrides: [
        catalogDataSourceProvider.overrideWithValue(_FakeCatalogDs()),
      ],
      child: const MaterialApp(
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
}
