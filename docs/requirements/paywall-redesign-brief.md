# 付费墙重做设计需求（GoMuseum）

写给设计侧的交接文档。目标：重做付费相关的全部界面。
现状代码见 `frontend/gomuseum_app/lib/features/payment/`。

---

## 一、先说清楚"丑"在哪 —— 根因不是配色

现在有**两套并存的设计语言**，用户在一次购买里会连续撞见两次风格切换：

| 界面 | 文件 | 用的什么 |
|---|---|---|
| 付费墙底部弹层 | `paywall_sheet.dart` | ✅ 暖纸手册设计系统（`GmPalette` / `GmText` / `GmTicketButton`） |
| 权益页（点"获取通票"之后落地） | `benefits_page.dart` | ❌ 裸 Material：`Card(elevation: 2)`、`Colors.grey[600]`、`Colors.orange[50]`、圆角 12、系统 `CircularProgressIndicator` |
| 权益状态卡 | `benefits_status_widget.dart` | ❌ 同上 |
| 商品卡 | `ProductCard` | ❌ 同上 |

暖纸手册是**低饱和暖纸底 + 衬线标题 + 直角/4px 小圆角 + 门票隐喻**；权益页是 Material Design 默认外观。用户点完那个精致的门票按钮，落到一个 Google 风格的商品列表页 —— **这个断裂是"丑"的主要来源**，不是某个颜色不好看。

**所以重做范围必须包含权益页，只重做那个弹层等于没做。**

---

## 二、这是什么产品（设计前必须理解）

- **巴黎 7 日通票**，一次性购买，不是订阅。价格 €7.99 档（各地区本地化，从 Google Play 拿）。
- 覆盖卢浮宫、奥赛、橘园、小皇宫四馆。
- **旅游产品**：用户常常出发前几天就买好。
- **付费墙建在"现场体验"，不建在"内容"**：
  - 永远免费 → 浏览、搜索、**完整文字讲解**、接地预设问答
  - 需要通票 → 拍照识别（免费 5 次后）、语音讲解（免费试听 1 件后）

这条边界是产品的核心主张，设计上要让用户明确感到"我不是被锁在内容外面"，而不是常见的"免费版残废"。

### ⭐ 最重要的差异化承诺

**买了不马上开始计时。** 用户首次使用高级功能并**显式确认**后，7×24 小时才开始跑。

这是为旅游场景做的（提前买、到馆再开），也是与所有"买完立刻倒计时"的竞品最不一样的一点。现在这句话被塞在弹层里一个 12.5px 的灰色小圆点条目里，**分量严重不足**。设计上它应该是这张"票"的核心卖点之一。

---

## 三、必须设计的全部状态

不是一个界面，是一组。**漏掉任何一个状态，线上就会出现没设计过的界面。**

### A. 触发层（三档强度，避免反复打扰）

| 触发 | 现在是什么 | 需要什么 |
|---|---|---|
| 第 2 件作品点语音 | 系统 SnackBar + 一个文字按钮 | 轻碰一下，不打断现场体验。用户正站在画前面 |
| 同一件再点 / 点"了解" | 完整付费弹层 | ↓ |
| 免费识别 5 次用尽 | 完整付费弹层（强节点） | ↓ |

轻提示那一档现在是**纯系统 SnackBar**，完全在设计系统之外。

### B. 完整付费页（核心）

必须容纳：

1. 标题「巴黎 7 日通票」
2. 卖点：不限次拍照识别 + 四馆全部语音讲解
3. ⭐ **不立即计时**的承诺
4. **浏览/搜索/文字讲解始终免费**的声明
5. **价格** —— ⚠️ **现在这个弹层里根本没有价格**，用户是在不知道多少钱的情况下点"获取通票"的。必须补上，也是 Google Play 的合规要求
6. 主 CTA
7. 「恢复购买」次要入口

**未登录变体**：CTA 变成「登录后购买」，下面一行小字解释"通票绑定账号，换手机也不会丢"。（后端会 403 拦游客购买 —— 游客身份绑设备，买了换手机永久拿不回。）

### C. 激活确认弹窗

用户第一次用高级功能时弹，问「开始你的 7 天通票？」，说明"一旦开始就连续 7×24 小时，中途不暂停，建议到馆后再开始"，两个选项：再等等 / 现在开始。

现在是**系统默认 `AlertDialog`**。这是整个产品体验里**最关键的一次确认**（点错就烧掉整张票），却长得像个报错框。

### D. 权益页（点 CTA 之后落地的页面）

四种状态各要一个样子：

| 状态 | 该看到什么 |
|---|---|
| 未购买 | 商品 + 卖点 → 引导购买 |
| 已购未激活 | 「已购买 · 待激活」+ 说明何时开始计时。**不该再劝购** |
| 通票生效中 | 「通票生效中」+ 到期日 + 识别不限次。**不该再是个商店** |
| 到期后 | 提示已过期 + 可再购买 |

> 已购状态的信息架构刚在 PR #442 补上（此前已付费用户在这一页只看得到「识别次数」和一个商品列表，全程没有一处确认票在手上）。**设计要在此基础上做，不要退回纯商店。**

### E. 边缘状态（现在全是系统默认样式）

