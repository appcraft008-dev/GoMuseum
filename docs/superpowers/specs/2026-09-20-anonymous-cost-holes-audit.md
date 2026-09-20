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

### 0.1 🔑 这三步还是漏了一个，独立 review 抓到了

我把 `/content/tts/generate` 放进了"查过是好的"清单，理由是"它有 `_require_tts_access`"。
**闸是真的，但它判的不是这个动作。**

`_require_tts_access` 回答的是「**你能不能听**这个 (qid, section) 的音频」；
而这个端点的危险动作是「**写入**这个 (qid, section) 的音频」。闸存在，
却站在另一个问题前面 —— 见 §一。

**所以第 2 步要改写**：不是"这个路由有没有鉴权参数"，而是
**"这个路由做的每一个副作用，各自有没有对应的闸"**。
一个端点可以同时做读和写，闸只盖住了读。

同型教训：[[verify-tools-before-trusting-them]]（工具在、但它判的不是你以为的那件事）、
[[proxy-metric-is-not-the-thing-you-ship]]（测的判据和实施的判据差一个数量级）。
这次的形态是**"闸的存在"被当成了"闸的正确"**。

---

## 一、🔴 P0-1：`POST /content/tts/generate` 的 section 模式 —— 任意文本可被永久写成某件藏品的官方音频

`content.py:235-271`。**独立 review 发现，我漏了**（原因见 §0.1）。

```python
if request.qid and request.section_code:
    _require_tts_access(db, credentials, qid=..., language=..., section=...)
    existing = get_section_audio_key(db, request.qid, request.language, request.section_code)
    if existing:
        return AudioUrlResponse(..., cached=True)          # 已有 → 直接返回，不覆盖
    result = await tts_service.generate_audio(
        text=request.text, ...                              # ← 客户端自由文本
    )
    key = persist_section_audio(db, request.qid, request.language, request.section_code,
                                result["audio_data"], storage)   # ← 写成该段的正式音频
```

**`request.text` 与 DB 里 `object_content_sections.body` 没有任何关系。**
服务端既不查正文、也不比对。攻击者提交什么，就合成什么，然后写进 `audio_key` ——
**从此作为这件作品该语言该段落的官方音频，发给所有后续用户**。

### 1.1 谁能触发

`entitlement_service.py:314-316`：

```python
state, _ = resolve_state(db, user_id, city)
if state == ACTIVE:
    return True                    # ← 通票生效 = 任意 qid、任意 section、任意 language
if section != FREE_AUDIO_SECTION:
    return False
return qid in free_audio_qids(benefits)
```

| 身份 | 能写哪些槽位 |
|---|---|
| 买了一张通票（€9.49） | **全库任意 (qid, language, section)** |
| 免费注册 + 识别过一件 | 那件的 `guide` 段，10 个语言各一个槽位 |

而 `persist_section_audio`（`content_repo.py:80-88`）在没有该行时会**新建行**，
所以 `section_code` 还可以是编造的任意字符串。

### 1.2 为什么比"覆盖文字"更糟

- **音频是用户真正消费的东西**。文字有人扫一眼就发现不对，音频要听完。
- **写入即锁死**：`existing` 非空就走 `cached=True` 分支直接返回。一旦被写进去，
  **后续任何正常流程都不会覆盖它，也不会发现它** —— 除非有人正好听了那一段。
- **暴露面几乎是全库**：prod 只有约 1,464 条音频行，而 665 件 ready × 10 语 × 约 5 段
  ≈ 33,000 个槽位。**95% 以上的槽位处于"首次可写"状态**，stub 的 26,556 件更是全空。
- **完全在质量闸之外**。项目那套接地闸/忠实度闸挂在 `enrichment/` 里，这条路径不经过。

### 1.3 对照：`/audio` 端点是对的

`museums.py:92-168` 的 `/audio` 和 `/audio/stream` **不接受客户端 `text`** ——
音频正文由服务端从已发布 section 取（`get_or_make_audio_url`）。
同一个仓库里两条路径，一条对一条错，错的那条是历史遗留。

