/// 韩文按词断行（CSS `word-break: keep-all`）：词内相邻的谚文/字母/数字之间插
/// U+2060（WORD JOINER，不可见、禁止断行）。不含谚文的串原样返回，所以对任何
/// 语言都可以直接套。
///
/// 静态文案已由 `scripts/ko_keep_all.py` 写进 app_ko.arb（两处规则须一致）；
/// 这里给**运行时拼出来的**串用 —— 例如 intl 格式化的日期 "2026년 10월 25일"，
/// 不处理会断成 "2026|년"。
String keepAll(String s) => s.replaceAll(_join, '\u2060');

final _join = RegExp(
    r'(?<=[\uAC00-\uD7A3])(?=[\uAC00-\uD7A30-9A-Za-z{])|(?<=[0-9A-Za-z}])(?=[\uAC00-\uD7A3])');
