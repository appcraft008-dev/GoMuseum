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

import 'dart:ui' show Locale;

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gomuseum_app/features/content/data/datasources/catalog_remote_datasource.dart';
import 'package:gomuseum_app/features/content/data/models/guide_audio.dart';
import 'package:gomuseum_app/features/content/data/models/museum_detail_model.dart';
import 'package:gomuseum_app/features/content/data/models/object_content_model.dart';
import 'package:gomuseum_app/features/content/data/models/object_list_model.dart';
import 'package:gomuseum_app/features/content/presentation/providers/catalog_providers.dart';
import 'package:gomuseum_app/features/content/presentation/providers/object_list_notifier.dart';
import 'package:gomuseum_app/features/settings/presentation/providers/language_provider.dart';

/// 头 [failFirst] 次调用抛异常,之后成功。模拟"一次瞬时网络抖动"。
class _FlakyDs implements CatalogRemoteDataSource {
  _FlakyDs({this.failFirst = 0, this.generatingCalls = 0, this.emptyCalls = 0});

  final int failFirst;

  /// 讲解:头 [generatingCalls] 次返回「生成中」(后端还在写),之后返回生成完。
  final int generatingCalls;

  /// 讲解:头 [emptyCalls] 次返回「不在生成、这门语言也没内容」(status=empty)。
  final int emptyCalls;
  int calls = 0;

  void _tick() {
    calls++;
    if (calls <= failFirst) throw Exception('network glitch');
  }

