// 搜索模型解析容错：museum/thumbnail 缺失不炸（禁裸强转），has_image 默认 false。
import 'package:flutter_test/flutter_test.dart';
import 'package:gomuseum_app/features/search/data/search_api.dart';

void main() {
  test('SearchObject 缺 museum/thumbnail/has_image → 安全默认', () {
    final o = SearchObject.fromJson({'qid': 'Q1', 'title': '星夜'});
    expect(o.museum, isNull);
    expect(o.thumbnail, isNull);
    expect(o.hasImage, isFalse);
    expect(o.artist, '');
  });

  test('SearchObject 缺 title → 回退 qid', () {
    expect(SearchObject.fromJson({'qid': 'Q9'}).title, 'Q9');
  });

  test('SearchObject 完整解析', () {
    final o = SearchObject.fromJson({
      'qid': 'Q1',
      'title': '星夜',
      'artist': '文森特·梵高',
      'year': '1889',
      'thumbnail': 'http://x/1.jpg',
      'museum': 'orsay',
      'has_image': true,
    });
    expect(o.hasImage, isTrue);
    expect(o.museum, 'orsay');
    expect(o.year, '1889');
  });

  test('SearchResults 解析两段 + 空默认', () {
    final r = SearchResults.fromJson({
      'query': 'q',
      'museums': [
        {'slug': 'orsay', 'name': '奥赛', 'city': '巴黎'}
      ],
      'objects': [
        {'qid': 'Q1', 'title': '星夜'}
      ],
    });
    expect(r.museums.single.slug, 'orsay');
    expect(r.objects.single.qid, 'Q1');
    expect(r.isEmpty, isFalse);

    final empty = SearchResults.fromJson({'query': 'q'});
    expect(empty.isEmpty, isTrue);
  });
}
