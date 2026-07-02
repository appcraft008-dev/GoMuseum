/// GoMuseum 设置页 — 暖纸手册定稿（FinalSettings）
///
/// 门票式额度卡 + 01 通用 / 02 账户 / 03 支持与法律分区 + 版本脚注。
library;

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:gomuseum_app/core/theme/theme_mode_provider.dart';
import 'package:gomuseum_app/features/auth/domain/user.dart';
import 'package:gomuseum_app/features/auth/presentation/auth_provider.dart';
import 'package:gomuseum_app/features/payment/presentation/providers/benefits_provider.dart';
import 'package:gomuseum_app/features/settings/presentation/providers/language_provider.dart';
import 'package:gomuseum_app/l10n/app_localizations.dart';
import 'package:gomuseum_app/theme/gm_palette.dart';
import 'package:gomuseum_app/theme/gm_theme_x.dart';
import 'package:gomuseum_app/ui/gm/gm.dart';

class SettingsPage extends ConsumerStatefulWidget {
  const SettingsPage({super.key});

  @override
  ConsumerState<SettingsPage> createState() => _SettingsPageState();
}

class _SettingsPageState extends ConsumerState<SettingsPage> {
  /// 自动保存照片（偏好持久化接入前仅会话内有效）
  bool _autoSavePhoto = false;

  static const int _freeQuotaTotal = 10;

