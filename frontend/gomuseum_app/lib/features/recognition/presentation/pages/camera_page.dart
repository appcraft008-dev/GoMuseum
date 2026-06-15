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
        setState(() => _cameraError = '未找到可用相机');
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
      setState(() => _cameraError = e.description ?? '相机初始化失败');
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
    showModalBottomSheet<void>(
      context: context,
      backgroundColor: GmColors.bg,
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
            Text('展签检索',
                style: GmText.serif(size: 16.5, weight: FontWeight.w700)),
            const SizedBox(height: 6),
            Text(
              '禁拍照展区可输入展签编号、作品名或作者名',
              style: GmText.sans(size: 12, color: GmColors.sub),
            ),
            const SizedBox(height: 14),
            TextField(
              autofocus: true,
              style: GmText.sans(size: 13.5),
              decoration: InputDecoration(
                hintText: '如：INV 3692 / 在阿尔的卧室',
                hintStyle: GmText.sans(size: 13.5, color: GmColors.faint),
                filled: true,
                fillColor: GmColors.surface,
                enabledBorder: const OutlineInputBorder(
                  borderSide: BorderSide(color: GmColors.line),
                  borderRadius: BorderRadius.zero,
                ),
                focusedBorder: const OutlineInputBorder(
                  borderSide: BorderSide(color: GmColors.accent),
                  borderRadius: BorderRadius.zero,
                ),
              ),
              onSubmitted: (_) {
                Navigator.of(sheetContext).pop();
                ScaffoldMessenger.of(context).showSnackBar(
                  const SnackBar(content: Text('馆藏检索将在离线馆包接入后开放')),
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
    showModalBottomSheet<void>(
      context: context,
      backgroundColor: GmColors.bg,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(18)),
      ),
      builder: (sheetContext) => Padding(
        padding: const EdgeInsets.fromLTRB(22, 18, 22, 24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Text('免费识别次数已用尽',
                style: GmText.serif(size: 16.5, weight: FontWeight.w700)),
            const SizedBox(height: 8),
            Text(
              '升级后可继续畅听全馆讲解',
              style: GmText.sans(size: 12.5, color: GmColors.sub),
            ),
            const SizedBox(height: 16),
            GmTicketButton(
              label: '查看升级方案',
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
                      border: Border.all(color: GmColors.scanInk, width: 3),
                    ),
                    padding: const EdgeInsets.all(5),
                    child: const DecoratedBox(
                      decoration: BoxDecoration(
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
                            '不能拍照？输入展签编号',
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
    return GestureDetector(
      onTap: onTap,
      child: Container(
        width: 38,
        height: 38,
        decoration: BoxDecoration(
          color: active ? GmColors.accent : const Color(0x80171310),
          shape: BoxShape.circle,
        ),
        alignment: Alignment.center,
        child: GmIcon(icon, size: 19, color: GmColors.scanInk),
      ),
    );
  }

  List<Widget> _cornerBrackets() {
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
    return Container(
      width: double.infinity,
      decoration: const BoxDecoration(
        color: GmColors.bg,
        borderRadius: BorderRadius.vertical(top: Radius.circular(18)),
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
                  color: GmColors.line,
                  borderRadius: BorderRadius.circular(2),
                ),
              ),
            ),
            const SizedBox(height: 13),
            ...switch (state) {
              RecognitionLoading() => _loadingContent(),
              RecognitionSuccess() => _successContent(state),
              RecognitionError(:final message) => _errorContent(message),
              _ => const <Widget>[],
            },
          ],
        ),
      ),
    );
  }

  List<Widget> _loadingContent() {
    return [
      Row(
        children: [
          const SizedBox(
            width: 18,
            height: 18,
            child: CircularProgressIndicator(strokeWidth: 2),
          ),
          const SizedBox(width: 12),
          Text('正在识别…', style: GmText.serif(size: 16.5, weight: FontWeight.w700)),
        ],
      ),
      const SizedBox(height: 8),
      Text('AI 正在比对馆藏与公开艺术数据库',
          style: GmText.sans(size: 12, color: GmColors.sub)),
      const SizedBox(height: 10),
    ];
  }

  List<Widget> _successContent(RecognitionSuccess state) {
    final result = state.result;
    final confidence = (result.confidence * 100).round();
    return [
      Text('识别完成，请确认展品',
          style: GmText.serif(size: 16.5, weight: FontWeight.w700)),
      const SizedBox(height: 13),
      Container(
        padding: const EdgeInsets.all(11),
        decoration: BoxDecoration(
          color: GmColors.surface,
          border: Border.all(color: GmColors.accent, width: 1.5),
        ),
        child: Row(
          children: [
            SizedBox(
              width: 60,
              height: 60,
              child: _captured != null
                  ? Container(
                      decoration: BoxDecoration(
                        border: Border.all(color: GmColors.line),
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
                    style: GmText.sans(size: 12, color: GmColors.sub),
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
                      size: 18, weight: FontWeight.w700, color: GmColors.accentDeep),
                ),
                const SizedBox(height: 2),
                Text('置信度', style: GmText.sans(size: 10, color: GmColors.sub)),
              ],
            ),
          ],
        ),
      ),
      const SizedBox(height: 14),
      GmTicketButton(
        label: '确认，开始讲解',
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
            '都不是？搜索作品名或展签编号 →',
            style: GmText.sans(size: 12.5, color: GmColors.accent),
          ),
        ),
      ),
    ];
  }

  List<Widget> _errorContent(String message) {
    return [
      Text('识别失败', style: GmText.serif(size: 16.5, weight: FontWeight.w700)),
      const SizedBox(height: 6),
      Text(message, style: GmText.sans(size: 12, color: GmColors.sub)),
      const SizedBox(height: 14),
      GmTicketButton(label: '重新拍摄', icon: GmIcons.camera, onTap: _retake),
    ];
  }
}
