/// GoMuseum 识别页 — 暖纸手册定稿（FinalScan）
///
/// 深色取景器（四角框 + 关闭/闪光 + 「不能拍照」入口）+ 拍照后
/// 暖纸候选确认面板（装裱卡 + 置信度 + 门票式确认按钮）。
library;

import 'dart:io';

import 'package:camera/camera.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:image_picker/image_picker.dart';
import 'package:gomuseum_app/core/network/image_request.dart';
import 'package:gomuseum_app/features/guide/presentation/pages/guide_page.dart';
import 'package:gomuseum_app/features/payment/presentation/providers/benefits_provider.dart';
import 'package:gomuseum_app/features/recognition/data/models/recognize_response.dart';
import 'package:gomuseum_app/features/recognition/presentation/providers/recognition_provider.dart';
import 'package:gomuseum_app/features/settings/presentation/providers/language_provider.dart';
import 'package:gomuseum_app/l10n/app_localizations.dart';
import 'package:gomuseum_app/theme/gm_palette.dart';
import 'package:gomuseum_app/theme/gm_theme_x.dart';
import 'package:gomuseum_app/ui/gm/gm.dart';

class CameraPage extends ConsumerStatefulWidget {
  const CameraPage({super.key});

  @override
  ConsumerState<CameraPage> createState() => _CameraPageState();
}

