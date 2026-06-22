/// GoMuseum 设置页 — 暖纸手册定稿（FinalSettings）
///
/// 门票式额度卡 + 01 通用 / 02 账户 / 03 支持与法律分区 + 版本脚注。
library;

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:gomuseum_app/features/auth/domain/user.dart';
import 'package:gomuseum_app/features/auth/presentation/auth_provider.dart';
import 'package:gomuseum_app/features/payment/presentation/providers/benefits_provider.dart';
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
    final authState = ref.watch(currentUserProvider);
    final benefits = ref.watch(benefitsStateProvider);

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
                    '设 置',
                    style: GmText.serif(
                        size: 21, weight: FontWeight.w700, letterSpacing: 4),
                  ),
                  const SizedBox(height: 8),
                  const GmDiamond(width: 110),
                ],
              ),
            ),
            const SizedBox(height: 16),
            _quotaCard(gm, benefits.value?.totalQuota),
            const SizedBox(height: 20),
            const GmSectionHead(number: '01', label: '通用'),
            const SizedBox(height: 4),
            _row(
              gm: gm,
              icon: GmIcons.globe,
              label: '讲解语言',
              value: '简体中文',
              onTap: () => _comingSoon('多语言切换'),
            ),
            _row(
              gm: gm,
              icon: GmIcons.download,
              label: '离线馆包',
              value: '即将上线',
              onTap: () => _comingSoon('离线馆包'),
            ),
            _toggleRow(
              gm: gm,
              icon: GmIcons.photo,
              label: '自动保存照片',
              value: _autoSavePhoto,
              onChanged: (v) => setState(() => _autoSavePhoto = v),
            ),
            _row(
              gm: gm,
              icon: GmIcons.volume,
              label: 'TTS 音色',
              value: '沉稳 · 女声',
              onTap: () => _comingSoon('音色选择'),
            ),
            const SizedBox(height: 12),
            const GmSectionHead(number: '02', label: '账户'),
            const SizedBox(height: 4),
            ..._accountRows(gm, authState),
            const SizedBox(height: 12),
            const GmSectionHead(number: '03', label: '支持与法律'),
            const SizedBox(height: 4),
            _row(
              gm: gm,
              icon: GmIcons.heart,
              label: '鼓励我们',
              onTap: () => _comingSoon('应用商店评分'),
            ),
            _row(
              gm: gm,
              icon: GmIcons.shield,
              label: '隐私政策',
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
                  Text('免费识别额度',
                      style: GmText.sans(
                          size: 11.5, letterSpacing: 1, color: gm.sub)),
                  const SizedBox(height: 4),
                  Text.rich(
                    TextSpan(
                      text: '剩余 ${quota?.toString() ?? '—'} ',
                      style: GmText.serif(size: 18, weight: FontWeight.w700),
                      children: [
                        TextSpan(
                          text: '/ $_freeQuotaTotal 次',
                          style: GmText.serif(size: 13, color: gm.faint),
                        ),
                      ],
                    ),
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
                  '升级',
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
    return authState.when(
      data: (user) {
        if (user == null) {
          return [
            _row(
              gm: gm,
              icon: GmIcons.user,
              label: '登录 / 绑定账号',
              value: '未登录',
              onTap: () => context.push('/login'),
            ),
          ];
        }
        return [
          _row(
            gm: gm,
            icon: GmIcons.user,
            label: user.username ?? '用户',
            value: user.email ?? '未绑定邮箱',
          ),
          _row(
            gm: gm,
            icon: GmIcons.close,
            label: '登出',
            labelColor: GmColors.error,
            onTap: _handleLogout,
          ),
          _row(
            gm: gm,
            icon: GmIcons.shield,
            label: '删除账号',
            labelColor: GmColors.error,
            onTap: _handleDeleteAccount,
          ),
        ];
      },
      loading: () => [
        _row(gm: gm, icon: GmIcons.user, label: '加载中…'),
      ],
      error: (_, __) => [
        _row(
          gm: gm,
          icon: GmIcons.user,
          label: '登录 / 绑定账号',
          value: '未登录',
          onTap: () => context.push('/login'),
        ),
      ],
    );
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
      child: SizedBox(
        height: 48,
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
            if (onTap != null) GmIcon(GmIcons.chevR, size: 16, color: gm.faint),
          ],
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
    return SizedBox(
      height: 48,
      child: Row(
        children: [
          GmIcon(icon, size: 19, color: gm.sub),
          const SizedBox(width: 13),
          Expanded(child: Text(label, style: GmText.sans(size: 14))),
          GmToggle(value: value, onChanged: onChanged),
        ],
      ),
    );
  }

  void _comingSoon(String feature) {
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text('$feature即将开放')),
    );
  }

  void _showPrivacyPolicy() {
    final gm = context.gm;
    showDialog<void>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        backgroundColor: gm.surface,
        title: Text('隐私政策',
            style: GmText.serif(size: 16, weight: FontWeight.w700)),
        content: Text(
          '照片默认不上传原图，识别数据仅作临时处理；'
          '你可以随时删除账户与数据。完整条款将在正式发布时提供。',
          style: GmText.sans(size: 13, height: 1.7),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(dialogContext),
            child: Text('知道了', style: GmText.sans(size: 13)),
          ),
        ],
      ),
    );
  }

  Future<void> _handleDeleteAccount() async {
    final gm = context.gm;
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        backgroundColor: gm.surface,
        title: Text('永久删除账号？',
            style: GmText.serif(size: 16, weight: FontWeight.w700)),
        content: Text(
          '将删除你的账号资料与剩余额度，此操作不可恢复。',
          style: GmText.sans(size: 13, height: 1.7),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(dialogContext, false),
            child: Text('取消', style: GmText.sans(size: 13, color: gm.sub)),
          ),
          TextButton(
            onPressed: () => Navigator.pop(dialogContext, true),
            child: Text('永久删除',
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
        const SnackBar(content: Text('删除失败，请稍后再试')),
      );
    }
  }

  Future<void> _handleLogout() async {
    final gm = context.gm;
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        backgroundColor: gm.surface,
        title: Text('确认登出',
            style: GmText.serif(size: 16, weight: FontWeight.w700)),
        content: Text('确定要登出吗？', style: GmText.sans(size: 13)),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(dialogContext, false),
            child: Text('取消', style: GmText.sans(size: 13, color: gm.sub)),
          ),
          TextButton(
            onPressed: () => Navigator.pop(dialogContext, true),
            child:
                Text('确定', style: GmText.sans(size: 13, color: GmColors.error)),
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
