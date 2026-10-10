// 候选行点击区(10-10 用户定):整行含缩略图 = 选中;只有角上放大镜才全屏比对。
// 原先缩略图本身是放大,而人看着画就点画,确认了也常误点进大图。
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gomuseum_app/features/recognition/data/models/recognize_response.dart';
import 'package:gomuseum_app/features/recognition/presentation/pages/camera_page.dart';

const _item = RecognizedItem(
    qid: 'Q1',
    title: 'Olympia',
    artist: 'Manet',
    thumbnail: null,
    score: 0.9,
    museum: 'orsay',
    image: 'https://x/olympia.jpg');

Future<List<String>> _tap(WidgetTester t, Finder Function() target,
    {RecognizedItem item = _item}) async {
  final taps = <String>[];
  await t.pumpWidget(MaterialApp(
      home: Scaffold(
          body: CandidateRow(
              item: item,
              onPick: () => taps.add('pick'),
              onZoom: () => taps.add('zoom')))));
  await t.tap(target());
  return taps;
}

void main() {
  testWidgets('点缩略图 = 选中,不放大', (t) async {
    expect(await _tap(t, () => find.byKey(const Key('candThumb'))), ['pick']);
  });

  testWidgets('点放大镜 = 全屏比对,不选中', (t) async {
    expect(await _tap(t, () => find.byKey(const Key('candZoom'))), ['zoom']);
  });

  testWidgets('放大镜点击区 ≥36dp(原 12dp 图标难点中)', (t) async {
    await _tap(t, () => find.byKey(const Key('candZoom')));
    final s = t.getSize(find.byKey(const Key('candZoom')));
    expect(s.width >= 36 && s.height >= 36, isTrue);
  });

  testWidgets('无大图的作品不显示放大镜', (t) async {
    const noImage = RecognizedItem(
        qid: 'Q2',
        title: 'X',
        artist: 'Y',
        thumbnail: null,
        score: 0.9,
        museum: 'orsay');
    expect(await _tap(t, () => find.text('X'), item: noImage), ['pick']);
    expect(find.byKey(const Key('candZoom')), findsNothing);
  });
}
