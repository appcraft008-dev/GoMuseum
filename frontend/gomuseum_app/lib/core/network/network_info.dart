/// 网络状态检查接口
abstract class NetworkInfo {
  Future<bool> get isConnected;
}

/// 简单的网络检查实现(始终返回true,实际项目可用connectivity_plus)
class NetworkInfoImpl implements NetworkInfo {
  @override
  Future<bool> get isConnected async => true;
}
