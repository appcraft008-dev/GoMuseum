# iOS 内购后端校验(App Store)设计

日期:2026-10-22 · 状态:用户 10-22 批准,已实现 · 出处:backlog「iPhone 版」B 线

## 1. 为什么做

iPhone 版要和 Android 同一个 App 原样上架(10-22 定)。通票(`paris_pass_7d` 等)是
**消耗型**内购,iOS 上买完必须由后端核对 Apple 的交易、再发权益 —— 现有的 Apple 校验
代码从来没被任何客户端用过,而且对不上我们的客户端(见 §2),等于没有。

**成功标准**:iOS 用户在 Sandbox 买一张通票 → 后端验真 → 发 `purchased_not_activated`
权益 → 客户端 `completePurchase`;Apple 退款 → 权益被撤。Android 购买/退款路径行为不变。

## 2. 已查证的事实(写方案的依据)

| 事实 | 出处 |
|---|---|
| 客户端走的 `in_app_purchase_storekit` 0.4.11 **默认启用 StoreKit 2**(`_useStoreKit2 = true`) | `~/.pub-cache/.../in_app_purchase_storekit-0.4.11/lib/src/in_app_purchase_storekit_platform.dart:34` |
| StoreKit 2 下 `serverVerificationData` = Apple 签名的交易 **JWS**(`verification.jwsRepresentation`),不是旧式 app receipt | 同包 `darwin/.../InAppPurchasePlugin+StoreKit2.swift:268,289`;`sk2_transaction_wrapper.dart:158` |
| iOS < 15 回落 StoreKit 1,交的是 base64 app receipt(另一种格式) | 同包 CHANGELOG 0.4.14+1 |
| 前端把 `serverVerificationData` 原样作为 `receipt_data` 发给 `POST /payment/verify`,`platform='ios'` | `frontend/.../payment_remote_datasource.dart:47-62` |
| 现有 `verify_apple_receipt` 调的是 Apple **已弃用**的 `verifyReceipt`,且按订阅读 `latest_receipt_info`;喂它 JWS 必然失败 | `backend/app/services/iap_verification_service.py:30-111` |
| 核心已商店无关:`grant_from_purchase` / `revoke_for_purchase` 只认 `store_transaction_id`;泄漏只在 `payment.py` 的平台分支和 Play 专用的 `/payment/rtdn` | `docs/architecture/identity-and-paywall.md` §8.3;`entitlement_service.py:625,694` |
| 退款对账脚本只查 `platform == "android"` 的行,iOS 行不会被它误发给 Play | `backend/scripts/reconcile_refunds.py:91` |
| `purchases.platform` 实际存的是请求里的 `ios`/`android`(列注释写的 `google\|apple` 与实际不符,不改) | `payment.py:165` → `entitlement_service.py:670` |
| Apple 官方 Python 库 `app-store-server-library` 3.1.2(Python ≥3.7),依赖 `attrs, PyJWT<3, requests<3, cryptography>=43, pyOpenSSL, asn1==3.2.0, cattrs` | PyPI JSON,10-22 查 |

## 3. 目标 / 非目标 / 反目标

**目标**
- `platform=ios` 时校验 StoreKit 2 交易 JWS,通过后走现有 `grant_from_purchase`(核心零改动,见 §4.3 唯一例外)。
- 接收 App Store Server Notifications V2,退款/撤销 → `revoke_for_purchase`。
- 全部离线验签,**不需要 .p8 密钥**即可上线和测试。

**非目标(推迟,§8)**
- 主动对账(Apple 版 `reconcile_refunds`):要 .p8 调 App Store Server API,账号开通后再做。
- 回应 Apple 的 `CONSUMPTION_REQUEST`(退款申请时提供消费信息)。
- 支持 iOS 13/14(StoreKit 1 收据)—— 改为最低 iOS 15(§4.6)。
- 商店适配器抽象(§8.4 原则仍成立:只有两家,`if platform` 分支够用)。

