# 匿名成本洞与数据污染面：全量审计与封堵

> 2026-09-20。起因：查证"分享页会被爬虫点燃付费生成"这条警告是否成立时，
> 发现**同一个洞已经在 prod 上开着**，而且不止一个。用户要求"一次给他补齐"。
>
> 审计范围 = `backend/app/api/v1/endpoints/` 全部 11 个模块 × 全部路由，
> 逐个回答两个问题：**谁能调用它？调用它会不会花钱或写库？**

## 零、审计方法（先说清楚，免得下次重做）

不是读一遍端点列表就完事。三步交叉：

1. **从钱那头倒推**：`grep "AsyncOpenAI|chat.completions|audio.speech"` 列出**全部 7 个**
   付费调用点，逐个往上 trace caller 链，直到撞到某个 HTTP 路由或确认是 CLI-only。
2. **从路由那头正推**：`grep "^@router\."` 列出全部路由，逐个看有没有
   `credentials` / `Depends(security)` 参数。
3. **两张表对账**：付费点里"能从无鉴权路由到达"的，就是洞。

单走任何一步都会漏。只看路由会漏掉 `maybe_trigger` 这种**三层之下**才花钱的；
只看付费点会漏掉 `/recognition/recent` 这种不花钱但泄漏数据的。

---

## 一、🔴 P0-1：`POST /api/v1/content/explanation` —— 无鉴权的 LLM + 可覆盖已发布内容

`content.py:118`。**本次审计最严重的发现**，严重度高于最初怀疑的 `object_content`。

```python
@router.post("/explanation", response_model=ExplanationResponse)
async def generate_explanation(
    request: ExplanationRequest, content_service=Depends(get_content_generation_service)
) -> ExplanationResponse:
```

**没有 `credentials` 参数。没有限流。**

### 1.1 花钱：单次请求可放大 ~20 倍

`content_generation_service.py:191,253-260` → gpt-4o-mini，`max_tokens=1500`。
正常一次约 $0.001。但：

```python
if description:
    user_prompt = f"{user_prompt}\n\nBase description: {description}"
```

`description` 是**请求体里攻击者完全控制的自由文本**，直接拼进 prompt，
长度无任何校验。nginx 放行 15MB 请求体（`client_max_body_size 15m`），
撑到 gpt-4o-mini 的 128k 上下文上限 ≈ **$0.019/次**。

配合下面 P1 的"全局零限流"，这是个可以持续跑满的水龙头。

### 1.2 写库：绕过全部质量闸，覆盖已发布内容，并让音频静默变哑

```python
if request.qid and not result.get("fallback"):
    persist_explanation(db, request.qid, request.language, result, model="gpt-4o-mini")
```

`content_repo.py:19-46` 做了什么：

```python
row.body, row.status, row.source = body, "published", "ai_generated"
if existing is not None and existing.body != body:
    row.audio_key = None          # ← 已发布音频在这里被清掉
```

三条后果，一条比一条重：

| | 后果 |
|---|---|
| ① | 写入 `status="published"`，**绕过接地闸 / 忠实度闸 / 语言检测闸** —— 它根本不走富化管线，那些闸挂在 `enrichment/` 里 |
| ② | 命中已有行就**覆盖**（4 个 section + facts），真实已发布的讲解被替换成攻击者指定的 artist/period 生成出来的东西 |
| ③ | body 变了 → `audio_key = None` → **已灌好的音频静默变哑**，而且是 10 个语种里的那一个 |

②③ 合起来 = **匿名任何人可以定点破坏《蒙娜丽莎》的中文讲解并让它的中文音频消失**。
这不是成本问题，是数据完整性问题。
③ 这个机制本身是对的（正文改了旧音频就该失效），坏在**点火开关对全世界敞开**。

### 1.3 前端还在引用它吗？——在，但那条路实际走不到

`content_remote_datasource.dart:52` 确实打这个端点。往上 trace：

```
guide_page.dart:147  if (!widget.args.useA5) { _loadExplanation(); }
guide_page.dart:88   bool get useA5 => slug != null && qid != null;
```

