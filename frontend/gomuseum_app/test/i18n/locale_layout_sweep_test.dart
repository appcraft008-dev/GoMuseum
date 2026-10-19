// test/i18n/locale_layout_sweep_test.dart
//
// 多语言排版扫描：主要页面 × 全部 UI 语言，在 360dp 窄屏 + 真实字体下渲染，
//   - **溢出**（RenderFlex overflowed 等布局错误）→ 失败；
//   - **被截断的文本**（maxLines 到顶、出省略号）→ 只记录不失败（有些是刻意设计）；
//   - **被 FittedBox 缩小的文字**（<0.97）→ 只记录；不溢出，但字号随语言忽大忽小；
//   - **单词被拦腰断行**（窄 Expanded 把德语长词切成 "Anmelde|n"）→ 只记录；
//     这类不报布局错误，查溢出抓不到，却是多语言最丑的形态。
//   报告写到 build/i18n_sweep/report.tsv；
//   - 每格截图写到 build/i18n_sweep/<页面>/<语言>.png，供人眼横向比对。
// 真实字体见 real_fonts.dart —— 默认方块字体会把拉丁文宽度放大一倍，结论不可信。
//
// 只跑这一组：flutter test test/i18n/locale_layout_sweep_test.dart
import 'dart:async';
import 'dart:io';
import 'dart:ui' as ui;

import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter/rendering.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gomuseum_app/features/auth/data/auth_repository.dart';
import 'package:gomuseum_app/features/auth/presentation/auth_provider.dart';
import 'package:gomuseum_app/features/auth/presentation/login_page.dart';
import 'package:gomuseum_app/features/content/data/models/museum_summary_model.dart';
import 'package:gomuseum_app/features/content/data/models/object_content_model.dart';
import 'package:gomuseum_app/features/content/data/models/object_list_model.dart';
import 'package:gomuseum_app/features/content/presentation/providers/catalog_providers.dart';
import 'package:gomuseum_app/features/explore/presentation/pages/explore_page.dart';
import 'package:gomuseum_app/features/guide/presentation/pages/guide_page.dart';
import 'package:gomuseum_app/features/history/presentation/providers/history_providers.dart';
import 'package:gomuseum_app/features/home/data/nearby.dart';
import 'package:gomuseum_app/features/home/presentation/pages/home_page.dart';
import 'package:gomuseum_app/features/payment/data/entitlements.dart';
import 'package:gomuseum_app/features/payment/data/pass_history.dart';
import 'package:gomuseum_app/features/payment/data/pass_offer.dart';
import 'package:gomuseum_app/features/payment/data/pass_product.dart';
import 'package:gomuseum_app/features/payment/domain/entities/user_benefits.dart';
import 'package:gomuseum_app/features/payment/presentation/pages/benefits_page.dart';
import 'package:gomuseum_app/features/payment/presentation/providers/benefits_provider.dart';
import 'package:gomuseum_app/features/payment/presentation/widgets/paywall_sheet.dart';
import 'package:gomuseum_app/features/recognition/data/models/recognize_response.dart';
import 'package:gomuseum_app/features/recognition/presentation/pages/camera_page.dart';
import 'package:gomuseum_app/features/recognition/presentation/providers/recognition_provider.dart';
import 'package:gomuseum_app/features/settings/presentation/pages/settings_page.dart';
import 'package:gomuseum_app/features/settings/presentation/providers/language_provider.dart';
import 'package:gomuseum_app/l10n/app_localizations.dart';
import 'package:gomuseum_app/theme/app_theme.dart';
import 'package:gomuseum_app/theme/gm_tokens.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'real_fonts.dart';

// ---------------------------------------------------------------------------
// 假数据：后端内容按用户语言返回，所以中日韩给中文、其余给拉丁文。
// ---------------------------------------------------------------------------
bool _cjk(Locale l) => const {'zh', 'ja', 'ko'}.contains(l.languageCode);

List<MuseumSummary> _museums(Locale l) {
  MuseumSummary m(String slug, String zh, String lat, String city, int n) =>
      MuseumSummary(
        slug: slug,
        name: _cjk(l) ? zh : lat,
        nameEn: lat,
        city: _cjk(l) ? '巴黎' : city,
        cityEn: city,
        country: 'FR',
        coordinates: const [48.86, 2.33],
        artworkCount: n,
      );
  return [
    m('orsay', '奥赛博物馆', "Musée d'Orsay", 'Paris', 6789),
    m('orangerie', '橘园美术馆', "Musée de l'Orangerie", 'Paris', 140),
    m('petit-palais', '巴黎小皇宫', 'Petit Palais', 'Paris', 1100),
  ];
}

