# iOS 上架填表手册(App Store Connect)

账号开通后照此填写。文案见 `docs/marketing/aso/app-store/metadata-v1.md`;
上架整体进度见 `docs/ops/backlog.md` 第五节「iPhone 版」。

## 1. App 隐私问卷(App Privacy)

依据隐私政策 `deployment/legal-src/privacy.en.html` 第 2 节,
与 App 内隐私清单 `frontend/gomuseum_app/ios/Runner/PrivacyInfo.xcprivacy` 一一对应。**改一边要同步改另一边。**

- 「是否收集数据」:是
- 「是否用于跟踪(Tracking)」:**全部否**。不请求 ATT 跟踪授权,Firebase 只用默认自动事件,不做广告。

| Apple 分类 | 数据类型 | 用途 | 关联到身份 | 依据 |
|---|---|---|---|---|
| 联系信息 | 电子邮件地址 | App 功能 | 是 | 账号 |
| 联系信息 | 姓名 | App 功能 | 是 | 用户名 / Google、Apple 账号基本资料 |
| 标识符 | 用户 ID | App 功能、分析 | 是 | 账号 ID;自有服务器使用事件带账号 ID |
| 标识符 | 设备 ID | App 功能 | 是 | 免费额度与防滥用(`identifierForVendor`) |
| 购买项目 | 购买历史 | App 功能 | 是 | 通票发放 / 退款 |
| 用户内容 | 照片或视频 | App 功能 | 是 | 识别要上传照片;用户勾选「发给我们」时保留 ≤90 天 |
| 用户内容 | 客户支持 | App 功能 | 是 | 反馈框文字 |
| 用户内容 | 其他用户内容 | App 功能 | 是 | 随照片一起提交的备注、搜索词、墙签文字 |
| 使用数据 | 产品交互 | 分析 | 是 | 自有服务器的使用事件、Firebase Analytics |
| 诊断 | 崩溃数据 | 分析 | 否 | Crashlytics,未绑定用户 ID |
| 诊断 | 性能数据 | 分析 | 否 | Crashlytics |

**不申报**:位置。位置只在手机上算到各馆的距离,不上传(隐私政策原话「never uploaded to our servers」)。
Apple 的定义是「传出设备才算收集」,所以不申报。

## 2. 审核备注(App Review Information → Notes)

演示账号要**用户自己在 prod 注册**一个邮箱账号(建议 8 位以上密码),填进 Sign-in information。
**不要把密码写进仓库。**

✅ 已验证(10-26):「对着另一块屏幕上的名画拍照能认出来」——用户日常测试大多就是这样拍的,识别在后端、iOS 与 Android 同一套。

```
GoMuseum is an audio guide for Paris museums (Louvre, Musée d'Orsay, Musée de l'Orangerie, Petit Palais).

How to test without being in a museum:
- Recognition: tap the camera button and point it at a famous artwork shown on another screen (e.g. the Mona Lisa or Van Gogh's "Starry Night over the Rhône" from Orsay). The app identifies it and opens its guide.
- Search: open a museum and search by artwork or artist name (e.g. "Monet").
- Browsing, search and written guides work as a guest — no account needed.

In-app purchase (consumable "7-day Paris pass"):
- Buying a pass requires signing in (Sign in with Apple is available). The pass is a consumable product, so it cannot be restored by StoreKit; tying it to the account is the only way users can get it back after reinstalling or switching phones. Free features never require an account.
- A demo account is provided above.

Other:
- Location (optional) is used only on the device to show nearby museums; it is never uploaded.
- Account deletion: Settings → Delete account.
- The app is an independent guide and is not affiliated with the museums.
```

⚠️ 审核风险(5.1.1):Apple 常以「非账号型内购不得要求先注册」拒审。backlog 里的决定是先按现状送审、靠上面这段说明;**被拒再议游客购买**。

## 3. 其他一次性设置

- 主类别「旅游」,次类别「教育」;年龄分级问卷全选「无」→ 4+
- 出口合规:`Info.plist` 已设 `ITSAppUsesNonExemptEncryption = false`,上传后不会再问
- 销售范围:**取消勾选中国大陆**(要 ICP 备案,10-22 定)
- 内购商品:消耗型 `paris_pass_7d`、`nl_pass_7d`。ID 必须与后端 `PASSES` 同名,**删了不能复用**
- App Store 服务器通知 URL(生产 + Sandbox 两个都填):`https://api.gomuseum.app/api/v1/payment/apple-notifications`,版本选 V2
