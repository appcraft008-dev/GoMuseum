# 必看打卡(护照页)Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 每个有必看清单的馆加「必看」护照页:现场拍照识别成功(且扣费通过)盖章,打满一轮发一枚永久勋章,有官网展厅号的标位置。

**Architecture:** 后端只做加法——识别请求带可选 `capture`、事件表加可空列;打卡/轮在读的时候从 `recognition_events` 现算,勋章在 `GET /museums/{slug}/must-see` 算出「本轮已完成」时落 `must_see_medals` 表;展厅号随 `museums.yaml` 部署。App 新增「必看」顶层 tab(护照页)与讲解页临时提示。

**Tech Stack:** FastAPI + SQLAlchemy + Alembic(PostgreSQL,测试用 SQLite);Flutter + Riverpod + Dio + gen-l10n(10 语)。

**Spec:** `docs/superpowers/specs/2026-10-27-must-see-checkin-design.md`(样稿 `docs/superpowers/specs/2026-10-27-must-see-mockups/`)

## Global Constraints

- 契约只做加法:新端点、新可选参数、新可空列;老 App 行为不变。Flutter 解析新字段一律 `as T? ?? 默认值`,禁止裸 `as String`。
- 打卡判据复用 `app/api/v1/endpoints/history.py::_footprint_qid`,不另写一套。
- 30 天:相邻两次打卡间隔 **> 30 天**切轮;恰好 30 天仍同轮。
- 只有 `capture='camera'`、`confirm_source != 'search'`、扣费通过的才算打卡;`capture` 为 NULL(老 App)永不算。
- 十语文案;字号各语言一致,不用 FittedBox 缩字;韩语沿用 U+2060 word joiner 写法。
- 隐身馆沿用 `museum_visible` / `can_preview` 规则,无权限 → 404。
- 不直写 prod 数据库;展厅号、清单改动都走改 `backend/museums.yaml` 的 PR。
- 打卡**只按 `user_id` + `capture='camera'` + qid ∈ 该馆清单**判,**不看 `museum_slug`**(App 走全局端点,事件行 `museum_slug` 为 NULL;测试造行一律 `museum_slug=None`)。
- 后端发出的时间一律带时区:`dt.replace(tzinfo=timezone.utc).isoformat()`(`created_at` 是不带时区的 UTC,与 `entitlements.dart` 约定一致);服务端「现在」= `datetime.utcnow()`。
- 每个任务的后端测试命令:`cd backend && poetry run pytest <path> -q`;前端:`cd frontend/gomuseum_app && flutter test <path>`。提交前 `black`/`isort`/`dart format`(worktree 里钩子不跑,手动跑)。

## Review Focus

1. 老 App 不带 `capture` 的识别:照常 200、照常扣费,事件行 `capture` 为 NULL,永不计入打卡 → Task 2 测试。
2. 两个请求同时算出「本轮已完成」:只落一枚勋章,第二个请求不报错 → Task 3 测试(唯一约束 + IntegrityError 吞掉)。
3. 清单里某个 qid 目录里没有或没有图:必看端点照样列出它(标题回退 qid、缩略图 null),不 500,分母仍是清单件数 → Task 4 测试。
4. 必看页数据里缺 `location`/`medals` 等字段或类型不对:App 不崩,按「无位置/无勋章」画 → Task 6 测试。
5. 讲解页提示:从馆藏列表、搜索、相册进讲解页都不出提示;快门命中但这件不在清单也不出;候选确认慢网下也不漏 → Task 8 测试。

---

### Task 1: 清单支持展厅号写法

**Files:**
- Modify: `backend/app/services/enrichment/catalog.py:57,100`
- Modify: `backend/app/services/must_see.py`
- Test: `backend/tests/unit/services/test_must_see_yaml.py`