**反目标(做了也算失败)**
- 动到 Android 的校验/确认/RTDN/对账任何一行行为。
- 验签失败、配置缺失时放行(违反 I8/I15)。
- 幂等键用客户端给的任何字段而非 Apple 签名内的 `transactionId`(违反 I9)。

## 4. 方案

### 4.1 校验 JWS:用 Apple 官方库,不手写证书链

`app-store-server-library` 的 `SignedDataVerifier` 做了全部难点:x5c 证书链验到
Apple Root CA、ES256 验签、检查 `bundleId` 与 `environment`。手写证书链验证是安全代码,
写错 = 任何人能伪造通票,不自己造。

- **根证书**:`Apple Root CA - G3`(公开证书,从 apple.com/certificateauthority 下载)
  提交到 `backend/app/certs/AppleRootCA-G3.cer`。
- **两个 verifier**:Production(需要 `app_apple_id`,App Store Connect 里 App 的数字 ID)
  与 Sandbox(不需要)。先用 Production 验,`environment` 不符再用 Sandbox 验。
- `enable_online_checks=False`(不做 OCSP,免一次外网往返;JWS 签名本身已证明来源)。

新函数 `verify_apple_transaction(jws, product_id) -> dict`,返回形状**与
`verify_google_receipt` 一致**(`valid / transaction_id / product_id / platform / error`),
`payment.py` 下游不用区分。判 `valid=True` 需同时满足:

1. 验签通过(库抛 `VerificationException` → `valid=False, error="apple_jws_invalid"`)
2. `bundleId == APPLE_BUNDLE_ID`(库已查)
3. `productId == 请求里的 product_id` —— 否则 A 商品的 JWS 能冒充 B 商品
4. `type == "Consumable"`
5. 没有 `revocationDate`(已退款/撤销的交易不发权益)

`transaction_id` = JWS 内的 `transactionId`(I9:来自商店签名,不来自客户端)。
同一笔交易被重复上报(重启后 SK2 重投未完成交易)→ 命中现有幂等;被别的账号上报 → 现有 409。

旧的 `verify_apple_receipt` 与 `_get_apple_error_message` **删除**:从无客户端调用过,
留着只会让人以为 iOS 已支持(这正是本次发现问题的方式)。`APPLE_SHARED_SECRET` 随之不再读。

### 4.2 `payment.py` 改动面

只改 `if request.platform == "ios":` 这一行的调用目标:

```python
if request.platform == "ios":
    verification = await iap_service.verify_apple_transaction(
        request.receipt_data, request.product_id
    )
```

其余(`grant_from_purchase`、409、502、`log_event`、未知商品 400)原样复用。
Play 的 `acknowledge` 已在 `if request.platform == "android"` 里,iOS 不进。
**iOS 的交付确认(I19)= 客户端 `completePurchase`(SK2 `transaction.finish()`)**,
现有 `IapService._verifyAndDeliverProduct` 在后端成功后才调,失败留着下次启动重投 —— 不用改。

### 4.3 Sandbox 交易在 prod 怎么办(⚠️ 需用户拍板,见 §9-1)

`identity-and-paywall.md` §8.5 清单写着「沙盒/测试购买不得进入真实权益」。但:

- **App Review 审核员是在 prod 后端上用 Sandbox 账号买的**。Apple DTS 在开发者论坛答复:
  审核在 sandbox 环境进行,服务端应先按 Production 验、不符再按 Sandbox 验
  (developer.apple.com/forums/thread/683825、/thread/93773;10-22 查)。
  prod 拒 Sandbox → 审核员买票失败 → 以「内购不可用」拒审。
- 正式 App Store 安装包**只能**产生 Production 交易;Sandbox 交易只来自 TestFlight / Xcode 安装包和审核员。
  所以 prod 接受 Sandbox,白拿票的只有我们自己邀请的 TestFlight 测试员和审核员。

