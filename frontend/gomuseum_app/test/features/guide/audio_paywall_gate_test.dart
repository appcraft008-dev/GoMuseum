/// 撞墙时的**分档顺序**。这个顺序错一次就是真金白银的损失。
///
/// 2026-09-02 真机事故:已付费(purchased_not_activated)的用户,在"免费试听
/// 那一件"上永远等不到激活确认框 —— 因为 canPlayAudio 先返回 true 把他当免费
/// 用户放行了。他点多少次都只撞后端 402(免费试听只覆盖主讲解段,问答段不在内),
/// 最后以为没买成功,**又买了一次**。
///
/// 所以这里锁死的不是"哪些分支存在",而是**它们的先后**。
import 'package:flutter_test/flutter_test.dart';
import 'package:gomuseum_app/features/payment/data/entitlements.dart';

/// 撞墙分档的结果。与 GuideAudioPlayer._blockedByPaywall 的分支一致。
enum Gate {
  /// 放行,直接播
  play,

  /// 弹「开始你的 7 天通票?」
  activate,

  /// 弹付费墙(轻提示条或完整购买页)
  paywall,
}

/// 与 GuideAudioPlayer._blockedByPaywall 的判断顺序一致。
Gate gateFor(Entitlements? ent, String qid) {
  if (ent == null) return Gate.play; // 权益没加载完不拦,后端才是真闸
  // ⭐ 必须排在 canPlayAudio 之前
  if (ent.isPurchasedNotActivated) return Gate.activate;
  if (ent.canPlayAudio(qid)) return Gate.play;
  return Gate.paywall;
}

const _freeTrialQid = 'Q3937645'; // 事故当天那件:保罗·纪尧姆肖像

Entitlements _pending({String? freeQid}) => Entitlements(
      state: 'purchased_not_activated',
      canPurchase: true,
      canRecognize: true,
      canAudioAny: false,
      freeAudioQid: freeQid,
    );

void main() {
  group('已购未激活 → 一律先弹激活确认', () {
    test('⭐ 即使这一件正是免费试听件(事故复现)', () {
      expect(
        gateFor(_pending(freeQid: _freeTrialQid), _freeTrialQid),
        Gate.activate,
      );
    });

    test('其他作品上同样弹激活,不弹购买页', () {
      expect(
          gateFor(_pending(freeQid: _freeTrialQid), 'Q12418'), Gate.activate);
    });

    test('还没认领免费试听时也一样', () {
      expect(gateFor(_pending(), 'Q12418'), Gate.activate);
    });
  });

  group('没买过的人 → 分档不变', () {
    Entitlements free({String? claimed}) => Entitlements(
          state: 'not_purchased',
          canPurchase: true,
          canRecognize: true,
          canAudioAny: false,
          freeAudioQid: claimed,
        );

    // 免费首件的认领时机是**首次识别成功后自动播放**(见后端
    // entitlement_service.claim_free_audio 的注释),不是浏览到哪件就送哪件。
    // 所以没识别过的人在讲解页点播放,拿到的是付费墙,不是免费试听。
    test('未认领 → 付费墙(免费名额从识别流程里发,不从浏览发)', () {
      expect(gateFor(free(), 'Q12418'), Gate.paywall);
    });

    test('重看已认领的那件 → 放行(可无限重播)', () {
      expect(gateFor(free(claimed: 'Q12418'), 'Q12418'), Gate.play);
    });

    test('第二件 → 付费墙', () {
      expect(gateFor(free(claimed: 'Q12418'), 'Q151952'), Gate.paywall);
    });
  });

  test('通票生效 → 每件都放行', () {
    const active = Entitlements(
      state: 'active',
      canPurchase: true,
      canRecognize: true,
      canAudioAny: true,
    );
    expect(gateFor(active, '随便哪件'), Gate.play);
  });

  test('权益未加载 → 不拦(后端 402 才是真闸)', () {
    expect(gateFor(null, 'Q12418'), Gate.play);
  });
}
