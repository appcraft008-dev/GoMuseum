# 第 1 步设计 · 数据与存储地基

> 日期 2026-06-14。关联：`docs/PRE_PAID_ROADMAP.md` 第 1 步、`docs/architecture/recognition-and-storage-strategy.md`。
> 状态：设计定稿待评审 → 转 writing-plans。

## 目标与边界

把当前"**馆藏目录散在 JSON 文件 + 讲解只在 Redis + 音频在本地磁盘**"的临时形态，迁移成：

- **PostgreSQL 落库为唯一真相源**（讲解永久保存，Redis 仅做加速缓存）；
- **二进制资产（图片/音频）上 Cloudflare R2**（经统一存储抽象，本地实现先行，凭证已就绪）；
- **数据模型泛化成通用展品**（现在只填绘画，未来雕塑/器皿/珠宝/家具不改表结构）；
- **硬事实从 Wikidata 拉**（作者/年代/尺寸/材质/现藏地/馆藏号），不让 AI 生成。

本步范围：全做（DB + R2 + Wikidata 硬事实补全）。pgvector 向量索引**不在本步**（过早优化），仅预留演进路径。

### 关键决策（已与用户确认）

| 决策 | 选择 |
|---|---|
| 范围 | 全做 + Wikidata 硬事实补全 |
| R2 | 写存储抽象 + R2 实现（凭证已配，桶 `gomuseum-assets`，公共读已启用） |
| 真相源 | **DB 唯一真相源**；`build_museum_pack.py` 由"生成 JSON"升级为"导入器"，JSON 降级为备份/中间产物 |
| 内容结构 | 讲解拆"分节(section)"，一节=一个 UI tab；`category_section` 映射表数据驱动"哪类展品显示哪些 tab" |
| 向量字段 | 本步不加 pgvector 列，仅在 spec 固化未来 migration 路径 |
| tab 映射 | 现在就建 `section_type` + `category_section` 两张小表 |

## 身份模型（语言无关做钥匙，语言相关只当展示）

文化藏品没有"拉丁名"式的统一自然标识——每件是独一无二的个体。采用三层身份：

1. **内部主键 `id` (UUID)**：永久不变、与外部系统解耦、所有外键指它。**必有**。
2. **`qid` (Wikidata QID)**：跨语言锚（纯数字与语言无关），关联 Wikidata 事实 / 去重 / 未来识别锚点。知名件有，**可空且 UNIQUE**（Postgres 允许多个 NULL）。
3. **`inventory_number`（馆藏号）+ `museum_id`**：覆盖 QID 够不到的冷门件。约束 `UNIQUE(museum_id, inventory_number)`。**可空、尽力填**。

**去重/匹配优先级**（导入与识别共用）：`qid` → `(museum_id, inventory_number)` → 标题+作者弱匹配（兜底）。

**标题等语言相关字段绝不参与身份判定**，只作展示属性。

**馆藏号来源**：本步从 Wikidata `P217` 顺手拉（加一行 OPTIONAL，零新集成，部分覆盖）；未来按馆用开放数据（法国 POP/Joconde、The Met API、Europeana 等）回填。缺失不阻塞——识别靠图像+UUID，不依赖馆藏号。

## 数据模型（6 张表）

### `museum`
```
id uuid PK | slug text UNIQUE | qid text | name_zh | name_en | city_zh | city_en | country | created_at | updated_at
```

### `museum_object`（通用展品）
```
id uuid PK
museum_id uuid FK → museum
qid text UNIQUE NULL              -- Wikidata QID
inventory_number text NULL        -- 馆藏号；UNIQUE(museum_id, inventory_number)
category text                     -- "painting"（泛化字段，未来 sculpture/vessel/jewelry/furniture…）
title_zh | title_en
artist_zh | artist_en
year text                         -- 年代字符串（Wikidata 格式杂，存文本）
period_zh | period_en
popularity int                    -- 排序用
attributes jsonb                  -- 分类专属硬事实：{dimensions, material, medium, movement, inception, current_location…}
created_at | updated_at
UNIQUE(museum_id, inventory_number)
```
硬事实落 `attributes` JSON：每类展品不同的字段塞 JSON，不必加列。通用字段（作者/年代）留顶层列。

### `object_image`（展品图片，一对多）
```
id uuid PK
object_id uuid FK → museum_object
role text                         -- primary | detail | view | back …
source_url text                   -- 外部源（Wikimedia 等），溯源 + 重抓
image_key text NULL               -- R2 自存副本 key（镜像后才有）
license text NULL                 -- CC 许可（署名法律要求）
credit text NULL                  -- 作者署名
sort int
created_at | updated_at
```
油画放一条 `primary` 即可；雕塑/器物多视角直接多条，**表结构不变**。展示走 `image_key` 拼 R2 公共 URL，回落 `source_url`。

### `section_type`（讲解节类型 = tab 词表）
```
code text PK                      -- overview | artist | background | story …
label_zh | label_en               -- tab 显示名
icon text NULL
default_sort int
```

