// 楼层叫法(审查 I2):后端 level 是欧式楼层(0 = 地面层,1 = 地面往上一层)。
// 中日韩习惯「1 楼 = 地面层」,照搬数字会把人带错楼 → 东亚四语换算,欧语照官方叫法。
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gomuseum_app/features/must_see/presentation/passport_page.dart';
import 'package:gomuseum_app/l10n/app_localizations.dart';

String lv(String tag, int level) {
  final parts = tag.split('_');
  final l = parts.length == 2
      ? Locale.fromSubtags(languageCode: parts[0], scriptCode: parts[1])
      : Locale(tag);
  return levelText(lookupAppLocalizations(l), l.languageCode, level);
}

void main() {
  test('中文:0 → 1 楼,1 → 2 楼,-2 → 地下 2 层', () {
    expect(lv('zh', 0), '1 楼');
    expect(lv('zh', 1), '2 楼');
    expect(lv('zh', -2), '地下 2 层');
    expect(lv('zh_Hant', 1), '2 樓');
  });

  test('日韩同样换算', () {
    expect(lv('ja', 0), '1階');
    expect(lv('ja', -2), '地下2階');
    expect(lv('ko', 1), '2⁠층');
  });

  test('欧语照官方叫法', () {
    expect(lv('en', 0), 'Level 0');
    expect(lv('fr', -2), 'Niveau -2');
  });
}