- 加载中 → `CircularProgressIndicator`
- 商品拉取失败 → 「暂无可用商品」+ 一个灰色购物袋图标
- 购买失败 / 验证未完成 → 橙色 SnackBar
- 恢复购买进行中 → 「正在恢复购买...」SnackBar
- ⚠️ **恢复购买没有"没找到可恢复购买"的成功空态** —— 消耗型商品被消耗后本来就不返回，用户点了会觉得没反应

---

## 四、硬约束（不能违反，否则设计落不了地）

### 设计令牌已定，不要另起一套

来自 `design_handoff_gomuseum/gm-shared.jsx`，代码里是 `GmPalette`：

```
亮色  bg #F3EDDF  surface #FBF7EC  ink #2C2316  sub #8A7A5F
      faint #B0A283  line #DCD2B8  accent #A14E28  chipBg #EAE2CD
暗色  bg #201A12  surface #2A2218  ink #EFE6D2  sub #A89878
      faint #6E614C  line #3A3022  accent #D08050  chipBg #332A1D
```

**亮暗双主题都要出**。暗色不是把亮色反过来 —— 已有专门的暗色规格（`design_handoff_gomuseum/GoMuseum 暗色规格.html`）。

⚠️ 深色模式下 `ThemeData.primaryColor` 会等于 `colorScheme.surface`，也就是卡片背景色。今天真机上就出过"文字和底色同色、整块看不见"的事故。**任何深色稿都要自己核一遍对比度**。

### 可复用的现成组件

`GmTicketButton`（实底 + 内层虚线框 + 衬线字，门票隐喻）、`GmDiamond`（菱形分隔）、`GmSectionHead`（编号小节头）、`GmText.serif` / `GmText.sans`。

**优先复用**。新组件要说明为什么现有的不够用。

### 十种语言

zh / zh-Hant / en / fr / de / es / it / ja / ko / pl。

- 德语、法语、波兰语的按钮文案会**长很多**（"Get the pass" → "Vorteile ansehen" 级别的膨胀）
- **不能有固定宽度的按钮、不能假设标题只有一行、不能靠字符数做布局**
- 现有 `GmTicketButton` 用 `FittedBox(scaleDown)` 兜底，可以参考
- 价格字符串由 Google Play 按地区返回（`€7.99` / `£7.99` / `¥1,200`），长度和符号位置都不固定

### 版式

- 底部弹层：小屏（iPhone SE 级别）必须能完整看到 CTA，内容超出要能滚
- 需要适配安全区（`SafeArea`）
- Flutter 实现，不用 Web 布局特性

### Google Play 合规

- 购买前必须清楚展示**价格**和**买到什么**
- 不得用倒计时、虚假稀缺、"XX 人刚购买"之类的暗黑模式
- 「恢复购买」必须可达

---

## 五、明确不要做的

- ❌ 倒计时 / 限时折扣 / 虚假紧迫感 —— 违反 Play 政策，也不符合博物馆产品调性
- ❌ 多档价格对比表（目前只有一个商品，做三列对比是无中生有）
- ❌ 订阅话术（这是一次性购买，不是订阅，不要出现"每月""自动续费"）
- ❌ 把免费层描述成"残废版" —— 文字讲解是完整免费的，这是卖点不是限制
- ❌ 全屏强制付费墙 —— 用户正站在展品前，打断现场体验是最糟的时机

---

## 六、交付什么

1. **亮 + 暗**两套
2. 覆盖上面第三节 A–E 的**全部状态**（含边缘状态和空态）
3. 标注间距、字号、字重、颜色取哪个 token
4. 说明用了哪些现有组件、新增了哪些组件及理由
5. 长文案（德语）下的布局表现

---

## 附：现有文案（可改，但语义要保留）

| key | 中文 | 英文 |
|---|---|---|
| `paywallTitle` | 巴黎 7 日通票 | Paris 7-Day Pass |
| `paywallPitch` | 不限次拍照识别，卢浮宫、奥赛、橘园全馆语音讲解。 | Unlimited photo recognition and full audio commentary across the Louvre, Orsay and Orangerie. |
| `paywallClockNote` | 购买后不立即计时——首次使用高级功能并确认后才开始。 | The clock does not start at purchase — it begins when you first use a premium feature and confirm. |
| `paywallFreeAlways` | 浏览、搜索与完整文字讲解始终免费。 | Browsing, search and full written commentary are always free. |
| `paywallBuy` | 获取通票 | Get the pass |
| `paywallLoginToBuy` | 登录后购买 | Sign in to buy |
| `paywallLoginWhy` | 通票绑定账号，换手机也不会丢。 | Your pass is tied to your account, so you keep it on a new phone. |
| `paywallRestore` | 恢复购买 | Restore purchase |
| `audioLockedHint` | 语音讲解需要通票——免费试听名额已用在另一件作品上。 | Audio commentary needs the pass — your free preview has been used. |
| `activateTitle` | 开始你的 7 天通票？ | Start your 7-day pass? |
| `activateBody` | 一旦开始就连续计时 7×24 小时，中途不暂停。建议到馆后再开始。 | Once started it runs for 7×24 hours without pause. Start it when you're at the museum, not before. |
| `activateLater` / `activateConfirm` | 再等等 / 现在开始 | Not yet / Start now |
| `passActive` | 通票生效中 | Pass active |
| `passExpiresOn` | {date} 到期 | Expires {date} |
| `passPendingActivation` | 已购买 · 待激活 | Purchased · not activated |
| `passActivateHint` | 首次播放讲解时开始计时 | Starts when you first play a guide |