**Interfaces:**
- Produces: `MuseumConfig.must_see: list[str]`(不变,仍是 qid 列表);新增 `MuseumConfig.must_see_locations: dict[str, dict]`(qid → `{"wing": str|None, "level": int|None, "room": str|None}`,只收有任一字段的项);`app.services.must_see.MUST_SEE_LOCATION: dict[str, dict[str, dict]]`(slug → qid → location)。

- [ ] **Step 1: 写失败测试** `test_must_see_entry_accepts_dict_with_location`:用 `MuseumCatalog` 解析一段临时 yaml,`must_see: ["Q1", {qid: "Q2", wing: "Denon", level: 1, room: "711"}, {qid: "Q3"}]` → `must_see == ["Q1","Q2","Q3"]`,`must_see_locations == {"Q2": {"wing":"Denon","level":1,"room":"711"}}`。另测 `room: 711`(yaml 里写成数字)解析为字符串 `"711"`。
- [ ] **Step 2: 跑测试确认失败**(`str(dict)` 被当 qid)。
- [ ] **Step 3: 实现**:catalog 解析每项为 `str` 或 `dict`(取 `qid`);`must_see.py` 增 `MUST_SEE_LOCATION`,`_load` 同源。其余引用 `MUST_SEE` 的地方不动。
- [ ] **Step 4: 跑** `poetry run pytest tests/unit/services/test_must_see_yaml.py tests/unit/services/enrichment/test_catalog.py tests/integration/test_catalog_loader.py -q` → PASS。
- [ ] **Step 5: Commit** `feat(must-see): 清单项可带展厅号(wing/level/room)`

### Task 2: 识别带「拍照/相册」,没扣成费就撤销

**Files:**
- Create: `backend/alembic/versions/c1m1_recognition_capture.py`(`revision="c1m1"`, `down_revision="x2t1"`;加可空列 `capture VARCHAR(8)`)
- Modify: `backend/app/models/recognition_event.py`(加 `capture` 列)
- Modify: `backend/app/services/recognition/events.py`(`record_event(..., capture=None) -> uuid.UUID | None` 返回新行 id;新增 `clear_capture`)
- Modify: `backend/app/services/recognition/service.py`(`recognize` / `_compute` / `recognize_billed` 透传 `capture`,含缓存命中那次 `record_event`)
- Modify: `backend/app/api/v1/endpoints/recognize_global.py`(`run_recognition`、`recognize_global`、`recognize_confirm`)
- Modify: `backend/app/api/v1/endpoints/museums.py:325-347`(馆内端点同样收 `capture`)
- Test: `backend/tests/integration/test_recognize_flow.py`(落库与 402;402 场景照 `tests/integration/test_pass_scope_by_museum.py::test_pass_elsewhere_with_no_quota_is_402_for_that_museum` 造)、`backend/tests/unit/api/test_recognize_global.py`(确认路径用现有 `_confirm_client()`;该文件的 `client` fixture 是假 db,只用于参数校验)

**Interfaces:**
- Produces: `RecognitionEvent.capture: str | None`(`"camera"|"gallery"|None`);端点查询参数 `capture: Literal["camera","gallery"] | None = None`(非法值 422);`clear_capture(db, *, event_id=None, phash=None) -> None`(给 `event_id` 清那一行;给 `phash` 清「24h 内该 phash 最新一行」——与 `confirm_event` 改的是同一行;吞异常同 `record_event`)。
- 内部约定:`recognize` 在 `redis.setex` **之后**把本次事件 id 放进 `out["_event_id"]`(不进缓存);缓存命中那次 `record_event` 同样放;`recognize_billed` 第一时间 `pop` 出来。

