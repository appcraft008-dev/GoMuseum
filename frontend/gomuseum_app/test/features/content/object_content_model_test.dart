// test/features/content/object_content_model_test.dart
import 'package:flutter_test/flutter_test.dart';
import 'package:gomuseum_app/features/content/data/models/object_content_model.dart';
import 'package:gomuseum_app/features/content/data/models/object_list_model.dart';

void main() {
  test('A5 完整 shape', () {
    final c = ObjectContent.fromJson({
      'qid': 'Q1',
      'category': 'painting',
      'language': 'zh',
      'status': 'published',
      'title': '在阿尔勒的卧室',
      'images': [
        {'url': 'https://x/i.jpg', 'credit': 'Wikimedia / 公有领域'}
      ],
      'facts': {
        'artist': '梵高',
        'date': '1889',
        'medium': '布面油画',
        'dimensions': '57 × 74 cm',
        'inventory': 'RF 1959-2',
        'exhibitions': ['1905 秋季沙龙'],
        'bibliography': ['F 484']
      },
      'tabs': [
        {
          'section_code': 'overview',
          'label': '介绍',
          'body': '正文…',
          'audio_url': 'https://x/o.mp3'
        },
        {'section_code': 'author', 'label': '作者', 'body': ''}, // 空 → 待完善
      ],
      'suggested_questions': [
        {'question': '为什么透视是平的？', 'answer': '因为…'}
      ],
    });
    expect(c.status, ContentStatus.ready); // published→ready
    expect(c.title, '在阿尔勒的卧室');
    expect(c.images.single.credit, 'Wikimedia / 公有领域');
    expect(c.facts.artist, '梵高');
    expect(c.facts.exhibitions, ['1905 秋季沙龙']);
    expect(c.tabs.first.hasBody, isTrue);
    expect(c.tabs[1].hasBody, isFalse); // 空 body → 前端「待完善」
    expect(c.suggestedQuestions.single.question, '为什么透视是平的？');
  });

  test('status=generating；facts/tabs 缺失全空不崩', () {
    final c = ObjectContent.fromJson({'qid': 'Q', 'status': 'generating'});
    expect(c.status, ContentStatus.generating);
    expect(c.title, '未命名');
    expect(c.images, isEmpty);
    expect(c.tabs, isEmpty);
    expect(c.facts.artist, isNull);
  });
}
