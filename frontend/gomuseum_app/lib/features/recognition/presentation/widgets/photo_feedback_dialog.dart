import 'dart:typed_data';

import 'package:cross_file/cross_file.dart';
import 'package:flutter/material.dart';
import 'package:gomuseum_app/l10n/app_localizations.dart';
import 'package:gomuseum_app/theme/gm_theme_x.dart';
import 'package:gomuseum_app/ui/gm/gm.dart';

/// 本次 App 进程内用户拒绝过(没勾就继续)→ 不再问(spec ⑩)。进程重启即重置。
bool photoFeedbackDeclinedThisSession = false;

class PhotoFeedbackChoice {
  const PhotoFeedbackChoice({required this.send, this.text = ''});
  final bool send;
  final String text;
}

/// 「把这张照片发给我们?」——缩略图 + 一句用途 + **默认不勾**的勾选框 + 选填补充 + 继续。
/// 只有一个「继续」按钮:不勾不分叉,后续流程与勾选完全一样(spec ⑦⑩)。
/// 返回 null = 用户用系统返回关掉了(调用方按不发处理)。
Future<PhotoFeedbackChoice?> showPhotoFeedbackDialog(BuildContext context,
        {required XFile photo}) =>
    showDialog<PhotoFeedbackChoice>(
      context: context,
      builder: (_) => _PhotoFeedbackDialog(photo: photo),
    );

/// 有状态:输入框控制器跟着组件生命周期释放(在 showDialog 返回时释放会撞上关闭动画)。
class _PhotoFeedbackDialog extends StatefulWidget {
  const _PhotoFeedbackDialog({required this.photo});
  final XFile photo;

  @override
  State<_PhotoFeedbackDialog> createState() => _PhotoFeedbackDialogState();
}

class _PhotoFeedbackDialogState extends State<_PhotoFeedbackDialog> {
  late final Future<Uint8List> _bytes = widget.photo.readAsBytes();
  final _note = TextEditingController();
  bool _checked = false;

  @override
  void dispose() {
    _note.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context)!;
    final gm = context.gm;
    return AlertDialog(
      backgroundColor: gm.bg,
      title: Text(l10n.photoFbTitle,
          style: GmText.serif(size: 16.5, weight: FontWeight.w700)),
      content: SingleChildScrollView(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            SizedBox(
              height: 120,
              width: double.infinity,
              child: FutureBuilder<Uint8List>(
                future: _bytes,
                builder: (_, snap) => snap.hasData
                    ? Image.memory(snap.data!, fit: BoxFit.cover)
                    : ColoredBox(color: gm.chipBg),
              ),
            ),
            const SizedBox(height: 10),
            Text(l10n.photoFbBody,
                style: GmText.sans(size: 12.5, color: gm.sub, height: 1.5)),
            CheckboxListTile(
              value: _checked,
              onChanged: (v) => setState(() => _checked = v ?? false),
              title: Text(l10n.photoFbConsent, style: GmText.sans(size: 13.5)),
              contentPadding: EdgeInsets.zero,
              controlAffinity: ListTileControlAffinity.leading,
            ),
            TextField(
              controller: _note,
              enabled: _checked,
              maxLength: 300,
              style: GmText.sans(size: 13),
              decoration: InputDecoration(
                hintText: l10n.photoFbNoteHint,
                hintStyle: GmText.sans(size: 13, color: gm.faint),
              ),
            ),
          ],
        ),
      ),
      actions: [
        TextButton(
          key: const Key('photoFbContinue'),
          onPressed: () => Navigator.of(context)
              .pop(PhotoFeedbackChoice(send: _checked, text: _note.text)),
          child: Text(l10n.photoFbContinue),
        ),
      ],
    );
  }
}
