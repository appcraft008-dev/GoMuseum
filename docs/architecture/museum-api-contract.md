# GoMuseum 博物馆主文档（API 契约 + 内容体系 + 上馆手册 + 路线图）

> **这是唯一权威主文档。** 所有博物馆按本文的契约与路线图上线;奥赛 = 样板馆。
> **工作纪律**:每次决策 / 发现的问题 / 零散需求 → **回写本文**。带日期的 `docs/superpowers/specs/*` = 设计记录,**喂给本文**;本文永远是当前真相。新馆只读本文即可快速上线。
> 端点前缀 `/api/v1`。**加法/前向兼容**——只增字段、不破老解析;破坏性变更走版本化端点。
> 最近更新:2026-06-29(default_guide 阶段1 + 内容体系与路线图入册)。

## 北极星

上任意馆 = **配源 → 抓全证据包 → 生成一次(分层·去重·动态·接地)→ 封板**。馆上线后基本不再动,精力转下一个馆。本文 = 实现这一目标的契约 + 手册 + 路线图。

> 详细内容体系(三层体验 / 模块库 / 证据包)见 §内容体系;演进顺序见 §路线图。

## 端点总览

| 端点 | 用途 | 实现(`museum_repo.py`) |
|---|---|---|
| `GET /museums` | 馆索引(探索页) | `list_museums` |
| `GET /museums/{slug}?language=` | 完整馆包(元数据+分类+全藏品) | `get_museum_pack` |
| `GET /museums/{slug}/objects?...` | 分页藏品列表(列表页) | `list_objects` |
| `GET /museums/{slug}/objects/{qid}/content?language=` | 单件讲解(导览页) | `get_object_content` |

`language` 取值:`zh`/`en`/`fr`(当前生成的语种;`de`/`es`/`it` 在 `DEFAULT_LANGUAGES` 但暂未生成)。缺省 `zh`。

---

## 1. `GET /museums`

馆列表,不含藏品。无 language 参数。

```json
[
  {"slug": "orsay", "name_zh": "奥赛博物馆", "name_en": "Musée d'Orsay",
   "city_zh": "巴黎", "city_en": "Paris", "country": "FR", "artwork_count": 262}
]
```

> **规划未实现**:`cover_url`(馆封面图,前端首页"附近博物馆"需要)。届时加法补入,见交接备忘。

## 2. `GET /museums/{slug}?language=zh`

完整馆包:馆元数据 + **分类 facet** + 按热度降序的全藏品。`language` 仅影响 `categories[].label`。

```json
{
  "slug": "orsay", "name_zh": "奥赛博物馆", "name_en": "Musée d'Orsay",
  "city_zh": "巴黎", "city_en": "Paris", "country": "FR",
  "qid": "Q23402", "source": "...", "generated_at": "2026-...Z",
  "artwork_count": 262,
  "categories": [
    {"code": "all", "label": "全部", "count": 262},
    {"code": "painting", "label": "绘画", "count": 259},
    {"code": "unknown", "label": "其他", "count": 3}
  ],
  "artworks": [
    {"qid": "Q334138", "title_zh": "世界的起源", "title_en": "L'Origine du monde",
     "artist_zh": "居斯塔夫·库尔贝", "artist_en": "Gustave Courbet",
     "year": "1866", "period_zh": null, "period_en": null,
     "image": "<url>", "popularity": 51}
  ]
}
```

- `categories`:`all` 合计 + 各 `MuseumObject.category` 分组计数,标签本地化(`_CATEGORY_LABELS`:painting/sculpture/photography/decorative_arts/unknown)。
- `artworks[].title_zh` 永不为 null(回退 `title_en`→`qid`,防前端裸 `as String` 崩)。
- ⚠️ `artworks` 是**全量**(无分页);列表页改用端点 3。本端点保留供馆详情/概览。

## 3. `GET /museums/{slug}/objects`

分页藏品列表(列表页 A2/A3:分类 tab + 无限滚动)。

**Query**:`category`(可选,`all` 或省略=不过滤)、`sort`(默认 `popularity`)、`limit`(默认 50)、`offset`(默认 0)、`language`(默认 `zh`)。

```json
{
  "items": [
    {"qid": "Q334138", "title": "世界的起源", "artist": "居斯塔夫·库尔贝",
     "year": "1866", "thumbnail": "<url>", "content_status": "ready"}
  ],
  "total": 262, "limit": 50, "offset": 0
}
```

- `title`/`artist` 按 `language` 选语种(zh→`title_zh`→`title_en`→`qid`;fr→`attributes.title_fr`→`title_en`;en→`title_en`→`title_zh`)。
- `content_status`:见末节生命周期(前端据此显"待完善"角标)。
- 未知馆 → 404。

## 4. `GET /museums/{slug}/objects/{qid}/content?language=zh`

单件讲解(导览页)。按 `language` 返对应语种已发布内容。

