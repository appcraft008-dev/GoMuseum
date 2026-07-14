// SearchResultsView 分区渲染 + 无图 stub 出现 + 占位图。
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gomuseum_app/features/search/data/search_api.dart';
import 'package:gomuseum_app/features/search/presentation/search_results_view.dart';
import 'package:gomuseum_app/l10n/app_localizations.dart';
import 'package:gomuseum_app/ui/gm/gm.dart';

const _key = (slug: null, q: 'x', lang: 'zh');

Widget _wrap(SearchResults r) => ProviderScope(
      overrides: [
        searchProvider(_key).overrideWith((ref) => r),
      ],
      child: MaterialApp(
        localizationsDelegates: AppLocalizations.localizationsDelegates,
        supportedLocales: AppLocalizations.supportedLocales,
        locale: const Locale('zh'),
        home: const Scaffold(
          body: SingleChildScrollView(
            child: SearchResultsView(query: _key, showMuseums: true),
          ),
        ),
      ),
    );

void main() {
  testWidgets('分区渲染博物馆段 + 藏品段，无图 stub 也出现', (tester) async {
    await tester.pumpWidget(_wrap(const SearchResults(
      museums: [SearchMuseumHit(slug: 'orsay', name: '奥赛博物馆', city: '巴黎')],
      objects: [
        // 无图 stub（hasImage=false）→ GmInnerImage 类目占位；不发网络请求。
        SearchObject(qid: 'Q1', title: '星夜', artist: '梵高', museum: 'orsay'),
        SearchObject(
            qid: 'Q2', title: '罗纳河上的星夜', artist: '梵高', museum: 'orsay'),
      ],
    )));
    await tester.pump();

    expect(find.text('博物馆'), findsOneWidget); // 段标题
    expect(find.text('藏品'), findsOneWidget);
    expect(find.text('奥赛博物馆'), findsOneWidget);
    expect(find.text('星夜'), findsOneWidget);
    expect(find.text('罗纳河上的星夜'), findsOneWidget); // 无图 stub 照常出现
    // 两件藏品各一枚占位/缩略框
    expect(find.byType(GmInnerImage), findsNWidgets(2));
  });

  testWidgets('空结果 → 诚实空态', (tester) async {
    await tester.pumpWidget(_wrap(SearchResults.empty));
    await tester.pump();
    expect(find.text('没有找到相关结果'), findsOneWidget);
  });
}
