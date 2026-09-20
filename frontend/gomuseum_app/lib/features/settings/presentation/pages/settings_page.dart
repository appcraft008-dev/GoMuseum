/// GoMuseum 设置页 — 暖纸手册定稿（FinalSettings）
///
/// 门票式额度卡 + 01 通用 / 02 账户 / 03 支持与法律分区 + 版本脚注。
library;

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:gomuseum_app/core/theme/theme_mode_provider.dart';
import 'package:gomuseum_app/features/auth/domain/user.dart';
import 'package:gomuseum_app/features/auth/presentation/auth_provider.dart';
import 'package:gomuseum_app/features/feedback/presentation/widgets/feedback_sheet.dart';
import 'package:gomuseum_app/features/payment/data/entitlements.dart';
import 'package:gomuseum_app/features/settings/presentation/providers/auto_save_photo_provider.dart';
import 'package:gomuseum_app/features/settings/presentation/providers/language_provider.dart';
import 'package:gomuseum_app/l10n/app_localizations.dart';
// photo_manager 已在取景页的插件树里（最近照片条），这里不引入新原生插件。
import 'package:photo_manager/photo_manager.dart';
import 'package:gomuseum_app/theme/gm_palette.dart';
import 'package:gomuseum_app/theme/gm_theme_x.dart';
import 'package:gomuseum_app/ui/gm/gm.dart';

/// 完整隐私政策的网址。App 内只放摘要,完整版在这里 —— Google Play 要求
/// 用户能取得完整政策,而弹窗里塞不下一份完整政策。
///
/// ⛔ **不要为了"点一下就打开"引入 `url_launcher`**:它是原生插件、会改插件树,
/// 而 #434 那个致命缺陷正长在插件树差异的缝里(CI 与出包机解析出不同的树),
/// 只有真机能发现。照 `kSupportEmail` 的做法用剪贴板。
const kPrivacyPolicyUrl = 'https://gomuseum.app/privacy.html';

/// 版本脚注。**不会自动跟着 pubspec 走** —— `package_info_plus` 同样是
/// 原生插件(理由见 [kPrivacyPolicyUrl]),所以这里是手写的。
/// 发版改 pubspec 时必须一起改;忘了会被 `settings_version_test` 拦下。
const kVersionFootnote = 'GoMuseum 1.0.0 (37)';

class SettingsPage extends ConsumerStatefulWidget {
  const SettingsPage({super.key});

  @override
  ConsumerState<SettingsPage> createState() => _SettingsPageState();
}

