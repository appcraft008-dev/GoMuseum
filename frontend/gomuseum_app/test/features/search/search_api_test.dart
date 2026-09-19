// 搜索模型解析容错：museum/thumbnail 缺失不炸（禁裸强转），has_image 默认 false。
// 外加一条：请求到底带没带 limit —— 漏了不会报错，只会让一整类命中看不见。
import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gomuseum_app/features/recognition/presentation/providers/recognition_providers.dart';
import 'package:gomuseum_app/features/search/data/search_api.dart';

/// 记下最后一次请求的 RequestOptions，断言实际发出去的 query 参数。
class _CapturingAdapter implements HttpClientAdapter {
  RequestOptions? last;

  @override
  void close({bool force = false}) {}

  @override
  Future<ResponseBody> fetch(RequestOptions options,
      Stream<List<int>>? requestStream, Future? cancelFuture) async {
    last = options;
    return ResponseBody.fromString(
      '{"query":"x","museums":[],"objects":[]}',
      200,
      headers: {
        Headers.contentTypeHeader: [Headers.jsonContentType]
      },
    );
  }
}

void main() {
  test('SearchObject 缺 museum/thumbnail/has_image → 安全默认', () {
    final o = SearchObject.fromJson({'qid': 'Q1', 'title': '星夜'});
    expect(o.museum, isNull);
    expect(o.thumbnail, isNull);
    expect(o.hasImage, isFalse);
    expect(o.artist, '');
  });

  test('SearchObject 缺 title → 回退 qid', () {
    expect(SearchObject.fromJson({'qid': 'Q9'}).title, 'Q9');
  });

  test('SearchObject 完整解析', () {
    final o = SearchObject.fromJson({
      'qid': 'Q1',
      'title': '星夜',
      'artist': '文森特·梵高',
      'year': '1889',
      'thumbnail': 'http://x/1.jpg',
      'museum': 'orsay',
      'has_image': true,
    });
    expect(o.hasImage, isTrue);
    expect(o.museum, 'orsay');
    expect(o.year, '1889');
  });

  test('SearchResults 解析两段 + 空默认', () {
    final r = SearchResults.fromJson({
      'query': 'q',
      'museums': [
        {'slug': 'orsay', 'name': '奥赛', 'city': '巴黎'}
      ],
      'objects': [
        {'qid': 'Q1', 'title': '星夜'}
      ],
    });
    expect(r.museums.single.slug, 'orsay');
    expect(r.objects.single.qid, 'Q1');
    expect(r.isEmpty, isFalse);

    final empty = SearchResults.fromJson({'query': 'q'});
    expect(empty.isEmpty, isTrue);
  });

  group('请求参数', () {
    Future<RequestOptions?> fire(SearchQuery key) async {
      final adapter = _CapturingAdapter();
      final dio = Dio(BaseOptions(baseUrl: 'http://x'))
        ..httpClientAdapter = adapter;
      final container = ProviderContainer(
        overrides: [dioProvider.overrideWithValue(dio)],
      );
      addTearDown(container.dispose);
      await container.read(searchProvider(key).future);
      return adapter.last;
    }

    test('🔴 必须带 limit，且明显大于后端默认的 20', () async {
      final req = await fire((slug: null, q: 'portrait', lang: 'zh'));

      final limit = req!.queryParameters['limit'] as int?;
      expect(limit, isNotNull, reason: '没传 limit → 吃后端默认 20');
      // rank() 先按档排序再截断，被砍掉的正是「关键词在标题中间」那一层。
      // prod 实测 `portrait` 共 43 条命中，20 这个刀口把 13 个 Autoportrait
      // 全切没了。门槛按实测最大常见词取，不是拍脑袋。
      expect(limit, greaterThan(43), reason: '刀口还在常见词的命中数以内');
    });

    test('馆域搜索走同一条路，同样要带 limit（对照组）', () async {
      final req = await fire((slug: 'orsay', q: 'portrait', lang: 'zh'));

      expect(req!.path, '/api/v1/museums/orsay/search');
      expect(req.queryParameters['limit'], greaterThan(43));
    });

    test('空 query 不打网络', () async {
      expect(await fire((slug: null, q: '  ', lang: 'zh')), isNull);
    });
  });
}
