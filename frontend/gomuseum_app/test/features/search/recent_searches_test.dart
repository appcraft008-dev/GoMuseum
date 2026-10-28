// 最近搜索:只存本机、按范围(全局/各馆)分开、最多 5 条、新的在前、去重。
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gomuseum_app/features/search/data/recent_searches.dart';
import 'package:gomuseum_app/features/search/presentation/recent_searches_view.dart';
import 'package:gomuseum_app/l10n/app_localizations.dart';
import 'package:shared_preferences/shared_preferences.dart';

Future<List<String>> _settled(ProviderContainer c, String scope) async {
  c.read(recentSearchesProvider(scope));
  await Future<void>.delayed(Duration.zero);
  return c.read(recentSearchesProvider(scope));
}

void main() {
  setUp(() => SharedPreferences.setMockInitialValues({}));

  test('新的在前、重复挪到最前(不分大小写)、最多 5 条', () async {
    final c = ProviderContainer();
    addTearDown(c.dispose);
    final n = c.read(recentSearchesProvider('global').notifier);
    for (final q in ['a', 'b', 'c', 'd', 'e', 'f']) {
      await n.add(q);
    }
    await n.add(' C ');
    expect(c.read(recentSearchesProvider('global')), ['C', 'f', 'e', 'd', 'b']);
    await n.add('   ');
    expect(c.read(recentSearchesProvider('global')).length, 5);
  });

  test('全局与各馆分开记,且写进本机存储', () async {
    final c = ProviderContainer();
    await c.read(recentSearchesProvider('global').notifier).add('蒙娜丽莎');
    await c.read(recentSearchesProvider('orsay').notifier).add('睡莲');
    c.dispose();

    final c2 = ProviderContainer();
    addTearDown(c2.dispose);
    expect(await _settled(c2, 'global'), ['蒙娜丽莎']);
    expect(await _settled(c2, 'orsay'), ['睡莲']);
    expect(await _settled(c2, 'louvre'), isEmpty);
  });

  test('启动加载完成前就 add,不会被加载结果覆盖', () async {
    SharedPreferences.setMockInitialValues({
      'recent_searches_global': ['旧'],
    });
    final c = ProviderContainer();
    addTearDown(c.dispose);
    await c.read(recentSearchesProvider('global').notifier).add('新');
    expect(c.read(recentSearchesProvider('global')), ['新', '旧']);
  });

  testWidgets('标签:点击回填、× 删单条、清除全部', (t) async {
    SharedPreferences.setMockInitialValues({
      'recent_searches_global': ['星夜', '睡莲'],
    });
    String? picked;
    await t.pumpWidget(ProviderScope(
      child: MaterialApp(
        localizationsDelegates: AppLocalizations.localizationsDelegates,
        supportedLocales: AppLocalizations.supportedLocales,
        locale: const Locale('zh'),
        home: Scaffold(
          body: RecentSearchesView(scope: 'global', onPick: (q) => picked = q),
        ),
      ),
    ));
    await t.pumpAndSettle();
    expect(find.text('最近搜索'), findsOneWidget);

    await t.tap(find.text('星夜'));
    expect(picked, '星夜');

    await t.tap(find.byKey(const ValueKey('recent-remove-星夜')));
    await t.pumpAndSettle();
    expect(find.text('星夜'), findsNothing);
    expect(find.text('睡莲'), findsOneWidget);

    await t.tap(find.text('清除'));
    await t.pumpAndSettle();
    expect(find.text('睡莲'), findsNothing);
    expect(find.text('最近搜索'), findsNothing); // 没记录就整块不占地方
  });
}
