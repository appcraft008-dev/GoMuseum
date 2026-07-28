# anatomy.md

> Auto-maintained by OpenWolf. Last scanned: 2026-07-28T16:00:00.503Z
> Files: 540 tracked | Anatomy hits: 0 | Misses: 0

## ./

- `.coverage` (~14200 tok)
- `.DS_Store` (~4371 tok)
- `.editorconfig` — Editor configuration (~159 tok)
- `.eslintignore` — Dependencies (~141 tok)
- `.gitignore` — Git ignore rules (~493 tok)
- `.gitleaks.toml` — gitleaks 配置：保留全部默认规则，仅放行已确认的客户端配置/误报。 (~180 tok)
- `.nvmrc` (~3 tok)
- `.prettierignore` — Dependencies (~82 tok)
- `.prettierrc.json` — Prettier configuration (~26 tok)
- `20251004-claude-sesion.md` (~21 tok)
- `ACCEPTANCE_SUMMARY_20251002_222839.md` — GoMuseum Step 1 验收摘要 (~230 tok)
- `ACCEPTANCE_SUMMARY_20251002_223334.md` — GoMuseum Step 1 验收摘要 (~230 tok)
- `ACCEPTANCE_SUMMARY_20251003_095649.md` — GoMuseum Step 1 验收摘要 (~230 tok)
- `ACCEPTANCE_SUMMARY_20251004_235438.md` — GoMuseum Step 1 验收摘要 (~230 tok)
- `ACCEPTANCE_SUMMARY_20251005_072503.md` — GoMuseum Step 1 验收摘要 (~230 tok)
- `ACCEPTANCE_SUMMARY_20251005_121419.md` — GoMuseum Step 1 验收摘要 (~230 tok)
- `ACCEPTANCE_SUMMARY_20251005_131332.md` — GoMuseum Step 1 验收摘要 (~230 tok)
- `ACCEPTANCE_TEST_SUMMARY.md` — 自动化验收测试 - 交付总结 (~1497 tok)
- `analysis_options.yaml` — - lib/generated/\*\* (~1429 tok)
- `CACHE_FIX_README.md` — 识别缓存问题修复总结 (~1999 tok)
- `CI_CONFIGURATION.md` — GoMuseum CI/CD 配置说明 (~955 tok)
- `ci-test.md` (~27 tok)
- `ci-test2.txt` (~13 tok)
- `ci-verify.txt` (~14 tok)
- `CLAUDE.md` — Claude Code 项目规则 (claude.md) (~1417 tok)
- `COMMIT_READY.md` — 准备提交 - Step 1-2-3 完成 + CI修复 (~1151 tok)
- `COVERAGE_IMPROVEMENT_REPORT.md` — GoMuseum 测试覆盖率提升报告 (~2475 tok)
- `DEVELOPMENT_STANDARDS.md` — GoMuseum 开发规范 (~1262 tok)
- `docker-compose.production.yml` (~0 tok)
- `docker-compose.staging.yml` (~0 tok)
- `docker-compose.yml` — Docker Compose services (~365 tok)
- `environment-report.txt` (~118 tok)
- `eslint.config.js` — ESLint flat configuration (~291 tok)
- `eslint.config.mjs` — ESLint flat configuration (~96 tok)
- `Makefile` — Make build targets (~39 tok)
- `MANUAL_ACCEPTANCE_GUIDE.md` — GoMuseum Step 1 手工验收指南 (~3182 tok)
- `package-lock.json` — npm lock file (~16116 tok)
- `package.json` — Node.js package manifest (~365 tok)
- `pr-test.md` (~10 tok)
- `QUICK_START.md` — GoMuseum Step 1 快速启动指南 (~620 tok)
- `QUICKFIX.md` — 时间戳问题快速修复指南 (~463 tok)
- `README.md` — Project documentation (~11 tok)
- `sonar-project.properties` — ,**/.venv/**,**/venv/**,**/**pycache**/**,**/coverage/**,**/htmlcov/**,**/dist/**,**/build/**,backend/alembic/\*\* (~170 tok)
- `sonar-test.md` (~10 tok)
- `sonarcloud-test.md` (~12 tok)
- `STEP1_RE_VALIDATION_REPORT.md` — GoMuseum Step 1 重新验收报告 (~3739 tok)
- `TEST_FRAMEWORK_SUMMARY.md` — GoMuseum Step 1 (图像识别功能) 测试框架创建报告 (~1938 tok)
- `test_openai_api.py` — Tests: openai_api (~534 tok)
- `TEST_STATISTICS.txt` (~841 tok)
- `trigger.txt` (~4 tok)
- `WEB_PLATFORM_FIX_SUMMARY.md` — Web 平台兼容性修复总结 (~811 tok)
- `WEB_PLATFORM_FIX.md` — Web 平台兼容性修复文档 (~1307 tok)

## .claude/

- `settings.local.json` (~83 tok)

## .claude/commands/

- `pr.md` (~207 tok)

## .github/workflows/

- `branch-guard.yml` — 守卫：只有 staging 分支可以向 main 提 PR（GitHub 原生分支保护无法限制 PR 来源分支） (~161 tok)
- `ci.yml` — GoMuseum CI/CD 流水线配置（适配个人用户，无 GHAS） (~1935 tok)
- `deploy.yml` — CI: Deploy (~979 tok)
- `sync-main-to-staging.yml` — CI: Sync main → staging (~313 tok)

## .husky/

- `pre-commit` (~8 tok)
- `pre-push` — 推送前格式兜底：只查不改，发现未格式化即拦截（不跑全量测试，交给远端 CI） (~228 tok)

## .husky/\_/

- `.gitignore` — Git ignore rules (~1 tok)
- `applypatch-msg` (~11 tok)
- `commit-msg` (~11 tok)
- `h` (~147 tok)
- `husky.sh` (~46 tok)
- `post-applypatch` (~11 tok)
- `post-checkout` (~11 tok)
- `post-commit` (~11 tok)
- `post-merge` (~11 tok)
- `post-rewrite` (~11 tok)
- `pre-applypatch` (~11 tok)
- `pre-auto-gc` (~11 tok)
- `pre-commit` (~11 tok)
- `pre-merge-commit` (~11 tok)
- `pre-push` (~11 tok)
- `pre-rebase` (~11 tok)
- `prepare-commit-msg` (~11 tok)

## .pytest_cache/

- `.gitignore` — Git ignore rules (~10 tok)
- `CACHEDIR.TAG` (~51 tok)
- `README.md` — Project documentation (~76 tok)

## .pytest_cache/v/cache/

- `nodeids` (~1 tok)
- `stepwise` (~1 tok)

## .scannerwork/

- `.sonar_lock` (~0 tok)
- `report-task.txt` (~74 tok)

## .scannerwork/architecture/js/

- `eslint_config_js.udg` (~78 tok)
- `eslint_config_mjs.udg` (~102 tok)

## .superpowers/sdd/

- `.gitignore` — Git ignore rules (~1 tok)
- `deviceid-report.md` — 识别请求恒带 device_id — 实施报告 (~504 tok)
- `hotfix-text-chain-report.md` — Hotfix: GPT 兜底文字链不直判 match (~548 tok)
- `multicrop-report.md` — 低分多裁剪金字塔重查 — 实现报告 (~327 tok)
- `precision-fixes-report.md` — Recognition precision/speed fixes — report (~709 tok)
- `progress.md` — recognition-embedding-bench 进度 (plan: docs/superpowers/plans/2026-07-11-recognition-embedding-bench.md) (~1596 tok)
- `review-0bb61556..75d14a8f.diff` — Review package: 0bb61556..HEAD (~4028 tok)
- `review-0f1706a2..c55afddc.diff` — Review package: 0f1706a2..HEAD (~2046 tok)
- `review-1dafae24..50a69036.diff` — Review package: 1dafae24..HEAD (~2127 tok)
- `review-342636cf..1ea35c5e.diff` — Review package: 342636cf72c021f47a7bb8c210b251eaccc57a64..HEAD (~35747 tok)
- `review-3cec67f0..56dfc5e0.diff` — Review package: 3cec67f0..56dfc5e0 (~3754 tok)
- `review-3d076b1c..62686921.diff` — Review package: 3d076b1c..HEAD (~1272 tok)
- `review-4620d295..834f4e82.diff` — Review package: 4620d295..HEAD (~4839 tok)
- `review-487c5f98..af7d79a2.diff` — Review package: 487c5f98..HEAD (~2804 tok)
- `review-514bcb41..4620d295.diff` — Review package: 514bcb41..HEAD (~2347 tok)
- `review-581cd878..907580ba.diff` — Review package: 581cd878..HEAD (~1805 tok)
- `review-5d0a2aa2..ba52a8cc.diff` — Review package: 5d0a2aa2..HEAD (~3107 tok)
- `review-62686921..93ea429d.diff` — Review package: 62686921..HEAD (~2154 tok)
- `review-74f7bcae..c6c6c771.diff` — Review package: 74f7bcae..HEAD (~5640 tok)
- `review-75d14a8f..5d0a2aa2.diff` — Review package: 75d14a8f..HEAD (~5102 tok)
- `review-78316d48..1ea35c5e.diff` — Review package: 78316d48..HEAD (~3412 tok)
- `review-7bde4970..e2c651f4.diff` — Review package: 7bde4970..HEAD (~1989 tok)
- `review-834f4e82..487c5f98.diff` — Review package: 834f4e82..487c5f98 (~2283 tok)
- `review-88dd4bec..1ea35c5e.diff` — Review package: 88dd4bec..HEAD (~11967 tok)
- `review-907580ba..bd88c8b5.diff` — Review package: 907580ba..HEAD (~3975 tok)
- `review-93ea429d..74f7bcae.diff` — Review package: 93ea429d..HEAD (~1059 tok)
- `review-9ba13110..33f06c4a.diff` — Review package: 9ba13110..HEAD (~6671 tok)
- `review-af7d79a2..e6b3d878.diff` — Review package: af7d79a2..HEAD (~4138 tok)
- `review-b26e5342..3d076b1c.diff` — Review package: b26e5342..HEAD (~955 tok)
- `review-c092ae7a..ce9ee5fa.diff` — Review package: c092ae7a7962373b95744a7542280361a9176c9f..HEAD (~44569 tok)
- `review-c55afddc..514bcb41.diff` — Review package: c55afddc..HEAD (~1782 tok)
- `review-c6c6c771..1dafae24.diff` — Review package: c6c6c771..HEAD (~1002 tok)
- `review-d21e53c0..b26e5342.diff` — Review package: d21e53c0..HEAD (~1059 tok)
- `review-d3e4a468..ce9ee5fa.diff` — Review package: d3e4a468..ce9ee5fa (~11560 tok)
- `review-e2c651f4..0bb61556.diff` — Review package: e2c651f4..HEAD (~2173 tok)
- `review-ea99b459..e5848f7a.diff` — Review package: ea99b459..HEAD (~50096 tok)
- `task-1-brief.md` — ## Task 1 [OPUS]: recognition_events 表 + 服务端埋点 + phash 字段 + confirm 端点 (~634 tok)
- `task-1-report.md` — Task 1 报告：recognition_events 埋点 + 响应 phash + confirm 端点 (~733 tok)
- `task-2-brief.md` — ## Task 2 [SONNET]: catalog 收无图 stub（P18/P276 OPTIONAL） (~640 tok)
- `task-2-report.md` — Task 2 Report: catalog 收无图 stub（P18/P276 OPTIONAL） (~605 tok)
- `task-3-brief.md` — ## Task 3 [OPUS]: 列表/计数有图过滤 + 馆页双数字 (~303 tok)
- `task-3-report.md` — Task 3 Report: 列表/分类计数有图过滤 + 馆页双数字 (~705 tok)
- `task-4-brief.md` — fixture: sqlite(Museum/MuseumObject/ObjectImage/RecognitionEvent 表) 抄 test_object_embedding.py 模式 (~566 tok)
- `task-4-report.md` — Task 4 报告: 展陈状态模块 display_state.py (~626 tok)
- `task-5-brief.md` — ## Task 5 [OPUS]: view 自动治理（vet 升级 + 入库闸 + 图集白名单） (~358 tok)
- `task-5-report.md` — Task 5 Report: view 自动治理（vet 升级 + 入库闸 + 图集白名单） (~1046 tok)
- `task-6-brief.md` — ## Task 6 [OPUS]: Joconde 区域适配器样板 (~332 tok)
- `task-6-report.md` — Task 6 报告: Joconde 区域适配器样板 (~690 tok)
- `task-7-brief.md` — ## Task 7 [SONNET]: 覆盖率报告 CLI + museums.stats 回写 (~385 tok)
- `task-7-report.md` — Task 7 报告: 覆盖率报告 CLI + museums.stats 回写 (~954 tok)
- `task-8-brief.md` — ## Task 8 [OPUS]: 前端三件套（confirm 上报 + 用户照片 hero + 馆页双数字） (~417 tok)
- `task-8-report.md` — Task 8 Report: 前端三件套（confirm 上报 + 用户照片 hero + 馆页双数字 + 无图占位）— coverage-phase1 round (~761 tok)
- `task-9-brief.md` — ## Task 9: 前端切全局端点 (~260 tok)
- `task-9-report.md` — Task 9 报告：前端切全局识别端点 (~372 tok)

## .vscode/

- `extensions.json` (~215 tok)
- `settings.json` (~370 tok)

## backend/

- `.coveragerc` (~0 tok)
- `.dockerignore` — Docker ignore rules (~24 tok)
- `.flake8` (~0 tok)
- `.python-version` (~2 tok)
- `alembic.ini` — A generic, single database configuration. (~931 tok)
- `DATABASE_OPTIMIZATION_SUMMARY.md` — GoMuseum 数据库优化总结报告 (~1805 tok)
- `Dockerfile` — Docker container definition (~310 tok)
- `Dockerfile.prod` (~0 tok)
- `main.py` — backend/main.py (~38 tok)
- `museums.yaml` — 馆配置：加一个馆 = 加一段 (~622 tok)
- `pyproject.toml` — Python project configuration (~1302 tok)
- `requirements.txt` — Python dependencies (~74 tok)
- `test_api_connection.py` — Tests: openai, claude, fallback_strategy (~1338 tok)
- `TESTING.md` — Testing & Coverage Configuration (~599 tok)
- `zz_cov_probe.py` (~15 tok)

## backend/.pytest_cache/

- `.gitignore` — Git ignore rules (~10 tok)
- `CACHEDIR.TAG` (~51 tok)
- `README.md` — Project documentation (~76 tok)

## backend/.pytest_cache/v/cache/

- `lastfailed` (~229 tok)
- `nodeids` (~25762 tok)

## backend/alembic/

- `alembic.ini` (~30 tok)
- `env.py` — Alembic environment configuration (~667 tok)
- `script.py.mako` (~170 tok)

## backend/alembic/versions/

- `001_create_recognition_results_table.py` — Create recognition_results table (~608 tok)
- `002_optimize_recognition_indexes.py` — Optimize recognition_results indexes and add constraints (~1304 tok)
- `003_create_stats_tables.py` — Create recognition_stats and ai_service_logs tables (~2251 tok)
- `004_fix_timestamp_default.py` — Fix timestamp default to use server-side now() (~445 tok)
- `006_add_user_auth.py` — Add User model for authentication (~608 tok)
- `007_allow_null_email.py` — Allow users.email to be nullable for OAuth-only accounts (~234 tok)
- `008_add_is_guest_field.py` — Add is_guest field to users table for guest mode (~159 tok)
- `009_user_benefits_and_cleanup.py` — Create user_benefits table; drop removed facebook_id column (~595 tok)
- `a3b3_add_content_status.py` — add museum_objects.content_status (~180 tok)
- `d6ca257376ac_step1_data_foundation.py` — step1 data foundation (~2286 tok)
- `e1a1_add_object_sources.py` — add museum_object.sources jsonb (~159 tok)
- `f2a2_add_suggested_questions.py` — add object_suggested_questions table (~524 tok)
- `g1d3_add_guide_section_type.py` — add 'guide' section_type (默认标准讲解 default_guide 落库需满足 FK) (~305 tok)
- `h1e4_add_evidence_pack.py` — add evidence_pack JSONB column to museum_objects (~155 tok)
- `i1f5_retire_overview_tab.py` — retire overview tab: 删 category_sections 里 section_code='overview' 的映射行 (~166 tok)
- `j1g6_add_artists.py` — add artists table (作者一等实体) (~341 tok)
- `k1h7_add_name_i18n.py` — add artists.name_i18n (~130 tok)
- `l1i8_add_recognition_demands.py` — add recognition_demands (未收录需求记录) (~356 tok)
- `m1j9_add_artist_facts_i18n.py` — add artists.nationality_i18n / notable_works_i18n (作者卡多语,交接③) (~226 tok)
- `n1k0_add_audio_keys.py` — add QA audio_key + artists bio_audio (TTS Phase2:问答/作者介绍音频) (~211 tok)
- `o1l1_add_object_embeddings.py` — object_embeddings 表 + recognition_demands.museum_slug 可空(全局识别)。 (~402 tok)
- `p1m2_add_recognition_events_and_museum_stats.py` — recognition_events 埋点表(KPI+展陈证据一表两吃)+ museums.stats JSONB。 (~369 tok)
- `q1n3_add_museum_intro.py` — museums 加 description_i18n(AI 接地介绍)+ cover_image_key(得体封面)。 (~144 tok)
- `r1o4_add_llm_usage.py` — llm_usage 用量记账表(成本可观测性)。 (~202 tok)
- `s1p5_add_purchases_entitlements.py` — 订单与时长权益表 + 首件免费语音字段(收费模式定案 2026-07-27)。 (~953 tok)
- `t1q6_add_app_events.py` — 付费漏斗埋点表(P0-c,2026-07-27)。只做 12 个核心事件。 (~398 tok)

## backend/alembic/versions/**pycache**/

