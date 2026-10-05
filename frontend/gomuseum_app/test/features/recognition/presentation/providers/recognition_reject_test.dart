import 'dart:typed_data';

import 'package:cross_file/cross_file.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gomuseum_app/features/payment/presentation/providers/benefits_provider.dart';
import 'package:gomuseum_app/features/recognition/data/datasources/recognition_remote_datasource.dart';
import 'package:gomuseum_app/features/recognition/data/models/recognize_response.dart';
import 'package:gomuseum_app/features/recognition/presentation/providers/recognition_provider.dart';
import 'package:gomuseum_app/features/recognition/presentation/providers/recognition_providers.dart';

class _Ds implements RecognitionRemoteDataSource {
  final rejects = <(String, List<String>)>[];

  @override
  Future<RecognizeResponse> recognize({
    String? slug,
    required XFile image,
    required String language,
    String mode = 'artwork',
    String? deviceId,
  }) async =>
      RecognizeResponse.fromJson(const {
        'outcome': 'candidates',
        'phash': 'ph1',
        'candidates': [
          {'qid': 'Q1', 'museum': 'orsay', 'title': 'A'},
          {'qid': 'Q2', 'museum': 'orsay', 'title': 'B'},
        ],
      });

  @override
  Future<void> confirm({required String phash, required String qid}) async {}

  @override
  Future<void> reject(
          {required String phash, required List<String> qids}) async =>
      rejects.add((phash, qids));

  @override
  Future<Never> recognizeArtwork(XFile imageFile) async =>
      throw UnimplementedError();
}

void main() {
  test('「都不是」上报这组候选,并落未收录态', () async {
    final ds = _Ds();
    final c = ProviderContainer(overrides: [
      recognitionRemoteDataSourceProvider.overrideWithValue(ds),
      deviceIdProvider.overrideWith((ref) async => 'dev-1'),
    ]);
    addTearDown(c.dispose);
    final n = c.read(recognitionNotifierProvider.notifier);
    await n.recognize(
        image: XFile.fromData(Uint8List.fromList(const [0]), name: 'x.jpg'),
        language: 'en');
    expect(c.read(recognitionNotifierProvider), isA<RecognitionCandidates>());

    n.rejectCandidates();

    expect(c.read(recognitionNotifierProvider), isA<RecognitionUnrecognized>());
    expect(ds.rejects, hasLength(1));
    expect(ds.rejects.single.$1, 'ph1');
    expect(ds.rejects.single.$2, ['Q1', 'Q2']);
  });
}
