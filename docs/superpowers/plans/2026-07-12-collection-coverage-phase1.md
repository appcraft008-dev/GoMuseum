# 藏品覆盖率 Phase 1 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 落地覆盖率机制 Phase 1：KPI/展陈证据埋点、无图 stub 分层收录（列表隐形+馆页双数字+用户照片 hero）、展陈状态模型、view 自动治理、Joconde 区域适配器样板、覆盖率报告。

**Architecture:** spec 见 docs/superpowers/specs/2026-07-12-collection-coverage-phase1-design.md。北极星 KPI 与展陈证据共用一张 `recognition_events` 表（一鱼两吃）；无图 stub 靠 catalog P18 改 OPTIONAL 进库，列表/计数显式过滤有图，识别文字链与搜索天然可达；展陈状态存 `attributes["display"]`（零迁移）；view 治理纯自动双阈值+隔离 role；报告 CLI 聚合并回写 `museums.stats`。

**Tech Stack:** SQLAlchemy+alembic / FastAPI / numpy / Flutter。无新依赖。

**执行模型分层（调度者注意）**：标注 [SONNET] 的 task 计划内含全码=照抄+TDD；标注 [OPUS] 的需要读懂既有代码。审查：小 diff 用 sonnet，核心/共享代码 diff 用 opus；全分支终审 opus。

## Global Constraints

- 契约只加不改：识别响应新增 `phash` 字段（加法）；museum pack 新增 `catalog_count`/`archive_count`（加法）；`POST /api/v1/recognize/confirm` 新端点；老端点/老字段零变化。
- 埋点绝不阻断识别主流程：事件落库 try/except 只记日志；confirm 端点 fire-and-forget 语义（永远 200/204）。
- 隐私：事件只存 phash（与 demands 同规格），不存照片。
- 无图 stub：列表与分类计数**不出现**（显式有图过滤）；识别文字链/搜索可达；讲解懒生成照常。
- view 治理纯自动无人审：入索引 ≥0.4；<0.25 删（图行+向量）；0.25-0.4 → `role="view_quarantine"`（留档、不索引、不进详情图集）。
- Flutter 解析禁裸 `as String`；flutter analyze 零新告警。
- Python 过 black+isort；husky 钩子不绕过；**禁止把 .wolf/ GeneratedPluginRegistrant *.apk 等无关脏文件卷进提交（显式 add 目标文件）**。
- 分支：`feature/coverage-phase1`（spec 已在其上）。迁移接当前 head `o1l1`，revision id `p1m2`。
- 显示名/懒生成/翻译等既有机制零改动。

---

### Task 1 [OPUS]: recognition_events 表 + 服务端埋点 + phash 字段 + confirm 端点

**Files:**
- Create: `backend/app/models/recognition_event.py`
- Create: `backend/alembic/versions/p1m2_add_recognition_events_and_museum_stats.py`
- Modify: `backend/app/models/museum.py`（加 stats JSONB 列）
- Modify: `backend/app/services/recognition/service.py`（记录事件 + 响应加 phash + engine 追踪）
- Modify: `backend/app/api/v1/endpoints/recognize_global.py`（confirm 端点）
- Test: `backend/tests/unit/models/test_recognition_event.py`、`backend/tests/unit/services/recognition/test_service.py`（追加）、`backend/tests/unit/api/test_recognize_global.py`（追加）

**Interfaces:**
- Produces:
  - `RecognitionEvent(id, museum_slug str可空, phash str, outcome str, top_qid str可空, top_score float可空, confirmed_qid str可空, language str, engine str, created_at)`——engine ∈ `vector|vector_crops|text|cache|none`。
  - `Museum.stats`：`MutableDict.as_mutable(JSON().with_variant(JSONB,"postgresql"))`, default dict（模式抄 `museum_object.py:49` 的 attributes）。
  - 迁移 `p1m2`：建 `recognition_events` 表（`phash` 建索引、`museum_slug` 建索引）+ `museums` 加 `stats` JSONB server_default '{}'。down_revision="o1l1"。
  - `record_event(db, *, museum_slug, phash, outcome, top_qid, top_score, language, engine) -> None`（`app/services/recognition/events.py` 新建亦可放 model 旁——放 `app/services/recognition/events.py`；内部自行 commit 独立小事务或 flush 随主事务均可，但**任何异常吞掉只记日志**）。
  - 识别响应新增 `"phash": <感知哈希>`（三档都带；缓存命中的响应体里也有——缓存写入前就放进 out）。
  - `POST /api/v1/recognize/confirm`：JSON body `{"phash": str, "qid": str}`；行为=更新**最近 24h 内该 phash 最新一条**事件的 confirmed_qid；无匹配事件也返回 204（fire-and-forget）；无鉴权要求（写的是自家匿名统计，qid 必须存在于目录否则忽略）。
