/// D8 的三个加法字段:解析对、老后端不带时有安全回退。
import 'package:flutter_test/flutter_test.dart';
import 'package:gomuseum_app/features/payment/data/entitlements.dart';

void main() {
  test('解析到期时刻/已过期列表/窗口天数', () {
    final e = Entitlements.fromJson({
      'state': 'not_purchased',
      'free_audio_until': {'Q1': '2026-10-06T08:00:00+00:00', 'bad': 'x'},
      'free_audio_expired': ['Q2'],
      'free_audio_days': 3,
      'offers': [
        {
          'product_id': 'nl_pass_7d',
          'days': 7,
          'label': '荷兰',
          'covers': ['A']
        }
      ],
      'passes': [
        {
          'product_id': 'paris_pass_7d',
          'label': '巴黎',
          'days': 7,
          'state': 'active'
        }
      ],
    });
    expect(e.freeAudioUntil.keys, ['Q1'], reason: '坏时间串丢掉,不抛');
    expect(e.freeAudioUntil['Q1']!.toUtc(), DateTime.utc(2026, 10, 6, 8));
    expect(e.freeAudioExpired, ['Q2']);
    expect(e.freeAudioDays, 3);
    expect(e.offers.single.productId, 'nl_pass_7d');
    expect(e.passes.single.isActive, isTrue);
  });

  test('老后端不带这些字段:空表 + 默认 7 天,不崩', () {
    final e = Entitlements.fromJson({'state': 'active'});
    expect(e.freeAudioUntil, isEmpty);
    expect(e.freeAudioExpired, isEmpty);
    expect(e.freeAudioDays, 7);
    expect(e.offers, isEmpty);
    expect(e.passes, isEmpty);
  });
}
