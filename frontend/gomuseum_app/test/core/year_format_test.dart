import 'package:flutter/widgets.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gomuseum_app/core/utils/year_format.dart';
import 'package:gomuseum_app/l10n/app_localizations.dart';

void main() {
  final en = lookupAppLocalizations(const Locale('en'));
  final zh = lookupAppLocalizations(const Locale('zh'));

  test('负整数补公元前标注（按界面语言）', () {
    expect(formatYear('-140', en), '140 BC');
    expect(formatYear('-175', en), '175 BC');
    expect(formatYear('-1', en), '1 BC');
    expect(formatYear('-140', zh), '公元前140年');
  });

  test('公元后原样', () {
    expect(formatYear('1503', en), '1503');
    expect(formatYear('1503', zh), '1503');
  });

  test('非纯数字原样（法语脏串是另一个问题，不在这里处理）', () {
    expect(formatYear('1853 vers', en), '1853 vers');
    expect(formatYear('1896 entre,1911 et,1931 tirage', en),
        '1896 entre,1911 et,1931 tirage');
    expect(formatYear('1855-1856', en), '1855-1856');
    expect(formatYear('-140 vers', en), '-140 vers');
  });

  test('空白', () {
    expect(formatYear('', en), '');
    expect(formatYear('  -140  ', en), '140 BC');
  });
}