```json
{
  "qid": "Q334138", "category": "painting", "language": "zh",
  "status": "ready",
  "title": "世界的起源",
  "default_guide": {"body": "想象一下,站在一幅大胆的画作前…(单主线~300-600字现场导览)", "audio_url": null},
  "images": [{"url": "<url>", "credit": "..."}],
  "facts": {
    "artist": "居斯塔夫·库尔贝", "date": "1866",
    "medium": "...", "dimensions": "...", "inventory": "RF 1995 10",
    "location": "奥赛博物馆", "provenance": "...", "artist_life": null,
    "exhibitions": ["1988, New York...", "..."], "bibliography": ["..."]
  },
  "tabs": [
    {"section_code": "overview", "label": "通用描述", "icon": "...",
     "body": "《世界的起源》是...", "audio_url": null}
  ],
  "suggested_questions": [{"question": "...", "answer": "..."}]
}
```

- `default_guide`:**默认标准讲解**(单主线·5拍·~300-600字现场导览,识别后首先呈现的"主角")。`{body, audio_url}`,无则 `null`(前端回退 tabs)。**不混入 tabs**。前端分层页:default_guide 置顶 → 推荐 2-3 个 suggested_questions → tabs/其余收进"更多内容"。
- `tabs`:按类目的段落清单(`SECTIONS_BY_CATEGORY`)逐段(降级为"更多内容"深度模块;**overview 已退役**——默认讲解取代其作开场;**artist 已移出 tabs**——成独立作者卡;各模块各守互斥 lane、**不复述头条**、只会重复则返空不发布);`body` 为该语种已发布正文(无则 `null`);`audio_url` 为 R2 音频直链(未生成则 `null`,TTS 阶段)。
- `artist`:**必选常驻作者卡**(不随空隐)。`{name, birth, death, nationality, notable_works:[...], bio}`——生卒年/国籍/代表作取自作者 Wikidata 实体(P569/P570/P27/P800);`bio`=artist 段已发布叙事(无则 null)。⚠️ v1:`nationality`/`notable_works` 为 en 标签(zh 视图暂显 en),`name`/生卒年不受影响。
- `facts`:**已策展+人性化的墙签事实**(只 wall_label 级):`artist/date/medium/dimensions/inventory/location`。`medium`/`dimensions` 优先取证据包干净源(Wikidata P186/P2048)。⚠️ **`provenance` 返 null、`exhibitions`/`bibliography` 返 `[]`——已移出面板**(学术噪音;参考文献彻底不展示,收藏/展览史进证据包材料级,阶段2 由 background lane 讲成流转故事)。`artist_life` 暂 null。
- `suggested_questions`:好奇心问答(0-4 条)。
- 对象不属于该 slug / 不存在 → 404。

---

## `content_status` 生命周期

`stub`(只元数据,目录铺出) → `generating`(生成中,懒生成锁) → `ready`(≥1 段已发布)/ `empty`(无可接地材料)。前端:`stub`/`empty` 显"待完善",`ready` 正常。未知值按 `ready` 容错。

## 图片字段

`image`(端点2)/`thumbnail`(端点3)/`images[].url`(端点4)取值:`ObjectImage.image_key` 有则 R2 直链(`storage.public_url`),否则回退 `source_url`(当前多为 Wikimedia `Special:FilePath`)。
> ⚠️ **已知问题 + 规划**:Wikimedia 链接按 UA 策略拦截(需合规 UA)且原图大/现生成慢。规划:富化阶段把图自存 R2 并预生成尺寸档,`image_key` 填充后这些字段自动返 R2 直链(字段名不变,前端零改)。见图像自存交接。

---

## 上新馆 = 纯配置(零核心改动)

连接器已存在时(Wikidata 全球通用),上新馆只需:

1. **`backend/museums.yaml` 加一条**:
   ```yaml
   <slug>:
     name_zh / name_en / city_zh / city_en / country
     wikidata_qid: Q...        # 馆的 Wikidata 实体(P195 收藏于)
     category_filter: Q3305213 # 主类目 QID
     categories: [Q3305213, ...]
     country_lang: fr          # 馆所在国语言(取该语维基)
     fetch_limit / sample_size / sample_qids
     languages: []             # 空=用 DEFAULT_LANGUAGES;或指定子集
   ```
2. **铺目录**:`python scripts/onboard.py <slug> catalog --target <staging|prod>`
   → `WikidataCatalog.list` 列 stub → `merge_stubs` 去重 → `load_stubs` 落库(`content_status=stub`,元数据+路由 external_ids/wiki_titles)。
3. **生成内容**:`python scripts/onboard.py <slug> generate --target <env> [--qid Q..|--limit N] [--langs zh,en,fr]`
   → 逐件:stub 抓材料(Wikipedia/Joconde)→ 生成 → 接地闸 → 翻译 → 落库 → `ready`/`empty`。
4. 端点自动产出上述四个契约;前端零改接入。

**非 Wikidata 主源的馆**(如美国 Met):一次性写个 `CatalogSource` 连接器(同插件模式,核心零改),其余同上。

`--target` 必须匹配容器 `ENVIRONMENT`(守卫防误灌)。全量富化在 prod 跑(staging 仅样本验证机制)。

---

## 内容体系（三层 + 模块库 + 证据包）

**博物馆负责事实,AI 负责讲法。** 每件内容分三层,各守互斥职责,从同一份证据包生成、不重复:

- **第一层 默认标准讲解**(`default_guide`,已上 stage1):识别后首先呈现的"主角",单主线·5拍(钩子→引导观察→为什么重要→必要背景→记忆点)·按热度分档(普通 270-420 / 重点 420-675 中文字)。~1 分钟看懂。
- **第二层 预设常见问题**(`suggested_questions`):3-6 个,讲后推荐 2-3,补头条/模块**没答**的。
- **第三层 AI 自由问答**(`/ask`,规划):多轮,复用证据包,争议必 hedge。

**模块库(`tabs`,深度内容,降级为"更多内容")** —— 各守互斥 lane,**只补默认讲解没深挖的一面**:

| 模块 | 专属职责 | 不讲(交给谁) |
|---|---|---|
| artist | 作者其人(生平/性格/艺术史地位) | 不讲这幅画的丑闻/技法 |
| background | 作品史实链**事件**(何时/谁委托/在哪展/风波/流转) | 不讲"为什么重要"(→significance)、怎么看(→analysis) |
| analysis | 看什么(构图/笔触/视觉细节) | 不讲历史/影响 |
| significance | 影响与遗产(改变了什么/影响了谁) | 不复述丑闻事件(那是 background) |
| facts | 一个别处没有的趣闻 | 不与上面重复 |

**关键机制(✅阶段2a 已落地)**:① 先生成默认讲解(头条)→ 模块单调用带头条+证据包富属性+锐化 lane"各守职责、深化非复述、只会重复就返空"(生成已从证据包取料)→ 问答最后只补缝。② **动态显示**:空模块不展示(料薄优雅降级,默认讲解是地板)。③ overview 退役(与默认讲解头条重复)。

**证据包(`MuseumObject.evidence_pack`,内容唯一来源)**:每件生成时组装、落库(JSONB,后台中间产物,不进端点契约)。结构 `{facts:[{claim,value,source,topic,tier}], narrative:[{text,source,type}], flagged:[{text,type,source}]}`:
- `facts` = 结构原子(对象字段 + Joconde + Wikidata 富属性 P88/P180/P186/P135…),`tier`=`wall_label`(进 facts 面板)/`material`(只喂生成),`topic`=lane 提示。
- `narrative` = Wikipedia 作品/作者全文块,标 `mainstream`。
- `flagged` = LLM 抽出的争议/推测/未证实句(`contested/inference/unverified`,供阶段2 hedge)。
- **阶段1 已落地(`build_evidence_pack`)**:富属性按 registry 门控(真实生成走网络);阶段2 才把三层+模块生成切到证据包。Europeana 暂缓(待 key)。

## 路线图（执行顺序;每阶段 = 独立 spec→plan→实现,完成回写本文）

**✅ 已落地**:目录主干 + 4 端点契约 + 分类 facet + 作品信息 facts;接地·引人入胜生成 + 三类闸 + 多语翻译 + 建议问答;默认讲解 stage1(staging)。

- **阶段 1 — 材料地基(证据包)**:1a 源配全(Europeana + 更全 Wikidata P 属性;法国官方=Joconde 已有,非法国馆逐馆官方连接器)· 1b 证据包模型 + 分类落库。→ 每件一份完整分类证据包。
- **阶段 2 — 内容生成重构**:2a 统一分工去重(lane)+ 全从证据包生成 · 2b 动态模块 + 争议 hedge · 2c 两段式质量评估(事实质量 + 讲解质量)。
- **阶段 3 — 体验补全**:3a AI 自由问答 `/ask`(多轮)· 3b TTS 音频落库 ·(藏品识别机制 = 独立 brainstorm)。
- **阶段 4 — 规模化**:图像 R2 自存 + `cover_url` + 首页真实化 · 上新馆(逐馆官方连接器 + 纯配置)+ 懒生成接线。

**奥赛 = 样板馆**:作为先行者会多吞一两次重生成;流水线成型后,新馆从第一天即"配全·生成一次·封板"。

---

## 变更记录

- 2026-06-28:新建本活文档。纳入近期加法:端点3 `/objects` 分页;端点2 `categories` facet + language;端点4 `status/title/images/facts`;`content_status` 生命周期;上新馆路径。
- 2026-06-30:作者卡——content 增必选常驻 `artist` 卡(生卒P569/P570·国籍P27·代表作P800 from 作者实体 + artist段叙事为bio);artist 段移出 tabs。
- 2026-06-30:阶段2a 落地——生成从证据包取料(用上 P88/P180 富属性)+ guide 互知去重(模块各守 lane、不复述头条、返空不发布)+ overview 退役(迁移删 category_sections 映射)。
- 2026-06-29(晚):阶段1 证据包落地——`MuseumObject.evidence_pack`(facts/narrative/flagged);端点4 `facts` 策展+人性化(去学术噪音,provenance/exhibitions/bibliography 移出面板)。
- 2026-06-29:升级为**主文档**(契约+内容体系+上馆手册+路线图)。纳入端点4 `default_guide`(默认标准讲解);新增 §内容体系(三层+模块库+证据包+去重lane+动态模块)、§路线图(阶段1-4)、§北极星 + 工作纪律。