**撤销规则(capture 只留在扣费通过或按规则免扣的行上):**
- `recognize_billed` 命中之后的整段(从 `if cached == "inflight"` 起到 `return out`)包在 `try: ... except BaseException: clear_capture(db, event_id=eid); raise` 里——402、`_pass_active`/`museum_of_qid`/`resolve_state` 抛异常都会撤销。
- inflight 等待方(`cached == "inflight"`)直接 `clear_capture(db, event_id=eid)` 后返回:扣费归首请求那一行。
- `recognize_confirm`(非 search 来源)算一个 `billed`:覆盖该馆的票生效 → True;`first_time and user_id` 且 `consume_recognition` 成功 → True;`not first_time`(改选,同一张照片已扣过)→ 不撤销;其余(令牌失效 `user_id=None`、扣费失败、扣费抛异常)→ `clear_capture(db, phash=body.phash)`,抛异常的照常再抛。

- [ ] **Step 1: 写失败测试**:
  - `test_capture_param_recorded`:`POST /api/v1/recognize?capture=camera` → 新事件行 `capture == "camera"`;不带参数 → `None`;`capture=foo` → 422;馆内端点 `?capture=gallery` 落 `"gallery"`;缓存命中那行也带 capture。
  - `test_402_after_match_clears_capture`:持别处的票 + 免费额度 0、命中本馆 → 402,该行 `capture is None`。
  - `test_billing_exception_after_match_clears_capture`:monkeypatch `entitlement_service.museum_of_qid` 抛错 → 500,该行 `capture is None`。
  - `test_inflight_waiter_row_has_no_capture`:造 `_billed == "inflight"` 的返回 → 等待方那行 `capture is None`,首请求那行不受影响。
  - `test_confirm_without_billing_clears_capture`:候选行 `capture="camera"`;确认时无令牌 → 行 `capture is None`;`consume_recognition` 返回 False → `None`;抛异常 → 500 且 `None`;扣费成功或票生效 → 仍 `"camera"`;改选(第二次确认)→ 仍 `"camera"`。
- [ ] **Step 2: 跑测试确认失败。**
- [ ] **Step 3: 实现**(迁移 + 模型列 + 透传 + 上面的撤销规则)。
- [ ] **Step 4: 核查足迹**:在 `test_history_footprints.py` 加一条看「命中后 402」那行是否出现在 `/history`。**只记录结论,不在本计划里改足迹**:若出现,在 `docs/ops/backlog.md` 记一条并在最终汇报里告诉用户。
- [ ] **Step 5: 跑** `poetry run pytest tests/integration/test_recognize_flow.py tests/integration/test_pass_scope_by_museum.py tests/unit/api/test_recognize_global.py tests/unit/services/recognition/test_service.py tests/integration/test_history_footprints.py -q` → PASS;`poetry run alembic heads` 只有 `c1m1`。
- [ ] **Step 6: Commit** `feat(recognition): 识别请求带 capture(拍照/相册),没扣成费的撤销`

### Task 3: 打卡、轮与勋章服务

**Files:**
- Create: `backend/alembic/versions/c1m2_must_see_medals.py`(`revision="c1m2"`, `down_revision="c1m1"`)
- Create: `backend/app/models/must_see_medal.py`
- Create: `backend/app/services/must_see_checkin.py`
- Modify: `backend/app/services/auth_service.py`(`export_user_data` 加 `must_see_medals`;`delete_user_account` 真删该用户勋章行)
- Modify: `backend/tests/conftest.py::account_tables`(加 `MustSeeMedal.__table__`——删号路径的唯一表清单,不加则所有删号 fixture 缺表)
- 复用 `app.api.v1.endpoints.history._footprint_qid`(直接 import,不改名)
- Test: `backend/tests/unit/services/test_must_see_checkin.py`、`backend/tests/integration/test_export_user_data.py`、`backend/tests/integration/test_account_deletion.py`

