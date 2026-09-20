import 'package:gomuseum_app/l10n/app_localizations.dart';

final _bce = RegExp(r'^-(\d+)$');

/// 年代显示。后端 `year` 是 Wikidata `BIND(YEAR(?date))` 的原样透传，
/// 公元前日期在那里是**负整数**（prod 上 2933 件，-602750 ~ -1），
/// 直接显示成 "-140" 看着像数据错误 → 这里按界面语言补公元前标注。
///
/// 只认「纯负整数」；其余（"1503"、"1853 vers" 这类法语脏串）一律原样返回。
String formatYear(String raw, AppLocalizations l10n) {
  final t = raw.trim();
  final m = _bce.firstMatch(t);
  return m == null ? t : l10n.yearBce(m.group(1)!);
}
