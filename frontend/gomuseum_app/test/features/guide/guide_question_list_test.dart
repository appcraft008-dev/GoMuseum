import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gomuseum_app/features/content/data/models/object_content_model.dart';
import 'package:gomuseum_app/features/guide/presentation/widgets/guide_question_list.dart';
import 'package:gomuseum_app/theme/app_theme.dart';

Widget _wrap(Widget c) =>
    MaterialApp(theme: AppTheme.lightTheme(), home: Scaffold(body: c));

void main() {
  testWidgets('点击问题就地展开答案', (t) async {
    await t.pumpWidget(_wrap(const GuideQuestionList(questions: [
      SuggestedQuestion(question: '为什么星星这么大？', answer: '因为是煤气灯。'),
    ])));
    await t.pumpAndSettle();
    expect(find.text('因为是煤气灯。'), findsNothing); // 初始收起
    await t.tap(find.text('为什么星星这么大？'));
    await t.pumpAndSettle();
    expect(find.text('因为是煤气灯。'), findsOneWidget); // 展开
  });
}