**Interfaces:**
- Consumes: Task 1 `MUST_SEE`;Task 2 `RecognitionEvent.capture`。
- Produces:
  - 表 `must_see_medals`:`id` UUID PK、`user_id` String(64) not null、`museum_slug` String(64) not null、`completed_at` DateTime not null、`count` Integer not null、`created_at` server_default now;`UniqueConstraint(user_id, museum_slug, completed_at)`;索引 `(user_id, museum_slug)`。
  - `checkins(db, user_id: str, slug: str) -> list[tuple[str, datetime]]`:`user_id` 匹配、`capture == 'camera'`、`confirm_source != 'search'`(NULL 视为非 search)、`_footprint_qid(ev)` ∈ 该馆清单的 (qid, created_at),按时间升序。**不按 `museum_slug` 过滤。**
  - `split_rounds(checkins) -> list[list[tuple[str, datetime]]]`:相邻间隔 > 30 天切开。
  - `current_round(checkins, now: datetime) -> list[tuple[str, datetime]]`:`split_rounds` 的最后一段;最后一次打卡距 `now` > 30 天 → `[]`。
  - `progress(db, user_id: str | None, slug: str, now: datetime | None = None) -> dict`:`{"checked": {qid: iso}, "round_started_at": iso|None, "completed": bool, "medals": [{"completed_at": iso, "count": int}, ...新的在前]}`;`user_id is None` → `{"checked": {}, "round_started_at": None, "completed": False, "medals": []}`。**遍历所有轮**(不只当前轮):某轮覆盖当前清单全部 qid、且 `[该轮首次打卡, 该轮末次打卡]` 区间内没有勋章 → 插一条(`completed_at` = 该轮补齐最后一件那次打卡时间,`count` = 清单件数)——防止「补齐那次拉取失败、30 天内没再打开」导致永远不发。清单为空或当前轮为空 → `completed = False`,不插。`IntegrityError` 回滚后照常返回。时间按 Global Constraints 带时区输出。

- [ ] **Step 1: 写失败测试**(SQLite,造 `RecognitionEvent` 行,`now` 显式传入):
  - 所有用例造行用 `museum_slug=None`(与线上全局端点一致)。
  - `test_only_camera_counts`:`capture` 为 `None`/`"gallery"` 不算,`"camera"` 算。
  - `test_search_confirm_and_rejected_and_anonymous_excluded`:`confirm_source="search"`、qid 在 `rejected_qids`、`user_id=None` 均不算;`outcome="candidates"` 未确认不算,确认后(`confirm_source="candidates"`)算。
  - `test_qid_outside_list_ignored`。
  - `test_round_split_boundary`:间隔恰好 30 天同轮;30 天 + 1 秒切新轮。
  - `test_no_current_round_after_30_days`:最后一次打卡在 `now - 31 天` → `checked == {}`、`round_started_at is None`,已有勋章仍在 `medals`。
  - `test_completion_writes_one_medal`:打满 → `completed True`、`medals` 1 枚、`completed_at` = 最后补齐那次;再调两次仍 1 枚;直接再插同一行触发唯一约束时 `progress` 不抛。
  - `test_medal_survives_footprint_delete_and_list_change`:打满后把一行 `user_id` 置 NULL、或 monkeypatch 清单加一件 → `completed False`,`medals` 仍 1 枚,且补拍那件后不发第二枚。
  - `test_missed_completion_backfilled`:某轮打满后没调过 `progress`、`now` 已过 31 天 → 调用后补发 1 枚,`completed_at` = 该轮补齐时刻。
  - `test_empty_list_never_completes`:清单为空 → `completed False`、不插勋章。
  - `test_times_are_utc_aware`:输出的时间串以 `+00:00` 结尾。
  - 导出/删号:`test_export_includes_must_see_medals`、`test_delete_account_removes_medals`。
- [ ] **Step 2: 跑测试确认失败。**
- [ ] **Step 3: 实现**模型、迁移、服务(单用户单馆量很小,Python 里切轮)、导出(键名 `must_see_medals`,每项 `museum_slug/completed_at/count`)、删号(真删:勋章离开用户没有统计价值,与 spec 第五节 3 已统一)。
- [ ] **Step 4: 跑** `poetry run pytest tests/unit/services/test_must_see_checkin.py tests/integration/test_export_user_data.py tests/integration/test_account_deletion.py tests/integration/test_history_footprints.py tests/integration -q -k "delet or password or export"` → PASS;`alembic heads` 只有 `c1m2`。
- [ ] **Step 5: Commit** `feat(must-see): 打卡按轮现算,打满落勋章表(进导出与删号)`

