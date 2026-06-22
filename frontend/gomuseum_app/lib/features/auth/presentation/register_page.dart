/// 注册页 — 暖纸手册风格（设计稿外页面，按定稿风格补齐）
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:gomuseum_app/theme/gm_palette.dart';
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
                    '创建账号',
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
                    hint: '邮箱',
                    keyboardType: TextInputType.emailAddress,
                    validator: (v) {
                      if (v?.isEmpty == true) return '请输入邮箱';
                      final emailRegex = RegExp(
                          r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$');
                      if (!emailRegex.hasMatch(v!)) return '请输入有效的邮箱地址';
                      return null;
                    },
                  ),
                  const SizedBox(height: 14),
                  _gmField(
                    gm: gm,
                    controller: _usernameController,
                    hint: '用户名（可选）',
                  ),
                  const SizedBox(height: 14),
                  _gmField(
                    gm: gm,
                    controller: _passwordController,
                    hint: '密码',
                    obscure: true,
                    validator: (v) {
                      if (v?.isEmpty == true) return '请输入密码';
                      if (v!.length < 6) return '密码至少6位';
                      return null;
                    },
                  ),
                  const SizedBox(height: 14),
                  _gmField(
                    gm: gm,
                    controller: _confirmPasswordController,
                    hint: '确认密码',
                    obscure: true,
                    validator: (v) {
                      if (v != _passwordController.text) return '两次密码不一致';
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
                          label: '注 册',
                          icon: GmIcons.ticket,
                          onTap: _handleRegister,
                        ),
                  const SizedBox(height: 14),
                  GestureDetector(
                    onTap: () => context.pop(),
                    child: Text(
                      '已有账号？登录',
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
        const SnackBar(content: Text('注册失败，邮箱可能已被使用')),
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
