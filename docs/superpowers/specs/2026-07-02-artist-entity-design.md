# 作者一等实体(生成一次复用)+ 中文名补全 + 状态修 — 设计

> **状态**:定稿(2026-07-02 brainstorm)。下一步 writing-plans。
> **背景**:15 件验证发现 ① 作者介绍每件独立生成→不一致/漏(星夜有梵高材料却没 artist 段)② 冷门件缺中文标题 ③ La Guerre/Wheel `ready` 却 zh 无内容。

## Part 1:作者一等实体(主改动)

**问题**:`artist` 段每件重复生成,浪费 + 不一致 + 偶漏。作者介绍本是**按作者(而非作品)**的东西。

**设计:作者按 artist QID 生成一次、同作者所有作品复用。**

### 1a. 存储:`artists` 表(新,迁移)
```
qid            PK   # 作者 Wikidata QID(P170 值)
name_zh, name_en
birth, death, nationality
notable_works  JSON # list
bio            JSON # {lang: text} 规范作者介绍(en 生成→翻译)
created_at, updated_at
```

### 1b. 解析并存 artist_qid
`fetch_artist_facts` 的 SPARQL 加 `?artist`(P170 目标)→ 返回 `artist_qid`。pipeline 存进 `MuseumObject.attributes["artist_qid"]`(无需列迁移)。

### 1c. 生成:一次生成、复用
`generate_object` 里(拿到 artist 材料/facts 后):
- 取 `artist_qid`;查 `artists` 表。
- **已有 bio → 复用**(不生成)。
- **没有(或 force)→ 生成一次**:`enricher.generate_artist_bio(artist_material, target_chars)`(en 轴,复用 artist lane 语气)→ 三类闸 → `translator` 翻译 → 存 `Artist` 行(bio by lang + 结构 facts)。
- **`artist` 从 per-work `SECTIONS_BY_CATEGORY` 移除**(不再是每件的模块段)。

### 1d. 契约:作者卡从 artists 表取
`get_object_content` 的 `artist` 卡:`aqid = attrs.get("artist_qid")` → 查 `artists` 表 →
`{name: _pick(lang, art.name_zh, art.name_en, ...) or obj.artist_*, birth/death/nationality/notable_works: art.*, bio: art.bio.get(language)}`。
无 artist 行 → 回退用 obj.artist_zh/en 作 name、bio=null(优雅降级,卡仍在)。**卡字段形状不变**。

## Part 2:中文标题补全

生成时:若 `title_zh` 缺,用 `translator.translate_section(title_en, "zh")` 生成中文译名存 `title_zh`(冷门件 Wikidata 无 zh 标签时兜底)。艺术家名同理可选(本期先标题)。

## Part 3:状态按语言判(读取时)

`get_object_content` 返回的 `status`:若请求语种**无 guide 正文且无任何 tab**(该语种实为空)→ 返 `"empty"`(前端显"待完善"),不受 stored `content_status` 误导。修 La Guerre/Wheel"ready 却空"。

## 非目标

作者头像、作者其它作品跳转、artist QID 列(用 attributes)、多馆作者去重合并(同名不同 QID 暂不处理)、Europeana。

## 契约 / 迁移

- 新 `artists` 表(迁移)。`artist` 段退出 tabs(数据层)。作者卡 shape 不变;`status` 读取时可返 empty(前端已容错)。前向兼容。

## 测试

- `fetch_artist_facts` 返 `artist_qid`(fake run_query 含 ?artist)。
- `generate_artist_bio`(注入 complete)产 bio;pipeline:首件生成+存 Artist,同作者次件复用(不重复调生成)。
- artist 退出 SECTIONS_BY_CATEGORY。
- `get_object_content` 作者卡从 artists 表(有行→用之;无行→回退 name)。
- 中文标题:缺 title_zh→翻译补。
- status:无 guide+无 tab→empty。
- 全量回归无破。

## 改动文件

- `backend/app/models/artist.py`(新 Artist 模型)+ Alembic 迁移
- `backend/app/services/enrichment/material.py`(fetch_artist_facts +artist_qid)
- `backend/app/services/enrichment/content_enricher.py`(generate_artist_bio)
- `backend/app/services/enrichment/category_config.py`(SECTIONS_BY_CATEGORY 移除 artist)
- `backend/app/services/enrichment/pipeline.py`(生成/复用 Artist、存 artist_qid、补 title_zh)
- `backend/app/services/museum_repo.py`(作者卡从 artists 表;status 按语言判)
- 测试 + 回写主文档
