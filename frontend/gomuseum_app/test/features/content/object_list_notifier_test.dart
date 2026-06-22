// test/features/content/object_list_notifier_test.dart
import 'package:flutter_test/flutter_test.dart';
import 'package:gomuseum_app/features/content/data/datasources/catalog_remote_datasource.dart';
import 'package:gomuseum_app/features/content/data/models/museum_detail_model.dart';
import 'package:gomuseum_app/features/content/data/models/object_content_model.dart';
import 'package:gomuseum_app/features/content/data/models/object_list_model.dart';
import 'package:gomuseum_app/features/content/presentation/providers/object_list_notifier.dart';

class _FakeDs implements CatalogRemoteDataSource {
  int calls = 0;

  @override
  Future<MuseumDetail> getMuseumDetail(
          {required String slug, String language = 'zh'}) async =>
      throw UnimplementedError();

  @override
  Future<ObjectContent> getObjectContent(
          {required String slug,
          required String qid,
          String language = 'zh'}) async =>
      throw UnimplementedError();

  @override
  Future<ObjectListPage> getObjects(
      {required String slug,
      String? category,
      String sort = 'popularity',
      int limit = 50,
      int offset = 0}) async {
    calls++;
    const total = 120;
    final actualCount = (total - offset).clamp(0, limit);
    return ObjectListPage(
        items: List.generate(
            actualCount,
            (i) => ObjectListItem(
                qid: 'Q${offset + i}',
                title: 't',
                artist: '',
                year: null,
                thumbnail: null,
                status: ContentStatus.ready)),
        total: total,
        limit: limit,
        offset: offset);
  }
}

void main() {
  test('loadMore 递增 offset，hasMore 到底变 false', () async {
    final ds = _FakeDs();
    final n = ObjectListNotifier(ds: ds, slug: 'orsay', category: 'all');
    await n.loadInitial();
    expect(n.state.items.length, 50);
    expect(n.state.hasMore, isTrue);
    await n.loadMore();
    expect(n.state.items.length, 100);
    await n.loadMore();
    expect(n.state.items.length, 120);
    expect(n.state.hasMore, isFalse);
  });
}
