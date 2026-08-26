// 「跟随系统」= languageProvider 的 state 为 null。
// 最要紧的一条是 supportedLocales 首项必须是 en —— 「系统语言不支持则回退英文」
// 完全靠 Flutter 的 basicLocaleListResolution 拿 first，没有别的代码在兜底。
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gomuseum_app/features/settings/presentation/providers/language_provider.dart';
import 'package:shared_preferences/shared_preferences.dart';

const _kKey = 'selected_language';

Future<Locale?> _stateAfterLoad(Map<String, Object> prefs) async {
  SharedPreferences.setMockInitialValues(prefs);
  final container = ProviderContainer();
  addTearDown(container.dispose);
  // ⚠️ 必须 listen 而不是 read：provider 是 autoDispose，read 完没有订阅者就会
  // 被销毁，_loadLanguage 的异步赋值落空、再读又是一个全新的 build。
  final sub = container.listen(languageProvider, (_, __) {});
  await pumpEventQueue(); // 等 SharedPreferences 的异步链跑完
  return sub.read();
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  group('回退英文所依赖的契约', () {
    test('supportedLocales 首项是 en —— 匹配不上时 Flutter 回退到它', () {
      expect(kAppLocalesInResolutionOrder.first, const Locale('en'));
    });

    test('展示列表按展示名字母序排列（加语言时按序插入，别追加到末尾）', () {
      final names = kSupportedLocales.map(languageDisplayName).toList();
      expect(names, equals([...names]..sort()));
    });

    test('展示顺序与解析顺序内容一致（加语言别只加一处）', () {
      Set<String> tags(List<Locale> l) => l.map(localeTag).toSet();
      expect(tags(kAppLocalesInResolutionOrder), tags(kSupportedLocales));
    });
  });

  group('默认与持久化', () {
    test('没选过语言的用户默认跟随系统（state 为 null）', () async {
      expect(await _stateAfterLoad({}), isNull);
    });

    test('已选过语言的老用户不受默认值改动影响', () async {
      expect(await _stateAfterLoad({_kKey: 'ja'}), const Locale('ja'));
    });

    test('繁体读回不丢 scriptCode', () async {
      final l = await _stateAfterLoad({_kKey: 'zh-Hant'});
      expect(l?.languageCode, 'zh');
      expect(l?.scriptCode, 'Hant');
    });

    test('切回跟随系统会删掉 key，而不是存哨兵值', () async {
      SharedPreferences.setMockInitialValues({_kKey: 'fr'});
      final container = ProviderContainer();
      addTearDown(container.dispose);
      final sub = container.listen(languageProvider, (_, __) {});
      await container.read(languageProvider.notifier).setLanguage(null);
      expect(sub.read(), isNull);
      final prefs = await SharedPreferences.getInstance();
      expect(prefs.containsKey(_kKey), isFalse);
    });

    test('选具体语言仍存完整 tag', () async {
      SharedPreferences.setMockInitialValues({});
      final container = ProviderContainer();
      addTearDown(container.dispose);
      await container.read(languageProvider.notifier).setLanguage(
          const Locale.fromSubtags(languageCode: 'zh', scriptCode: 'Hant'));
      final prefs = await SharedPreferences.getInstance();
      expect(prefs.getString(_kKey), 'zh-Hant');
    });
  });

  group('设置项显示文案', () {
    test('null 显示「跟随系统」文案，否则显示语言名', () {
      expect(languageSettingLabel(null, '跟随系统'), '跟随系统');
      expect(languageSettingLabel(const Locale('ja'), '跟随系统'), '日本語');
    });
  });
}
