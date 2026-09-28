# 跨城市/跨国扩展（上新城市不发版 · 通票目录下发 · 国立博物馆隐身演练）

> **状态：📝 方案已定稿，未实现（2026-09-28）。**
> 目标（用户原话）：扩展博物馆——包括跨城市、跨国——**对用户无感，不需要更新前端 App**。
>
> 与 [2026-09-20 上新馆可见性闸](2026-09-20-museum-visibility-gate-design.md) 配套：
> 那份管「一家馆准备期间不被看见、一条 SQL 放出」（**同城加馆**已够用）；
> 本文管「**新城市/新国家**」额外需要的东西——几乎全在付费链路上。

## 已定决策（2026-09-28，用户逐条拍板）

| # | 决策 | 备注 |
|---|---|---|
| D1 | **通票按商品分开、由后端下发**（方案 A） | 否决方案 B「一张通用票、激活时绑城市」：各地无法分别定价 |
| D2 | **免费识别 5 次全局共用**（所有城市、所有馆一个池子） | 维持现状，零改动 |
| D3 | **可见性闸现在解冻实施** | 它的解冻条件就是「下一家馆开灌之前」 |
| D4 | **推 Play 正式轨道推迟到本文第四节四步做完** | 理由见 §一 |
| D5 | **第二国 = 荷兰，首馆国立博物馆（Rijksmuseum），商品 ID `nl_pass_7d`** | ID 永久不可改；选 `nl_` = 荷兰按**国家**出票 |
| D6 | **国立博物馆以隐身状态上目录做演练**：只收有图的绘画；3-5 件出中英正文，不翻译、不做音频 | 公开一个空馆 = 半开的馆 + 懒生成被任何人点燃 |
| D7 | **识别不限次也只在票覆盖的馆内**；范围外按免费用户处理（2026-09-29 用户纠正我的初稿） | 见 §3.4 |

## 一、为什么必须在推正式轨道之前做

现在零真实用户、Console 在内测轨道。**第一个推上正式轨道的 APK，会把其中的每一处
硬编码永久带进每台装机**。如果「只认巴黎」进了那个包，第二个国家上线那天，已装用户
必须更新 App 才能买票——正好违背目标。之后再改，只能等用户慢慢升级。

所以这是**一次性去硬编码**：付一次前端改动，之后开任何城市/国家都只改后端。

## 二、现状审计：同城无感，跨城不行

**已经无感的**：首页/探索页馆列表来自 `GET /museums`，城市 chips 由返回数据去重生成；
内容语言 server-driven；可见性闸（设计完成）覆盖「准备期隐身」。

### 2.1 前端硬编码（跨城必须发版的根源）

| 位置 | 写死了什么 |
|---|---|
| `core/services/iap_service.dart:25-28`、`payment/data/pass_product.dart:22`、`payment/presentation/pages/benefits_page.dart:151` | 商品 ID 只有 `paris_pass_7d` |
| `l10n/app_*.arb` `paywallTitle`（9 语） | 「巴黎 7 日通票」 |
| `payment/presentation/widgets/gm_ticket.dart:165` | 票面 `GOMUSEUM · PARIS` |
| `payment/presentation/widgets/paywall_sheet.dart` `_kPassDuration` | 7 天 |
| `content/data/models/museum_summary_model.dart:74` `localizedCity` | 城市名只有中/英两套 |
| `l10n/app_*.arb` `paywallPitch`（10 语，8 处调用：`paywall_sheet.dart`、`benefits_page.dart`） | **点名巴黎四馆**：「卢浮宫、奥赛、橘园、小皇宫四馆全部语音讲解」——荷兰用户付款那一刻看到的是巴黎的馆名（review 发现） |
| `core/services/iap_service.dart:68-98` | 商品详情只在**启动时**按静态 ID 表查一次；`purchaseProduct` 在缓存里找不到就抛「商品不存在」——光换 ID 不重查，荷兰票照样买不了（review 发现） |

### 2.2 后端对通票范围「半盲」

`audio_access` 已按城市校验（`museums.py:50-63`），但以下几处**完全不看范围**。
一旦用户同时持有两国的票，或者持巴黎票走进荷兰的馆，就会出错：

