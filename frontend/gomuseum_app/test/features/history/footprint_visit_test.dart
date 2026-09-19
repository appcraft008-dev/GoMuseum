// 足迹的分组规则。分错组不会报错，只会让用户把两次参观读成一次 ——
// 或者把去年今天读成今天。
import 'package:flutter_test/flutter_test.dart';
import 'package:gomuseum_app/features/history/domain/entities/history_item.dart';
import 'package:gomuseum_app/features/history/presentation/footprint_visit.dart';

HistoryItem item(String name, DateTime t, {String? slug}) => HistoryItem(
      id: '$name@${t.toIso8601String()}',
      artworkName: name,
      artist: '',
      period: '',
      description: '',
      confidence: 0.9,
      timestamp: t,
      museumSlug: slug,
      qid: 'Q1',
    );

void main() {
  group('groupFootprintsByVisit', () {
    test('🔴 跨年的同月同日不合并', () {
      // 改版前用格式化出来的 "9月18日" 当分组键，而全仓库日期文案都不含年份，
      // 于是这两条会并成一组。"过了很长时间再回头看"正是它发作的条件。
      final visits = groupFootprintsByVisit([
        item('今年', DateTime(2026, 9, 18, 10), slug: 'orsay'),
        item('去年', DateTime(2025, 9, 18, 10), slug: 'orsay'),
      ]);

      expect(visits.length, 2, reason: '去年今天被并进今年今天了');
      expect(visits.first.items.single.artworkName, '今年', reason: '应新到旧');
      expect(visits.last.items.single.artworkName, '去年');
    });

    test('一天里逛了两个馆 → 两次参观', () {
      // 奥赛和橘园走路十分钟，巴黎一天连看两个是常态。
      final visits = groupFootprintsByVisit([
        item('舞女', DateTime(2026, 9, 18, 10), slug: 'orsay'),
        item('睡莲', DateTime(2026, 9, 18, 15), slug: 'orangerie'),
      ]);

      expect(visits.length, 2);
      expect(visits.map((v) => v.museumSlug), ['orangerie', 'orsay']);
    });

    test('同一天同一个馆的多件 → 合并成一次参观（对照组）', () {
      // 少了这条，一个"每条都单开一组"的实现也能让上面两条全绿。
      final visits = groupFootprintsByVisit([
        item('a', DateTime(2026, 9, 18, 10), slug: 'orsay'),
        item('b', DateTime(2026, 9, 18, 11), slug: 'orsay'),
        item('c', DateTime(2026, 9, 18, 12), slug: 'orsay'),
      ]);

      expect(visits.length, 1);
      expect(visits.single.items.length, 3);
    });

    test('一天里 A→B→A 算两次参观，不是三次', () {
      // 按键归拢而不是按相邻游程：用户记忆里那天只去过两个馆。
      final visits = groupFootprintsByVisit([
        item('a1', DateTime(2026, 9, 18, 10), slug: 'orsay'),
        item('b1', DateTime(2026, 9, 18, 12), slug: 'orangerie'),
        item('a2', DateTime(2026, 9, 18, 14), slug: 'orsay'),
      ]);

      expect(visits.length, 2, reason: '游程分组会切成三次');
      final orsay = visits.firstWhere((v) => v.museumSlug == 'orsay');
      expect(orsay.items.map((i) => i.artworkName), ['a2', 'a1']);
    });

    test('整条时间线倒序，组内也倒序', () {
      final visits = groupFootprintsByVisit([
        item('旧', DateTime(2026, 8, 1, 9), slug: 'louvre'),
        item('新', DateTime(2026, 9, 18, 9), slug: 'orsay'),
        item('新一点', DateTime(2026, 9, 18, 17), slug: 'orsay'),
      ]);

      expect(visits.map((v) => v.museumSlug), ['orsay', 'louvre']);
      expect(visits.first.items.map((i) => i.artworkName), ['新一点', '新']);
      expect(visits.first.latest.hour, 17);
    });

    test('museumSlug 为 null 的老事件自成一组，不会消失', () {
      final visits = groupFootprintsByVisit([
        item('有馆', DateTime(2026, 9, 18, 10), slug: 'orsay'),
        item('老事件', DateTime(2026, 9, 18, 11)),
      ]);

      expect(visits.length, 2);
      expect(
        visits.expand((v) => v.items).map((i) => i.artworkName),
        containsAll(['有馆', '老事件']),
        reason: '没有馆的足迹被丢掉了',
      );
    });

    test('空列表不炸', () {
      expect(groupFootprintsByVisit([]), isEmpty);
    });
  });

  group('footprintsSpanCities', () {
    test('四个馆全在巴黎 → 不显示城市层', () {
      expect(footprintsSpanCities(['巴黎', '巴黎', '巴黎']), isFalse);
    });

    test('跨城 → 显示（对照组：恒 false 的实现会在这里红）', () {
      expect(footprintsSpanCities(['巴黎', '阿姆斯特丹']), isTrue);
    });

    test('🔴 "巴黎 + 未知" 不算跨城', () {
      // 城市为空只说明馆列表没加载完 / 事件没带馆，不是"去了另一个城市"。
      expect(footprintsSpanCities(['巴黎', '', '巴黎']), isFalse);
    });

    test('全都未知 → 不显示', () {
      expect(footprintsSpanCities(['', '']), isFalse);
    });
  });
}
