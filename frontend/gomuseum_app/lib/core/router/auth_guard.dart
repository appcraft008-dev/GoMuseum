/// Auth guard for route protection
import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../features/auth/data/auth_repository.dart';

/// Check if user is authenticated
Future<String?> authGuard(
    BuildContext context, GoRouterState state, WidgetRef ref) async {
  final repository = ref.read(authRepositoryProvider);
  final isLoggedIn = await repository.isLoggedIn();

  // Public routes that don't require auth
  final publicRoutes = ['/login', '/register'];
  final isPublicRoute = publicRoutes.contains(state.uri.path);

  if (!isLoggedIn && !isPublicRoute) {
    // Not logged in, redirect to login
    return '/login';
  }

  if (isLoggedIn && isPublicRoute) {
    // Already logged in, redirect to home
    return '/';
  }

  // All good, no redirect
  return null;
}

// Provider for auth repository
final authRepositoryProvider = Provider<AuthRepository>((ref) {
  return ref.watch(authRepositoryProviderFromAuth);
});

// Import from auth module
final authRepositoryProviderFromAuth = Provider<AuthRepository>((ref) {
  throw UnimplementedError('This should be overridden');
});
