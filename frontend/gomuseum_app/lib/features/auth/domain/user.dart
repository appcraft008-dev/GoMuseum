/// User entity
class User {
  final String id;
  final String? email;
  final String? username;
  final String? avatarUrl;
  final bool isActive;
  final bool isVerified;

  /// 是不是游客账号。
  ///
  /// 游客在服务端是一行**真的** User（有 token、能过鉴权），所以"有没有登录"
  /// 这个问题对游客的答案是"有"。但游客点「登录后购买」正是要去转正 ——
  /// 路由守卫必须能把这两者分开，否则游客永远到不了登录页、也就永远买不了票。
  ///
  /// 老后端不返回该字段 → 回退 `false`（当成正式账号，保持旧行为）。
  final bool isGuest;
  final DateTime createdAt;
  final DateTime? lastLoginAt;

  User({
    required this.id,
    this.email,
    this.username,
    this.avatarUrl,
    required this.isActive,
    required this.isVerified,
    this.isGuest = false,
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
      isGuest: json['is_guest'] as bool? ?? false,
      createdAt: DateTime.parse(json['created_at']),
      lastLoginAt: json['last_login_at'] != null
          ? DateTime.parse(json['last_login_at'])
          : null,
    );
  }
}
