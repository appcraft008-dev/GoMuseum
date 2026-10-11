# 无图作品不对用户开放 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 搜索、识别、懒生成、馆包与馆数量统一只对用户开放有图作品;被隐藏的识别命中记入 `text_trace.hidden_imageless`。

**Architecture:** 有图口径 = `must_see.has_image_clause`(任意非隔离图)。搜索索引条目加 `has_image`,搜索与识别文字链据此过滤(文字链在全量上匹配、取 limit=50 后再过滤以免被截断)。懒生成对无图 stub 返回 `no_image`;馆包与馆列表件数改为有图件数、`archive_count` 置 null。前端讲解页认 `no_image`。

**Tech Stack:** FastAPI、SQLAlchemy、pytest;Flutter(一处分支 + widget 测试)。

**Spec:** `docs/superpowers/specs/2026-10-11-hide-imageless-objects-design.md`

## Global Constraints

- 有图 = 至少一张 `image_key` 或 `source_url` 非空且 `role != 'view_quarantine'` 的图。
- 内容 / 音频 / 分享 / 足迹端点对已有内容**不变**,不 404。
- 懒翻译**不拦**;只拦无图 stub 的懒生成,且在方案 A 额度检查之前(不扣额度)。
- 编号精确搜到无图件也不返回(用户 10-11 定)。
- 识别缓存键前缀 `recog3` → `recog4`。
- `unavailable_reason` 新取值 `"no_image"`;`archive_count` 返回 null;`artwork_count` = 有图件数。
- 后端测试:`cd backend && nice -n 19 $PY -m pytest -q --no-cov -p no:cacheprovider <files>`,
  `$PY=~/Library/Caches/pypoetry/virtualenvs/gomuseum-backend-eWQPCnDy-py3.13/bin/python`。
- 前端测试:`cd frontend/gomuseum_app && nice -n 19 flutter test <file>`。

## Review Focus

1. 文字链 top 5 全是无图件、第 6 名有图且过门槛 → 候选里必须有它(limit 截断坑)。→ Task 2。
2. 馆藏号直判命中无图件 → 不直判、继续模糊匹配,且 `hidden_imageless` 按 qid 去重。→ Task 2。
3. 只有 view 图(无 primary)的件:搜索可见、缩略图为空。→ Task 1。
4. 匿名请求打开无图 stub 也拿到 `no_image`,且不点火。→ Task 3。
5. 馆包 `artworks=False` 分支 `artwork_count` 也是有图件数。→ Task 4。

---

### Task 1: 搜索索引 `has_image` + 搜索过滤

**Files:** Modify `backend/app/services/search/inprocess.py`(`_build_global`、`search`);Test `backend/tests/unit/services/search/test_inprocess.py`、`backend/tests/integration/test_search_endpoint.py`

**Produces:** 索引条目键 `"has_image": bool`(任意非隔离图口径)。

- [ ] Step 1 测试:把 `test_no_image_stub_in_results_with_flag` 改为 `test_no_image_stub_not_in_results`(`"starry"` 只返回 Q45585);新增 `test_view_only_object_is_searchable_without_thumbnail`(只有 role=view 图的件可搜到、`thumbnail is None`);新增 `test_inventory_exact_hit_on_imageless_not_returned`;新增 `test_index_entry_has_image_flag`(view_quarantine 图不算有图)。
- [ ] Step 2 跑,确认新/改测试失败。
- [ ] Step 3 实现:`_build_global` 另查一次
  ```python
  has_img = {
      oid
      for (oid,) in db.query(ObjectImage.object_id)
      .filter(
          or_(ObjectImage.image_key.isnot(None), ObjectImage.source_url.isnot(None)),
          ObjectImage.role != "view_quarantine",
      )
      .distinct()
  }
  ```
  条目加 `"has_image": oid in has_img`;`search()` 里 `index = [e for e in index if e.get("has_image")]`(与 visible 过滤同处)。改模块 docstring 与 `search.py` 端点 docstring 里「无图 stub 照常出现」为「无图件不对用户开放(spec 2026-10-11 方案 B)」。
