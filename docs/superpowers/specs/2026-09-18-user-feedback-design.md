# 用户反馈渠道设计（一条管道、两类反馈、坐标全自动）

> 2026-09-18 brainstorm 定稿。补上 AI 内容质量原则里唯一没建的那一环。
> 与 [[content-enrichment-mechanism]]、[[text-quality-metrics]]、
> [[grounding-gate-visual-description-blindspot]] 配套——那些是**生成侧**的闸，
> 这个是**消费侧**的兜底。

## 为什么要做

**理由一：契约里它是必需品，而它不存在。** CLAUDE.md 的「AI 内容质量原则」写着
`人只审形式安全（空段/乱码/语言/冒犯），不审事实对错；错漏靠用户反馈兜底`。
生成侧的闸都建了——接地闸、忠实度闸、语言一致性闸、锐度闸、响度闸。
唯独兜底这一环：`grep -i feedback backend/app frontend/*/lib` **零命中**。
兜底的是空气。

**理由二：Play 发版在即，站内反馈是截流。** 一个想抱怨的用户找不到站内通道，
他会去 Play 打一星。对一个还没放量、评价样本量极小的 App，前 20 条评价决定后面的
转化率。iOS 侧连 Play 都没有。

> ⚠️ 期望值：反馈按钮的行业转化率 <1%，而当前**零真实用户**。短期内这个功能
> 产出不了任何数据。判断标准不是"能收多少反馈"，是"出事时有没有通路"。
> 所以——**最省形态就是对的形态**，别在这上面做精美 UI。

## 原则

### 1. 两类反馈价值差一个数量级，但共用一套管道

| | 藏品内容错漏 | App 整体意见 |
|---|---|---|
| 价值 | **不可替代**。没有任何外部渠道会告诉你「小皇宫 2040 件的繁体讲解念错了」 | 主要在**截流**，不在信息量 |
| 可行动性 | 自带精确坐标，直接定位 DB 行 | 量少、杂、重复（"闪退""不好用"） |

共用端点、共用表、共用面板 widget，靠 `scope` 区分。不为第二类单开一套。

### 2. 坐标全自动上报，用户只选现象

| 字段 | 来源 | 为什么必须自动 |
|---|---|---|
| `language` | `guide_page` 的 **API 语言参数** | 见下方硬约束 |
| `qid` / `museum_slug` | 当前页 | 用户不可能知道 qid |
| `device_id` / `user_id?` | 已有身份层（`deviceIdProvider`） | 游客也要能反馈——最需要反馈的时刻往往正是游客态 |
| `app_version` / `platform` | `kVersionFootnote` / `Platform` | 闪退类反馈没版本号等于没有 |

**🔴 language 硬约束**：必须取 `guide_page` 传给 API 的那个 `language`
（`guide_page.dart:1074` 注释：「API 语言参数（繁体已 zh-hant）」），
**不是 UI locale**。繁体在这里是 `zh-hant` 不是 `zh`，带错 = 修错行。

10 语 = 10 份独立内容（独立生成、独立翻译、独立音频、独立 audio_key）。
一条不知道语种的内容反馈**不可行动**——你不知道该改哪一行。这不是"要不要区分
语言用户"的产品选择题，是数据模型决定的硬要求。

### 3. 绝不让用户区分「内容问题 vs 音频问题」

用户不懂这个分层。繁体念错那次（[[tts-selfhost-voxcpm-recipe]]）**文本是对的、
TTS 念错了**，用户只会说"读得很怪"。让他在面板里选「文本问题/音频问题」会选错，
而且多一步。

**给现象，不给分类**：chips 是用户能感知的现象，映射到技术分层是后台的事。

附带好处：预设 `kind` **可枚举 = 可统计 = 能按命中数排修复优先级**。纯自由文本
做不到这点，而且文本会以 10 种语言进来，读它要翻译。chips 是免翻译的那一半。

### 4. 读的路径不做，前面全白搭

没有读它的路径 = 没做这个功能。按项目既定惯例（`app_events` 的
「不建后台，靠 `ops_report.py` 出数」）：一个聚合脚本，**不建后台**。

## 契约（纯加法，后端可先行独立部署）

