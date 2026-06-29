import 'package:flutter_test/flutter_test.dart';
import 'package:gomuseum_app/features/content/data/models/object_content_model.dart';

void main() {
  test('default_guide 缺失 → null（前向兼容当前后端）', () {
    final c = ObjectContent.fromJson({
      'qid': 'Q1',
      'title': 'T',
      'status': 'published',
      'tabs': [],
      'suggested_questions': [],
    });
    expect(c.defaultGuide, isNull);
  });

  test('default_guide 在场 → 解析 body/audio_url（audio 可空）', () {
    final c = ObjectContent.fromJson({
      'qid': 'Q1',
      'title': 'T',
      'status': 'published',
      'default_guide': {'body': '一分钟主线讲解', 'audio_url': null},
    });
    expect(c.defaultGuide, isNotNull);
    expect(c.defaultGuide!.body, '一分钟主线讲解');
    expect(c.defaultGuide!.audioUrl, isNull);
  });

  test('default_guide 字段类型异常 → 不抛、body 回退空串', () {
    final c = ObjectContent.fromJson({
      'qid': 'Q1',
      'title': 'T',
      'status': 'published',
      'default_guide': {'body': 123, 'audio_url': 456},
    });
    expect(c.defaultGuide, isNotNull);
    expect(c.defaultGuide!.body, '');
    expect(c.defaultGuide!.audioUrl, isNull);
  });
}
