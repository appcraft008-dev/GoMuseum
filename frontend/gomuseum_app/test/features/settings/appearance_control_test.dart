// test/features/settings/appearance_control_test.dart
import 'dart:async';
import 'package:gomuseum_app/l10n/app_localizations.dart';

import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:gomuseum_app/core/theme/theme_mode_provider.dart';
import 'package:gomuseum_app/features/settings/presentation/pages/settings_page.dart';
import 'package:gomuseum_app/features/auth/presentation/auth_provider.dart';
import 'package:gomuseum_app/features/auth/data/auth_repository.dart';
import 'package:gomuseum_app/features/payment/data/entitlements.dart';
import 'package:gomuseum_app/features/payment/presentation/providers/benefits_provider.dart';
import 'package:gomuseum_app/features/payment/domain/entities/user_benefits.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  testWidgets('点「深色」切到 ThemeMode.dark', (tester) async {
    SharedPreferences.setMockInitialValues({});
    final container = ProviderContainer(
      overrides: [
        // Stub auth: skip network — start as logged-out immediately.
        currentUserProvider.overrideWith(
          (ref) => _StubAuthNotifier(AuthRepository(Dio())),
        ),
        // Stub benefits: no network calls.
        benefitsStateProvider.overrideWith(() => _StubBenefitsState()),
        // Stub entitlements: SettingsPage 会 watch 它，不 override 会打真实网络
        // （AuthInterceptor 读 FlutterSecureStorage，测试环境没有平台通道 mock，
        // 会真的挂起，直到 auth_interceptor.dart 的超时兜底触发才结束）。
        entitlementsProvider.overrideWith((ref) async => Entitlements.unknown),
      ],
    );
    addTearDown(container.dispose);

    await tester.pumpWidget(
      UncontrolledProviderScope(
        container: container,
        // Scaffold provides Material ancestor required by InkWell rows.
        child: const MaterialApp(
            localizationsDelegates: AppLocalizations.localizationsDelegates,
            supportedLocales: AppLocalizations.supportedLocales,
            locale: const Locale('zh'),
            home: Scaffold(body: SettingsPage())),
      ),
    );
    // Let _load() in ThemeModeNotifier settle before interacting.
    await tester.pumpAndSettle();

    await tester.tap(find.text('深色'));
    // Allow setMode async work to complete.
    await tester.pumpAndSettle();

    expect(container.read(themeModeProvider), ThemeMode.dark);
  });
}

/// AuthNotifier subclass that skips _loadUser (no network call in ctor).
class _StubAuthNotifier extends AuthNotifier {
  _StubAuthNotifier(super.repository) {
    // Override the loading state with data(null) immediately.
    state = const AsyncValue.data(null);
  }
}

/// BenefitsState stub — returns UserBenefits.none() without network.
class _StubBenefitsState extends BenefitsState {
  @override
  FutureOr<UserBenefits> build() => UserBenefits.none();
}
