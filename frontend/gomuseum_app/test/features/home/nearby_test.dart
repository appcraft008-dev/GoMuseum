/// 「当前在哪座城市」的判定(spec 2026-09-29-home-nearby-explore-by-city §一)。
///
/// 优先级:定位 > 12 小时内的**现场拍照**命中 > 无。每一条都有正反两格:
/// 只测"判得出"的话,一个永远返回第一座城市的实现也会绿。
import 'package:flutter_test/flutter_test.dart';
import 'package:gomuseum_app/features/content/data/models/museum_summary_model.dart';
import 'package:gomuseum_app/features/home/data/nearby.dart';

MuseumSummary _m(String slug, String city, List<double> c) => MuseumSummary(
      slug: slug,
      name: slug,
      nameEn: slug,
      city: city,
      cityEn: city,
      country: city == '巴黎' ? 'FR' : 'NL',
      coordinates: c,
      artworkCount: 1,
    );

final _all = [
  _m('louvre', '巴黎', [48.86111, 2.33583]),
  _m('orsay', '巴黎', [48.85997, 2.32653]),
  _m('rijksmuseum', '阿姆斯特丹', [52.36, 4.88528]),
];
final _now = DateTime(2026, 9, 29, 12);
const _inAmsterdam = (lat: 52.3731, lng: 4.8922); // 水坝广场
const _inTokyo = (lat: 35.68, lng: 139.76);

void main() {
  test('距离:卢浮宫到奥赛不到 1 km,巴黎到阿姆斯特丹约 430 km', () {
    expect(distanceKm(48.86111, 2.33583, 48.85997, 2.32653), lessThan(1));
    expect(distanceKm(48.86, 2.33, 52.36, 4.885), closeTo(430, 15));
  });

  test('有定位:只列 50 km 内的馆,按距离排', () {
    final n = resolveNearby(_all, here: _inAmsterdam, now: _now);
    expect(n.mode, NearbyMode.gps);
    expect(n.museums.map((m) => m.slug), ['rijksmuseum']);
    expect(n.cityKey, '阿姆斯特丹');
  });

  test('定位到了但身边没有我们的馆 → 不冒充附近(往下看现场命中/无)', () {
    final n = resolveNearby(_all, here: _inTokyo, now: _now);
    expect(n.mode, NearbyMode.none);
    expect(n.museums, hasLength(3));
  });

  test('没定位:12 小时内现场命中 → 那家馆所在城市的全部馆', () {
    final n = resolveNearby(_all,
        live: LiveMatch('orsay', _now.subtract(const Duration(hours: 3))),
        now: _now);
    expect(n.mode, NearbyMode.live);
    expect(n.museums.map((m) => m.slug), unorderedEquals(['louvre', 'orsay']));
  });

  test('现场命中超过 12 小时 → 作废(上个月在巴黎不代表现在在巴黎)', () {
    final n = resolveNearby(_all,
        live: LiveMatch('orsay', _now.subtract(const Duration(hours: 13))),
        now: _now);
    expect(n.mode, NearbyMode.none);
  });

  test('定位优先于现场命中:人已到阿姆斯特丹,早上在巴黎拍的不算', () {
    final n = resolveNearby(_all,
        here: _inAmsterdam,
        live: LiveMatch('orsay', _now.subtract(const Duration(hours: 1))),
        now: _now);
    expect(n.cityKey, '阿姆斯特丹');
  });

  test('馆没坐标(老后端)→ 不参与距离排序,也不崩', () {
    final noCoords = [_m('louvre', '巴黎', const [])];
    final n = resolveNearby(noCoords, here: _inAmsterdam, now: _now);
    expect(n.mode, NearbyMode.none);
  });
}
