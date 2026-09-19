import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:gomuseum_app/l10n/app_localizations.dart';
import 'package:gomuseum_app/theme/gm_theme_x.dart';
import 'package:gomuseum_app/ui/gm/gm.dart';
import 'package:gomuseum_app/ui/gm/gm_icon.dart';
import 'package:gomuseum_app/ui/gm/gm_ticket_button.dart';
import 'package:gomuseum_app/features/auth/presentation/auth_provider.dart'
    show dioProvider;
import 'package:gomuseum_app/features/feedback/data/feedback_repository.dart';
import 'package:gomuseum_app/features/payment/presentation/providers/benefits_provider.dart'
    show deviceIdProvider;

/// 反馈的两种场景。**位置决定 scope**，用户不用选。
enum FeedbackScope { object, app }

/// 藏品级：用户能**感知到的现象**，不是技术分层。
///
/// 绝不让他选「文本问题 vs 音频问题」——繁体念错那次文本是对的、TTS 念错了，
/// 用户只会说"读得很怪"，让他选技术分类必然选错，而且多一步。
const _objectKinds = ['content_wrong', 'audio_bad', 'audio_missing', 'other'];
const _appKinds = ['app_crash', 'recognition_bad', 'feature_request', 'other'];

/// 打开反馈面板。
///
/// 藏品级必须传全 [slug]/[qid]/[language]——后端缺一个就 422（一条不知道指向
/// 哪件、哪个语种的"内容反馈"是垃圾数据）。[language] 要传 **API 语言参数**。
Future<void> showFeedbackSheet(
  BuildContext context, {
  FeedbackScope scope = FeedbackScope.object,
  String? slug,
  String? qid,
  String? language,
}) {
  assert(
    scope != FeedbackScope.object ||
        (slug != null && qid != null && language != null),
    '藏品级反馈必须带全坐标，否则后端会 422',
  );
  return showModalBottomSheet<void>(
    context: context,
    isScrollControlled: true,
    backgroundColor: Colors.transparent,
    builder: (_) => FeedbackSheetContent(
      scope: scope,
      slug: slug,
      qid: qid,
      language: language,
    ),
  );
}

/// 面板内容。抽出便于单测（不依赖 `showModalBottomSheet`）——同
/// `paywall_sheet.dart` / `guide_deep_sheet.dart` 的既定做法。
class FeedbackSheetContent extends ConsumerStatefulWidget {
  const FeedbackSheetContent({
    super.key,
    required this.scope,
    this.slug,
    this.qid,
    this.language,
  });

  final FeedbackScope scope;
  final String? slug;
  final String? qid;
  final String? language;

  @override
  ConsumerState<FeedbackSheetContent> createState() =>
      _FeedbackSheetContentState();
}

enum _Step { idle, submitting, failed }

class _FeedbackSheetContentState extends ConsumerState<FeedbackSheetContent> {
  // 草稿**留在局部 State**，不放共享 provider：sheet 关闭即销毁，
  // 两个入口（藏品页 / 设置页）先后打开绝不会串味。用共享 provider 而忘了
  // 按场景重置，就会出现"在藏品页写一半关掉、从设置页打开还带着上次的内容"。
  String? _kind;
  final _text = TextEditingController();
  _Step _step = _Step.idle;

  @override
  void dispose() {
    _text.dispose();
    super.dispose();
  }

  List<String> get _kinds =>
      widget.scope == FeedbackScope.object ? _objectKinds : _appKinds;

  String _kindLabel(AppLocalizations l10n, String kind) => switch (kind) {
        'content_wrong' => l10n.fbContentWrong,
        'audio_bad' => l10n.fbAudioBad,
        'audio_missing' => l10n.fbAudioMissing,
        'app_crash' => l10n.fbAppCrash,
        'recognition_bad' => l10n.fbRecognitionBad,
        'feature_request' => l10n.fbFeatureRequest,
        _ => l10n.fbOther,
      };

