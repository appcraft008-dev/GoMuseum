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
  _Ds(this.resp);
  final Map<String, dynamic> resp;
  final confirms = <List<String?>>[];

  @override
  Future<RecognizeResponse> recognize({
    String? slug,
    required XFile image,
    required String language,
    String mode = 'artwork',
    String? deviceId,
  }) async =>
      RecognizeResponse.fromJson(resp);

  @override
  Future<void> confirm(
          {required String phash, required String qid, String? source}) async =>
      confirms.add([phash, qid, source]);

  @override
  Future<void> reject(
      {required String phash, required List<String> qids}) async {}

  @override
  Future<Never> recognizeArtwork(XFile imageFile) async =>
      throw UnimplementedError();
}

Future<(ProviderContainer, _Ds)> _run(Map<String, dynamic> resp) async {
  final ds = _Ds(resp);
  final c = ProviderContainer(overrides: [
    recognitionRemoteDataSourceProvider.overrideWithValue(ds),
    deviceIdProvider.overrideWith((ref) async => 'dev-1'),
  ]);
  await c.read(recognitionNotifierProvider.notifier).recognize(
      image: XFile.fromData(Uint8List.fromList(const [0]), name: 'x.jpg'),
      language: 'en');
  return (c, ds);
}

void main() {
  test('unrecognized state carries phash', () async {
    final (c, _) =
        await _run(const {'outcome': 'unrecognized', 'phash': 'ph-u'});
    addTearDown(c.dispose);
    final st = c.read(recognitionNotifierProvider);
    expect(st, isA<RecognitionUnrecognized>());
    expect((st as RecognitionUnrecognized).phash, 'ph-u');
  });

  test('「都不是」后的未收录态也带 phash', () async {
    final (c, _) = await _run(const {
      'outcome': 'candidates',
      'phash': 'ph-c',
      'candidates': [
        {'qid': 'Q1', 'museum': 'orsay', 'title': 'A'}
      ],
    });
    addTearDown(c.dispose);
    c.read(recognitionNotifierProvider.notifier).rejectCandidates();
    expect(
        (c.read(recognitionNotifierProvider) as RecognitionUnrecognized).phash,
        'ph-c');
  });

  test('confirm from search sends source=search with unrecognized phash',
      () async {
    final (c, ds) =
        await _run(const {'outcome': 'unrecognized', 'phash': 'ph-u'});
    addTearDown(c.dispose);
    await c
        .read(recognitionNotifierProvider.notifier)
        .confirmRecognition('Q9', fromSearch: true);
    expect(ds.confirms, [
      ['ph-u', 'Q9', 'search']
    ]);
  });

  test('confirm from search without phash is a no-op (old backend)', () async {
    final (c, ds) = await _run(const {'outcome': 'unrecognized'});
    addTearDown(c.dispose);
    await c
        .read(recognitionNotifierProvider.notifier)
        .confirmRecognition('Q9', fromSearch: true);
    expect(ds.confirms, isEmpty);
  });

  test('phashOverride wins (label path confirms the ARTWORK photo)', () async {
    final (c, ds) =
        await _run(const {'outcome': 'unrecognized', 'phash': 'ph-label'});
    addTearDown(c.dispose);
    await c.read(recognitionNotifierProvider.notifier).confirmRecognition('Q9',
        fromSearch: true, phashOverride: 'ph-artwork');
    expect(ds.confirms, [
      ['ph-artwork', 'Q9', 'search']
    ]);
  });
}
