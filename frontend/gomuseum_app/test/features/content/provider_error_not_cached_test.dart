/// 错误态不许被永久缓存 —— 一次网络抖动不该把一个 (馆,语言) 永久钉死在失败上。
///
/// 真机实证 2026-09-22:波兰语下小皇宫整页「加载失败」,而 14 天的 nginx 日志里
/// 那个 (petit_palais, pl) 请求**一次都没出现过** —— App 拿缓存的 AsyncError
/// 直接渲染,连请求都不发;杀进程重开即好。根因是 family provider 没有
/// autoDispose,state(含错误态)永久驻留在 App 生命周期上。与语言无关。
///
/// 两条断言互为对照,缺一条都测不住:
///   ① 失败后重新监听 → 必须重新请求(calls 变 2)。少了它,bug 回归测不出。
///   ② 成功后重新监听 → 必须**不**重新请求(calls 仍 1)。少了它,"把 autoDispose
///      加成每次进页面都重取"也能通过——那会打回「切回原来的语言又要重新加载」
///      那个已修的真机 bug。
library;

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gomuseum_app/features/content/data/datasources/catalog_remote_datasource.dart';
import 'package:gomuseum_app/features/content/data/models/guide_audio.dart';
import 'package:gomuseum_app/features/content/data/models/museum_detail_model.dart';
import 'package:gomuseum_app/features/content/data/models/object_content_model.dart';
import 'package:gomuseum_app/features/content/data/models/object_list_model.dart';
import 'package:gomuseum_app/features/content/presentation/providers/catalog_providers.dart';
import 'package:gomuseum_app/features/content/presentation/providers/object_list_notifier.dart';

/// 头 [failFirst] 次调用抛异常,之后成功。模拟"一次瞬时网络抖动"。
class _FlakyDs implements CatalogRemoteDataSource {
  _FlakyDs({this.failFirst = 0});

  final int failFirst;
  int calls = 0;

  void _tick() {
    calls++;
    if (calls <= failFirst) throw Exception('network glitch');
  }

  @override
  Future<MuseumDetail> getMuseumDetail(
      {required String slug, String language = 'zh'}) async {
    _tick();
    return const MuseumDetail(
      slug: 'petit_palais',
      name: '小皇宫美术馆',
      nameEn: 'Petit Palais',
      city: 'Paris',
      country: 'FR',
      coordinates: [],
      openingHours: null,
      officialUrl: null,
      categories: [],
    );
  }

  @override
  Future<ObjectListPage> getObjects(
      {required String slug,
      String? category,
      String sort = 'popularity',
      int limit = 50,
      int offset = 0,
      String language = 'zh'}) async {
    _tick();
    return const ObjectListPage(items: [], total: 0, limit: 50, offset: 0);
  }

  @override
  Future<ObjectContent> getObjectContent(
          {required String slug,
          required String qid,
          String language = 'zh'}) async =>
      throw UnimplementedError();

  @override
  Future<GuideAudioResult> getGuideAudio(
          {required String slug,
          required String qid,
          required String language,
          String section = 'guide',
          int? qaSort}) async =>
      const GuideAudioFailed();

  @override
  String audioStreamUrl(
          {required String slug,
          required String qid,
          required String language,
          String section = 'guide'}) =>
      'http://x/stream';
}

ProviderContainer _container(_FlakyDs ds) {
  final c = ProviderContainer(
      overrides: [catalogDataSourceProvider.overrideWithValue(ds)]);
  addTearDown(c.dispose);
  return c;
}

/// 移除订阅 + 放行一轮事件循环,让 autoDispose 真正释放。
Future<void> _leavePage(ProviderSubscription<Object?> sub) async {
  sub.close();
  await Future<void>.delayed(Duration.zero);
}

void main() {
  group('museumDetailProvider', () {
    test('① 首次失败 → 重进页面必须重试', () async {
      final ds = _FlakyDs(failFirst: 1);
      final c = _container(ds);
      final p = museumDetailProvider((slug: 'petit_palais', language: 'pl'));

      var sub = c.listen(p, (_, __) {});
      await expectLater(c.read(p.future), throwsA(isA<Exception>()));
      expect(ds.calls, 1);
      await _leavePage(sub);

      sub = c.listen(p, (_, __) {});
      final detail = await c.read(p.future);
      expect(ds.calls, 2, reason: '错误态驻留的话这里还是 1 —— 永远不再发请求');
      expect(detail.nameEn, 'Petit Palais');
      sub.close();
    });

    test('② 成功结果仍永久缓存(别改成每次进页面都重取)', () async {
      final ds = _FlakyDs();
      final c = _container(ds);
      final p = museumDetailProvider((slug: 'petit_palais', language: 'pl'));

      var sub = c.listen(p, (_, __) {});
      await c.read(p.future);
      expect(ds.calls, 1);
      await _leavePage(sub);

      sub = c.listen(p, (_, __) {});
      await c.read(p.future);
      expect(ds.calls, 1, reason: '成功结果必须 keepAlive,否则「切回原语言又要重新加载」回归');
      sub.close();
    });
  });

  group('objectListProvider', () {
    final key = (slug: 'petit_palais', category: 'all', language: 'pl');

    test('① 首次失败 → 重进页面必须重试', () async {
      final ds = _FlakyDs(failFirst: 1);
      final c = _container(ds);

      var sub = c.listen(objectListProvider(key), (_, __) {});
      await Future<void>.delayed(Duration.zero);
      expect(c.read(objectListProvider(key)).error, isNotNull);
      expect(ds.calls, 1);
      await _leavePage(sub);

      sub = c.listen(objectListProvider(key), (_, __) {});
      await Future<void>.delayed(Duration.zero);
      expect(ds.calls, 2, reason: '错误态驻留的话这里还是 1 —— 永远不再发请求');
      expect(c.read(objectListProvider(key)).error, isNull);
      sub.close();
    });

    test('② 成功结果仍永久缓存', () async {
      final ds = _FlakyDs();
      final c = _container(ds);

      var sub = c.listen(objectListProvider(key), (_, __) {});
      await Future<void>.delayed(Duration.zero);
      expect(ds.calls, 1);
      await _leavePage(sub);

      sub = c.listen(objectListProvider(key), (_, __) {});
      await Future<void>.delayed(Duration.zero);
      expect(ds.calls, 1, reason: '成功列表必须 keepAlive,否则每次进馆都重拉');
      sub.close();
    });
  });
}
