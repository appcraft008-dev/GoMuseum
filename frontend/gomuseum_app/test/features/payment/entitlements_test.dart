/// 权益解析:每条对应一个真会出事的场景,不是为覆盖率凑数。
import 'package:flutter_test/flutter_test.dart';
import 'package:gomuseum_app/features/payment/data/entitlements.dart';

void main() {
  test('缺字段不炸 —— 富化/多语言数据天然缺字段,裸强转会整页崩', () {
    // 只给 state,其余全缺(模拟老后端或部分失败的响应)
    final e = Entitlements.fromJson({'state': 'not_purchased'});
    expect(e.canRecognize, isTrue); // 缺 can 时按免费层放行识别
    expect(e.canAudioAny, isFalse); // 但不白送语音
    expect(e.freeRecognitionsLeft, isNull);
    expect(e.freeRecognitionsTotal, isNull);
  });

  test('空响应也不炸', () {
    final e = Entitlements.fromJson({});
    expect(e.state, 'not_purchased');
    expect(e.isActive, isFalse);
  });

  test('通票生效:不显示剩余次数,语音全放行', () {
    final e = Entitlements.fromJson({
      'state': 'active',
      'expires_at': '2026-08-04T10:00:00+00:00',
      'free_recognitions_left': null,
      'free_recognitions_total': null,
      'can': {'recognize': true, 'audio_any': true, 'ai_ask': true},
    });
    expect(e.isActive, isTrue);
    expect(e.freeRecognitionsLeft, isNull);
    expect(e.canPlayAudio('Q12418'), isTrue);
    expect(e.canPlayAudio('随便哪件'), isTrue);
    expect(e.expiresAt, isNotNull);
  });

  test('免费用户:只有已认领的首件能放语音,可重播;第二件锁', () {
    final e = Entitlements.fromJson({
      'state': 'not_purchased',
      'free_recognitions_left': 3,
      'free_recognitions_total': 5,
      'free_audio_qid': 'Q12418',
      'can': {'recognize': true, 'audio_any': false, 'ai_ask': false},
    });
    expect(e.canPlayAudio('Q12418'), isTrue);
    expect(e.canPlayAudio('Q12418'), isTrue, reason: '首件可无限重播');
    expect(e.canPlayAudio('Q151952'), isFalse);
  });

  test('已购未激活 ≠ 生效中 —— 用户常提前几天买,误判会白烧有效期', () {
    final e = Entitlements.fromJson({
      'state': 'purchased_not_activated',
      'expires_at': null,
      'can': {'recognize': true, 'audio_any': false, 'ai_ask': false},
    });
    expect(e.isPurchasedNotActivated, isTrue);
    expect(e.isActive, isFalse);
    expect(e.expiresAt, isNull, reason: '还没开始计时');
  });

  test('分母来自后端,不是前端写死的 10', () {
    final e = Entitlements.fromJson({
      'state': 'not_purchased',
      'free_recognitions_left': 5,
      'free_recognitions_total': 5,
    });
    expect(e.freeRecognitionsTotal, 5);
  });

  test('拿不到权益时按免费层保守回退:不假装有通票', () {
    expect(Entitlements.unknown.isActive, isFalse);
    expect(Entitlements.unknown.canAudioAny, isFalse);
    expect(Entitlements.unknown.canAiAsk, isFalse);
    expect(Entitlements.unknown.canRecognize, isTrue,
        reason: '后端抖动不该把免费用户也挡在识别外');
  });
}