**建议**:prod 接受 Sandbox 交易,但给发出的权益打 `granted_reason="sandbox"`(列已存在,
现值 `purchase|beta|compensation`),便于统计时排除、需要时一键撤。
**Sandbox 票在产品上与真票完全一样**(能激活、7 天有效、真实消耗 TTS)—— 不加隔离分支
(设计者决定:审核员必须体验到完整付费流程;发票对象只有自己邀请的测试员和审核员,量可忽略)。
验证函数把 `environment` 带回给 `payment.py`,以便传 `granted_reason`。
这要给 `grant_from_purchase` 加一个默认 `"purchase"` 的关键字参数 —— 核心唯一改动,纯加法,
Android 调用方不传 = 行为不变。同时把 §8.5 那条清单改成「沙盒购买可进权益但必须可区分」。

### 4.4 退款通知:`POST /payment/apple-notifications`

App Store Server Notifications V2:Apple POST `{"signedPayload": "<JWS>"}`。

- 用同一对 verifier 验 `signedPayload`(`verify_and_decode_notification`);验不过 → 403。
- `notificationType in {"REFUND", "REVOKE"}` → 再验内层 `data.signedTransactionInfo`,
  取 `transactionId` → `revoke_for_purchase(db, txn, reason="refunded" | "revoked")`。
- 其他类型(`CONSUMPTION_REQUEST`、`REFUND_DECLINED`、`TEST` 等)→ 只记日志。
- 验签通过后**始终 200**(非 2xx Apple 会重试),与 `/payment/rtdn` 的 204 同理。
- 限流 `120/minute`,理由同 RTDN:公开未认证端点,验签要做证书运算。
- 幂等:`revoke_for_purchase` 找不到订单返 False,重复推送无副作用。
- `log_event(db, "purchase_refunded", ...)` 与 RTDN 一致,便于同一处看退款。

App Store Connect 里 Production URL 和 Sandbox URL 都填 prod 的
`https://api.gomuseum.app/api/v1/payment/apple-notifications`(staging 联调时 Sandbox URL 可临时改成 staging)。

### 4.5 配置(`app/core/config.py`,全部加法)

**商品 ID 两端必须同名**:App Store Connect 里建的消耗型商品 ID 与 `PASSES` 的 key 一字不差
(`paris_pass_7d`、`nl_pass_7d`),因为 `pass_scope/pass_duration` 都按 ID 查。Apple 商品 ID
删除后**永不可复用**,建错别删、改名新建。Bundle ID 已核对:iOS 工程 `PRODUCT_BUNDLE_IDENTIFIER = com.gomuseum.app`。

| 变量 | 默认 | 说明 |
|---|---|---|
| `APPLE_BUNDLE_ID` | `com.gomuseum.app` | 与 iOS 工程一致 |
| `APPLE_APP_ID` | `None` | App Store Connect 里的数字 App ID。**缺失 → Production JWS 一律拒绝**(I15),Sandbox 仍可验 —— 所以账号开通前 Sandbox 联调不受阻 |

已有的 `APPLE_CLIENT_ID/TEAM_ID/KEY_ID/PRIVATE_KEY_PATH` 属 Apple 登录,不碰。

### 4.6 客户端:最低系统改 iOS 15

iOS 13/14 走 StoreKit 1,交的是另一种格式;为这部分设备(iPhone 6s/SE 一代可升到 15,
真正卡在 14 的极少)维护第二套校验不值。`IPHONEOS_DEPLOYMENT_TARGET` 13.0 → 15.0,
`Podfile` 写明 `platform :ios, '15.0'`。并入 PR #1051(同属 iOS 工程配置,当前为草稿、未合并;
若它先合了就单开 PR)。**无 Dart 改动。**

### 4.7 依赖

`pyproject.toml` 加 `app-store-server-library (>=3.1.2,<4.0.0)`,**必须同步 `poetry lock`**
(项目教训:只改 pyproject 不 lock,镜像构建装不上)。`asn1==3.2.0` 是精确钉版,
lock 时若与现有依赖冲突,先停下报告,不换手写方案。

### 4.8 文档

- `docs/architecture/identity-and-paywall.md`:§8.3 现状、§8.5 沙盒条(按 §9-1 结论)、
  端点表加 `/payment/apple-notifications`;I19 补「Apple = 客户端 finish」。