### Task 4: 必看端点与馆列表 `must_see_count`

**Files:**
- Modify: `backend/app/api/v1/endpoints/museums.py`(新路由;隐身馆用现有 `_hidden()` 闸)
- Modify: `backend/app/services/museum_repo.py:923-964`(`list_museums` 每行加 `must_see_count`)
- Modify: `docs/architecture/museum-api-contract.md`(API 面:新端点、`capture`、`must_see_count`;「上新馆」配方加选必看两条规则 + 展厅号规则)
- Test: `backend/tests/unit/api/test_must_see_endpoint.py`

**Interfaces:**
- Consumes: Task 1 `MUST_SEE`、`MUST_SEE_LOCATION`;Task 3 `progress`;现有 `museum_repo.list_objects`(取标题/作者/缩略图)。
- Produces: `GET /api/v1/museums/{slug}/must-see?language=zh`(令牌可选)→
  ```json
  {"items": [{"qid": "Q12418", "title": "…", "artist": "…", "thumbnail": "…|null",
              "location": {"wing": "Denon", "level": 1, "room": "711"} | null}],
   "checked": {"Q12418": "2026-10-27T10:00:00+00:00"}, "round_started_at": "…|null",
   "completed": false, "medals": [{"completed_at": "…", "count": 12}]}
  ```
  `items` 按 yaml 顺序;目录里查不到/无图的 qid 也列出(`title` 回退 qid,`artist` 回退 `""`,`thumbnail` null)。`GET /api/v1/museums` 每项加 `must_see_count: int`(= yaml 清单件数,无清单 0)。

- [ ] **Step 1: 写失败测试**:有清单馆返回顺序与 `location`;无清单馆 `items == []`;未知馆、隐身馆(非预览)404;匿名无进度;带令牌返回 Task 3 的进度;清单里有目录缺失的 qid 时 200 且该项按回退值;`/museums` 列表项含 `must_see_count`,无清单馆为 0。
- [ ] **Step 2: 跑测试确认失败。**
- [ ] **Step 3: 实现**:`list_objects(db, slug, language=language, limit=len(清单))` 已把必看排在最前,按 qid 取用,缺的走回退;令牌用 `recognize_global._user_id` 同款解析。
- [ ] **Step 4: 跑** `poetry run pytest tests/unit/api/test_must_see_endpoint.py tests/unit/api -q -k "museum"` → PASS。
- [ ] **Step 5: Commit** `feat(must-see): GET /museums/{slug}/must-see + 馆列表 must_see_count;契约回写`

### Task 5: 展厅号取数脚本 + 清单重审提案(交用户确认)

**Files:**
- Create: `tools/must_see_rooms/fetch_rooms.py`(只读官网,输出 yaml 片段到 stdout)
- Create: `tools/must_see_rooms/test_fetch_rooms.py`(用存下来的官网响应做解析测试,不联网)
- Create: `tools/must_see_rooms/fixtures/`(卢浮宫 JSON 1 份、橘园作品页 HTML 1 份、巴黎博物馆集团作品页 HTML 1 份)
- Create: `docs/ops/must-see-review-2026-10.md`(重审提案,不改 yaml)

**Interfaces:**
- Produces: `parse_louvre(json: dict) -> dict|None`、`parse_orangerie(html: str) -> dict|None`、`parse_parismusees(html: str) -> dict|None`,均返回 `{"wing","level","room"}`(取不到的字段 None;全取不到 → None)。CLI:`python tools/must_see_rooms/fetch_rooms.py <slug>` 读 `backend/museums.yaml` 清单,逐件请求(间隔 ≥1s、失败不重试),打印可直接贴回 yaml 的 `must_see:` 片段。官网链接从 Wikidata 取:卢浮宫 P9394 → `https://collections.louvre.fr/ark:/53355/cl{id}.json`;橘园、小皇宫取 P973 中对应域名的链接。奥赛直接打印原清单(官网 403)。