| 位置 | 现状 | 持巴黎票在荷兰馆的后果 |
|---|---|---|
| 402 响应 `{"reason":"pass_required"}` | 不说该买哪张 | 付费墙卖巴黎票 → 用户买了 → 仍被锁 = **丢钱洞** |
| `GET /entitlements/me` → `summary()` | `resolve_state(db, user_id)` 不带范围 | 返回 `state=active / audio_any=true`，前端本地闸放行，点播放却 402 |
| `POST /entitlements/activate` → `activate()` | 不带范围 | 两张未激活票并存时，可能在荷兰**烧掉巴黎那张** |
| `POST /entitlements/audio/unlock` | `resolve_state==ACTIVE` 就幂等返回 | 持巴黎有效票在荷兰点「用 1 次解锁」→ 什么都没解锁，**卡死** |
| `pass_scope()` 找不到商品时默认 `"paris"` | 配错不报错 | 新国家漏配商品时，静默当成巴黎票 |

## 三、设计

### 3.1 范围语法：城市 / 国家 / 全部

`PASSES[*].scope` 取值：

```
city:paris      # 按 Museum.city_en（大小写不敏感）
country:NL      # 按 Museum.country（ISO 3166-1 alpha-2）
*               # 全部
paris           # 旧写法，等同 city:paris —— DB 里已有的 Entitlement.scope 不迁移
```

`covers_museum(scope, museum)` 改为吃整个馆（要同时读 `city_en` 与 `country`）。
**城市票还是国家票，是后端配置，随时可改，不需要发版**——前提是前端不假设「范围就是城市」（见 3.3）。

`pass_scope()` 去掉 `"paris"` 默认值：未知商品 = 不覆盖任何馆（宁可锁住，不可错放）。
顺手删 `entitlement_service.py:41` `PASS_DURATION`（零调用方，且写死 `paris_pass_7d` 键）。

### 3.2 商品目录加展示字段

```python
PASSES = {
    "paris_pass_7d": {"days": 7, "scope": "city:paris",
                      "label": {"zh": "巴黎", "en": "Paris", ...十语}},
    "nl_pass_7d":    {"days": 7, "scope": "country:NL",
                      "label": {"zh": "荷兰", "en": "Netherlands", ...十语},
                      "on_sale": False},   # 演练期不卖;放出时改 True
}
```

**馆 → 在售商品**：`pass_for_museum(museum)` = 第一个 `on_sale` 且范围覆盖该馆的商品，
没有就是 `None`。它是下面所有下发点的单一真相源。

### 3.3 下发契约（全部加法）

**一个形状，三处下发**：

```json
"pass": {"product_id": "nl_pass_7d", "days": 7, "label": "荷兰",
         "covers": ["国立博物馆"]}
```

`label` 按请求 `language` 取，缺语言回退 en。前端只显示它，**不知道它是城市还是国家**。
`covers` = 该商品范围内**已放出**的馆的本地化馆名（走 `visible_museum_ids`，隐身馆不泄漏；预览者可见），
替代写死四馆名的 `paywallPitch`——卖点「具体能听哪几家」保留，且上新馆自动变长。

| 下发点 | 用途 |
|---|---|
| `GET /museums/{slug}`（馆包）加 `pass` | 进馆就知道这里卖哪张票，付费墙提前查好价格 |
| 402 `detail` 加 `pass` | 撞墙那一刻兜底（拿着老馆包缓存也不会卖错票） |
| `GET /museums`（馆列表）每项加 `city_i18n` 对应的本地化城市名 | 城市 chips / 卡片十语显示 |

城市十语名走 `museums.yaml`，与馆名 `names:` 同款写法（新增 `city_names:`），缺语言回退 `city_en`。

### 3.4 权益按馆求值（全部加法，不带参数 = 旧行为）

| 端点 | 新增可选参数 | 语义 |
|---|---|---|
| `GET /entitlements/me` | `?museum=slug` | `state` / `can.audio_any` / `expires_at` 只看**覆盖该馆**的票 |
| `POST /entitlements/activate` | `?museum=slug` | 只激活覆盖该馆的那张 |
| `POST /entitlements/audio/unlock` | （无新参数） | 用 qid 反查馆，`ACTIVE` 判断改为「覆盖该馆的票是否有效」 |

`GET /entitlements/me` 不带参数（设置页、权益页）另加 `passes: [{product_id, label, state, expires_at, activate_by}]`，
权益页据此显示「荷兰 7 日通票 · 有效至…」「巴黎 7 日通票 · 待激活」，
用户看得出**哪张票管哪里**。

**识别也按范围（D7，2026-09-29 用户纠正）**：通票只在它覆盖的馆里「识别不限次」，
范围外的馆里持票人**就是免费用户**。

> 🔴 我初稿写的是「识别不分范围，因为识别发生在知道是哪家馆之前」——**理由是错的**：
> 计费本来就在识别**之后**（`recognize_billed` 在 `outcome == "match"` 后才扣），
> 那时馆已知。而且后果比「多识别几次」严重：每次命中都会 `_unlock_audio` 把该件
> 主讲解段**永久**加进 `free_audio_qids`（`recognition/service.py:366`），票生效期内
> 不扣额度（`:424`）。即：买最便宜的荷兰票，到巴黎见一件拍一件 = 巴黎主讲解音频全免费，
> 票过期后仍然能听。`/recognize/confirm`（`recognize_global.py:140-145`）同型。

