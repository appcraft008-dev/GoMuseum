# 搜索功能设计（稳定契约 + 可替换引擎）

> 2026-07-13 brainstorm 定稿。搜索是识别机制的姊妹功能，也是无图 stub（文字可识别层，
> 奥赛 ~2782 件）的主要可达路径。与 [[recognition-mechanism]]、覆盖率 Phase 1 配套。

## 目标与原则

- **两入口按位置分工**：探索页 = 全局搜（跨馆藏品 + 博物馆本身）；馆列表页 = 只搜当前馆藏品。
- **打字搜索 ≠ 识别匹配**：识别 matcher 是整串模糊相似（GPT 给完整候选名）；搜索是**子串/分词**
  （用户打"梵高"/"moulin"/"RF1668"）。搜索匹配逻辑独立设计，仅复用 matcher 的归一化工具。
- **全语种搜**：藏品 `title_i18n` 全语种 + 作者 `name_i18n` 全语种都进搜索（中文界面打 Van Gogh 也中）。
- **无图 stub 必须可搜**：与浏览列表（隐藏无图件）相反——搜索是无图件的主入口。
- **稳定契约 + 可替换引擎**（照搬识别机制已验证的架构）：用户可感知行为由契约锁定、跨引擎不变；
  引擎可插拔演进。**这是本设计的核心。**

## 架构：契约层 + 引擎层

### 契约层（稳定，跨引擎不变）

两个加法端点：
```
GET /api/v1/search?q=<关键词>&language=<lang>&limit=20        # 全局(探索页)
GET /api/v1/museums/{slug}/search?q=<关键词>&language=<lang>&limit=20   # 馆域(馆列表页)
```

响应（全局版含 museums + objects 两段；馆域版只有 objects）：
```json
{ "query": "梵高",
  "museums": [ {"slug":"orsay","name":"奥赛博物馆","city":"巴黎"} ],
  "objects": [
    {"qid":"Q...","title":"星夜","artist":"文森特·梵高","year":"1889",
     "thumbnail":"<R2 URL 或 null>","museum":"orsay","has_image":true} ] }
```
- `title/artist` 按 `language` 走既有显示名规则（`_resolve_name`）；`thumbnail` 无图件 null；
  `museum` = 归属馆 slug（点击跳讲解页用，与识别 match 同款导航）。
- **无图 stub 照常在 objects 里**（`has_image:false`，前端类目占位图）。
- `museums` 字段仅全局端点有（馆域端点不返回）。
- 空 `q` 或无结果 → `objects:[]`（+全局的 `museums:[]`），诚实空态，不脑补。

### 引擎层（可替换）

抽象接口：`search_engine.search(db, query, *, museum_id=None, language, limit) -> (museums, objects)`。

**首发实现 = 进程内索引**（`app/services/search/inprocess.py`）：
- `build_search_index(db, museum_id=None) -> list[dict]`：每件产
  `{qid, museum_slug, museum_id, names:set(全语种归一化标题), artists:set(全语种归一化作者名),
    inv:str|None, popularity:int, has_image:bool}`；归一化复用 `matcher.normalize`/`normalize_inv`。
  馆域索引进程内缓存 TTL 600s（同 matcher `_index_cache` 模式，key=museum_id，None=全局）。
- 博物馆搜索（仅全局）：对 `museums` 表的 `name_zh`/`name_en`/`city_zh`/`city_en` 列归一化子串
  匹配（Museum 无 i18n JSONB，就这几列；小集合，直接查全表内存过滤）。
- 匹配+排序（藏品）：query 归一化+分词 → 三路：
  - **编号精确**（`normalize_inv(q)` == entry.inv，≥3 位）→ 分 1.0（最高）；
  - **标题前缀命中** → 0.8；**标题子串命中** → 0.6；**作者子串命中** → 0.4；
  - 同分按 `popularity` 降序；取 top `limit`。
- 空表/空 query → `[]`。

