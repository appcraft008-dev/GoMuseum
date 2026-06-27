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
import 'package:gomuseum_app/features/guide/presentation/pages/guide_page.dart';
import 'package:gomuseum_app/features/payment/presentation/providers/benefits_provider.dart';
import 'package:gomuseum_app/features/recognition/presentation/providers/recognition_provider.dart';
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

    final benefits = ref.read(benefitsStateProvider.notifier);
    if (!benefits.hasRecognitionAccess) {
      _showQuotaExhaustedSheet();
      return;
    }

    final shot = await controller.takePicture();
    setState(() => _captured = shot);
    await ref.read(recognitionNotifierProvider.notifier).recognizeArtwork(shot);
    // 识别成功才扣减免费额度
    if (ref.read(recognitionNotifierProvider) is RecognitionSuccess) {
      await benefits.consumeQuota();
    }
  }

  void _retake() {
    setState(() => _captured = null);
    ref.read(recognitionNotifierProvider.notifier).resetState();
  }

  void _confirm(RecognitionSuccess success) {
    context.pushReplacement(
      '/guide',
      extra: GuideArgs(result: success.result, imagePath: _captured?.path),
    );
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
        // 底部：快门 + 展签检索入口
        if (state is RecognitionInitial)
          Positioned(
            left: 0,
            right: 0,
            bottom: 16,
            child: Column(
              children: [
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
              RecognitionSuccess() => _successContent(gm, state),
              RecognitionError(:final message) => _errorContent(gm, message),
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

  List<Widget> _successContent(GmPalette gm, RecognitionSuccess state) {
    final l10n = AppLocalizations.of(context)!;
    final result = state.result;
    final confidence = (result.confidence * 100).round();
    return [
      Text(l10n.camConfirmPrompt,
          style: GmText.serif(size: 16.5, weight: FontWeight.w700)),
      const SizedBox(height: 13),
      Container(
        padding: const EdgeInsets.all(11),
        decoration: BoxDecoration(
          color: gm.surface,
          border: Border.all(color: gm.accent, width: 1.5),
        ),
        child: Row(
          children: [
            SizedBox(
              width: 60,
              height: 60,
              child: _captured != null
                  ? Container(
                      decoration: BoxDecoration(
                        border: Border.all(color: gm.line),
                        image: DecorationImage(
                          image: FileImage(File(_captured!.path)),
                          fit: BoxFit.cover,
                        ),
                      ),
                    )
                  : const GmInnerImage(image: null, height: 60, width: 60),
            ),
            const SizedBox(width: 14),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    result.artworkName,
                    style: GmText.serif(size: 16.5, weight: FontWeight.w600),
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                  ),
                  const SizedBox(height: 4),
                  Text(
                    '${result.artist} · ${result.period}',
                    style: GmText.sans(size: 12, color: gm.sub),
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                  ),
                ],
              ),
            ),
            const SizedBox(width: 8),
            Column(
              children: [
                Text(
                  '$confidence%',
                  style: GmText.serif(
                      size: 18, weight: FontWeight.w700, color: gm.accentDeep),
                ),
                const SizedBox(height: 2),
                Text(l10n.camConfidence,
                    style: GmText.sans(size: 10, color: gm.sub)),
              ],
            ),
          ],
        ),
      ),
      const SizedBox(height: 14),
      GmTicketButton(
        label: l10n.camConfirmStart,
        icon: GmIcons.headphones,
        onTap: () => _confirm(state),
      ),
      const SizedBox(height: 11),
      Center(
        child: GestureDetector(
          onTap: () {
            _retake();
            _showTagSearchSheet();
          },
          child: Text(
            l10n.camNoneSearch,
            style: GmText.sans(size: 12.5, color: gm.accent),
          ),
        ),
      ),
    ];
  }

  List<Widget> _errorContent(GmPalette gm, String message) {
    final l10n = AppLocalizations.of(context)!;
    return [
      Text(l10n.camRecognizeFailed,
          style: GmText.serif(size: 16.5, weight: FontWeight.w700)),
      const SizedBox(height: 6),
      Text(message, style: GmText.sans(size: 12, color: gm.sub)),
      const SizedBox(height: 14),
      GmTicketButton(
          label: l10n.camRetake, icon: GmIcons.camera, onTap: _retake),
    ];
  }
}