### 1.4 处置：删掉 section 模式

**App 从不使用它。** `GenerateTtsAudioParams`（`generate_tts_audio.dart:52-63`）
只有 `text / language / voice / speed` **四个字段，没有 qid，也没有 sectionCode`**。
datasource 里那段 `if (qid != null && sectionCode != null)` 分支（`content_remote_datasource.dart:96`）
**没有任何调用方能满足条件**。App 的真实音频一直走 `/museums/.../audio`。

所以最小且彻底的修法是**删掉 section 模式整个分支**，不是"改成服务端取正文"——
后者是在给一条没有用户的路径写新功能。ad-hoc 模式（需通票 ACTIVE）保留不动。

> 备选（若将来真需要这个端点）：section 模式忽略 `request.text`，
> 改为服务端按 `(qid, language, section_code)` 查正文，与 `/audio` 完全一致。
> 现在不做 —— 没有调用方。

---

## 二、🔴 P0-2：`POST /api/v1/content/explanation` —— 无鉴权的 LLM + 可覆盖已发布内容

`content.py:118`。严重度高于最初怀疑的 `object_content`：它同时命中"花钱"和"污染数据"。

```python
@router.post("/explanation", response_model=ExplanationResponse)
async def generate_explanation(
    request: ExplanationRequest, content_service=Depends(get_content_generation_service)
) -> ExplanationResponse:
```

**没有 `credentials` 参数。没有限流。**

### 2.1 花钱：单次请求可放大 ~20 倍

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

### 2.2 写库：绕过全部质量闸，覆盖已发布内容，并让音频静默变哑

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

### 2.3 前端还在引用它吗？——在，但那条路实际走不到

`content_remote_datasource.dart:52` 确实打这个端点。往上 trace：

```
guide_page.dart:147  if (!widget.args.useA5) { _loadExplanation(); }
guide_page.dart:88   bool get useA5 => slug != null && qid != null;
```

全部 5 个 `GuideArgs(...)` 构造点里，只有 `history_page.dart:282` 那一处不传 slug+qid，
而它自己的注释写着「**老后端不返回 slug/qid 时的兜底**」。prod 后端从 #483 起一直返回。

而且 App 这条路**从不传 `qid`**（`GenerateExplanationParams` 里就没这个字段）——
1.2 那整条写库分支**只有攻击者会走**。

### 2.4 处置：410 退役，保留路由当信号

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

## 三、🔴 P0-3：`GET /museums/{slug}/objects/{qid}/content` —— 无鉴权点燃懒生成

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

### 3.1 成本估算（公式 + 每个变量的来源，可独立重算）

| 变量 | 值 | 来源 |
|---|---|---|
| prod stub 件数 | **26,556**（ready 665） | prod DB `museum_objects.content_status` |
| 近 40 天 `generate` 通道 | 563 calls / 1.90M in / 0.196M out | prod `llm_usage` |
| 近 40 天 `gate` 通道 | 1,706 calls / 5.87M in / 0.020M out | 同上 |
| 近 40 天 `vision` 通道 | 66 calls / 79.3k in / 8.7k out（gpt-4o） | 同上 |
| 近 40 天实际生成件数 | **473 件 / 838 段** | `object_content_sections.generated_at` |
| 单价 | 4o-mini $0.15/$0.60 per 1M；4o $2.50/$10.00 | OpenAI |

| 近 40 天 `translate` 通道 | 4o: 29,305 calls / 5.07M in / 0.337M out；4o-mini: 29,740 / 14.20M / 1.79M | 同上 |

#### 三个可靠通道

| 通道 | 40 天成本 | ÷ 473 件 |
|---|---|---|
| generate | 1.902825×0.15 + 0.195806×0.60 = **$0.4029** | $0.000852 |
| gate | 5.874057×0.15 + 0.019951×0.60 = **$0.8931** | $0.001888 |
| vision | 0.079280×2.50 + 0.008676×10.00 = **$0.2850** | $0.000603 |

#### 🔴 translate：我第一版算错了，独立 review 的质疑成立

我原本写 "翻译 ≈ $0.0035/件"，做法是 59,045 次调用 ÷ 473 件。
review 质疑这批调用可能是**一次性存量回填**而非随生成触发的翻译。**按天拆开一查，是的**：

| 日期 | translate calls | generate calls |
|---|---|---|
| 2026-08-31 | 6,261 | **0** |
| 2026-09-01 | 29,543 | **0** |
| 2026-09-02 | 20,557 | **0** |
| 其余 15 天合计 | 2,684 | 563 |

**56,361 / 59,045 = 95.5% 的翻译调用发生在 3 天里，而那 3 天 `generate` 全是 0。**
那是六语开放的存量回填（[[six-languages-rollout]]），与"点燃一件新藏品"毫无关系。
把它摊进单件成本 = 教科书式的 [[proxy-metric-is-not-the-thing-you-ship]]。

按桶重算，只取"生成活跃日"那一桶（2,684 calls）：
4o: 0.011523×2.50 + 0.004447×10.00 = $0.073；
4o-mini: 1.413814×0.15 + 0.215573×0.60 = $0.341
→ **$0.4147 ÷ 473 = $0.00088/件**（比我原来的估算低 4 倍）

#### 结果：给区间，不给点估计

| | 单件 | × 26,556 |
|---|---|---|
| **下界**（历史比率照搬：vision 14% 触发、观察到的语言组合） | $0.00422 | **≈ $112** |
| **上界**（vision 100% 触发、十语全扫） | $0.0151 | **≈ $400** |

⚠️ **两个变量的不确定性，方向相反地被我各错了一次**：
- **vision 触发率**：我原先按 $0.2850/66 = **每次调用**成本乘到每一件，等于假设 100% 触发；
  历史实测只有 66/473 = **14%**。但 review 指出剩下 26,556 件恰恰是**材料最薄的冷门件**
  （小皇宫 84% 无英文标题），视觉兜底触发率必然高于历史值。所以下界偏低、上界偏高，真值在中间。
- **translate**：我高估了 4 倍（见上）。

两处误差方向相反、大致抵消，我原来那个 $265 恰好落在区间里 —— **但那是运气，不是计算**。

⚠️ **不在这个估算里的成本**：TTS（已迁自托管 VoxCPM2，不走 OpenAI 计费，但有 GPU 成本）、
R2 存储与出网（美分级）。

✅ **确认不存在的风险**：`pipeline.py:401-402` 保证 `generate_object` 结束后状态必然收敛到
`ready` 或 `empty`，**从不停留在 `stub`** —— 所以同一件不会被反复重新点燃。
这是这条路径上唯一真实有效的"总量"保护。

### 3.2 钱不是最大的损失

按 [[grounding-gate-visual-description-blindspot]]：**无维基条目的件不能规模化生成**——
外观描写是编的，而接地闸判 `IMPRESSION` 会放行（小皇宫 97.8% 是这种件）。
被爬虫点燃 26,556 件 = 一大批脑补内容进库，且按「生成一次、永久落库」原则**是永久的**。
百来美元能再赚回来，污染的库要一条条查出来删。

### 3.3 处置：两道，都是加法

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

## 四、🟠 P1：全局零限流

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

## 五、🟠 P1：`GET /museums/{slug}` 全量馆包（可用性，非成本）

`museums.py:224`，无鉴权，`artworks` **缺省 true**。
docstring 自己记了实测数字：**卢浮宫全量 5.0MB / 5.7s**。

prod 跑 `--workers 2`，十几个并发请求就能把两个 worker 连同 DB 一起压死。
不花 LLM 的钱，但花可用性。

同一类的还有 `list_objects`（`museums.py:176` `limit: int = 50`）和
`search.py:23,35`（`limit: int = 20`）——**都没有上限**，`limit=999999` 可以一次拉全库。

**处置**：
- `get_museum_pack` 的 `artworks` 缺省值**不动**（老 App 契约：改了老 App 收不到藏品列表）。
- `list_objects` / `search` 的 `limit` 加**服务端截断** `min(limit, 200)`。
  ⚠️ 不用 `Query(le=...)` —— 那会让传了更大值的老 App 收到 422，是破坏性变更。
  截断是加法。（`history.py:162` 用的是 `le=100`，那是 2026-09 新写的端点，没有老客户端包袱。）
- 速率那一半交给 §四 的 nginx 限流。

---

## 六、🟡 P2：`recognition.py` 的三个遗留端点

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

## 七、✅ 查过是好的（写下来，免得下次重审）

审计的价值有一半在这里 —— 否则下次又要把这些全部重新 trace 一遍。

| 端点 | 为什么安全 |
|---|---|
| `POST /chat/ask` | `chat.py:84` 无条件 `raise 503`，后面的 OpenAI 调用是死代码 |
| `POST /recognition/recognize` | `recognition.py:73` 无条件 `raise 410` |
| `POST /content/tts/generate` **ad-hoc 模式**（无 qid） | `_require_tts_access(qid=None)` 要求通票 ACTIVE；只返回 mp3 流，**不落库**。⚠️ 同端点的 **section 模式不安全，见 §一** |
| `GET /museums/.../audio`、`/audio/stream` | `_require_audio_access`（`museums.py:28`）—— **付费墙唯一执行点**，在触发 TTS 之前，且**不接受客户端 `text`** |
| `POST /recognize`、`POST /museums/{slug}/recognize` | 配额闸 `recognize_billed`（`service.py:411`）在 GPT 调用**之前**抛 `QuotaExceededError`。⚠️ 但配额本身绕得过，见 §八 |
| `POST /recognize/confirm` | `confirm_event` 要求 24h 内存在匹配 `phash` 的事件行，否则静默 no-op |
| `POST /feedback` | 60/hour 限流 |
| `/auth/*` | 六处限流齐全 |
| `POST /payment/rtdn` | OIDC 验签（[[staging-pending-prod-release]] 债②） |
| `GET /content/tts/info`、`/tts/voices/{lang}` | 无鉴权但不调 TTS，只做 hash 和词数估算 |

`lazy_audio.py:22`、`streaming_audio.py:145` 两个 TTS 调用点只由 `museums.py:125,153` 触达，
两处都先过 `_require_audio_access`，且正文由服务端取。**这两条是干净的**
—— 但 `content.py:255` 那条不是（§一）。

---

## 八、已知且已接受，不在本次范围

**device_id 可刷 → 免费识别额度可绕**。`recognize_billed` 的 docstring
（`service.py:395-397`）自己写明了：

> 存在"反复拍到候选就能不限次识别"的窗口 —— 与删号刷额度同源
> (设备身份可刷,见 `auth_service.delete_user_account`),根治同样要靠 Play Integrity,MVP 接受。

这是**已记录的决策**，不是新发现。

**但独立 review 把它说得更准，这部分是新的**：不只是"反复拍到候选"这个窗口，而是
**GPT 视觉链按构造永远产不出 `match`**：

- `service.py:250` 向量命中才可能是 `match`；向量未命中 → `service.py:256` 调 GPT 视觉
- GPT 链的结果只可能是 `candidates` 或 `unrecognized`
  （`service.py:274` 的注释写明「直判只属于向量像素证据」）
- `service.py:427` 只在 `outcome == "match"` 时扣费

**⇒ 每一次 GPT 视觉调用，在结构上都不会扣费。** 配额永远是满的，
`service.py:411` 那道闸对这条路径形同虚设。图片按 sha256 缓存，改一个字节即绕过。
原 docstring 只提到 `candidates`，没提 `unrecognized` 也走 GPT —— 覆盖了一半。

**本次不改计费逻辑**（"不为失败付费"是用户 2026-09-20 做的产品决定，不该由一次安全审计推翻），
但这条使 §四 的 nginx 限流从"锦上添花"变成**必需项** —— 它是这条路径上唯一的量的上限。

---

## 九、改动清单（按提交顺序）

| # | 改动 | 文件 | 性质 | 对应 |
|---|---|---|---|---|
| 1 | 删 `/content/tts/generate` 的 section 模式分支（ad-hoc 模式保留） | `content.py` | 删除 | §一 |
| 2 | `/content/explanation` → 410 退役 | `content.py` | 删除 | §二 |
| 3 | 删 `/recognition/{recent,stats,recognize/{id}}` | `recognition.py` | 删除 | §六 |
| 4 | `object_content` 加 optional bearer，匿名不 `maybe_trigger` | `museums.py` | 加法 | §三 |
| 5 | `maybe_trigger` 加全局日上限 | `lazy.py` | 加法 | §三 |
| 6 | `list_objects` / `search` 的 `limit` 服务端截断（**不是 422**，见 §十一） | `museums.py`、`search.py` | 加法 | §五 |
| 7 | nginx `limit_req` | `deployment/production/nginx-api.gomuseum.app.conf` | 配置（手动 reload） | §四、§八 |

三条是**删除**，三条是**加法**，一条配置，零条"新功能"。

**契约前向兼容**：1/2/3 是退役 —— 按契约本该走版本化端点，
但这里的判据是已查证**没有现役调用方**：
1 → `GenerateTtsAudioParams` 没有 qid/sectionCode 字段（§1.4）；
2 → 唯一引用在一条走不到的兜底路径上，且 App 从不传 qid（§2.3）；
3 → prod 表 0 行（§六）。
4/5 是纯加法，响应形状零变化。**全部不需要发 App 包。**

**顺带不做的**：`ExplanationRequest` / `TTSRequest` 各字段补 `max_length`。
端点 1/2 删掉之后，剩下的 ad-hoc TTS 已经要求通票 ACTIVE，
长度放大的实际意义不大；nginx 限流兜住速率。YAGNI。

---

## 十、自检

按 [[test-across-config-dimension]]，配置/身份两侧都要测。
按本次新增纪律：**凡涉及花钱的格子，断言"花钱那一步没被调用"，不是断言状态码。**

断言 404/410 只证明响应码对，证明不了闸站在花费**上游** ——
一个先调 LLM 再返回 410 的实现照样全绿，而钱已经付了。

| # | 用例 | 断言 |
|---|---|---|
| 1 | `POST /content/tts/generate` 带 `qid` + `section_code` + 任意 `text`，**持有效通票** | `tts_service.generate_audio` **未被调用**，且 `persist_section_audio` **未被调用** |
| 2 | 同 1，且该 (qid, language, section) **原本没有音频** | 事后该行 `audio_key` 仍为 `None`（回归：这是 §1.2 的破坏力，**别只断言状态码**） |
| 3 | `POST /content/tts/generate` **ad-hoc**（无 qid）+ 有效通票 | 仍正常出 mp3（反向：删 section 模式不能把 ad-hoc 一起弄坏） |
| 4 | `POST /content/explanation` 任意 body | 410，且 `content_service.generate_explanation` **未被调用** |
| 5 | 同 4 带 `qid=<已发布件>` | 410，且该件的 `body` / `audio_key` **一字未变**（§2.2 的破坏力） |
| 6 | `GET .../content` **匿名** + stub 件 | 200 且返回已有内容，但 `run_lazy_generation` **未被调用** |
| 7 | `GET .../content` **持令牌** + stub 件 | 200，且 `run_lazy_generation` **被调用**（反向：闸不能一刀切死） |
| 8 | 同 7 但当日计数已超 `_LAZY_DAILY_CAP` | 200，且 `run_lazy_generation` **未被调用** |
| 9 | `GET .../content` 持**过期/损坏**令牌 | **不 401**（老 App 不能崩），按匿名处理 |
| 10 | `GET /recognition/recent` | 404（路由已删） |

**成对的格子，缺一半就等于没测**：

- **6 和 7** 是同一张 2×2 的两格。只写 6 的话，一个把 `maybe_trigger` 整个删掉的
  实现也会绿；只写 7 的话，原样不改也会绿。
- **1 和 3** 同理。只写 1 的话，把整个端点删掉也会绿 —— 而 ad-hoc 模式是要留的。

这两组正是 [[petit-palais-batch-generation]] 记下的**双向破坏验证**：
既要验"过严的实现会红"，也要验"过松的实现会红"。

`_LAZY_DAILY_CAP` 的判定函数要留一个可跑的自检（[[verify-tools-before-trusting-them]]：
判定类逻辑先用已知正/负样本验证它的判断力，再信它）。

⚠️ 测试本身**零成本** —— 打桩 + 断言 not-called，真实 LLM/TTS 一次都不会被调到；
#607 的 conftest 外网禁连闸（`tests/conftest.py:34`）是最后一道兜底，
万一某个桩漏打了也连不出去，会响亮失败而不是静默花钱。

---

## 十一、独立 review 结论（2026-09-20，已折入）

按 CLAUDE.md 规则 6 跑的独立审计（换模型，**只给原始任务和原始数据，不给我的结论**）。

| 严重度 | 发现 | 处置 |
|---|---|---|
| 🔴 致命 | `/content/tts/generate` section 模式：`request.text` 与 DB 正文无关，可被永久写成某件藏品的官方音频 | **采纳**，提为 §一，改动清单加第 1 条 |
| 🔴 | `translate` 通道的成本不能按"总调用 ÷ 件数"外推，可能是一次性回填 | **采纳且已用数据证实**（95.5% 在 3 天里，那 3 天 generate=0）；§3.1 重算，我原估高 4 倍 |
| 🟠 | GPT 视觉链按构造永不产出 `match` ⇒ 每次视觉调用都不扣费，配额闸对它形同虚设 | **采纳**，写入 §八；使 nginx 限流从可选变必需 |
| 🟡 | `list_objects` / `search` 的 `limit` 无上限，可一次拉全库 | **采纳但改了做法**，见下 |
| 🔵 | 各请求字段无 `max_length` | **不采纳**，理由见 §九"顺带不做的" |

**一处改了做法**：review 建议照 `history.py:162` 的 `Query(default=20, le=100)` 给
`limit` 加校验。**改成服务端 `min(limit, 200)` 静默截断，不返回 422** ——
`le=` 会让任何传了更大值的**已装老 App 直接收到 422**，而契约硬约束是
「后端升级必须前向兼容已部署的老 App」。截断是加法，拒绝是破坏性变更。

**一处指出 review 的交叉校验无效**：review 用"卢浮宫 17,283 件 $40.06 = $0.00232/件"
交叉校验我的单件成本，并以量级一致作为可信证据。**这两个数不是一回事** ——
prod 全库只有 **665 件**有内容，$40.06 不可能是 17,283 件的内容生成费用，
那是**目录接入 + 向量嵌入**的成本。量级偶然接近，不构成校验。

> 🔑 复盘：这次 review 抓到的 §一，我在自己的审计里**明确看过那个端点并判定为安全**。
> 判错的原因不是漏读代码，是**把"闸的存在"当成了"闸的正确"**（§0.1）。
> 这也再次印证规则 6 的那句：给它原始材料而不是我的结论 ——
> 如果我把"这些端点我查过是安全的"一起交过去，它多半会跳过这一个。

---

## 十二、与可见性闸的关系

两件事**独立**，不要合并：

| | 成本洞（本文档） | 可见性闸（`2026-09-20-museum-visibility-gate-design.md`） |
|---|---|---|
| 解决什么 | 匿名调用者能烧钱 / 污染数据 | 准备期的馆不该被真实用户看见 |
| 现状 | **洞现在就开着** | 现有四馆全已上线，零影响 |
| 截止日 | **现在** | 下一家馆开灌之前 |

可见性闸的 §二 暴露面清单里有几个直达端点与本文档重叠（`object_content` 等）。
**它们加的是不同维度的检查** —— 本文档加"你是谁"，可见性闸加"这家馆放出了没有"，
两者都堵在解析层，不冲突。先做本文档的，可见性闸落地时在同样的位置加第二个谓词。
