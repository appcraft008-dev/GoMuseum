/// 收据冲突(契约 I18/I22)从 HTTP 409 一路到 UI 的链路。
///
/// ⚠️ **这条链在真机上走不到,只有这里兜着。** 触发 409 需要一张 Google 仍然
/// 认可、且已归属别人的收据;而通票是消耗型商品,验证成功即被消耗,App 之后
/// 再也回放不出它来。后端侧有两条测试守着
/// (`test_purchase_verification.py` 的服务层 + 端点 409 不被吞成 500),
/// prod 上也用正负样本实测过 —— 前端这半段此前**一条都没有**。
///
/// 断言分正负两组:一个只会喊"冲突"的映射和一个从不喊的一样没用。
library;

import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gomuseum_app/core/error/exceptions.dart';
import 'package:gomuseum_app/core/error/failures.dart';
import 'package:gomuseum_app/core/network/network_info.dart';
import 'package:gomuseum_app/features/payment/data/datasources/payment_remote_datasource.dart';
import 'package:gomuseum_app/features/payment/data/repositories/payment_repository_impl.dart';
import 'package:in_app_purchase/in_app_purchase.dart';

final _purchase = PurchaseDetails(
  productID: 'paris_pass_7d',
  purchaseID: 'GPA.0000-0000-0000-00000',
  verificationData: PurchaseVerificationData(
    localVerificationData: 'local',
    serverVerificationData: 'token',
    source: 'google_play',
  ),
  transactionDate: '1757000000000',
  status: PurchaseStatus.purchased,
);

/// 只会以指定状态码失败的 Dio。
Dio _dioFailing(int status) => Dio()
  ..interceptors.add(InterceptorsWrapper(
    onRequest: (o, h) => h.reject(DioException.badResponse(
      statusCode: status,
      requestOptions: o,
      response: Response<dynamic>(requestOptions: o, statusCode: status),
    )),
  ));

class _AlwaysOnline implements NetworkInfo {
  @override
  Future<bool> get isConnected async => true;
}

Future<Object?> _thrownBy(int status) async {
  final ds = PaymentRemoteDataSourceImpl(dio: _dioFailing(status));
  try {
    await ds.verifyPurchase(purchase: _purchase, deviceId: 'dev-1');
    return null;
  } catch (e) {
    return e;
  }
}

Future<Failure?> _failureFor(int status) async {
  final repo = PaymentRepositoryImpl(
    remoteDataSource: PaymentRemoteDataSourceImpl(dio: _dioFailing(status)),
    networkInfo: _AlwaysOnline(),
  );
  final r = await repo.verifyPurchase(purchase: _purchase, deviceId: 'dev-1');
  return r.fold((f) => f, (_) => null);
}

void main() {
  group('数据源:HTTP 状态码 → 异常', () {
    test('409 → PurchaseConflictException', () async {
      expect(await _thrownBy(409), isA<PurchaseConflictException>());
    });

    test('500 不是冲突 —— 别把所有失败都当成"换个账号"', () async {
      final e = await _thrownBy(500);
      expect(e, isA<ServerException>());
      expect(e, isNot(isA<PurchaseConflictException>()));
    });
  });

  group('仓储:异常 → Failure', () {
    test('409 → PurchaseConflictFailure(UI 才知道该给"换账号"而非"重试")', () async {
      expect(await _failureFor(409), isA<PurchaseConflictFailure>());
    });

    test('500 → ServerFailure', () async {
      final f = await _failureFor(500);
      expect(f, isA<ServerFailure>());
      expect(f, isNot(isA<PurchaseConflictFailure>()));
    });
  });
}
