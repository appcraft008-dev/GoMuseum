import 'dart:async' hide TimeoutException;
import 'dart:typed_data';

import 'package:flutter/widgets.dart';

import 'package:cross_file/cross_file.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gomuseum_app/core/error/exceptions.dart';
import 'package:gomuseum_app/features/payment/presentation/providers/benefits_provider.dart';
import 'package:gomuseum_app/features/recognition/data/datasources/recognition_remote_datasource.dart';
import 'package:gomuseum_app/features/recognition/data/models/recognize_response.dart';
import 'package:gomuseum_app/features/recognition/presentation/providers/recognition_provider.dart';
import 'package:gomuseum_app/features/recognition/presentation/providers/recognition_providers.dart';

/// 按调用序依次抛错/返回;记录调用次数与发生顺序。
class _ScriptedDs implements RecognitionRemoteDataSource {
  _ScriptedDs(this.script, this.log);
  final List<Object> script; // Exception = 抛;RecognizeResponse = 返回
  final List<String> log;
  int calls = 0;

  @override
  Future<RecognizeResponse> recognize({
    String? slug,
    required XFile image,
    required String language,
    String mode = 'artwork',
    String? deviceId,
  }) async {
    final step = script[calls++];
    log.add('send');
    if (step is RecognizeResponse) return step;
    throw step;
  }

  @override
  Future<void> confirm({required String phash, required String qid}) async {}

  @override
  Future<void> reject(
      {required String phash, required List<String> qids}) async {}

  @override
  Future<Never> recognizeArtwork(XFile imageFile) async =>
      throw UnimplementedError();
}

final _unrecognized =
    RecognizeResponse.fromJson(const {'outcome': 'unrecognized'});

void main() {
  late List<String> log;

  Future<(RecognitionState, _ScriptedDs)> run(List<Object> script) async {
    final ds = _ScriptedDs(script, log);
    final container = ProviderContainer(overrides: [
      recognitionRemoteDataSourceProvider.overrideWithValue(ds),
      deviceIdProvider.overrideWith((ref) async => 'dev-1'),
      foregroundWaiterProvider.overrideWithValue(() async => log.add('fg')),
    ]);
    addTearDown(container.dispose);
    await container.read(recognitionNotifierProvider.notifier).recognize(
          image: XFile.fromData(Uint8List.fromList(const [0, 1]),
              name: 'x.jpg', mimeType: 'image/jpeg'),
          language: 'en',
        );
    return (container.read(recognitionNotifierProvider), ds);
  }

  setUp(() => log = []);

  test('timeout then success → result, sent twice', () async {
    final (st, ds) = await run([const TimeoutException(), _unrecognized]);
    expect(st, isA<RecognitionUnrecognized>());
    expect(ds.calls, 2);
  });

  test('network error then success → result', () async {
    final (st, ds) = await run([const NetworkException(), _unrecognized]);
    expect(st, isA<RecognitionUnrecognized>());
    expect(ds.calls, 2);
  });

  test('transient twice → error, exactly two sends (only one retry)', () async {
    final (st, ds) = await run(
        [const NetworkException(), const NetworkException(), _unrecognized]);
    expect(st, isA<RecognitionError>());
    expect(ds.calls, 2);
  });

  test('waits for foreground before resending', () async {
    await run([const TimeoutException(), _unrecognized]);
    expect(log, ['send', 'fg', 'send']);
  });

  test('server error (500) is not retried', () async {
    final (st, ds) = await run([const ServerException('boom'), _unrecognized]);
    expect(st, isA<RecognitionError>());
    expect(ds.calls, 1);
  });

  test('402 is not retried', () async {
    final (st, ds) = await run([const QuotaExceededException(), _unrecognized]);
    expect(st, isA<RecognitionQuotaExceeded>());
    expect(ds.calls, 1);
  });

  testWidgets('untilAppResumed: completes immediately when resumed',
      (tester) async {
    tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.resumed);
    var done = false;
    unawaited(untilAppResumed().then((_) => done = true));
    await tester.pump();
    expect(done, isTrue);
  });

  testWidgets('untilAppResumed: waits while paused, completes on resume',
      (tester) async {
    tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.inactive);
    tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.hidden);
    tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.paused);
    var done = false;
    unawaited(untilAppResumed().then((_) => done = true));
    await tester.pump();
    expect(done, isFalse);
    tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.hidden);
    tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.inactive);
    tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.resumed);
    await tester.pump();
    expect(done, isTrue);
  });
}
