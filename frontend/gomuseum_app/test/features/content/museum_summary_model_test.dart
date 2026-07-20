import 'package:flutter_test/flutter_test.dart';
import 'package:gomuseum_app/features/content/data/models/museum_summary_model.dart';

void main() {
  test('A1 标准 shape 解析', () {
    final m = MuseumSummary.fromJson({
      'slug': 'orsay',
      'name': '奥赛博物馆',
      'city': '巴黎',
      'country': 'FR',
      'coordinates': [48.8599, 2.3266],
      'artwork_count': 1400,
    });
    expect(m.slug, 'orsay');
    expect(m.name, '奥赛博物馆');
    expect(m.city, '巴黎');
    expect(m.country, 'FR');
    expect(m.coordinates, [48.8599, 2.3266]);
    expect(m.artworkCount, 1400);
  });

  test('缺字段防御：name→name_zh→slug 回退；坐标缺→空列表；artwork_count 缺→0', () {
    // name 缺，回退 name_zh
    final m1 = MuseumSummary.fromJson({'slug': 'vangogh', 'name_zh': '梵高博物馆'});
    expect(m1.name, '梵高博物馆');
    expect(m1.coordinates, isEmpty);
    expect(m1.artworkCount, 0);

    // name 和 name_zh 均缺，回退 slug
    final m2 = MuseumSummary.fromJson({'slug': 'louvre'});
    expect(m2.name, 'louvre');
    expect(m2.city, '');
    expect(m2.country, '');
  });

  test('artwork_count 为整数型 num 解析', () {
    final m = MuseumSummary.fromJson({
      'slug': 'x',
      'artwork_count': 500,
      'coordinates': [51.5, -0.1],
    });
    expect(m.artworkCount, 500);
    expect(m.coordinates.length, 2);
    expect(m.coordinates[0], closeTo(51.5, 0.001));
  });

  test('cover_image 加法字段(2026-07-20)：解析；空串/缺 → null', () {
    final m = MuseumSummary.fromJson(const {
      'slug': 'orsay',
      'cover_image': 'https://r2/cover_thumb.jpg',
    });
    expect(m.coverImage, 'https://r2/cover_thumb.jpg');

    final empty =
        MuseumSummary.fromJson(const {'slug': 'orsay', 'cover_image': ''});
    expect(empty.coverImage, isNull);

    final old = MuseumSummary.fromJson(const {'slug': 'orsay'});
    expect(old.coverImage, isNull);
  });
}
