// S4:识别选择页接管藏品点选(带照片进详情、回传答案);按编号找时露出完整馆藏号。
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gomuseum_app/features/search/data/search_api.dart';
import 'package:gomuseum_app/features/search/presentation/search_results_view.dart';
import 'package:gomuseum_app/l10n/app_localizations.dart';

const _hit = SearchResults(objects: [
  SearchObject(
      qid: 'Q1',
      title: 'Portrait',
      artist: 'X',
      museum: 'orsay',
      inventory: 'INV 779'),
]);

Widget _wrap(String q, {void Function(SearchObject)? onPick}) {
  final key = (slug: null, q: q, lang: 'en');
  return ProviderScope(
    overrides: [searchProvider(key).overrideWith((ref) => _hit)],
    child: MaterialApp(
      localizationsDelegates: AppLocalizations.localizationsDelegates,
      supportedLocales: AppLocalizations.supportedLocales,
      home: Scaffold(
        body: SearchResultsView(
            query: key, showMuseums: false, onPickObject: onPick),
      ),
    ),
  );
}

void main() {
  testWidgets('onPickObject replaces default navigation', (t) async {
    SearchObject? picked;
    await t.pumpWidget(_wrap('779', onPick: (o) => picked = o));
    await t.pump();
    await t.tap(find.text('Portrait'));
    expect(picked?.qid, 'Q1');
  });

  testWidgets('inventory shown when query has digits', (t) async {
    await t.pumpWidget(_wrap('779'));
    await t.pump();
    expect(find.textContaining('INV 779'), findsOneWidget);
  });

  testWidgets('inventory hidden when searching by name', (t) async {
    await t.pumpWidget(_wrap('portrait'));
    await t.pump();
    expect(find.textContaining('INV 779'), findsNothing);
  });
}
