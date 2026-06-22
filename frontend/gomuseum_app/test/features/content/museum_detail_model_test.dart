// test/features/content/museum_detail_model_test.dart
import 'package:flutter_test/flutter_test.dart';
import 'package:gomuseum_app/features/content/data/models/museum_detail_model.dart';

void main() {
  test('A2 标准 shape 解析 categories', () {
    final m = MuseumDetail.fromJson({
      'slug': 'orsay',
      'name': '奥赛博物馆',
      'city': '巴黎',
      'country': 'FR',
      'coordinates': [48.8599, 2.3266],
      'opening_hours': '周二–周日 9:30–18:00',
      'official_url': 'https://www.musee-orsay.fr',
      'categories': [
        {'code': 'all', 'label': '全部', 'count': 1400},
        {'code': 'painting', 'label': '绘画', 'count': 500},
      ],
    });
    expect(m.name, '奥赛博物馆');
    expect(m.categories.length, 2);
    expect(m.categories.first.code, 'all');
    expect(m.coordinates, [48.8599, 2.3266]);
  });

  test('缺 name → 回退旧 name_zh → 再回退 slug；缺 categories → 空表不崩', () {
    final m = MuseumDetail.fromJson({'slug': 'x', 'name_zh': '老字段馆'});
    expect(m.name, '老字段馆');
    expect(m.categories, isEmpty);
    final m2 = MuseumDetail.fromJson({'slug': 'y'});
    expect(m2.name, 'y');
  });
}
