/// 防买错城市的两个加法字段:`offers[].recommended`、`passes[].exchange_to`。
/// 老后端没有 → 不推荐任何一张、不给换(退化成旧行为,不猜)。
import 'package:flutter_test/flutter_test.dart';
import 'package:gomuseum_app/features/payment/data/pass_offer.dart';
import 'package:gomuseum_app/features/payment/presentation/widgets/paywall_sheet.dart';

void main() {
  test('recommended / exchange_to 解析,缺省 = 不推荐、不可换', () {
    expect(
        PassOffer.fromJson({'product_id': 'nl', 'recommended': true})!
            .recommended,
        isTrue);
    expect(PassOffer.fromJson({'product_id': 'nl'})!.recommended, isFalse);
    expect(
        OwnedPass.fromJson({
          'product_id': 'paris',
          'exchange_to': ['nl', 3, null]
        })!
            .exchangeTo,
        ['nl']);
    expect(OwnedPass.fromJson({'product_id': 'paris'})!.exchangeTo, isEmpty);
  });

  test('⭐ 购买路由:馆内没票只说暂未开售,绝不退回列出所有城市', () {
    expect(benefitsRoute('nl_pass_7d'), '/benefits?pass=nl_pass_7d');
    expect(benefitsRoute('nl_pass_7d', buy: true),
        '/benefits?pass=nl_pass_7d&buy=1');
    // 在馆里、这家馆没票:`?pass=` 空 = 什么都不卖(不是"不知道在哪,全列")
    expect(benefitsRoute(null, inMuseum: true), '/benefits?pass=');
    expect(benefitsRoute(null, inMuseum: true, buy: true), '/benefits?pass=');
    // 真不知道在哪家馆(首页/全局识别):全列,后端已按足迹排序
    expect(benefitsRoute(null), '/benefits');
  });
}