全部 5 个 `GuideArgs(...)` 构造点里，只有 `history_page.dart:282` 那一处不传 slug+qid，
而它自己的注释写着「**老后端不返回 slug/qid 时的兜底**」。prod 后端从 #483 起一直返回。

而且 App 这条路**从不传 `qid`**（`GenerateExplanationParams` 里就没这个字段）——
1.2 那整条写库分支**只有攻击者会走**。

### 1.4 处置：410 退役，保留路由当信号

与代码库已有的先例完全同款 —— `recognition.py:62` 的 `/recognition/recognize`
当初就是这么处理的，它的退役理由读起来像是在描述本次发现：

> 裸 GPT 猜测流:**不鉴权、不计费、不接地**……一条任何人都能无限调用、
> 烧我们 GPT 额度的后门……保留路由只为给可能还在调它的老客户端一个明确信号,不是静默 404。

**为什么不是"加鉴权"**：加了鉴权，注册一个免费账号照样能烧、照样能覆盖已发布内容——
鉴权把匿名变成可追溯，但 1.2 的破坏力一点没降。而这个端点**没有任何现役用途**：
它的产品形态（识别出一件库里没有的作品 → 现场生成讲解）已经被
「`/recognize` 返 qid → `/museums/{slug}/objects/{qid}/content`」整条取代，
后者还带全套质量闸。留着它 = 留一条绕过所有闸的旁路。

**风险与判定**：已装老 APK 若走到 history 页那条兜底 → 讲解页显示错误而非内容。
触发条件是"后端不返回 slug/qid"，prod 不会发生。判定可接受。

**同批处置 `/content/tts/info`、`/content/tts/voices/{language}`**：无鉴权但**不花钱**
（`content.py:320-366` 只做 hash + 词数估时长，不调 TTS），前端也不用。
**留着不动** —— 本次只砍会花钱或会写库的，不做顺手清理。

---

## 二、🔴 P0-2：`GET /museums/{slug}/objects/{qid}/content` —— 无鉴权点燃懒生成

`museums.py:72`。这就是分享页那条警告的本体，**它不是未来的风险，是现在就开着的**。

```python
def object_content(slug, qid, background_tasks, language="zh", db=Depends(get_db)):
    maybe_trigger(db, qid, schedule=background_tasks.add_task, language=language)
```

无 `credentials`。`lazy.py:233-260` 的 `maybe_trigger`：
`content_status == "stub"` → `run_lazy_generation`；
`ready` 但请求语言缺内容且有 en 轴心 → `run_lazy_translation`。
两条都是真金白银的 LLM 调用（`content_enricher.py:176`、`vision.py:189`）。

另外注意：**`maybe_trigger` 在 404 检查之前调用**（第 85 行 vs 第 87 行）。
顺序是刻意的（注释解释了：先上锁否则前端不轮询），但副作用是
"这个 qid 根本不属于这个 slug"也会先走一遍触发逻辑。

### 2.1 成本估算（公式 + 每个变量的来源，可独立重算）

| 变量 | 值 | 来源 |
|---|---|---|
| prod stub 件数 | **26,556**（ready 665） | prod DB `museum_objects.content_status` |
| 近 40 天 `generate` 通道 | 563 calls / 1.90M in / 0.196M out | prod `llm_usage` |
| 近 40 天 `gate` 通道 | 1,706 calls / 5.87M in / 0.020M out | 同上 |
| 近 40 天 `vision` 通道 | 66 calls / 79.3k in / 8.7k out（gpt-4o） | 同上 |
| 近 40 天实际生成件数 | **473 件 / 838 段** | `object_content_sections.generated_at` |
| 单价 | 4o-mini $0.15/$0.60 per 1M；4o $2.50/$10.00 | OpenAI |

→ generate $0.403 ÷ 473 = **$0.00085/件**；gate $0.893 ÷ 473 = **$0.0019/件**；
vision **$0.0043/件**；请求语言翻译 ≈ **$0.0035/件**
→ **≈ $0.01/件 × 26,556 ≈ $265**（一次性：每件只生成一次，之后转 ready/empty）