```
POST /api/v1/feedback  →  204 No Content
{
  "scope": "object" | "app",
  "museum_slug": "petit-palais",   // scope=object 必填
  "qid": "Q3937645",               // scope=object 必填
  "language": "zh-hant",           // scope=object 必填；API 语言参数
  "kind": "content_wrong",         // 白名单
  "text": "……",                    // 选填，≤1000
  "app_version": "GoMuseum 1.0.0 (31)",   // kVersionFootnote 整串,带前缀
  "platform": "android" | "ios"
}
```

新端点、不动老端点、老 App 无感 → 符合「加法优先」，可独立于前端发包先上 prod。

`kind` 白名单（改这里前先问：少了它哪个问题答不了？）：

```python
OBJECT_KINDS = ("content_wrong", "audio_bad", "audio_missing", "other")
APP_KINDS    = ("app_crash", "recognition_bad", "feature_request", "other")
```

**护栏**（`/history/*` 那个零鉴权洞的教训——匿名可写的端点必须有护栏）：

- `@limiter.limit("60/hour")`——复用 `app/core/rate_limit.py` 现成的 slowapi，零新代码。
  ⚠️ 不用 `5/hour`（guest_login 那个值）：**博物馆共享 WiFi 是真实场景**
  （见 `app_event.py` 里 guest_created 的注释），同一出口 IP 下多人反馈完全正常，
  收太紧会误伤真实用户。这个端点写坏了最坏后果是垃圾行（SQL 能批量清），
  不是账号/资金风险，与 `guest_login` 那类资源型端点的风险画像不同，可以更松。
  ```
  # ponytail: 只按 IP 限流。按 device_id 的日配额是升级路径，等真被刷了再加。
  ```

  ⚠️ 按 IP 限流曾经**根本没有按真实用户生效**（全站共享一个桶）——写这个 spec 时
  顺带挖出来的，已由 PR #577 修好（详见下方「前置依赖」）。本端点的限流值建立在
  那个修复之上才有意义。
- `text` ≤ 1000 字符（Pydantic `max_length`），`kind` 白名单校验，
  `scope="object"` 时 `qid`/`museum_slug`/`language` 必填 → 否则 422。
  一条不知道指向哪件藏品的"内容反馈"是垃圾数据，宁可拒收。
- 匿名可写（无需登录）。

## ✅ 前置依赖：IP 限流在 prod 从未按真实用户生效（已修，#577）

复核这个 spec 的限流值时挖出来的，**不属于本功能，但本功能的护栏依赖它**。
已实测确认，不是推测：

```
nginx（宿主机） --proxy_pass--> 127.0.0.1:8100 --docker-proxy--> 容器:8000
```

- `deployment/production/docker-compose.yml:54` 映射 `127.0.0.1:8100:8000`，
  `:57` 的 uvicorn 命令**没有** `--forwarded-allow-ips`。
- uvicorn 的 `--proxy-headers` 默认开，但 `--forwarded-allow-ips` 默认只信 `127.0.0.1`。
  容器看到的对端是 docker 网桥网关，**不在白名单** → `X-Forwarded-For` 被丢弃。
- nginx 那边 `proxy_set_header X-Real-IP / X-Forwarded-For` 都设了
  （`nginx-api.gomuseum.app.conf:13-14`），**转发头一直在发，只是没人信**。

**实测**（prod 容器 access log 全量，19997 条请求）：出现过的客户端 IP 只有两个
——`127.0.0.1`（容器内健康检查）和 `172.22.0.1`（**全部**外部流量）。
零个真实访客 IP。`get_remote_address()` 对所有用户返回同一个值。

**后果：所有按 IP 限流的端点，全站共享一个桶。**

| 端点 | 限流值 | 全站共享后的实际含义 |
|---|---|---|
| `guest_login` | 5/hour | **全站每小时只有 5 个新游客能进 App** |
| `register` | 5/min | 全站每分钟 5 次注册 |
| `login` | 10/min | 全站每分钟 10 次登录 |
| 密码重置申请 / verify-email | 5/hour | 全站每小时 5 次 |

`guest_login` 那条是发版阻塞级的：新用户装完 App 第一件事就是游客登录。

