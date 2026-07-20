# 交接（后端）：馆封面选图算法 + 探索页缩略图字段 + 简介分段（三处，均为馆介绍功能的收尾）

> 前端 session 真机测试馆介绍(spec 2026-07-18)后发现三处问题，定位到都是后端生成/契约缺口，
> 非前端能改。前端已实现"封面/藏品"两 tab 详情页(#292 之后)消费这些数据，本交接只需后端配合。

## 问题 1：探索页馆列表没有图片（A1 端点缺字段）

`GET /museums`（`list_museums()`，探索页数据源）只返回 `_PACK_FIELDS`（slug/name/city/country）
+ artwork_count，**没有任何图片字段**。探索页因此对首个馆渲染大卡但只能用占位图标，其余馆降级成纯文
字行——用户反馈"橘园没有图片""奥赛不能展开"，根因就是这里完全没数据可用，不是前端没接。

**修法**：`list_museums()` 已经用 `db.query(Museum, ...)` 拿到完整 ORM 行，`m.cover_image_key`
零成本可读（同一行，非额外查询）。加一个 `cover_image`（`thumb` 或 `medium` 档，探索页列表缩略图用途，
不需要 `large`）：

```python
row["cover_image"] = (
    _sized(storage, m.cover_image_key, "thumb") if m.cover_image_key else None
)
```

纯加法字段，老 App 不读不炸。**注意**：这依赖问题 2 修好后 `cover_image_key` 存的是建筑外观图；
现在就加这个字段也不会错，只是在问题 2 落地前，图会是"热门藏品图"（不算错，但不够好）。

## 问题 2：封面选图选的是"著名藏品"，不是建筑外观（用户明确要求：不要用藏品图）

当前 `museum_intro.py` `select_cover()` 从 `MuseumObject`（馆藏品）里按热度选图、过安全闸——**完全没
考虑馆自身的建筑照**。实测：奥赛封面被选中的是《煎饼磨坊的舞会》（Q683274，一幅画），橘园是《婚礼派对》
（Q21849357，另一幅画）。用户想要的是"博物馆全景图/外观建筑/正门入口图"。

**已验证数据现成**：馆自身 Wikidata QID（`Museum.qid`，与 `MuseumObject.qid` 是两码事）本身的
**P18（image）属性**就是机构惯例的建筑照，不是藏品：

| 馆 | Museum.qid | P18 图 |
|---|---|---|
| orsay | Q23402 | `MuseeDOrsay.jpg`、`Gare d'Orsay (49570190081).jpg`（火车站外观）、`Musee d'Orsay and Pont Royal...jpg` |
| orangerie | Q726781 | `2011-12-Musee de lorangerie.jpg` |

**修法方向**：`select_cover()` 加一个"馆自身 P18"优先分支——用 `m.qid` 查 Wikidata
`wbgetclaims?property=P18`，拿到 Commons 文件名，走现有图片下载/R2 落库管线（复用
`ObjectImage`/`_sized` 那套，或专门给 Museum 建一条同构路径），设 `m.cover_image_key`。
**保留现有藏品图选择作为 fallback**（没有 P18 或下载失败时）——不要因新逻辑失败就整体开天窗。

安全闸（`build_cover_safety_prompt`）对建筑照大概率不需要（没有裸体风险），但过一遍也无妨、成本极低。

## 问题 3：简介写死"ONE paragraph"，读起来累（用户要求分段）

`_MUSEUM_INTRO_SYSTEM`（`prompts.py`）明确要求"You write ONE engaging paragraph (~100-160
words)"——故意生成不分段的一整块。用户反馈"一大段文字没有分段读起来累"。

**修法**：prompt 改成要求 2-3 个短段落，用 `\n\n` 分隔（比如：①历史/建筑背景 ②馆藏亮点与风格
③邀请一句）。**前端已经能直接消费**——`Text` 组件天然按 `\n` 换行，不需要前端做任何改动，
生成时字符串里带 `\n\n` 就会自动分段显示。⚠️ 存量已生成的馆（如 orsay/orangerie）不会自动补
分段，需要 `force=True` 重跑 `generate_museum_intro` 才能吃到新 prompt。

## 验收

1. `GET /museums` 响应含 `cover_image`（thumb/medium 档，非 null 时）；
2. orsay/orangerie 重新生成封面后，`cover_image` 指向建筑外观图（非藏品画作）；
3. orsay/orangerie 重新生成简介后，`description` 含 `\n\n` 分段（前端自动渲染，无需联调）。

## 相关

- 前端已实现的"封面(默认)/藏品"两 tab 详情页：`frontend/gomuseum_app/lib/features/explore/presentation/pages/museum_page.dart`
  （`_CoverTab`/`_CoverTabBody`——已消费 `description`/`cover_image`/`opening_hours`/`official_url`，
  三处后端改动落地后前端零改动即可生效）；
- 前序：`museum_intro.py`（`generate_museum_intro`/`select_cover`）、`prompts.py`
  （`_MUSEUM_INTRO_SYSTEM`/`build_cover_safety_prompt`）；
- 契约：`docs/architecture/museum-api-contract.md`（A1 `GET /museums` 需回写新增 `cover_image` 字段）。