- 埋点位置：`service.recognize()` 内、缓存判定之后结果确定之处统一落一次（缓存命中 engine="cache"；向量命中 engine="vector" 或触发过裁剪的 "vector_crops"；GPT 链命中/未收录 engine="text"；识别器全不可用 engine="none"）。engine 追踪用局部变量随流程赋值。

- [ ] **Step 1: 失败测试**——模型往返+唯一性无(允许同 phash 多行)；service 埋点(三档各 1 例断言事件行字段, fake redis/embed 注入沿用既有模式);响应含 phash;confirm 端点 204+回填断言+乱 phash 也 204。测试骨架自行按既有 test_service.py/test_recognize_global.py 模式写（fixture 复用）。
- [ ] **Step 2: RED 确认。**
- [ ] **Step 3: 实现**（模型/迁移抄 o1l1 模式;service 埋点在 `if redis is not None: ... setex` 附近统一出口处调 record_event;out["phash"]=phash 在构造 out 时加）。
- [ ] **Step 4: GREEN**：`cd backend && python -m pytest tests/unit/models/test_recognition_event.py tests/unit/services/recognition/ tests/unit/api/ tests/integration/test_recognize_flow.py -v` 无回归（既有断言若逐键比对响应体需容忍新 phash 键——只允许为此调整断言方式,不许改语义）。
- [ ] **Step 5: Commit** `feat(coverage): recognition_events埋点(KPI+展陈证据一表两吃)+响应phash+confirm端点`

---

### Task 2 [SONNET]: catalog 收无图 stub（P18/P276 OPTIONAL）

**Files:**
- Modify: `backend/app/services/enrichment/sources/wikidata.py`（QUERY 两处）
- Modify: `backend/app/services/enrichment/sources/wikidata_catalog.py`（image 可空 + p276 透传）
- Modify: `backend/museums.yaml`（orsay fetch_limit 6000→12000，注释更新）
- Test: `backend/tests/unit/services/enrichment/test_wikidata_catalog.py`（追加）

**Interfaces:**
- Produces: StubRecord 现在可 `image_url=None, image_urls=[]`（importer 已天然支持空 images——`object_importer.py:82` `images or ...` 为空即不建图行，无需改）；`raw` 里带 `p276`（Wikidata 位置 QID 串或 None）供 Task 4 读。
- QUERY 改动（`wikidata.py:16` 起的 QUERY 常量）：
  - `?item wdt:P18 ?image .` → `OPTIONAL {{ ?item wdt:P18 ?image . }}`
  - SELECT 变量列表加 `?p276`；WHERE 加 `OPTIONAL {{ ?item wdt:P276 ?p276 . }}`
- `wikidata_catalog.list`：`_wd._v(row,"image")` 已是安全取值（None 即无图）——确认无图行不进 `image_urls` 且首图逻辑不炸；p276 取值 `(_wd._v(row,"p276") or "").rsplit("/",1)[-1] or None` 存 `raw["p276_qid"]`。

- [ ] **Step 1: 追加失败测试**

```python
def test_wikidata_catalog_imageless_stub():
    """P18 OPTIONAL:无图行也产 StubRecord(image_url None,image_urls 空)。"""
    row = _row("Q9", "NoImage", 3)
    row.pop("image", None)
    out = list(WikidataCatalog(run_query=lambda s: [row] if "OFFSET 0" in s else []).list(_Cfg()))
    assert len(out) == 1 and out[0].image_url is None and out[0].image_urls == []


def test_wikidata_catalog_query_image_optional_and_p276():
    captured = {}

    def fake(sparql):
        captured["q"] = sparql
        return []

    list(WikidataCatalog(run_query=fake).list(_Cfg()))
    assert "OPTIONAL {" in captured["q"] and "wdt:P18" in captured["q"]
    assert "wdt:P276" in captured["q"]


def test_wikidata_catalog_p276_passthrough():
    row = _row("Q9", "A", 3)
    row["p276"] = {"value": "http://www.wikidata.org/entity/Q123456"}
    out = list(WikidataCatalog(run_query=lambda s: [row] if "OFFSET 0" in s else []).list(_Cfg()))
    assert out[0].raw.get("p276_qid") == "Q123456"
```