**为什么至今没炸**：零真实用户。这个缺陷会**正好在 Play 放量时显现**——与
[[monetization-plan]] 里那批"只有真机真购买能发现"的缺陷同类：测试环境
（`TestClient` 进程内直连、不经 nginx）行为完全正常。

**✅ 已修复：PR #577（`hotfix/trust-proxy-headers`），已合入 staging。**

⛔ **本节最初写的修法是错的，留在这里当反面教材**：我本来写的是
「compose 的 uvicorn 命令加 `--forwarded-allow-ips="*"`，容器只绑 127.0.0.1
所以 `*` 安全」。**那会制造一个比缺陷本身更糟的洞。**实现时去读 uvicorn 0.37
源码才发现：

```python
# uvicorn/middleware/proxy_headers.py::_TrustedHosts.get_trusted_client_host
if self.always_trust:
    return x_forwarded_for_hosts[0]     # ← "*" 取最左端
```

而 nginx 用的是 `$proxy_add_x_forwarded_for`（**追加**语义）：访客自带的 XFF 会被
保留，nginx 把真实 `remote_addr` 追加在**右边**。攻击者发 `X-Forwarded-For: 1.2.3.4`，
后端收到 `1.2.3.4, <真实IP>`，`"*"` 取 `[0]` 就是伪造值 → 每个请求换个假 IP
即可无限刷 `register`/`guest_login`。原来的「全站一个桶」至少还挡得住暴力刷，
改成 `*` 反而全开。

**正确修法**：指定可信网段，走 `for host in reversed(...)` 那条分支——从右往左取
第一个不可信的 host = nginx 记下的真实 IP，左边伪造的那段被忽略。

```python
# app/main.py
TRUSTED_PROXY_HOSTS = ["127.0.0.1", "172.16.0.0/12"]
app.add_middleware(ProxyHeadersMiddleware, trusted_hosts=TRUSTED_PROXY_HOSTS)
```

**改在 `app/main.py` 而不是 compose**：`deploy.yml` 只 rsync `backend/`，
compose 文件在 VPS 的 `/opt/gomuseum/{deploy,staging}` 里、**不由 CI 更新**
（实测两处都是旧命令）。改仓库里那份 compose 不会生效。

> 🔑 教训：**「容器不对外，所以信任谁都安全」这个推理漏了一层**——不对外只保证
> 请求都经过 nginx，不保证请求**内容**可信；XFF 的左段本来就是访客自己写的。
> 安全判断不能停在"谁能连上我"，还要看"这个字段是谁填的"。

## 数据模型

```python
# alembic: a2x3_add_feedbacks.py   (承 z1w2，字母序回到 a、cycle 进位到 2)
class Feedback(Base):
    __tablename__ = "feedbacks"
    id           = Column(UUID, primary_key=True, default=uuid.uuid4)
    created_at   = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    user_id      = Column(String(255), nullable=True, index=True)
    device_id    = Column(String(255), nullable=True, index=True)
    scope        = Column(String(16), nullable=False, index=True)   # object | app
    museum_slug  = Column(String(64), nullable=True, index=True)
    qid          = Column(String(32), nullable=True, index=True)
    language     = Column(String(8), nullable=True, index=True)
    kind         = Column(String(32), nullable=False, index=True)
    text         = Column(Text, nullable=True)
    app_version  = Column(String(32), nullable=True)
    platform     = Column(String(16), nullable=True)
    status       = Column(String(16), nullable=False, default="new")  # new|triaged|done
```

**不塞进 `app_events`**：那张表是纯分析窄表（一行一事件、JSONB props、
`log_event` 异常全吞）。反馈有自由文本和**处理状态**，混进去会把分析数据搞脏，
而且 `log_event` 的「失败静默吞掉」纪律对反馈是错的——用户点了提交却没存下来，
必须让他知道。

**匿名单向**：不收集联系方式、不回信。零 PII，不触发
「加身份维度必连带三件事（政策披露/删号断链/导出包含）」那条铁律。
`user_id` 是已登录时后端自动带的，删号断链已由现有机制覆盖（该表 `user_id` 可空）。

> ⚠️ 自由文本框用户可能自己填进邮箱/手机号。**隐私政策要补一句披露**
> （Play 发版清单里政策文档还没上线，正好一起）。

