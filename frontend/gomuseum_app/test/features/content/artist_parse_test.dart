import 'package:flutter_test/flutter_test.dart';
import 'package:gomuseum_app/features/content/data/models/object_content_model.dart';

void main() {
  test('artist 缺失 → null（前向兼容老后端）', () {
    final c = ObjectContent.fromJson({
      'qid': 'Q1',
      'title': 'T',
      'status': 'published',
    });
    expect(c.artist, isNull);
  });

  test('artist 全字段 → 完整解析', () {
    final c = ObjectContent.fromJson({
      'qid': 'Q1',
      'title': 'T',
      'status': 'published',
      'artist': {
        'name': '爱德华·马奈',
        'birth': '1832',
        'death': '1883',
        'nationality': 'France',
        'notable_works': ['Olympia', 'The Fifer'],
        'bio': '马奈的经历……',
      },
    });
    final a = c.artist!;
    expect(a.name, '爱德华·马奈');
    expect(a.birth, '1832');
    expect(a.death, '1883');
    expect(a.nationality, 'France');
    expect(a.notableWorks, ['Olympia', 'The Fifer']);
    expect(a.bio, '马奈的经历……');
  });

  test('artist 仅 name、其余 null/空（容错，对齐 staging 实况）', () {
    final c = ObjectContent.fromJson({
      'qid': 'Q1',
      'title': 'T',
      'status': 'published',
      'artist': {
        'name': '居斯塔夫·库尔贝',
        'birth': null,
        'death': null,
        'nationality': null,
        'notable_works': [],
        'bio': '一段经历叙事',
      },
    });
    final a = c.artist!;
    expect(a.name, '居斯塔夫·库尔贝');
    expect(a.birth, isNull);
    expect(a.death, isNull);
    expect(a.nationality, isNull);
    expect(a.notableWorks, isEmpty);
    expect(a.bio, '一段经历叙事');
  });
}
