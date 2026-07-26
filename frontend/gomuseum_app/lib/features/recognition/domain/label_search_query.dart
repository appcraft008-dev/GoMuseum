/// 墙签 OCR 文本 → 搜索词。
///
/// 未识别且已拍墙签时给用户一跳直达搜索(此前只有"重拍",是死胡同)。
/// 后端搜索是**子串匹配**,所以必须给一条干净的标题行,不能塞整段 OCR。
///
/// 墙签常见排版是「标题 / 作者 / 年代 / 材质」,标题多在首行;但首行也常是
/// 馆藏号(INV 779 / MR 1234)或年代(1503-1519)。故跳过这两类噪音行,
/// 取第一条像标题的。取不到就给原文——宁可让用户在搜索框里改,也不给空。
library;

/// 噪音行:无字母(年代、编号),或"全大写且很短"(INV、MR 12)。
/// 全大写但较长的(MONA LISA)保留——那多半真是标题。
bool _isNoise(String line) {
  if (!RegExp(r'[A-Za-zÀ-ÿ一-鿿]').hasMatch(line)) return true;
  final hasLower = RegExp(r'[a-zà-ÿ]').hasMatch(line);
  final hasCjk = RegExp(r'[一-鿿]').hasMatch(line);
  return !hasLower && !hasCjk && line.length < 8;
}

String labelSearchQuery(String label) {
  final lines = label
      .split(RegExp(r'[\r\n]+'))
      .map((e) => e.trim())
      .where((e) => e.isNotEmpty)
      .toList();
  for (final line in lines) {
    if (!_isNoise(line)) return line;
  }
  return label.trim();
}