## 前端

### A. 删掉假星标（先决项）

`guide_page.dart:110` 的 `bool _starred = false` 是**页面局部状态**：只有
`setState`，没有持久化、没有后端、没有任何地方读它。用户点了以为收藏了，
退出页面就没了——**这比没有更糟**。

与刚修的「自动保存照片」（#576）是同一个模式：页面局部状态假装成功能。

**而且不止这一处——这是第三例。** 复核时挖出 `history_page.dart:28` 还有一份
**完全独立**的同款：`final Set<String> _starred = {}`，足迹列表里逐条的星标
（`:176` 读、`:217` 切换），同样只有 `setState`、无持久化、无后端。
这一份比顶栏那个更糟：列表里逐条打星，用户会当"标记我喜欢的作品"用，
攒了一路退出就全没了。

删除范围（两个文件）：

- `guide_page.dart`：`_starred` 字段（`:110`）、A5 路径传参与回调（`:327`/`:332`）、
  legacy 顶栏两处（`:434`/`:437`）、`_A5HeroSliverAppBar` 的 `starred`
  与 `onToggleStar` 两个构造参数（`:782`/`:784`/`:796`/`:820`/`:825`）
- `history_page.dart`：`_starred` 字段（`:28`）、`:176` 的读、`:210-224` 整个
  星标 `GestureDetector`

`GmIcons.star` 枚举保留（图标集是设计稿移植，不动）。
**现有测试零引用**（`test/` 全文搜 `star` 无命中），删除不会让任何测试变红。

收藏是独立功能，且「足迹」tab 已经在回答"我看过什么"。真要做该单独规划。

### B. 讲解页顶栏入口

```
_A5HeroSliverAppBar.actions: [ ⚑ 内容反馈 ]     ← 本次新增，替掉 star 的位置
                             [ ↗ 分享 ]        ← 以后，位置留着，本次不做
```

**只加在 A5 页。`_buildLegacyPage` 不加**——那是 `qid`/`slug` 缺失时的兜底路径，
没有坐标可上报。

新图标 `GmIcons.flag`：`gm_icon.dart` 加一条 enum + 一条 SVG path
（24×24 viewBox、1.6pt 圆头描边，与图标集其余一致）。图标集里没有现成的"反馈"
语义——`mail` 会被读成"联系客服"，旗标才是全行业通用的"报告问题"。

### C. 设置页入口（净增 0 条）

`03 支持与法律` 组现状：

```
♡  鼓励我们    → _comingSoon(appStoreRating)   ← 死的占位
🛡  隐私政策
```

`encourageUs` 想做的正是"跳商店评价"，而它做不成：`settings_page.dart:26` 有硬禁令
不许引 `url_launcher`（#434 教训——CI 与出包机解析出不同插件树，只有真机能发现），
`in_app_review` 同样是新原生插件。**所以"去 Play 评价"这条路在 App 内根本没通。**

**为什么不直接复用已有的剪贴板邮箱范式？** 项目已有 `kSupportEmail`
（`benefits_page.dart:48`，复制邮箱到剪贴板，零依赖）——比建表建端点省得多，
必须正面回答。答案是**它解决不了主要问题**：

- 它在权益页，是**支付专用的逃生口**（票面不显示对方邮箱，用户不知道该登哪个账号），
  不是通用反馈渠道。设置页没有任何反馈入口。
- 用户要切到邮件 App、粘贴、自己组织正文——转化率极低。
- 致命的是**拿不到坐标**：qid / language / app_version 全靠用户手写，而他不会写，
  也写不对（他不知道 qid 是什么，更不知道自己在读的是 `zh-hant` 还是 `zh`）。
  而坐标正是藏品级反馈的全部价值。

所以藏品级必须是站内表单。表单既然要建，App 级复用它就是零边际成本——
反过来说，如果只做 App 级，剪贴板邮箱确实够用。

改成：

```
⚑  意见反馈    → showFeedbackSheet(scope: app)
🛡  隐私政策
```

条目数不变，一条死的变活的。等以后真能跳商店了（发版后 `in_app_review` 值不值得引
再单议），"鼓励我们"可以加回来——那时它才有东西可跳。