⚠️ **最弱的变量是"一件几次调用"** —— 用 40 天总量摊算，若那批混了重跑则单件成本被高估。
量级可信（百美元级，不是万美元级也不是十美元级），精度不可信。

### 2.2 钱不是最大的损失

按 [[grounding-gate-visual-description-blindspot]]：**无维基条目的件不能规模化生成**——
外观描写是编的，而接地闸判 `IMPRESSION` 会放行（小皇宫 97.8% 是这种件）。
被爬虫点燃 26,556 件 = 一大批脑补内容进库，且按「生成一次、永久落库」原则**是永久的**。
$265 能再赚回来，污染的库要一条条查出来删。

### 2.3 处置：两道，都是加法

**① 匿名不点火**（根因）。读内容保持公开（探索页不带令牌是正常形态），
但**点燃付费生成需要一个可追溯的身份**：

```python
credentials: HTTPAuthorizationCredentials | None = Depends(_bearer)
...
if _user_id(db, credentials):                 # 坏/过期令牌当匿名，绝不 401
    maybe_trigger(db, qid, schedule=..., language=language)
```

沿用 `recognize_global.py:23` 已有的 `_user_id` 容错写法 —— **绝不 401**，
否则老 App 拿着过期 token 打详情页会直接崩。

行为影响近乎为零：App 里连游客都持有令牌（`/auth/guest` 发）。
**副产品**：将来的公开网页层天然不点火，[[product-backlog]] 里那条 🔴🔴 告警一并解掉。

**② 全局日上限**（钱包止损）。身份闸让匿名无限变成"注册一个号就能刷"——
可追溯可封号，但不会自动停。按 `_SEM(2)` × 2 worker × 每次 30-60s 估，
一个脚本化账号约 5 天能跑完全库。

```python
# ponytail: 单条 count 查询,不建表。钉住"最坏一天能花多少钱"这一件事。
_LAZY_DAILY_CAP = 300          # ≈ $3/天;正常业务量(近 40 天 473 件)远低于它
```

用 `object_content_sections.generated_at >= today` 计数，超了 `maybe_trigger` 直接 return。
它保护的是**总额**，与调用者是谁无关 —— 这是身份闸覆盖不到的那一半。

**不做每用户配额**：有了 ①+② 之后它是第三层，YAGNI。

---

## 三、🟠 P1：全局零限流

- **应用层**：`core/rate_limit.py` 的 slowapi limiter **只挂在** `feedback.py:78`（60/hour）、
  `payment.py:396`（120/minute）、`auth.py` 六处。上面 P0 的两个端点、搜索、馆包**全裸奔**。
- **nginx 层**：`deployment/production/nginx-api.gomuseum.app.conf` 里
  **一条 `limit_req` / `limit_conn` 都没有**，只有 `client_max_body_size 15m`。

这是把每个洞的破坏力从"有上限"变成"无上限"的乘数因子。堵洞的同时必须补它，
否则下一个新加的端点又是一条敞开的水龙头 —— 单点防御的老问题
（同 conftest 堵一处 vs 逐个用例补注入，#607）。

**处置**：nginx 加一层 IP 级限流，一道兜底所有路由：

```nginx
limit_req_zone $binary_remote_addr zone=api:10m rate=10r/s;
limit_req zone=api burst=20 nodelay;
limit_req_status 429;
```

10r/s + burst 20 对正常 App 使用绰绰有余（一次开页也就几个请求）。

⚠️ 这是部署配置，**不在 `backend/` 路径下 → 不触发 CD**，
需要在 VPS 上手动 `nginx -t && nginx -s reload`。**⛔ prod 写操作由用户执行。**

---

## 四、🟠 P1：`GET /museums/{slug}` 全量馆包（可用性，非成本）

`museums.py:224`，无鉴权，`artworks` **缺省 true**。
docstring 自己记了实测数字：**卢浮宫全量 5.0MB / 5.7s**。

