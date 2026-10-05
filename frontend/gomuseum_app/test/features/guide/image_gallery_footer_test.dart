import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gomuseum_app/features/content/data/models/object_content_model.dart';
import 'package:gomuseum_app/features/guide/presentation/widgets/image_gallery.dart';

void main() {
  testWidgets('footerBuilder renders per page and its button is tappable',
      (tester) async {
    int? picked;
    await tester.pumpWidget(MaterialApp(
      home: Builder(
        builder: (ctx) => TextButton(
          onPressed: () => showImageGallery(
            ctx,
            images: const [
              ObjectImage(url: 'a.jpg', credit: null),
              ObjectImage(url: 'b.jpg', credit: null),
            ],
            footerBuilder: (_, i) =>
                TextButton(onPressed: () => picked = i, child: Text('pick $i')),
          ),
          child: const Text('open'),
        ),
      ),
    ));
    await tester.tap(find.text('open'));
    await tester.pumpAndSettle();
    expect(find.text('pick 0'), findsOneWidget);
    await tester.tap(find.text('pick 0'));
    expect(picked, 0);
  });

  testWidgets('tapping footer blank area does not close the gallery',
      (tester) async {
    await tester.pumpWidget(MaterialApp(
      home: Builder(
        builder: (ctx) => TextButton(
          onPressed: () => showImageGallery(
            ctx,
            images: const [ObjectImage(url: 'a.jpg', credit: null)],
            // 文字下面一块**没有内容**的空白区:点它才测得出透传
            // (SizedBox 包 Text 时 Text 会被撑满整个框,点哪都是点在文字上)
            footerBuilder: (_, i) => const Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                Text('title here'),
                SizedBox(key: Key('gap'), width: 300, height: 60),
              ],
            ),
          ),
          child: const Text('open'),
        ),
      ),
    ));
    await tester.tap(find.text('open'));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('gap')), warnIfMissed: false);
    await tester.pumpAndSettle();
    expect(find.text('title here'), findsOneWidget); // 画廊还开着
  });
}