（`_row`/`_Cfg` 为该测试文件既有 helper；若 `_row` 默认带 image 键按上面 pop 处理；分页判定条件按既有 helper 的 fake 模式调整——不确定就看文件里现有 fake 怎么写。注意 `test_wikidata_catalog_query_requires_image` 这个既有测试断言"查询必须含 P18 必选"——**其语义已被本任务推翻，允许改写成断言 OPTIONAL**，这是 spec 驱动的行为变更。）

- [ ] **Step 2: RED。**
- [ ] **Step 3: 实现**（QUERY 两处 OPTIONAL + SELECT 加 ?p276；list() 里 first_img 逻辑已安全；p276_qid 塞 raw；museums.yaml orsay `fetch_limit: 12000  # 全条目5353+多P31/多图重复行`）。
- [ ] **Step 4: GREEN** `python -m pytest tests/unit/services/enrichment/ -v` 无回归。
- [ ] **Step 5: Commit** `feat(coverage): catalog收无图stub(P18/P276 OPTIONAL,文字可识别层入库)`

---

### Task 3 [OPUS]: 列表/计数有图过滤 + 馆页双数字

**Files:**
- Modify: `backend/app/services/museum_repo.py`（list_objects 与分类计数加有图过滤；pack 加双数字）
- Test: `backend/tests/unit/services/test_museum_repo.py`（若存在则追加；否则 `tests/unit/services/test_museum_repo_coverage.py` 新建，fixture 模式抄 recognition 的 sqlite StaticPool）

**Interfaces:**
- 有图过滤定义：`EXISTS (ObjectImage where object_id=o.id AND (image_key IS NOT NULL OR source_url IS NOT NULL) AND role != 'view_quarantine')`——即"有任何可展示图"。落为可复用的查询条件 helper `_has_image_clause()`（供 list 与计数两处用，读 museum_repo 现状定最顺写法：exists() 子查询）。
- `list_objects`（`museum_repo.py:502` 起）与分类计数（`:305` 附近 group_by 查询）都加该过滤。
- `get_museum_pack` 响应加：`"catalog_count": <有图件数>, "archive_count": <总件数>`——**优先读 `museum.stats`**（Task 7 回写），stats 缺失时现场 count 兜底（保证语义即时正确）。加法字段。
- Consumes: Task 7 会写 `museum.stats["catalog_count"|"archive_count"]`。

- [ ] **Step 1: 失败测试**：建 1 有图件+1 无图 stub → list_objects 只回有图；分类计数不含 stub；pack 含 catalog_count=1, archive_count=2（无 stats 时现场算）；stats 存在时优先读 stats 值。
- [ ] **Step 2-4: RED→实现→GREEN**（`python -m pytest tests/unit/services/ tests/unit/api/ -v` 无回归——注意详情/内容端点对无图件应照常工作,列表过滤不影响 qid 直达）。
- [ ] **Step 5: Commit** `feat(coverage): 列表与分类计数有图过滤+馆页双数字(在线图录N·档案M)`

---

### Task 4 [SONNET]: 展陈状态模块 display_state.py

**Files:**
- Create: `backend/app/services/coverage/__init__.py`（空）
- Create: `backend/app/services/coverage/display_state.py`
- Test: `backend/tests/unit/services/coverage/test_display_state.py`

