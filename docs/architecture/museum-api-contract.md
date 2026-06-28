# GoMuseum 馆藏 API 契约（活文档）

> **这是唯一权威契约来源。** 改了端点/字段就改这里。各 spec 链接到本文,不再各自抄一份。
> 端点前缀 `/api/v1`。原则:**加法/前向兼容**——只增字段、不破老解析;破坏性变更走版本化端点。
> 最近更新:2026-06-28(catalog Phase B + 富化提厚 + 分类facet + content facts + 语言切换 后)。

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

- `tabs`:按类目的段落清单(`SECTIONS_BY_CATEGORY`)逐段;`body` 为该语种已发布正文(无则 `null`);`audio_url` 为 R2 音频直链(未生成则 `null`,TTS 阶段)。
- `facts`:硬事实面板(墙签信息);`exhibitions`/`bibliography` 为 list(Joconde `#` 分隔拆分);`artist_life` 暂为 null(待接 Wikidata 作者源)。
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

## 变更记录

- 2026-06-28:新建本活文档。纳入近期加法:端点3 `/objects` 分页;端点2 `categories` facet + language;端点4 `status/title/images/facts`;`content_status` 生命周期;上新馆路径。
