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
  "app_version": "1.0.0 (31)",
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

- `@limiter.limit("30/hour")`——复用 `app/core/rate_limit.py` 现成的 slowapi，零新代码。
  ⚠️ 不用 `5/hour`（guest_login 那个值）：**博物馆共享 WiFi 是真实场景**
  （见 `app_event.py` 里 guest_created 的注释），同一出口 IP 下多人反馈完全正常，
  收太紧会误伤真实用户。
  ```
  # ponytail: 只按 IP 限流。按 device_id 的日配额是升级路径，等真被刷了再加。
  ```
- `text` ≤ 1000 字符（Pydantic `max_length`），`kind` 白名单校验，
  `scope="object"` 时 `qid`/`museum_slug`/`language` 必填 → 否则 422。
  一条不知道指向哪件藏品的"内容反馈"是垃圾数据，宁可拒收。
- 匿名可写（无需登录）。

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

与刚修的「自动保存照片」（#576）是同一个模式：页面局部 bool 假装成功能。
两周内第二例。

删除范围：`_starred` 字段、`onToggleStar` 回调、`_A5HeroSliverAppBar.starred`
与 `.onToggleStar` 两个参数、A5 顶栏和 legacy 顶栏（`:434`）两处 star icon。
`GmIcons.star` 枚举保留（图标集是设计稿移植，不动）。

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

> `app_version` 复用 `kVersionFootnote`（`settings_page.dart:34`）。它是**手工维护的
> 硬编码常量**（`package_info_plus` 同样被禁），但**不会静默过期**——发版时忘了改
> 会被现有的 `settings_version_test` 拦下。所以反馈复用它不引入新的失效点。

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
- 提交失败时 sheet 不关闭、给出可重试提示

**双向破坏验证**（[[petit-palais-batch-generation]] 的教训：测试只能钉住你已想到的
错法）：把实现改坏必须变红（漏传 language → 红），**同时**把实现改成过严
（scope=app 也强制要 qid → 对照组必须红）。两个方向都验，否则"判对了"和
"拆松了"无法区分。

## 读反馈（不建后台）

`scripts/feedback_report.py`——按 `(qid, language, kind)` 聚合计数排序，
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
