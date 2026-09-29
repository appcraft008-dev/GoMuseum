# 分享与公开网页层设计（分享图 + 文字网页 + App Links）

> 2026-09-20 brainstorm 初稿（冻结）→ **2026-09-29 解冻，按本版实现**。
> 初稿的完整推理与复核记录见本文件的 git 历史（#600 版本）；本版只保留仍成立的结论，
> 并写入 2026-09-29 与用户确认的决定。
> 与 [[monetization-plan]]（付费墙）、[[audio-guide-positioning-and-paywall]]（定位）配套。

## 〇、2026-09-29 定案（与初稿的差异）

| 问题 | 初稿 | 定案 |
|---|---|---|
| 做不做、何时做 | 冻结，等推正式轨道之后 | **推正式轨道之前做完前端部分**（用户：推正式后尽量少发前端） |
| 音频 | 待决策（试听片段 / 签名 URL） | **完全不给。音频是收费核心资产**（用户定）。页面只写一句「这件有语音讲解，在 App 里听」 |
| 分享形态 | 只发链接，靠 OG 卡片 | **分享图 + 链接**（用户定）。微信里链接不出卡片，图片是唯一好看的形态 |
| App Links | 与下载入口分开做（未排期） | **放进这一版**：已装用户点链接 → 自动打开 App 并直接进那件藏品的讲解页（用户定） |
| 域名 | — | 用现有 `gomuseum.app`，不申请新域名 |

初稿里「签名 URL」那条硬约束随音频一起作废：它其实隐含一个没写出来的前置工程
（音频目前在**公开桶**，靠不可推测 key 防护，见 `content_repo.py:audio_key` 的注释；
要签名就得先迁私有桶）。不给音频，这整条链都不需要了。

## 一、为什么这么做（保值的结论）

1. **落地在网页，不在商店。** 朋友点开商店 → 装 → 注册 → 才看到内容，四步漏斗且朋友多半不在巴黎。
   落在能立刻读的网页上，愿意装的才是真要去的人。
2. **现在是获客渠道，不是病毒循环。** 零真实用户 × 任何 K 因子 = 0。上线后分享数据恒为 0 **不是失败信号**（见 §八）。
3. **SEO 只是副产品**，不是理由（高量词排不上，长尾词没人搜；详见 git 历史）。本版不做 sitemap 提交。
4. **必须服务端出 HTML。** 与 SEO 无关：WhatsApp/Telegram/Messenger 抓预览卡片**不执行 JS**，客户端渲染拿不到卡片。
   FastAPI 出 HTML（Jinja 模板），不做预渲染（内容一直在变）。

## 二、什么写死在 App 里、什么在服务器上

**这是本版设计的主轴。** 推正式后少发前端 ⇒ App 里只放「没法放服务器」的东西，其余全部 server-driven。

| 写死在 App（推正式前一次做对） | 服务器（随时改，不发版） |
|---|---|
| 讲解页的分享按钮（位置 + 按 `share` 字段显隐） | 分享什么：链接、分享文字、分享图 —— 全由 `share` 字段下发 |
| 调系统分享面板（`share_plus`）发「图 + 文字」 | 分享图的版式和文案 |
| App Links：intent-filter + `/a/:slug/:qid` 路由 | 网页内容、OG 卡片、下载按钮、按聊天工具区分的引导 |
| 登录守卫对深链接的保留（§五） | 哪些件可分享（`share` 为 null 就不显示按钮） |

🔑 **链接格式也不写死在 App 里**：App 分享的是服务器给的 `share.url`。
但**已经发出去的链接会永久留在别人的聊天记录里** —— `/a/{slug}/{qid}` 这个路径一旦上线就只能兼容、不能改。

## 三、契约：内容接口加 `share` 字段（加法）

`GET /museums/{slug}/objects/{qid}/content?language=xx` 响应新增：

```json
"share": {
  "url": "https://gomuseum.app/a/louvre/Q123?lang=zh&s=app",
  "text": "《门闩》— 弗拉戈纳尔",
  "image_url": "https://gomuseum.app/a/louvre/Q123/card.png?lang=zh"
}
```

或 `"share": null`。**null 的条件**（任一成立）：

- 该件在**请求语言**下没有已发布的 guide 正文（按语言判，不按对象级 `content_status` —— 对象 ready 不代表这个语言有正文，见 `museum_repo.py` 列表的同款处理）
- 所在馆未放出（`museums.published_at IS NULL`）—— **预览账号也是 null**：隐身馆的链接朋友打开是 404
- 该件无作品图（分享图做不出来）

老 App 忽略未知字段，前向兼容。该字段属 API 面 → 回写 `museum-api-contract`。

## 四、公开网页 `GET /a/{slug}/{qid}?lang=xx`

### 4.1 页面

