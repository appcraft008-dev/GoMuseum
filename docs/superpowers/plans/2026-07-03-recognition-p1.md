# 识别机制 P1 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 拍照→GPT视觉查询+墙签OCR→目录接地匹配→三档呈现(直开/确认卡/未收录+记需求)的识别闭环。

**Architecture:** 新包 `app/services/recognition/`（vision 识别器 / matcher 匹配层 / demands 需求记录 / service 编排），加法端点 `POST /museums/{slug}/recognize`；老 `/recognition` 不动标 deprecated。匹配层是不变核心（P2 CLIP 只替换引擎位）。

**Tech Stack:** GPT-4o-mini vision（复用 default_complete 风格注入）、stdlib difflib（模糊匹配）、既有 image_service（哈希/校验）、Redis（结果缓存）、SQLAlchemy+alembic（demands 表）。

## Global Constraints

- spec: `docs/superpowers/specs/2026-07-03-recognition-design.md`
- **零新依赖**；识别器/匹配层注入可测（离线不触网）
- R1：candidates 只当查询，响应里绝不出现未匹配到目录的名字当身份
- 阈值常量 `HIGH=0.85` `LOW=0.5`（真实数据校准前的初值）
- `outcome/reason` 机器码不译；`title/artist` 按 language 走显示名规则（`_resolve_name`）
- 批处理纪律不适用（这是在线请求路径），但缓存/超时护栏必须有

---

### Task 1: 识别器 vision.py

**Files:**
- Create: `backend/app/services/recognition/__init__.py`（空）
- Create: `backend/app/services/recognition/vision.py`
- Test: `backend/tests/unit/services/recognition/test_vision.py`

**Interfaces:**
- Produces: `identify(image_b64: str, mode: str = "artwork", complete=None) -> dict`
  返回 `{"candidates": [{"title": str, "artist": str|None}], "label_text": str|None, "self_confidence": "high|medium|low"}`；
  `complete(system, user_content) -> str`（user_content 为 OpenAI 多模态 content 列表）；默认走 gpt-4o-mini vision。
  异常/坏 JSON → 返回空 candidates（不抛，服务层按 no_candidates 处理）。

- [ ] RED：fake complete 返回合法 JSON → candidates/label_text 解析正确；坏 JSON → 空结构不抛；`mode="label"` 的 system prompt 含 "transcribe" 不含 "identify"
- [ ] GREEN：两个 prompt（artwork=识别+顺带转写可见文字；label=纯转写）；`_parse_json` 复用 content_enricher 的；默认 complete 用 OpenAI 客户端（`_get_openai_client`）带 30s 超时
- [ ] 全量绿 → commit `feat(recognition): vision 识别器(候选名+墙签转写,注入可测)`

### Task 2: 匹配层 matcher.py（不变核心）

**Files:**
- Create: `backend/app/services/recognition/matcher.py`
- Test: `backend/tests/unit/services/recognition/test_matcher.py`

**Interfaces:**
- Produces:
  - `normalize(s: str) -> str`（小写/NFD 去音符/去标点/压空白）
  - `build_index(db, museum_id) -> list[dict]`（每件：`{"qid", "names": set[str]（title_i18n 全语种+title_en/zh 归一化）, "artists": set[str]}`；进程内缓存 `{museum_id: (ts, index)}` TTL 600s，`_index_cache.clear()` 供测试）
  - `match(index, queries: list[str], label_lines: list[str]) -> list[tuple[str, float]]`（按 score 降序去重 qid；标题相似度为主(difflib ratio)，作者名出现在 queries/label 中 +0.1 封顶 1.0）
  - 常量 `HIGH = 0.85`、`LOW = 0.5`

- [ ] RED：
  - `normalize("Théodore, Géricault!") == "theodore gericault"`
  - zh 查询《世界的起源》命中 title_i18n.zh 该件 score≥HIGH
  - 近似查询 "Origin of the World" 命中 en 名
  - 墙签多行 `["Le Radeau de la Méduse", "Théodore Géricault", "1819"]` 逐行匹配命中且作者行加分
  - 无关查询 "Mona Lisa" → 最高分 < LOW
  - 索引缓存：同 museum_id 二次 build 不再查库（fake db 计数）
- [ ] GREEN 实现 → 全量绿 → commit `feat(recognition): 目录接地匹配层(多语模糊+作者加分+索引缓存)`

### Task 3: 需求记录 demands

