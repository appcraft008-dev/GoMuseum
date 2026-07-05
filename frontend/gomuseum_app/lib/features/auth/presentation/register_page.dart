/// 注册页 — 暖纸手册风格（设计稿外页面，按定稿风格补齐）
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:gomuseum_app/theme/gm_palette.dart';
import 'package:gomuseum_app/l10n/app_localizations.dart';
import 'package:gomuseum_app/theme/gm_theme_x.dart';
import 'package:gomuseum_app/ui/gm/gm.dart';
import 'auth_provider.dart';

class RegisterPage extends ConsumerStatefulWidget {
  const RegisterPage({super.key});

  @override
  ConsumerState<RegisterPage> createState() => _RegisterPageState();
}

class _RegisterPageState extends ConsumerState<RegisterPage> {
  final _formKey = GlobalKey<FormState>();
  final _emailController = TextEditingController();
  final _usernameController = TextEditingController();
  final _passwordController = TextEditingController();
  final _confirmPasswordController = TextEditingController();
  bool _isLoading = false;

  @override
  Widget build(BuildContext context) {
    final gm = context.gm;
    final l10n = AppLocalizations.of(context)!;
    return Scaffold(
      backgroundColor: gm.bg,
      body: SafeArea(
        child: Center(
          child: SingleChildScrollView(
            padding: const EdgeInsets.symmetric(horizontal: 26, vertical: 24),
            child: Form(
              key: _formKey,
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  Row(
                    children: [
                      GestureDetector(
                        onTap: () => context.pop(),
                        behavior: HitTestBehavior.opaque,
                        child: GmIcon(GmIcons.back, size: 20, color: gm.ink),
                      ),
                    ],
                  ),
                  const SizedBox(height: 16),
                  Text(
                    l10n.authCreateAccount,
                    textAlign: TextAlign.center,
                    style: GmText.serif(
                        size: 21, weight: FontWeight.w700, letterSpacing: 4),
                  ),
                  const SizedBox(height: 10),
                  const Center(child: GmDiamond(width: 110)),
                  const SizedBox(height: 32),
                  _gmField(
                    gm: gm,
                    controller: _emailController,
                    hint: l10n.authEmailHint,
                    keyboardType: TextInputType.emailAddress,
                    validator: (v) {
                      if (v?.isEmpty == true) return l10n.authEmailRequired;
                      final emailRegex = RegExp(
                          r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$');
                      if (!emailRegex.hasMatch(v!))
                        return l10n.authEmailInvalid;
                      return null;
                    },
                  ),
                  const SizedBox(height: 14),
                  _gmField(
                    gm: gm,
                    controller: _usernameController,
                    hint: l10n.authUsernameOptionalHint,
                  ),
                  const SizedBox(height: 14),
                  _gmField(
                    gm: gm,
                    controller: _passwordController,
                    hint: l10n.authPasswordHint,
                    obscure: true,
                    validator: (v) {
                      if (v?.isEmpty == true) return l10n.authPasswordRequired;
                      if (v!.length < 6) return l10n.authPasswordMin6;
                      return null;
                    },
                  ),
                  const SizedBox(height: 14),
                  _gmField(
                    gm: gm,
                    controller: _confirmPasswordController,
                    hint: l10n.authConfirmPasswordHint,
                    obscure: true,
                    validator: (v) {
                      if (v != _passwordController.text) {
                        return l10n.authPasswordMismatch;
                      }
                      return null;
                    },
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
                          label: l10n.authRegisterButton,
                          icon: GmIcons.ticket,
                          onTap: _handleRegister,
                        ),
                  const SizedBox(height: 14),
                  GestureDetector(
                    onTap: () => context.pop(),
                    child: Text(
                      l10n.authHaveAccount,
                      textAlign: TextAlign.center,
                      style: GmText.sans(size: 12.5, color: gm.accent),
                    ),
                  ),
                ],
              ),
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

  Future<void> _handleRegister() async {
    if (!_formKey.currentState!.validate()) return;

    setState(() => _isLoading = true);

    final success = await ref.read(currentUserProvider.notifier).register(
          _emailController.text,
          _passwordController.text,
          username: _usernameController.text.isEmpty
              ? null
              : _usernameController.text,
        );

    setState(() => _isLoading = false);

    if (success && mounted) {
      context.go('/');
    } else if (mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
            content: Text(AppLocalizations.of(context)!.authRegisterFailed)),
      );
    }
  }

  @override
  void dispose() {
    _emailController.dispose();
    _usernameController.dispose();
    _passwordController.dispose();
    _confirmPasswordController.dispose();
    super.dispose();
  }
}