  @override
  Future<MuseumDetail> getMuseumDetail({
    required String slug,
    String language = 'zh',
  }) async {
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
  Future<ObjectListPage> getObjects({
    required String slug,
    String? category,
    String sort = 'popularity',
    int limit = 50,
    int offset = 0,
    String language = 'zh',
  }) async {
    _tick();
    return const ObjectListPage(items: [], total: 0, limit: 50, offset: 0);
  }

  @override
  Future<ObjectContent> getObjectContent({
    required String slug,
    required String qid,
    String language = 'zh',
  }) async {
    _tick();
    return ObjectContent(
      qid: qid,
      category: 'painting',
      language: language,
      status: calls <= emptyCalls ? ContentStatus.empty : ContentStatus.ready,
      generating: calls <= generatingCalls,
      title: '安东尼娅',
      images: const [],
      facts: const ObjectFacts(),
      tabs: const [],
      suggestedQuestions: const [],
    );
  }

  @override
  Future<GuideAudioResult> getGuideAudio({
    required String slug,
    required String qid,
    required String language,
    String section = 'guide',
    int? qaSort,
  }) async =>
      const GuideAudioFailed();

  @override
  String audioStreamUrl({
    required String slug,
    required String qid,
    required String language,
    String section = 'guide',
  }) =>
      'http://x/stream';
}

ProviderContainer _container(_FlakyDs ds) {
  final c = ProviderContainer(
    overrides: [
      catalogDataSourceProvider.overrideWithValue(ds),
      resolvedLocaleProvider.overrideWithValue(const Locale('zh')),
    ],
  );
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

  /// 2026-10-04 真机:识别「安东尼娅」时讲解正在懒生成,App 缓存了生成中的空壳;
  /// 服务器 19 秒后就有了中文讲解,可再进这件作品一直转圈、一个请求都不发
  /// (nginx 日志实证),杀进程重开才有内容。生成中 = 未完成,跟错误态一样不许驻留。
  group('objectContentProvider', () {
    final key = (slug: 'orangerie', qid: 'joconde-00000089487');

    test('① 生成中的结果 → 重进页面必须重新请求', () async {
      final ds = _FlakyDs(generatingCalls: 1);
      final c = _container(ds);

      var sub = c.listen(objectContentProvider(key), (_, __) {});
      expect(
        (await c.read(objectContentProvider(key).future)).generating,
        isTrue,
      );
      expect(ds.calls, 1);
      await _leavePage(sub);

      sub = c.listen(objectContentProvider(key), (_, __) {});
      final content = await c.read(objectContentProvider(key).future);
      expect(ds.calls, 2, reason: '生成中的空壳驻留的话这里还是 1 —— 永远转圈');
      expect(content.generating, isFalse);
      sub.close();
    });

    test('② 首次失败 → 重进页面必须重试', () async {
      final ds = _FlakyDs(failFirst: 1);
      final c = _container(ds);

      var sub = c.listen(objectContentProvider(key), (_, __) {});
      await expectLater(
        c.read(objectContentProvider(key).future),
        throwsA(isA<Exception>()),
      );
      await _leavePage(sub);

      sub = c.listen(objectContentProvider(key), (_, __) {});
      await c.read(objectContentProvider(key).future);
      expect(ds.calls, 2);
      sub.close();
    });

    /// #1045 真机 10-21:zh 等待中离开,再进连请求都不发。后端有个窗口(英文生成完
    /// 清锁 → 补语言登记 pending 之前)会回 generating=false + 这门语言 empty;
    /// 旧代码见 generating=false 就 keepAlive,把「暂无讲解」缓存到杀进程。
    test('④ 不在生成但这门语言没内容 → 重进页面必须重新请求', () async {
      final ds = _FlakyDs(emptyCalls: 1);
      final c = _container(ds);

      var sub = c.listen(objectContentProvider(key), (_, __) {});
      final first = await c.read(objectContentProvider(key).future);
      expect(first.generating, isFalse);
      expect(first.status, ContentStatus.empty);
      await _leavePage(sub);

      sub = c.listen(objectContentProvider(key), (_, __) {});
      final content = await c.read(objectContentProvider(key).future);
      expect(ds.calls, 2, reason: '空结果驻留的话这里还是 1 —— 一直「暂无讲解」');
      expect(content.status, ContentStatus.ready);
      sub.close();
    });

    test('③ 生成完的结果仍永久缓存', () async {
      final ds = _FlakyDs();
      final c = _container(ds);

      var sub = c.listen(objectContentProvider(key), (_, __) {});
      await c.read(objectContentProvider(key).future);
      await _leavePage(sub);

      sub = c.listen(objectContentProvider(key), (_, __) {});
      await c.read(objectContentProvider(key).future);
      expect(ds.calls, 1, reason: '已完成的讲解必须 keepAlive,否则每次进作品都重拉');
      sub.close();
    });
  });

  group('objectContentProvider 换语言(#1045 真机 10-21)', () {
    final key = (slug: 'petit_palais', qid: 'Q138632428');

    test('④ en 已完成 → 切 zh 生成中 → 离开再进必须重新请求', () async {
      final ds = _LangDs();
      final locale = StateProvider<Locale>((_) => const Locale('en'));
      final c = ProviderContainer(
        overrides: [
          catalogDataSourceProvider.overrideWithValue(ds),
          resolvedLocaleProvider.overrideWith((ref) => ref.watch(locale)),
        ],
      );
      addTearDown(c.dispose);

      var sub = c.listen(objectContentProvider(key), (_, __) {});
      expect(
        (await c.read(objectContentProvider(key).future)).generating,
        isFalse,
      ); // en 完成 → keepAlive
      c.read(locale.notifier).state = const Locale('zh');
      expect(
        (await c.read(objectContentProvider(key).future)).generating,
        isTrue,
      );
      final before = ds.calls;
      await _leavePage(sub);

      sub = c.listen(objectContentProvider(key), (_, __) {});
      await c.read(objectContentProvider(key).future);
      expect(
        ds.calls,
        before + 1,
        reason: 'en 那次的 keepAlive 没随重建释放的话,这里不发请求(真机 78s 无 /content)',
      );
      sub.close();
    });
  });
}

/// en 生成完;zh 一直生成中。
class _LangDs extends _FlakyDs {
  @override
  Future<ObjectContent> getObjectContent({
    required String slug,
    required String qid,
    String language = 'zh',
  }) async {
    final c = await super.getObjectContent(
      slug: slug,
      qid: qid,
      language: language,
    );
    return ObjectContent(
      qid: c.qid,
      category: c.category,
      language: language,
      status: c.status,
      generating: language != 'en',
      title: c.title,
      images: c.images,
      facts: c.facts,
      tabs: c.tabs,
      suggestedQuestions: c.suggestedQuestions,
    );
  }
}