- `001_create_recognition_results_table.cpython-311.pyc` (~890 tok)
- `002_optimize_recognition_indexes.cpython-311.pyc` (~1112 tok)
- `003_create_stats_tables.cpython-311.pyc` (~2466 tok)
- `004_fix_timestamp_default.cpython-311.pyc` — Declares instead (~513 tok)
- `006_add_user_auth.cpython-311.pyc` (~982 tok)
- `007_allow_null_email.cpython-311.pyc` (~365 tok)
- `008_add_is_guest_field.cpython-311.pyc` (~312 tok)
- `009_user_benefits_and_cleanup.cpython-311.pyc` (~959 tok)
- `a3b3_add_content_status.cpython-311.pyc` (~334 tok)
- `d6ca257376ac_step1_data_foundation.cpython-311.pyc` (~3350 tok)
- `e1a1_add_object_sources.cpython-311.pyc` (~329 tok)
- `f2a2_add_suggested_questions.cpython-311.pyc` (~855 tok)
- `g1d3_add_guide_section_type.cpython-311.pyc` — Declares Revises (~510 tok)
- `h1e4_add_evidence_pack.cpython-311.pyc` (~333 tok)
- `i1f5_retire_overview_tab.cpython-311.pyc` (~312 tok)
- `j1g6_add_artists.cpython-311.pyc` (~695 tok)
- `k1h7_add_name_i18n.cpython-311.pyc` (~316 tok)
- `l1i8_add_recognition_demands.cpython-311.pyc` (~689 tok)
- `m1j9_add_artist_facts_i18n.cpython-311.pyc` (~423 tok)
- `n1k0_add_audio_keys.cpython-311.pyc` (~406 tok)
- `o1l1_add_object_embeddings.cpython-311.pyc` (~678 tok)
- `p1m2_add_recognition_events_and_museum_stats.cpython-311.pyc` (~721 tok)