### D. 反馈面板（一个 widget，两处复用）

```
内容反馈                                    ×
──────────────────────────────────────
 [内容有误]  [读音奇怪]  [没有语音]  [其他]

 ┌──────────────────────────────────┐
 │ 补充说明（选填）                   │
 └──────────────────────────────────┘

                            [ 提 交 ]
```

提交后 sheet 关闭 + 一句 toast「已收到，谢谢」。失败给可重试的提示（**不静默吞**）。

**提交态不是 try/catch 能应付的**，要有 idle / submitting / failed 三态：
`submitting` 时按钮禁用（防双击产生重复行，见下）、`failed` 时 sheet **不关闭**
且保留用户已填的文本。照 `paywall_sheet.dart` 的 `PaywallSheetContent` 抄这套模式。

**草稿状态用 `StatefulWidget` 局部持有，不要用共享 Riverpod provider**——
两个入口（藏品页 / 设置页）共用同一个 provider 而忘了按场景重置的话，
在藏品页写一半关掉、再从设置页打开，上次的 kind/text 会漏进来。
sheet 关闭即销毁局部状态，这个坑从根上不存在。

**不需要新出设计稿。**所需原子全部已在代码库，照现有范式套：

| 要素 | 现成的在哪 |
|---|---|
| 底部 sheet | `guide_deep_sheet.dart` / `paywall_sheet.dart` |
| 内容抽成独立 widget 便于单测 | 同上两处的既定做法（`paywall_sheet.dart:156` 注释） |
| 单选 chip | `explore_page.dart:237` `_cityChips` |
| 文本输入框 | `login_page` / `explore_page` 搜索框 |
| 设置页条目 | `settings_page.dart:316` `_row()` |
| 配色/字体 | `GmPalette` token / `GmText` |

唯一需要新画的是 `GmIcons.flag` 的 path。

`scope: app` 时同一个 widget，chips 换成 App 级四项，不带 qid/language。

**l10n**：10 语 × 14 key = 面板标题 ×2（内容反馈 / 意见反馈）、chips ×8、
提交按钮、提交成功、提交失败、文本框占位符。

**发请求的那一层**：项目里有两套范式——完整 Clean Architecture
（datasource 接口 + Impl + repository 返 `Either`，见 `features/payment/data/`）
和轻量版（单个类里直接 `_dio.post`，见 `auth_repository.dart`）。
反馈只有一个 POST、没有 domain 逻辑、不需要 usecase，**照轻量版写**：
一个 `FeedbackRepository`（`_dio.post` + 把 `DioException` 翻成 bool/异常），
sheet 里调它。不建 datasource/entity/usecase 三层——那是为复杂领域准备的。

> `app_version` 复用 `kVersionFootnote`（`settings_page.dart:34`）。它是**手工维护的
> 硬编码常量**（`package_info_plus` 同样被禁），但**不会静默过期**——发版时忘了改
> 会被现有的 `settings_version_test` 拦下。所以反馈复用它不引入新的失效点。
>
> ⚠️ 它的实际值是 `'GoMuseum 1.0.0 (31)'`，**带 `GoMuseum ` 前缀**。上面契约示例里的
> `"1.0.0 (31)"` 是错的——直接整串送出，契约示例改成 `"GoMuseum 1.0.0 (31)"`，
> 零字符串处理。`feedback_report.py` 只拿它当字符串分组，前缀无害。

## 测试

**后端**（正负成对，`kind`/必填项两侧都要）：

- 匿名可写 → 204，行落库，字段齐
- `scope=object` 缺 `qid` → 422（**负样本：不能收垃圾数据**）
- `scope=object` 缺 `language` → 422
- 未知 `kind` → 422
- `text` 超 1000 → 422
- `scope=app` 不带 qid → 204（正样本，证明上面两条不是一刀切）
- 已登录时 `user_id` 落库；游客时为空而 `device_id` 有值

**前端**（面板内容 widget 单测，不依赖 `showModalBottomSheet`）：