- [ ] **Step 1: 写失败测试**:三份 fixture 分别解析出 卢浮宫 `{"wing":"Denon","level":1,"room":"711"}`(源字段 `"Salle 711, Aile Aile Denon, Niveau 1"`,注意源里重复的 "Aile")、橘园 `{"wing":None,"level":-2,"room":"8"}`、小皇宫 `room "04"`、楼层按 Rez-de-Jardin = -1 映射;卢浮宫 `room == ""`(费隆妮叶夫人那种)→ None。
- [ ] **Step 2: 跑** `python -m pytest tools/must_see_rooms -q` 确认失败,实现,再跑 → PASS。
- [ ] **Step 3: 实跑**:先各抽查 2 件确认 Wikidata 上有对应链接(P9394 / P973 是否真存在),缺的在提案里标出;再实跑卢浮宫、橘园、小皇宫三馆,保存输出。
- [ ] **Step 4: 写重审提案** `docs/ops/must-see-review-2026-10.md`:每馆每件一行——是否常年在展(依据:卢浮宫 JSON `exhibition` 外借史、Wikidata 展览史 P608)、是否可识别(库里有图/向量,查 `object_embeddings`)、取到的展厅号、建议「留/换/删」。
- [ ] **Step 5: Commit** `feat(tools): 必看展厅号取数脚本 + 四馆清单重审提案`
- [ ] **Step 6: ⛔ 停下交用户确认提案。** 用户确认后,按提案改 `backend/museums.yaml`(新写法带展厅号、按馆内动线排序),跑 Task 1 测试与 `tests/unit/services/test_must_see_yaml.py`(按新件数改断言),Commit `chore(must-see): 四馆清单按常年在展重审并补展厅号`。

### Task 6: App 数据层(capture、must-see 模型、馆列表计数)

**Files:**
- Modify: `frontend/gomuseum_app/lib/features/recognition/data/datasources/recognition_remote_datasource.dart`(`recognize({..., String? capture})` → 查询参数 `capture`)
- Modify: `frontend/gomuseum_app/lib/features/recognition/presentation/providers/recognition_provider.dart`(`recognize({..., String? capture})` 透传)
- Modify: `frontend/gomuseum_app/lib/features/recognition/presentation/pages/camera_page.dart:365-372`(`capture: live ? 'camera' : 'gallery'`)
- Modify: `frontend/gomuseum_app/lib/features/content/data/models/museum_summary_model.dart`(`mustSeeCount`,`json['must_see_count'] as int? ?? 0`)
- Create: `frontend/gomuseum_app/lib/features/must_see/data/must_see_models.dart`
- Create: `frontend/gomuseum_app/lib/features/must_see/data/must_see_providers.dart`
- Modify(接口加参数后必须跟着改签名的 fake):`test/features/guide/guide_not_this_one_test.dart`、`test/features/recognition/presentation/providers/recognition_{retry,reject,quota_state,refreshes_footprints,search_confirm}_test.dart`
- Test: `frontend/gomuseum_app/test/features/must_see/must_see_models_test.dart`、`test/features/recognition/` 下现有 datasource 测试

**Interfaces:**
- Produces:
  - `class MustSeeLocation { final String? wing; final int? level; final String? room; }`
  - `class MustSeeItem { final String qid, title, artist; final String? thumbnail; final MustSeeLocation? location; }`
  - `class MustSeeMedal { final DateTime completedAt; final int count; }`
  - `class MustSeeData { final List<MustSeeItem> items; final Map<String, DateTime> checked; final DateTime? roundStartedAt; final bool completed; final List<MustSeeMedal> medals; int get checkedCount; factory MustSeeData.fromJson(Map<String, dynamic>); }`——时间解析为 UTC 再 `toLocal()`。
  - `final mustSeeProvider = FutureProvider.autoDispose.family<MustSeeData, String>`(slug;带当前语言;随账号失效同 `museumsListProvider`)。
  - `MuseumSummary.mustSeeCount: int`(加进 Equatable `props`)。