规则（命中后按**命中的馆**判）：

| 命中的馆 | 票覆盖该馆 | 票不覆盖、免费额度 > 0 | 票不覆盖、额度 = 0 |
|---|---|---|---|
| 行为 | 不扣额度 + 解锁主讲解 | 扣 1 次 + 解锁（同免费用户） | 402，`detail.pass` = **该馆**的在售商品，不返回结果、不解锁 |

- 前置闸（`check_access`）保持宽松：持任一有效票或额度 > 0 即放行识别；范围判定在命中后做。
  按馆识别端点（馆已知）直接在前置闸按馆判。
- 候选态不变（不扣不解，挪到 confirm）；`/recognize/confirm` 按同一张表判。
- `_pass_active(db, user_id)` 改为 `_pass_covers(db, user_id, museum)`，与音频闸共用 `covers_museum`。
- 免费 5 次全局共用（D2）不变。

### 3.5 前端一次性改动

1. 商品 ID 从后端取（馆包 / 402 的 `pass.product_id`）；删掉 `kParisPass7d` 常量与 `kProductIds` 静态表。
   **购买前按该 ID 现查 `queryProductDetails`**，不用启动时的缓存（`purchaseProduct` 现在找不到就抛异常）。
2. `paywallPitch` 改带占位符「不限次拍照识别，{museums}全部语音讲解」，`{museums}` = `covers` 按语言的列举符拼接（中日「、」，其余「, 」）。
   `paywallTitle` 改带占位符：「{label} {days} 日通票」（9 语重写）；票面刻印 = `label` 英文大写（`GOMUSEUM · NETHERLANDS`）；删 `_kPassDuration`，用 `pass.days`。
3. 馆内所有权益请求带 `?museum=slug`；本地闸（`canAudioAny`）改读按馆求值的结果。
   权益 provider 改为**按 slug 的 `autoDispose.family`**（同 `museumDetailProvider` 的写法）——现在的 `entitlementsProvider`/`BenefitsState`
   是全局单例，不按馆分键会把 A 馆的「可播」带进 B 馆；不带 autoDispose 的 family 会把错误态钉死（#630 同型）。
4. `localizedCity` 改读城市十语名，回退链保留。
5. 权益页按 `passes[]` 列出每张票及其范围。
6. **容错**：`pass` 为 null（后端老版本/馆没配商品）→ 付费墙回落为「暂未开售」，**绝不回落到巴黎票**。

### 3.6 可见性闸 spec 的三处补充（已回写该文件 §九）

1. **解冻**（D3）。
2. **暴露面用测试自动遍历**：遍历 `app.routes` 里所有带 `{slug}`/`{qid}` 的路由，断言都经过 `resolve_museum`/`museum_of_qid`——第 12 个端点不会再靠人记。
3. **放出前置检查**：`pass_for_museum(museum)` 非 None 才允许 `published_at` 写入（`onboard_verify` 加一项）。

## 四、实施顺序（推正式轨道的前置条件）

1. **可见性闸**（按 9-20 spec 实现 + §3.6）→ 后端，CD 上 prod。
2. **通票下发 + 权益按馆**（§3.1-3.4）→ 后端先上 prod（加法，老包不受影响）。
3. **前端一次性改动**（§3.5）→ 出包内测。
4. **国立博物馆隐身演练**（§五）→ 用正式签名包 + 预览账号验收。
5. 四项全绿 → 推正式轨道（⛔ 用户操作）。

## 五、国立博物馆隐身演练

**数据源**：旧的 key 制 `rijksmuseum.nl/api` 已于 2025-11 停服，新服务 `data.rijksmuseum.nl`
（Linked Art，无需 key，公开）。**演练只用现有 Wikidata 目录管线**（P195 = 国立博物馆），
预期零新代码；官方 CC0 高清图源适配器（[[collection-coverage-strategy]] P2②）留到正式上馆。

**范围**：有图的绘画（P31=Q3305213 且有 P18）。正式上馆时再加展出的装饰艺术、船模、玩偶屋。
⏳ 件数待查（Wikidata 计数本次会话被权限检查拦下，未取到）——若过大，按热度截 TOP N。

