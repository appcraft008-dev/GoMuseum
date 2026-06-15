import 'package:riverpod_annotation/riverpod_annotation.dart';
import '../../../recognition/presentation/providers/recognition_providers.dart';
import '../../data/datasources/payment_remote_datasource.dart';
import '../../data/repositories/payment_repository_impl.dart';
import '../../domain/repositories/payment_repository.dart';
import '../../domain/usecases/consume_recognition.dart';
import '../../domain/usecases/get_user_benefits.dart';
import '../../domain/usecases/verify_purchase.dart';

part 'payment_providers.g.dart';

/// 支付远程数据源Provider
@riverpod
PaymentRemoteDataSource paymentRemoteDataSource(
    PaymentRemoteDataSourceRef ref) {
  return PaymentRemoteDataSourceImpl(dio: ref.watch(dioProvider));
}

/// 支付Repository Provider
@riverpod
PaymentRepository paymentRepository(PaymentRepositoryRef ref) {
  return PaymentRepositoryImpl(
    remoteDataSource: ref.watch(paymentRemoteDataSourceProvider),
    networkInfo: ref.watch(networkInfoProvider),
  );
}

/// VerifyPurchase UseCase Provider
@riverpod
VerifyPurchase verifyPurchaseUseCase(VerifyPurchaseUseCaseRef ref) {
  return VerifyPurchase(repository: ref.watch(paymentRepositoryProvider));
}

/// GetUserBenefits UseCase Provider
@riverpod
GetUserBenefits getUserBenefitsUseCase(GetUserBenefitsUseCaseRef ref) {
  return GetUserBenefits(repository: ref.watch(paymentRepositoryProvider));
}

/// ConsumeRecognition UseCase Provider
@riverpod
ConsumeRecognition consumeRecognitionUseCase(ConsumeRecognitionUseCaseRef ref) {
  return ConsumeRecognition(repository: ref.watch(paymentRepositoryProvider));
}
