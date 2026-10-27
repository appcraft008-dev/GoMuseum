import 'package:flutter_test/flutter_test.dart';
import 'package:gomuseum_app/features/content/data/models/museum_summary_model.dart';
import 'package:gomuseum_app/features/must_see/data/must_see_models.dart';

void main() {
  test('完整 JSON 解析', () {
    final d = MustSeeData.fromJson({
      'items': [
        {
          'qid': 'Q12418',
          'title': '蒙娜丽莎',
          'artist': '达·芬奇',
          'thumbnail': 'https://x/t.jpg',
          'location': {'wing': 'Denon', 'level': 1, 'room': '711'},
        },
        {
          'qid': 'Q2',
          'title': 'B',
          'artist': '',
          'thumbnail': null,
          'location': null
        },
      ],
      'checked': {'Q12418': '2026-10-27T10:00:00+00:00'},
      'round_started_at': '2026-10-27T10:00:00+00:00',
      'completed': false,
      'medals': [
        {'completed_at': '2025-06-01T09:00:00+00:00', 'count': 12},
      ],
    });
    expect(d.items.length, 2);
    expect(d.items.first.location!.wing, 'Denon');
    expect(d.items.first.location!.level, 1);
    expect(d.items.first.location!.room, '711');
    expect(d.items[1].location, isNull);
    expect(d.items[1].thumbnail, isNull);
    expect(d.checkedCount, 1);
    expect(d.checked['Q12418'], DateTime.utc(2026, 10, 27, 10).toLocal());
    expect(d.roundStartedAt, isNotNull);
    expect(d.completed, isFalse);
    expect(d.medals.single.count, 12);
  });

  test('字段缺失或类型不对不崩', () {
    final d = MustSeeData.fromJson({
      'items': [
        {
          'qid': 'Q1',
          'location': {'level': '1', 'room': 711}
        },
        'garbage',
        {'title': 'no qid'},
      ],
      'checked': 'nope',
    });
    expect(d.items.length, 1);
    expect(d.items.single.title, 'Q1'); // 缺标题回退 qid
    expect(d.items.single.artist, '');
    expect(d.items.single.location, isNull); // 类型都不对 → 当没有位置
    expect(d.checked, isEmpty);
    expect(d.medals, isEmpty);
    expect(d.completed, isFalse);
    expect(d.roundStartedAt, isNull);
  });

  test('UTC 时间解析后转本地(马德里 23:30Z → 次日)', () {
    final d = MustSeeData.fromJson({
      'items': [],
      'checked': {'Q1': '2026-10-27T23:30:00+00:00'},
    });
    expect(d.checked['Q1']!.isUtc, isFalse);
    expect(d.checked['Q1'], DateTime.utc(2026, 10, 27, 23, 30).toLocal());
  });

  test('MuseumSummary 缺 must_see_count → 0', () {
    expect(MuseumSummary.fromJson({'slug': 'x'}).mustSeeCount, 0);
    expect(
        MuseumSummary.fromJson({'slug': 'x', 'must_see_count': 12})
            .mustSeeCount,
        12);
  });
}
