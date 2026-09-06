/// 登录页 — 暖纸手册风格（设计稿外页面，按定稿风格补齐）
import 'package:gomuseum_app/core/router/app_router.dart';
import 'package:flutter/foundation.dart'
    show defaultTargetPlatform, TargetPlatform;
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:google_sign_in/google_sign_in.dart';
import 'package:gomuseum_app/features/payment/presentation/providers/benefits_provider.dart';
import 'package:gomuseum_app/theme/gm_palette.dart';
import 'package:gomuseum_app/theme/gm_theme_x.dart';
import 'package:gomuseum_app/l10n/app_localizations.dart';
import 'package:gomuseum_app/ui/gm/gm.dart';
import 'package:sign_in_with_apple/sign_in_with_apple.dart';
import 'auth_provider.dart';

class LoginPage extends ConsumerStatefulWidget {
  const LoginPage({super.key, this.upgrading = false});

  /// 这次是不是**主动**来换身份的（游客转正 / 收据冲突换账号）。
  ///
  /// 由路由从 `?upgrade=1` 解析后传进来 —— 页面不自己去读
  /// `GoRouterState.of(context)`：那会让 LoginPage 硬依赖 GoRouter 祖先，
  /// 任何不在路由里渲染它的地方（包括几个既有测试）都会当场抛
  /// `The parent route must be a page route`。解析 URL 是路由的活。
  ///
  /// ⚠️ 判据是**这次导航的意图**，不是当前用户的身份：守卫在冷启动时也会把人
  /// 弹到这一页（登录态还没加载完），那次到达不是用户的意图。按身份判会让每个
  /// 冷启动的游客都看不到游客按钮 —— 而他本来就该被直接送回首页。
  final bool upgrading;

  @override
  ConsumerState<LoginPage> createState() => _LoginPageState();
}

class _LoginPageState extends ConsumerState<LoginPage> {
  final _formKey = GlobalKey<FormState>();
  final _emailController = TextEditingController();
  final _passwordController = TextEditingController();
  // 「忘记密码」弹窗里那个输入框。**由页面持有,不在弹窗里就地 new**:
  // 弹窗关闭后还有一段退场动画,那期间 TextField 仍在读这个 controller ——
  // showDialog 一 return 就 dispose 会当场抛
  // "A TextEditingController was used after being disposed"。
  final _resetEmailController = TextEditingController();
  bool _isLoading = false;

  // Google Sign-In instance
  // serverClientId is required for backend token verification
  // This should match GOOGLE_CLIENT_ID in backend .env
  final GoogleSignIn _googleSignIn = GoogleSignIn(
    scopes: ['email', 'profile'],
    serverClientId:
        '110810284497-qn7co4o0a3rsmj18ls007c9f3pmqe53u.apps.googleusercontent.com',
  );