- [ ] **Step 1: 写失败测试**:完整 JSON 解析正确;`location` 为 null/缺字段/类型错(如 `level: "1"`)→ 不抛、按 null;`medals`/`checked` 缺失 → 空;`items` 某项缺 `title` → 回退 qid。datasource 测试断言带 `capture=camera` 的查询参数,`capture` 为 null 时不带该键。`MuseumSummary.fromJson` 无 `must_see_count` → 0;时间串带 `+00:00` 时解析后 `toLocal()` 正确(马德里 23:30Z → 次日日期)。
- [ ] **Step 2: 跑测试确认失败,实现,再跑** `flutter test test/features/must_see test/features/recognition test/features/content` → PASS。
- [ ] **Step 3: Commit** `feat(must-see): App 数据层(识别带 capture、必看模型与 provider)`

### Task 7: 馆页「必看」tab 与护照页

**Files:**
- Modify: `frontend/gomuseum_app/lib/features/explore/presentation/pages/museum_page.dart:47-48,140-160,190-224`
- Create: `frontend/gomuseum_app/lib/features/must_see/presentation/passport_page.dart`
- Modify: `frontend/gomuseum_app/lib/l10n/app_*.arb`(10 语;下列 key)
- Modify: `test/features/explore/museum_page_smoke_test.dart`(补 override `museumsListProvider`,否则馆页同步读它会发真请求)
- Test: `frontend/gomuseum_app/test/features/must_see/passport_page_test.dart`、`test/features/explore/` 下馆页测试

**Interfaces:**
- Consumes: Task 6 `mustSeeProvider`、`MuseumSummary.mustSeeCount`。
- Produces: `class MustSeePassport extends ConsumerWidget { const MustSeePassport({required this.slug, required this.museumName}); }`;l10n key:`museumTabMustSee`(必看)、`passportTitle(museum)`({museum} · 必看)、`passportStamped(done, total)`(已盖 {done} / {total} 枚章)、`passportRoundSince(date)`(本轮始于 {date})、`passportRoundDone`(本轮已完成 ✓)、`passportSealTitle`(必看完成)、`passportShare`(分享这一页)、`passportMedals`(我的勋章)、`passportNoLocation`(暂无展厅信息)、`passportLevel(level)`(楼层,各语言叫法用 select/plural)、`passportRoom(room)`({room} 厅);侧翼名原样;三段在 Dart 里缺哪段跳过、用 " · " 拼;`mustSeeToastStamped(done, total)`(盖章!必看 {done} / {total})、`mustSeeToastDone(total)`(必看完成 {total} / {total})。

- [ ] **Step 1: 写失败测试**:
  - 馆页:`mustSeeCount > 0` → 三个 tab「封面/必看/藏品」且默认选中「必看」;`mustSeeCount == 0` 或馆列表还没加载 → 两个 tab、默认「藏品」(与现状一致)。
  - 护照页:5/12 时副标题文字;已打卡章位显示日期签(如 `10·27`)、未打卡显示序号;有位置的按 (wing, level) 分组且组名出现,无位置的归「暂无展厅信息」组且排最后;整馆无位置 → 不出组名;`completed` → 出现「本轮已完成 ✓」与大章;`medals` 非空 → 「我的勋章」+ 每枚奖章,空则不出该块;点章位 push `/guide`(`GuideArgs(slug, qid)`)。
  - 切走再切回「必看」tab 会重新请求 must-see。
  - 十语布局扫描(沿用 `test/i18n` 现有扫描方式,真实字体)无溢出。
