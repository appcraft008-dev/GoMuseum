import 'package:dartz/dartz.dart';
import 'package:in_app_purchase/in_app_purchase.dart';
import '../../../../core/error/exceptions.dart';
import '../../../../core/error/failures.dart';
import '../../../../core/network/network_info.dart';
import '../../domain/entities/consumption_result.dart';
import '../../domain/entities/purchase_result.dart';
import '../../domain/entities/user_benefits.dart';
import '../../domain/repositories/payment_repository.dart';
import '../datasources/payment_remote_datasource.dart';

/// 支付仓储实现
class PaymentRepositoryImpl implements PaymentRepository {
  final PaymentRemoteDataSource remoteDataSource;
  final NetworkInfo networkInfo;

  const PaymentRepositoryImpl({
    required this.remoteDataSource,
    required this.networkInfo,
  });

  @override
  Future<Either<Failure, PurchaseResult>> verifyPurchase({
    required PurchaseDetails purchase,
    String? userId,
    required String deviceId,
  }) async {
    // 检查网络连接
    if (!await networkInfo.isConnected) {
      return const Left(NetworkFailure('No internet connection'));
    }

    try {
      final result = await remoteDataSource.verifyPurchase(
        purchase: purchase,
        userId: userId,
        deviceId: deviceId,
      );
      return Right(result);
    } on ServerException catch (e) {
      return Left(ServerFailure(e.message));
    } on NetworkException catch (e) {
      return Left(NetworkFailure(e.message));
    } on TimeoutException catch (e) {
      return Left(TimeoutFailure(e.message));
    } catch (e) {
      return Left(ServerFailure('Unexpected error: $e'));
    }
  }

  @override
  Future<Either<Failure, UserBenefits>> getUserBenefits({
    String? userId,
    required String deviceId,
  }) async {
    // 检查网络连接
    if (!await networkInfo.isConnected) {
      return const Left(NetworkFailure('No internet connection'));
    }

    try {
      final result = await remoteDataSource.getUserBenefits(
        userId: userId,
        deviceId: deviceId,
      );
      return Right(result);
    } on ServerException catch (e) {
      return Left(ServerFailure(e.message));
    } on NetworkException catch (e) {
      return Left(NetworkFailure(e.message));
    } on TimeoutException catch (e) {
      return Left(TimeoutFailure(e.message));
    } catch (e) {
      return Left(ServerFailure('Unexpected error: $e'));
    }
  }

  @override
  Future<Either<Failure, ConsumptionResult>> consumeRecognition({
    String? userId,
    required String deviceId,
  }) async {
    // 检查网络连接
    if (!await networkInfo.isConnected) {
      return const Left(NetworkFailure('No internet connection'));
    }

    try {
      final result = await remoteDataSource.consumeRecognition(
        userId: userId,
        deviceId: deviceId,
      );
      return Right(result);
    } on ServerException catch (e) {
      return Left(ServerFailure(e.message));
    } on NetworkException catch (e) {
      return Left(NetworkFailure(e.message));
    } on TimeoutException catch (e) {
      return Left(TimeoutFailure(e.message));
    } catch (e) {
      return Left(ServerFailure('Unexpected error: $e'));
    }
  }
}