ObjectContent _content(Locale l) {
  final c = _cjk(l);
  return ObjectContent(
    qid: 'Q1',
    category: 'painting',
    language: l.languageCode,
    status: ContentStatus.ready,
    title: c ? '在阿尔勒的卧室' : 'The Bedroom in Arles',
    images: const [],
    facts: ObjectFacts(
      artist: c ? '文森特·梵高' : 'Vincent van Gogh',
      date: '1889',
      medium: c ? '布面油画' : 'Oil on canvas',
      dimensions: '57 × 74 cm',
    ),
    tabs: [
      ObjectTab(
        sectionCode: 'overview',
        label: 'overview',
        body: c
            ? '这是梵高在阿尔勒黄房子里的卧室。他用鲜艳的平涂色块和略微倾斜的透视，'
                '把一间朴素的小屋画成了“休息”本身。'
            : 'This is the bedroom Van Gogh rented in the Yellow House in Arles. '
                'With flat areas of bright colour and a slightly tilted '
                'perspective, he turned a plain little room into the very idea '
                'of rest.',
        hasAudio: false,
      ),
    ],
    suggestedQuestions: [
      SuggestedQuestion(
        question: c ? '为什么透视是歪的？' : 'Why does the perspective look tilted?',
        answer: c ? '梵高有意如此。' : 'Van Gogh did it on purpose.',
      ),
    ],
  );
}

class _Benefits extends BenefitsState {
  @override
  FutureOr<UserBenefits> build() => const UserBenefits(
        hasAccess: true,
        recognitionQuota: 8,
        referralBonusQuota: 0,
        totalQuota: 8,
        totalUsed: 2,
      );
}

/// 拍照页的识别状态钉死在某一态（resetState 也不回到初始态）。
class _FixedRec extends RecognitionNotifier {
  _FixedRec(this.fixed);
  final RecognitionState fixed;
  @override
  RecognitionState build() => fixed;
  @override
  void resetState() {}
}

List<RecognizedItem> _candidates(Locale l) {
  final c = _cjk(l);
  RecognizedItem i(String q, String zh, String lat, String a) => RecognizedItem(
      qid: q, title: c ? zh : lat, artist: a, thumbnail: null, score: 0.8);
  return [
    i('Q1', '在阿尔勒的卧室', 'The Bedroom in Arles', 'Vincent van Gogh'),
    i('Q2', '星夜', 'The Starry Night Over the Rhône', 'Vincent van Gogh'),
    i('Q3', '草地上的午餐', 'Le Déjeuner sur l\'herbe', 'Édouard Manet'),
  ];
}

class _NoHistory extends History {
  @override
  HistoryState build() => const HistoryState(isLoading: false, hasMore: false);
}

class _LoggedOut extends AuthNotifier {
  _LoggedOut(super.repository) {
    state = const AsyncValue.data(null);
  }
}

Entitlements _free(Locale l) => Entitlements(
      state: 'not_purchased',
      canPurchase: true,
      canRecognize: true,
      canAudioAny: false,
      freeRecognitionsLeft: 3,
      freeRecognitionsTotal: 5,
      offers: [
        PassOffer(
          productId: 'paris_pass_7d',
          days: 7,
          label: _cjk(l) ? '巴黎' : 'Paris',
          covers: _museums(l).map((m) => m.name).toList(),
        ),
      ],
    );

Entitlements _active(Locale l) => Entitlements(
      state: 'active',
      canPurchase: true,
      canRecognize: true,
      canAudioAny: true,
      expiresAt: DateTime(2026, 10, 25, 18),
      offers: _free(l).offers,
      passes: [
        OwnedPass(
            productId: 'paris_pass_7d',
            label: _cjk(l) ? '巴黎' : 'Paris',
            days: 7,
            state: 'active'),
      ],
    );

// ---------------------------------------------------------------------------
// 页面清单：名字 → (overrides, 页面)
// ---------------------------------------------------------------------------
typedef _Page = ({List<Override> Function(Locale) overrides, Widget page});

List<Override> _common(Locale l, Entitlements ent) => [
      currentUserProvider
          .overrideWith((ref) => _LoggedOut(AuthRepository(Dio()))),
      benefitsStateProvider.overrideWith(_Benefits.new),
      entitlementsProvider.overrideWith((ref) async => ent),
      museumEntitlementsProvider.overrideWith((ref, _) async => ent),
      museumsListProvider.overrideWith((_) async => _museums(l)),
      deviceLocationProvider.overrideWith((ref) async => null),
      nearbyProvider
          .overrideWith((ref) async => const Nearby(NearbyMode.none, [])),
      historyProvider.overrideWith(_NoHistory.new),
      passHistoryProvider.overrideWith((ref) async => const <PassRecord>[]),
      passPriceProvider.overrideWith((ref, _) async => '€7.99'),
      objectContentProvider.overrideWith((ref, _) async => _content(l)),
    ];

