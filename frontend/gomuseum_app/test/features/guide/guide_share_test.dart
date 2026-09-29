// 分享键(spec 2026-09-20-share-web-pages-design §六)。
// 钉三件事:share 为 null 时根本没有分享键(空页不分享)、解析容错(不裸 as String)、
// 分享图下载失败时退化为只发文字+链接,而不是报错打断。
import 'dart:typed_data';

import 'package:flutter_test/flutter_test.dart';
import 'package:gomuseum_app/features/content/data/models/object_content_model.dart';
import 'package:gomuseum_app/features/guide/presentation/share_object.dart';
import 'package:share_plus/share_plus.dart';

void main() {
  group('ShareInfo.fromJson 容错', () {
    test('完整字段', () {
      final s = ShareInfo.fromJson({
        'url': 'https://gomuseum.app/a/louvre/Q1?lang=zh&s=app',
        'text': '《门闩》— 弗拉戈纳尔',
        'image_url': 'https://gomuseum.app/a/louvre/Q1/card.png?lang=zh',
      })!;
      expect(s.text, '《门闩》— 弗拉戈纳尔');
    });
    test('null / 非 Map / 缺 url → null(老后端没有这个字段)', () {
      expect(ShareInfo.fromJson(null), isNull);
      expect(ShareInfo.fromJson('x'), isNull);
      expect(ShareInfo.fromJson({'text': 't'}), isNull);
      expect(ShareInfo.fromJson({'url': 42}), isNull);
    });
    test('ObjectContent 缺 share 字段 → null', () {
      final c = ObjectContent.fromJson(const {'qid': 'Q1'});
      expect(c.share, isNull);
    });
  });

  group('shareObject', () {
    const info = ShareInfo(
      url: 'https://gomuseum.app/a/louvre/Q1?lang=zh&s=app',
      text: '《门闩》— 弗拉戈纳尔',
      imageUrl: 'https://gomuseum.app/a/louvre/Q1/card.png?lang=zh',
    );

    test('图下载成功 → 图 + 文字 + 链接', () async {
      ShareParams? sent;
      await shareObject(info,
          fetch: (_) async => Uint8List.fromList([1, 2, 3]),
          send: (p) async => sent = p);
      expect(sent!.files, hasLength(1));
      expect(sent!.text,
          '《门闩》— 弗拉戈纳尔\nhttps://gomuseum.app/a/louvre/Q1?lang=zh&s=app');
    });

    test('图下载失败 → 只发文字 + 链接,不抛', () async {
      ShareParams? sent;
      await shareObject(info,
          fetch: (_) async => null, send: (p) async => sent = p);
      expect(sent!.files, anyOf(isNull, isEmpty));
      expect(sent!.text, contains(info.url));
    });
  });
}
