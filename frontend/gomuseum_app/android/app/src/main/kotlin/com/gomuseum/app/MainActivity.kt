package com.gomuseum.app

import android.app.Activity
import android.content.ActivityNotFoundException
import android.content.Intent
import android.net.Uri
import com.google.android.play.core.appupdate.AppUpdateInfo
import com.google.android.play.core.appupdate.AppUpdateManager
import com.google.android.play.core.appupdate.AppUpdateManagerFactory
import com.google.android.play.core.appupdate.AppUpdateOptions
import com.google.android.play.core.install.InstallStateUpdatedListener
import com.google.android.play.core.install.model.AppUpdateType
import com.google.android.play.core.install.model.InstallStatus
import com.google.android.play.core.install.model.UpdateAvailability
import io.flutter.embedding.android.FlutterActivity
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.plugin.common.MethodChannel

class MainActivity : FlutterActivity() {
    private var updateManager: AppUpdateManager? = null
    private var updateListener: InstallStateUpdatedListener? = null
    private var lastUpdateInfo: AppUpdateInfo? = null

    override fun configureFlutterEngine(flutterEngine: FlutterEngine) {
        super.configureFlutterEngine(flutterEngine)
        val messenger = flutterEngine.dartExecutor.binaryMessenger

        // 用系统浏览器打开条款/隐私页。手写通道而不是 url_launcher:不改插件树(见 open_url.dart)。
        MethodChannel(messenger, "gomuseum/open_url")
            .setMethodCallHandler { call, result ->
                val url = call.arguments as? String
                if (call.method != "open" || url == null || !url.startsWith("https://")) {
                    result.success(false)
                    return@setMethodCallHandler
                }
                try {
                    startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(url)))
                    result.success(true)
                } catch (e: ActivityNotFoundException) {
                    result.success(false)
                }
            }

        // Play 应用内更新(后台下载流程,见 app_update_service.dart)。同上,手写通道不加插件。
        val manager = AppUpdateManagerFactory.create(this)
        updateManager = manager
        val channel = MethodChannel(messenger, "gomuseum/app_update")
        updateListener = InstallStateUpdatedListener { state ->
            if (state.installStatus() == InstallStatus.DOWNLOADED) {
                channel.invokeMethod("downloaded", null)
            }
        }.also { manager.registerListener(it) }
        channel.setMethodCallHandler { call, result ->
            when (call.method) {
                // 非 Play 安装(本地调试包等)这里会失败 → 返回 null,Dart 侧当作没更新
                "check" -> manager.appUpdateInfo
                    .addOnSuccessListener { info ->
                        lastUpdateInfo = info
                        result.success(
                            mapOf(
                                "available" to (info.updateAvailability() == UpdateAvailability.UPDATE_AVAILABLE &&
                                    info.isUpdateTypeAllowed(AppUpdateType.FLEXIBLE)),
                                "versionCode" to info.availableVersionCode(),
                                "downloaded" to (info.installStatus() == InstallStatus.DOWNLOADED),
                            )
                        )
                    }
                    .addOnFailureListener { result.success(null) }
                "start" -> {
                    val info = lastUpdateInfo
                    if (info == null) {
                        result.success(false)
                    } else {
                        manager.startUpdateFlow(
                            info, this, AppUpdateOptions.defaultOptions(AppUpdateType.FLEXIBLE)
                        )
                            .addOnSuccessListener { code -> result.success(code == Activity.RESULT_OK) }
                            .addOnFailureListener { result.success(false) }
                    }
                }
                "complete" -> {
                    manager.completeUpdate()
                    result.success(null)
                }
                else -> result.notImplemented()
            }
        }
    }

    override fun onDestroy() {
        updateListener?.let { updateManager?.unregisterListener(it) }
        super.onDestroy()
    }
}
