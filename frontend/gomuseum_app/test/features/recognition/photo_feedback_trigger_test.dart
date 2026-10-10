// S5 「什么时候问用户要照片」的判定(spec ⑦⑧⑨)。隐私敏感:多问一次是打扰,
// 少问一次是丢信号。逐场景钉住,相机页只负责把状态喂进来。
import 'package:flutter_test/flutter_test.dart';
import 'package:gomuseum_app/features/recognition/presentation/pages/camera_page.dart';

String? trig({
  bool fromSearch = false,
  bool reachedChoice = false,
  bool foundAsked = false,
}) =>
    photoFeedbackTriggerOnPick(
      fromSearch: fromSearch,
      reachedChoice: reachedChoice,
      foundAsked: foundAsked,
    );

void main() {
  test('a) 都不是 → 输入编号 → 选中 = found', () {
    expect(trig(fromSearch: true, reachedChoice: true), 'found');
  });

  test('b) 没认出 → 拍说明牌 → 直接认出 = found', () {
    expect(trig(reachedChoice: true), 'found');
  });

  test('作品候选都不是 → 说明牌候选选 B = found(经选择页找到)', () {
    expect(trig(reachedChoice: true), 'found');
  });

  test('d) 作品候选首次就选第 2 名 = 不问(⑨)', () {
    expect(trig(), isNull);
  });

  test('同一张照片「找到了」只问一次', () {
    expect(
        trig(fromSearch: true, reachedChoice: true, foundAsked: true), isNull);
  });

  test('直接命中(没走过选择页)= 不问', () {
    expect(trig(), isNull);
  });

  test('g) 选择页上放弃 = not_found;没走到选择页放弃 = 不问', () {
    expect(
        photoFeedbackTriggerOnRetake(reachedChoice: true, onChoicePage: true),
        'not_found');
    expect(
        photoFeedbackTriggerOnRetake(reachedChoice: false, onChoicePage: true),
        isNull);
    expect(
        photoFeedbackTriggerOnRetake(reachedChoice: true, onChoicePage: false),
        isNull);
  });
}