prod 跑 `--workers 2`，十几个并发请求就能把两个 worker 连同 DB 一起压死。
不花 LLM 的钱，但花可用性。

**处置：本次不改代码**。缺省值是老 App 契约不能动（改了老 App 收不到藏品列表），
而加上限等于改语义。§三 的 nginx 限流已经覆盖这个场景 —— 它就是为"无上限"而加的。
在此记一笔，免得下次审计重新推一遍。

---

## 五、🟡 P2：`recognition.py` 的三个遗留端点

`/recognition/recognize` 已经 410 退役，但同一个 router 里还留着三个**无鉴权**的：

| 路由 | 位置 | 问题 |
|---|---|---|
| `GET /recognition/recent?limit=N` | `recognition.py:260` | 返回**他人**识别结果；`limit` 无上限 |
| `GET /recognition/stats` | `recognition.py:223` | 泄漏内部统计 + 性能指标 |
| `GET /recognition/recognize/{id}` | `recognition.py:171` | id 可枚举 |

**prod 实测 `recognition_results` 表 0 行** —— 唯一的写入者是已经 410 的那条老路径
（`recognition_service.py:121`），所以今天它们返回空，不泄漏任何东西。

但这是颗雷：**表里一有行就立刻变成泄漏**，而没人会记得这三个端点还开着。
同型的洞这个项目已经修过一次 —— `/history/*` 的"匿名可读可删"
（[[product-backlog]]，加 user_id 维度时顺手堵的）。

**处置：删掉这三个路由**（纯删除，不是加代码）。`/recognition/recognize` 的 410
信号保留不动。

---

## 六、✅ 查过是好的（写下来，免得下次重审）

审计的价值有一半在这里 —— 否则下次又要把这些全部重新 trace 一遍。

| 端点 | 为什么安全 |
|---|---|
| `POST /chat/ask` | `chat.py:84` 无条件 `raise 503`，后面的 OpenAI 调用是死代码 |
| `POST /recognition/recognize` | `recognition.py:73` 无条件 `raise 410` |
| `POST /content/tts/generate` | `_require_tts_access`（`content.py:33`）：无 qid 要通票 ACTIVE，有 qid 同 `/audio` 规则 |
| `GET /museums/.../audio`、`/audio/stream` | `_require_audio_access`（`museums.py:28`）—— **付费墙唯一执行点**，且在触发 TTS 之前 |
| `POST /recognize`、`POST /museums/{slug}/recognize` | 配额闸 `recognize_billed`（`service.py:411`）在 GPT 调用**之前**抛 `QuotaExceededError` |
| `POST /recognize/confirm` | `confirm_event` 要求 24h 内存在匹配 `phash` 的事件行，否则静默 no-op |
| `POST /feedback` | 60/hour 限流 |
| `/auth/*` | 六处限流齐全 |
| `POST /payment/rtdn` | OIDC 验签（[[staging-pending-prod-release]] 债②） |
| `GET /content/tts/info`、`/tts/voices/{lang}` | 无鉴权但不调 TTS，只做 hash 和词数估算 |

**TTS 侧全部三个调用点都在闸后**（`content.py:255,287` 经 `_require_tts_access`；
`lazy_audio.py:22`、`streaming_audio.py:145` 只由 `museums.py:125,153` 调用，
两处都先过 `_require_audio_access`）。TTS 这条线是干净的。

---

## 七、已知且已接受，不在本次范围

**device_id 可刷 → 免费识别额度可绕**。`recognize_billed` 的 docstring
（`service.py:395-397`）自己写明了：

> 存在"反复拍到候选就能不限次识别"的窗口 —— 与删号刷额度同源
> (设备身份可刷,见 `auth_service.delete_user_account`),根治同样要靠 Play Integrity,MVP 接受。

这是**已记录的决策**，不是新发现。每次识别的边际成本被 DINOv2 主引擎吃掉大半
（GPT 只在兜底档），且它绕的是"免费额度"不是"总成本"。不在本次范围，
但要知道 §三 的 nginx 限流会顺带把它的速率压下来。

