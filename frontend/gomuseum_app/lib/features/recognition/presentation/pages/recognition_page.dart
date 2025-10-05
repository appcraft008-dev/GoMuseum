import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:image_picker/image_picker.dart';
import '../providers/recognition_provider.dart';
import '../widgets/recognition_result_widget.dart';

/// 识别页面
class RecognitionPage extends ConsumerWidget {
  const RecognitionPage({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final state = ref.watch(recognitionNotifierProvider);

    return Scaffold(
      appBar: AppBar(
        title: const Text('Artwork Recognition'),
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
              label: const Text('Take Photo'),
            ),
            const SizedBox(height: 16),

            // 从相册选择按钮
            ElevatedButton.icon(
              onPressed: () => _pickImageFromGallery(context, ref),
              icon: const Icon(Icons.photo_library),
              label: const Text('Choose from Gallery'),
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
    return switch (state) {
      RecognitionInitial() => const Center(
          child: Text(
            'Select an image to recognize artwork',
            textAlign: TextAlign.center,
            style: TextStyle(fontSize: 16, color: Colors.grey),
          ),
        ),
      RecognitionLoading() => const Center(
          child: CircularProgressIndicator(),
        ),
      RecognitionSuccess(:final result) =>
        RecognitionResultWidget(result: result),
      RecognitionError(:final message) => Center(
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              const Icon(Icons.error_outline, size: 64, color: Colors.red),
              const SizedBox(height: 16),
              Text(
                'Error: $message',
                textAlign: TextAlign.center,
                style: const TextStyle(color: Colors.red),
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
