import 'package:equatable/equatable.dart';

/// 基础Failure抽象类
abstract class Failure extends Equatable {
  final String message;

  const Failure(this.message);

  @override
  List<Object> get props => [message];
}

/// 服务器错误
class ServerFailure extends Failure {
  const ServerFailure([super.message = 'Server error occurred']);
}

/// 缓存错误
class CacheFailure extends Failure {
  const CacheFailure([super.message = 'Cache error occurred']);
}

/// 网络错误
class NetworkFailure extends Failure {
  const NetworkFailure([super.message = 'Network connection failed']);
}

/// 验证错误
class ValidationFailure extends Failure {
  const ValidationFailure([super.message = 'Validation failed']);
}

/// 超时错误
class TimeoutFailure extends Failure {
  const TimeoutFailure([super.message = 'Request timeout']);
}
