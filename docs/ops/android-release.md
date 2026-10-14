# Android 出包与发版核验

> 2026-10-14 从 `museum-api-contract.md` 纪律 36 移来(与博物馆 API / 新馆扩容无关,属前端发版流程)。**编号仍叫「纪律 36」**,代码注释与历史文档按号引用。

36. **出包核验必须从产物里读,不能从源码里读;清单本身要有来源**(2026-09-20 v35 添)。
   Android 出包有一组"错了就整包作废、而且构建全程不报错"的属性。核验它们时
   **唯一有效的证据是从 aab 里把值读出来**,"我刚改过源码"不算证据 ——
   改了源码但没参与构建、构建用了缓存、改的是另一个 flavor,都会让两者对不上。

   | 属性 | 怎么从产物里读 | 错了的后果 |
   |---|---|---|
   | versionCode / 包名 | `build/app/intermediates/packaged_manifests/prodRelease/**/AndroidManifest.xml` | 传不上去 / 传成 staging 包 |
   | 签名 | `keytool -printcert -file <aab>/META-INF/UPLOAD.RSA`,比对 keystore 指纹 | **静默回落 debug 签名**,Play 直接拒 |
   | `API_BASE_URL` | 从每个 ABI 的 `base/lib/*/libapp.so` 里提字符串 | 连 localhost,开屏白屏 |
   | **版本脚注 `kVersionFootnote`** | 同上,grep `GoMuseum x.y.z (N)` | 见下 |

   ⭐ **本条的由来,是核验清单漏了最后一项,而漏的恰好就是错的那项。**
   v35 出包时 `pubspec.yaml` bump 了、脚注常量没动,四项核验全绿、包发出去了,
   是 CI 的 `settings_version_test` 把它拦下的。**清单是凭记忆列的,只覆盖列清单的人
   想得到的错法** —— 所以清单要有来源:**每道钉住出包属性的测试,都必须在清单里有对应的一行**。
   (`aapt2` 读不了 aab —— 它的 manifest 是 protobuf 不是 AXML,别在这上面浪费时间。)

   ⚠️ 关于 `kVersionFootnote` 为什么是手写常量而不是读 pubspec:读它要引
   `package_info_plus`,那是**原生插件、会改插件树**,而 #434 那个致命缺陷正长在
   "CI 与出包机解析出不同插件树"的缝里,只有真机能发现。为一行脚注冒这个险不划算。
   **它同时被 `feedback_repository.dart` 当 `app_version` 上报** —— 忘了改不只是
   显示错,是之后所有用户反馈都标着上一个版本号,排查时会认错版本。

   ⚠️ 构建坑:**不带 `--flavor prod` 时 gradle 会把 staging 和 prod 两个 flavor 都构建**,
   而 flutter 工具找的是无 flavor 的 `app-release.aab` → 报
   `Gradle build failed to produce an .aab file`。**包其实已经生成了**,这条错误信息会骗人。
   出包命令固定为:
   `flutter build appbundle --flavor prod --release --dart-define=API_BASE_URL=https://api.gomuseum.app`

   ⚠️ 出包前先确认目标 versionCode 在 Play 侧没被占(号被占时别逐个 +1 猜,
   去 Console 看最高号一次到位 —— 曾为此白出三版包)。

   ⭐ **2026-09-29 V40 又漏了 `kVersionFootnote` —— 本条早就写着,但出包前没回来读。**
   而且 bump PR 在 CI 红着的情况下被 `gh pr merge` 合进了 staging(合并命令前没判 checks 全绿),
   第一版 V40 作废重出。**纪律写在文档里不等于会被执行**:①出包是重复性流程,**动手前先打开本条逐项过**;
   ②**合并前必须确认 checks 全部 pass**(脚本里显式判 non-pass 数为 0 才 merge),CI 红就是红,不因"只改了版本号"放行。
