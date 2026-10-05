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
            footerBuilder: (_, i) => const SizedBox(
                width: 300, height: 80, child: Text('title here')),
          ),
          child: const Text('open'),
        ),
      ),
    ));
    await tester.tap(find.text('open'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('title here'));
    await tester.pumpAndSettle();
    expect(find.text('title here'), findsOneWidget); // 画廊还开着
  });
}
