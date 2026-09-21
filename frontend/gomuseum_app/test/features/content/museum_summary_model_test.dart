import 'package:flutter_test/flutter_test.dart';
import 'package:gomuseum_app/features/content/data/models/museum_summary_model.dart';

void main() {
  test('A1 标准 shape 解析', () {
    final m = MuseumSummary.fromJson({
      'slug': 'orsay',
      'name': '奥赛博物馆',
      'city': '巴黎',
      'country': 'FR',
      'coordinates': [48.8599, 2.3266],
      'artwork_count': 1400,
    });
    expect(m.slug, 'orsay');
    expect(m.name, '奥赛博物馆');
    expect(m.city, '巴黎');
    expect(m.country, 'FR');
    expect(m.coordinates, [48.8599, 2.3266]);
    expect(m.artworkCount, 1400);
  });

  test('缺字段防御：name→name_zh→slug 回退；坐标缺→空列表；artwork_count 缺→0', () {
    // name 缺，回退 name_zh
    final m1 = MuseumSummary.fromJson({'slug': 'vangogh', 'name_zh': '梵高博物馆'});
    expect(m1.name, '梵高博物馆');
    expect(m1.coordinates, isEmpty);
    expect(m1.artworkCount, 0);

    // name 和 name_zh 均缺，回退 slug
    final m2 = MuseumSummary.fromJson({'slug': 'louvre'});
    expect(m2.name, 'louvre');
    expect(m2.city, '');
    expect(m2.country, '');
  });

  test('artwork_count 为整数型 num 解析', () {
    final m = MuseumSummary.fromJson({
      'slug': 'x',
      'artwork_count': 500,
      'coordinates': [51.5, -0.1],
    });
    expect(m.artworkCount, 500);
    expect(m.coordinates.length, 2);
    expect(m.coordinates[0], closeTo(51.5, 0.001));
  });

  test('cover_image 加法字段(2026-07-20)：解析；空串/缺 → null', () {
    final m = MuseumSummary.fromJson(const {
      'slug': 'orsay',
      'cover_image': 'https://r2/cover_thumb.jpg',
    });
    expect(m.coverImage, 'https://r2/cover_thumb.jpg');

    final empty =
        MuseumSummary.fromJson(const {'slug': 'orsay', 'cover_image': ''});
    expect(empty.coverImage, isNull);

    final old = MuseumSummary.fromJson(const {'slug': 'orsay'});
    expect(old.coverImage, isNull);
  });

  test('name_i18n 加法字段(2026-09-21)：十语馆名；老后端不返回 → 回退两语', () {
    final m = MuseumSummary.fromJson(const {
      'slug': 'louvre',
      'name_zh': '卢浮宫',
      'name_en': 'Louvre Museum',
      'name_i18n': {
        'zh': '卢浮宫',
        'en': 'Louvre Museum',
        'fr': 'Musée du Louvre',
        'ja': 'ルーヴル美術館',
      },
    });
    // 判别式用卢浮宫:橘园/奥赛的 name_en 本身就是法语拼写,拿它们测的话
    // "回退英文名"和"真给了法语名"输出一样,分不开。
    expect(m.localizedName('fr'), 'Musée du Louvre'); // ← 不是 "Louvre Museum"
    expect(m.localizedName('ja'), 'ルーヴル美術館');
    expect(m.localizedName('zh'), '卢浮宫');
    expect(m.localizedName('en'), 'Louvre Museum');
    // 表里没有的语言 → 旧回退链,不返回 null 也不显 slug
    expect(m.localizedName('ko'), 'Louvre Museum');

    // 老后端(无此键)必须与改动前行为完全一致
    final old = MuseumSummary.fromJson(const {
      'slug': 'louvre',
      'name_zh': '卢浮宫',
      'name_en': 'Louvre Museum',
    });
    expect(old.nameI18n, isEmpty);
    expect(old.localizedName('fr'), 'Louvre Museum');
    expect(old.localizedName('zh'), '卢浮宫');
  });

  test('name_i18n 脏值防御：null / 空串 / 非字符串一律跳过,不崩', () {
    // 富化数据天然缺字段,裸强转是出过事故的写法(馆藏页整页崩)。
    final m = MuseumSummary.fromJson(const {
      'slug': 'x',
      'name_en': 'X Museum',
      'name_i18n': {'fr': null, 'de': '', 'ja': 123, 'ko': '박물관'},
    });
    expect(m.nameI18n, const {'ko': '박물관'});
    expect(m.localizedName('fr'), 'X Museum'); // null 值 → 回退,不是显示 "null"
    expect(m.localizedName('ja'), 'X Museum');
    expect(m.localizedName('ko'), '박물관');
  });

  test('name_i18n 不是 Map 时不崩(后端换形状/中间层塞了字符串)', () {
    final m = MuseumSummary.fromJson(const {'slug': 'x', 'name_i18n': 'oops'});
    expect(m.nameI18n, isEmpty);
    expect(m.localizedName('fr'), 'x');
  });
}