- [ ] Step 4 跑 search 两个测试文件 + `tests/unit/services/matching/test_index.py`,全过。
- [ ] Step 5 commit `feat(search): 无图作品不出现在搜索结果`

### Task 2: 识别文字链过滤 + 隐藏记录 + 缓存键

**Files:** Modify `backend/app/services/recognition/service.py`(`_cache_key`、`_compute` 文字链段);Test `backend/tests/integration/test_recognize_flow.py`

**Consumes:** Task 1 的 `has_image`。

- [ ] Step 1 测试(fixture 里补一件有图、一件无图同名件;已有依赖无图件 Q152509 当候选的测试按新规则改断言):
  - `test_text_candidates_exclude_imageless_and_record_hidden`:无图件得分最高 → 候选不含它、含有图件,`text_trace["hidden_imageless"] == [{"qid":…, "score":…, "via":"match"}]`。
  - `test_text_candidates_not_truncated_by_hidden`:构造 5 件同名无图 + 1 件同名有图(都过门槛)→ 候选含有图那件。
  - `test_inv_hit_on_imageless_falls_back_to_match`:馆藏号+作者命中无图件 → `outcome != "match"`,hidden 含 `via="inv"`,同 qid 不重复。
  - `test_all_imageless_unrecognized`:只命中无图件 → `unrecognized`,`reason == "low_confidence"` 或 `not_in_catalog` 维持原判据。
  - `test_cache_key_prefix_recog4`。
- [ ] Step 2 跑,确认失败。
- [ ] Step 3 实现:`_cache_key` 前缀改 `recog4`(注释:无图件可能在旧缓存里,方案 B);文字链:
  ```python
  img_ok = {e["qid"] for e in index if e.get("has_image")}
  hidden: dict[str, dict] = {}
  inv_hit = inv_artist_hit(index, queries + label_lines, artist_hints)
  if inv_hit and inv_hit not in img_ok:
      hidden[inv_hit] = {"qid": inv_hit, "score": 1.0, "via": "inv"}
      inv_hit = None
  text_trace["inv_hit"] = inv_hit
  if inv_hit:
      results, raw = [(inv_hit, 1.0)], [[inv_hit, 1.0, True]]
  else:
      # limit=50:匹配核心按 limit 截断(core.py),先截 5 再去无图件会丢掉有图候选
      results, raw = match_with_trace(..., limit=50, ...)
      for q, s in results[:3]:
          if s >= LOW and q not in img_ok:
              hidden.setdefault(q, {"qid": q, "score": round(s, 3), "via": "match"})
      results = [(q, s) for q, s in results if q in img_ok]
  if hidden:
      text_trace["hidden_imageless"] = list(hidden.values())
  ```
  其余(`shown`、`single_direct`、候选组装)沿用过滤后的 `results`。
- [ ] Step 4 跑 `test_recognize_flow.py`、`test_recognition_flow.py`、`tests/unit/services/recognition/`,全过。
- [ ] Step 5 commit `feat(recognition): 文字链不给无图作品,被隐藏的命中记入 text_trace`

### Task 3: 懒生成对无图 stub 返回 `no_image`

**Files:** Modify `backend/app/services/enrichment/lazy.py`(`maybe_trigger`、新增 `imageless_stub`)、`backend/app/api/v1/endpoints/museums.py`(`object_content`);Test `backend/tests/integration/test_lazy_generation.py`、`backend/tests/integration/test_object_content_endpoint.py`

**Produces:** `imageless_stub(db, obj) -> bool`;`maybe_trigger` 可返回 `"no_image"`。

