import 'package:flutter_test/flutter_test.dart';
import 'package:gomuseum_app/features/home/presentation/pages/home_page.dart';
import 'package:gomuseum_app/features/payment/data/entitlements.dart';
import 'package:gomuseum_app/features/payment/data/pass_offer.dart';
import 'package:gomuseum_app/l10n/app_localizations_zh.dart';

void main() {
  final l10n = AppLocalizationsZh();
  const active = 'active', pending = 'purchased_not_activated';
  Entitlements ent(String state, List<OwnedPass> passes) => Entitlements(
        state: state,
        canPurchase: true,
        canRecognize: true,
        canAudioAny: state == active,
        passes: passes,
      );
  OwnedPass pass(String label, String state, {String? title}) => OwnedPass(
      productId: label, label: label, title: title, days: 7, state: state);

  test('一张生效中:写明票名,优先用后端 title', () {
    expect(
        quotaLineText(l10n, ent(active, [pass('巴黎', active, title: '卢浮宫单馆票')])),
        '卢浮宫单馆票生效中');
    // 老后端没 title → 前端按 label+days 拼
    expect(
        quotaLineText(l10n, ent(active, [pass('巴黎', active)])), '巴黎 7 日通票生效中');
  });

  test('一张生效 + 未激活的:只报在用的那张', () {
    expect(
        quotaLineText(
            l10n,
            ent(active, [
              pass('巴黎', active),
              pass('荷兰', pending),
              pass('比利时', pending),
            ])),
        '巴黎 7 日通票生效中');
  });

  test('多张同状态:只报张数(票名全列在长语言里缩到看不清)', () {
    expect(
        quotaLineText(
            l10n,
            ent(active, [
              pass('巴黎', active),
              pass('荷兰', active),
              pass('比利时', pending),
            ])),
        '2 张通票生效中');
    expect(
        quotaLineText(
            l10n, ent(pending, [pass('巴黎', pending), pass('荷兰', pending)])),
        '2 张通票已购 · 点击激活');
  });

  test('一张待激活:写明票名', () {
    expect(quotaLineText(l10n, ent(pending, [pass('荷兰', pending)])),
        '荷兰 7 日通票已购 · 点击激活');
  });

  test('老后端不给 passes → 通用文案,不编票名', () {
    expect(quotaLineText(l10n, ent(active, const [])), l10n.homePassActive);
    expect(quotaLineText(l10n, Entitlements.unknown), startsWith('免费识别还剩'));
  });
}