**规模触发换引擎**（写入本 spec，不拍脑袋）：藏品总量越过 ~5-10 万（**具象参照：上了卢浮宫+蓬皮杜
量级之后**）/ 实测查询延迟退化（进程内线性扫描 + 内存 ×worker 数是瓶颈）/ 上第 N 个馆。届时换
**自托管搜索引擎**（Meilisearch / Typesense：CJK 分词好、子串/前缀/错字容忍、百万级即时搜索、
自托管边际成本低——同 DINOv2/Qwen3-TTS 理念）。换引擎只换 `search()` 实现，**契约与前端零改动**；
唯一细微差别是排序权重（引擎自有算法），"能搜到什么"完全一致。

> **决策记录（2026-07-13，用户定）**：现在**进程内起步**（单一真相源=Postgres，零同步，新馆/新藏品
> 自动出现；一个馆 5000 件毫秒级足够）。Meilisearch 虽部署简单、资源不高，但引入第二数据源=永久的
> 同步+漂移管理负担；在当前规模不划算。等触发信号（如卢浮宫+蓬皮杜级别）再换，抽象层已铺路、
> 迁移是被契约保护的独立小工程。

## 前端

### 探索页（`explore_page.dart`，升级现有搜索框）
- 现搜索框（客户端过滤馆）→ 升级调全局 `/search`，即时（debounce 300ms，输入 ≥1 字符触发）。
- 空查询 → 正常探索页（馆列表 + 城市 chips 不变）；有输入 → **分区结果**：
  「博物馆」段（名+城市 → 点击进馆页）+「藏品」段（→ 点击进讲解页）。
- 城市 chips 保留（浏览用），与搜索并存。

### 馆列表页（`museum_page.dart`，激活右上角占位搜索图标）
- 图标点击 → 展开馆内搜索（即时，只搜当前馆）；结果 = 纯藏品列表（无博物馆段）。

### 藏品结果行（两处共用）
- 缩略图（有图）/ **类目占位图（无图，复用覆盖率轮 `GmInnerImage` 占位）** + 标题（当前语言显示名）
  + 作者 + 年代；点击 → 讲解页（`GuideArgs(slug=item.museum ?? fallback, qid)`，与识别 match 同款导航）；
  无图件 → 占位 hero + 内容懒生成（文字可识别层入口跑通）。
- 契约容错：`museum`/`thumbnail` 用 `as String?`，`has_image` 用 `as bool? ?? false`。

### 识别 → 搜索闭环（小增强）
- 识别"未收录"卡加「输入编号/名称查找」按钮 → 跳当前馆搜索（预聚焦）。识别兜底与搜索闭环。

## 测试

**后端（TDD，sqlite fixture 抄 `tests/unit/services/recognition/test_matcher.py`）：**
- 标题子串命中（含跨语种：中文界面查 "Van Gogh" 命中）、作者子串、编号精确、排序
  （编号 1.0 > 前缀 0.8 > 子串 0.6 > 作者 0.4）、馆域 vs 全局过滤、**无图 stub 出现在结果**、
  空查询/无结果 → []、显示名本地化、无图件 thumbnail=null、博物馆名/城市搜索（仅全局）。
- 端点：全局 vs 馆域、响应形状（museums 段仅全局）、language 参数、馆不存在 404（馆域端点）。

**前端（`flutter analyze && flutter test`）：**
- datasource 两 URL 选择 + query 参数；结果解析（has_image/museum 禁裸强转）；分区结果 widget；
  无图占位渲染；识别未收录卡→搜索跳转。
- debounce/即时输入交互做 smoke 或从简。

## 不做（YAGNI）

- 不上 Meilisearch/搜索引擎（进程内够用到 5-10 万件；触发信号已写明）；
- 不做 Postgres 全文检索（CJK 分词硬伤）；
- 不做搜索历史/热门搜索/拼写纠错（等真实需求）；
- 不做跨馆藏品去重/合并（各馆独立记录）。

## 契约回写（实现完成后）

主契约加：`/search` 两端点 API 面（全局/馆域、响应形状、三路匹配、全语种、无图可达）+
"搜索=稳定契约+可替换引擎，进程内起步、规模触发换 Meilisearch"通用原则 + 识别未收录→搜索闭环。