- `payment.py` 里 `/verify` docstring 的 iOS 示例改成 JWS。

## 5. Android 不受影响的保证

| 改动 | 为什么碰不到 Android |
|---|---|
| `verify_apple_transaction` 新函数、删旧 Apple 函数 | 只在 `platform == "ios"` 分支被调 |
| `/payment/apple-notifications` 新端点 | 新路由;`/payment/rtdn` 不动 |
| `grant_from_purchase` 新增可选参数 | 默认值 = 现行为;Android 调用处不改 |
| 新依赖 | 只在 iOS 路径 import(函数内 import,与现有 `google.oauth2` 用法一致),导入失败也不影响 Android 请求 |
| `reconcile_refunds.py` | 不改;它只查 android 行 |

`tests/integration/test_purchase_verification.py` 里现有 Android/RTDN 用例**一个不改**,全绿即证明。

## 6. 测试(没有 Apple 账号也能全做)

测试里用 `cryptography` 现生成一条「假根 CA → 中间 → 叶子」证书链,把假根传给
`SignedDataVerifier(root_certificates=...)`,用叶子私钥签 JWS。这样能构造任意交易:

- 合法 Production / 合法 Sandbox → 发权益(Sandbox 的 `granted_reason` 按 §9-1)
- 签名被篡改 / 用别的根签 → 拒
- `bundleId` 不符、`productId` 与请求不符、`type` 非 Consumable、带 `revocationDate` → 拒
- `APPLE_APP_ID` 缺失 → Production 拒、Sandbox 过
- 同一 JWS 两个账号上报 → 第二个 409(复用现有语义)
- 通知:REFUND 撤权益、REVOKE 撤权益、未知类型 200 不动数据、坏签名 403、重复推送幂等
- 回归:现有 Android/RTDN 测试原样通过

真机/Sandbox 端到端(账号开通后):App Store Connect 建 App 记录与同名消耗型商品 → 配
`APPLE_APP_ID` → Sandbox 测试员在 TestFlight 包里买 → 查 `purchases`/`entitlements` 行 →
App Store Connect 里对该笔发起 Sandbox 退款 → 确认权益被撤。

## 7. 上线顺序

1. 后端 PR → staging → main:**现在就能上 prod**。没有任何 iOS 客户端存在,新代码在 prod 上
   不会被调用;Android 无感。
2. 账号开通后:配 `APPLE_APP_ID`(prod/staging env)、App Store Connect 填通知 URL。
3. TestFlight Sandbox 端到端(§6 末段)。
4. 送审。⚠️ 新建的内购商品要**和 App 版本一起提交审核**(版本页勾选),否则审核时商品取不到。

## 8. 推迟项(写进 backlog)

- Apple 退款主动对账:`.p8` + App Store Server API `Get Transaction Info` 查每笔
  `revocationDate`,并入 `reconcile_refunds.py` 的 iOS 分支(护栏同 Android:默认 dry-run、比例上限)。
  触发:账号开通且第一笔真实 iOS 收入出现。
- `CONSUMPTION_REQUEST` 回应:可降低恶意退款,要 .p8。触发:出现第一笔 iOS 退款。
- `appAccountToken`(购买时绑账号 UUID):现有归属校验已够,不做。

## 9. 用户拍板(10-22 两条均同意)

1. **Sandbox 交易在 prod 是否发权益**(§4.3)。建议:发,标 `granted_reason="sandbox"`;
   否则审核员买不了票、会被拒审。
2. **最低 iOS 版本 13 → 15**(§4.6)。建议:改。

## 10. 留给实现者的

- verifier 实例化放模块级懒加载还是每次新建(证书解析有成本,懒加载单例即可)。
- 测试证书链的生成放 `tests/fixtures/` 还是测试文件内(按现有 `oidc` fixture 风格)。
- `revoke_for_purchase` 的 `reason` 对 REVOKE 用 `"revoked"`(列注释已有该值)。
