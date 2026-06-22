// test/core/theme/theme_mode_provider_test.dart
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:gomuseum_app/core/theme/theme_mode_provider.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  test('默认 system；setMode 持久化', () async {
    SharedPreferences.setMockInitialValues({});
    final c = ProviderContainer();
    addTearDown(c.dispose);
    expect(c.read(themeModeProvider), ThemeMode.system);
    await c.read(themeModeProvider.notifier).setMode(ThemeMode.dark);
    expect(c.read(themeModeProvider), ThemeMode.dark);
    final sp = await SharedPreferences.getInstance();
    expect(sp.getString('theme_mode'), 'dark');
  });
}