## backend/app/

- `__init__.py` (~0 tok)
- `main.py` — backend/app/main.py (~951 tok)

## backend/app/**pycache**/

- `__init__.cpython-311.pyc` (~45 tok)
- `__init__.cpython-314.pyc` (~42 tok)
- `main.cpython-311.pyc` (~1432 tok)

## backend/app/api/

- `__init__.py` — API module initialization (~27 tok)

## backend/app/api/**pycache**/

- `__init__.cpython-311.pyc` (~80 tok)

## backend/app/api/v1/

- `__init__.py` — API v1 initialization (~436 tok)

## backend/app/api/v1/**pycache**/

- `__init__.cpython-311.pyc` (~481 tok)

## backend/app/api/v1/endpoints/

- `__init__.py` — API v1 endpoints initialization (~32 tok)
- `auth.py` — Authentication API endpoints (~1729 tok)
- `chat.py` — API: POST, GET (2 endpoints) (~2324 tok)
- `content.py` — API: POST, GET (4 endpoints) (~3164 tok)
- `entitlements.py` — 统一权益接口(收费模式定案 2026-07-27)。 (~486 tok)
- `history.py` — API: GET, DELETE (4 endpoints) (~2392 tok)
- `museums.py` — Museum pack endpoints (~1747 tok)
- `payment.py` — API: POST, GET (3 endpoints) (~3100 tok)
- `recognition.py` — API: POST, GET (4 endpoints) (~2301 tok)
- `recognize_global.py` — 全局识别端点 POST /api/v1/recognize(museum 可选)。 (~871 tok)
- `search.py` — 搜索端点(加法契约,识别机制的姊妹功能)。 (~391 tok)

