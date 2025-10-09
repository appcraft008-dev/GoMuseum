import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:image_picker/image_picker.dart';
import '../../../../l10n/app_localizations.dart';
import '../providers/recognition_provider.dart';
import '../widgets/recognition_result_widget.dart';

/// 识别页面
class RecognitionPage extends ConsumerWidget {
  const RecognitionPage({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final state = ref.watch(recognitionNotifierProvider);
    final l10n = AppLocalizations.of(context)!;

    return Scaffold(
      appBar: AppBar(
        title: Text(l10n.artworkRecognition),
        actions: [
          IconButton(
            icon: const Icon(Icons.settings),
            tooltip: l10n.settings,
            onPressed: () {
              Navigator.pushNamed(context, '/settings');
            },
          ),
        ],
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
            ),
            const SizedBox(height: 16),

            // 从相册选择按钮
            ElevatedButton.icon(
              onPressed: () => _pickImageFromGallery(context, ref),
              icon: const Icon(Icons.photo_library),
              label: Text(l10n.chooseFromGallery),
            ),
            const SizedBox(height: 32),

            // 状态展示
            Expanded(
              child: _buildStateWidget(state),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildStateWidget(RecognitionState state) {
    // We can't use BuildContext directly in this method, so we'll need to refactor
    return switch (state) {
      RecognitionInitial() => Center(
          child: Builder(
            builder: (context) => Text(
              AppLocalizations.of(context)!.selectImagePrompt,
              textAlign: TextAlign.center,
              style: const TextStyle(fontSize: 16, color: Colors.grey),
            ),
          ),
        ),
      RecognitionLoading() => const Center(
          child: CircularProgressIndicator(),
        ),
      RecognitionSuccess(:final result) =>
        RecognitionResultWidget(result: result),
      RecognitionError(:final message) => Center(
          child: Builder(
            builder: (context) => Column(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                const Icon(Icons.error_outline, size: 64, color: Colors.red),
                const SizedBox(height: 16),
                Text(
                  '${AppLocalizations.of(context)!.error}: $message',
                  textAlign: TextAlign.center,
                  style: const TextStyle(color: Colors.red),
                ),
              ],
            ),
          ),
        ),
    };
  }

  Future<void> _pickImageFromCamera(BuildContext context, WidgetRef ref) async {
    final picker = ImagePicker();
    final XFile? image = await picker.pickImage(source: ImageSource.camera);

    if (image != null) {
      if (context.mounted) {
        // 直接传递 XFile，不需要转换为 File
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
        // 直接传递 XFile，不需要转换为 File
        await ref
            .read(recognitionNotifierProvider.notifier)
            .recognizeArtwork(image);
      }
    }
  }
}
