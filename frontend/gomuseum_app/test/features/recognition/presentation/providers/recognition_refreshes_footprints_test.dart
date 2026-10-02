/// 识别命中 / 候选点选后,足迹列表必须重拉 —— 足迹 tab 与首页「继续游览」共用这份
/// 常驻缓存,不刷就一直停在打开 App 那一刻(2026-10-02 真机:连拍几十件两处都看不到)。
library;

import 'dart:async';
import 'dart:typed_data';

import 'package:cross_file/cross_file.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gomuseum_app/features/history/data/datasources/history_remote_datasource.dart';
import 'package:gomuseum_app/features/history/data/models/history_item_model.dart';
import 'package:gomuseum_app/features/history/presentation/providers/history_providers.dart';
import 'package:gomuseum_app/features/payment/domain/entities/user_benefits.dart';
import 'package:gomuseum_app/features/payment/presentation/providers/benefits_provider.dart';
import 'package:gomuseum_app/features/recognition/data/datasources/recognition_remote_datasource.dart';
import 'package:gomuseum_app/features/recognition/data/models/recognize_response.dart';
import 'package:gomuseum_app/features/recognition/presentation/providers/recognition_provider.dart';
import 'package:gomuseum_app/features/recognition/presentation/providers/recognition_providers.dart';
import 'package:gomuseum_app/features/settings/presentation/providers/language_provider.dart';

class _Ds implements RecognitionRemoteDataSource {
  _Ds(this.json);
  final Map<String, dynamic> json;

  @override
  Future<RecognizeResponse> recognize({
    String? slug,
    required XFile image,
    required String language,
    String mode = 'artwork',
    String? deviceId,
  }) async =>
      RecognizeResponse.fromJson(json);

  @override
  Future<void> confirm({required String phash, required String qid}) async {}

  @override
  Future<Never> recognizeArtwork(XFile imageFile) async =>
      throw UnimplementedError();
}

class _CountingHistory implements HistoryRemoteDataSource {
  int fetches = 0;

  @override
  Future<List<HistoryItemModel>> getRecentHistory({
    int limit = 20,
    int offset = 0,
    int? days,
    String? language,
  }) async {
    fetches++;
    return [];
  }

  @override
  Future<List<HistoryItemModel>> searchHistory({
    required String query,
    int limit = 20,
    String? language,
  }) async =>
      [];

  @override
  Future<Map<String, dynamic>> getHistoryStats({int days = 30}) async => {};

  @override
  Future<void> deleteHistoryItem(String id) async {}
}

class _StubBenefits extends BenefitsState {
  @override
  FutureOr<UserBenefits> build() => UserBenefits.none();

  @override
  Future<void> refresh() async {}
}

const _item = {'qid': 'Q12418', 'title': 'Mona Lisa', 'museum': 'louvre'};

Future<(ProviderContainer, _CountingHistory)> _setup(
    Map<String, dynamic> resp) async {
  final history = _CountingHistory();
  final c = ProviderContainer(overrides: [
    recognitionRemoteDataSourceProvider.overrideWithValue(_Ds(resp)),
    deviceIdProvider.overrideWith((ref) async => 'dev-1'),
    historyRemoteDataSourceProvider.overrideWithValue(history),
    resolvedLocaleProvider.overrideWithValue(const Locale('zh')),
    benefitsStateProvider.overrideWith(() => _StubBenefits()),
  ]);
  addTearDown(c.dispose);
  // 首页常驻 watch 着足迹 —— 这里用 listen 模拟,并等首次加载完
  c.listen(historyProvider, (_, __) {});
  c.listen(recognitionNotifierProvider, (_, __) {}); // 相机页常驻 watch
  await Future<void>.delayed(Duration.zero);
  history.fetches = 0;
  await c.read(recognitionNotifierProvider.notifier).recognize(
        image: XFile.fromData(Uint8List.fromList(const [0, 1]),
            name: 'x.jpg', mimeType: 'image/jpeg'),
        language: 'zh',
      );
  await Future<void>.delayed(Duration.zero);
  return (c, history);
}

void main() {
  test('命中 → 足迹重拉', () async {
    final (_, h) = await _setup({'outcome': 'match', 'match': _item});
    expect(h.fetches, 1);
  });

  test('出候选还没点 → 不算足迹,不重拉;点选确认 → 重拉', () async {
    final (c, h) = await _setup({
      'outcome': 'candidates',
      'candidates': [_item],
      'phash': 'abc',
    });
    expect(h.fetches, 0);
    await c
        .read(recognitionNotifierProvider.notifier)
        .confirmRecognition('Q12418');
    await Future<void>.delayed(Duration.zero);
    expect(h.fetches, 1);
  });
}
