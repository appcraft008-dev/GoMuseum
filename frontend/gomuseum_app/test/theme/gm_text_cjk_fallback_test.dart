// 中日韩回退字体按 UI 语言选：同一个汉字在简/繁/日的标准字形不同（汉字统一码），
// 回退一律用 SC 时，日文和繁体界面里的汉字会是简体中文写法。
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:gomuseum_app/theme/gm_tokens.dart';

void main() {
  tearDown(() => GmText.locale = null);

  final cases = <Locale?, (TextStyle, TextStyle)>{
    const Locale('ja'): (GoogleFonts.notoSerifJp(), GoogleFonts.notoSansJp()),
    const Locale('ko'): (GoogleFonts.notoSerifKr(), GoogleFonts.notoSansKr()),
    const Locale.fromSubtags(languageCode: 'zh', scriptCode: 'Hant'): (
      GoogleFonts.notoSerifTc(),
      GoogleFonts.notoSansTc()
    ),
    const Locale('zh'): (GoogleFonts.notoSerifSc(), GoogleFonts.notoSansSc()),
    const Locale('fr'): (GoogleFonts.notoSerifSc(), GoogleFonts.notoSansSc()),
    null: (GoogleFonts.notoSerifSc(), GoogleFonts.notoSansSc()),
  };

  cases.forEach((locale, fonts) {
    test('$locale → ${fonts.$1.fontFamily} / ${fonts.$2.fontFamily}', () {
      GmText.locale = locale;
      expect(GmText.serif().fontFamilyFallback, [fonts.$1.fontFamily]);
      expect(GmText.sans().fontFamilyFallback, [fonts.$2.fontFamily]);
    });
  });
}
