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

Entitlements _pending({List<String> unlocked = const []}) => Entitlements(
      state: 'purchased_not_activated',
      canPurchase: true,
      canRecognize: true,
      canAudioAny: false,
      freeAudioQids: unlocked,
    );

void main() {
  group('已购未激活 → 一律先弹激活确认', () {
    test('⭐ 即使这一件正是免费解锁的那件(事故复现)', () {
      expect(
        gateFor(_pending(unlocked: [_freeTrialQid]), _freeTrialQid),
        Gate.activate,
      );
    });

    test('其他作品上同样弹激活,不弹购买页', () {
      expect(gateFor(_pending(unlocked: [_freeTrialQid]), 'Q12418'),
          Gate.activate);
    });

    test('一件都还没解锁时也一样', () {
      expect(gateFor(_pending(), 'Q12418'), Gate.activate);
    });
  });

  group('没买过的人 → 分档不变', () {
    Entitlements free({List<String> unlocked = const []}) => Entitlements(
          state: 'not_purchased',
          canPurchase: true,
          canRecognize: true,
          canAudioAny: false,
          freeAudioQids: unlocked,
        );

    // 🔴 这条断言在 2026-09-19 一天之内翻过**两次**,两次都是真机推翻的,
    // 值得把来龙去脉留着 —— 它是"同一份判据只能有一个实现"最贵的一课。
    //
    // 起初:「未认领 → 付费墙」(免费名额从识别流程里发,不从浏览发)。
    //   自动播那侧(audio_autoplay_test)却判"未认领 → 播",而 _maybeAutoPlay
    //   放行后立刻调 _onTap、_onTap 第一件事就是这道闸。两个文件各自手抄了
    //   一份判据、各自绿着,合起来是"识别完自动播,然后弹墙" ——
    //   prod 日志实证:新账号识别成功后 `/audio` 请求**一条都没有**。
    // 改成:「未认领 → 放行」。修好了上面那条,但"免费只有一件"本身仍然与
    //   "免费识别 5 次"对不齐:用户识别第二件、点播放被弹墙。
    // 最终(现在):免费语音**跟着识别走** —— 识别出来的作品都能听,
    //   免费识别次数是唯一的那个数字。于是"浏览进来的不给"这个意图由
    //   解锁清单**天然**表达(没识别过就不在清单里),不再需要靠入口区分
    //   (入口区分本来也拦不住任何人,curl 就能绕过,只拦得住自己的用户)。
    test('识别过的作品 → 放行,可无限重播', () {
      expect(gateFor(free(unlocked: ['Q12418']), 'Q12418'), Gate.play);
    });

    test('识别过的第二件 → 一样放行(免费不再只有一件)', () {
      expect(
          gateFor(free(unlocked: ['Q12418', 'Q151952']), 'Q151952'), Gate.play);
    });

    test('没识别过的 → 付费墙', () {
      expect(gateFor(free(unlocked: ['Q12418']), 'Q151952'), Gate.paywall);
    });

    test('一件都没识别过 → 付费墙', () {
      expect(gateFor(free(), 'Q12418'), Gate.paywall);
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
