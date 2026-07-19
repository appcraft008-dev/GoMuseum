# GoMuseum 博物馆主文档（API 契约 + 内容体系 + 上馆手册 + 路线图）

> **这是唯一权威主文档。** 所有博物馆按本文的契约与路线图上线;奥赛 = 样板馆。
> **工作纪律**:每次决策 / 发现的问题 / 零散需求 → **回写本文**。带日期的 `docs/superpowers/specs/*` = 设计记录,**喂给本文**;本文永远是当前真相。新馆只读本文即可快速上线。
> 端点前缀 `/api/v1`。**加法/前向兼容**——只增字段、不破老解析;破坏性变更走版本化端点。
> 最近更新:2026-07-03(契约-代码对齐:端点3 artist 落地 name_i18n;facts.medium 接证据包 P186;country_lang/sources 馆配置化)。

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
| `GET /search?q=&language=&limit=` | 全局搜索(探索页;跨馆藏品+博物馆) | `search/inprocess.py` |
| `GET /museums/{slug}/search?q=&language=&limit=` | 馆域搜索(馆列表页;只搜当前馆藏品) | `search/inprocess.py` |
| `GET /museums/{slug}/objects/{qid}/audio?language=&section=` | 懒 TTS(点播放才生成;返 `{audio_url}` R2 直链;生成中 409) | `endpoints/museums.py` |
| `GET /museums/{slug}/objects/{qid}/audio/stream?language=&section=` | 流式 TTS(✅2026-07-16 #256):首播边生成边播 | `endpoints/museums.py` |

**音频流式端点(加法,老 `/audio` 不动)**:`/audio/stream` 仅 guide/深度段(qa 连念/artist_bio v1 仍走 `/audio`)。⚠️ **同一个 200 有两种形状**——首播返 `audio/mpeg` chunked 字节流(单次 TTS tee:客户端边收边播 + detached 落库,断连也把整段落 R2,不重复付费);已落库返 JSON `{"audio_url"}` R2 直链。**前端必须按 Content-Type 分支**;409=同段他人正在生成(重试即缓存命中),404=该段文本未发布。流式响应无 Content-Length/不支持 Range。

`language` 取值 = `DEFAULT_LANGUAGES`(lang_config.py,唯一真相源;当前 7 语 en/fr/de/es/it/zh/pl)。缺省 `zh`。**加语言=加配置**:新语言按§多语显示名的"加语言 checklist"落配置即全端点生效,**本行不再随之改动**(引用真相源,非硬列举)。新内容全语生成;老内容缺语走懒翻译/`translate` 补。

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
  "description": "奥赛坐落在一座1900年的火车站里…(AI接地叙事,按language)",
  "cover_image": "<url|null>",
  "artworks": [
    {"qid": "Q334138", "title_zh": "世界的起源", "title_en": "L'Origine du monde",
     "artist_zh": "居斯塔夫·库尔贝", "artist_en": "Gustave Courbet",
     "year": "1866", "period_zh": null, "period_en": null,
     "image": "<url>", "popularity": 51}
  ]
}
```

- `description`(✅2026-07-18 spec museum-intro,加法):馆叙事介绍,AI 接地生成 `description_i18n[language]`,缺→en→任一→**null**。`cover_image`:得体性筛选后的封面 R2 直链(large 档,**可 null**)。前端 `as String?`,null 整块隐藏。老 App 不读不炸。

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

- `title` 按多语显示名规则:`title_i18n[lang]`(Wikidata权威)→ 该语言 legacy 列 → en 兜底。`artist` 同理经 name_i18n。
- `content_status`:**按请求语言解读**(2026-07-03 定)——对象有内容但该语言无已发布内容 → 返 `empty`(前端显"待完善",防"列表看着有、点进去空")。见末节生命周期。
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
- `artist`:**必选常驻作者卡**(不随空隐)。**数据来自 `artists` 一等实体**(按 artist QID 生成一次、同作者所有作品复用→一致/完整/省;artist 不再是 per-work 段)。`{name, birth, death, nationality, notable_works:[...], bio}`(**name/title 按多语显示名规则解析:i18n 权威→翻译→en**;bio 按语言取)——生卒年/国籍/代表作取自作者 Wikidata 实体(P569/P570/P27/P800);`bio`=artist 段已发布叙事(无则 null)。~~v1 局限~~ ✅2026-07-04 解除:`nationality`/`notable_works` 按 language 本地化(`nationality_i18n`/`notable_works_i18n`:P27/P800 多语权威标签→translate_name 兜底→en 列;生成与 names 回填两路都填,幂等)。
- `facts`:**已策展+人性化的墙签事实**(只 wall_label 级):`artist/date/medium/dimensions/inventory/location`。`medium` 优先证据包干净源(Wikidata P186,多值合并人性化),回退 Joconde `medium_fr`;`dimensions` 取 Joconde 串人性化(证据包暂不抓 P2048/P2049,非法国馆无 Joconde 时为 null)。⚠️ **`provenance` 返 null、`exhibitions`/`bibliography` 返 `[]`——已移出面板**(学术噪音;参考文献彻底不展示,收藏/展览史进证据包材料级,阶段2 由 background lane 讲成流转故事)。`artist_life` 暂 null。
- `suggested_questions`:好奇心问答(0-4 条)。
- 对象不属于该 slug / 不存在 → 404。

---

## `content_status` 生命周期

`stub`(只元数据,目录铺出) → `ready`(≥1 段已发布)/ `empty`(无可接地材料)。前端:`stub`/`empty` 显"待完善",`ready` 正常。未知值按 `ready` 容错。

**懒生成(✅2026-07-03 落地)**:content 端点命中 `stub` → 后台触发该件完整生成(全语言;**请求者语言排队首、逐语言翻完即落库**——用户最快看到自己的语言,单语言翻译失败不拖垮其他),几分钟后再取即 `ready`。

**首屏关键路径原则(✅2026-07-16 #257 定,TTFC 45.9s→~15s)**:懒生成语句顺序=**请求者首屏最短路径**——材料抓取(guide 的接地输入:对象/作者 wiki 提取 + artist_facts + 证据包,**必须在 guide 前**)→ guide(en) 落库 → **请求语言 guide 翻译立即落库(用户 ~15s 见主讲解)** → 其余全部延后(作者实体 bio/i18n、canonical 深度段、其余语言、QA)。**今后往管线加任何生成步骤,先问:在 guide 依赖链内吗?不在 → 一律放首屏之后**。纯重排:调用集/prompt 不变=质量与成本不变;每段 persist 即 commit=前端轮询立即可见。锁=内部 `attributes.lazy_lock_at`(TTL 10min 自愈),**不对外暴露中间状态**——stub 期间前端照旧"待完善",契约形状零变化、老 App 无感。`empty` 不重试(已判无可接地材料,防循环烧钱)。并发上限 2/进程;仅 staging/production 环境生效。

**`generation` 进度字段(✅2026-07-10 加法)**:content 端点返回 `generation: {published, expected}`——真实段落分数(expected=guide+该类目深度段;published=已发布的 guide+深度段)。前端显"N/M 段"诚实进度(**不做假百分比/时间进度条**:LLM 时间不可预测,假条会卡在90%伤信任)。配合 guide 先出流式,等待体验=主讲解先出+真实段落进度+计时预期。

**`generating` 字段(✅2026-07-04 加法)**:content 端点返回 `generating: bool`(信号源=懒任务锁)——true=懒生成/懒翻译进行中。前端三态:generating→"生成中"继续轮询;false+empty→"资料不足"停;false+stub 无内容→"待完善"+重试入口。老 App 不读则无感。

**懒翻译(✅2026-07-03 落地,懒生成姐妹场景)**:content 端点命中"对象 `ready`、有 en 轴心、但**请求语言**无已发布内容" → 后台**只翻这一门语言**(补语种原语:段落+问答+作者bio,数十秒、费用分钱级)。配合**列表 content_status 按请求语言解读**:该语言缺 → 列表即显"待完善",点开触发懒翻译,刷新即有——任何语言视图所见即所得,新加语言自动享受同样行为。同锁/并发/环境门。

## 图片字段（✅2026-07-03 R2 自存落地）

`image`(端点2)/`thumbnail`(端点3)→ **thumb 档**(480px);`images[].url`(端点4)→ **large 档**(1600px,兼识别参照)。`ObjectImage.image_key` 存**基础键**(`images/{qid}/{sort}`),端点拼 `_thumb.jpg`/`_large.jpg` 出 R2 直链;无 key 回退 `source_url`(Wikimedia)。字段名不变,前端零改。

- **多角度图**:catalog 收 P18 全部值 → 多行 ObjectImage(首张 `role=primary`,其余 `view`;雕塑识别参照)。Commons 分类(P373)深挖留给识别机制 brainstorm。
- **物化**:`onboard.py <slug> images --target <env> [--limit N]`——下载(合规UA限速)→Pillow两档(JPEG q82,不放大)→R2→Commons 署名(license/credit,CC-BY 摄影必署)。逐行幂等,失败留空重跑重试;SVG/超60MB 跳过。不存原图(source_url 可重下)。
- **懒补漏**:content 端点发现该件缺图 → 后台补单件(自愈运维疏漏/新进目录;不占内容锁)。
- **⚠️ 成本分界(通用原则)**:**图=目录门面必须预物化**(列表一屏几十张缩略图多数永不被点开;识别参照库必须先于识别存在;成本≈0)——与**内容=必须懒生成**($/件)相反。新馆照此:catalog→names→images 全量预跑,generate 分层。

---

## 收录策略（通用规则,任何馆 0 代码复制;2026-07-03 定）

**① 分层收录(2026-07-13 取代"有图才收录"硬规则;版权边界语义不变)。** 三层：
**视觉可识别层**(有自由版权图 P18/Wikimedia——图仍是识别参照物+合规边界,官方 RMN 类版权图照旧不碰)→向量识别+列表展示全功能；**文字可识别层**(有 Wikidata 条目无图,catalog P18 已 OPTIONAL 收全条目)→墙签 OCR/馆藏号/搜索命中,讲解懒生成照常,**列表与分类计数不出现**(浏览面密度优先),馆页双数字揭示规模;**需求层**(无条目)→unrecognized+记需求。无图件讲解页 hero=识别路径用用户自己照片(会话内回显)/搜索路径类目占位图。

**② 三层口径与北极星 KPI(2026-07-13 验收换轴)。** 口径:官方全馆藏(奥赛~15万) ≫ **常设在展(3-4千,真实分母)** > Wikidata 条目(5353=档案层) > 有图(~2065=图录层)。**上新馆验收不看导入件数,看"现场识别成功率"**——用户实拍一件眼前藏品被正确识别的概率(recognition_events 聚合:(match+确认候选)/尝试)。**KPI 归因口径(2026-07-13 实测修正)**:App 主入口是全局识别端点(事件 museum_slug 为空),按**命中对象的归属馆**归因;全局且未命中(top_qid 也空)的事件无法归馆、不计入任何馆的分子分母(诚实局限,不引入方向性偏差)。`onboard coverage-report` 是配方最后一步:输出分层数字/展陈分布/KPI 并回写 museums.stats(馆页双数字数据源)。

**③ 定期重跑 catalog 吃增量 + 展陈状态动态化(2026-07-13)。** Wikimedia 持续增长,catalog 幂等重跑收新;**展陈状态绝不做静态布尔**——`attributes.display`={status(CONFIRMED_ON_DISPLAY/LIKELY_ON_DISPLAY/TEMPORARY_EXHIBITION 预留/NOT_ON_DISPLAY/UNKNOWN), evidence[], confidence, verified_at},证据源按普适性三层:**自家识别流量(最强,零适配器,近30天确认识别→CONFIRMED)** > Wikidata P276(稀疏先验→LIKELY) > 区域适配器(可选增强;样板=Joconde 开放API,reference=P347,localisation 为保管馆级,覆盖全法博物馆)。报告 CLI 触发重算,不做实时。

**④ 通用分类法(全馆共用 8 大类 + unknown 兜底)。** `CATEGORY_BY_QID`(category_config.py)是唯一真相源:P31 QID → 类目;**加类型=加一行映射 + 馆 yaml `categories` 选用,零代码**。多 P31 作品已知类目优先于 unknown。每类目一套深度模块段落集(SECTIONS_BY_CATEGORY;未细化的类用通用兜底,真上馆再细化)。

| 类目 code | zh | 归并(示例) | 段落集 |
|---|---|---|---|
| painting | 绘画 | 油画/壁画 | 专属 |
| sculpture | 雕塑 | 雕塑/雕像/半身像/小像 | 专属(材质工艺) |
| works_on_paper | 纸上作品 | 素描/水彩/色粉/版画/习作/草图 | 同绘画 |
| photography | 摄影 | 照片 | 专属(摄影师) |
| decorative_arts | 装饰艺术 | 家具/陶瓷/玻璃/金工 | 专属(maker/用途) |
| textile | 纺织 | 挂毯/服饰 | 兜底 |
| artifact | 文物器物 | 考古/礼器/武器 | 兜底 |
| manuscript | 手稿古籍 | 手抄本/书籍 | 兜底 |

**⑤ 内容生成分层(目录便宜、生成贵;2026-07-05 定 N 默认=0)。** 目录+显示名+图物化全量做(全馆 ~$20 内,零 LLM 成本);**讲解内容默认不批量预生成(N=0),完全靠懒生成/懒翻译按需兜底**——上新馆零内容预付,用户点开哪件才生成那件(请求语言优先,~2-3 分钟)。上线运营后按**实际热度/需求**由运营决定某馆 top-N 值再 `generate --limit N` 批量富化(热门件零等待)。**全量目录/图只在 prod 跑;staging 只做小样本验证机制**(`catalog --limit`)。

**⑥ staging 轻量化(2026-07-17 定,spec 2026-07-17-staging-lightweight)。** staging=机制验证平台,**永不为数据规模付 LLM 费**:机制验证用小样本(护栏强制——onboard names/generate/translate 在 staging 默认 limit=50,rescan 系需显式 `--allow-full`);规模数据一律从 prod 搬运(`sync_staging_from_prod.py`,slim=金样本 ~300-500 件/full=发版前拉真;内容是 prod 已付费资产,共 R2 桶 key 复制即解析,零 LLM);**用户表(users/benefits/devices)与 recognition_events 永不跨环境**。上新馆同理:staging 只跑 `catalog --limit` 验证配方,全量只在 prod。

## 上新馆 = 纯配置(零核心改动)

连接器已存在时(Wikidata 全球通用),上新馆只需:

1. **`backend/museums.yaml` 加一条**:
   ```yaml
   <slug>:
     name_zh / name_en / city_zh / city_en / country
     wikidata_qid: Q...        # 馆的 Wikidata 实体(P195 收藏于)
     category_filter: Q3305213 # 主类目 QID
     categories: [Q3305213, ...]
     country_lang: fr          # 馆所在国语言(取该语维基;作者材料同用)
     sources: [joconde, wikipedia]  # 每馆补充源;缺省 [wikipedia]。Wikidata 是脊柱不在此列
     fetch_limit / sample_size / sample_qids
     languages: []             # 空=用 DEFAULT_LANGUAGES;或指定子集
   ```
2. **铺目录**:`python scripts/onboard.py <slug> catalog --target <staging|prod> [--limit N]`
   → `WikidataCatalog.list` 列 stub(只收有图,§收录策略)→ `merge_stubs` 去重 → `load_stubs` 落库(`content_status=stub`,元数据+路由 external_ids/wiki_titles)。新类目先跑一次 `scripts/seed_sections.py`(幂等)。
3. **回填显示名**:`python scripts/onboard.py <slug> names --target <env>`
   → 全馆 `title_i18n` + `artist_qid`(P170 批量)+ Artist 名字行(权威标签→翻译→en;幂等)。stub 即有完整多语显示名。
4. **物化图片**:`python scripts/onboard.py <slug> images --target <env>`
   → 全馆缺图行下载→两档→R2→署名(幂等;见§图片字段)。
5. **生成内容**:`python scripts/onboard.py <slug> generate --target <env> [--qid Q..|--limit N] [--langs zh,en,fr]`
   → 逐件:stub 抓材料(Wikipedia/Joconde)→ 生成 → 接地闸 → 翻译 → 落库 → `ready`/`empty`。
6. 端点自动产出上述四个契约;前端零改接入。

**非 Wikidata 主源的馆**(如美国 Met):一次性写个 `CatalogSource` 连接器(同插件模式,核心零改),其余同上。

`--target` 必须匹配容器 `ENVIRONMENT`(守卫防误灌)。全量富化在 prod 跑(staging 仅样本验证机制)。

> **⚠️ 批处理纪律(2026-07-03 定,prod 三次崩溃换来;适用于全部上馆命令 catalog/names/images/translate/generate 及未来新批任务):**
> 1. **单件/单批失败跳过继续**——错误计数(`errors`)不炸全局(教训:一次 Wikidata ReadTimeout 炸死整馆 names);
> 2. **分批落盘**——每 N 件 commit(names 50/images 25),崩溃/重部署不丢进度(教训:253 件进度全丢);
> 3. **批量外部查询必须分批 + 瞬时错误重试**——VALUES 有 URL 上限(教训:1300 QID 单条查询 HTTP 414);5xx 重试一次仍败跳批(教训:Wikidata 502);
> 4. **一切批任务幂等可重跑**——重跑只补缺,断点即续传。新写批任务时按此四条自查。
> 5. **空响应≠数据到底,必须重试后再判**(2026-07-11 添)——WDQS 深 OFFSET+ORDER BY 超时会返回
>    HTTP 200 的**空结果**,把空页当"翻完了"会**静默缺件**(教训:orsay catalog 两次截断 1537/1517,
>    漏收 500+ 长尾件含用户实拍的库尔贝《鹿斗》)。翻页循环连续空 N 次才允许 break;
>    上新馆跑完 catalog 核对 loaded 数与该馆 Wikidata 有图量级是否相符。
> 6. **容器内长任务:避开部署窗口 + 脱会话 + 日志必须实时落地**(2026-07-16 添)——后端容器随每次
>    staging/prod 部署 **recreate,里面的批任务被无声杀死**;起长任务前确认无部署在途/等部署落定再起。
>    启动用 `docker exec -d` + `setsid`(SSH 断连不死);日志逐行 flush 到文件(教训:staging Joconde
>    补名首跑中途死、日志 0 字节,**死因无法回溯**;重建带日志脚本后 1038 件零失败跑完)。
>    "监控到进程消失"≠"任务成功"——收尾判断只认日志 DONE 行 + 数据核验(纪律 4 幂等保证随时续跑)。

---

## 内容体系（三层 + 模块库 + 证据包）

> **⚠️ 英语轴心（en axis）——核心生成约定,所有生成内容必守。**
> 一切内容(讲解 / 深度模块 / 问答 / 作者 bio)**先用英语生成**(prompt 必须含 "Write in English")→ 三类**接地闸在英语上判** → 再 `translate_object` 翻成 zh/fr/…(各自忠实度校验)。
> **为什么**:接地/事实校验只在英语做一遍,其它语言靠忠实翻译继承 → 省、且跨语言一致。
> **教训(2026-07-02)**:新加 `generate_artist_bio` 时漏了 "Write in English",作者 bio 随材料语言乱输出(en 条存成中/法文),切语言不对。**新增任何生成 prompt 都要强制英文。**

> **⚠️ 多语显示名规则(title / artist.name)——语言无关,核心约定。**
> 任何**显示名**(藏品标题、作者名)按请求语言解析,走固定回退链:
> **① 该语言的权威标签**(Wikidata 多语 labels / 馆方官方标签,专有名词最优)→ **② 从英语轴心机器翻译**(该语言无权威标签时兜底)→ **③ 英语轴心原名**(永不空)。
> **语言无关**:新增语言(de/es/it…)**只加进 `DEFAULT_LANGUAGES` 语言集**,生成时一次性抓该实体全部目标语言的 Wikidata labels、缺的从 en 翻译 —— **同一套机制、零 per-language 代码**。这就是"加语言=加配置"。
> **配套**:**QID 是全系统匹配键**(识别/查询/去重/跳转都用 qid);显示名纯展示,名字回退绝不影响匹配。避开脏格式(如 Joconde 的 "Lastname First (dates)")。
> **非 Wikidata 条目的身份(✅2026-07-16 #255 定)**:无 Wikidata 条目的件,qid 位=**合成把手 `<source>-<reference>`**(如 `joconde-000SC010033`)——对外稳定、全系统当 qid 同键用(识别/搜索/跳转零分叉);内部检索按 UUID 回查。`is_wikidata_qid()`(Q+数字)做门控:合成把手**跳过一切 Wikidata SPARQL**(省成本+避免 `wd:<合成号>` 垃圾查询)。**names 配方**:这类件无权威标签可抓 → 直接走显示名规则②(title_en 轴心纯翻译,staging 实证 1038 件×10 语零失败);**无 title_en 则无轴心 → 留空不硬造**(宁缺毋滥)。上新馆接任何非 Wikidata 源(区域目录/官方馆藏库)照此,零核心改动。
> **解析时机 = 铺目录时(2026-07-03 定)**:显示名是**目录元数据、不是生成内容**——catalog 后立即跑 `onboard.py <slug> names --target <env>`(幂等可重跑),全馆补齐 `title_i18n`/`artist_qid`/Artist 名字行;stub 一进目录就有完整多语显示名,**不等内容生成**(此前只在 generate 时填,导致列表页大量 stub 在 zh 视图显英/法文名)。generate 时同一机制增量修补。en 也权威优先(纠正目录把非英文标签误存 title_en,如 "Régates à Argenteuil")。

> **⚠️ 本地化完整性原则(2026-07-03 定,分类标签教训)。**
> - **凡端点返回的用户可见文本必须随 `language` 本地化**:内容类走生成/翻译管线;**固定小集合**(分类标签/段落标签/材质名/`all` tab 等)用**静态翻译表一次配齐全部 `DEFAULT_LANGUAGES`**——不许只配部分语言(三语时代的表在六语开放后成洞)。缺译回退 en、**永不 null**。
> - **机器码字段永不翻译**:`code`/`qid`/`section_code` 是前端逻辑键(筛选/路由/匹配),显示一律靠 `label`——由此所有文案改进都是 server-driven、免发版。
> - **"加语言" checklist(加语言=加配置的完整清单)**:① `DEFAULT_LANGUAGES`+`LANG_NAMES`(lang_config)② 静态标签表(`_CATEGORY_LABELS`/`_ALL_LABEL`/`SECTION_LABELS`)③ 非拉丁文字语言扩 `_clean_i18n` 文字检测(现查 zh/zh-hant 汉字)④ 前端 ARB 文案+语言选择器(kSupportedLocales)⑤ 存量回补:显示名跑 `names`(幂等),讲解/问答跑 **`onboard.py <slug> translate --target <env> --langs <新语>`**(✅已实现:从已存 en 段**纯翻译**落库,忠实度校验继承接地,不重生成;幂等只补缺)。
>   **⑥ 仅字形变体语言**(如 zh-hant——同一语言不同字形、可 OpenCC 逐字确定性转换):额外在 `material._SCRIPT_VARIANTS` 加一行 `(标签变体优先序, OpenCC 方向)`;前端注意繁体 API 参数发 `zh-hant` 非 `zh`(见 handoff 4 陷阱)。**独立语言不适用**——即便相似如加泰罗尼亚/葡萄牙语,词汇不同、不能逐字转,走普通翻译路径(①–⑤)即可。判据:两形式间有无"确定性逐字保词转换"。
>   **⑦ 加完必跑质量验收(强制,非拉丁语言尤其)**:按 `docs/i18n-translation-quality-checklist.md` 跑**完整**六检查点——**扫全部已发布段**(guide+深度模块+QA,不只 guide),核残片/标题多通路一致/显示名质量/忠实度/字形。残片命中要分辨专有名词语境(机构官方名=误报)。教训:2026-07-06 只跑子集漏了 zh-hant 深度模块残片,用户审计才发现。**加语言不验收 = 没加完。**
> 教训:2026-07-03 六语开放,分类标签表只配了 zh/en/fr → de/es/it 真机标签栏中英混杂(前端交接件修复,#142)。
> - **加非拉丁语言(ja/ko/zh-hant)前跑翻译质量验收**:见 `docs/i18n-translation-quality-checklist.md`(六检查点:残片/专名一致/标题多通路一致/显示名质量/忠实度/字形;全语言无关机制)。
> - **语言一致性(2026-07-10 定,核心差异点)**:所有用户可见文本(讲解/深度/问答/作者bio/藏品简介)在语言 X 下必须真的是语言 X,**零混杂**。经语言一致性闸(`lang_detect.text_in_language`:非拉丁按目标字形占比、拉丁用 lingua 识别)校验;不符→gpt-4o 重译→仍不符 `needs_review` 不发布(宁缺毋滥)。**语言无关**:检测候选集派生自 `DEFAULT_LANGUAGES`,加语言自动覆盖。取代此前查中/法语的打地鼠补丁。加语言必过质量清单的语言一致性检查点。
> - **显示名真相唯一化——标题+作者名(2026-07-05 定标题;2026-07-17 #277 扩作者名)**:显示名是正文称呼的**唯一真相源**——藏品标题=`title_i18n[lang]`,**作者名=`artists.name_i18n[lang]`**。所有内容通路(讲解 guide / 深度模块 / 建议问答)在正文里引用本作品标题或称呼作者时**必须跟随显示名**——翻译时把两者作为 glossary 注入(`translate_object(titles=, artists=)` / `suggest(titles=, artists=)` / `translate_qa_items(title=, artist=)`)。否则各通路独立翻译会分叉:标题如"显现/幻影";**作者名凡目标语言有多个通行音译即分叉**(真机实证:正文"修拉" vs 作者卡"秀拉",同为 Seurat;高危:Renoir/Toulouse-Lautrec/Courbet 等,音译型语言 zh/zh-hant/ja/ko 均有风险)。en 轴心天然一致(材料带 `Artist: artist_en`)。引用**其他**作品/作者不受此约束(各用各的真相)。**存量修复工具**:`scripts/rescan_artist_names.py`(en 段提作者姓而译文不含规范名姓段→删段带 glossary 重译,音频随段失效;幂等)——上新馆后或发现分叉时可跑。
> - **翻译质量规则必须语言无关(2026-07-05 定)**:改进翻译质量(如"全部译出、不留源语言残片")一律靠 `{lang}` 占位符 / 忠实度闸的失败信号,**绝不硬编语言名单**(如"难句 zh 用 gpt-4o")。否则每加一种与英语高距离的语言(zh/ja/ko/zh-hant)都要重打补丁。教训:gpt-4o-mini 对 zh 稳定漏翻"severed head"类短语(距离近的欧洲语言靠同源词"照抄"绕过),按语言无关规则修则 ja/ko 上线自动受益(#197)。

> **⚠️ 完整性判断按语言维度(2026-07-03 定,一日三错的统摄原则)。**
> 凡是"内容是否已存在"的判断(跳过生成/跳过翻译/显示状态/静态表取值),一律问"**该语言**是否已存在",**绝不问"对象是否已存在"**。同一根子当天犯三次:
> ① 列表 `content_status` 按对象判 → de 视图显 ready 点开空(#146 修:按请求语言判);
> ② 作者 bio "存在即跳过" → 复用老作者时新语言永远补不上(#147 修:生成时语种补齐);
> ③ 静态标签表只配部分语言(#142 修:一次配齐全语种)。
> **推论——复用≠跳过**:任何"生成一次、全馆复用"的实体(作者 bio/显示名/将来的流派介绍等),**每个复用点必须做语种补齐**——en 轴心在、目标语言缺 → 纯翻译补(幂等,已有语种不动)。新馆复制时:凡新增"共享实体"或"存在性检查",按此自查。

**博物馆负责事实,AI 负责讲法。** 每件内容分三层,各守互斥职责,从同一份证据包生成、不重复:

- **第一层 默认标准讲解**(`default_guide`,已上 stage1):识别后首先呈现的"主角",单主线·5拍(钩子→引导观察→为什么重要→必要背景→记忆点)·按热度分档(普通 270-420 / 重点 420-675 中文字)。~1 分钟看懂。
- **第二层 预设常见问题**(`suggested_questions`):3-6 个,讲后推荐 2-3,补头条/模块**没答**的。
- **第三层 AI 自由问答**(`/ask`,规划):多轮,复用证据包,争议必 hedge。

**模块库(`tabs`,深度内容,降级为"更多内容")** —— 各守互斥 lane,**只补默认讲解没深挖的一面**:

| 模块 | 专属职责 | 不讲(交给谁) |
|---|---|---|
| artist | 作者其人(生平/性格/艺术史地位) | 不讲这幅画的丑闻/技法 |
| background | 作品史实链**事件**(何时/谁委托/在哪展/风波/流转) | 不讲"为什么重要"(→significance)、怎么看(→analysis) |
| analysis | **怎么画的(技法:笔触/光色/构图结构)** | 不复述解说已点的符号/题材(那是看什么) |
| significance | 影响与遗产(改变了什么/影响了谁) | 不复述丑闻事件(那是 background) |
| facts | 一个别处没有的趣闻 | 不与上面重复 |

**关键机制(✅阶段2a 已落地)**:① 先生成默认讲解(头条)→ 模块单调用带头条+证据包富属性+锐化 lane"各守职责、深化非复述、只会重复就返空"(生成已从证据包取料)→ 问答最后只补缝。② **动态显示**:空模块不展示(料薄优雅降级,默认讲解是地板)。**深度模块字数按热度分档**(重点件 ×1.5),名作能深则深、薄件天然短;深=用材料具体细节铺开非注水(接地闸+去重兜底)。③ overview 退役(与默认讲解头条重复)。

**证据包(`MuseumObject.evidence_pack`,内容唯一来源)**:每件生成时组装、落库(JSONB,后台中间产物,不进端点契约)。结构 `{facts:[{claim,value,source,topic,tier}], narrative:[{text,source,type}], flagged:[{text,type,source}]}`:
- `facts` = 结构原子(对象字段 + Joconde + Wikidata 富属性 P88/P180/P186/P135… + **关系属性 P4969衍生/P144基于/P941启发/P361系列**→喂 significance/background),`tier`=`wall_label`(进 facts 面板)/`material`(只喂生成),`topic`=lane 提示。
- `narrative` = Wikipedia 作品/作者全文块,标 `mainstream`。
- `flagged` = LLM 抽出的争议/推测/未证实句(`contested/inference/unverified`,供阶段2 hedge)。
- **阶段1 已落地(`build_evidence_pack`)**:富属性按 registry 门控(真实生成走网络);阶段2 才把三层+模块生成切到证据包。Europeana 暂缓(待 key)。

## 识别（拍照→讲解;✅P1 2026-07-03;✅向量引擎+全局端点 2026-07-11）

**原则（通用,任何馆零代码）:**
- **R1 识别接地第一原则**:AI 视觉输出是**查询不是答案**——候选名必须匹配到真实目录记录才展示身份;不中就诚实"未收录",绝不把模型猜测当事实。(向量检索天然接地:命中的就是目录参考图。)
- **R2 墙签 OCR=权威接地源,但是增强不是依赖**:照片常无签是常态,主路靠画面内容;"引导补拍说明牌"是未收录 UX 的组成部分(`mode=label` 纯转写)。墙签行同时做**馆藏号精确匹配**(归一化后≥3位,编号=馆方主键,命中即满分)。
- **R3 三档呈现**:高置信(≥HIGH)直开讲解页 / 中置信确认卡(1-3 候选带缩略图) / 低置信未收录+引导拍签。**确认卡=免费人工标注**(真实照片→确认QID,数据飞轮)。**GPT 兜底链命中一律走确认卡不直判(同名撞车实证:自画像/The Bathers 精确同名撞他馆无关件),直开讲解页只来自向量高置信(像素证据)。**
- **R4 引擎可替换,匹配/接地层是不变核心——✅已兑现**:主引擎=DINOv2 ViT-S/14 向量检索(参考图库余弦近邻;benchmark 非名作 Top-1 95.8%/库外零误接受,见 2026-07-11 bench spec);GPT-4o-mini+墙签 OCR 降级为**兜底**(无参考图/低分件;调用量从每张必调降为仅 miss)。引擎任何不可用形态(模型缺失/坏图/表空)→ 自动走兜底,绝不 500。
- **R5 需求自适应**:未收录拍摄记 `recognition_demands`(按 馆+感知哈希 幂等计数,全局识别时馆可空;墙签文字=高质量需求) → 目录跟真实需求生长。
- **R6 足迹 vs 归属两轴分离**:到访足迹用物理位置(GPS/App 选馆),绝不用识别到藏品的拥有馆(借展场景两轴背离)。后续落地,原则先立。

**端点(两个,响应同形):**
- `POST /api/v1/recognize`(**2026-07-11 新增,App 主入口**):multipart `image` + query `museum`(slug,**可选**) + `language` + `mode`。不传 `museum` = 全局识别(拍前无需选馆——导航栏识别按钮直达相机);传了 = 只搜该馆。
- `POST /museums/{slug}/recognize`(保留,行为不变):馆域内匹配。**⚠️ 馆域调用不做全局回退**(2026-07-11 裁决:老 App 不读 `museum` 字段,跨馆命中会拿他馆 qid 撞详情 404 死胡同——前向兼容;将来带馆提示要"馆内优先+全局回退"时加显式参数再开)。

响应:`{outcome: match|candidates|unrecognized, match:{qid,title,artist,thumbnail,confidence,museum}, candidates:[{…,score,museum}], label_text, reason, phash}`
——**`phash`(2026-07-13 加法字段)**=该次识别的感知哈希,配套 **`POST /api/v1/recognize/confirm`**(`{"phash","qid"}`,永远204,fire-and-forget):确认卡点选时上报,回填 recognition_events.confirmed_qid——**确认卡=标注飞轮**从此有服务端落点(KPI 的 hits=match+确认候选;match 直跳不上报,confirmed 语义=用户确认)。识别每次调用落 `recognition_events`(只存 phash 不存照片;engine 记 vector/vector_crops/text/cache)——**KPI 与展陈证据一表两吃**。museum pack 加法字段 `catalog_count`/`archive_count`(馆页双数字"在线图录N·档案M",数据源=museums.stats,coverage-report 回写)。
——**`museum`=归属馆 slug(2026-07-11 加法字段)**,前端跳详情用它(老 App 不读不炸;新前端解析 `as String?` + 回退)。`outcome/reason` 机器码不译;`title/artist` 按 language 走显示名规则;thumbnail=thumb 档。命中跳详情 → 懒生成/懒翻译/懒补图自动接管。同图重复识别走 Redis 缓存(命中 30 天/未收录 1 天;键空间 `recog3`)。**阈值 server-driven**:向量档 `RECOG_HIGH=0.85`/`RECOG_LOW=0.72`(环境变量,由 benchmark 校准,库外零误接受);文字兜底档沿用 HIGH=0.85/LOW=0.5。

**低分自动多裁剪重查(2026-07-11)**:全图向量分 < LOW 时(即原本注定失败的照片)自动裁 中心60%/35%+四象限+左右半幅 批量重查取最大分,再不中才进 GPT 兜底。**正常近拍照片走快路径零延迟影响**;触发裁剪的照片 +~2s,仍快于其下一站 GPT(2-5s)。已知代价(bench 实测):库外照片经多裁剪误出候选卡比例升高(48%→81%)——确认卡"都不是"出口兜底,可接受。

**⚠️ 识别优化的优先级原则(2026-07-12 定,真实用户测试得出)**:**App 用户是"有意图取景"的**——想识别某件作品的人会主动找能看清整幅作品的角度,拍歪了自己重拍;合影/极偏构图不是主流场景。Commons 随手拍照片测出的失败案例会高估怪构图的真实占比。**故:不再对怪构图做裁剪/阈值工程加码**(已合并的多裁剪留作免费保险丝);识别精度投入主线=**二维靠参考图覆盖,三维靠多视角图库**(建设策略并入藏品覆盖率机制,另立 spec)。

**识别参照库(与目录共生)**:参考图入库(物化)即嵌入(DINOv2 向量落 `object_embeddings`,生成一次永久落库,model 字段版本化);存量用 backfill CLI。**雕塑多视角**:Commons 分类(P373)拉他人照片入 `role=view`(≤4张/件,Special:FilePath 规范 URL 保署名链),物化即嵌入——3D 单视角是 benchmark 实测短板(真实照 Top-1 ~33%)的对症药。**view 自动治理(2026-07-13 落地,纯自动无人审)**:Commons 分类混入非本体图(orsay 实测 14%)的清洗策略——view 与该件正面照相似度 **<0.25 自动删**(实测全为垃圾)/**0.25-0.4 隔离**(`role=view_quarantine`:留档、不进索引、不上图集、不计有图)/**≥0.4 入索引**;物化嵌入钩子同规则前置闸(新图入库即治理);错杀极端角度由照片飞轮(Phase 3)补回。**上新馆配方(2026-07-13 全串)**:`catalog`(含无图条目)→`names`(⚠️ 首次收全条目时为数千件×10语回填,Wikidata 限速下**约数小时级**——须在服务器侧 nohup 脱管跑,orsay 实测 4800 件≈8h;增量重跑只处理新件,分钟级)→`images`→`backfill_embeddings`→`onboard views`+`images`→`vet_view_images`(执行)→`display-evidence --museum <slug>`(区域适配器,可选)→**`intro`(馆介绍+封面)**→**`coverage-report`(收官:分层数字/展陈分布/KPI,回写 stats)**。
> **馆介绍=门面类预生成内容(2026-07-18 定,spec museum-intro)**:同"图=门面必须预物化"侧(馆页高频入口,总成本封顶=馆数×几分钱),不走懒生成。`onboard <slug> intro` 幂等**按语言维度补缺**(en 轴心在→只翻缺语;加语言重跑自动补),gate 不过=该语言不落(无 needs_review;宁缺毋滥),语言集 `resolve_languages(cfg.languages)` 馆配置驱动。**封面=后端 LLM 得体性筛选**(server-driven:选错改后端即生效免 Play 审核;top-N 有图件逐件纯文本判定,古典/宗教/神话裸体=艺术惯例可,写实露骨性描绘如《世界的起源》否决)。**绝不碰开放时间/票价**(易变运营数据,AI 不脏补;也保零代码上新馆)。
**计费(2026-07-04 定)**:`match/candidates` 扣 1 次配额;`unrecognized` 不扣(不为失败付费);缓存命中不扣;配额用尽 → **402** `{reason: quota_exceeded}`(先于 GPT 调用,不烧钱)。身份=Bearer 令牌(App 自带)或 `device_id` 参数;两者皆无 → 401 `{reason: identity_required}`。服务端扣费,不再依赖前端自觉调 `/payment/consume`。

**老端点 `/api/v1/recognition` 标记 deprecated**(裸 GPT 猜测当事实,违反 R1;留给老 App,新 App 一律走新端点)。

## 搜索（打字查找;✅2026-07-13;稳定契约+可替换引擎）

识别的姊妹功能,也是**文字可识别层无图 stub 的主可达路径**(与浏览列表隐藏无图件相反——搜索是无图件主入口)。**打字搜索 ≠ 识别匹配**:识别是整串模糊相似(GPT/向量给完整候选),搜索是子串/前缀/分词命中(用户打"梵高"/"moulin"/"RF1668");搜索匹配独立设计,仅复用 matcher 归一化工具。

**两端点(加法,响应同族)**:
- `GET /api/v1/search?q=&language=&limit=20`——全局(探索页),响应含 `museums`+`objects` 两段。
- `GET /api/v1/museums/{slug}/search?q=&language=&limit=20`——馆域(馆列表页),只有 `objects`;馆不存在 404。

响应:`{query, museums:[{slug,name,city}](仅全局), objects:[{qid,title,artist,year,thumbnail,museum,has_image}]}`。`title/artist` 走既有显示名规则(`_resolve_name`,全语种);**无图 stub 照常在 `objects`(`has_image:false`,`thumbnail:null`),前端类目占位图**;`museum`=归属馆 slug(点击跳讲解页,与识别 match 同款导航);空 `q`/无结果 → 诚实空态 `objects:[]`。全语种搜(藏品 `title_i18n`+作者 `name_i18n` 全语种进索引,中文界面打 Van Gogh 也中)。

**稳定契约 + 可替换引擎**(照搬识别架构):用户可感知行为由契约锁定、跨引擎不变;引擎可插拔。**首发=进程内索引**(`search/inprocess.py`,单一真相源=Postgres、零同步,馆域索引 TTL 600s 缓存;三路匹配:编号精确 1.0>标题前缀 0.8>标题子串 0.6>作者子串 0.4,同分按 popularity)。**规模触发换引擎**(藏品越过 ~5-10 万件/卢浮+蓬皮杜级别,或实测延迟退化)→ 自托管 Meilisearch/Typesense(CJK 分词好、百万级即时);换引擎只换 `search()` 实现,**契约与前端零改**,唯排序权重可微差、"能搜到什么"一致。

**识别未收录→搜索闭环**:相机识别兜底的「展签检索」sheet 即全局即时搜索,命中点选→讲解页(识别与搜索兜底互通)。

## 路线图（执行顺序;每阶段 = 独立 spec→plan→实现,完成回写本文）

**✅ 已落地**:目录主干 + 4 端点契约 + 分类 facet + 作品信息 facts;接地·引人入胜生成 + 三类闸 + 多语翻译 + 建议问答;默认讲解 stage1(staging)。

- **阶段 1 — 材料地基(证据包)**:1a 源配全(Europeana + 更全 Wikidata P 属性;法国官方=Joconde 已有,非法国馆逐馆官方连接器)· 1b 证据包模型 + 分类落库。→ 每件一份完整分类证据包。
- **阶段 2 — 内容生成重构**:2a 统一分工去重(lane)+ 全从证据包生成 · 2b 动态模块 + 争议 hedge · 2c 两段式质量评估(事实质量 + 讲解质量)。
- **阶段 3 — 体验补全**:3a AI 自由问答 `/ask`(多轮)· 3b TTS 音频落库 · ~~3c 懒生成接线~~(✅落地)· ~~藏品识别 P1~~(✅2026-07-03 落地,见§识别;P2=CLIP 前置+需求聚合+足迹)。前端增强(生成中提示/自动刷新/识别相机流程)见交接文档。
- **阶段 4 — 规模化**:图像 R2 自存 + `cover_url` + 首页真实化 · 上新馆(逐馆官方连接器 + 纯配置)· **官方馆藏库连接器**(抓元数据+在展清单/展厅号,不抓图;用"在展×有自由图"校准优先级,修正名作偏置)。

**奥赛 = 样板馆**:作为先行者会多吞一两次重生成;流水线成型后,新馆从第一天即"配全·生成一次·封板"。

---

## 变更记录

- 2026-07-19:**第二家馆橘园落地——"零代码上新馆"实证成立**(spec orangerie-onboarding)。全程唯一改动=museums.yaml 一个条目;配方全链(catalog×2→names→images→物化即嵌入→intro→coverage-report)原样跑通:档案140/图录15/向量16;封面得体性筛选一次到位(卢梭《婚礼派对》);探索页/搜索/懒讲解(zh 18s)全自动可用。**实测上馆成本基准(llm_usage 首份完整账单):全馆 ~$0.60,其中 names(gpt-4o)$0.59=98%**——坐实成本工程②(Batch API 砍 names)是唯一值得的刀。Joconde 馆名须用 POP 精确官方名(橘园="musée de l'Orangerie des Tuileries")。

- 2026-07-18:**博物馆介绍+封面落地**(spec museum-intro)。馆包加法字段 `description`(AI 接地叙事,按语言回退,null 安全)/`cover_image`(得体性筛选封面,可 null);`onboard intro` 命令(复用富化管线,按语言维度幂等补缺,gate 不过不落);封面=后端 LLM 得体性判定(《世界的起源》类否决,server-driven 免 Play 审核);上新馆配方加 intro 步。迁移 q1n3。门面类预生成(成本分界),不碰运营数据。

- 2026-07-17:**staging 轻量化落地**(收录⑥)——护栏(staging 默认小样本/--allow-full)+ prod→staging 搬运两档(slim 金样本/full 拉真)+ 用户表红线。背景:staging 已成 prod 近镜像,十万件×10语全量回填≈百万级强模型调用不可持续。
- 2026-07-17:**显示名真相唯一化扩到作者名**(#277)——`artists.name_i18n[lang]` 成为正文/问答称呼作者的唯一真相源,glossary 与标题双锁(`translate_object(titles=, artists=)`);修机制级音译分叉(修拉/秀拉)。存量工具 `rescan_artist_names.py`(staging 实跑:92 段+51 问答分叉修复)。原则语言无关、作者无关——新馆多音译作者自动受保护。
- 2026-07-16:**#252-257 批次回写**。API 面加法:`/audio`(懒 TTS)与 `/audio/stream`(流式,单次 tee,⚠️200 双形状按 Content-Type 分支)入端点总览。原则×2:**首屏关键路径原则**(懒生成顺序=请求者最短路径,新增生成步骤不在 guide 依赖链内一律延后;TTFC 45.9s→~15s)、**非 Wikidata 条目身份**(合成把手 `<source>-<ref>` 当 qid 同键用+`is_wikidata_qid` 门控跳 SPARQL+names 走 title_en 轴心)。批处理纪律第 6 条:容器内长任务避开部署窗口+脱会话+日志实时落地("进程消失≠成功",只认 DONE 行+数据核验)。
- 2026-07-13:**搜索功能落地**(spec 2026-07-13-search-feature-design)。API 面加法:`GET /search`(全局,museums+objects 两段)+`GET /museums/{slug}/search`(馆域,仅 objects);无图 stub 可搜(has_image/thumbnail:null)、全语种、三路匹配。原则:**搜索=稳定契约+可替换引擎,进程内起步(零同步)→规模触发换 Meilisearch,契约与前端零改**。前端:探索页升级全局搜(debounce 300ms 分区结果)+馆列表页激活馆内搜+识别未收录→搜索闭环。
- 2026-07-06:加语言 checklist 补⑥字形变体(_SCRIPT_VARIANTS)+⑦强制跑质量验收清单(完整六检查点/全段落扫描;i18n-translation-quality-checklist.md)。
- 2026-07-05:定**标题真相唯一化**原则(显示名=标题唯一真相,内容三通路引用跟随;glossary 注入,修显现/幻影分叉)。
- 2026-07-05:**内容生成 N 默认=0**(收录策略⑤)——上新馆零内容预付,纯懒生成兜底;N 上线后按实际热度/需求由运营逐馆决定。
- 2026-07-04:content 端点加法字段 `generating`(懒任务锁即信号)——前端等待提示三态化(生成中/资料不足/待完善可重试),修盲轮询三隐患。
- 2026-07-13:**覆盖率机制 Phase 1 落地**(spec 2026-07-12-collection-coverage-phase1):§收录策略改**分层收录**(视觉/文字/需求三层,P18 OPTIONAL 收全条目,列表隐形+馆页双数字+用户照片hero);**北极星 KPI 换轴**(验收=现场识别成功率,不看件数);**展陈状态动态化**(attributes.display+证据三层:流量>P276>区域适配器,Joconde样板);**view 自动治理落地**(0.25删/0.4隔离/入库闸,取代dry-run待定);recognition_events 一表两吃(KPI+证据,只存phash);API 面加法:响应 phash+`/recognize/confirm`+pack 双数字;上新馆配方全串至 coverage-report 收官。迁移 p1m2。
- 2026-07-12:定**识别优化优先级原则**(App 用户有意图取景,怪构图非主流,不再加码裁剪/阈值工程;精度主线=二维参考图覆盖+三维多视角库,并入覆盖率机制 spec)+ 记录 **views 污染已知问题**(Commons 分类混入非本体图 14%,vet_view_images 分诊,清洗策略待覆盖率轮;配方加 dry-run 步骤)+ 多裁剪已知代价(库外误出候选卡 48%→81%,确认卡出口兜底)。
- 2026-07-11:**低分自动多裁剪重查**(全景式拍法对症,真实用户实证 0.51→0.84;近拍快路径零影响)+ 批处理纪律第 5 条**空响应≠到底**(WDQS 深 OFFSET 静默截断实证,catalog 漏收 500+ 长尾件;上新馆必核 loaded 数量级)。
- 2026-07-11:**GPT 兜底文字链一律不直判**(命中只出确认卡,不产 `outcome=match`;同名撞车 E2E 实证:自画像/The Bathers 精确同名撞他馆无关件)——直开讲解页只来自向量高置信像素证据;label 模式亦然(多一次确认点)。
- 2026-07-11:**识别主引擎换 DINOv2 向量检索**(R4 兑现:benchmark 裁决 DINOv2 胜 CLIP,非名作 Top-1 95.8%/库外零误接受;GPT+OCR 降为兜底,不可用绝不 500)。**新增全局端点 `POST /api/v1/recognize`**(museum 可选,拍前不选馆)+ 响应加法字段 `museum`(归属馆 slug);裁决**馆域调用不做全局回退**(老 App 前向兼容,跨馆命中=详情 404 死胡同)。参照库=物化即嵌入+backfill;雕塑多视角 view 图(P373 深挖落地);墙签行加馆藏号精确匹配;阈值 server-driven(RECOG_HIGH/LOW 环境变量)。
- 2026-07-04:识别端点**服务端计费**落地(match/candidates 扣1,unrecognized/缓存不扣,超额402;身份=令牌或device_id)——堵住新端点绕过配额的洞,弃用前端自觉调 /payment/consume 的客户端计费。
- 2026-07-04:作者卡 `nationality`/`notable_works` 多语本地化落地(前端交接③;v1 局限解除)。交接①分类标签已由 #142 先行修复;交接②"老件补语种"因 prod 内容清空+六语生成而失效(translate 命令备用)。
- 2026-07-03:**识别 P1 落地**+§识别入契约(R1-R6:接地第一/墙签增强非依赖/三档呈现/引擎可替换/需求自适应/足迹vs归属)。新端点 `/museums/{slug}/recognize`;老 `/recognition` deprecated;P2=CLIP/需求聚合/足迹。
- 2026-07-03:定**批处理纪律**四条(单件容错/分批落盘/外部查询分批+重试/幂等可重跑)——prod names 三次崩溃(ReadTimeout 炸全局、进度全丢、414、502)的血泪成文,全部上馆命令适用(#158/#160 落地)。
- 2026-07-03:**图像 R2 自存落地**(阶段4提前):两档(thumb480/large1600)/多角度(P18全收 primary+view)/署名/懒补漏;image_key=基础键;上新馆步骤加 `images`(第4步);定"图=预物化 vs 内容=懒生成"成本分界。Commons P373 深挖留识别轮。
- 2026-07-03:定**完整性判断按语言维度**原则(一日三错 #142/#146/#147 的统摄:存在性检查按语言问不按对象问;复用≠跳过,共享实体每个复用点做语种补齐)。#147:生成时为已存在作者补齐 bio 缺失语种。
- 2026-07-03:**列表 content_status 按请求语言解读**(该语言无内容→empty"待完善",防列表骗人)+ **懒翻译落地**(ready 但请求语言缺→后台只翻该语言,复用补语种原语+懒生成锁)。
- 2026-07-03:懒生成**请求语言优先**(lang_priority,逐语言翻完即落库,单语言失败不拖垮)+ **补语种命令落地**(`onboard translate`:存量对象缺失语言从 en 段纯翻译,checklist⑤ 闭环;老 243 件补 de/es/it 用它)。
- 2026-07-03:定**本地化完整性原则**——用户可见文本必随 language(固定小集合用静态表配齐全语种,缺译回退 en);机器码永不翻译;"加语言"checklist(五步)。教训:六语开放分类标签只配三语(#142 修)。前端六语选择器 #138-140。
- 2026-07-03:**懒生成落地**(路线图3c):stub 首次访问 → 后台生成(attributes.lazy_lock_at 锁,TTL 10min;并发2;仅部署环境)。组件装配抽 factory(onboard 与懒生成共用)。契约形状零变化。
- 2026-07-03:定**§收录策略**(通用):有图才收录(识别参照+合规)/三层口径(全馆藏≫在展>有图)/定期重跑吃增量/通用分类法8大类(CATEGORY_BY_QID 真相源,多P31已知优先)/生成分层(top-N=奥赛200 只在 prod;staging 小样本;懒生成入路线图3c;官方馆藏库连接器入阶段4)。类目代码统一(photograph→photography、decorative→decorative_arts);奥赛 categories 扩至四大类,catalog P18 必填。
- 2026-07-03:定**显示名解析时机=铺目录时**——新增 `names` 回填命令(title_i18n/artist_qid/Artist名字行,幂等);`_fill_i18n` en 也权威优先;Artist 行存在但 bio 空时 generate 补 bio。修列表页 stub 在 zh 视图显英/法文名问题(截图反馈)。翻译兜底规则经讨论**维持所有语言统一**(权威→机翻→en),不按拉丁/非拉丁分叉。
- 2026-07-03:契约-代码对齐——端点3 `artist` 真正走 name_i18n(此前只 title);facts.medium 优先证据包 P186(修正 P2048 措辞:尺寸仍 Joconde);`country_lang`/`sources` 从 museums.yaml 读(去 France 硬编码,上新馆=纯配置成立)。
- 2026-06-28:新建本活文档。纳入近期加法:端点3 `/objects` 分页;端点2 `categories` facet + language;端点4 `status/title/images/facts`;`content_status` 生命周期;上新馆路径。
- 2026-07-02:多语显示名规则**落地**(title_i18n/Artist.name_i18n:Wikidata多语标签+翻译兜底;端点 resolve_name 语言感知;避 Joconde 脏格式)。
- 2026-07-02:定**多语显示名规则**(权威标签→翻译兜底→en;语言无关,加语言=加配置)入契约。
- 2026-07-02:补记**英语轴心**核心约定(所有生成先英语→接地闸→翻译;新增 prompt 必强制英文)+ 修 generate_artist_bio 漏英文致 bio 语言错。
- 2026-07-02:作者一等实体(artists 表,按 artist QID 生成一次、同作者复用,修每件重复/漏)+ 缺中文标题生成补 + status 按语言判空(修 ready 却空)。
- 2026-07-01:配源round2a——证据包补 Wikidata 关系属性(衍生/基于/启发/系列),给 significance/background 接地影响钩子。
- 2026-07-01:问答去重(QA 收 covered=解说+模块,只问没讲过)+ analysis lane 收到技法(怎么画的,不复述解说符号)。
- 2026-06-30:模块深度——深度模块字数抬高+按热度分档(重点件×1.5,section_target_chars),名作能深则深、薄件天然短、不注水。
- 2026-06-30:作者卡——content 增必选常驻 `artist` 卡(生卒P569/P570·国籍P27·代表作P800 from 作者实体 + artist段叙事为bio);artist 段移出 tabs。
- 2026-06-30:阶段2a 落地——生成从证据包取料(用上 P88/P180 富属性)+ guide 互知去重(模块各守 lane、不复述头条、返空不发布)+ overview 退役(迁移删 category_sections 映射)。
- 2026-06-29(晚):阶段1 证据包落地——`MuseumObject.evidence_pack`(facts/narrative/flagged);端点4 `facts` 策展+人性化(去学术噪音,provenance/exhibitions/bibliography 移出面板)。
- 2026-06-29:升级为**主文档**(契约+内容体系+上馆手册+路线图)。纳入端点4 `default_guide`(默认标准讲解);新增 §内容体系(三层+模块库+证据包+去重lane+动态模块)、§路线图(阶段1-4)、§北极星 + 工作纪律。