## backend/app/api/v1/endpoints/**pycache**/

- `__init__.cpython-311.pyc` (~88 tok)
- `auth.cpython-311.pyc` (~2341 tok)
- `chat.cpython-311.pyc` (~2325 tok)
- `content.cpython-311.pyc` (~4106 tok)
- `entitlements.cpython-311.pyc` (~853 tok)
- `history.cpython-311.pyc` (~3247 tok)
- `museums.cpython-311.pyc` (~2232 tok)
- `payment.cpython-311.pyc` (~3721 tok)
- `recognition.cpython-311.pyc` (~2906 tok)
- `recognize_global.cpython-311.pyc` (~1210 tok)
- `search.cpython-311.pyc` (~672 tok)

## backend/app/core/

- `__init__.py` — Core module initialization (~209 tok)
- `config.py` — Settings: get_database_url, get_settings (~1104 tok)
- `database.py` — SQLAlchemy: SessionLocal (~776 tok)
- `exceptions.py` — Declares GoMuseumException (~355 tok)
- `rate_limit.py` — 全局速率限制器（slowapi，按客户端 IP） (~77 tok)
- `security.py` — Security utilities for password hashing and JWT (~558 tok)
- `token_blacklist.py` — Refresh token 撤销名单 (~558 tok)

## backend/app/core/**pycache**/

- `__init__.cpython-311.pyc` (~253 tok)
- `__init__.cpython-314.pyc` (~208 tok)
- `config.cpython-311.pyc` (~1434 tok)
- `config.cpython-314.pyc` (~1590 tok)
- `database.cpython-311.pyc` (~909 tok)
- `exceptions.cpython-311.pyc` — Declares for (~835 tok)
- `rate_limit.cpython-311.pyc` (~157 tok)
- `security.cpython-311.pyc` (~972 tok)
- `token_blacklist.cpython-311.pyc` (~970 tok)

## backend/app/models/

- `__init__.py` — Models module initialization (~207 tok)
- `ai_service_log.py` — SQLAlchemy: AIServiceLog (ai_service_logs) (~1254 tok)
- `app_event.py` — 付费漏斗埋点(P0-c,2026-07-27)。 (~465 tok)
- `artist.py` — 作者一等实体:按 artist QID 生成一次的规范作者介绍,同作者作品复用。 (~478 tok)
- `content.py` — 讲解内容：SectionType（tab 词表）+ CategorySection（类→tab 映射）+ ObjectContentSection（实际内容）。 (~986 tok)
- `llm_usage.py` — LLM 用量记账(成本可观测性,backlog LLM成本工程①)。 (~185 tok)
- `museum_object.py` — 通用展品（MuseumObject）+ 展品图片（ObjectImage，一对多）。 (~916 tok)
- `museum.py` — 博物馆实体。 (~375 tok)
- `object_embedding.py` — 展品参考图向量(生成一次永久落库;model 字段版本化,换模型共存不冲突)。 (~272 tok)
- `purchase.py` — 内购订单与时长权益(收费模式定案 2026-07-27)。 (~802 tok)
- `recognition_demand.py` — 未收录需求记录:识别不中即记,按 (馆, 感知哈希) 幂等聚合计数。 (~324 tok)
- `recognition_event.py` — 识别事件埋点:KPI(识别率/引擎分布)+ 展陈证据一表两吃。每次 recognize() 落一行。 (~287 tok)
- `recognition_result.py` — SQLAlchemy: RecognitionResult (recognition_results) (~607 tok)
- `recognition_stats.py` — SQLAlchemy: RecognitionStats (recognition_stats) (~1089 tok)
- `user_benefits.py` — SQLAlchemy: UserBenefits (user_benefits) (~1524 tok)
- `user.py` — User model for authentication (~414 tok)

## backend/app/models/**pycache**/

- `__init__.cpython-311.pyc` (~279 tok)
- `ai_service_log.cpython-311.pyc` (~1472 tok)
- `app_event.cpython-311.pyc` (~590 tok)
- `artist.cpython-311.pyc` (~802 tok)
- `content.cpython-311.pyc` (~1563 tok)
- `llm_usage.cpython-311.pyc` (~331 tok)
- `museum_object.cpython-311.pyc` (~1360 tok)
- `museum.cpython-311.pyc` (~696 tok)
- `object_embedding.cpython-311.pyc` (~493 tok)
- `purchase.cpython-311.pyc` (~1159 tok)
- `recognition_demand.cpython-311.pyc` (~590 tok)
- `recognition_event.cpython-311.pyc` (~511 tok)
- `recognition_result.cpython-311.pyc` (~873 tok)
- `recognition_stats.cpython-311.pyc` (~1319 tok)
- `user_benefits.cpython-311.pyc` (~1646 tok)
- `user.cpython-311.pyc` (~624 tok)

## backend/app/schemas/