**Interfaces:**
- Produces:
  - `STATUS = ("CONFIRMED_ON_DISPLAY","LIKELY_ON_DISPLAY","TEMPORARY_EXHIBITION","NOT_ON_DISPLAY","UNKNOWN")`
  - `recompute_display(db, museum_slug: str, *, traffic_days: int = 30) -> dict`：对该馆全部对象重算 `attributes["display"]`，返回 `{"confirmed": n, "likely": n, "unknown": n}`。
  - 规则（spec ③）：近 `traffic_days` 天 `recognition_events` 中该 qid 有 `outcome='match'` 或 `confirmed_qid=qid` → CONFIRMED_ON_DISPLAY（evidence 加 `{"source":"recognition_traffic","type":"confirmed_scan","at":ISO,"detail":"n=<次数>"}`）；否则 `attributes["p276"]`（Task 2 的 raw 由 importer 存入 attributes——见下）或 evidence 里已有 location_claim → LIKELY；否则 UNKNOWN。已有 evidence 数组**追加去重**（同 source+type 只留最新），不清空外部适配器写入的证据。
  - `add_evidence(obj, *, source, type, detail=None, location=None, confidence=None) -> None`：往 `attributes["display"]["evidence"]` 追加并更新 status/confidence/verified_at 的纯函数（Task 6 Joconde 用）。
- **p276 入 attributes**：object_importer 的 attributes 已透传 `art["attributes"]`——catalog_loader 组装 art 时把 `raw["p276_qid"]` 放进 `attributes["p276"]`。检查 `backend/app/services/enrichment/catalog_loader.py` 组装点，加一行（本 task 一并做，带测试）。

- [ ] **Step 1: 失败测试**

```python
"""展陈状态汇总:流量证据→CONFIRMED;P276→LIKELY;无→UNKNOWN;evidence追加去重。"""
# fixture: sqlite(Museum/MuseumObject/ObjectImage/RecognitionEvent 表) 抄 test_object_embedding.py 模式
# 用例1: 造 match 事件(qid=Q1,15天前) → recompute → Q1 display.status==CONFIRMED_ON_DISPLAY, evidence 含 recognition_traffic
# 用例2: Q2 attributes["p276"]="Q123" 无事件 → LIKELY_ON_DISPLAY
# 用例3: Q3 全无 → UNKNOWN
# 用例4: 事件在 40 天前(超窗) → 不算 confirmed(落到 LIKELY/UNKNOWN)
# 用例5: 先 add_evidence(joconde location_claim) 再 recompute → evidence 两条共存,joconde 不被清掉
# 用例6: add_evidence 同 source+type 重复调用 → 只留最新一条
```

（测试代码按上述用例完整写出——每个用例独立函数，断言 attributes["display"] 的 status/evidence 内容。）

- [ ] **Step 2-4: RED→实现→GREEN**（`python -m pytest tests/unit/services/coverage/ tests/unit/services/enrichment/ -v`）。
- [ ] **Step 5: Commit** `feat(coverage): 展陈状态模块(流量证据CONFIRMED/P276 LIKELY/evidence追加去重)+p276入attributes`

---

### Task 5 [OPUS]: view 自动治理（vet 升级 + 入库闸 + 图集白名单）

**Files:**
- Modify: `backend/scripts/vet_view_images.py`（策略升级：删/隔离/保留三段）
- Modify: `backend/app/services/recognition/embeddings.py`（embed_image_row 对 role=view 的前置闸）
- Modify: `backend/app/services/museum_repo.py`（详情图集查询排除 `view_quarantine`）
- Test: `backend/tests/unit/scripts/test_vet_view_images.py`（改造）、`backend/tests/unit/services/recognition/test_embeddings.py`（追加）

**Interfaces:**
- `vet_views(db, *, delete_below=0.25, quarantine_below=0.4, dry_run=False) -> dict`
  返回 `{"checked": n, "deleted": n, "quarantined": n}`：sim<delete_below → 删图行+向量；
  delete_below≤sim<quarantine_below → `role="view_quarantine"` + 删其向量（不再索引）；≥ 保留。
  dry_run 只打印。CLI argparse 对应 `--delete-below/--quarantine-below/--dry-run`。
- `embed_image_row` 闸：`row.role=="view"` 且该对象 primary 已有向量时——sim<0.25 → 删 row 返回 False；<0.4 → row.role="view_quarantine" 返回 False（不建向量）；≥0.4 正常。primary 向量尚不存在 → 照常建向量（后续 vet 兜底）。注释：纯自动无人审(spec ④);错杀极端角度由照片飞轮补回。
- 详情图集（`museum_repo.py:381` 附近 images 查询）：加 `ObjectImage.role != "view_quarantine"` 过滤。
- ⚠️ 既有 vet 测试的行为断言要按新策略改（0.1→删，0.32 类→隔离，0.9→保留）；沿用其 fixture。

