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
      'can': {'recognize': true, 'audio_any': true},
    });
    expect(e.isActive, isTrue);
    expect(e.freeRecognitionsLeft, isNull);
    expect(e.canPlayAudio('Q12418'), isTrue);
    expect(e.canPlayAudio('随便哪件'), isTrue);
    expect(e.expiresAt, isNotNull);
  });

  test('免费用户:识别过的作品能放语音、可重播;没识别过的锁', () {
    final e = Entitlements.fromJson({
      'state': 'not_purchased',
      'free_recognitions_left': 3,
      'free_recognitions_total': 5,
      'free_audio_qids': ['Q12418', 'Q151952'],
      'can': {'recognize': true, 'audio_any': false},
    });
    expect(e.canPlayAudio('Q12418'), isTrue);
    expect(e.canPlayAudio('Q12418'), isTrue, reason: '可无限重播');
    expect(e.canPlayAudio('Q151952'), isTrue, reason: '识别过的都算,不只第一件');
    expect(e.canPlayAudio('Q4'), isFalse, reason: '没识别过的要票');
  });

  test('一次都还没识别 → 语音全锁(后端也是 denied,两边同一套判据)', () {
    // 2026-09-19 前这里是反的:免费名额是"一张待花的券",`free_audio_qid`
    // 为空被读成「还没用掉,哪件都能听」。规则改成跟着识别走之后,
    // 空清单的含义变成「还没识别过任何作品」—— 同一个 JSON,判断相反。
    final e = Entitlements.fromJson({
      'state': 'not_purchased',
      'free_recognitions_left': 5,
      'free_recognitions_total': 5,
      'free_audio_qids': <String>[],
      'can': {'recognize': true, 'audio_any': false},
    });
    expect(e.canPlayAudio('Q12418'), isFalse);
    expect(e.canPlayAudio('Q151952'), isFalse);
  });

  test('老后端没有这个字段 → 空表,不炸(上线顺序必须后端先行)', () {
    final e = Entitlements.fromJson({
      'state': 'not_purchased',
      'can': {'recognize': true, 'audio_any': false},
    });
    expect(e.freeAudioQids, isEmpty);
    expect(e.canPlayAudio('Q12418'), isFalse);
  });

  test('已解锁的那一件:深度段仍要票 —— 别让"识别过"变成整件解锁', () {
    final e = Entitlements.fromJson({
      'state': 'not_purchased',
      'free_audio_qids': ['Q12418'],
      'can': {'recognize': true, 'audio_any': false},
    });
    expect(e.canPlayAudio('Q12418'), isTrue);
    // 深度段/问答/作者介绍各自独立 TTS,属付费内容。
    // 不判 section 的话前端放行、后端 402,白跑一趟。
    expect(e.canPlayAudio('Q12418', section: 'analysis'), isFalse);
    expect(e.canPlayAudio('Q12418', section: 'qa'), isFalse);
    expect(e.canPlayAudio('Q12418', section: 'artist_bio'), isFalse);
  });

  test('通票生效:深度段也全放行', () {
    final e = Entitlements.fromJson({
      'state': 'active',
      'can': {'recognize': true, 'audio_any': true},
    });
    expect(e.canPlayAudio('随便哪件', section: 'analysis'), isTrue);
  });

  test('已购未激活 ≠ 生效中 —— 用户常提前几天买,误判会白烧有效期', () {
    final e = Entitlements.fromJson({
      'state': 'purchased_not_activated',
      'expires_at': null,
      'can': {'recognize': true, 'audio_any': false},
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
    expect(Entitlements.unknown.canRecognize, isTrue,
        reason: '后端抖动不该把免费用户也挡在识别外');
  });
}
