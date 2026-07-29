/// 自动播的**准入**规则。
///
/// 免费首件靠自动播"保证送达":券式设计(给一张待花的券)下,很多用户到最后
/// 压根没用过语音,付费墙就白建了。但反过来 —— 免费用户的第二件如果也自动播,
/// 就变成"一进页面就被推销",是最差的体验。所以准入判断必须精确。
import 'package:flutter_test/flutter_test.dart';
import 'package:gomuseum_app/features/payment/data/entitlements.dart';

/// 与 GuideAudioPlayer._maybeAutoPlay 的准入条件一致。
bool willAutoPlay(Entitlements? ent, String qid) {
  if (ent == null) return false;
  return ent.isActive || ent.freeAudioQid == null || ent.freeAudioQid == qid;
}

Entitlements _free({String? claimed}) => Entitlements(
      state: 'not_purchased',
      canPurchase: false,
      canRecognize: true,
      canAudioAny: false,
      freeAudioQid: claimed,
    );

void main() {
  test('免费用户尚未认领 → 自动播(这就是"保证送达的首体验")', () {
    expect(willAutoPlay(_free(), 'Q12418'), isTrue);
  });

  test('免费用户重看已认领的那一件 → 仍自动播(可无限重播)', () {
    expect(willAutoPlay(_free(claimed: 'Q12418'), 'Q12418'), isTrue);
  });

  test('⭐ 免费用户的第二件 → 不自动播(否则一进页面就撞墙)', () {
    expect(willAutoPlay(_free(claimed: 'Q12418'), 'Q151952'), isFalse);
  });

  test('通票生效 → 每件都自动播(现场"边看边听"的产品形态)', () {
    const active = Entitlements(
      state: 'active',
      canPurchase: true,
      canRecognize: true,
      canAudioAny: true,
    );
    expect(willAutoPlay(active, '随便哪件'), isTrue);
  });

  test('权益还没加载出来 → 不自动播(宁可不响,也不要撞墙)', () {
    expect(willAutoPlay(null, 'Q12418'), isFalse);
  });

  test('已购未激活 → 不自动播(该先弹激活确认,不是静默烧掉有效期)', () {
    const pending = Entitlements(
      state: 'purchased_not_activated',
      canPurchase: true,
      canRecognize: true,
      canAudioAny: false,
    );
    // 未激活时 isActive=false、freeAudioQid=null → 会走免费首件那条路,
    // 由 _blockedByPaywall 弹激活确认,不会静默消耗通票有效期
    expect(pending.isActive, isFalse);
    expect(pending.isPurchasedNotActivated, isTrue);
  });
}
