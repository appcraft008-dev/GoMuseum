import 'dart:typed_data';

import 'package:cross_file/cross_file.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gomuseum_app/core/error/exceptions.dart';
import 'package:gomuseum_app/features/payment/presentation/providers/benefits_provider.dart';
import 'package:gomuseum_app/features/recognition/data/datasources/recognition_remote_datasource.dart';
import 'package:gomuseum_app/features/recognition/data/models/recognize_response.dart';
import 'package:gomuseum_app/features/recognition/presentation/providers/recognition_provider.dart';
import 'package:gomuseum_app/features/recognition/presentation/providers/recognition_providers.dart';

/// 额度用尽必须与识别失败分开落态:相机页据此弹付费墙而不是"识别失败"。
class _ThrowingDs implements RecognitionRemoteDataSource {
  _ThrowingDs(this.error);
  final Object error;

  @override
  Future<RecognizeResponse> recognize({
    String? slug,
    required XFile image,
    required String language,
    String mode = 'artwork',
    String? deviceId,
  }) async =>
      throw error;

  @override
  Future<void> confirm({required String phash, required String qid}) async {}

  @override
  Future<Never> recognizeArtwork(XFile imageFile) async => throw error;
}

void main() {
  Future<RecognitionState> stateAfter(Object error) async {
    final container = ProviderContainer(overrides: [
      recognitionRemoteDataSourceProvider.overrideWithValue(_ThrowingDs(error)),
      deviceIdProvider.overrideWith((ref) async => 'dev-1'),
    ]);
    addTearDown(container.dispose);
    await container.read(recognitionNotifierProvider.notifier).recognize(
          image: XFile.fromData(Uint8List.fromList(const [0, 1]),
              name: 'x.jpg', mimeType: 'image/jpeg'),
          language: 'en',
        );
    return container.read(recognitionNotifierProvider);
  }

  test('402 lands in RecognitionQuotaExceeded (paywall, not failure)',
      () async {
    expect(await stateAfter(const QuotaExceededException()),
        isA<RecognitionQuotaExceeded>());
  });

  test('other errors still land in RecognitionError', () async {
    expect(await stateAfter(const ServerException('boom')),
        isA<RecognitionError>());
  });
}
