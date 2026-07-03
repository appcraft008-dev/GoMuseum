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

`language` 取值:`DEFAULT_LANGUAGES` 全集 `en/fr/de/es/it/zh`(2026-07-03 起新生成内容六语全跑;早期存量 243 件讲解只有 zh/en/fr,de/es/it 视图对老件显"待完善",待"补语种"增量命令回补)。缺省 `zh`。显示名(title/artist)六语已全量回填。

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

- `title` 按多语显示名规则:`title_i18n[lang]`(Wikidata权威)→ 该语言 legacy 列 → en 兜底。`artist` 同理经 name_i18n。
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
- `artist`:**必选常驻作者卡**(不随空隐)。**数据来自 `artists` 一等实体**(按 artist QID 生成一次、同作者所有作品复用→一致/完整/省;artist 不再是 per-work 段)。`{name, birth, death, nationality, notable_works:[...], bio}`(**name/title 按多语显示名规则解析:i18n 权威→翻译→en**;bio 按语言取)——生卒年/国籍/代表作取自作者 Wikidata 实体(P569/P570/P27/P800);`bio`=artist 段已发布叙事(无则 null)。⚠️ v1:`nationality`/`notable_works` 为 en 标签(zh 视图暂显 en),`name`/生卒年不受影响。
- `facts`:**已策展+人性化的墙签事实**(只 wall_label 级):`artist/date/medium/dimensions/inventory/location`。`medium` 优先证据包干净源(Wikidata P186,多值合并人性化),回退 Joconde `medium_fr`;`dimensions` 取 Joconde 串人性化(证据包暂不抓 P2048/P2049,非法国馆无 Joconde 时为 null)。⚠️ **`provenance` 返 null、`exhibitions`/`bibliography` 返 `[]`——已移出面板**(学术噪音;参考文献彻底不展示,收藏/展览史进证据包材料级,阶段2 由 background lane 讲成流转故事)。`artist_life` 暂 null。
- `suggested_questions`:好奇心问答(0-4 条)。
- 对象不属于该 slug / 不存在 → 404。

---

## `content_status` 生命周期

`stub`(只元数据,目录铺出) → `ready`(≥1 段已发布)/ `empty`(无可接地材料)。前端:`stub`/`empty` 显"待完善",`ready` 正常。未知值按 `ready` 容错。

**懒生成(✅2026-07-03 落地)**:content 端点命中 `stub` → 后台触发该件完整生成(全语言),几分钟后再取即 `ready`。锁=内部 `attributes.lazy_lock_at`(TTL 10min 自愈),**不对外暴露中间状态**——stub 期间前端照旧"待完善",契约形状零变化、老 App 无感。`empty` 不重试(已判无可接地材料,防循环烧钱)。并发上限 2/进程;仅 staging/production 环境生效。

## 图片字段

`image`(端点2)/`thumbnail`(端点3)/`images[].url`(端点4)取值:`ObjectImage.image_key` 有则 R2 直链(`storage.public_url`),否则回退 `source_url`(当前多为 Wikimedia `Special:FilePath`)。
> ⚠️ **已知问题 + 规划**:Wikimedia 链接按 UA 策略拦截(需合规 UA)且原图大/现生成慢。规划:富化阶段把图自存 R2 并预生成尺寸档,`image_key` 填充后这些字段自动返 R2 直链(字段名不变,前端零改)。见图像自存交接。

---

## 收录策略（通用规则,任何馆 0 代码复制;2026-07-03 定）

**① 有图才收录(硬规则)。** 只收 Wikidata 上有自由版权图(P18/Wikimedia)的藏品:图是**识别的参照物**(App 靠拍照识别,无图=不可识别的死重)也是**合规边界**(官方馆藏库的图多为 RMN 类版权摄影,商用展示/自存都踩线)。catalog SPARQL 中 P18 必填。