**Files:**
- Create: `backend/app/models/recognition_demand.py`（`recognition_demands`：id UUID/museum_slug/phash(index)/label_text/gpt_candidates JSON/language/hit_count default 1/created_at/updated_at；UniqueConstraint(museum_slug, phash)）
- Create: `backend/alembic/versions/l1i8_add_recognition_demands.py`（照 k1h7 惯例手写）
- Create: `backend/app/services/recognition/demands.py`
- Test: `backend/tests/unit/services/recognition/test_demands.py`

**Interfaces:**
- Produces: `record_demand(db, slug, phash, *, label_text=None, candidates=None, language="zh") -> int`（返回该记录当前 hit_count；同 (slug,phash) 幂等 +1，label_text/candidates 有值则更新）

- [ ] RED：首记 hit_count=1；同 phash 再记 =2 且不新增行；不同 phash 各自成行
- [ ] GREEN → 全量绿 → commit `feat(recognition): 未收录需求记录(phash 幂等聚合)`

### Task 4: 编排 service.py + 端点

**Files:**
- Create: `backend/app/services/recognition/service.py`
- Modify: `backend/app/api/v1/endpoints/museums.py`（加 `POST /{slug}/objects/recognize`…实际路由 `POST /{slug}/recognize`）
- Test: `backend/tests/integration/test_recognize_flow.py`

**Interfaces:**
- Consumes: Task1 `identify`、Task2 `build_index/match/HIGH/LOW`、Task3 `record_demand`、`image_service.generate_hash/generate_perceptual_hash/validate_image`、`museum_repo._resolve_name/_sized`
- Produces: `recognize(db, slug, image_bytes, *, language="zh", mode="artwork", identify_fn=None, redis=None) -> dict | None`（未知馆 None；响应形状=spec；Redis 缓存 key `recog2:{slug}:{sha256}` TTL 30 天，redis 不可用时静默跳过）

流程：validate → sha/phash → 缓存查 → identify（注入）→ queries=candidates 标题 + label 行 → match → 分档：
- top≥HIGH → outcome=match（查该 qid 对象 → title/artist 按 language、thumbnail=thumb 档）
- LOW≤top<HIGH → outcome=candidates（top 3 同形状+score）
- else → outcome=unrecognized + reason(no_candidates 若 vision 空/not_in_catalog 若有候选没命中/low_confidence 其余) + record_demand
- label_text 原样透传；结果写缓存。

- [ ] RED（sqlite fixture: 馆+2件带 title_i18n/图；fake identify）：
  - 高置信：identify 返回精确题名 → outcome=match、qid 正确、title 按 language、thumbnail 以 `_thumb.jpg` 结尾
  - 中置信：近似名 → outcome=candidates 1-3 个含 score
  - 未命中：胡编名 → outcome=unrecognized、reason=not_in_catalog、demands 表 +1
  - vision 空 → reason=no_candidates
  - `mode="label"`：identify_fn 收到 mode="label"
  - 未知馆 → None（端点 404）
- [ ] GREEN → 端点接线（UploadFile → bytes；404；返回 dict）→ 全量绿 → commit `feat(recognition): 接地识别端点(三档呈现+缓存+记需求)`

### Task 5: 契约回写(R1-R6) + 前端交接 + PR + staging e2e

**Files:**
- Modify: `docs/architecture/museum-api-contract.md`（新节"§识别(拍照→讲解)":R1-R6 原则+端点契约+三档语义+老端点 deprecated+P2 规划；变更记录）
- Create: `docs/handoff/2026-07-03-recognition-frontend.md`（相机流程：拍→loading→三档 UI（直开/确认卡/未收录卡+「拍下作品旁的说明牌」按钮→mode=label 二拍）；响应字段表；staging 测试法）

- [ ] 契约+交接写好 → 全量测试+black → PR → staging（自动合并）
- [ ] staging e2e：`curl -F "image=@..." "https://staging-api.gomuseum.app/api/v1/museums/orsay/recognize?language=zh"` 用维基下载的《世界的起源》图 → match；随机风景照 → unrecognized+demands 行
- [ ] 汇报（prod 发布照例先问用户）

## Self-Review

- spec 覆盖：R1(matcher 归一/服务分档)✓ R2(mode=label+交接引导)✓ R3(三档)✓ R4(identify_fn 注入=引擎位)✓ R5(demands)✓ R6(P2,契约记录)✓ 缓存护栏✓ 老端点不动✓
- 签名一致：identify/build_index/match/record_demand/recognize 各任务引用一致
- 无占位符