- [ ] **Step 1: 失败测试**：三段行为各一例+dry_run 零改动+embed 闸三段+图集过滤（详情查询不回隔离图）。
- [ ] **Step 2-4: RED→实现→GREEN**（`python -m pytest tests/unit/scripts/ tests/unit/services/recognition/ tests/unit/services/ -v`）。
- [ ] **Step 5: Commit** `feat(coverage): view自动治理(0.25删/0.4隔离role=view_quarantine/入库闸/图集白名单)`

---

### Task 6 [OPUS]: Joconde 区域适配器样板

**Files:**
- Create: `backend/app/services/coverage/joconde.py`
- Test: `backend/tests/unit/services/coverage/test_joconde.py`（fake http 注入，不打真网）

**Interfaces:**
- 先探明 API（**本任务含调研步骤**）：Joconde 开放数据在 data.culture.gouv.fr（opendatasoft 平台），按 Joconde 编号（我们目录 `external_ids["P347"]`——确认 importer 落到哪个字段，object_importer/StubRecord.external_ids 的去向）查记录，取 `localisation`/展出相关字段。**若实测 API 不可用/字段与假设不符：报 BLOCKED 附调研发现，不要硬编一个查不到东西的实现。**
- `fetch_joconde_evidence(joconde_ref: str, *, http_get=None) -> dict | None`：返回 `{"location": str|None, "detail": <原始字段摘录>}` 或 None。UA `GoMuseumEnrichment/1.0 (appcraft008@gmail.com)`，sleep ≥0.2s。
- `enrich_museum_display(db, museum_slug, *, fetch=None, limit=None) -> dict`：遍历该馆有 P347 的对象 → fetch → `display_state.add_evidence(obj, source="joconde", type="location_claim", location=..., detail=...)`；返回计数。CLI 入口 `python -m app.services.coverage.joconde <slug>`（或挂 onboard 子命令 `display-evidence --museum <slug>`——选 onboard 子命令，与其余管线一致）。
- Consumes: `display_state.add_evidence`（Task 4）。

- [ ] **Step 1: 调研**（curl 探 API、找 P347 在库内字段位置，写进报告）。
- [ ] **Step 2: 失败测试**（fake http 返回 canned JSON → evidence 写入断言;无 P347 对象跳过;fetch None 容错）。
- [ ] **Step 3-4: RED→实现→GREEN。**
- [ ] **Step 5: Commit** `feat(coverage): Joconde区域适配器样板(P347→localisation展陈证据,覆盖全法博物馆)`

---

### Task 7 [SONNET]: 覆盖率报告 CLI + museums.stats 回写

**Files:**
- Create: `backend/scripts/coverage_report.py`（独立脚本；onboard 挂子命令 `coverage-report` 转调它）
- Modify: `backend/scripts/onboard.py`（子命令）
- Test: `backend/tests/unit/scripts/test_coverage_report.py`

**Interfaces:**
- `build_report(db, museum_slug, *, traffic_days=30) -> dict`：
  ```python
  {"archive_count": 总件数, "catalog_count": 有图件数, "textonly_count": 差值,
   "embeddings": 向量数, "images_with_key": 物化图数,
   "views": {"objects": 有view件数, "images": view图数, "quarantined": 隔离数},
   "display": {"CONFIRMED_ON_DISPLAY": n, "LIKELY_ON_DISPLAY": n, "UNKNOWN": n, ...},
   "kpi": {"attempts": n, "hits": match数+confirmed数, "rate": 0.xx | None},
   "generated_at": ISO}
  ```
  kpi 从 recognition_events 近 traffic_days 聚合（该馆 slug 或 top_qid 归属该馆——用 museum_slug 列即可，attempts=0 时 rate=None 显示"待累计"）。
- `write_stats(db, museum_slug, report) -> None`：报告整体写 `museum.stats["coverage"]`，另冗余顶层 `stats["catalog_count"]/["archive_count"]`（Task 3 pack 读这里）。
- CLI 打印人类可读版（分行树状,参考 spec ⑤ 样例）+ `--json` 输出原始 dict；执行前先调 `display_state.recompute_display`（报告=状态重算的触发点，spec 定"不做实时"）。
- Consumes: Task 4 `recompute_display`、Task 1 事件表、Task 5 quarantine role。

