import 'package:gomuseum_app/l10n/app_localizations.dart';

final _bce = RegExp(r'^-(\d+)$');

typedef _Render = String Function(RegExpMatch, AppLocalizations);

/// Joconde 脏串的归一化规则。**只收能确定语义的形态**,表外的一律原样返回
/// —— 猜出来的年代比读着别扭的年代糟糕得多。
///
/// 尾部的 `N tirage` 是**印制年**不是创作年,丢掉是归位不是丢信息
/// (`year` 这一列装的就是创作年代)。
final _joconde = <RegExp, _Render>{
  // 1853 vers → c. 1853(约)。circa 是艺术史通行记法,保住了"约"这层
  // 不确定性 —— 直接写成 1853 等于把估计说成确定。语言中立,不走 l10n。
  RegExp(r'^(\d+) vers$'): (m, _) => 'c. ${m[1]}',
  RegExp(r'^(\d+) vers,\d+ tirage$'): (m, _) => 'c. ${m[1]}',
  // 1896 entre,1911 et → 1896–1911(区间,en dash)
  RegExp(r'^(\d+) entre,(\d+) et$'): (m, _) => '${m[1]}–${m[2]}',
  RegExp(r'^(\d+) entre,(\d+) et,\d+ tirage$'): (m, _) => '${m[1]}–${m[2]}',
  // 1855-1856 → 1855–1856(连字符换排版用的 en dash)
  RegExp(r'^(\d+)-(\d+)$'): (m, _) => '${m[1]}–${m[2]}',
  // avant/après 没有通用的语言中立记号(`ante`/`post` 是拉丁行话,
  // 普通观众不认),所以这两个走 l10n。
  RegExp(r'^(\d+) avant$'): (m, l) => l.yearBefore(m[1]!),
  RegExp(r'^(\d+) après$'): (m, l) => l.yearAfter(m[1]!),
};

/// 年代显示。`year` 是各目录源的原样透传,两种形态读着像数据错误:
///
/// 1. **负整数**(2933 件):Wikidata `BIND(YEAR(?date))` 对公元前日期就返回
///    负数,`-140` 看着像坏数据 → 按界面语言补公元前标注。
/// 2. **法语编目串**(713 件,全部来自 Joconde):`1853 vers`、
///    `1896 entre,1911 et,1931 tirage` —— 限定词被反序拼在年份后面。
///    归一化覆盖其中 92.6%;剩下的是 `1867 vers,1868 ou`(约1867**或**1868)、
///    `1870 (?),1871 (?)` 这类语义本身就模糊的,**原样留着** ——
///    把"或"压成区间是改写原意。
///
/// ⚠️ 这批脏串**不是存量,会持续产生**:官方 Joconde CSV 里
/// `Millesime_de_creation` 本身就是这个格式(已核对三条具体记录,
/// 与库里完全一致),不是某个中间平台加工出来的。所以 importer 无论换到
/// 哪条通道都照样写进来 —— 真正的治本是**入库时解析**,这里是兜底。
String formatYear(String raw, AppLocalizations l10n) {
  final t = raw.trim();

  final bce = _bce.firstMatch(t);
  if (bce != null) return l10n.yearBce(bce.group(1)!);

  for (final e in _joconde.entries) {
    final m = e.key.firstMatch(t);
    if (m != null) return e.value(m, l10n);
  }

  return t;
}
