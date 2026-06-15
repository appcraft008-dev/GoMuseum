/// 登录页 — 暖纸手册风格（设计稿外页面，按定稿风格补齐）
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:google_sign_in/google_sign_in.dart';
import 'package:gomuseum_app/features/payment/presentation/providers/benefits_provider.dart';
import 'package:gomuseum_app/ui/gm/gm.dart';
import 'package:sign_in_with_apple/sign_in_with_apple.dart';
import 'dart:io' show Platform;
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
    return Scaffold(
      backgroundColor: GmColors.bg,
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
                  '随身博物馆导览手册',
                  textAlign: TextAlign.center,
                  style: GmText.sans(
                      size: 11, letterSpacing: 3, color: GmColors.sub),
                ),
                const SizedBox(height: 40),
                _gmField(
                  controller: _emailController,
                  hint: '邮箱',
                  keyboardType: TextInputType.emailAddress,
                  validator: (v) => v?.isEmpty == true ? '请输入邮箱' : null,
                ),
                const SizedBox(height: 14),
                _gmField(
                  controller: _passwordController,
                  hint: '密码',
                  obscure: true,
                  validator: (v) => v?.isEmpty == true ? '请输入密码' : null,
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
                        label: '登 录',
                        icon: GmIcons.ticket,
                        onTap: _handleLogin,
                      ),
                const SizedBox(height: 14),
                GestureDetector(
                  onTap: () => context.push('/register'),
                  child: Text(
                    '还没有账号？注册',
                    textAlign: TextAlign.center,
                    style: GmText.sans(size: 12.5, color: GmColors.accent),
                  ),
                ),
                const SizedBox(height: 24),
                _divider('或使用以下方式登录'),
                const SizedBox(height: 18),
                _socialButton('使用 Google 登录', _handleGoogleLogin),
                const SizedBox(height: 10),
                _socialButton('使用 Apple 登录', _handleAppleLogin),
                const SizedBox(height: 18),
                _divider('或'),
                const SizedBox(height: 18),
                _socialButton('游客登录', _handleGuestLogin, emphasized: true),
              ],
            ),
          ),
        ),
      ),
    );
  }

  Widget _gmField({
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
        hintStyle: GmText.sans(size: 13.5, color: GmColors.faint),
        filled: true,
        fillColor: GmColors.surface,
        contentPadding:
            const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
        enabledBorder: const OutlineInputBorder(
          borderSide: BorderSide(color: GmColors.line),
          borderRadius: BorderRadius.zero,
        ),
        focusedBorder: const OutlineInputBorder(
          borderSide: BorderSide(color: GmColors.accent),
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
    return Row(
      children: [
        const Expanded(child: GmHairline()),
        Padding(
          padding: const EdgeInsets.symmetric(horizontal: 14),
          child:
              Text(label, style: GmText.sans(size: 11.5, color: GmColors.sub)),
        ),
        const Expanded(child: GmHairline()),
      ],
    );
  }

  Widget _socialButton(String label, VoidCallback onTap,
      {bool emphasized = false}) {
    return GestureDetector(
      onTap: _isLoading ? null : onTap,
      child: Container(
        height: 46,
        alignment: Alignment.center,
        decoration: BoxDecoration(
          color: emphasized ? GmColors.chipBg : GmColors.surface,
          border: Border.all(color: GmColors.line),
        ),
        child: Text(
          label,
          style: GmText.sans(
            size: 13.5,
            color: GmColors.ink,
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
        const SnackBar(content: Text('登录失败，请检查邮箱和密码')),
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
            const SnackBar(content: Text('Google登录已取消')),
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
          const SnackBar(content: Text('Google登录失败，请重试')),
        );
      }
    } catch (e) {
      if (mounted) {
        String errorMsg = 'Google登录错误';
        if (e.toString().contains('GOOGLE_CLIENT_ID not configured')) {
          errorMsg = 'Google登录未配置，请联系管理员配置 GOOGLE_CLIENT_ID';
        } else if (e.toString().contains('DEVELOPER_ERROR') ||
            e.toString().contains('sign_in_failed') ||
            e.toString().contains('GoogleService-Info.plist')) {
          errorMsg = 'Google登录未配置，请联系管理员添加GoogleService-Info.plist';
        } else if (e.toString().contains('network')) {
          errorMsg = 'Google登录网络错误，请检查网络连接';
        } else {
          errorMsg = 'Google登录错误: ${e.toString()}';
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

  Future<void> _handleAppleLogin() async {
    // Check if running on iOS/macOS
    if (!Platform.isIOS && !Platform.isMacOS) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Apple登录仅支持iOS和macOS设备')),
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
          const SnackBar(content: Text('Apple登录失败，请重试')),
        );
      }
    } catch (e) {
      if (mounted) {
        String errorMsg = 'Apple登录错误';
        if (e.toString().contains('entitlements') ||
            e.toString().contains('not enabled') ||
            e.toString().contains('not configured')) {
          errorMsg = 'Apple登录未配置，请检查Xcode的Sign In with Apple capability';
        } else if (e.toString().contains('cancelled') ||
            e.toString().contains('1001')) {
          errorMsg = 'Apple登录已取消';
        } else {
          errorMsg = 'Apple登录错误: ${e.toString()}';
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
          const SnackBar(content: Text('游客登录失败，请重试')),
        );
      }
    } catch (e) {
      if (mounted) {
        setState(() => _isLoading = false);
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('游客登录错误: ${e.toString()}'),
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
