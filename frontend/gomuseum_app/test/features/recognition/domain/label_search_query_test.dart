import 'package:flutter_test/flutter_test.dart';
import 'package:gomuseum_app/features/recognition/domain/label_search_query.dart';

void main() {
  test('多行墙签取标题行', () {
    const label = 'La Joconde\nLéonard de Vinci\n1503-1519\nHuile sur bois';
    expect(labelSearchQuery(label), 'La Joconde');
  });

  test('跳过馆藏号首行(INV / MR 1234)', () {
    expect(labelSearchQuery('INV\n7\nThe Lacemaker\nVermeer'), 'The Lacemaker');
    expect(labelSearchQuery('MR 1234\nVenus de Milo'), 'Venus de Milo');
  });

  test('跳过纯年代行', () {
    expect(labelSearchQuery('1503-1519\nMona Lisa'), 'Mona Lisa');
  });

  test('全大写但较长的当标题(不是编号)', () {
    expect(labelSearchQuery('MONA LISA\nda Vinci'), 'MONA LISA');
  });

  test('中文墙签正常取首行标题', () {
    expect(labelSearchQuery('蒙娜丽莎\n列奥纳多·达·芬奇\n1503'), '蒙娜丽莎');
  });

  test('已知局限:中文表头(编号/名称)识别不出,会被当标题', () {
    // 噪音规则靠"无小写字母且短"识别编号,对 CJK 无效。欧洲馆墙签无中文,
    // 暂不为此加词表(YAGNI);搜索框可编辑,用户 2 秒能改掉。真上中文馆再说。
    expect(labelSearchQuery('编号\n蒙娜丽莎'), '编号');
  });

  test('单行墙签原样返回(去空白)', () {
    expect(labelSearchQuery('  Venus de Milo  '), 'Venus de Milo');
  });

  test('全是噪音时给原文,不给空(让用户自己改)', () {
    expect(labelSearchQuery('INV\n7'), 'INV\n7');
  });

  test('CRLF 换行也能切', () {
    expect(labelSearchQuery('Mona Lisa\r\nda Vinci'), 'Mona Lisa');
  });
}
