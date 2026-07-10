import 'package:flutter/material.dart';
import 'package:gomuseum_app/features/content/data/models/object_content_model.dart';
import 'package:gomuseum_app/features/guide/presentation/widgets/guide_audio_player.dart';
import 'package:gomuseum_app/theme/gm_palette.dart';
import 'package:gomuseum_app/theme/gm_theme_x.dart';
import 'package:gomuseum_app/theme/gm_tokens.dart';

/// 预设问题竖排，点击就地展开答案（答案随契约返回，无需联网）。
/// slug/qid/language 齐备且该问答有 sort 时，展开处给「问+答连念」播放（section=qa）。
class GuideQuestionList extends StatefulWidget {
  const GuideQuestionList({
    super.key,
    required this.questions,
    this.slug,
    this.qid,
    this.language,
  });
  final List<SuggestedQuestion> questions;
  final String? slug;
  final String? qid;
  final String? language;

  @override
  State<GuideQuestionList> createState() => _GuideQuestionListState();
}

class _GuideQuestionListState extends State<GuideQuestionList> {
  final Set<int> _open = {};

  bool get _canPlay =>
      widget.slug != null && widget.qid != null && widget.language != null;

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
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Text(q.answer!,
                    style: GmText.sans(size: 13, height: 1.9, color: gm.sub),
                    textAlign: TextAlign.justify),
                if (_canPlay && q.sort != null)
                  GuideAudioPlayer(
                    slug: widget.slug!,
                    qid: widget.qid!,
                    language: widget.language!,
                    section: 'qa',
                    qaSort: q.sort,
                  ),
              ],
            ),
          ),
      ],
    );
  }
}