  /// device_id 是**锦上添花**，不是提交的前提。
  ///
  /// 拿不到时传 `null` 而**不是空串**：报告按不同 device_id 计数
  /// （`feedback_report.py`），空串会把所有拿不到 id 的人去重成"同一个人"，
  /// 让真实的多人反馈看起来只有一个人报过。
  /// 也必须有超时——没有的话这个 provider 一挂，提交就永远停在「提交中」。
  Future<String?> _deviceId() async {
    try {
      return await ref
          .read(deviceIdProvider.future)
          .timeout(const Duration(seconds: 3));
    } catch (_) {
      return null;
    }
  }

  Future<void> _submit() async {
    if (_kind == null || _step == _Step.submitting) return;
    setState(() => _step = _Step.submitting);

    final ok = await FeedbackRepository(ref.read(dioProvider)).submit(
      scope: widget.scope == FeedbackScope.object ? 'object' : 'app',
      kind: _kind!,
      museumSlug: widget.slug,
      qid: widget.qid,
      language: widget.language,
      text: _text.text,
      deviceId: await _deviceId(),
    );

    if (!mounted) return;
    if (!ok) {
      // 失败**不关面板、不清文本** —— 让用户白填一遍是最气人的。
      setState(() => _step = _Step.failed);
      return;
    }
    Navigator.of(context).pop();
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text(AppLocalizations.of(context)!.fbThanks)),
    );
  }

  @override
  Widget build(BuildContext context) {
    final gm = context.gm;
    final l10n = AppLocalizations.of(context)!;
    final busy = _step == _Step.submitting;

    return Container(
      decoration: BoxDecoration(
        color: gm.bg,
        border: Border(top: BorderSide(color: gm.line)),
      ),
      padding: EdgeInsets.fromLTRB(
        20,
        16,
        20,
        MediaQuery.of(context).viewInsets.bottom + 20,
      ),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Row(
            children: [
              Expanded(
                child: Text(
                  widget.scope == FeedbackScope.object
                      ? l10n.fbTitleObject
                      : l10n.fbTitleApp,
                  style: GmText.serif(size: 15, weight: FontWeight.w700),
                ),
              ),
              GestureDetector(
                onTap: () => Navigator.of(context).pop(),
                behavior: HitTestBehavior.opaque,
                child: GmIcon(GmIcons.close, size: 18, color: gm.sub),
              ),
            ],
          ),
          const SizedBox(height: 14),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: [
              for (final k in _kinds)
                GestureDetector(
                  onTap: busy ? null : () => setState(() => _kind = k),
                  child: Container(
                    padding:
                        const EdgeInsets.symmetric(horizontal: 15, vertical: 7),
                    decoration: BoxDecoration(
                      color: k == _kind ? gm.ctaBg : Colors.transparent,
                      border:
                          Border.all(color: k == _kind ? gm.ctaBg : gm.line),
                    ),
                    child: Text(
                      _kindLabel(l10n, k),
                      style: GmText.sans(
                        size: 12.5,
                        color: k == _kind ? gm.ctaInk : gm.sub,
                      ),
                    ),
                  ),
                ),
            ],
          ),
          const SizedBox(height: 14),
          TextField(
            controller: _text,
            enabled: !busy,
            maxLines: 3,
            maxLength: 1000, // 与后端 TEXT_MAX 一致
            style: GmText.sans(size: 13),
            decoration: InputDecoration(
              hintText: l10n.fbTextHint,
              hintStyle: GmText.sans(size: 13, color: gm.faint),
              border: OutlineInputBorder(
                borderRadius: BorderRadius.zero,
                borderSide: BorderSide(color: gm.line),
              ),
              enabledBorder: OutlineInputBorder(
                borderRadius: BorderRadius.zero,
                borderSide: BorderSide(color: gm.line),
              ),
            ),
          ),
          if (_step == _Step.failed) ...[
            const SizedBox(height: 4),
            Text(l10n.fbFailed,
                style: GmText.sans(size: 12, color: GmColors.error)),
          ],
          const SizedBox(height: 10),
          GmTicketButton(
            label: _step == _Step.failed ? l10n.fbRetry : l10n.fbSubmit,
            busy: busy,
            // 没选 chip 不能提交:kind 是后端必填,也是唯一可统计的那一半。
            onTap: _kind == null || busy ? null : _submit,
          ),
        ],
      ),
    );
  }
}
