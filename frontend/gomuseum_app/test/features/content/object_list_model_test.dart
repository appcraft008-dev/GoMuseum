// test/features/content/object_list_model_test.dart
import 'package:flutter_test/flutter_test.dart';
import 'package:gomuseum_app/features/content/data/models/object_list_model.dart';

void main() {
  test('A3 分页 + content_status 缺省 ready', () {
    final p = ObjectListPage.fromJson({
      'items': [
        {
          'qid': 'Q1',
          'title': '在阿尔勒的卧室',
          'artist': '梵高',
          'year': '1889',
          'thumbnail': 'https://x/t.jpg',
          'content_status': 'ready'
        },
        {'qid': 'Q2'}, // 极端缺字段
      ],
      'total': 500,
      'limit': 50,
      'offset': 0,
    });
    expect(p.total, 500);
    expect(p.items.first.title, '在阿尔勒的卧室');
    expect(p.items.first.status, ContentStatus.ready);
    // 缺字段：title 占位「未命名」，thumbnail null，status 缺省 ready
    expect(p.items[1].title, '未命名');
    expect(p.items[1].thumbnail, isNull);
    expect(p.items[1].status, ContentStatus.ready);
  });

  test('content_status=stub 解析为 stub；未知值回退 ready', () {
    expect(
        ObjectListItem.fromJson({'qid': 'a', 'content_status': 'stub'}).status,
        ContentStatus.stub);
    expect(ObjectListItem.fromJson({'qid': 'a', 'content_status': '??'}).status,
        ContentStatus.ready);
  });
}
