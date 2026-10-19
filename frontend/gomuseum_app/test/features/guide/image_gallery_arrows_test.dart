// 左右箭头(10-19 用户提):只有页码「1/3」时没人想到能滑;放大后拖动是平移不是翻页,
// 箭头是放大状态下换一张比对的唯一途径。首张无左箭头、末张无右箭头。
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gomuseum_app/features/content/data/models/object_content_model.dart';
import 'package:gomuseum_app/features/guide/presentation/widgets/image_gallery.dart';

Future<void> _open(WidgetTester t, int n) async {
  await t.pumpWidget(MaterialApp(
    home: Builder(
      builder: (ctx) => TextButton(
        onPressed: () => showImageGallery(ctx, images: [
          for (var i = 0; i < n; i++) ObjectImage(url: '$i.jpg', credit: null)
        ]),
        child: const Text('open'),
      ),
    ),
  ));
  await t.tap(find.text('open'));
  await t.pumpAndSettle();
}

const _prev = Key('galPrev');
const _next = Key('galNext');

void main() {
  testWidgets('首张只有右箭头,点它翻到下一张', (t) async {
    await _open(t, 3);
    expect(find.byKey(_prev), findsNothing);
    await t.tap(find.byKey(_next));
    await t.pumpAndSettle();
    expect(find.text('2/3'), findsOneWidget);
    expect(find.byKey(_prev), findsOneWidget);
  });

  testWidgets('末张没有右箭头,点左箭头回上一张', (t) async {
    await _open(t, 2);
    await t.tap(find.byKey(_next));
    await t.pumpAndSettle();
    expect(find.byKey(_next), findsNothing);
    await t.tap(find.byKey(_prev));
    await t.pumpAndSettle();
    expect(find.text('1/2'), findsOneWidget);
  });

  testWidgets('单张图不显示箭头', (t) async {
    await _open(t, 1);
    expect(find.byKey(_prev), findsNothing);
    expect(find.byKey(_next), findsNothing);
  });

  trailingPageTests();
}

// 候选比对(10-19 用户定):最后一个候选后面多一页「都不是」,滑过去就到,滑回来能撤。
void trailingPageTests() {
  Future<void> openWithTrailing(WidgetTester t) async {
    await t.pumpWidget(MaterialApp(
      home: Builder(
        builder: (ctx) => TextButton(
          onPressed: () => showImageGallery(
            ctx,
            images: const [
              ObjectImage(url: 'a.jpg', credit: null),
              ObjectImage(url: 'b.jpg', credit: null),
            ],
            footerBuilder: (_, i) => Text('footer $i'),
            trailingPage: const Text('none page'),
          ),
          child: const Text('open'),
        ),
      ),
    ));
    await t.tap(find.text('open'));
    await t.pumpAndSettle();
  }

  testWidgets('末张图仍有右箭头,翻过去是尾页:无页码、无底栏、无右箭头', (t) async {
    await openWithTrailing(t);
    await t.tap(find.byKey(_next));
    await t.pumpAndSettle();
    expect(find.text('2/2'), findsOneWidget);
    await t.tap(find.byKey(_next));
    await t.pumpAndSettle();
    expect(find.text('none page'), findsOneWidget);
    expect(find.textContaining('/2'), findsNothing);
    expect(find.textContaining('footer'), findsNothing);
    expect(find.byKey(_next), findsNothing);
  });

  testWidgets('尾页左滑回来,回到最后一张图', (t) async {
    await openWithTrailing(t);
    await t.tap(find.byKey(_next));
    await t.pumpAndSettle();
    await t.tap(find.byKey(_next));
    await t.pumpAndSettle();
    await t.tap(find.byKey(_prev));
    await t.pumpAndSettle();
    expect(find.text('2/2'), findsOneWidget);
    expect(find.text('footer 1'), findsOneWidget);
  });
}