- [ ] Step 1 测试:无图 stub → `maybe_trigger` 返回 `"no_image"`、不调度、Redis 无计数;有图 stub → 照常调度;无图 ready 件缺语言 → 懒翻译照常;端点带令牌与匿名两种请求打开无图 stub → `unavailable_reason == "no_image"`、`generating is False`。(注意 `test_lazy_generation.py` 的 fixture 里 Q1 无图:原有懒生成测试要给 Q1 补一张图,否则全部变成 no_image。)
- [ ] Step 2 跑,确认失败。
- [ ] Step 3 实现:
  ```python
  def imageless_stub(db, obj) -> bool:
      """无图 stub 不点火(方案 B):用户本就到不了它,生成了也没人看,还会编外观描写。"""
      from app.services.must_see import has_image_clause

      if obj.content_status != "stub":
          return False
      return not db.query(MuseumObject.id).filter(MuseumObject.id == obj.id, has_image_clause()).first()
  ```
  `maybe_trigger` 在 `wants_generation` 判定后、`daily_budget_exhausted` 前:`if wants_generation and imageless_stub(db, o): return "no_image"`。
  端点:登录走 `maybe_trigger`;匿名时 `reason = "no_image" if imageless_stub(db, obj) else None`(按 qid 查 obj,查不到交给后面的 404)。
- [ ] Step 4 跑两测试文件 + `test_lazy_caps.py` + `test_visibility_gate.py` + `test_share.py`,全过。
- [ ] Step 5 commit `feat(lazy): 无图待完善作品不点火,返回 no_image`

### Task 4: 馆包与馆列表口径

**Files:** Modify `backend/app/services/museum_repo.py`(`list_museums`、`get_museum_pack`);Test `backend/tests/integration/test_museum_repo.py`

- [ ] Step 1 测试:fixture 加一件无图件 → `list_museums` 的 `artwork_count` 只算有图;`get_museum_pack` 的 `artworks` 不含无图件、`artwork_count`(两个分支)= 有图件数、`archive_count is None`、键集合不变。
- [ ] Step 2 跑,确认失败。
- [ ] Step 3 实现:`list_museums` 的 outerjoin 计数改为 `func.count(MuseumObject.id).filter(has_image_clause())`(SQLAlchemy `FILTER` 子句;sqlite 测试与 Postgres 都支持)或拆成子查询;`get_museum_pack` 的 `objs` 查询加 `.filter(_has_image_clause())`;`artwork_count = catalog_count`;`"archive_count": None` 并加注释(用户 10-11 定:档案条目不再对用户展示,后端照算 `archive_count` 变量供内部用——变量保留则删,不留死代码:直接删掉 archive_count 那条 COUNT)。
- [ ] Step 4 跑 `test_museum_repo.py`、`test_museums_endpoint_db.py`、`test_museum_pack_intro.py`、`test_pack_and_content_facts.py`、`tests/unit/services/test_museum_repo_coverage.py`,全过。
- [ ] Step 5 commit `feat(museums): 馆件数改为有图件数,档案条目不再对用户显示`

### Task 5: 前端讲解页认 `no_image`

**Files:** Modify `frontend/gomuseum_app/lib/features/content/data/models/object_content_model.dart`、`lib/features/guide/presentation/pages/guide_page.dart`;Test `frontend/gomuseum_app/test/features/content/object_content_model_test.dart`(+ 现有讲解页 widget 测试文件里加一条,若无则模型测试即可)

- [ ] Step 1 测试:`unavailable_reason: "no_image"` → `noImage == true`、`dailyCapReached == false`。
- [ ] Step 2 跑确认失败。
- [ ] Step 3 实现:模型加 `bool get noImage => unavailableReason == 'no_image';`;`guide_page.dart` 的「3) 非生成中且无内容」处:`if (content.status == ContentStatus.empty || content.noImage)` → `_A5UnavailableScaffold`(默认文案「暂无讲解」)。
- [ ] Step 4 `flutter analyze` + 该测试文件通过。
- [ ] Step 5 commit `feat(guide): 无图作品显示暂无讲解,不给假重试`

### Task 6: 契约与 backlog

- [ ] `docs/architecture/museum-api-contract.md`:`unavailable_reason` 段补 `no_image`;馆包 `archive_count` 改 null、`artwork_count` 口径;搜索段「无图 stub 可搜」改为不返回;变更记录加 2026-10-11 方案 B。
- [ ] `docs/ops/backlog.md`:第三节方案 B 行删除并移到「最近关闭」(写 PR 号);加一条「前端 no_image 分支随下个版本发包」。
- [ ] commit `docs: 方案B回写契约与backlog`