- `__init__.py` — Schemas module initialization (~92 tok)
- `auth.py` — Authentication schemas (~263 tok)
- `recognition.py` — Pydantic: RecognitionRequest (21 fields) (~1272 tok)
- `user.py` — User schemas for API validation (~226 tok)

## backend/app/schemas/**pycache**/

- `__init__.cpython-311.pyc` (~139 tok)
- `auth.cpython-311.pyc` (~653 tok)
- `recognition.cpython-311.pyc` (~1939 tok)
- `user.cpython-311.pyc` (~615 tok)

## backend/app/services/

- `__init__.py` — Services module initialization (~127 tok)
- `ai_service.py` — AIService: recognize, recognize_with_timeout (~3962 tok)
- `auth_service.py` — Authentication service (~5309 tok)
- `benefits_service.py` — BenefitsService: get_or_create_benefits, check_access, consume_recognition, add_recognition_pack + 4 more (~2356 tok)
- `cache_service.py` — CacheService: get_cached_result, get_similar_cached_result, cache_result, invalidate_cache + 3 more (~3349 tok)
- `content_cache.py` — 内容缓存与 AI 用量熔断 (~1549 tok)
- `content_generation_service.py` — ContentGenerationService: generate_explanation (~3702 tok)
- `content_repo.py` — 把一次生成的讲解（含 5 子字段）落库到 object_content_section（按 qid + 语言）。 (~1780 tok)
- `entitlement_service.py` — 统一权益判断(收费模式定案 2026-07-27)。 (~1844 tok)
- `event_log.py` — 事件记录。**记账失败绝不破坏业务** —— 与 llm_usage 同纪律。 (~201 tok)
- `iap_verification_service.py` — IAPVerificationService: verify_apple_receipt, verify_google_receipt, get_iap_verification_service (~2333 tok)
- `image_service.py` — ImageService: validate_image, generate_hash, generate_perceptual_hash, hash_similarity + 4 more (~2705 tok)
- `llm_usage.py` — LLM 用量记账 helper(成本工程①)。记账绝不拖垮生成:任何失败吞掉只告警。 (~359 tok)
- `museum_repo.py` — 从 DB 读馆藏并拼回与旧 museum_packs JSON 完全一致的形状（保接口兼容）。 (~6514 tok)
- `object_importer.py` — 把一条馆/展品数据幂等 upsert 进库。匹配优先级：qid → (museum, inventory_number)。 (~818 tok)
- `recognition_service.py` — RecognitionService: recognize_artwork, get_recognition_by_id, get_recent_recognitions, get_statistics + 1 more (~2824 tok)
- `tts_service.py` — TTSService: generate_audio, generate_audio_stream, get_supported_voices, generate_text_hash + 1 more (~2784 tok)

## backend/app/services/**pycache**/

- `__init__.cpython-311.pyc` (~182 tok)
- `__init__.cpython-314.pyc` (~157 tok)
- `ai_service.cpython-311.pyc` (~4610 tok)
- `ai_service.cpython-314.pyc` (~4638 tok)
- `auth_service.cpython-311.pyc` (~5719 tok)
- `benefits_service.cpython-311.pyc` (~2893 tok)
- `cache_service.cpython-311.pyc` (~4143 tok)
- `content_cache.cpython-311.pyc` (~2638 tok)
- `content_generation_service.cpython-311.pyc` (~3883 tok)
- `content_repo.cpython-311.pyc` (~2714 tok)
- `entitlement_service.cpython-311.pyc` (~2317 tok)
- `event_log.cpython-311.pyc` (~350 tok)
- `iap_verification_service.cpython-311.pyc` (~2324 tok)
- `image_service.cpython-311.pyc` (~3263 tok)
- `llm_usage.cpython-311.pyc` (~628 tok)
- `museum_repo.cpython-311.pyc` (~8779 tok)
- `object_importer.cpython-311.pyc` (~1290 tok)
- `recognition_service.cpython-311.pyc` — Declares to (~3450 tok)
- `tts_service.cpython-311.pyc` (~3319 tok)

## backend/app/services/coverage/

- `__init__.py` (~0 tok)
- `display_state.py` — 展陈状态汇总:识别流量证据(强,动态)+ Wikidata P276 静态先验(弱)→ attributes["display"]。 (~1274 tok)
- `joconde.py` — Joconde 区域适配器样板:按 Joconde 编号(external_ids["P347"])查 data.culture.gouv.fr (~984 tok)

## backend/app/services/coverage/**pycache**/

- `__init__.cpython-311.pyc` (~50 tok)
- `display_state.cpython-311.pyc` (~1766 tok)
- `joconde.cpython-311.pyc` (~1394 tok)

## backend/app/services/enrichment/

