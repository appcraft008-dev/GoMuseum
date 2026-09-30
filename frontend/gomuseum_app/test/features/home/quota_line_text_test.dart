import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gomuseum_app/features/home/presentation/pages/home_page.dart';
import 'package:gomuseum_app/features/payment/data/entitlements.dart';
import 'package:gomuseum_app/features/payment/data/pass_offer.dart';
import 'package:gomuseum_app/l10n/app_localizations_zh.dart';

void main() {
  final l10n = AppLocalizationsZh();
  const zh = Locale('zh');
  Entitlements ent(String state, List<OwnedPass> passes) => Entitlements(
        state: state,
        canPurchase: true,
        canRecognize: true,
        canAudioAny: state == 'active',
        passes: passes,
      );
  OwnedPass pass(String label, String state, {String? title}) => OwnedPass(
      productId: label, label: label, title: title, days: 7, state: state);

  test('生效中:写明票名,优先用后端 title', () {
    expect(
        quotaLineText(
            l10n, ent('active', [pass('巴黎', 'active', title: '卢浮宫单馆票')]), zh),
        '卢浮宫单馆票生效中');
    // 老后端没 title → 前端按 label+days 拼
    expect(quotaLineText(l10n, ent('active', [pass('巴黎', 'active')]), zh),
        '巴黎 7 日通票生效中');
  });

  test('两张生效中的票都列出,未激活的不混进来', () {
    expect(
        quotaLineText(
            l10n,
            ent('active', [
              pass('巴黎', 'active'),
              pass('荷兰', 'active'),
              pass('比利时', 'purchased_not_activated'),
            ]),
            zh),
        '巴黎 7 日通票、荷兰 7 日通票生效中');
  });

  test('待激活:写明票名', () {
    expect(
        quotaLineText(
            l10n,
            ent('purchased_not_activated',
                [pass('荷兰', 'purchased_not_activated')]),
            zh),
        '荷兰 7 日通票已购 · 点击激活');
  });

  test('老后端不给 passes → 通用文案,不编票名', () {
    expect(
        quotaLineText(l10n, ent('active', const []), zh), l10n.homePassActive);
    expect(quotaLineText(l10n, Entitlements.unknown, zh), startsWith('免费识别还剩'));
  });
}
