/// 馆详情缓存键必须含语言 —— 否则切回原语言仍会重新加载(真机反馈)。
import 'package:flutter_test/flutter_test.dart';
import 'package:gomuseum_app/features/content/presentation/providers/catalog_providers.dart';

void main() {
  test('缓存键按 (slug, language) 区分:不同语言是不同的 provider 实例', () {
    final zh = museumDetailProvider((slug: 'louvre', language: 'zh'));
    final en = museumDetailProvider((slug: 'louvre', language: 'en'));
    final zh2 = museumDetailProvider((slug: 'louvre', language: 'zh'));
    expect(zh, isNot(equals(en)), reason: '不同语言必须是不同实例,否则互相挤掉缓存');
    expect(zh, equals(zh2), reason: '同 (馆,语言) 必须命中同一实例,切回来才不重取');
  });

  test('不同馆同语言也各自缓存', () {
    final a = museumDetailProvider((slug: 'louvre', language: 'zh'));
    final b = museumDetailProvider((slug: 'orsay', language: 'zh'));
    expect(a, isNot(equals(b)));
  });
}
