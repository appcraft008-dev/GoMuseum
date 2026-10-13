// 「没认出来 / 没找到」两种结局的文案(10-13 用户定):各一行说明,不自相矛盾。
// 读到了墙签文字还没对上时,不能再叫人「拍说明牌」(已经拍过了)。
import 'package:flutter/widgets.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gomuseum_app/l10n/app_localizations.dart';

void main() {
  test('读出墙签没对上:不再叫人拍说明牌;两种结局说明不同', () {
    for (final loc in AppLocalizations.supportedLocales) {
      final l = lookupAppLocalizations(loc);
      expect(l.recLabelNoMatch, isNot(l.recMaybeNotCollected), reason: '$loc');
      expect(l.recNotInCatalog, isNot(l.recNotRecognized), reason: '$loc');
    }
    final zh = lookupAppLocalizations(const Locale('zh'));
    expect(zh.recLabelNoMatch, isNot(contains('说明牌')));
    expect(zh.recNotInCatalog, isNot(contains('收录'))); // 读错字也会走到这,别断言库里没有
  });
}