class _CameraPageState extends ConsumerState<CameraPage>
    with WidgetsBindingObserver {
  CameraController? _controller;
  String? _cameraError;
  bool _flashOn = false;
  XFile? _captured;

  /// 引导拍墙签模式：下一张照片以 `mode=label` 提交。
  bool _labelMode = false;

  // ponytail: 现阶段固定 orsay;接入馆上下文后从当前馆 slug 取。
  static const String _slug = 'orsay';

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    _initCamera();
    // 进入识别页时重置上一次识别状态
    WidgetsBinding.instance.addPostFrameCallback((_) {
      ref.read(recognitionNotifierProvider.notifier).resetState();
    });
  }

  Future<void> _initCamera() async {
    try {
      final cameras = await availableCameras();
      if (cameras.isEmpty) {
        setState(
            () => _cameraError = AppLocalizations.of(context)!.camNoCamera);
        return;
      }
      final back = cameras.firstWhere(
        (c) => c.lensDirection == CameraLensDirection.back,
        orElse: () => cameras.first,
      );
      final controller = CameraController(
        back,
        ResolutionPreset.high,
        enableAudio: false,
      );
      await controller.initialize();
      if (!mounted) {
        await controller.dispose();
        return;
      }
      setState(() => _controller = controller);
    } on CameraException catch (e) {
      setState(() => _cameraError =
          e.description ?? AppLocalizations.of(context)!.camInitFailed);
    }
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    final controller = _controller;
    if (controller == null || !controller.value.isInitialized) return;
    if (state == AppLifecycleState.inactive) {
      controller.dispose();
      _controller = null;
    } else if (state == AppLifecycleState.resumed) {
      _initCamera();
    }
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    _controller?.dispose();
    super.dispose();
  }

  Future<void> _toggleFlash() async {
    final controller = _controller;
    if (controller == null) return;
    final next = !_flashOn;
    await controller.setFlashMode(next ? FlashMode.torch : FlashMode.off);
    setState(() => _flashOn = next);
  }

  Future<void> _shoot() async {
    final controller = _controller;
    if (controller == null || controller.value.isTakingPicture) return;
    if (!ref.read(benefitsStateProvider.notifier).hasRecognitionAccess) {
      _showQuotaExhaustedSheet();
      return;
    }
    final shot = await controller.takePicture();
    await _recognizeImage(shot);
  }

  /// 从图库选图上传识别（无相机拍摄，走同一识别路由）。
  Future<void> _pickFromGallery() async {
    if (!ref.read(benefitsStateProvider.notifier).hasRecognitionAccess) {
      _showQuotaExhaustedSheet();
      return;
    }
    final picked = await ImagePicker().pickImage(source: ImageSource.gallery);
    if (picked == null || !mounted) return;
    await _recognizeImage(picked);
  }

  /// 拍摄/选图共用：识别 + 三档路由 + 命中扣额度。
  Future<void> _recognizeImage(XFile shot) async {
    setState(() => _captured = shot);
    final benefits = ref.read(benefitsStateProvider.notifier);
    final lang = ref.read(languageProvider).languageCode;
    final mode = _labelMode ? 'label' : 'artwork';
    await ref
        .read(recognitionNotifierProvider.notifier)
        .recognize(slug: _slug, image: shot, language: lang, mode: mode);
    if (!mounted) return;
    final st = ref.read(recognitionNotifierProvider);
    // 得到有用结果（命中/候选）才扣额度；未收录/错误不扣，不惩罚"没帮上忙"。
    if (st is RecognitionMatched || st is RecognitionCandidates) {
      await benefits.consumeQuota();
    }
    if (st is RecognitionMatched && mounted) {
      _goGuide(st.slug, st.match.qid);
    }
  }

  void _retake() {
    setState(() {
      _captured = null;
      _labelMode = false;
    });
    ref.read(recognitionNotifierProvider.notifier).resetState();
  }

  /// 进入引导拍墙签：回取景器，下一张以 `mode=label` 提交。
  void _startLabelCapture() {
    setState(() {
      _captured = null;
      _labelMode = true;
    });
    ref.read(recognitionNotifierProvider.notifier).resetState();
  }

  void _goGuide(String slug, String qid) {
    context.pushReplacement('/guide', extra: GuideArgs(slug: slug, qid: qid));
  }

  void _showTagSearchSheet() {
    final gm = context.gm;
    final l10n = AppLocalizations.of(context)!;
    showModalBottomSheet<void>(
      context: context,
      backgroundColor: gm.bg,
      isScrollControlled: true,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(18)),
      ),
      builder: (sheetContext) => Padding(
        padding: EdgeInsets.fromLTRB(
            22, 18, 22, 18 + MediaQuery.of(sheetContext).viewInsets.bottom),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(l10n.camTagSearch,
                style: GmText.serif(size: 16.5, weight: FontWeight.w700)),
            const SizedBox(height: 6),
            Text(
              l10n.camTagHint,
              style: GmText.sans(size: 12, color: gm.sub),
            ),
            const SizedBox(height: 14),
            TextField(
              autofocus: true,
              style: GmText.sans(size: 13.5),
              decoration: InputDecoration(
                hintText: l10n.camTagExample,
                hintStyle: GmText.sans(size: 13.5, color: gm.faint),
                filled: true,
                fillColor: gm.surface,
                enabledBorder: OutlineInputBorder(
                  borderSide: BorderSide(color: gm.line),
                  borderRadius: BorderRadius.zero,
                ),
                focusedBorder: OutlineInputBorder(
                  borderSide: BorderSide(color: gm.accent),
                  borderRadius: BorderRadius.zero,
                ),
              ),
              onSubmitted: (_) {
                Navigator.of(sheetContext).pop();
                ScaffoldMessenger.of(context).showSnackBar(
                  SnackBar(content: Text(l10n.camPackComingSoon)),
                );
              },
            ),
            const SizedBox(height: 14),
          ],
        ),
      ),
    );
  }

  void _showQuotaExhaustedSheet() {
    final gm = context.gm;
    final l10n = AppLocalizations.of(context)!;
    showModalBottomSheet<void>(
      context: context,
      backgroundColor: gm.bg,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(18)),
      ),
      builder: (sheetContext) => Padding(
        padding: const EdgeInsets.fromLTRB(22, 18, 22, 24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Text(l10n.camQuotaUsedUp,
                style: GmText.serif(size: 16.5, weight: FontWeight.w700)),
            const SizedBox(height: 8),
            Text(
              l10n.camUpgradeHint,
              style: GmText.sans(size: 12.5, color: gm.sub),
            ),
            const SizedBox(height: 16),
            GmTicketButton(
              label: l10n.camViewUpgrade,
              icon: GmIcons.ticket,
              onTap: () {
                Navigator.of(sheetContext).pop();
                context.push('/benefits');
              },
            ),
          ],
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(recognitionNotifierProvider);

    return Scaffold(
      // 取景器背景使用固定深色，非主题色
      backgroundColor: GmColors.scanBg,
      body: Column(
        children: [
          Expanded(child: _viewfinder(state)),
          if (state is! RecognitionInitial) _bottomPanel(state),
        ],
      ),
    );
  }

  Widget _viewfinder(RecognitionState state) {
    return Stack(
      fit: StackFit.expand,
      children: [
        if (_captured != null)
          Image.file(File(_captured!.path), fit: BoxFit.cover)
        else if (_controller != null && _controller!.value.isInitialized)
          CameraPreview(_controller!)
        else
          Center(
            child: _cameraError != null
                ? Padding(
                    padding: const EdgeInsets.all(32),
                    child: Text(
                      _cameraError!,
                      textAlign: TextAlign.center,
                      // 取景器文字使用固定浅色
                      style: GmText.sans(size: 13, color: GmColors.scanInk),
                    ),
                  )
                : const CircularProgressIndicator(color: GmColors.scanInk),
          ),
        // 轻微暗角
        const ColoredBox(color: Color(0x2E171310)),
        // 顶部：关闭 / 闪光
        SafeArea(
          child: Padding(
            padding: const EdgeInsets.fromLTRB(16, 12, 16, 0),
            child: Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                _roundButton(GmIcons.close, () => context.pop()),
                _roundButton(GmIcons.flash, _toggleFlash, active: _flashOn),
              ],
            ),
          ),
        ),
        // 四角取景框
        ..._cornerBrackets(),
        // 引导拍墙签模式提示
        if (state is RecognitionInitial && _labelMode)
          Positioned(
            left: 24,
            right: 24,
            top: 76,
            child: Center(
              child: Container(
                padding:
                    const EdgeInsets.symmetric(horizontal: 14, vertical: 7),
                decoration: BoxDecoration(
                  color: const Color(0x8C171310),
                  borderRadius: BorderRadius.circular(999),
                ),
                child: Text(
                  AppLocalizations.of(context)!.recViewfinderLabelHint,
                  textAlign: TextAlign.center,
                  style: GmText.sans(size: 12.5, color: GmColors.scanInk),
                ),
              ),
            ),
          ),
        // 底部：快门 + 展签检索入口
        if (state is RecognitionInitial)
          Positioned(
            left: 0,
            right: 0,
            bottom: 16,
            child: Column(
              children: [
                Row(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    // 从图库上传
                    _roundButton(GmIcons.photo, _pickFromGallery),
                    const SizedBox(width: 36),
                    GestureDetector(
                      onTap: _shoot,
                      child: Container(
                        width: 68,
                        height: 68,
                        decoration: BoxDecoration(
                          shape: BoxShape.circle,
                          // 取景框快门使用固定浅色描边
                          border: Border.all(color: GmColors.scanInk, width: 3),
                        ),
                        padding: const EdgeInsets.all(5),
                        child: const DecoratedBox(
                          decoration: BoxDecoration(
                            // 取景框快门内圆使用固定浅色
                            color: GmColors.scanInk,
                            shape: BoxShape.circle,
                          ),
                        ),
                      ),
                    ),
                    const SizedBox(width: 36),
                    // 占位：保持快门视觉居中
                    const SizedBox(width: 38),
                  ],
                ),
                const SizedBox(height: 14),
                Center(
                  child: GestureDetector(
                    onTap: _showTagSearchSheet,
                    child: Container(
                      padding: const EdgeInsets.symmetric(
                          horizontal: 16, vertical: 8),
                      decoration: BoxDecoration(
                        color: const Color(0x8C171310),
                        borderRadius: BorderRadius.circular(999),
                      ),
                      child: Row(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          const GmIcon(GmIcons.search,
                              size: 15, color: GmColors.scanInk),
                          const SizedBox(width: 7),
                          Text(
                            AppLocalizations.of(context)!.camCantPhoto,
                            style: GmText.sans(
                                size: 12.5, color: GmColors.scanInk),
                          ),
                        ],
                      ),
                    ),
                  ),
                ),
              ],
            ),
          ),
      ],
    );
  }

  Widget _roundButton(GmIcons icon, VoidCallback onTap, {bool active = false}) {
    // active 时使用主题 accent，inactive 时用半透明深色（固定取景器色）
    final color = active ? context.gm.accent : const Color(0x80171310);
    return GestureDetector(
      onTap: onTap,
      child: Container(
        width: 38,
        height: 38,
        decoration: BoxDecoration(
          color: color,
          shape: BoxShape.circle,
        ),
        alignment: Alignment.center,
        child: GmIcon(icon, size: 19, color: GmColors.scanInk),
      ),
    );
  }

  List<Widget> _cornerBrackets() {
    // 四角框线使用固定取景器浅色，不随主题切换
    const side = BorderSide(color: GmColors.scanInk, width: 2.5);
    Widget bracket({
      double? top,
      double? left,
      double? right,
      double? bottom,
      bool bt = false,
      bool bb = false,
      bool bl = false,
      bool br = false,
    }) {
      return Positioned(
        top: top,
        left: left,
        right: right,
        bottom: bottom,
        child: Container(
          width: 30,
          height: 30,
          decoration: BoxDecoration(
            border: Border(
              top: bt ? side : BorderSide.none,
              bottom: bb ? side : BorderSide.none,
              left: bl ? side : BorderSide.none,
              right: br ? side : BorderSide.none,
            ),
          ),
        ),
      );
    }

    return [
      bracket(top: 110, left: 40, bt: true, bl: true),
      bracket(top: 110, right: 40, bt: true, br: true),
      bracket(bottom: 140, left: 40, bb: true, bl: true),
      bracket(bottom: 140, right: 40, bb: true, br: true),
    ];
  }

  Widget _bottomPanel(RecognitionState state) {
    final gm = context.gm;
    return Container(
      width: double.infinity,
      decoration: BoxDecoration(
        color: gm.bg,
        borderRadius: const BorderRadius.vertical(top: Radius.circular(18)),
      ),
      padding: const EdgeInsets.fromLTRB(22, 10, 22, 18),
      child: SafeArea(
        top: false,
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Center(
              child: Container(
                width: 36,
                height: 4,
                decoration: BoxDecoration(
                  color: gm.line,
                  borderRadius: BorderRadius.circular(2),
                ),
              ),
            ),
            const SizedBox(height: 13),
            ...switch (state) {
              RecognitionLoading() => _loadingContent(gm),
              RecognitionCandidates() => _candidatesContent(gm, state),
              RecognitionUnrecognized() => _unrecognizedContent(gm, state),
              RecognitionError() => _errorContent(gm),
              _ => const <Widget>[],
            },
          ],
        ),
      ),
    );
  }

  List<Widget> _loadingContent(GmPalette gm) {
    final l10n = AppLocalizations.of(context)!;
    return [
      Row(
        children: [
          const SizedBox(
            width: 18,
            height: 18,
            child: CircularProgressIndicator(strokeWidth: 2),
          ),
          const SizedBox(width: 12),
          Text(l10n.camRecognizing,
              style: GmText.serif(size: 16.5, weight: FontWeight.w700)),
        ],
      ),
      const SizedBox(height: 8),
      Text(l10n.camComparing, style: GmText.sans(size: 12, color: gm.sub)),
      const SizedBox(height: 10),
    ];
  }

  /// 候选确认卡「是这件吗？」——点选跳该 qid 详情，都不是走未收录。
  List<Widget> _candidatesContent(GmPalette gm, RecognitionCandidates state) {
    final l10n = AppLocalizations.of(context)!;
    return [
      Text(l10n.recCandidatesTitle,
          style: GmText.serif(size: 16.5, weight: FontWeight.w700)),
      const SizedBox(height: 12),
      for (final c in state.candidates) ...[
        _candidateRow(gm, c, state.slug),
        const SizedBox(height: 8),
      ],
      const SizedBox(height: 4),
      Center(
        child: GestureDetector(
          onTap: () =>
              ref.read(recognitionNotifierProvider.notifier).rejectCandidates(),
          child: Text(l10n.recNoneOfThese,
              style: GmText.sans(size: 12.5, color: gm.accent)),
        ),
      ),
    ];
  }

  Widget _candidateRow(GmPalette gm, RecognizedItem c, String slug) {
    // ponytail: 点选=一条"照片→确认QID"标注(喂后端二期 CLIP 校准);
    // 埋点接口 P2 提供,现只保证跳转畅通。
    return GestureDetector(
      onTap: () => _goGuide(slug, c.qid),
      behavior: HitTestBehavior.opaque,
      child: Container(
        padding: const EdgeInsets.all(9),
        decoration: BoxDecoration(
          color: gm.surface,
          border: Border.all(color: gm.line),
        ),
        child: Row(
          children: [
            SizedBox(
              width: 52,
              height: 52,
              child: c.thumbnail != null
                  ? Image.network(sizedImageUrl(c.thumbnail!, 200),
                      fit: BoxFit.cover,
                      headers: kImageRequestHeaders,
                      errorBuilder: (_, __, ___) => ColoredBox(
                          color: gm.chipBg,
                          child: Center(
                              child: GmIcon(GmIcons.photo,
                                  size: 20, color: gm.faint))))
                  : ColoredBox(color: gm.chipBg),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(c.title,
                      style: GmText.serif(size: 14.5, weight: FontWeight.w600),
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis),
                  const SizedBox(height: 3),
                  Text(c.artist,
                      style: GmText.sans(size: 12, color: gm.sub),
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis),
                ],
              ),
            ),
            const SizedBox(width: 6),
            GmIcon(GmIcons.chevR, size: 16, color: gm.faint),
          ],
        ),
      ),
    );
  }

  /// 未收录卡——绝不显示 AI 猜测的名字（契约 R1）。
  /// 有 label_text：诚实告知已记需求；无：引导拍墙签。
  List<Widget> _unrecognizedContent(
      GmPalette gm, RecognitionUnrecognized state) {
    final l10n = AppLocalizations.of(context)!;
    final label = state.labelText;
    if (label != null) {
      return [
        Text(l10n.recLabelSeen(label),
            style: GmText.sans(size: 13, height: 1.5)),
        const SizedBox(height: 16),
        Center(
          child: GestureDetector(
            onTap: _retake,
            child: Text(l10n.camRetake,
                style: GmText.sans(size: 12.5, color: gm.accent)),
          ),
        ),
      ];
    }
    return [
      Text(l10n.recNotRecognized,
          style: GmText.serif(size: 16.5, weight: FontWeight.w700)),
      const SizedBox(height: 14),
      GmTicketButton(
        label: l10n.recShootLabelBtn,
        icon: GmIcons.camera,
        onTap: _startLabelCapture,
      ),
      const SizedBox(height: 8),
      Text(l10n.recShootLabelHint,
          textAlign: TextAlign.center,
          style: GmText.sans(size: 11.5, color: gm.sub)),
      const SizedBox(height: 12),
      Center(
        child: GestureDetector(
          onTap: _retake,
          child: Text(l10n.camRetake,
              style: GmText.sans(size: 12.5, color: gm.accent)),
        ),
      ),
    ];
  }

  List<Widget> _errorContent(GmPalette gm) {
    final l10n = AppLocalizations.of(context)!;
    return [
      Text(l10n.camRecognizeFailed,
          style: GmText.serif(size: 16.5, weight: FontWeight.w700)),
      const SizedBox(height: 6),
      Text(l10n.camComparing, style: GmText.sans(size: 12, color: gm.sub)),
      const SizedBox(height: 14),
      GmTicketButton(
          label: l10n.camRetake, icon: GmIcons.camera, onTap: _retake),
    ];
  }
}