- [ ] **Step 2: 跑测试确认失败。**
- [ ] **Step 3: 实现**:`TabController` 长度/初始 index 由**同步读取** `museumsListProvider` 的缓存值决定;护照页按样稿 `2026-10-27-must-see-mockups/passport-v2b.html`、`medal-styles.html`(B 圆形奖章)用 `GmColors`/`GmText` 画,亮暗主题都要成立;分享按钮复用 `lib/features/guide/presentation/share_object.dart` 的分享方式,内容 = 文字(馆名 + 必看完成 N/N + 日期)+ 馆链接;加载/失败/空态沿用馆页现有写法。切到「必看」tab 时 invalidate `mustSeeProvider(slug)`,每次显示都是最新进度(spec 第五节 6 末条)。
- [ ] **Step 4: 跑** `flutter test test/features/must_see test/features/explore test/i18n && flutter analyze` → PASS / No issues。
- [ ] **Step 5: Commit** `feat(must-see): 馆页必看 tab(护照页、完成大章、圆形勋章)十语`

### Task 8: 讲解页盖章提示

**Files:**
- Modify: `frontend/gomuseum_app/lib/features/guide/presentation/pages/guide_page.dart:57-100`(`GuideArgs.liveShot`,默认 false;`GuideArgs.pendingConfirm: Future<void>?`)
- Modify: `frontend/gomuseum_app/lib/features/recognition/presentation/pages/camera_page.dart:500-560`(`_goGuide`:`liveShot: _lastShotLive && !fromSearch`;把 `confirmRecognition(...)` 的 Future 存下传给 `pendingConfirm`,仍不 await)
- Create: `frontend/gomuseum_app/lib/features/must_see/presentation/stamp_toast.dart`
- Test: `frontend/gomuseum_app/test/features/must_see/stamp_toast_test.dart`

**Interfaces:**
- Consumes: Task 6 `mustSeeProvider`、`MuseumSummary.mustSeeCount`;Task 7 l10n key `mustSeeToastStamped` / `mustSeeToastDone`、`passportLevel`、`passportRoom`。
- Produces: `GuideArgs.liveShot: bool`、`GuideArgs.pendingConfirm: Future<void>?`;`Future<void> maybeShowStampToast(BuildContext context, WidgetRef ref, {required String slug, required String qid, Future<void>? pendingConfirm})`。

流程:`liveShot` 为 false → 不做事;`museumsListProvider` 缓存里该馆 `mustSeeCount == 0` → 不请求;否则先 `await pendingConfirm`(候选确认要等它提交;出错照样继续),再 invalidate 并读 `mustSeeProvider(slug)`;`checked` 含该 qid 才显示。不用定时重试。

- [ ] **Step 1: 写失败测试**:`liveShot` 为 true、qid 在清单且在 `checked` → 出现「盖章!必看 6 / 12」与厅号,约 4 秒后消失;点提示**不跳转**(路由栈不变);`pendingConfirm` 未完成时不请求、完成后才请求;`completed` → 文案「必看完成 12 / 12」;`liveShot` false、`mustSeeCount == 0`、qid 不在清单或不在 `checked` → 都不显示且(前两种)不发请求。
- [ ] **Step 2: 跑测试确认失败,实现,再跑** `flutter test test/features/must_see test/features/guide test/features/recognition && flutter analyze` → PASS。
- [ ] **Step 3: Commit** `feat(must-see): 拍照命中必看时讲解页顶部临时盖章提示`

---

**收尾(不属于某个任务):** 合并前再跑一次 `poetry run alembic heads`(并行 worktree 可能也加了迁移,有新 head 就把 `c1m1` 的 `down_revision` 改接上去);全量 `poetry run pytest -q` 与 `flutter test`;`/pr` 开 feature→staging PR,CI 绿后合并;staging 用真机按 spec 第七节「真机」条验收;Task 2 Step 4 的足迹核查结论与 Task 5 提案的确认状态写进最终汇报;出包(V75)由用户决定时机。