  @override
  Widget build(BuildContext context) {
    final gm = context.gm;
    final l10n = AppLocalizations.of(context)!;
    final upgrading = widget.upgrading;
    return Scaffold(
      backgroundColor: gm.bg,
      body: Center(
        child: SingleChildScrollView(
          padding: const EdgeInsets.symmetric(horizontal: 26, vertical: 24),
          child: Form(
            key: _formKey,
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                // 刊头
                Text(
                  'GOMUSEUM',
                  textAlign: TextAlign.center,
                  style: GmText.serif(
                      size: 15, letterSpacing: 7, weight: FontWeight.w700),
                ),
                const SizedBox(height: 10),
                const Center(child: GmDiamond(width: 150)),
                const SizedBox(height: 10),
                Text(
                  l10n.homePocketGuide,
                  textAlign: TextAlign.center,
                  style: GmText.sans(size: 11, letterSpacing: 3, color: gm.sub),
                ),
                const SizedBox(height: 40),
                // 社交登录置顶。原先的理由是"邮箱密码是唯一没有找回路径的
                // 入口" —— **那条理由已经不成立**:找回密码在 2026-09-05 落地
                // (见下方 authForgotPassword 与后端 /auth/password-reset/*)。
                // 顺序保持不变:Google/Apple 用户根本没有密码可忘,一步登录仍是
                // 更省事的那条路;但它现在只是"更省事",不再是"另一条是死路"。
                //
                // 游客按钮**故意不跟着上移**:它最省事,但游客不能购买,
                // 提上来是拿收入换点击率。"最常用的放最显眼"在这里不成立 ——
                // 判据是"最省事 **且** 不把人带进死路"。
                if (_appleLoginSupported) ...[
                  _socialButton(gm, l10n.authAppleLogin, _handleAppleLogin),
                  const SizedBox(height: 10),
                ],
                _socialButton(gm, l10n.authGoogleLogin, _handleGoogleLogin),
                const SizedBox(height: 24),
                _divider(l10n.authOrWithEmail),
                const SizedBox(height: 18),
                _gmField(
                  gm: gm,
                  controller: _emailController,
                  hint: l10n.authEmailHint,
                  keyboardType: TextInputType.emailAddress,
                  validator: (v) =>
                      v?.isEmpty == true ? l10n.authEmailRequired : null,
                ),
                const SizedBox(height: 14),
                _gmField(
                  gm: gm,
                  controller: _passwordController,
                  hint: l10n.authPasswordHint,
                  obscure: true,
                  validator: (v) =>
                      v?.isEmpty == true ? l10n.authPasswordRequired : null,
                ),
                const SizedBox(height: 22),
                _isLoading
                    ? const Center(
                        child: SizedBox(
                          width: 28,
                          height: 28,
                          child: CircularProgressIndicator(strokeWidth: 2.5),
                        ),
                      )
                    : GmTicketButton(
                        label: l10n.authLoginButton,
                        icon: GmIcons.ticket,
                        onTap: _handleLogin,
                      ),
                const SizedBox(height: 14),
                // 忘记密码。**紧挨着密码框那一侧**，而不是塞进页面最底下：
                // 会点它的人此刻正卡在密码上，视线就在这一带。
                GestureDetector(
                  onTap: _showForgotPasswordSheet,
                  child: Text(
                    l10n.authForgotPassword,
                    textAlign: TextAlign.center,
                    style: GmText.sans(size: 12.5, color: gm.sub),
                  ),
                ),
                const SizedBox(height: 12),
                GestureDetector(
                  // 意图要跟着走：从「转正登录页」点进注册，如果不带 upgrade，
                  // 守卫会把已登录的游客从注册页弹回首页 —— 转正这条路又断了。
                  onTap: () => context.push(
                      upgrading ? '/register?$kUpgradeParam=1' : '/register'),
                  child: Text(
                    l10n.authNoAccount,
                    textAlign: TextAlign.center,
                    style: GmText.sans(size: 12.5, color: gm.accent),
                  ),
                ),
                // 游客入口：**主动来换身份的人不该再看到它**。
                //
                // 他点的是「登录后购买」（通票挂账号，游客不许直接买）或收据冲突的
                // 「换个账号登录」——再给他「以游客身份继续」，点了等于原地踏步：
                // 还是同一个游客账号、还是买不了票，而他刚刚做的选择正是要离开
                // 这个状态。
                //
                // 判据是**这次导航的意图**而非用户身份，理由见 [LoginPage.upgrading]。
                if (!upgrading) ...[
                  const SizedBox(height: 24),
                  _divider(l10n.authOr),
                  const SizedBox(height: 18),
                  _socialButton(gm, l10n.authGuestLogin, _handleGuestLogin,
                      emphasized: true),
                ],
              ],
            ),
          ),
        ),
      ),
    );
  }

  Widget _gmField({
    required GmPalette gm,
    required TextEditingController controller,
    required String hint,
    TextInputType? keyboardType,
    bool obscure = false,
    String? Function(String?)? validator,
  }) {
    return TextFormField(
      controller: controller,
      keyboardType: keyboardType,
      obscureText: obscure,
      validator: validator,
      style: GmText.sans(size: 13.5),
      decoration: InputDecoration(
        hintText: hint,
        hintStyle: GmText.sans(size: 13.5, color: gm.faint),
        filled: true,
        fillColor: gm.surface,
        contentPadding:
            const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
        enabledBorder: OutlineInputBorder(
          borderSide: BorderSide(color: gm.line),
          borderRadius: BorderRadius.zero,
        ),
        focusedBorder: OutlineInputBorder(
          borderSide: BorderSide(color: gm.accent),
          borderRadius: BorderRadius.zero,
        ),
        errorBorder: const OutlineInputBorder(
          borderSide: BorderSide(color: GmColors.error),
          borderRadius: BorderRadius.zero,
        ),
        focusedErrorBorder: const OutlineInputBorder(
          borderSide: BorderSide(color: GmColors.error),
          borderRadius: BorderRadius.zero,
        ),
      ),
    );
  }

  Widget _divider(String label) {
    final gm = context.gm;
    return Row(
      children: [
        const Expanded(child: GmHairline()),
        Padding(
          padding: const EdgeInsets.symmetric(horizontal: 14),
          child: Text(label, style: GmText.sans(size: 11.5, color: gm.sub)),
        ),
        const Expanded(child: GmHairline()),
      ],
    );
  }

  Widget _socialButton(GmPalette gm, String label, VoidCallback onTap,
      {bool emphasized = false}) {
    return GestureDetector(
      onTap: _isLoading ? null : onTap,
      child: Container(
        height: 46,
        alignment: Alignment.center,
        decoration: BoxDecoration(
          color: emphasized ? gm.chipBg : gm.surface,
          border: Border.all(color: gm.line),
        ),
        child: Text(
          label,
          style: GmText.sans(
            size: 13.5,
            color: gm.ink,
            weight: emphasized ? FontWeight.w600 : FontWeight.w400,
          ),
        ),
      ),
    );
  }

  /// 「忘记密码」：填邮箱 → 后端发一条一次性链接 → 用户在浏览器里改完，回来登录。
  ///
  /// ⚠️ **不需要 url_launcher。** 链接由邮件客户端自己打开；App 只负责发起申请。
  /// 这个取舍是硬的：加原生插件会改动插件树，而 #434 那个致命缺陷就长在这条缝里
  /// （CI 与出包解析出不同插件树），只有真机才照得出来。
  ///
  /// ⚠️ 提示语只能说「**如果**这个邮箱注册过」。后端对查无此邮箱也返 204
  /// （否则端点就是账号枚举器），说成「已发送到你的邮箱」是替后端撒一个
  /// 它没做的保证 —— 而收不到信的人会一直等下去。
  Future<void> _showForgotPasswordSheet() async {
    final l10n = AppLocalizations.of(context)!;
    final gm = context.gm;
    // 用户多半刚在上面那个框里打过邮箱，别让他再打一遍
    final controller = _resetEmailController
      ..text = _emailController.text.trim();
    var sending = false;

    await showDialog<void>(
      context: context,
      builder: (dialogContext) => StatefulBuilder(
        builder: (dialogContext, setLocal) => AlertDialog(
          backgroundColor: gm.surface,
          shape: const RoundedRectangleBorder(borderRadius: BorderRadius.zero),
          title: Text(l10n.authResetTitle, style: GmText.serif(size: 16)),
          content: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Text(
                l10n.authResetPrompt,
                style: GmText.sans(size: 12.5, color: gm.sub),
              ),
              const SizedBox(height: 14),
              TextField(
                controller: controller,
                autofocus: true,
                keyboardType: TextInputType.emailAddress,
                style: GmText.sans(size: 13.5),
                decoration: InputDecoration(
                  hintText: l10n.authEmailHint,
                  hintStyle: GmText.sans(size: 13.5, color: gm.faint),
                  isDense: true,
                ),
              ),
            ],
          ),
          actions: [
            TextButton(
              onPressed:
                  sending ? null : () => Navigator.of(dialogContext).pop(),
              child: Text(l10n.cancel,
                  style: GmText.sans(size: 13, color: gm.sub)),
            ),
            TextButton(
              onPressed: sending
                  ? null
                  : () async {
                      final email = controller.text.trim();
                      if (email.isEmpty) return;
                      setLocal(() => sending = true);
                      final ok = await _requestReset(email);
                      if (!dialogContext.mounted) return;
                      Navigator.of(dialogContext).pop();
                      if (!mounted) return;
                      ScaffoldMessenger.of(context).showSnackBar(
                        SnackBar(
                          content: Text(
                            ok ? l10n.authResetSent : l10n.authResetFailed,
                          ),
                          duration: const Duration(seconds: 6),
                        ),
                      );
                    },
              child: Text(l10n.authResetSend,
                  style: GmText.sans(size: 13, color: gm.accent)),
            ),
          ],
        ),
      ),
    );
  }

  /// 发申请。返回"信到底有没有发出去" —— 后端在没配发信/投递失败时会回
  /// 503/502，那不能被吞成成功：用户会守着一封永远不来的邮件。
  Future<bool> _requestReset(String email) async {
    try {
      await ref.read(authRepositoryProvider).requestPasswordReset(
            email,
            language: Localizations.localeOf(context).languageCode,
          );
      return true;
    } catch (_) {
      return false;
    }
  }

  Future<void> _handleLogin() async {
    if (!_formKey.currentState!.validate()) return;

    setState(() => _isLoading = true);

    final success = await ref.read(currentUserProvider.notifier).login(
          _emailController.text,
          _passwordController.text,
        );

    if (!mounted) return;

    setState(() => _isLoading = false);

    if (success && mounted) {
      context.go('/');
    } else if (mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(AppLocalizations.of(context)!.authLoginFailed)),
      );
    }
  }

  Future<void> _handleGoogleLogin() async {
    setState(() => _isLoading = true);

    try {
      // 0. 先登出缓存的 Google 会话，确保每次都弹账号选择器（支持切换账号）
      await _googleSignIn.signOut();

      // 1. Call Google Sign-In
      final GoogleSignInAccount? account = await _googleSignIn.signIn();

      if (account == null) {
        // User cancelled the sign-in
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(
                content:
                    Text(AppLocalizations.of(context)!.authGoogleCancelled)),
          );
        }
        setState(() => _isLoading = false);
        return;
      }

      // 2. Get authentication
      final GoogleSignInAuthentication auth = await account.authentication;
      final String? idToken = auth.idToken;

      if (idToken == null) {
        throw Exception('Failed to get Google ID token');
      }

      // 3. Call backend API through provider
      final success =
          await ref.read(currentUserProvider.notifier).loginWithGoogle(
                idToken,
                username: account.displayName,
              );

      if (success && mounted) {
        context.go('/');
      } else if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
              content: Text(AppLocalizations.of(context)!.authGoogleFailed)),
        );
      }
    } catch (e) {
      if (mounted) {
        final l10n = AppLocalizations.of(context)!;
        String errorMsg = l10n.authGoogleError;
        if (e.toString().contains('GOOGLE_CLIENT_ID not configured') ||
            e.toString().contains('DEVELOPER_ERROR') ||
            e.toString().contains('sign_in_failed') ||
            e.toString().contains('GoogleService-Info.plist')) {
          errorMsg = l10n.authGoogleNotConfigured;
        } else if (e.toString().contains('network')) {
          errorMsg = l10n.authGoogleNetworkError;
        } else {
          errorMsg = '${l10n.authGoogleError}: ${e.toString()}';
        }
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(errorMsg),
            duration: const Duration(seconds: 5),
          ),
        );
      }
    } finally {
      if (mounted) {
        setState(() => _isLoading = false);
      }
    }
  }

  /// Apple 登录只在 Apple 平台露面:安卓上点它唯一的结果是弹「仅支持 iOS 和
  /// macOS」——必然失败的按钮不该占位子。反向不成立,iOS 上两个都留着
  /// (4.8 条款只约束 Apple 平台,且多数 Apple 用户也有 Google 账号)。
  ///
  /// 单一真相源:按钮的显隐和处理函数的守卫必须用同一个判据,
  /// 分成两套迟早会出现"按钮在、点了报错"或反过来。
  bool get _appleLoginSupported =>
      defaultTargetPlatform == TargetPlatform.iOS ||
      defaultTargetPlatform == TargetPlatform.macOS;

  Future<void> _handleAppleLogin() async {
    // 守卫留着:按钮已经不该出现在安卓上,但这层不花钱,且挡住将来别处
    // 误接这个入口。
    if (!_appleLoginSupported) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
              content: Text(AppLocalizations.of(context)!.authAppleOnlyApple)),
        );
      }
      return;
    }

    setState(() => _isLoading = true);

    try {
      // 1. Check if Apple Sign In is available
      final isAvailable = await SignInWithApple.isAvailable();
      if (!isAvailable) {
        throw Exception('Apple Sign In is not available on this device');
      }

      // 2. Get Apple ID credential
      final credential = await SignInWithApple.getAppleIDCredential(
        scopes: [
          AppleIDAuthorizationScopes.email,
          AppleIDAuthorizationScopes.fullName,
        ],
      );

      final String? idToken = credential.identityToken;
      if (idToken == null) {
        throw Exception('Failed to get Apple ID token');
      }

      // 3. Build username from full name if available
      String? username;
      if (credential.givenName != null || credential.familyName != null) {
        username =
            '${credential.givenName ?? ''} ${credential.familyName ?? ''}'
                .trim();
      }

      // 4. Call backend API through provider
      final success =
          await ref.read(currentUserProvider.notifier).loginWithApple(
                idToken,
                username: username,
              );

      if (success && mounted) {
        context.go('/');
      } else if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
              content: Text(AppLocalizations.of(context)!.authAppleFailed)),
        );
      }
    } catch (e) {
      if (mounted) {
        final l10n = AppLocalizations.of(context)!;
        String errorMsg = l10n.authAppleError;
        if (e.toString().contains('entitlements') ||
            e.toString().contains('not enabled') ||
            e.toString().contains('not configured')) {
          errorMsg = l10n.authAppleNotConfigured;
        } else if (e.toString().contains('cancelled') ||
            e.toString().contains('1001')) {
          errorMsg = l10n.authAppleCancelled;
        } else {
          errorMsg = '${l10n.authAppleError}: ${e.toString()}';
        }
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(errorMsg),
            duration: const Duration(seconds: 5),
          ),
        );
      }
    } finally {
      if (mounted) {
        setState(() => _isLoading = false);
      }
    }
  }

  Future<void> _handleGuestLogin() async {
    setState(() => _isLoading = true);

    try {
      final deviceId = await ref.read(deviceIdProvider.future);
      final success = await ref
          .read(currentUserProvider.notifier)
          .loginAsGuest(deviceId: deviceId);

      if (!mounted) return;

      setState(() => _isLoading = false);

      if (success && mounted) {
        context.go('/');
      } else if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
              content: Text(AppLocalizations.of(context)!.authGuestFailed)),
        );
      }
    } catch (e) {
      if (mounted) {
        setState(() => _isLoading = false);
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(
                '${AppLocalizations.of(context)!.authGuestError}: ${e.toString()}'),
            duration: const Duration(seconds: 5),
          ),
        );
      }
    }
  }

  @override
  void dispose() {
    _emailController.dispose();
    _passwordController.dispose();
    _resetEmailController.dispose();
    super.dispose();
  }
}
