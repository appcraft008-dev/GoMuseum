// test/features/settings/quota_card_layout_test.dart
//
// 回归：设置页三处 Row 曾按"内容固有宽度"摆放不限宽的文本/控件，某些语言的译法
// 比英语长得多时会把 Row 挤到溢出（真机截图 + 窄屏实测均已复现）：
//   1. 通票卡片 Row(Expanded(到期日文本), 按钮)——法语"Voir mes avantages"把
//      Expanded 那侧挤到几乎为零，到期日文本被迫逐字折行成一长条。
//   2. 外观分段控件 Row(图标+标签, Spacer, 三段控件)——德语/波兰语标签+控件
//      固有宽度之和超过整行宽度，窄屏下溢出 135px。
//   3. GmSectionHead 的 Row(编号, 标签, Expanded(发丝线))——法语"Aide &
//      Mentions légales"这类长标签本身就能撑爆整行，溢出 34px。
// 用真实渲染在窄屏(360dp，常见 Android 逻辑宽度)+ 多语言下跑一遍，
// 抓 RenderFlex overflow 断言，而不是走查代码猜测。
import 'dart:async';

import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gomuseum_app/features/auth/data/auth_repository.dart';
import 'package:gomuseum_app/features/auth/presentation/auth_provider.dart';
import 'package:gomuseum_app/features/payment/data/entitlements.dart';
import 'package:gomuseum_app/features/payment/domain/entities/user_benefits.dart';
import 'package:gomuseum_app/features/payment/presentation/providers/benefits_provider.dart';
import 'package:gomuseum_app/features/settings/presentation/pages/settings_page.dart';
import 'package:gomuseum_app/l10n/app_localizations.dart';
import 'package:shared_preferences/shared_preferences.dart';

const _activePass = Entitlements(
  state: 'active',
  canPurchase: false,
  canRecognize: true,
  canAudioAny: true,
);

const _freeTier = Entitlements(
  state: 'not_purchased',
  canPurchase: true,
  canRecognize: true,
  canAudioAny: false,
  freeRecognitionsLeft: 3,
  freeRecognitionsTotal: 5,
);

class _StubAuthNotifier extends AuthNotifier {
  _StubAuthNotifier(super.repository) {
    state = const AsyncValue.data(null);
  }
}

class _StubBenefitsState extends BenefitsState {
  @override
  FutureOr<UserBenefits> build() => UserBenefits.none();
}

Future<List<FlutterErrorDetails>> _renderSettings(
  WidgetTester tester, {
  required String locale,
  required Entitlements entitlements,
}) async {
  tester.view.physicalSize = const Size(360, 900);
  tester.view.devicePixelRatio = 1.0;
  addTearDown(tester.view.resetPhysicalSize);
  addTearDown(tester.view.resetDevicePixelRatio);

  SharedPreferences.setMockInitialValues({});
  final container = ProviderContainer(overrides: [
    currentUserProvider.overrideWith(
      (ref) => _StubAuthNotifier(AuthRepository(Dio())),
    ),
    benefitsStateProvider.overrideWith(() => _StubBenefitsState()),
    entitlementsProvider.overrideWith((ref) async => entitlements),
  ]);
  addTearDown(container.dispose);

  final errors = <FlutterErrorDetails>[];
  final originalOnError = FlutterError.onError;
  FlutterError.onError = errors.add;
  addTearDown(() => FlutterError.onError = originalOnError);

  await tester.pumpWidget(
    UncontrolledProviderScope(
      container: container,
      child: MaterialApp(
        localizationsDelegates: AppLocalizations.localizationsDelegates,
        supportedLocales: AppLocalizations.supportedLocales,
        locale: Locale(locale),
        home: const Scaffold(body: SettingsPage()),
      ),
    ),
  );
  await tester.pump();
  await tester.pump(); // entitlementsProvider 的 Future 落地
  return errors;
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  // fr/de/pl 是已知的"译法明显长于英语"的高风险语言(通票按钮、外观标签、
  // 支持区标题分别在这几种语言下最长)；en 作为基线一起跑。
  for (final locale in ['fr', 'de', 'pl', 'en']) {
    testWidgets('通票生效中 · $locale · 360dp 窄屏不溢出', (tester) async {
      final errors = await _renderSettings(tester,
          locale: locale, entitlements: _activePass);
      expect(errors, isEmpty,
          reason: errors.map((e) => e.exceptionAsString()).join('\n---\n'));
    });

    testWidgets('免费层 · $locale · 360dp 窄屏不溢出', (tester) async {
      final errors = await _renderSettings(tester,
          locale: locale, entitlements: _freeTier);
      expect(errors, isEmpty,
          reason: errors.map((e) => e.exceptionAsString()).join('\n---\n'));
    });
  }

  // ⚠️ 上面那组只抓 RenderFlex overflow —— 而 GmSectionHead 加了
  // `Flexible + TextOverflow.ellipsis` 之后**就再也不会溢出了**,它改成默默截断。
  // 上面那组从此对这一类缺陷完全失明:2026-09-08 真机上法语「Aide & Mention…」
  // 被截成读不懂,而这个文件当时全绿。
  //
  // 🔴 **为什么这里查的是字数而不是像素**:widget test 跑在 `--use-test-fonts` 下,
  // 每个字形都是**正方形 em** —— 拉丁字母被量成真实宽度的约两倍,CJK 才接近真实。
  // 而会出事的恰恰是拉丁语言,所以在 widget test 里量 `didExceedMaxLines`
  // 会系统性冤枉法语/德语/西语(第一版就是这么写的,en 都判不过)。
  // 渲染宽度这件事只有真机/真字体说了算,单测能守住的是**上游那个变量:译法长度**。
  //
  // 预算依据(实测,不是拍的):fr 23 字符在真机上被截断;缩短后最长是 it 17 字符,
  // 真机复验正常。取 18 留一格余量。换机型/改字号后如果真机又出现截断,
  // **该做的是把这个数字调小并记下新的实测依据**,不是删掉这条测试。
  const budget = 18;
  test('分区标题各语言译法长度不超预算(挡住"下次翻译又变长")', () {
    final tooLong = <String>[];
    for (final locale in AppLocalizations.supportedLocales) {
      final l10n = lookupAppLocalizations(locale);
      for (final entry in {
        'secGeneral': l10n.secGeneral,
        'secAccount': l10n.secAccount,
        'secSupport': l10n.secSupport,
      }.entries) {
        if (entry.value.length > budget) {
          tooLong.add('$locale/${entry.key} = "${entry.value}"'
              ' (${entry.value.length} 字符)');
        }
      }
    }
    expect(tooLong, isEmpty,
        reason: '这些分区标题会在窄屏被截成省略号,读不懂。'
            '上限 $budget 字符:\n${tooLong.join('\n')}');
  });
}
