# 交接（前端）：博物馆介绍 + 封面(折叠 hero)

> 后端已上(spec 2026-07-18-museum-intro)。馆包(`GET /museums/{slug}?language=`)新增两个**加法**字段,
> 老 App 不读不炸。本交接 = 在馆列表页顶部加封面 + 折叠介绍卡。

## 契约(馆包新增两字段)

```json
{
  "slug": "orsay", "name_zh": "...", "artwork_count": 262, "categories": [...],
  "description": "奥赛坐落在一座1900年的火车站里…(按 language 的叙事介绍)",
  "cover_image": "https://r2/…/…_large.jpg",
  "artworks": [...]
}
```

- `description`:AI 接地叙事,一段 ~150-250 字,按请求 `language`(缺→en→**null**)。
- `cover_image`:得体性筛选后的封面直链(large 档),**可能 null**。
- ⚠️ 两字段都 `as String?`,**null 时整块隐藏**(不是每个馆都有——生成失败/无合规封面时为 null)。

## 呈现:折叠 hero(不做 tab)

馆列表页(藏品列表)**顶部**加一块,藏品列表仍是主视图:

1. `cover_image` 非 null → 顶部大图 banner(16:9 或 3:2,`cover_image` 是 large 档够清晰);null → 不显图。
2. `description` 非 null → 图下方一张介绍卡,**默认收起显 2 行 + "展开"**,点开展全段;null → 不显卡。
3. 两者都 null → 整个 hero 块不出现,列表照旧(老行为)。

**为什么折叠 hero 不做 tab**:用户点进馆是来看藏品的,tab 会把藏品列表降级成要切换的次要视图、多一次 tap;
折叠 hero 让介绍锦上添花不挡路。若你更想要 tab,后端零改动,自行决定。

## 验收(真机)

1. orsay 馆页顶部出现封面(《煎饼磨坊的舞会》)+ 中文介绍卡(默认 2 行,可展开);
2. 切语言 → 介绍卡文字随 `language` 变(zh/en/ja…);
3. 构造一个 `description=null` 的馆(或后端未跑 intro 的馆)→ hero 块整体不出现,列表正常。

## 相关

- 后端:`onboard <slug> intro`(馆介绍+封面,已在上新馆配方);`museum_intro.py`。
- 契约:`docs/architecture/museum-api-contract.md` 端点 2。
