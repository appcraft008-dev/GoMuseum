/// 足迹的两条契约:解析不许崩、点进去要走得到真讲解。
///
/// 背景:足迹 tab(底部四主 tab 之一)此前读的是一张 prod 上 0 行、且没有任何
/// 写入方的表 —— 结构上永远空。后端改成读识别事件之后,前端这两处就成了
/// "看得见"和"点得动"的分界线。
library;

import 'package:flutter_test/flutter_test.dart';
import 'package:gomuseum_app/features/history/data/models/history_item_model.dart';

void main() {
  group('解析:后端字段缺了也不能崩', () {
    test('四个字符串字段为 null 时回退成空串,不抛异常', () {
      // 富化数据天然缺字段。原实现是裸 `as String`,这份 JSON 会直接抛
      // type cast 异常 → 足迹页整页崩(同 2026-06-16 title_zh 变 null 那次)。
      final item = HistoryItemModel.fromJson({
        'id': 'e1',
        'artwork_name': null,
        'artist': null,
        'period': null,
        'description': null,
        'confidence': null,
        'timestamp': null,
      });

      expect(item.artworkName, '');
      expect(item.artist, '');
      expect(item.period, '');
      expect(item.description, '');
      expect(item.confidence, 0.0);
    });

    test('字段整个缺席（老后端/新老混部）也不崩', () {
      final item = HistoryItemModel.fromJson({'id': 'e1'});
      expect(item.artworkName, '');
      expect(item.hasGuide, isFalse);
    });

    test('confidence 是 int 而不是 double 时也能解析', () {
      // JSON 里 1 和 1.0 都可能出现,`as num` 之后再 toDouble
      expect(HistoryItemModel.fromJson({'id': 'e', 'confidence': 1}).confidence,
          1.0);
    });

    test('正常数据照常解析,包括新增的加法字段', () {
      final item = HistoryItemModel.fromJson({
        'id': 'e1',
        'artwork_name': '蒙娜丽莎',
        'artist': '达芬奇',
        'period': '文艺复兴',
        'description': '',
        'confidence': 0.93,
        'timestamp': '2026-09-05T10:30:00',
        'museum_slug': 'louvre',
        'qid': 'Q12418',
        'thumbnail': 'https://cdn.example/thumb.jpg',
      });

      expect(item.artworkName, '蒙娜丽莎');
      expect(item.confidence, 0.93);
      expect(item.museumSlug, 'louvre');
      expect(item.qid, 'Q12418');
      expect(item.thumbnail, 'https://cdn.example/thumb.jpg');
      expect(item.timestamp.hour, 10);
    });
  });

  group('点进去走哪条路', () {
    test('有 slug+qid → 走馆藏那条(能拿到完整讲解)', () {
      final item = HistoryItemModel.fromJson({
        'id': 'e1',
        'museum_slug': 'louvre',
        'qid': 'Q12418',
      });
      expect(item.hasGuide, isTrue);
    });

    test('缺任意一半都不算 —— GuideArgs 断言要求两者同时存在', () {
      // GuideArgs 的 assert 是 `(slug != null && qid != null) || result != null`,
      // 只带其中一个会在运行时炸断言,必须回落到 result 那条兜底路径。
      expect(
        HistoryItemModel.fromJson({'id': 'e', 'museum_slug': 'louvre'})
            .hasGuide,
        isFalse,
      );
      expect(
        HistoryItemModel.fromJson({'id': 'e', 'qid': 'Q12418'}).hasGuide,
        isFalse,
      );
    });
  });

  test('toEntity 不能把新字段丢掉', () {
    // 加了字段却忘了在 toEntity 里带上 —— 解析对了、页面却拿不到,
    // 是这套 model/entity 分层最容易漏的一处。
    final e = HistoryItemModel.fromJson({
      'id': 'e1',
      'museum_slug': 'louvre',
      'qid': 'Q12418',
      'thumbnail': 'https://cdn.example/t.jpg',
    }).toEntity();

    expect(e.museumSlug, 'louvre');
    expect(e.qid, 'Q12418');
    expect(e.thumbnail, 'https://cdn.example/t.jpg');
    expect(e.hasGuide, isTrue);
  });
}
