import 'dart:io' show Platform;
import 'package:dio/dio.dart';
import 'package:in_app_purchase/in_app_purchase.dart';
import '../../../../core/error/exceptions.dart';
import '../models/consumption_result_model.dart';
import '../models/purchase_result_model.dart';
import '../models/user_benefits_model.dart';

/// 支付远程数据源接口
abstract class PaymentRemoteDataSource {
  /// 验证IAP购买凭证
  Future<PurchaseResultModel> verifyPurchase({
    required PurchaseDetails purchase,
    String? userId,
    required String deviceId,
  });

  /// 获取用户权益
  Future<UserBenefitsModel> getUserBenefits({
    String? userId,
    required String deviceId,
  });

  /// 消耗识别配额
  Future<ConsumptionResultModel> consumeRecognition({
    String? userId,
    required String deviceId,
  });
}

/// 支付远程数据源实现
class PaymentRemoteDataSourceImpl implements PaymentRemoteDataSource {
  final Dio dio;

  const PaymentRemoteDataSourceImpl({required this.dio});

  @override
  Future<PurchaseResultModel> verifyPurchase({
    required PurchaseDetails purchase,
    String? userId,
    required String deviceId,
  }) async {
    try {
      // 获取平台名称
      String platform;
      try {
        platform = Platform.isIOS ? 'ios' : 'android';
      } catch (e) {
        // Web平台会抛出异常，默认使用android
        platform = 'android';
      }

      // 获取receipt数据
      final receiptData = purchase.verificationData.serverVerificationData;

      // 构建请求体
      final requestBody = {
        'platform': platform,
        'receipt_data': receiptData,
        'product_id': purchase.productID,
        if (userId != null) 'user_id': userId,
        'device_id': deviceId,
      };

      final response = await dio.post(
        '/api/v1/payment/verify',
        data: requestBody,
        options: Options(
          headers: {
            'Accept': 'application/json',
            'Content-Type': 'application/json',
          },
        ),
      );

      if (response.statusCode == 200) {
        return PurchaseResultModel.fromJson(
            response.data as Map<String, dynamic>);
      } else {
        throw ServerException(
            'Server returned status code: ${response.statusCode}');
      }
    } on DioException catch (e) {
      if (e.type == DioExceptionType.connectionTimeout ||
          e.type == DioExceptionType.receiveTimeout ||
          e.type == DioExceptionType.sendTimeout) {
        throw const TimeoutException('Request timeout');
      } else if (e.type == DioExceptionType.connectionError) {
        throw const NetworkException('Network connection failed');
      } else {
        throw ServerException('Server error: ${e.message}');
      }
    } catch (e) {
      throw ServerException('Unexpected error: $e');
    }
  }

  @override
  Future<UserBenefitsModel> getUserBenefits({
    String? userId,
    required String deviceId,
  }) async {
    try {
      // 构建查询参数
      final queryParams = {
        'device_id': deviceId,
        if (userId != null) 'user_id': userId,
      };

      final response = await dio.get(
        '/api/v1/payment/benefits',
        queryParameters: queryParams,
        options: Options(
          headers: {
            'Accept': 'application/json',
          },
        ),
      );

      if (response.statusCode == 200) {
        return UserBenefitsModel.fromJson(
            response.data as Map<String, dynamic>);
      } else {
        throw ServerException(
            'Server returned status code: ${response.statusCode}');
      }
    } on DioException catch (e) {
      if (e.type == DioExceptionType.connectionTimeout ||
          e.type == DioExceptionType.receiveTimeout ||
          e.type == DioExceptionType.sendTimeout) {
        throw const TimeoutException('Request timeout');
      } else if (e.type == DioExceptionType.connectionError) {
        throw const NetworkException('Network connection failed');
      } else {
        throw ServerException('Server error: ${e.message}');
      }
    } catch (e) {
      throw ServerException('Unexpected error: $e');
    }
  }

  @override
  Future<ConsumptionResultModel> consumeRecognition({
    String? userId,
    required String deviceId,
  }) async {
    try {
      // 构建查询参数
      final queryParams = {
        'device_id': deviceId,
        if (userId != null) 'user_id': userId,
      };

      final response = await dio.post(
        '/api/v1/payment/consume',
        queryParameters: queryParams,
        options: Options(
          headers: {
            'Accept': 'application/json',
          },
        ),
      );

      if (response.statusCode == 200) {
        return ConsumptionResultModel.fromJson(
            response.data as Map<String, dynamic>);
      } else {
        throw ServerException(
            'Server returned status code: ${response.statusCode}');
      }
    } on DioException catch (e) {
      if (e.type == DioExceptionType.connectionTimeout ||
          e.type == DioExceptionType.receiveTimeout ||
          e.type == DioExceptionType.sendTimeout) {
        throw const TimeoutException('Request timeout');
      } else if (e.type == DioExceptionType.connectionError) {
        throw const NetworkException('Network connection failed');
      } else {
        throw ServerException('Server error: ${e.message}');
      }
    } catch (e) {
      throw ServerException('Unexpected error: $e');
    }
  }
}
