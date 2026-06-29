import 'package:flutter/material.dart';
import 'package:gomuseum_app/features/content/data/models/object_content_model.dart';
import 'package:gomuseum_app/theme/gm_palette.dart';
import 'package:gomuseum_app/theme/gm_theme_x.dart';
import 'package:gomuseum_app/theme/gm_tokens.dart';

/// 预设问题竖排，点击就地展开答案（答案随契约返回，无需联网）。
class GuideQuestionList extends StatefulWidget {
  const GuideQuestionList({super.key, required this.questions});
  final List<SuggestedQuestion> questions;

  @override
  State<GuideQuestionList> createState() => _GuideQuestionListState();
}

class _GuideQuestionListState extends State<GuideQuestionList> {
  final Set<int> _open = {};

  @override
  Widget build(BuildContext context) {
    final gm = context.gm;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        for (int i = 0; i < widget.questions.length; i++)
          _row(context, gm, i, widget.questions[i]),
        Container(height: 1, color: gm.line),
      ],
    );
  }

  Widget _row(BuildContext context, GmPalette gm, int i, SuggestedQuestion q) {
    final open = _open.contains(i);
    final hasAnswer = (q.answer ?? '').trim().isNotEmpty;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        GestureDetector(
          behavior: HitTestBehavior.opaque,
          onTap: hasAnswer
              ? () => setState(() => open ? _open.remove(i) : _open.add(i))
              : null,
          child: Container(
            padding: const EdgeInsets.symmetric(vertical: 11),
            decoration: BoxDecoration(
              border: Border(top: BorderSide(color: gm.line)),
            ),
            child: Row(
              children: [
                Expanded(
                  child: Text(q.question,
                      style: GmText.sans(size: 13.5, height: 1.45)),
                ),
                const SizedBox(width: 10),
                SizedBox(
                  width: 14,
                  child: Text(open ? '⌄' : '›',
                      textAlign: TextAlign.center,
                      style: GmText.sans(
                          size: 18, color: gm.accent, weight: FontWeight.w700)),
                ),
              ],
            ),
          ),
        ),
        if (open && hasAnswer)
          Container(
            padding: const EdgeInsets.fromLTRB(0, 10, 0, 14),
            decoration: BoxDecoration(
              border: Border(top: BorderSide(color: gm.line)),
            ),
            child: Text(q.answer!,
                style: GmText.sans(size: 13, height: 1.9, color: gm.sub),
                textAlign: TextAlign.justify),
          ),
      ],
    );
  }
}