class _SettingsPageState extends ConsumerState<SettingsPage> {
  @override
  Widget build(BuildContext context) {
    final gm = context.gm;
    final l10n = AppLocalizations.of(context)!;
    final authState = ref.watch(currentUserProvider);
    final ent = ref.watch(entitlementsProvider);
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
            _quotaCard(gm, ent.value),
            const SizedBox(height: 20),
            GmSectionHead(number: '01', label: l10n.secGeneral),
            const SizedBox(height: 4),
            _row(
              gm: gm,
              icon: GmIcons.globe,
              label: l10n.guideLanguage,
              value: languageSettingLabel(
                  currentLocale, l10n.languageFollowSystem),
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
              value: ref.watch(autoSavePhotoProvider),
              onChanged: _setAutoSavePhoto,
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
            // 「鼓励我们」原本要跳应用商店评价,而那条路在 App 内走不通
            // (url_launcher / in_app_review 都是原生插件,见 kPrivacyPolicyUrl 的禁令),
            // 一直挂着 coming soon。换成站内反馈:条目数不变,一条死的变活的。
            // 等以后真能跳商店了,「鼓励我们」再加回来——那时它才有东西可跳。
            _row(
              gm: gm,
              icon: GmIcons.flag,
              label: l10n.fbTitleApp,
              onTap: () => showFeedbackSheet(context, scope: FeedbackScope.app),
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
                kVersionFootnote,
                style: GmText.sans(size: 11, color: gm.faint),
              ),
            ),
            const SizedBox(height: 10),
          ],
        ),
      ),
    );
  }

  /// 额度卡 / 通票卡（同一个位置,按权益状态换内容）。
  ///
  /// ⚠️ 已购用户**不能**再看到「免费识别额度 —/0」和一个「升级」按钮:
  /// 通票生效期间后端把 free_recognitions_left/total 返回 null(不限次),
  /// 照原样渲染就是一张空额度卡 + 一个把人再送进商店的按钮 ——
  /// 用户付了钱、App 从头到尾没有一处告诉他票在手上(2026-09-02 用户提出)。
  ///
  /// [total] 由后端给(/entitlements/me 的 free_recognitions_total)——
  /// 别在前端写死:曾写死 10,后端把免费额度调成 5 后新用户会看到 "5/10"。
  Widget _quotaCard(GmPalette gm, Entitlements? ent) {
    final l10n = AppLocalizations.of(context)!;
    final hasPass =
        ent != null && (ent.isActive || ent.isPurchasedNotActivated);
    final remaining = ent?.freeRecognitionsLeft ?? 0;
    final total = ent?.freeRecognitionsTotal;
    final denominator = (total == null || total <= 0) ? null : total;
    final progress = denominator == null
        ? 0.0
        : (remaining / denominator).clamp(0.0, 1.0).toDouble();

    final String label;
    final String value;
    if (ent != null && ent.isActive) {
      label = l10n.passActive;
      // expires_at 理论上必有,但契约要求不裸取:缺了就只显示状态、不显示日期。
      value = ent.expiresAt == null
          ? l10n.passActive
          : l10n.passExpiresOn(ent.expiresAt!);
    } else if (ent != null && ent.isPurchasedNotActivated) {
      label = l10n.passPendingActivation;
      value = l10n.passActivateHint;
    } else {
      label = l10n.freeQuota;
      value = l10n.quotaValue(
          ent?.freeRecognitionsLeft?.toString() ?? '—', denominator ?? 0);
    }
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
        // 按钮曾和文字同一个 Row(Expanded(文字), 按钮)——按钮按自身文案的固有宽度
        // 占位、不参与压缩。法语/德语「查看权益」按钮文案更长时,Expanded 那侧被
        // 挤到极窄,到期日文本被迫逐字折行(真机/多语言实测发现)。按钮换到文字
        // 下方单独一行,不再与文字共享横向空间,不论语言多长都不会挤压彼此。
        //
        // 🔴 但那一版留下了**两条对齐轴**:文字左对齐、按钮右对齐,同一张小卡片里
        // 各拉各的,语言一换宽度差异就把这个歪斜放大(2026-09-08 真机多语言反馈)。
        // 现在统一成:**文字居中 + 按钮撑满整行**。
        // - 居中呼应页面标题「设 置」那套居中+菱形的视觉语言,票据本来就是居中的;
        // - 按钮撑满则**彻底消掉各语言的宽度差异**——这是根因,不是把它对齐到某一边
        //   就没有了(中文「查看权益」4 个字,西语按钮长一倍多)。
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Text(label,
                textAlign: TextAlign.center,
                style:
                    GmText.sans(size: 11.5, letterSpacing: 1, color: gm.sub)),
            const SizedBox(height: 4),
            Text(
              value,
              textAlign: TextAlign.center,
              style: GmText.serif(size: 17, weight: FontWeight.w700),
            ),
            // 进度条只在免费层有意义:通票不限次,画一根满格或空的槽
            // 都是在暗示一个并不存在的额度。
            if (!hasPass) ...[
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
            const SizedBox(height: 12),
            GestureDetector(
              onTap: () => context.push('/benefits'),
              child: Container(
                padding:
                    const EdgeInsets.symmetric(horizontal: 18, vertical: 9),
                color: gm.ctaBg,
                child: Text(
                  hasPass ? l10n.viewBenefits : l10n.upgrade,
                  textAlign: TextAlign.center,
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

    // 曾是单行 Row(图标+标签, Spacer, 分段控件)——分段控件按内容固有宽度占位、
    // 不参与压缩。德语「Erscheinungsbild」+ 波兰语「Systemowy」这类较长译法会让
    // 标签和三段控件的固有宽度之和超过整行宽度(窄屏实测:溢出 135px)。
    // 改成标签独占一行、分段控件另起一行且三段各 Expanded 平分宽度——分段控件
    // 因此恒好等于卡片宽度,不论文案多长都不会溢出,各语言下结构也保持一致。
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 6),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              GmIcon(GmIcons.sliders, size: 19, color: gm.sub),
              const SizedBox(width: 13),
              Text(l10n.appearance,
                  style: GmText.sans(size: 14, color: gm.ink)),
            ],
          ),
          const SizedBox(height: 10),
          Container(
            decoration: BoxDecoration(
              border: Border.all(color: gm.line),
            ),
            child: Row(
              children: segments.map((seg) {
                final isActive = current == seg.mode;
                return Expanded(
                  child: Material(
                    type: MaterialType.transparency,
                    child: InkWell(
                      onTap: () => ref
                          .read(themeModeProvider.notifier)
                          .setMode(seg.mode),
                      child: Container(
                        height: 40,
                        color: isActive ? gm.ctaBg : Colors.transparent,
                        padding: const EdgeInsets.symmetric(horizontal: 6),
                        alignment: Alignment.center,
                        child: Text(
                          seg.label,
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                          style: GmText.serif(
                            size: 12,
                            weight: FontWeight.w600,
                            color: isActive ? gm.ctaInk : gm.sub,
                          ),
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

  /// 「跟随系统」在弹窗里的哨兵值 —— 直接 pop(null) 会和「用户取消」混淆。
  static const Locale _kFollowSystem = Locale('\u0000follow-system');

  Future<void> _pickLanguage() async {
    final gm = context.gm;
    final l10n = AppLocalizations.of(context)!;
    final current = ref.read(languageProvider);
    final picked = await showModalBottomSheet<Locale>(
      context: context,
      backgroundColor: gm.bg,
      // 语言数已达 10 种，默认半屏会裁掉末尾——可滚动 + 限高。
      isScrollControlled: true,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(18)),
      ),
      builder: (ctx) => SafeArea(
        child: ConstrainedBox(
          constraints:
              BoxConstraints(maxHeight: MediaQuery.of(ctx).size.height * 0.7),
          child: ListView(
            shrinkWrap: true,
            padding: const EdgeInsets.symmetric(vertical: 8),
            children: [
              // 跟随系统排在最前:它是默认值,也是多数人想要的。
              // 用 sentinel 而非 null 回传,因为 pop(null) 与「用户取消」无法区分。
              ListTile(
                title: Text(l10n.languageFollowSystem,
                    style: GmText.sans(size: 15, color: gm.ink)),
                trailing: current == null
                    ? GmIcon(GmIcons.check, size: 18, color: gm.ink)
                    : null,
                onTap: () => Navigator.of(ctx).pop(_kFollowSystem),
              ),
              for (final loc in kSupportedLocales)
                ListTile(
                  title: Text(languageDisplayName(loc),
                      style: GmText.sans(size: 15, color: gm.ink)),
                  // 按完整 tag 比：简体 zh 与繁体 zh-Hant 的 languageCode 都是 'zh'，会误勾。
                  trailing:
                      current != null && localeTag(loc) == localeTag(current)
                          ? GmIcon(GmIcons.check, size: 18, color: gm.ink)
                          : null,
                  onTap: () => Navigator.of(ctx).pop(loc),
                ),
            ],
          ),
        ),
      ),
    );
    if (picked == null) return; // 用户点了空白处取消
    await ref
        .read(languageProvider.notifier)
        .setLanguage(picked == _kFollowSystem ? null : picked);
  }

  /// 打开「自动保存照片」前先要到相册写权限：没权限就写不进去，而开关开着、
  /// 照片一张没存的话用户无从知道为什么。要不到就**不写偏好、开关保持关**。
  /// 关闭时不请求权限（不需要）。
  // ponytail: 权限判断不分平台。Android 10+ 走 MediaStore 其实无需任何权限，
  // 此处一刀切会把「拒了相册读权限但保存本可成功」的机型也挡住 —— 但那批用户
  // 取景页的最近照片条同样是空的，提示他去开权限并不冤；换成分平台判断要引
  // device_info_plus 查 SDK 版本，不值当。
  Future<void> _setAutoSavePhoto(bool enabled) async {
    final notifier = ref.read(autoSavePhotoProvider.notifier);
    if (!enabled) {
      await notifier.setEnabled(false);
      return;
    }
    final ps = await PhotoManager.requestPermissionExtend(
      requestOption: const PermissionRequestOption(
        androidPermission:
            AndroidPermission(type: RequestType.image, mediaLocation: false),
        // iOS 只要「加入」权限，不必读整个相册；Info.plist 需有
        // NSPhotoLibraryAddUsageDescription，缺了会崩。
        iosAccessLevel: IosAccessLevel.addOnly,
      ),
    );
    if (!ps.hasAccess) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(
          content:
              Text(AppLocalizations.of(context)!.autoSavePhotoNeedsAccess)));
      return;
    }
    await notifier.setEnabled(true);
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
        content: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(l10n.privacyBody, style: GmText.sans(size: 13, height: 1.7)),
            const SizedBox(height: 16),
            Text(
              l10n.privacyFullPolicy,
              style: GmText.sans(size: 11, color: gm.faint, letterSpacing: 1),
            ),
            const SizedBox(height: 3),
            // 摘要不是政策。完整版在网上,这里把地址给全 ——
            // 打不开链接的用户至少能照着抄。
            SelectableText(
              kPrivacyPolicyUrl,
              style: GmText.sans(size: 12.5, color: gm.accent, height: 1.5),
            ),
          ],
        ),
        actions: [
          TextButton(
            onPressed: () async {
              await Clipboard.setData(
                  const ClipboardData(text: kPrivacyPolicyUrl));
              if (dialogContext.mounted) Navigator.pop(dialogContext);
              if (mounted) {
                ScaffoldMessenger.of(context)
                  ..clearSnackBars()
                  ..showSnackBar(SnackBar(
                    content: Text(l10n.privacyLinkCopied),
                    duration: const Duration(seconds: 3),
                    // 见 paywall_sheet:带 action 的 SnackBar 默认 persist,
                    // 这条没 action 所以本不必写 —— 但显式写着不吃亏。
                    persist: false,
                  ));
              }
            },
            child: Text(l10n.privacyCopyLink, style: GmText.sans(size: 13)),
          ),
          TextButton(
            onPressed: () => Navigator.pop(dialogContext),
            child: Text(l10n.gotIt, style: GmText.sans(size: 13)),
          ),
        ],
      ),
    );
  }

  /// 删号弹窗要不要点名「通票一并作废」。
  ///
  /// ⚠️ **权益读不到时也要说** —— 「读不到」不等于「没有」(契约 I21)。
  /// 这里宁可对一个没买过票的人多说一句,也不能对一个刚买完票的人漏说:
  /// 前者只是多看一行字,后者是钱付了、票没了、还不知道为什么。
  bool _mayHavePass() {
    final ent = ref.read(entitlementsProvider).valueOrNull;
    if (ent == null || !ent.known) return true;
    return ent.isActive || ent.isPurchasedNotActivated;
  }

  Future<void> _handleDeleteAccount() async {
    final gm = context.gm;
    final l10n = AppLocalizations.of(context)!;
    // 后端 delete_user_account 会把 entitlement 置 revoked;而通票是消耗型商品,
    // 验证成功即被 Google 消耗 —— restorePurchases 之后永远回放不出来,
    // 重装重注册也只能再买一次。契约 I20:没收已付款项必须**事前**披露。
    final body = _mayHavePass() ? l10n.deleteAccountBodyPass : null;
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        backgroundColor: gm.surface,
        title: Text(l10n.deleteAccountQ,
            style: GmText.serif(size: 16, weight: FontWeight.w700)),
        content: Text(
          body == null
              ? l10n.deleteAccountBody
              : '${l10n.deleteAccountBody}\n\n$body',
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