- `__init__.py` (~0 tok)
- `backfill.py` — 既有对象 content_status 回填：有已发布 section → ready，否则 stub。 (~4286 tok)
- `batch_names.py` — names 的 Batch 模式(成本工程②,spec 2026-07-19-batch-names)。 (~2770 tok)
- `catalog_loader.py` — 把 CatalogSource 产的 StubRecord 列灌成 stub 对象（只元数据 + 路由信息）。 (~954 tok)
- `catalog_source.py` — 目录层抽象：CatalogSource 列对象产 StubRecord（元数据+身份），供身份去重 + 落 stub。 (~306 tok)
- `catalog.py` — View: get (~761 tok)
- `category_config.py` — 类别单一真相源：Wikidata P31 QID → canonical 类别名。 (~2821 tok)
- `content_enricher.py` — ContentEnricher：把事实 + Wikipedia 素材接地生成英语轴心分段讲解。 (~1526 tok)
- `content_report.py` — 内容质量报告（canary）：从 DB 已生成内容算覆盖率/needs_review%/缺音频。spec §8B。 (~648 tok)
- `evidence.py` — 证据包组装:结构原子事实 + 标源叙事块 + LLM 抽争议。spec 2026-06-29-evidence-pack。 (~1742 tok)
- `factory.py` — 生成组件工厂:onboard generate 与懒生成共用装配(LLM 组件/registry/语言)。 (~534 tok)
- `fetcher.py` — Fetcher: fetch (~786 tok)
- `http_client.py` — 礼貌抓取 HTTP 客户端：UA 强制 + 令牌桶限速 + 429/503 退避（遵守 Retry-After）+ 熔断。 (~699 tok)
- `identity.py` — 身份去重：多源 StubRecord 按强键归并成一对象。 (~311 tok)
- `lang_config.py` — 目标翻译语言集配置：全局默认 + museums.yaml 覆盖，代码零硬编码语言。spec §14。 (~203 tok)
- `lang_detect.py` — 语言一致性检测器:text 是否真的是 lang(散文校验)。离线、确定性。 (~649 tok)
- `lazy_audio.py` — guide 音频懒生成(点播放触发):有 audio_key 秒返,否则生成+落库+返 URL。仅 guide(Phase1)。 (~1559 tok)
- `lazy.py` — 懒生成(路线图3c):stub 首次访问触发后台生成一次。 (~2348 tok)
- `loader.py` — select_sample, load (~409 tok)
- `material.py` — 逐件材料富化：给一件（qid + 外部ID + wiki 标题）按需路由富化源、抓材料、merge。 (~3774 tok)
- `materializer.py` — 图像物化器:扫"有 source_url 无 image_key"的 ObjectImage 行 → (~2018 tok)
- `merge.py` — 优先级：越靠后越高。v1 只有 wikidata。 (~492 tok)
- `museum_intro.py` — 博物馆介绍 + 封面(spec 2026-07-18)。 (~1856 tok)
- `pack_store.py` — View: put, get (~284 tok)
- `pipeline.py` — generate 编排：DB 对象 → 生成(2a) → 质量闸(2b) → 落英语 → 翻译(2c) → 按语言落库。 (~4830 tok)
- `prompts.py` — grounded 生成 prompt：只依据材料、类别感知、原创表达、缺料留空。 (~4750 tok)
- `qa_suggester.py` — QASuggester：每件接地预生成 3-4 个"问题+答案"（英语轴心→答案过闸→翻译铺语言）。 (~1080 tok)
- `quality.py` — 质量闸 QualityGate：逐句蕴含校验删不支持句 + 叙事/硬事实对账 + 质量分 → status。 (~1216 tok)
- `registry.py` — 源注册表 + 外部 ID 路由：读对象 Wikidata 外部 ID → 自动选适用连接器(零管理员配置)。 (~288 tok)
- `report.py` — build_report (~398 tok)
- `source_cache.py` — 源抓取结果缓存：抓一次复用（键 source+key+day），走 ObjectStorage（本地/R2）。 (~320 tok)
- `streaming_audio.py` — TTS 流式播放 + 解耦落库(单次 tee)。 (~1443 tok)
- `translator.py` — ContentTranslator：把英语轴心正文翻译到目标语言 + 译文忠实校验。 (~1165 tok)
- `views.py` — 雕塑多视角补图:Wikidata→Commons 分类→他人照片规范 URL 注入既有图管线。 (~1066 tok)

## backend/app/services/enrichment/**pycache**/

- `__init__.cpython-311.pyc` (~50 tok)
- `backfill.cpython-311.pyc` (~6222 tok)
- `batch_names.cpython-311.pyc` (~4328 tok)
- `catalog_loader.cpython-311.pyc` (~1399 tok)
- `catalog_source.cpython-311.pyc` (~588 tok)
- `catalog.cpython-311.pyc` (~1241 tok)
- `category_config.cpython-311.pyc` (~2220 tok)
- `content_enricher.cpython-311.pyc` (~2716 tok)
- `content_report.cpython-311.pyc` (~1334 tok)
- `evidence.cpython-311.pyc` — Declares as (~2042 tok)
- `factory.cpython-311.pyc` (~888 tok)
- `fetcher.cpython-311.pyc` (~1039 tok)
- `http_client.cpython-311.pyc` (~1040 tok)
- `identity.cpython-311.pyc` (~575 tok)
- `lang_config.cpython-311.pyc` (~260 tok)
- `lang_detect.cpython-311.pyc` (~920 tok)
- `lazy_audio.cpython-311.pyc` (~2313 tok)
- `lazy.cpython-311.pyc` (~3576 tok)
- `loader.cpython-311.pyc` (~774 tok)
- `material.cpython-311.pyc` (~5507 tok)
- `materializer.cpython-311.pyc` (~3087 tok)
- `merge.cpython-311.pyc` (~687 tok)
- `museum_intro.cpython-311.pyc` (~2778 tok)
- `pack_store.cpython-311.pyc` (~733 tok)
- `pipeline.cpython-311.pyc` (~5777 tok)
- `prompts.cpython-311.pyc` (~4743 tok)
- `qa_suggester.cpython-311.pyc` (~1578 tok)
- `quality.cpython-311.pyc` (~1898 tok)
- `registry.cpython-311.pyc` (~760 tok)
- `report.cpython-311.pyc` (~1074 tok)
- `source_cache.cpython-311.pyc` (~676 tok)
- `streaming_audio.cpython-311.pyc` (~2319 tok)
- `translator.cpython-311.pyc` (~1483 tok)
- `views.cpython-311.pyc` (~1667 tok)

## backend/app/services/enrichment/sources/

- `__init__.py` (~0 tok)
- `base.py` — class: fetch, probe, enrich (~274 tok)
- `joconde_catalog.py` — JocondeCatalog：从 data.culture.gouv.fr(Joconde 开放数据)列该馆全部作品 → StubRecord。 (~1254 tok)
- `joconde.py` — JocondeSource：法国国家藏品库(data.culture.gouv.fr base-joconde-extrait)。 (~538 tok)
- `wikidata_catalog.py` — WikidataCatalog：用现有 Wikidata SPARQL 主干列对象、产 StubRecord。 (~1235 tok)
- `wikidata.py` — WikidataSource: run_sparql, build_cat_filter, fetch (~1710 tok)
- `wikipedia.py` — WikipediaSource：按对象各语言 Wikipedia 标题拉**全文** plaintext（叙事接地素材，有界）。 (~472 tok)

## backend/app/services/enrichment/sources/**pycache**/

- `__init__.cpython-311.pyc` (~52 tok)
- `base.cpython-311.pyc` (~587 tok)
- `joconde_catalog.cpython-311.pyc` (~1784 tok)
- `joconde.cpython-311.pyc` (~918 tok)
- `wikidata_catalog.cpython-311.pyc` (~1541 tok)
- `wikidata.cpython-311.pyc` (~2238 tok)
- `wikipedia.cpython-311.pyc` (~691 tok)

## backend/app/services/recognition/

- `__init__.py` (~0 tok)
- `demands.py` — 未收录需求记录(契约R5 需求自适应):同 (馆, phash) 幂等计数;墙签文字/候选有值则更新。 (~260 tok)
- `embedder.py` — 线上 embedding 引擎:DINOv2 ONNX 推理 + 模型 R2 懒下载。 (~1300 tok)
- `embeddings.py` — 入库即嵌入(生成一次永久落库):补图/backfill 共用。失败只记日志不阻断主流程。 (~694 tok)
- `events.py` — 识别事件埋点(KPI + 展陈证据一表两吃):落一行 recognition_events;确认回填 confirmed_qid。 (~530 tok)
- `matcher.py` — 匹配层(识别的不变核心;P2 换 CLIP 引擎也不动它): (~1453 tok)
- `service.py` — 识别编排:校验/哈希 → 缓存 → vision(引擎位,P2 换 CLIP) → 目录匹配 → 三档分流。 (~3497 tok)
- `vector_index.py` — 向量索引(识别的查询侧):全量 embedding → numpy 矩阵,余弦 Top-k。 (~627 tok)
- `vision.py` — 识别器:一次 GPT-4o-mini 视觉调用 → 候选名(R1:只当查询,绝不当答案展示) (~1061 tok)

