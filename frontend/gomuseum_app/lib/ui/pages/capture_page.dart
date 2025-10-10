import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:image_picker/image_picker.dart';
import '../../l10n/app_localizations.dart';
import '../../theme/tokens.dart';
import '../../features/recognition/presentation/providers/recognition_provider.dart';
import '../../features/recognition/presentation/widgets/recognition_result_widget.dart';

/// 拍照识别页面
class CapturePage extends ConsumerWidget {
  const CapturePage({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final state = ref.watch(recognitionNotifierProvider);
    final l10n = AppLocalizations.of(context)!;

    return Scaffold(
      appBar: AppBar(
        title: Text(l10n.artworkRecognition),
      ),
      body: Padding(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            // 拍照按钮
            ElevatedButton.icon(
              onPressed: () => _pickImageFromCamera(context, ref),
              icon: const Icon(Icons.camera_alt),
              label: Text(l10n.takePhoto),
              style: ElevatedButton.styleFrom(
                backgroundColor: const Color(GMColors.ctaRecognize),
                foregroundColor: Colors.black,
                padding: const EdgeInsets.symmetric(vertical: 16),
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(GMRadius.lg),
                ),
              ),
            ),
            const SizedBox(height: 16),

            // 从相册选择按钮
            ElevatedButton.icon(
              onPressed: () => _pickImageFromGallery(context, ref),
              icon: const Icon(Icons.photo_library),
              label: Text(l10n.chooseFromGallery),
              style: ElevatedButton.styleFrom(
                backgroundColor: const Color(GMColors.brandPrimary),
                foregroundColor: Colors.white,
                padding: const EdgeInsets.symmetric(vertical: 16),
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(GMRadius.lg),
                ),
              ),
            ),
            const SizedBox(height: 32),

            // 状态展示
            Expanded(
              child: _buildStateWidget(state, l10n),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildStateWidget(RecognitionState state, AppLocalizations l10n) {
    return switch (state) {
      RecognitionInitial() => Center(
          child: Text(
            l10n.selectImagePrompt,
            textAlign: TextAlign.center,
            style: const TextStyle(
              fontSize: 16,
              color: Color(GMColors.textSecondary),
            ),
          ),
        ),
      RecognitionLoading() => const Center(
          child: CircularProgressIndicator(
            color: Color(GMColors.brandPrimary),
          ),
        ),
      RecognitionSuccess(:final result) =>
        RecognitionResultWidget(result: result),
      RecognitionError(:final message) => Center(
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Icon(
                Icons.error_outline,
                size: 64,
                color: Color(GMColors.error),
              ),
              SizedBox(height: 16),
              Text(
                '${l10n.error}: $message',
                textAlign: TextAlign.center,
                style: TextStyle(
                  color: Color(GMColors.error),
                ),
              ),
            ],
          ),
        ),
    };
  }

  Future<void> _pickImageFromCamera(BuildContext context, WidgetRef ref) async {
    final picker = ImagePicker();
    final XFile? image = await picker.pickImage(source: ImageSource.camera);

    if (image != null) {
      if (context.mounted) {
        await ref
            .read(recognitionNotifierProvider.notifier)
            .recognizeArtwork(image);
      }
    }
  }

  Future<void> _pickImageFromGallery(
      BuildContext context, WidgetRef ref) async {
    final picker = ImagePicker();
    final XFile? image = await picker.pickImage(source: ImageSource.gallery);

    if (image != null) {
      if (context.mounted) {
        await ref
            .read(recognitionNotifierProvider.notifier)
            .recognizeArtwork(image);
      }
    }
  }
}
