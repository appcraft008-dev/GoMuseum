import Flutter
import UIKit

@main
@objc class AppDelegate: FlutterAppDelegate {
  override func application(
    _ application: UIApplication,
    didFinishLaunchingWithOptions launchOptions: [UIApplication.LaunchOptionsKey: Any]?
  ) -> Bool {
    GeneratedPluginRegistrant.register(with: self)
    // 与 Android MainActivity 同名的手写通道(不加 url_launcher,理由见 open_url.dart);
    // 缺了它 iOS 上隐私政策等链接只能复制,审核要求 App 内能打开。
    if let registrar = registrar(forPlugin: "GoMuseumOpenUrl") {
      FlutterMethodChannel(name: "gomuseum/open_url", binaryMessenger: registrar.messenger())
        .setMethodCallHandler { call, result in
          guard call.method == "open", let s = call.arguments as? String,
            let url = URL(string: s)
          else {
            result(FlutterMethodNotImplemented)
            return
          }
          UIApplication.shared.open(url) { result($0) }
        }
    }
    return super.application(application, didFinishLaunchingWithOptions: launchOptions)
  }
}
