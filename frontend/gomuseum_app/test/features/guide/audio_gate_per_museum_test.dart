/// 馆内音频闸**按馆**判票(spec 2026-09-28 §2.2 / §3.5)。
///
/// 事故形态:持巴黎票进荷兰的馆。全局权益说「通票生效中、audio_any=true」,
/// 若播放器读的是全局那份 → 本地闸放行 → 去拉音频 → 后端 402,用户看到的是
/// 「按钮坏了」。所以播放器必须读 `museumEntitlementsProvider(slug)`。
///
/// 正反两格都要:只测「拦得住」的话,一个无论如何都拦的实现也会绿。
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gomuseum_app/features/guide/presentation/widgets/guide_audio_player.dart';
import 'package:gomuseum_app/features/payment/data/entitlements.dart';
import 'package:gomuseum_app/l10n/app_localizations.dart';
import 'package:gomuseum_app/ui/gm/gm.dart';

const _parisActive = Entitlements(
  state: 'active',
  canPurchase: true,
  canRecognize: true,
  canAudioAny: true,
);

/// 同一个人、在荷兰的馆里:巴黎票不覆盖,免费额度也用完了。
const _notCoveredHere = Entitlements(
  state: 'not_purchased',
  canPurchase: true,
  canRecognize: true,
  canAudioAny: false,
  freeRecognitionsLeft: 0,
  freeRecognitionsTotal: 5,
);

Widget _app(
        {required Entitlements global,
        required Entitlements here,
        String qid = 'Q9'}) =>
    ProviderScope(
      overrides: [
        entitlementsProvider.overrideWith((ref) async => global),
        museumEntitlementsProvider.overrideWith((ref, _) async => here),
      ],
      child: MaterialApp(
        localizationsDelegates: AppLocalizations.localizationsDelegates,
        supportedLocales: AppLocalizations.supportedLocales,
        locale: Locale('zh'),
        home: Scaffold(
          body: GuideAudioPlayer(slug: 'rijks', qid: qid, language: 'zh'),
        ),
      ),
    );

void main() {
  testWidgets('⭐ 全局有巴黎票、这家馆不覆盖:点播放撞墙,不按全局那份放行', (t) async {
    await t.pumpWidget(_app(global: _parisActive, here: _notCoveredHere));
    await t.pumpAndSettle();
    final l10n = await AppLocalizations.delegate.load(const Locale('zh'));

    await t.tap(find.byWidgetPredicate((w) => w is GmIcon).first);
    await t.pump();
    expect(find.text(l10n.audioLockedHint('7')), findsOneWidget,
        reason: '读了全局权益 → 本地闸放行 → 去拉音频吃 402');
    // 提示条自己会走(见 paywall_sheet 的 persist: false),把计时器跑完
    await t.pump(const Duration(seconds: 5));
    await t.pumpAndSettle();
  });

  testWidgets('对照:这家馆被票覆盖 → 不撞墙', (t) async {
    await t.pumpWidget(_app(global: _notCoveredHere, here: _parisActive));
    await t.pumpAndSettle();
    final l10n = await AppLocalizations.delegate.load(const Locale('zh'));

    await t.tap(find.byWidgetPredicate((w) => w is GmIcon).first);
    await t.pump();
    expect(find.text(l10n.audioLockedHint('7')), findsNothing,
        reason: '按馆的那份说能播,就不该弹墙(过严实现也要能抓到)');
    await t.pump(const Duration(seconds: 1));
  });

  testWidgets('D8:通票过期 → 提示写明「通票已过期」', (t) async {
    final l10n = await AppLocalizations.delegate.load(const Locale('zh'));
    const expired = Entitlements(
      state: 'expired',
      canPurchase: true,
      canRecognize: true,
      canAudioAny: false,
      freeRecognitionsLeft: 0,
    );
    expect(await _hintAfterTap(t, expired, 'Q101'), l10n.audioPassExpiredHint);
  });

  testWidgets('D8:这件解锁过但 7 天已过 → 「免费试听已结束」,不是泛泛的锁', (t) async {
    final l10n = await AppLocalizations.delegate.load(const Locale('zh'));
    const lapsed = Entitlements(
      state: 'not_purchased',
      canPurchase: true,
      canRecognize: true,
      canAudioAny: false,
      freeRecognitionsLeft: 0,
      freeAudioExpired: ['Q102'],
    );
    expect(await _hintAfterTap(t, lapsed, 'Q102'), l10n.audioFreeExpiredHint);
  });

  testWidgets('D8:从没解锁过 → 默认提示,天数取后端给的窗口', (t) async {
    final l10n = await AppLocalizations.delegate.load(const Locale('zh'));
    const never = Entitlements(
      state: 'not_purchased',
      canPurchase: true,
      canRecognize: true,
      canAudioAny: false,
      freeRecognitionsLeft: 0,
      freeAudioExpired: ['Q1'], // 别的件过期了,不影响这件
      freeAudioDays: 3,
    );
    expect(await _hintAfterTap(t, never, 'Q103'), l10n.audioLockedHint('3'));
  });

  testWidgets('D8:免费试听的件在播放条上写剩几天', (t) async {
    final l10n = await AppLocalizations.delegate.load(const Locale('zh'));
    final free = Entitlements(
      state: 'not_purchased',
      canPurchase: true,
      canRecognize: true,
      canAudioAny: false,
      freeAudioQids: const ['Q9'],
      freeAudioUntil: {
        'Q9': DateTime.now().add(const Duration(days: 2, hours: 3))
      },
    );
    await t.pumpWidget(_app(global: free, here: free));
    await t.pumpAndSettle();
    expect(find.text(l10n.audioFreePreviewDays('3')), findsOneWidget);
  });
}

// ---- D8:撞墙要写明原因,免费试听要写剩几天 --------------------------------

/// 播放器按 qid 记「已轻提示过」(静态集合,跨用例共享)——每条用自己的 qid。
Future<String> _hintAfterTap(
    WidgetTester t, Entitlements here, String qid) async {
  await t.pumpWidget(_app(global: here, here: here, qid: qid));
  await t.pumpAndSettle();
  await t.tap(find.byWidgetPredicate((w) => w is GmIcon).first);
  await t.pump();
  final snack = t.widget<SnackBar>(find.byType(SnackBar));
  final text = (snack.content as Text).data!;
  await t.pump(const Duration(seconds: 5));
  await t.pumpAndSettle();
  return text;
}