final Map<String, _Page> _pages = {
  'login': (overrides: (l) => _common(l, _free(l)), page: const LoginPage()),
  'home': (
    overrides: (l) => _common(l, _free(l)),
    page: const Scaffold(body: HomePage())
  ),
  'explore': (
    overrides: (l) => _common(l, _free(l)),
    page: const Scaffold(body: ExplorePage())
  ),
  'guide': (
    overrides: (l) => _common(l, _free(l)),
    page: const GuidePage(args: GuideArgs(slug: 'orsay', qid: 'Q1'))
  ),
  'benefits_free': (
    overrides: (l) => _common(l, _free(l)),
    page: const BenefitsPage()
  ),
  'benefits_active': (
    overrides: (l) => _common(l, _active(l)),
    page: const BenefitsPage()
  ),
  'settings_free': (
    overrides: (l) => _common(l, _free(l)),
    page: const Scaffold(body: SettingsPage())
  ),
  'camera': (overrides: (l) => _common(l, _free(l)), page: const CameraPage()),
  'rec_candidates': (
    overrides: (l) => [
          ..._common(l, _free(l)),
          recognitionNotifierProvider.overrideWith(() =>
              _FixedRec(RecognitionCandidates(_candidates(l), null, 'orsay'))),
        ],
    page: const CameraPage()
  ),
  'rec_unrecognized': (
    overrides: (l) => [
          ..._common(l, _free(l)),
          recognitionNotifierProvider.overrideWith(() =>
              _FixedRec(const RecognitionUnrecognized(null, null, 'orsay'))),
        ],
    page: const CameraPage()
  ),
  'rec_error': (
    overrides: (l) => [
          ..._common(l, _free(l)),
          recognitionNotifierProvider
              .overrideWith(() => _FixedRec(const RecognitionError('timeout'))),
        ],
    page: const CameraPage()
  ),
  'rec_quota': (
    overrides: (l) => [
          ..._common(l, _free(l)),
          recognitionNotifierProvider
              .overrideWith(() => _FixedRec(const RecognitionQuotaExceeded())),
        ],
    page: const CameraPage()
  ),
  'paywall': (
    overrides: (l) => _common(l, _free(l)),
    page: const Scaffold(
        body: SingleChildScrollView(child: PaywallSheetContent()))
  ),
  'settings_active': (
    overrides: (l) => _common(l, _active(l)),
    page: const Scaffold(body: SettingsPage())
  ),
};

// ---------------------------------------------------------------------------

const _logical = Size(360, 1400); // 360dp 常见 Android 窄屏；高度给足让列表全渲染
const _dpr = 2.0;

/// 1.3 = 系统「大字体」常见档位；看展人群里调大字号的不少。
const _scales = [1.0, 1.3];
final _boundary = GlobalKey();
final _report = <String>[];

/// 中日文本来就允许任意字间断行；拉丁文/谚文要在空格或连字符处断。
final _wordChar = RegExp(r'[\p{L}\p{N}]', unicode: true);
final _breakAnywhere = RegExp(
    r'[\p{Script=Han}\p{Script=Hiragana}\p{Script=Katakana}]',
    unicode: true);

/// 找出第一个"拦腰断开的单词"，标成 `前半|后半`；没有返回 null。
/// 判据：位置 i 处换行（上游/下游光标不在同一行）且 i 两侧都是单词字符。
String? _midWordBreak(RenderParagraph p, String s) {
  for (var i = 1; i < s.length; i++) {
    final a = s[i - 1], b = s[i];
    if (!_wordChar.hasMatch(a) || !_wordChar.hasMatch(b)) continue;
    if (_breakAnywhere.hasMatch(a) || _breakAnywhere.hasMatch(b)) continue;
    final up = p.getOffsetForCaret(
        TextPosition(offset: i, affinity: TextAffinity.upstream), Rect.zero);
    final down = p.getOffsetForCaret(TextPosition(offset: i), Rect.zero);
    if (up.dy != down.dy) {
      final from = s.lastIndexOf(RegExp(r'\s'), i - 1) + 1;
      final m = RegExp(r'\s').firstMatch(s.substring(i));
      final to = m == null ? s.length : i + m.start;
      return '${s.substring(from, i)}|${s.substring(i, to)}';
    }
  }
  return null;
}

