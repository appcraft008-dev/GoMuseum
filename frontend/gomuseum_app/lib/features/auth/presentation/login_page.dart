/// 登录页 — 暖纸手册风格（设计稿外页面，按定稿风格补齐）
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
  const LoginPage({super.key});

  @override
  ConsumerState<LoginPage> createState() => _LoginPageState();
}

class _LoginPageState extends ConsumerState<LoginPage> {
  final _formKey = GlobalKey<FormState>();
  final _emailController = TextEditingController();
  final _passwordController = TextEditingController();
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
    // 读不到登录态时按「不是游客」处理：宁可多显示一个入口，
    // 也不要让真·未登录的用户面对一个没有游客选项的登录页。
    final isGuest =
        ref.watch(currentUserProvider).valueOrNull?.isGuest ?? false;
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
                // 社交登录置顶。理由不是"它更常用",而是:**邮箱密码是唯一
                // 没有找回路径的入口**(找回密码尚未实现,见 backlog),而
                // Google/Apple 用户根本没有密码可忘。页面把谁放在最上面,
                // 就决定了多少用户掉进那条没有退路的路。
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
                GestureDetector(
                  onTap: () => context.push('/register'),
                  child: Text(
                    l10n.authNoAccount,
                    textAlign: TextAlign.center,
                    style: GmText.sans(size: 12.5, color: gm.accent),
                  ),
                ),
                // 游客入口：**已经是游客的人不该再看到它**。
                //
                // 游客到得了登录页只有一种情形——他点了「登录后购买」
                // （通票挂账号，游客不许直接买）或收据冲突的「换个账号登录」。
                // 这时再给他「以游客身份继续」，点了等于原地踏步：还是同一个
                // 游客账号、还是买不了票，而他刚刚做的选择正是要离开这个状态。
                //
                // 判据用「当前是不是游客」而不是「从哪个入口来的」：后者要给三个
                // 调用点各传一个参数，而且会漏掉将来新增的入口；前者在任何入口下
                // 都成立。未登录（user == null）时按钮照常留着——那才是它的用武之地。
                if (!isGuest) ...[
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
    super.dispose();
  }
}