**步骤**：
1. `museums.yaml` 加 `rijksmuseum`（`city_en: Amsterdam`、`country: NL`、十语馆名与城市名），`published_at` 保持 NULL。
2. prod 跑 catalog → names → images → backfill（⛔ prod 写由用户执行）。
3. 挑 3-5 件 `generate --langs en,zh`，**不翻译、不做音频**。
4. Console 建 `nl_pass_7d`（价格待定，可低于巴黎——首发只有一家馆），`PASSES` 里 `on_sale: False`。
5. 预览账号（`can_preview`）用正式签名包验收：

| # | 验什么 | 通过标准 |
|---|---|---|
| 1 | 探索页 | 出现「阿姆斯特丹」chip，城市名十语正确；**普通账号看不见** |
| 2 | 付费墙 | 在国立博物馆显示「荷兰 7 日通票」+ Play 本地化价格 |
| 3 | 范围隔离 | 持巴黎有效票的账号在国立博物馆被拦，权益页写明「巴黎 7 日通票」 |
| 4 | 激活不串票 | 同时持两张未激活票，在荷兰激活只动 `nl_pass_7d` |
| 5 | 购买链路 | 许可测试员买 `nl_pass_7d` → 验证 → 发票 → 激活 → 国立博物馆出声（需临时 `on_sale: True`） |
| 6 | 识别 | 拍国立博物馆绘画命中本馆，不串到巴黎四馆 |
| 7 | 识别范围 | 只持荷兰票、免费额度用完的账号在巴黎馆拍照命中 → 弹**巴黎**通票付费墙，`free_audio_qids` 不增加 |

演练结束后国立博物馆**保持隐身**，直到正式内容做完（按小皇宫的分批节奏）再放出。

## 六、自检

**范围 × 馆 矩阵**（按 [[test-across-config-dimension]]，两侧都要测）：

| | 巴黎馆 | 荷兰馆 |
|---|---|---|
| 持 `city:paris` 票 | 放行 | **拦** |
| 持 `country:NL` 票 | **拦** | 放行 |
| 持 `*` 票 | 放行 | 放行 |
| 无票 | 拦 | 拦 |

对 `audio_access`、`/me?museum=`、`/activate?museum=`、`/audio/unlock`、**`recognize_billed` 命中后计费、`/recognize/confirm`** 各跑一遍。
识别两格额外断言：范围外命中时 `free_audio_qids` **没有增加**（断言 402 不够——先解锁后 402 的实现照样全绿）。额外：

- 旧写法 `scope="paris"` 的存量权益行，行为与 `city:paris` 完全一致。
- 未知商品 ID：不覆盖任何馆（不再默认巴黎）。
- `/activate?museum=` 同时持两张未激活票：断言**另一张的 `activated_at` 仍为 NULL**。
- 402 的 `pass.product_id` 与馆包的一致（同一个 `pass_for_museum`）。
- 前端：`pass` 为 null 时付费墙不出现任何商品 ID 硬编码回退（grep 断言 `paris_pass_7d` 字面量不再出现在 `lib/`）。

## 七、review 结论（2026-09-29，已折入）

按 CLAUDE.md 规则 6 跑独立 review（换模型，只给目标和代码、让它自己对照查）。
**§2.1 五行、§2.2 五行逐条 file:line 复核成立**；购买验证端点（`payment.py`）本就按 `is_pass_product` 判、与商品无关；
`Museum.country` 列已存在且四馆均为 `FR`；Android 配置、货币、时区均无写死。

| 严重度 | 发现 | 处置 |
|---|---|---|
| 🔴 | `paywallPitch` 十语写死巴黎四馆名，付款页对荷兰用户卖巴黎的馆 | §2.1 补行；§3.3 加 `covers`；§3.5 第 2 条 |
| 🟠 | IAP 商品只在启动时查一次，换 ID 不重查照样抛「商品不存在」 | §2.1 补行；§3.5 第 1 条 |
| 🟠 | 权益 provider 全局单例，`?museum=` 无处落 | §3.5 第 3 条改 `autoDispose.family` |
| 🔵 | `PASS_DURATION` 死代码写死巴黎键 | §3.1 顺手删 |

排除项（review 查过、不是缺口）：`content.py` `_require_tts_access` 的 qid 分支是死代码（ad-hoc TTS 已返 410）；
识别调用 `resolve_state` 不带城市 = D2/§3.4 的既定设计。

## 八、明确不做

- 按用户位置/IP 排序首页馆列表：馆少时无意义，等城市多了再说（纯后端，届时不需要发版）。
- 跨城同名作品识别撞车（如罗丹《思想者》多地铸件）：荷兰演练不涉及，第二个**同时有雕塑铸件**的城市前再做（纯后端，用足迹判最近所在馆）。
- 新的界面语言（如荷兰语、葡萄牙语）：客群是外国游客，十语足够；真要加界面语言躲不开发版。