void main() {
  for (final entry in _pages.entries) {
    for (final locale in kAppLocalesInResolutionOrder) {
      for (final scale in _scales) {
        final tag = locale.toLanguageTag();
        final cell = scale == 1.0 ? tag : '$tag@${scale}x';
        testWidgets('${entry.key} · $cell · 不溢出', (t) async {
          await loadRealFonts(t);
          // 测试里没有相机插件：取景页按「没有相机」那一态渲染。
          t.binding.defaultBinaryMessenger.setMockMethodCallHandler(
              const MethodChannel('plugins.flutter.io/camera'),
              (call) async => call.method == 'availableCameras' ? [] : null);
          // 「最近图库」条：相册权限按拒绝处理（2 = PermissionState.denied），静默不显示。
          t.binding.defaultBinaryMessenger.setMockMethodCallHandler(
              const MethodChannel('com.fluttercandies/photo_manager'),
              (call) async => 2);
          // 页面里按 languageProvider 取请求语言；它从这个 key 读用户选择。
          SharedPreferences.setMockInitialValues(
              {'selected_language': localeTag(locale)});
          t.view.physicalSize = _logical * _dpr;
          t.view.devicePixelRatio = _dpr;
          t.platformDispatcher.textScaleFactorTestValue = scale;
          addTearDown(t.platformDispatcher.clearTextScaleFactorTestValue);
          addTearDown(t.view.reset);

          final errors = <String>[];
          final orig = FlutterError.onError;
          FlutterError.onError = (d) => errors.add(d.toString());

          await t.pumpWidget(ProviderScope(
            overrides: entry.value.overrides(locale),
            child: RepaintBoundary(
              key: _boundary,
              child: MaterialApp(
                locale: locale,
                localizationsDelegates: AppLocalizations.localizationsDelegates,
                supportedLocales: AppLocalizations.supportedLocales,
                theme: AppTheme.lightTheme(),
                builder: (context, child) {
                  GmText.locale =
                      Localizations.localeOf(context); // 同 main.dart
                  return child!;
                },
                home: entry.value.page,
              ),
            ),
          ));
          for (var i = 0; i < 5; i++) {
            await t.pump(const Duration(milliseconds: 100));
          }

          final paras = t.allRenderObjects.whereType<RenderParagraph>().toSet();
          final key = '${entry.key} · $cell';
          for (final f
              in t.allRenderObjects.whereType<RenderFittedBox>().toSet()) {
            final c = f.child;
            if (c == null || !c.hasSize || c.size.isEmpty) continue;
            final k = (f.size.width / c.size.width)
                .clamp(0.0, f.size.height / c.size.height);
            if (k >= 0.97) continue;
            final texts = <String>[];
            void visit(RenderObject o) {
              if (o is RenderParagraph) texts.add(o.text.toPlainText());
              o.visitChildren(visit);
            }

            visit(c);
            if (texts.isNotEmpty) {
              _report
                  .add('$key\t缩放\t${k.toStringAsFixed(2)}\t${texts.join(' ')}');
            }
          }
          for (final p in paras) {
            final text = p.text.toPlainText();
            if (p.didExceedMaxLines) {
              _report.add('$key\t截断\t$text');
              continue; // 截断处的换行是省略号造成的，不算断词
            }
            final at = _midWordBreak(p, text);
            if (at != null) _report.add('$key\t断词\t$at');
          }

          await t.runAsync(() async {
            final ro = _boundary.currentContext!.findRenderObject()!
                as RenderRepaintBoundary;
            final img = await ro.toImage(pixelRatio: 1);
            final png = await img.toByteData(format: ui.ImageByteFormat.png);
            final f = File('build/i18n_sweep/${entry.key}/$cell.png');
            await f.create(recursive: true);
            await f.writeAsBytes(png!.buffer.asUint8List());
          });

          // 拆树再断言：页面里的计时器/动画不留到下一格。
          await t.pumpWidget(const SizedBox());
          // 先还原再 expect，否则断言失败时 binding 卡死整个进程。
          FlutterError.onError = orig;
          expect(errors.where((e) => e.contains('overflowed')), isEmpty,
              reason: errors.join('\n---\n'));
        });
      }
    }
  }

  tearDownAll(() {
    File('build/i18n_sweep/report.tsv')
      ..createSync(recursive: true)
      ..writeAsStringSync(
          '${_report.map((l) => l.replaceAll('\n', '⏎')).join('\n')}\n');
  });
}