---

## 八、改动清单（按提交顺序）

| # | 改动 | 文件 | 性质 |
|---|---|---|---|
| 1 | `/content/explanation` → 410 退役 | `content.py` | 删除 |
| 2 | 删 `/recognition/{recent,stats,recognize/{id}}` | `recognition.py` | 删除 |
| 3 | `object_content` 加 optional bearer，匿名不 `maybe_trigger` | `museums.py` | 加法 |
| 4 | `maybe_trigger` 加全局日上限 | `lazy.py` | 加法 |
| 5 | nginx `limit_req` | `deployment/production/nginx-api.gomuseum.app.conf` | 配置（手动 reload） |

**契约前向兼容**：1 和 2 是退役，形状上是"老端点返 410" —— 按契约本该走版本化，
但这里的判据是 §1.3/§5 已查证**没有现役调用方**（1 的唯一引用在一条走不到的兜底路径上，
2 的表 0 行）。3 和 4 是纯加法，响应形状零变化。**不需要发 App 包。**

---

## 九、自检

按 [[test-across-config-dimension]]，配置/身份两侧都要测。
按本次新增纪律：**凡涉及花钱的格子，断言"花钱那一步没被调用"，不是断言状态码。**

断言 404/410 只证明响应码对，证明不了闸站在花费**上游** ——
一个先调 LLM 再返回 410 的实现照样全绿，而钱已经付了。

| # | 用例 | 断言 |
|---|---|---|
| 1 | `POST /content/explanation` 任意 body | 410，且 `content_service.generate_explanation` **未被调用** |
| 2 | 同上带 `qid=<已发布件>` | 410，且该件的 `body` / `audio_key` **一字未变**（回归测试：这是 §1.2 的破坏力） |
| 3 | `GET .../content` **匿名** + stub 件 | 200 且返回内容，但 `run_lazy_generation` **未被调用** |
| 4 | `GET .../content` **持令牌** + stub 件 | 200，且 `run_lazy_generation` **被调用**（反向：闸不能一刀切死） |
| 5 | 同 4 但当日计数已超 `_LAZY_DAILY_CAP` | 200，且 `run_lazy_generation` **未被调用** |
| 6 | `GET .../content` 持**过期/损坏**令牌 | **不 401**（老 App 不能崩），按匿名处理 |
| 7 | `GET /recognition/recent` | 404（路由已删） |

3 和 4 是同一张 2×2 的两格，**必须成对**：只写 3 的话，一个把 `maybe_trigger`
整个删掉的实现也会绿；只写 4 的话，原样不改也会绿。

`_LAZY_DAILY_CAP` 的判定函数要留一个可跑的自检（[[verify-tools-before-trusting-them]]：
判定类逻辑先用已知正/负样本验证它的判断力，再信它）。

⚠️ 测试本身**零成本** —— 打桩 + 断言 not-called，真实 LLM/TTS 一次都不会被调到；
#607 的 conftest 外网禁连闸（`tests/conftest.py:34`）是最后一道兜底，
万一某个桩漏打了也连不出去，会响亮失败而不是静默花钱。

---

## 十、与可见性闸的关系

两件事**独立**，不要合并：

| | 成本洞（本文档） | 可见性闸（`2026-09-20-museum-visibility-gate-design.md`） |
|---|---|---|
| 解决什么 | 匿名调用者能烧钱 / 污染数据 | 准备期的馆不该被真实用户看见 |
| 现状 | **洞现在就开着** | 现有四馆全已上线，零影响 |
| 截止日 | **现在** | 下一家馆开灌之前 |

可见性闸的 §二 暴露面清单里有 5 个直达端点与本文档重叠（`object_content` 等）。
**它们加的是不同维度的检查** —— 本文档加"你是谁"，可见性闸加"这家馆放出了没有"，
两者都堵在解析层，不冲突。先做本文档的，可见性闸落地时在同样的位置加第二个谓词。