**② 三层口径(奥赛样板数字,评估任何馆时先查这三层)。** 官方全馆藏(奥赛~15万,绝大多数在库房) ≫ **常设在展(奥赛 3-4千,产品真实分母——游客只可能拍到它)** > Wikidata 有条目(5353) > **有图可收录(2065=我们的集合)**。Wikidata 收录天然偏名作、与"在展"高度相关,故有图集合对现场识别命中率的真实覆盖远好于比例数字。

**③ 定期重跑 catalog 吃增量。** Wikimedia 图持续增长;catalog/merge_stubs 幂等,重跑自动收新有图的藏品——"只收有图"不是一锤子,是动态逼近全部可识别集。

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

**⑤ 内容生成分层(目录便宜、生成贵)。** 目录+显示名回填全量做(全馆 ~$20 内);讲解生成按热度 **top-N 批量**(`generate --limit N`;奥赛 N=200)+ **长尾懒生成**(规划中,`content_status=generating` 锁已预留;staging 验证后上 prod)。**全量目录/生成只在 prod 跑;staging 只做小样本验证机制**(`catalog --limit`)。

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
4. **生成内容**:`python scripts/onboard.py <slug> generate --target <env> [--qid Q..|--limit N] [--langs zh,en,fr]`
   → 逐件:stub 抓材料(Wikipedia/Joconde)→ 生成 → 接地闸 → 翻译 → 落库 → `ready`/`empty`。
5. 端点自动产出上述四个契约;前端零改接入。

**非 Wikidata 主源的馆**(如美国 Met):一次性写个 `CatalogSource` 连接器(同插件模式,核心零改),其余同上。

`--target` 必须匹配容器 `ENVIRONMENT`(守卫防误灌)。全量富化在 prod 跑(staging 仅样本验证机制)。

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
> **解析时机 = 铺目录时(2026-07-03 定)**:显示名是**目录元数据、不是生成内容**——catalog 后立即跑 `onboard.py <slug> names --target <env>`(幂等可重跑),全馆补齐 `title_i18n`/`artist_qid`/Artist 名字行;stub 一进目录就有完整多语显示名,**不等内容生成**(此前只在 generate 时填,导致列表页大量 stub 在 zh 视图显英/法文名)。generate 时同一机制增量修补。en 也权威优先(纠正目录把非英文标签误存 title_en,如 "Régates à Argenteuil")。

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

## 路线图（执行顺序;每阶段 = 独立 spec→plan→实现,完成回写本文）

**✅ 已落地**:目录主干 + 4 端点契约 + 分类 facet + 作品信息 facts;接地·引人入胜生成 + 三类闸 + 多语翻译 + 建议问答;默认讲解 stage1(staging)。

- **阶段 1 — 材料地基(证据包)**:1a 源配全(Europeana + 更全 Wikidata P 属性;法国官方=Joconde 已有,非法国馆逐馆官方连接器)· 1b 证据包模型 + 分类落库。→ 每件一份完整分类证据包。
- **阶段 2 — 内容生成重构**:2a 统一分工去重(lane)+ 全从证据包生成 · 2b 动态模块 + 争议 hedge · 2c 两段式质量评估(事实质量 + 讲解质量)。
- **阶段 3 — 体验补全**:3a AI 自由问答 `/ask`(多轮)· 3b TTS 音频落库 · ~~3c 懒生成接线~~(✅2026-07-03 落地,见 content_status 节)·(藏品识别机制 = 独立 brainstorm)。前端增强(生成中提示/自动刷新)另排。
- **阶段 4 — 规模化**:图像 R2 自存 + `cover_url` + 首页真实化 · 上新馆(逐馆官方连接器 + 纯配置)· **官方馆藏库连接器**(抓元数据+在展清单/展厅号,不抓图;用"在展×有自由图"校准优先级,修正名作偏置)。

**奥赛 = 样板馆**:作为先行者会多吞一两次重生成;流水线成型后,新馆从第一天即"配全·生成一次·封板"。

---

## 变更记录

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
