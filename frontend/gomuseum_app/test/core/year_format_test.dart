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

  // 以下样本全部取自 prod 真实值（每种形态各一条），不是编的。
  group('Joconde 存量脏串归一化', () {
    test('约 N 年 → c. N（保住"约"这层不确定性，不谎报成确定年份）', () {
      expect(formatYear('1832 vers', en), 'c. 1832');
      // 尾部 tirage 是印制年不是创作年，丢掉是归位
      expect(formatYear('1860 vers,1928 tirage', en), 'c. 1860');
    });

    test('N 至 M 年间 → N–M（en dash）', () {
      expect(formatYear('1829 entre,1831 et', en), '1829–1831');
      expect(formatYear('1865 entre,1881 et,1931 tirage', en), '1865–1881');
      expect(formatYear('1854-1856', en), '1854–1856');
    });

    test('与界面语言无关：归一化结果对十种语言一致', () {
      expect(formatYear('1832 vers', zh), 'c. 1832');
      expect(formatYear('1829 entre,1831 et', zh), '1829–1831');
    });
  });

  group('表外形态一律原样 —— 猜出来的年代比读着别扭的糟糕得多', () {
    // avant/après/ou/(?) 没有通用的语言中立记号，不强行处理。
    const untouched = [
      '1859 avant',
      '1864 après',
      '1901 (?)',
      '1911,?',
      '1898 après,?',
      '1897 avant,?',
      '1870 (?),1871 (?)',
      '1876 vers,?',
      '1878 vers,1879 vers',
      '1867 vers,1868 ou',
      '1915 vers,1917 avant',
      '1906 vers,1907 et',
      '1899 vers,1900 ET',
      '1911 vers,1912 ou,1914 et',
      '1881 vers,1882 ou,?',
      '1886 vers,1889,1931 tirage',
      '1924,1928 ou,?',
      '1889,1922 tirage',
      '1873 entre,1878 et,?',
      '1878 avant,1882 entre,1895 et,1931 tirage',
    ];
    for (final s in untouched) {
      test('原样：$s', () => expect(formatYear(s, en), s));
    }
  });

  test('负数不被脏串规则误吃', () {
    expect(formatYear('-140 vers', en), '-140 vers');
  });

  test('空白', () {
    expect(formatYear('', en), '');
    expect(formatYear('  -140  ', en), '140 BC');
  });
}
