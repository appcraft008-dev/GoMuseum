/// User entity
class User {
  final String id;
  final String? email;
  final String? username;
  final String? avatarUrl;
  final bool isActive;
  final bool isVerified;
  final DateTime createdAt;
  final DateTime? lastLoginAt;

  User({
    required this.id,
    this.email,
    this.username,
    this.avatarUrl,
    required this.isActive,
    required this.isVerified,
    required this.createdAt,
    this.lastLoginAt,
  });

  factory User.fromJson(Map<String, dynamic> json) {
    return User(
      id: json['id'],
      email: json['email'] as String?,
      username: json['username'],
      avatarUrl: json['avatar_url'],
      isActive: json['is_active'],
      isVerified: json['is_verified'],
      createdAt: DateTime.parse(json['created_at']),
      lastLoginAt: json['last_login_at'] != null
          ? DateTime.parse(json['last_login_at'])
          : null,
    );
  }
}