  @override
  Widget build(BuildContext context) {
    final gm = context.gm;
    final l10n = AppLocalizations.of(context)!;
    final authState = ref.watch(currentUserProvider);
    final benefits = ref.watch(benefitsStateProvider);
    final currentLocale = ref.watch(languageProvider);

    return SafeArea(
      bottom: false,
      child: SingleChildScrollView(
        padding: const EdgeInsets.fromLTRB(26, 16, 26, 12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Center(
              child: Column(
                children: [
                  Text(
                    l10n.settingsTitle,
                    style: GmText.serif(
                        size: 21,
                        weight: FontWeight.w700,
                        letterSpacing: context.gmLetterSpacing(4)),
                  ),
                  const SizedBox(height: 8),
                  const GmDiamond(width: 110),
                ],
              ),
            ),
            const SizedBox(height: 16),
            _quotaCard(gm, benefits.value?.totalQuota),
            const SizedBox(height: 20),
            GmSectionHead(number: '01', label: l10n.secGeneral),
            const SizedBox(height: 4),
            _row(
              gm: gm,
              icon: GmIcons.globe,
              label: l10n.guideLanguage,
              value: languageDisplayName(currentLocale),
              onTap: _pickLanguage,
            ),
            _row(
              gm: gm,
              icon: GmIcons.download,
              label: l10n.offlinePacks,
              value: l10n.comingSoonShort,
              onTap: () => _comingSoon(l10n.offlinePacks),
            ),
            _toggleRow(
              gm: gm,
              icon: GmIcons.photo,
              label: l10n.autoSavePhoto,
              value: _autoSavePhoto,
              onChanged: (v) => setState(() => _autoSavePhoto = v),
            ),
            _row(
              gm: gm,
              icon: GmIcons.volume,
              label: l10n.ttsVoice,
              value: l10n.ttsVoiceValue,
              onTap: () => _comingSoon(l10n.ttsVoiceSelect),
            ),
            _appearanceRow(gm),
            const SizedBox(height: 12),
            GmSectionHead(number: '02', label: l10n.secAccount),
            const SizedBox(height: 4),
            ..._accountRows(gm, authState),
            const SizedBox(height: 12),
            GmSectionHead(number: '03', label: l10n.secSupport),
            const SizedBox(height: 4),
            _row(
              gm: gm,
              icon: GmIcons.heart,
              label: l10n.encourageUs,
              onTap: () => _comingSoon(l10n.appStoreRating),
            ),
            _row(
              gm: gm,
              icon: GmIcons.shield,
              label: l10n.privacyPolicy,
              onTap: _showPrivacyPolicy,
            ),
            const SizedBox(height: 28),
            Center(
              child: Text(
                'GoMuseum 0.1.0 · MVP',
                style: GmText.sans(size: 11, color: gm.faint),
              ),
            ),
            const SizedBox(height: 10),
          ],
        ),
      ),
    );
  }

  Widget _quotaCard(GmPalette gm, int? quota) {
    final l10n = AppLocalizations.of(context)!;
    final remaining = quota ?? 0;
    final progress = (remaining / _freeQuotaTotal).clamp(0.0, 1.0).toDouble();
    return Container(
      decoration: BoxDecoration(
        color: gm.surface,
        border: Border.all(color: gm.line),
      ),
      padding: const EdgeInsets.all(6),
      child: Container(
        decoration: BoxDecoration(
          border: Border.all(color: gm.faint, width: 1),
        ),
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
        child: Row(
          children: [
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(l10n.freeQuota,
                      style: GmText.sans(
                          size: 11.5, letterSpacing: 1, color: gm.sub)),
                  const SizedBox(height: 4),
                  Text(
                    l10n.quotaValue(quota?.toString() ?? '—', _freeQuotaTotal),
                    style: GmText.serif(size: 17, weight: FontWeight.w700),
                  ),
                  const SizedBox(height: 9),
                  Stack(
                    children: [
                      Container(height: 3, color: gm.chipBg),
                      FractionallySizedBox(
                        widthFactor: progress,
                        child: Container(height: 3, color: gm.accent),
                      ),
                    ],
                  ),
                ],
              ),
            ),
            const SizedBox(width: 14),
            GestureDetector(
              onTap: () => context.push('/benefits'),
              child: Container(
                padding:
                    const EdgeInsets.symmetric(horizontal: 18, vertical: 9),
                color: gm.ctaBg,
                child: Text(
                  l10n.upgrade,
                  style: GmText.serif(
                      size: 13,
                      weight: FontWeight.w600,
                      letterSpacing: 2,
                      color: gm.ctaInk),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  List<Widget> _accountRows(GmPalette gm, AsyncValue<User?> authState) {
    final l10n = AppLocalizations.of(context)!;
    return authState.when(
      data: (user) {
        if (user == null) {
          return [
            _row(
              gm: gm,
              icon: GmIcons.user,
              label: l10n.loginBind,
              value: l10n.notLoggedIn,
              onTap: () => context.push('/login'),
            ),
          ];
        }
        return [
          _row(
            gm: gm,
            icon: GmIcons.user,
            label: _accountName(user, l10n),
            value: user.email ?? l10n.noEmailBound,
          ),
          _row(
            gm: gm,
            icon: GmIcons.close,
            label: l10n.logout,
            labelColor: GmColors.error,
            onTap: _handleLogout,
          ),
          _row(
            gm: gm,
            icon: GmIcons.shield,
            label: l10n.deleteAccount,
            labelColor: GmColors.error,
            onTap: _handleDeleteAccount,
          ),
        ];
      },
      loading: () => [
        _row(gm: gm, icon: GmIcons.user, label: l10n.loadingShort),
      ],
      error: (_, __) => [
        _row(
          gm: gm,
          icon: GmIcons.user,
          label: l10n.loginBind,
          value: l10n.notLoggedIn,
          onTap: () => context.push('/login'),
        ),
      ],
    );
  }

  /// 账户显示名。后端给游客生成的用户名带中文前缀「游客_」，非中文界面下
  /// 换成本地化前缀（Guest_/Invité_…），保留其后的唯一后缀。纯呈现层本地化。
  String _accountName(User user, AppLocalizations l10n) {
    final name = user.username;
    if (name == null) return l10n.userDefault;
    const cnPrefix = '游客_';
    if (name.startsWith(cnPrefix)) {
      return '${l10n.guestPrefix}${name.substring(cnPrefix.length)}';
    }
    return name;
  }

  Widget _row({
    required GmPalette gm,
    required GmIcons icon,
    required String label,
    String? value,

    /// null → gm.ink；传入固定色（如 GmColors.error）时使用传入值
    Color? labelColor,
    VoidCallback? onTap,
  }) {
    final effectiveLabelColor = labelColor ?? gm.ink;
    return InkWell(
      onTap: onTap,
      // minHeight 而非死高：长标签（如法语"Packs de musée hors ligne"）折 2 行
      // 时行高自增、不被裁切；单行仍保持 48。
      child: ConstrainedBox(
        constraints: const BoxConstraints(minHeight: 48),
        child: Padding(
          padding: const EdgeInsets.symmetric(vertical: 6),
          child: Row(
            children: [
              GmIcon(icon, size: 19, color: gm.sub),
              const SizedBox(width: 13),
              Expanded(
                child: Text(label,
                    style: GmText.sans(size: 14, color: effectiveLabelColor)),
              ),
              if (value != null) ...[
                Text(value, style: GmText.sans(size: 12.5, color: gm.sub)),
                const SizedBox(width: 8),
              ],
              if (onTap != null)
                GmIcon(GmIcons.chevR, size: 16, color: gm.faint),
            ],
          ),
        ),
      ),
    );
  }

  Widget _toggleRow({
    required GmPalette gm,
    required GmIcons icon,
    required String label,
    required bool value,
    required ValueChanged<bool> onChanged,
  }) {
    return ConstrainedBox(
      constraints: const BoxConstraints(minHeight: 48),
      child: Padding(
        padding: const EdgeInsets.symmetric(vertical: 6),
        child: Row(
          children: [
            GmIcon(icon, size: 19, color: gm.sub),
            const SizedBox(width: 13),
            Expanded(child: Text(label, style: GmText.sans(size: 14))),
            GmToggle(value: value, onChanged: onChanged),
          ],
        ),
      ),
    );
  }

  /// 外观分段控件：浅色 / 深色 / 跟随系统
  /// 激活态：ctaBg 底 + ctaInk 文字；非激活：transparent
  /// 无圆角（border-radius: 0，暖纸设计语言）。
  Widget _appearanceRow(GmPalette gm) {
    final l10n = AppLocalizations.of(context)!;
    final segments = [
      (label: l10n.themeLight, mode: ThemeMode.light),
      (label: l10n.themeDark, mode: ThemeMode.dark),
      (label: l10n.themeSystem, mode: ThemeMode.system),
    ];
    final current = ref.watch(themeModeProvider);

    return SizedBox(
      height: 48,
      child: Row(
        children: [
          GmIcon(GmIcons.sliders, size: 19, color: gm.sub),
          const SizedBox(width: 13),
          Text(l10n.appearance, style: GmText.sans(size: 14, color: gm.ink)),
          const Spacer(),
          Container(
            decoration: BoxDecoration(
              border: Border.all(color: gm.line),
            ),
            child: Row(
              mainAxisSize: MainAxisSize.min,
              children: segments.map((seg) {
                final isActive = current == seg.mode;
                return Material(
                  type: MaterialType.transparency,
                  child: InkWell(
                    onTap: () =>
                        ref.read(themeModeProvider.notifier).setMode(seg.mode),
                    child: Container(
                      height: 40,
                      color: isActive ? gm.ctaBg : Colors.transparent,
                      padding: const EdgeInsets.symmetric(horizontal: 10),
                      alignment: Alignment.center,
                      child: Text(
                        seg.label,
                        style: GmText.serif(
                          size: 12,
                          weight: FontWeight.w600,
                          color: isActive ? gm.ctaInk : gm.sub,
                        ),
                      ),
                    ),
                  ),
                );
              }).toList(),
            ),
          ),
        ],
      ),
    );
  }

  Future<void> _pickLanguage() async {
    final gm = context.gm;
    final current = ref.read(languageProvider);
    final picked = await showModalBottomSheet<Locale>(
      context: context,
      backgroundColor: gm.bg,
      builder: (ctx) => SafeArea(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const SizedBox(height: 8),
            for (final loc in kSupportedLocales)
              ListTile(
                title: Text(languageDisplayName(loc),
                    style: GmText.sans(size: 15, color: gm.ink)),
                trailing: loc.languageCode == current.languageCode
                    ? GmIcon(GmIcons.check, size: 18, color: gm.ink)
                    : null,
                onTap: () => Navigator.of(ctx).pop(loc),
              ),
            const SizedBox(height: 8),
          ],
        ),
      ),
    );
    if (picked != null) {
      await ref.read(languageProvider.notifier).setLanguage(picked);
    }
  }

  void _comingSoon(String feature) {
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
          content:
              Text(AppLocalizations.of(context)!.featureComingSoon(feature))),
    );
  }

  void _showPrivacyPolicy() {
    final gm = context.gm;
    final l10n = AppLocalizations.of(context)!;
    showDialog<void>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        backgroundColor: gm.surface,
        title: Text(l10n.privacyPolicy,
            style: GmText.serif(size: 16, weight: FontWeight.w700)),
        content: Text(
          l10n.privacyBody,
          style: GmText.sans(size: 13, height: 1.7),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(dialogContext),
            child: Text(l10n.gotIt, style: GmText.sans(size: 13)),
          ),
        ],
      ),
    );
  }

  Future<void> _handleDeleteAccount() async {
    final gm = context.gm;
    final l10n = AppLocalizations.of(context)!;
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        backgroundColor: gm.surface,
        title: Text(l10n.deleteAccountQ,
            style: GmText.serif(size: 16, weight: FontWeight.w700)),
        content: Text(
          l10n.deleteAccountBody,
          style: GmText.sans(size: 13, height: 1.7),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(dialogContext, false),
            child:
                Text(l10n.cancel, style: GmText.sans(size: 13, color: gm.sub)),
          ),
          TextButton(
            onPressed: () => Navigator.pop(dialogContext, true),
            child: Text(l10n.permanentDelete,
                style: GmText.sans(size: 13, color: GmColors.error)),
          ),
        ],
      ),
    );
    if (confirmed != true || !mounted) return;

    final ok = await ref.read(currentUserProvider.notifier).deleteAccount();
    if (!mounted) return;
    if (ok) {
      context.go('/login');
    } else {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(l10n.deleteFailed)),
      );
    }
  }

  Future<void> _handleLogout() async {
    final gm = context.gm;
    final l10n = AppLocalizations.of(context)!;
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        backgroundColor: gm.surface,
        title: Text(l10n.confirmLogout,
            style: GmText.serif(size: 16, weight: FontWeight.w700)),
        content: Text(l10n.confirmLogoutBody, style: GmText.sans(size: 13)),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(dialogContext, false),
            child:
                Text(l10n.cancel, style: GmText.sans(size: 13, color: gm.sub)),
          ),
          TextButton(
            onPressed: () => Navigator.pop(dialogContext, true),
            child: Text(l10n.confirmYes,
                style: GmText.sans(size: 13, color: GmColors.error)),
          ),
        ],
      ),
    );

    if (confirmed == true && mounted) {
      await ref.read(currentUserProvider.notifier).logout();
      if (mounted) context.go('/login');
    }
  }
}
