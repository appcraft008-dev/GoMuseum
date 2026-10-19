// 墙签检索预填(10-19 用户定):预填整段全选,一打字就整段替换;右侧 × 一点清空。
// 原先光标停在长串末尾,搜不到想换词只能逐字删(真机截图 10-19)。
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gomuseum_app/features/recognition/presentation/pages/camera_page.dart';

Future<List<String>> _pump(WidgetTester t, String? initial) async {
  final changes = <String>[];
  await t.pumpWidget(MaterialApp(
    home: Scaffold(
      body: LabelSearchField(
        initialQuery: initial,
        hint: 'hint',
        onChanged: changes.add,
      ),
    ),
  ));
  await t.pump();
  return changes;
}

TextEditingController _ctrl(WidgetTester t) =>
    t.widget<EditableText>(find.byType(EditableText)).controller;

void main() {
  testWidgets('预填文字整段选中', (t) async {
    await _pump(t, 'Christ Carrying the Cross — Nicolas de Largillierre');
    final c = _ctrl(t);
    expect(c.selection.start, 0);
    expect(c.selection.end, c.text.length);
  });

  testWidgets('点 × 清空并通知,× 随之消失', (t) async {
    final changes = await _pump(t, 'La Pie');
    await t.tap(find.byKey(const Key('labelSearchClear')));
    await t.pump();
    expect(_ctrl(t).text, '');
    expect(changes, ['']);
    expect(find.byKey(const Key('labelSearchClear')), findsNothing);
  });

  testWidgets('空框不显示 ×,输入后出现', (t) async {
    await _pump(t, null);
    expect(find.byKey(const Key('labelSearchClear')), findsNothing);
    await t.enterText(find.byType(TextField), 'RF');
    await t.pump();
    expect(find.byKey(const Key('labelSearchClear')), findsOneWidget);
  });
}
