// test/i18n/real_fonts.dart
//
// 让 widget 测试用**真实字体**排版。flutter_test 默认字体每个字形都是 1em 方块：
// 中日韩宽度碰巧准，拉丁文却被放大约 2 倍（"Hello world" 方块 110px / Noto Sans
// 49px）—— 拿它判断多语言溢出，西语系会报一堆假溢出。
//
// 做法：按 google_fonts 的家族名（`NotoSans_700` 这种）预先用 FontLoader 注册
// 同一份字体文件；google_fonts 自己的网络加载在测试里会失败，但同名字体已在引擎里，
// 渲染照样用上。字体从 fonts.gstatic.com 下载一次，缓存到 .dart_tool/（不进 git）。
//
// 中日韩：按地区取真实字体（见 _cjk），截图里各语言字形是对的。
import 'dart:io';
import 'dart:typed_data';

import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';

/// google_fonts 8.1.0 的 w400–w700 文件哈希（= fonts.gstatic.com/s/a/{hash}.ttf）。
const _latin = {
  'NotoSans': [
    '61ea1e781b9d7b10db9b4a6aa2d855cf2215c316c7cb700aeb067a0440d031e0',
    '86553647e178b7a8f5f613ef27d057b69168db555caa4235d1bfee92d01d0273',
    '6c302f0c3ac2c7afcfde0f124337360cdceda4f28564fab69d39460e5ecb4392',
    '1c657f0687537f6987bb0db652a59dbf90843778c641a0a53ac020372cac10d1',
  ],
  'NotoSerif': [
    'a6e0283968e506c67c3d4ff94093e3ff9f4d7ec3c704ff1cb51382f1e45b66b9',
    '573f2e6c8b0eb3d8c159af7700b9968a51fec14d596c7bd81cd62dea6a7f9eb2',
    '468d67b7f26a6f8ab83cf43a71de164d1580f62b0c36403e56d5e2963a275d6b',
    '1cff8098b873570abf5e194f781e85078d6b250ef5b95eb1e03c390f2ab223e2',
  ],
};

/// 中日韩按地区各取 w400 一份，注册到该地区所有字重名下（粗体由引擎合成）：
/// SC 里没有谚文，韩文落到 SC 会显示成豆腐块。衬线 SC 单独取 —— 简中标题用它。
const _cjk = {
  'NotoSansSC':
      'a0ecca1c67a4da5a89857703b84a44eba9fce7d7b5941bf4285e8c0a8346cf60',
  'NotoSerifSC':
      '5fbd8ebc1678279307a49822f08015acb572dcdc282c38653a0449890f603db6',
  'NotoSansJP':
      '0eba77a9f62df60eda7b56719cf57bbfbd8434583f2a137a9b91d4d67cf420c0',
  'NotoSansKR':
      '65f278fc677a3a0128c733af662c3eb31b910c9bce81e046ccc3c6d3ede879e2',
  'NotoSansTC':
      '17d9b1bfc0eb614c5947422e575e4bf664afc809def6cdcd7760d76c71928e50',
};

/// 日韩繁的衬线体各 7–14MB，测试里用同地区无衬线代替（宽度一致，字形不同）。
const _cjkAlias = {
  'NotoSerifJP': 'NotoSansJP',
  'NotoSerifKR': 'NotoSansKR',
  'NotoSerifTC': 'NotoSansTC',
};
const _variants = ['regular', '500', '600', '700'];

class _RealHttp extends HttpOverrides {}

Future<Uint8List> _fetch(String hash) async {
  final f = File('.dart_tool/test_fonts/$hash.ttf');
  if (f.existsSync()) return f.readAsBytes();
  // flutter_test 把 HttpClient 换成了恒返回 400 的假实现，这里显式要真的。
  final client =
      HttpOverrides.runWithHttpOverrides(() => HttpClient(), _RealHttp());
  final res = await (await client
          .getUrl(Uri.parse('https://fonts.gstatic.com/s/a/$hash.ttf')))
      .close();
  if (res.statusCode != 200) throw StateError('font $hash: ${res.statusCode}');
  final bytes = await res
      .fold<BytesBuilder>(BytesBuilder(), (b, x) => b..add(x))
      .then((b) => b.takeBytes());
  client.close();
  await f.create(recursive: true);
  await f.writeAsBytes(bytes);
  return bytes;
}

Future<void> _register(String family, Uint8List bytes) =>
    (FontLoader(family)..addFont(Future.value(ByteData.sublistView(bytes))))
        .load();

bool _loaded = false;

/// 在 testWidgets 里调用一次即可（同进程内只加载一次）。
Future<void> loadRealFonts(WidgetTester tester) async {
  if (_loaded) return;
  await tester.runAsync(() async {
    for (final e in _latin.entries) {
      for (var i = 0; i < _variants.length; i++) {
        await _register('${e.key}_${_variants[i]}', await _fetch(e.value[i]));
      }
    }
    final bytes = {
      for (final e in _cjk.entries) e.key: await _fetch(e.value),
    };
    for (final fam in [..._cjk.keys, ..._cjkAlias.keys]) {
      for (final v in _variants) {
        await _register('${fam}_$v', bytes[_cjkAlias[fam] ?? fam]!);
      }
    }
  });
  _loaded = true;
}