```
┌─────────────────────────┐
│  作品图（large）          │
│  《门闩》                 │
│  弗拉戈纳尔 · 1777         │
│  🎧 这件有语音讲解，在 App 里听 │ ← 仅当 guide 有音频时显示;一句话,无播放键
├─────────────────────────┤
│  guide 正文 / 深度模块（平铺）│
│  常见问题 / 作者卡          │
├─────────────────────────┤
│  图片与内容来源声明（images.credit）│
└─────────────────────────┘
[粘底条] 在博物馆现场，拍一张就能认出它
```

粘底条按访客分（服务端判 UA，改它不发版）：

| 访客 | 粘底条 |
|---|---|
| **推正式轨道之前（所有人）** | 只有这句话，**不带链接**（内测轨道的 Play 链接对外人是「找不到该应用」） |
| 推正式后 · Android | 点击 → Play，带 referrer（`utm_source=gomuseum.app&utm_medium=share`，沿用落地页 #637 的约定） |
| 推正式后 · iPhone | 诚实提示：目前只有 Android 版 |
| 微信内置浏览器（UA 含 `MicroMessenger`） | 只有这句话，**不做按钮**（国内打不开 Play，多数国产安卓无 Play） |

「推正式了没有」是服务端一个配置开关，推正式那天改配置即可。

### 4.2 OG 卡片

`og:image` = 作品图（中号，压到 WhatsApp 能接受的大小 —— 实测确定），`og:title` =《作品》— 作者，
`og:description` = guide 正文前 ~100 字。**不放 logo、不出现「下载」**：卡片要像一件艺术品，不像广告。

### 4.3 语言

- `?lang=` 有正文 → 按该语言渲染；页面上可切换，**只列有正文的语言**（hreflang 同）
- `?lang=` 没正文 → 302 到该件有正文的语言（优先 en）；一个语言都没有 → 404
- 缺省 `lang` → 按 `Accept-Language` 选有正文的语言，再回落 en

### 4.4 🔴 硬约束

1. **不点燃任何生成。** 路由**直接查 repo 层**，不调内容接口、**绝不配服务账号令牌**
   （懒生成闸按「有无身份」判，带令牌 = 把 2026-09-20 关掉的敞口原样打开）。
2. **不出现任何音频。** HTML 里不许有音频存储域名、`audio_key`、音频接口地址 —— 守卫测试钉住。
3. **可见性闸**：复用 `museum_visible(db, slug, preview=False)` + `qid_visible(...)`，
   隐身馆 / 未知 qid / 无正文 → 同一个静态 404 + `noindex`（不泄漏差异）。
4. **不放出「待完善」页。** 无已发布 guide 正文 = 404（原则：分享空页 = 负向拉新；规模化空页 = 站点降权）。

## 五、分享图 `GET /a/{slug}/{qid}/card.png?lang=xx`

```
┌────────────────────┐
│    [作品图]         │
│ 《门闩》             │
│ 弗拉戈纳尔 · 1777    │
│ "这幅小画在…"（一句）  │
│ ─────────────────  │
│ 卢浮宫 · GoMuseum    │
│ 图片:© …（credit）   │ ← 有 credit 就必须印上
└────────────────────┘
```

- 服务端用 Pillow 合成（依赖已在 `pyproject.toml`）。可见性 / 语言 / 404 规则与网页**完全一致**（同一个判定函数）。
- ⚠️ **字体**：后端镜像目前**没有任何字体**，而标题有中日韩文。需在镜像里放 CJK 字体
  （Noto Sans CJK 子集或 `fonts-noto-cjk`），并加测试：渲染中文标题不出方框（检查字形覆盖）。
- 缓存：`Cache-Control` 长缓存 + 按 `(qid, lang, 模板版本)` 做 ETag。
  `# ponytail: 每次请求现场合成;可分享集合有上限(有正文件数 × 语言),CPU 成问题再落 R2`
- 为什么不在 App 里画：版式写进 App 就改不了了（§二）。

## 六、App 端（本版唯一要发包的部分）

1. **分享按钮**：讲解页右上角，`share != null` 才显示。点击 → 下载 `share.image_url` 到临时目录 →
   `share_plus` 发「图片 + `share.text` + 换行 + `share.url`」。
   - 下载失败 → 退化为只发文字 + 链接（不报错打断用户）。
   - 微信会丢掉附带的文字、只收图 —— 已知且接受。
2. **App Links**
   - `AndroidManifest`：`https://gomuseum.app/a/*` 的 `intent-filter android:autoVerify="true"`。
     **只加在 prod flavor**（staging 包名不同，验证不过；staging 用 `adb shell am start -d` 手测）。
   - 服务器：`gomuseum.app/.well-known/assetlinks.json`，填 **Play 应用签名密钥**的 SHA-256
     （Play Console →「应用完整性」，⚠️ 不是上传密钥）+ 上传密钥的 SHA-256（本地装的包也能验）。**需用户从 Console 复制。**
   - go_router 新增 `/a/:slug/:qid` → `GuidePage(GuideArgs(slug:, qid:))`（该构造已被搜索/足迹使用）。
     App 用**用户自己的 App 语言**，忽略链接里的 `lang`。
   - 隐身馆 / 不存在的 qid → 讲解页现有的「找不到」状态，不崩。
