/// 设置页脚注里的版本号**不会自动跟着 pubspec 走**。
///
/// 读 pubspec 需要 `package_info_plus`,那是原生插件、会改插件树 ——
/// 而 #434 那个致命缺陷正长在插件树差异的缝里(CI 与出包机解析出不同的树),
/// 只有真机能发现。为一行脚注冒这个险不划算,所以它是手写的常量。
///
/// 手写就会忘:发到 v18 了,脚注上还写着 `GoMuseum 0.1.0 · MVP`
/// (2026-09-04 Play 发版前核查时发现,正式版里显示 MVP 字样)。
/// 这条测试把它和 pubspec 钉在一起,忘了改就红。
library;

import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:gomuseum_app/features/settings/presentation/pages/settings_page.dart';

void main() {
  test('版本脚注与 pubspec.yaml 一致', () {
    final pubspec = File('pubspec.yaml').readAsStringSync();
    final m = RegExp(r'^version:\s*(\S+)\+(\d+)\s*$', multiLine: true)
        .firstMatch(pubspec);
    expect(m, isNotNull, reason: 'pubspec.yaml 里没找到 version: x.y.z+n');

    final name = m!.group(1)!; // 1.0.0
    final code = m.group(2)!; // 18

    expect(kVersionFootnote, contains(name),
        reason: '设置页脚注「$kVersionFootnote」没有 pubspec 的版本名 $name —— '
            '发版改了 pubspec 就要一起改这个常量');
    expect(kVersionFootnote, contains(code),
        reason: '设置页脚注「$kVersionFootnote」没有 pubspec 的 versionCode $code');
  });

  test('脚注不许再出现 MVP / 0.1.0 之类的开发期字样', () {
    for (final ghost in ['MVP', 'beta', 'Beta', 'dev', '0.1.0']) {
      expect(kVersionFootnote.contains(ghost), isFalse,
          reason: '正式版的设置页底部不该显示「$ghost」');
    }
  });

  test('隐私政策链接指向真实的完整政策,不是占位', () {
    expect(kPrivacyPolicyUrl, startsWith('https://'));
    expect(kPrivacyPolicyUrl, contains('gomuseum.app'));
    expect(kPrivacyPolicyUrl, contains('privacy'));
  });
}