### `category_section`（哪类展品显示哪些 tab，数据驱动）
```
category text
section_code text FK → section_type
sort_order int
PK(category, section_code)
```
加品类 / 改 tab 集 = 插数据，不改代码、不发版。

### `object_content_section`（讲解内容，一节一行）
```
id uuid PK
object_id uuid FK → museum_object
language text                     -- zh | en …
section_code text FK → section_type
body text                         -- 该节正文
audio_key text NULL               -- 该节 TTS 音频在 R2 的 key（每节可单独听）
status text                       -- draft | published | needs_review（质检/重生成用）
model text NULL                   -- 生成模型 / prompt 版本，溯源 + 可复现
source text                       -- ai_generated | manual
generated_at | created_at | updated_at
UNIQUE(object_id, language, section_code)
```

### 未来演进（本步只预留，不建）
- 识别检索：一条干净 migration 给 `museum_object` 加 `embedding vector(N)` + 索引（装 pgvector）。`qid`/`id` 即稳定锚点。
- 用户照片：**不进库**（识别完即弃），不在本数据模型内。

## 存储抽象（R2-ready）

接口 `ObjectStorage`：`put(key, data, content_type)` / `get(key)` / `exists(key)` / `delete(key)` / `public_url(key)`。

- `LocalObjectStorage`：存本地目录，`public_url` 走后端 `/assets/{key}`（取代现 TTS 散盘做法）。
- `R2ObjectStorage`：boto3 走 S3 兼容协议连 R2，`public_url` 返回 `R2_PUBLIC_BASE_URL/{key}`。
- 工厂 `get_object_storage()` 按 `STORAGE_BACKEND`(local|r2) 返回单例。
- key 命名：图片 `images/{qid_or_id}/{role}.jpg`，音频 `audio/{qid_or_id}/{lang}/{section}.mp3`（结构化、可覆盖重生成）。
- 配置在 `.env`：`STORAGE_BACKEND` / `R2_ENDPOINT_URL` / `R2_ACCESS_KEY_ID` / `R2_SECRET_ACCESS_KEY` / `R2_BUCKET` / `R2_PUBLIC_BASE_URL`（已就绪）。

## 导入 / 迁移流程

1. **Alembic 迁移**：建 6 张表 + 约束。pgvector 列不建。
2. **种子数据**：`section_type` 灌 overview/artist/background/story（中英标签）；`category_section` 配 `painting` → 这 4 节及顺序。
3. **导入器**（升级 `build_museum_pack.py`）：Wikidata SPARQL → upsert `museum` + `museum_object`，新增拉 `P217`(馆藏号) 及硬事实(尺寸 P2048/材质 P186/现藏 P276/流派 P135/创作 P571)进 `attributes`。按身份优先级幂等 upsert。可选保留 JSON 导出备份。
4. **图片镜像**：每条 `object_image.source_url` 下载 → `storage.put(images/…)` → 写回 `image_key`（R2 已可用）。
5. **一次性数据迁移**：
   - 现有 `museum_packs/orsay.json`（60 件 + popularity）灌库，不丢已策展目录；
   - **Redis 现有讲解 → `object_content_section` 的 `overview` 节**（按 作品+作者+语言 键匹配到展品，status=published, source=ai_generated），已付费内容不丢。

## 接口改造（保持返回形状不变，不惊动审核中的 App）

- `museums.py`：改读 DB，加序列化器把库里行拼回**现有 pack JSON 形状**（list + 完整 pack），字段逐一对齐，App 无感。
- `content.py`：讲解从 `object_content_section` 读；未命中才生成 → **落库 + 写 Redis 缓存**。Redis 自此仅加速，DB 是真相。
- 新增薄接口：按展品返回"有序 tab 列表（含标签/图标）+ 各节正文/音频"，供后续 tab 化 UI（UI 接线本身在第 5 步）。

## 测试

- **迁移/模型**：7 表与约束建立正确；`UNIQUE(museum_id, inventory_number)`、`qid` 可空唯一生效。
- **导入器幂等**：连跑两次行数不变（按身份键 upsert）。
- **Redis→DB 迁移**：键匹配正确、归到 overview、status/source 正确。
- **接口向后兼容**：`museums` 返回与现有 JSON 逐字段一致（防止动到审核中的 App）。
- **存储抽象**：local 实现 put/get/public_url；R2 实现仅在有凭证时跑、否则跳过。
- **content 接口**：命中库 / 未命中→生成→落库 两条路径。

## 不做（YAGNI / 明确推迟）

- pgvector 向量列与检索索引（演进路径已固化）。
- 用户照片持久化。
- 多语音/语速音频变体（每节每语言一条规范音频即可）。
- 馆方开放数据全量回填馆藏号（按需逐馆，非前置）。
- 藏品生命周期（退藏/借展/轮展状态）——以后加 status 列即可，不影响现结构。