3. **🔴 登录守卫必须保留深链接目标。** 现状 `authRedirect`：冷启动时登录态还在 loading → user 为 null →
   弹到 `/login` → 加载完已登录 → 弹回 `/`。**深链接会在这一来一回里丢掉**，用户点了链接却落在首页。
   （同一机制 2026-09-05 就坑过一次游客冷启动，见 `app_router.dart` 注释。）
   修法：被守卫弹走时把原目标带上（`/login?from=/a/...`），弹回时回到原目标而不是 `/`；
   真未登录的人登录/游客进入后同样回到原目标。`auth_guard_test` 补这几条分支。

## 七、nginx（用户手动，CD 带不过去）

`gomuseum.app` 的 server 块（宿主机 `/etc/nginx/sites-available/gomuseum.app`，仓库无模板）：

- `/a/` → 反代到 prod 后端 :8100
- `/.well-known/assetlinks.json` → 静态文件（放 `deployment/website/.well-known/`）
- **`limit_req`**：这个 server 块目前 **0 行限流**（2026-09-21 实测），`/a/` 上去之前必须配上。
  原则 3 关的是「点火」，限流挡的是「量」（DB 查询、R2 出网、合成图片 CPU），两件事。
- 改完 `nginx -t && systemctl reload nginx`。

staging 验证不依赖这一步：staging 后端直接在 `staging-api.gomuseum.app/a/...` 上出页面，
分享链接的域名取自配置 `PUBLIC_WEB_BASE_URL`（prod = `https://gomuseum.app`，staging = staging-api 域名）。

## 八、怎么知道有没有用

- 虚荣指标不作判据：PV、分享次数、下载量。唯一算数的是**经这条路进来、最终完成一次识别的人**。
- 埋点（服务端 `log_event`，不发版可调）：分享图被取（≈ 分享次数）、网页被看（带 `s=app` 来源）、粘底条点击。
- 装回来那一截（点下载 → 装 → 用）第一版接不上，只能看 Play Console 的 `utm_medium=share` 安装数。
- **≥100 真实活跃用户之前别看分享数据**：会把"没有用户"误读成"分享没用"（[[proxy-metric-is-not-the-thing-you-ship]]）。

## 九、第一版不做

| 不做 | 原因 |
|---|---|
| 音频（任何形式） | 收费核心资产（用户定） |
| sitemap / SEO 实验 | SEO 已降级为副产品 |
| 桌面二维码 | 分享链接 99% 在手机上打开；SEO 不做则桌面访客很少 |
| 足迹分享 | 零用户零足迹，且涉及隐私 |
| Install Referrer 回流（装完直接打开那件） | 实现重，二期；App Links 已覆盖「已装用户」那一半 |
| 微信卡片（开放平台 SDK） | 需注册微信开放平台应用，对我们不现实 |

## 十、上线顺序（硬约束）

1. 后端（`share` 字段 + 网页 + 分享图 + assetlinks）合 staging → staging 实测
2. **后端上 prod + 用户配好 nginx**（`/a/` 反代、assetlinks、限流）→ `gomuseum.app/a/...` 外网可打开
3. 才发带分享按钮的 App 包（否则分享出去的链接是 404）→ 真机验：WhatsApp 卡片、微信收图、App Links 直达、冷启动深链接
4. 推正式轨道那天：改服务端开关，粘底条换成 Play 下载按钮（不发版）

## 已确认的现有基础设施（2026-09-29 核对代码）

| 需要的东西 | 现状 |
|---|---|
| 内容读取 | ✅ repo 层 `get_object_content`；接口对匿名不点火（2026-09-20 审计） |
| 可见性闸 | ✅ `app/services/visibility.py`：`museum_visible` / `qid_visible`（#679） |
| 音频 | 公开桶 + 不可推测 key；**网页层完全不碰** |
| 作品图 | ✅ `object_images` + `_sized(..., "large")`，含 `credit` |
| Pillow | ✅ 已在依赖；❌ **镜像无字体**，要加 CJK |
| 讲解页按 slug+qid 打开 | ✅ `GuideArgs(slug:, qid:)`（搜索、足迹已在用）；❌ 无 URL 路由，要加 `/a/:slug/:qid` |
| 登录守卫 | ⚠️ 冷启动会丢深链接目标，要改（§六.3） |
| `share_plus` | ❌ 未引入 |
| App Links | ❌ Manifest 无 intent-filter；❌ 无 prod flavor 专属 manifest 目录，要建 `src/prod/` |
| `assetlinks.json` | ❌ 要建；SHA-256 需用户从 Play Console 提供 |
| `gomuseum.app` nginx | ⚠️ 仓库无模板、0 行限流，用户手动配 |
| 可分享件数 | ⏳ 初稿记 665 件有正文（2026-09-20），实现时按「语言 × 已发布 guide」重查 prod |