- [ ] **Step 1: 失败测试**：fixture 造 2 有图+1 无图+1 quarantine view+2 事件(1 match 1 unrecognized) → build_report 各数字断言；write_stats 后 museum.stats 可读回；attempts=0 时 rate None。
- [ ] **Step 2-4: RED→实现→GREEN**（`python -m pytest tests/unit/scripts/ -v`）。
- [ ] **Step 5: Commit** `feat(coverage): 覆盖率报告CLI(coverage-report)+museums.stats回写(报告即状态重算触发点)`

---

### Task 8 [OPUS]: 前端三件套（confirm 上报 + 用户照片 hero + 馆页双数字）

**Files:**
- Modify: `frontend/gomuseum_app/lib/features/recognition/data/models/recognize_response.dart`（加 phash 解析）
- Modify: `frontend/gomuseum_app/lib/features/recognition/data/datasources/recognition_remote_datasource.dart`（confirm 调用）
- Modify: `frontend/gomuseum_app/lib/features/recognition/presentation/pages/camera_page.dart`（确认卡点选→fire confirm；_goGuide 传拍摄照片路径）
- Modify: 馆页 widget（读 pack 的 catalog_count/archive_count 显示一行双数字——找馆页文件：grep "附近博物馆"/museum 卡片或馆详情页）
- Modify: `GmFramedImage` 空图占位（找到其定义文件；null image 时按类目画占位——类目图标已有 GmIcons? 用类目 icon+标题排版的简洁占位，无类目信息时通用画框图形）
- Test: `frontend/gomuseum_app/test/` 相应追加（phash 解析、confirm 请求参数、null-hero 渲染 smoke）

**Interfaces:**
- `RecognizeResponse` 加 `final String? phash;`（`j['phash'] as String?`）。
- datasource 加 `Future<void> confirm({required String phash, required String qid})` → `POST /api/v1/recognize/confirm` JSON body；异常吞掉（fire-and-forget，绝不打扰 UX）。
- camera_page：`_candidateRow` onTap 里在 `_goGuide` 前 fire `confirm(phash, qid)`（response 的 phash 存进 state）；`_goGuide` 增传 `imagePath: <本次拍摄的本地文件路径>`（拍摄 XFile.path 已在 state/流程里——找到相机拍摄结果变量传下去；guide_page 的 GuideArgs.imagePath 已支持 FileImage 渲染，零改动）。相册上传同理（XFile.path 同样可用）。
- 馆页双数字文案（i18n）：`在线图录 {n} 件 · 档案条目 {m} 件（可识别/搜索）`——l10n 各语言键新增（十语翻译按既有 arb 模式，机器翻译水平即可）。
- 契约容错：catalog_count/archive_count 均 `as int?`，null 时不显示该行（老后端兼容）。

- [ ] **Step 1: 测试先行**（phash 解析/缺省 null；confirm datasource 参数断言;可测则测 GmFramedImage null 渲染不炸）。
- [ ] **Step 2-3: RED→实现。**
- [ ] **Step 4: `flutter analyze && flutter test` 全绿零新告警。**
- [ ] **Step 5: Commit** `feat(app): 确认卡上报confirm+用户照片hero直通讲解页+馆页双数字+无图占位`

---

### Task 9 [调度者 inline]: staging 全量跑 + 契约回写 + 验收

- [ ] PR `feature/coverage-phase1` → staging，CI 绿合并（自动部署+迁移 p1m2）。
- [ ] staging 容器：`onboard orsay catalog --target staging`（收全 5353 条目含无图）→ `names` → `vet_view_images`（真执行：预期删 ~14、隔离 ~46）→ `onboard orsay display-evidence --museum orsay`（Joconde）→ `onboard orsay coverage-report`（核对报告各数字、stats 回写、馆页双数字 API）。
- [ ] E2E：拍已收录件 → 确认卡点选 → confirm 落库断言（SQL 查 confirmed_qid）；搜索/墙签路径命中无图 stub → 讲解页占位 hero；列表无 stub；KPI 报表出数。
- [ ] 契约回写（museum-api-contract.md）：分层收录原则替换"有图才收录"、北极星 KPI 口径、展陈状态模型、上新馆配方更新（…→vet(执行)→display-evidence→coverage-report）、pack 双数字与 /recognize/confirm、响应 phash 字段。更新历史加行。
- [ ] 记忆/ledger 更新；汇报（staging 验证完等用户点 prod）。