## backend/app/services/recognition/**pycache**/

- `__init__.cpython-311.pyc` (~50 tok)
- `demands.cpython-311.pyc` (~372 tok)
- `embedder.cpython-311.pyc` (~2436 tok)
- `embeddings.cpython-311.pyc` (~880 tok)
- `events.cpython-311.pyc` (~844 tok)
- `matcher.cpython-311.pyc` (~2711 tok)
- `service.cpython-311.pyc` (~4406 tok)
- `vector_index.cpython-311.pyc` (~1347 tok)
- `vision.cpython-311.pyc` (~1504 tok)

## backend/app/services/search/

- `__init__.py` (~0 tok)
- `inprocess.py` — 搜索引擎首发实现:进程内索引(可替换)。 (~2415 tok)

## backend/app/services/search/**pycache**/

- `__init__.cpython-311.pyc` (~49 tok)
- `inprocess.cpython-311.pyc` (~3717 tok)

## backend/app/services/storage/

- `__init__.py` — 存储工厂：按 settings.STORAGE_BACKEND 返回单例 ObjectStorage。 (~266 tok)
- `base.py` — 对象存储统一抽象：图片/音频。实现见 local.py（本地）、r2.py（Cloudflare R2）。 (~178 tok)
- `local.py` — 本地文件实现：落盘到 root_dir/key，public_url 走后端静态前缀。 (~287 tok)
- `r2.py` — Cloudflare R2（S3 兼容）实现。public_url 走 R2_PUBLIC_BASE_URL。 (~580 tok)

## backend/app/services/storage/**pycache**/

- `__init__.cpython-311.pyc` (~355 tok)
- `base.cpython-311.pyc` (~467 tok)
- `local.cpython-311.pyc` (~796 tok)
- `r2.cpython-311.pyc` (~982 tok)

## backend/app/utils/

- `__init__.py` — Utils module initialization (~92 tok)
- `database_utils.py` — DatabaseUtils: explain_query, get_table_sizes, get_index_usage, get_slow_queries + 5 more (~3504 tok)
- `performance_monitor.py` — PerformanceMonitor: track_request_time, get_p95_latency, get_p99_latency, get_average_latency + 14 more (~1933 tok)

## backend/app/utils/**pycache**/

- `__init__.cpython-311.pyc` (~128 tok)
- `database_utils.cpython-311.pyc` — Declares for (~4296 tok)
- `performance_monitor.cpython-311.pyc` — Declares performance (~2830 tok)

## backend/app/workers/

- `__init__.py` (~0 tok)

## backend/gomuseum_backend.egg-info/

- `dependency_links.txt` (~1 tok)
- `PKG-INFO` (~513 tok)
- `requires.txt` (~172 tok)
- `SOURCES.txt` (~295 tok)
- `top_level.txt` (~1 tok)

## backend/htmlcov/