- 🔴 **`zh-hant` 不被降级成 `zh`**——这是本设计最容易错、且错了最难发现的一点
- `scope=app` 提交的 payload 不含 `qid`
- 未选 chip 时提交按钮禁用
- **提交中按钮禁用**（防双击造重复行，见下方「已知错法 1」）
- 提交失败时 sheet 不关闭、**且保留已填文本**
- **两个入口先后打开互不干扰**：藏品页填一半关掉 → 设置页打开是干净的
  （局部状态实现下这条恒真，但要有测试钉住，防后人改成共享 provider）

**双向破坏验证**（[[petit-palais-batch-generation]] 的教训：测试只能钉住你已想到的
错法）：把实现改坏必须变红（漏传 language → 红），**同时**把实现改成过严
（scope=app 也强制要 qid → 对照组必须红）。两个方向都验，否则"判对了"和
"拆松了"无法区分。

⚠️ 全库搜 `model_validator` / `root_validator` **零命中**——"按 scope 做条件必填校验"
在这个代码库里没有现成模式可抄，是本次新引入的写法。上面那组正负样本因此格外要认真，
不能想当然套用别处代码。

## 已知错法（复核挖出来的，测试清单已据此扩充）

**1. 双击提交 / 超时重试 → 重复行污染「按命中数排序」。**
这个机制是本设计的核心（第三个人报同一件事就浮上来），而重复提交会直接喂给它假热度。
前端「提交中禁用」挡得住双击，但挡不住"请求其实已到达、客户端超时、用户点重试"。
**修法放在读侧而不是写侧**：`feedback_report.py` 聚合时数 **不同 `device_id` 的个数**，
不是数行数。比加幂等键省，而且更正确——排序要的本来就是"多少人报过"。

**2. `language` 坐标对 facts 面板字段不是可信定位。**
用户在 `zh-hant` 页面看到作者名显示成英文，那是 `museum_repo.py:600-621` `_resolve_name`
的正常回退（缺 zh-hant 时回退英文）。他点「内容有误」，`language=zh-hant` 会被忠实记下，
但真正缺的是 `artist.name_i18n` 的 zh-hant 支，**不在 `object_content_sections` 那一行里**。
坐标"对得上语言"不等于"对得上出错的表"。
不在 UI 上解决（让用户区分是哪张表 = 又回到"让用户懂技术分层"）。
写进 `feedback_report.py` 的注释：`content_wrong` 类反馈要先看一眼是不是名字回退，
别直接去改 section 正文。

## 读反馈（不建后台）

`scripts/feedback_report.py`——按 `(qid, language, kind)` 聚合，
**计数数的是不同 `device_id` 的个数，不是行数**（见「已知错法 1」）；
`scope=app` 的按 `(kind, app_version)` 聚合。第三个人报同一件事时它自己浮上来。

并进 `ops_report.py` 还是独立脚本，实施时看哪个改动小。

## 上线顺序

1. **后端先行**（纯加法、`deploy.yml` 只认 `backend/**`，会自动 CD）。
   老 App 不认识这个端点，零影响。
2. **前端跟下一个包**——正好卡在「前端发包等一会合并另几个修改后再发」的约束上。
3. **隐私政策补自由文本披露**，与 Play 发版清单里的法律文档一起上线。

## 不做（YAGNI）

- **不建管理后台**。SQL + 脚本，与 `app_events` 同惯例。
- **不回信、不收邮箱**。见「匿名单向」。
- **不做行为型隐式反馈**（音频 3 秒内关掉、反复重新识别）。成本高于收益，
  且零真实用户阶段拿不到信号。`recognition_demands` 已经在覆盖"识别不中"那一类。
- **不做截图上传**。存储 + 审核成本，等有真实反馈量再说。
- **不做分享**。顶栏留位，单独讨论。
- **不做投票/点赞**（"这条讲解有用吗 👍👎"）。那是内容质量**度量**，与错漏**上报**
  是两件事，混在一起两边都做不好。

## 契约回写（实现完成后）

按 [[contract-governance]] 判断：`POST /api/v1/feedback` 是新 API 面
→ **进 `museum-api-contract.md`**。
「反馈是内容质量的兜底环」这条原则已在 CLAUDE.md 的 AI 内容质量原则里，
补一句指向本端点即可。面板 UI 行为、chips 文案属实现细节，**不进契约**。
