/// 服务器异常
class ServerException implements Exception {
  final String message;
  const ServerException([this.message = 'Server error occurred']);

  @override
  String toString() => 'ServerException: $message';
}

/// 收据已归属另一个账号(后端 409 `purchase_belongs_to_another_account`)。
///
/// **必须与普通失败分开**:这是唯一一种"重试永远不会成功"的购买失败。
/// 混进 ServerException 就会显示成「购买失败,请重试」,用户点到死也不会好,
/// 最后要么重复购买、要么申请退款。
class PurchaseConflictException implements Exception {
  final String message;
  const PurchaseConflictException([
    this.message = 'Purchase belongs to another account',
  ]);

  @override
  String toString() => 'PurchaseConflictException: $message';
}

/// 缓存异常
class CacheException implements Exception {
  final String message;
  const CacheException([this.message = 'Cache error occurred']);

  @override
  String toString() => 'CacheException: $message';
}

/// 网络异常
class NetworkException implements Exception {
  final String message;
  const NetworkException([this.message = 'Network connection failed']);

  @override
  String toString() => 'NetworkException: $message';
}

/// 验证异常
class ValidationException implements Exception {
  final String message;
  const ValidationException([this.message = 'Validation failed']);

  @override
  String toString() => 'ValidationException: $message';
}

/// 超时异常
class TimeoutException implements Exception {
  final String message;
  const TimeoutException([this.message = 'Request timeout']);

  @override
  String toString() => 'TimeoutException: $message';
}