- `.gitignore` — Git ignore rules (~8 tok)
- `class_index.html` — Coverage report (~19056 tok)
- `coverage_html_cb_6fb7b396.js` — For details: https://github.com/nedbat/coveragepy/blob/master/NOTICE.txt (~7279 tok)
- `function_index.html` — Coverage report (~76910 tok)
- `index.html` — Coverage report (~11104 tok)
- `status.json` (~9590 tok)
- `style_cb_6b508a39.css` — Styles: 117 rules, 51 media queries (~4468 tok)
- `z_257b53c25398f6ee___init___py.html` — Coverage for app/api/v1/**init**.py: 0% (~5047 tok)
- `z_41f09dac0431399d_auth_py.html` — Coverage for app/api/v1/endpoints/auth.py: 0% (~14153 tok)
- `z_41f09dac0431399d_entitlements_py.html` — Coverage for app/api/v1/endpoints/entitlements.py: 0% (~4392 tok)
- `z_41f09dac0431399d_museums_py.html` — Coverage for app/api/v1/endpoints/museums.py: 0% (~16703 tok)
- `z_41f09dac0431399d_recognition_py.html` — Coverage for app/api/v1/endpoints/recognition.py: 0% (~18834 tok)
- `z_41f09dac0431399d_recognize_global_py.html` — Coverage for app/api/v1/endpoints/recognize_global.py: 0% (~9209 tok)
- `z_41f09dac0431399d_search_py.html` — Coverage for app/api/v1/endpoints/search.py: 0% (~5141 tok)
- `z_43a9dab25ffe7d4f_display_state_py.html` — Coverage for app/services/coverage/display_state.py: 0% (~12308 tok)
- `z_43a9dab25ffe7d4f_joconde_py.html` — Coverage for app/services/coverage/joconde.py: 0% (~9376 tok)
- `z_4b42c0c19a0de449___init___py.html` — Coverage for app/services/storage/**init**.py: 0% (~3311 tok)
- `z_4b42c0c19a0de449_local_py.html` — Coverage for app/services/storage/local.py: 0% (~4321 tok)
- `z_4b42c0c19a0de449_r2_py.html` — Coverage for app/services/storage/r2.py: 0% (~6554 tok)
- `z_57076877a629fb66_base_py.html` — Coverage for app/services/enrichment/sources/base.py: 0% (~3708 tok)
- `z_57076877a629fb66_joconde_catalog_py.html` — Coverage for app/services/enrichment/sources/joconde_catalog.py: 0% (~12494 tok)
- `z_57076877a629fb66_joconde_py.html` — Coverage for app/services/enrichment/sources/joconde.py: 0% (~5870 tok)
- `z_57076877a629fb66_wikidata_catalog_py.html` — Coverage for app/services/enrichment/sources/wikidata_catalog.py: 0% (~11099 tok)
- `z_57076877a629fb66_wikidata_py.html` — Coverage for app/services/enrichment/sources/wikidata.py: 0% (~13819 tok)
- `z_57076877a629fb66_wikipedia_py.html` — Coverage for app/services/enrichment/sources/wikipedia.py: 0% (~5444 tok)
- `z_5f5a17c013354698_main_py.html` — Coverage for app/main.py: 0% (~9254 tok)
- `z_6c0e4b930745278b_ai_service_log_py.html` — Coverage for app/models/ai_service_log.py: 88% (~10278 tok)
- `z_6c0e4b930745278b_app_event_py.html` — Coverage for app/models/app_event.py: 0% (~5487 tok)
- `z_6c0e4b930745278b_llm_usage_py.html` — Coverage for app/models/llm_usage.py: 0% (~2923 tok)
- `z_6c0e4b930745278b_recognition_result_py.html` — Coverage for app/models/recognition_result.py: 94% (~5847 tok)
- `z_6c0e4b930745278b_recognition_stats_py.html` — Coverage for app/models/recognition_stats.py: 75% (~8740 tok)
- `z_6c0e4b930745278b_user_benefits_py.html` — Coverage for app/models/user_benefits.py: 58% (~13006 tok)
- `z_748a0465d46c2a16_database_utils_py.html` — Coverage for app/utils/database_utils.py: 0% (~25598 tok)
- `z_748a0465d46c2a16_performance_monitor_py.html` — Coverage for app/utils/performance_monitor.py: 0% (~16699 tok)
- `z_8f7e1016f2d37417_config_py.html` — Coverage for app/core/config.py: 97% (~9846 tok)
- `z_8f7e1016f2d37417_database_py.html` — Coverage for app/core/database.py: 69% (~6567 tok)
- `z_8f7e1016f2d37417_security_py.html` — Coverage for app/core/security.py: 0% (~6133 tok)
- `z_8f7e1016f2d37417_token_blacklist_py.html` — Coverage for app/core/token_blacklist.py: 0% (~6287 tok)
- `z_ba332e4ad85229f5_inprocess_py.html` — Coverage for app/services/search/inprocess.py: 0% (~22911 tok)
- `z_c0f67d75e686303c_recognition_py.html` — Coverage for app/schemas/recognition.py: 61% (~10542 tok)
- `z_c318f3fa19a49f69_ai_service_py.html` — Coverage for app/services/ai_service.py: 12% (~28314 tok)
- `z_c318f3fa19a49f69_auth_service_py.html` — Coverage for app/services/auth_service.py: 0% (~42445 tok)
- `z_c318f3fa19a49f69_cache_service_py.html` — Coverage for app/services/cache_service.py: 10% (~24098 tok)
- `z_c318f3fa19a49f69_content_cache_py.html` — Coverage for app/services/content_cache.py: 0% (~14415 tok)
- `z_c318f3fa19a49f69_content_repo_py.html` — Coverage for app/services/content_repo.py: 0% (~17779 tok)
- `z_c318f3fa19a49f69_entitlement_service_py.html` — Coverage for app/services/entitlement_service.py: 71% (~18302 tok)
- `z_c318f3fa19a49f69_event_log_py.html` — Coverage for app/services/event_log.py: 0% (~3334 tok)
- `z_c318f3fa19a49f69_image_service_py.html` — Coverage for app/services/image_service.py: 29% (~20106 tok)
- `z_c318f3fa19a49f69_llm_usage_py.html` — Coverage for app/services/llm_usage.py: 0% (~4825 tok)
- `z_c318f3fa19a49f69_museum_repo_py.html` — Coverage for app/services/museum_repo.py: 0% (~62229 tok)
- `z_c318f3fa19a49f69_object_importer_py.html` — Coverage for app/services/object_importer.py: 0% (~9330 tok)
- `z_e9d3c5ffcd110500_backfill_py.html` — Coverage for app/services/enrichment/backfill.py: 0% (~39402 tok)
- `z_e9d3c5ffcd110500_batch_names_py.html` — Coverage for app/services/enrichment/batch_names.py: 0% (~26776 tok)
- `z_e9d3c5ffcd110500_catalog_loader_py.html` — Coverage for app/services/enrichment/catalog_loader.py: 0% (~9298 tok)
- `z_e9d3c5ffcd110500_catalog_py.html` — Coverage for app/services/enrichment/catalog.py: 0% (~7864 tok)
- `z_e9d3c5ffcd110500_category_config_py.html` — Coverage for app/services/enrichment/category_config.py: 0% (~25737 tok)
- `z_e9d3c5ffcd110500_content_enricher_py.html` — Coverage for app/services/enrichment/content_enricher.py: 0% (~15516 tok)
- `z_e9d3c5ffcd110500_evidence_py.html` — Coverage for app/services/enrichment/evidence.py: 0% (~15736 tok)
- `z_e9d3c5ffcd110500_factory_py.html` — Coverage for app/services/enrichment/factory.py: 0% (~5448 tok)
- `z_e9d3c5ffcd110500_fetcher_py.html` — Coverage for app/services/enrichment/fetcher.py: 0% (~7906 tok)
- `z_e9d3c5ffcd110500_http_client_py.html` — Coverage for app/services/enrichment/http_client.py: 0% (~7022 tok)
- `z_e9d3c5ffcd110500_identity_py.html` — Coverage for app/services/enrichment/identity.py: 0% (~4540 tok)
- `z_e9d3c5ffcd110500_lang_detect_py.html` — Coverage for app/services/enrichment/lang_detect.py: 0% (~7201 tok)
- `z_e9d3c5ffcd110500_lazy_audio_py.html` — Coverage for app/services/enrichment/lazy_audio.py: 0% (~15350 tok)
- `z_e9d3c5ffcd110500_lazy_py.html` — Coverage for app/services/enrichment/lazy.py: 0% (~23222 tok)
- `z_e9d3c5ffcd110500_loader_py.html` — Coverage for app/services/enrichment/loader.py: 0% (~5262 tok)
- `z_e9d3c5ffcd110500_material_py.html` — Coverage for app/services/enrichment/material.py: 0% (~34691 tok)
- `z_e9d3c5ffcd110500_materializer_py.html` — Coverage for app/services/enrichment/materializer.py: 0% (~19415 tok)
- `z_e9d3c5ffcd110500_merge_py.html` — Coverage for app/services/enrichment/merge.py: 0% (~5916 tok)
- `z_e9d3c5ffcd110500_museum_intro_py.html` — Coverage for app/services/enrichment/museum_intro.py: 0% (~18038 tok)
- `z_e9d3c5ffcd110500_pack_store_py.html` — Coverage for app/services/enrichment/pack_store.py: 0% (~4072 tok)
- `z_e9d3c5ffcd110500_pipeline_py.html` — Coverage for app/services/enrichment/pipeline.py: 0% (~42862 tok)
- `z_e9d3c5ffcd110500_prompts_py.html` — Coverage for app/services/enrichment/prompts.py: 0% (~21979 tok)
- `z_e9d3c5ffcd110500_qa_suggester_py.html` — Coverage for app/services/enrichment/qa_suggester.py: 0% (~11284 tok)
