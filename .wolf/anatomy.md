# anatomy.md

> Auto-maintained by OpenWolf. Last scanned: 2026-06-22T10:00:00.227Z
> Files: 536 tracked | Anatomy hits: 0 | Misses: 0

## ./

- `.coverage` (~14200 tok)
- `.DS_Store` (~3824 tok)
- `.editorconfig` — Editor configuration (~159 tok)
- `.eslintignore` — Dependencies (~141 tok)
- `.gitignore` — Git ignore rules (~468 tok)
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
- `API_KEYS_SETUP_GUIDE.md` — GoMuseum API Keys 配置指南 (~1070 tok)
- `CACHE_FIX_README.md` — 识别缓存问题修复总结 (~1999 tok)
- `CI_CONFIGURATION.md` — GoMuseum CI/CD 配置说明 (~955 tok)
- `ci-test.md` (~27 tok)
- `ci-test2.txt` (~13 tok)
- `ci-verify.txt` (~14 tok)
- `CLAUDE.md` — Claude Code 项目规则 (claude.md) (~1375 tok)
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
- `STEP1_FINAL_ACCEPTANCE.md` — GoMuseum Step 1 - 最终验收报告 (~2117 tok)
- `STEP1_RE_VALIDATION_REPORT.md` — GoMuseum Step 1 重新验收报告 (~3739 tok)
- `TEST_FRAMEWORK_SUMMARY.md` — GoMuseum Step 1 (图像识别功能) 测试框架创建报告 (~1938 tok)
- `test_openai_api.py` — Tests: openai_api (~534 tok)
- `TEST_STATISTICS.txt` (~841 tok)
- `trigger.txt` (~4 tok)
- `WEB_PLATFORM_FIX_SUMMARY.md` — Web 平台兼容性修复总结 (~811 tok)
- `WEB_PLATFORM_FIX.md` — Web 平台兼容性修复文档 (~1307 tok)

## .claude/

- `settings.local.json` (~60 tok)

## .claude/commands/

- `pr.md` (~207 tok)

## .github/workflows/

- `branch-guard.yml` — 守卫：只有 staging 分支可以向 main 提 PR（GitHub 原生分支保护无法限制 PR 来源分支） (~161 tok)
- `ci.yml` — GoMuseum CI/CD 流水线配置（适配个人用户，无 GHAS） (~1935 tok)
- `deploy.yml` — CI: Deploy (~947 tok)
- `sync-main-to-staging.yml` — CI: Sync main → staging (~283 tok)

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

## .vscode/

- `extensions.json` (~215 tok)
- `settings.json` (~370 tok)

## backend/

- `.coverage` (~28399 tok)
- `.coveragerc` (~0 tok)
- `.dockerignore` — Docker ignore rules (~24 tok)
- `.flake8` (~0 tok)
- `.python-version` (~2 tok)
- `alembic.ini` — A generic, single database configuration. (~931 tok)
- `DATABASE_OPTIMIZATION_SUMMARY.md` — GoMuseum 数据库优化总结报告 (~1805 tok)
- `Dockerfile` — Docker container definition (~310 tok)
- `Dockerfile.prod` (~0 tok)
- `main.py` — backend/main.py (~38 tok)
- `museums.yaml` — 馆配置：加一个馆 = 加一段 (~92 tok)
- `pyproject.toml` — Python project configuration (~1226 tok)
- `requirements.txt` — Python dependencies (~74 tok)
- `test_api_connection.py` — Tests: openai, claude, fallback_strategy (~1338 tok)
- `TESTING.md` — Testing & Coverage Configuration (~599 tok)
- `zz_cov_probe.py` (~15 tok)

## backend/.pytest_cache/

- `.gitignore` — Git ignore rules (~10 tok)
- `CACHEDIR.TAG` (~51 tok)
- `README.md` — Project documentation (~76 tok)

## backend/.pytest_cache/v/cache/

- `lastfailed` (~217 tok)
- `nodeids` (~14475 tok)

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

## backend/app/

- `__init__.py` (~0 tok)
- `main.py` — backend/app/main.py (~850 tok)

## backend/app/**pycache**/

- `__init__.cpython-311.pyc` (~45 tok)
- `__init__.cpython-314.pyc` (~42 tok)
- `main.cpython-311.pyc` (~1305 tok)

## backend/app/api/

- `__init__.py` — API module initialization (~27 tok)

## backend/app/api/**pycache**/

- `__init__.cpython-311.pyc` (~80 tok)

## backend/app/api/v1/

- `__init__.py` — API v1 initialization (~314 tok)

## backend/app/api/v1/**pycache**/

- `__init__.cpython-311.pyc` (~374 tok)

## backend/app/api/v1/endpoints/

- `__init__.py` — API v1 endpoints initialization (~32 tok)
- `auth.py` — Authentication API endpoints (~1729 tok)
- `chat.py` — API: POST, GET (2 endpoints) (~2162 tok)
- `content.py` — API: POST, GET (4 endpoints) (~3164 tok)
- `history.py` — API: GET, DELETE (4 endpoints) (~2392 tok)
- `museums.py` — Museum pack endpoints (~356 tok)
- `payment.py` — API: POST, GET (3 endpoints) (~2805 tok)
- `recognition.py` — API: POST, GET (4 endpoints) (~2301 tok)

## backend/app/api/v1/endpoints/**pycache**/

- `__init__.cpython-311.pyc` (~88 tok)
- `auth.cpython-311.pyc` (~2341 tok)
- `chat.cpython-311.pyc` (~2632 tok)
- `content.cpython-311.pyc` (~4106 tok)
- `history.cpython-311.pyc` (~3247 tok)
- `museums.cpython-311.pyc` (~624 tok)
- `payment.cpython-311.pyc` (~3524 tok)
- `recognition.cpython-311.pyc` (~2906 tok)

## backend/app/core/

- `__init__.py` — Core module initialization (~209 tok)
- `config.py` — Settings: get_database_url, get_settings (~950 tok)
- `database.py` — SQLAlchemy: SessionLocal (~776 tok)
- `exceptions.py` — Declares GoMuseumException (~355 tok)
- `rate_limit.py` — 全局速率限制器（slowapi，按客户端 IP） (~77 tok)
- `security.py` — Security utilities for password hashing and JWT (~558 tok)
- `token_blacklist.py` — Refresh token 撤销名单 (~558 tok)

## backend/app/core/**pycache**/

- `__init__.cpython-311.pyc` (~253 tok)
- `__init__.cpython-314.pyc` (~208 tok)
- `config.cpython-311.pyc` (~1330 tok)
- `config.cpython-314.pyc` (~1494 tok)
- `database.cpython-311.pyc` (~909 tok)
- `exceptions.cpython-311.pyc` — Declares for (~835 tok)
- `rate_limit.cpython-311.pyc` (~157 tok)
- `security.cpython-311.pyc` (~972 tok)
- `token_blacklist.cpython-311.pyc` (~970 tok)

## backend/app/models/

- `__init__.py` — Models module initialization (~207 tok)
- `ai_service_log.py` — SQLAlchemy: AIServiceLog (ai_service_logs) (~1254 tok)
- `content.py` — 讲解内容：SectionType（tab 词表）+ CategorySection（类→tab 映射）+ ObjectContentSection（实际内容）。 (~966 tok)
- `museum_object.py` — 通用展品（MuseumObject）+ 展品图片（ObjectImage，一对多）。 (~834 tok)
- `museum.py` — 博物馆实体。 (~248 tok)
- `recognition_result.py` — SQLAlchemy: RecognitionResult (recognition_results) (~607 tok)
- `recognition_stats.py` — SQLAlchemy: RecognitionStats (recognition_stats) (~1089 tok)
- `user_benefits.py` — SQLAlchemy: UserBenefits (user_benefits) (~1415 tok)
- `user.py` — User model for authentication (~414 tok)

## backend/app/models/**pycache**/

- `__init__.cpython-311.pyc` (~279 tok)
- `ai_service_log.cpython-311.pyc` (~1472 tok)
- `content.cpython-311.pyc` (~1550 tok)
- `museum_object.cpython-311.pyc` (~1310 tok)
- `museum.cpython-311.pyc` (~552 tok)
- `recognition_result.cpython-311.pyc` (~873 tok)
- `recognition_stats.cpython-311.pyc` (~1319 tok)
- `user_benefits.cpython-311.pyc` (~1491 tok)
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
- `benefits_service.py` — BenefitsService: get_or_create_benefits, check_access, consume_recognition, add_recognition_pack + 4 more (~2257 tok)
- `cache_service.py` — CacheService: get_cached_result, get_similar_cached_result, cache_result, invalidate_cache + 3 more (~3349 tok)
- `content_cache.py` — 内容缓存与 AI 用量熔断 (~1549 tok)
- `content_generation_service.py` — ContentGenerationService: generate_explanation (~3628 tok)
- `content_repo.py` — 把一次生成的讲解（含 5 子字段）落库到 object_content_section（按 qid + 语言）。 (~1609 tok)
- `iap_verification_service.py` — IAPVerificationService: verify_apple_receipt, verify_google_receipt, get_iap_verification_service (~2333 tok)
- `image_service.py` — ImageService: validate_image, generate_hash, generate_perceptual_hash, hash_similarity + 4 more (~2705 tok)
- `museum_repo.py` — 从 DB 读馆藏并拼回与旧 museum_packs JSON 完全一致的形状（保接口兼容）。 (~1352 tok)
- `object_importer.py` — 把一条馆/展品数据幂等 upsert 进库。匹配优先级：qid → (museum, inventory_number)。 (~754 tok)
- `recognition_service.py` — RecognitionService: recognize_artwork, get_recognition_by_id, get_recent_recognitions, get_statistics + 1 more (~2824 tok)
- `tts_service.py` — TTSService: generate_audio, generate_audio_stream, get_supported_voices, generate_text_hash + 1 more (~2536 tok)

## backend/app/services/**pycache**/

- `__init__.cpython-311.pyc` (~182 tok)
- `__init__.cpython-314.pyc` (~157 tok)
- `ai_service.cpython-311.pyc` (~4610 tok)
- `ai_service.cpython-314.pyc` (~4638 tok)
- `auth_service.cpython-311.pyc` (~5719 tok)
- `benefits_service.cpython-311.pyc` (~2812 tok)
- `cache_service.cpython-311.pyc` (~4143 tok)
- `content_cache.cpython-311.pyc` (~2638 tok)
- `content_generation_service.cpython-311.pyc` (~3821 tok)
- `content_repo.cpython-311.pyc` (~2504 tok)
- `iap_verification_service.cpython-311.pyc` (~2324 tok)
- `image_service.cpython-311.pyc` (~3263 tok)
- `museum_repo.cpython-311.pyc` (~2307 tok)
- `object_importer.cpython-311.pyc` (~1219 tok)
- `recognition_service.cpython-311.pyc` — Declares to (~3450 tok)
- `tts_service.cpython-311.pyc` (~2993 tok)

## backend/app/services/enrichment/

- `__init__.py` (~0 tok)
- `backfill.py` — 既有对象 content_status 回填：有已发布 section → ready，否则 stub。 (~229 tok)
- `catalog_source.py` — 目录层抽象：CatalogSource 列对象产 StubRecord（元数据+身份），供身份去重 + 落 stub。 (~221 tok)
- `catalog.py` — View: get (~526 tok)
- `category_config.py` — 类别单一真相源：Wikidata P31 QID → canonical 类别名。 (~1070 tok)
- `content_enricher.py` — ContentEnricher：把事实 + Wikipedia 素材接地生成英语轴心分段讲解。 (~884 tok)
- `content_report.py` — 内容质量报告（canary）：从 DB 已生成内容算覆盖率/needs_review%/缺音频。spec §8B。 (~648 tok)
- `fetcher.py` — Fetcher: fetch (~786 tok)
- `http_client.py` — 礼貌抓取 HTTP 客户端：UA 强制 + 令牌桶限速 + 429/503 退避（遵守 Retry-After）+ 熔断。 (~558 tok)
- `identity.py` — 身份去重：多源 StubRecord 按强键归并成一对象。 (~232 tok)
- `lang_config.py` — 目标翻译语言集配置：全局默认 + museums.yaml 覆盖，代码零硬编码语言。spec §14。 (~166 tok)
- `loader.py` — select_sample, load (~409 tok)
- `merge.py` — 优先级：越靠后越高。v1 只有 wikidata。 (~492 tok)
- `pack_store.py` — View: put, get (~284 tok)
- `pipeline.py` — generate 编排：DB 对象 → 生成(2a) → 质量闸(2b) → 落英语 → 翻译(2c) → 按语言落库。 (~1091 tok)
- `prompts.py` — grounded 生成 prompt：只依据材料、类别感知、原创表达、缺料留空。 (~1574 tok)
- `qa_suggester.py` — QASuggester：每件接地预生成 3-4 个"问题+答案"（英语轴心→答案过闸→翻译铺语言）。 (~617 tok)
- `quality.py` — 质量闸 QualityGate：逐句蕴含校验删不支持句 + 叙事/硬事实对账 + 质量分 → status。 (~756 tok)
- `registry.py` — 源注册表 + 外部 ID 路由：读对象 Wikidata 外部 ID → 自动选适用连接器(零管理员配置)。 (~150 tok)
- `report.py` — build_report (~398 tok)
- `source_cache.py` — 源抓取结果缓存：抓一次复用（键 source+key+day），走 ObjectStorage（本地/R2）。 (~320 tok)
- `translator.py` — ContentTranslator：把英语轴心正文翻译到目标语言 + 译文忠实校验。 (~568 tok)

## backend/app/services/enrichment/**pycache**/

- `__init__.cpython-311.pyc` (~50 tok)
- `backfill.cpython-311.pyc` (~470 tok)
- `catalog_source.cpython-311.pyc` (~506 tok)
- `catalog.cpython-311.pyc` (~981 tok)
- `category_config.cpython-311.pyc` (~949 tok)
- `content_enricher.cpython-311.pyc` (~1586 tok)
- `content_report.cpython-311.pyc` (~1334 tok)
- `fetcher.cpython-311.pyc` (~1039 tok)
- `http_client.cpython-311.pyc` (~916 tok)
- `identity.cpython-311.pyc` (~438 tok)
- `lang_config.cpython-311.pyc` (~236 tok)
- `loader.cpython-311.pyc` (~774 tok)
- `merge.cpython-311.pyc` (~687 tok)
- `pack_store.cpython-311.pyc` (~733 tok)
- `pipeline.cpython-311.pyc` (~1714 tok)
- `prompts.cpython-311.pyc` (~1779 tok)
- `qa_suggester.cpython-311.pyc` (~975 tok)
- `quality.cpython-311.pyc` (~1287 tok)
- `registry.cpython-311.pyc` (~443 tok)
- `report.cpython-311.pyc` (~1074 tok)
- `source_cache.cpython-311.pyc` (~676 tok)
- `translator.cpython-311.pyc` (~883 tok)

## backend/app/services/enrichment/sources/

- `__init__.py` (~0 tok)
- `base.py` — class: fetch, probe, enrich (~274 tok)
- `joconde.py` — JocondeSource：法国国家藏品库(data.culture.gouv.fr base-joconde-extrait)。 (~451 tok)
- `wikidata_catalog.py` — WikidataCatalog：用现有 Wikidata SPARQL 主干列对象、产 StubRecord。 (~772 tok)
- `wikidata.py` — WikidataSource: fetch (~1284 tok)
- `wikipedia.py` — WikipediaSource：按对象各语言 Wikipedia 标题拉正文摘录（叙事接地素材）。 (~307 tok)

## backend/app/services/enrichment/sources/**pycache**/

- `__init__.cpython-311.pyc` (~52 tok)
- `base.cpython-311.pyc` (~587 tok)
- `joconde.cpython-311.pyc` (~785 tok)
- `wikidata_catalog.cpython-311.pyc` (~1247 tok)
- `wikidata.cpython-311.pyc` (~1691 tok)
- `wikipedia.cpython-311.pyc` (~561 tok)

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
- `class_index.html` — Coverage report (~12903 tok)
- `coverage_html_cb_6fb7b396.js` — For details: https://github.com/nedbat/coveragepy/blob/master/NOTICE.txt (~7279 tok)
- `function_index.html` — Coverage report (~40194 tok)
- `index.html` — Coverage report (~7261 tok)
- `status.json` (~5965 tok)
- `style_cb_6b508a39.css` — Styles: 117 rules, 51 media queries (~4468 tok)
- `z_41f09dac0431399d_auth_py.html` — Coverage for app/api/v1/endpoints/auth.py: 0% (~14153 tok)
- `z_41f09dac0431399d_museums_py.html` — Coverage for app/api/v1/endpoints/museums.py: 0% (~4847 tok)
- `z_41f09dac0431399d_recognition_py.html` — Coverage for app/api/v1/endpoints/recognition.py: 0% (~18828 tok)
- `z_4b42c0c19a0de449___init___py.html` — Coverage for app/services/storage/**init**.py: 0% (~3316 tok)
- `z_4b42c0c19a0de449_local_py.html` — Coverage for app/services/storage/local.py: 0% (~4321 tok)
- `z_4b42c0c19a0de449_r2_py.html` — Coverage for app/services/storage/r2.py: 0% (~6554 tok)
- `z_57076877a629fb66_base_py.html` — Coverage for app/services/enrichment/sources/base.py: 88% (~3672 tok)
- `z_57076877a629fb66_joconde_py.html` — Coverage for app/services/enrichment/sources/joconde.py: 0% (~5206 tok)
- `z_57076877a629fb66_wikidata_catalog_py.html` — Coverage for app/services/enrichment/sources/wikidata_catalog.py: 89% (~7891 tok)
- `z_57076877a629fb66_wikidata_py.html` — Coverage for app/services/enrichment/sources/wikidata.py: 27% (~10492 tok)
- `z_57076877a629fb66_wikipedia_py.html` — Coverage for app/services/enrichment/sources/wikipedia.py: 0% (~4039 tok)
- `z_5f5a17c013354698_main_py.html` — Coverage for app/main.py: 0% (~8534 tok)
- `z_6c0e4b930745278b_ai_service_log_py.html` — Coverage for app/models/ai_service_log.py: 88% (~10278 tok)
- `z_6c0e4b930745278b_recognition_result_py.html` — Coverage for app/models/recognition_result.py: 94% (~5847 tok)
- `z_6c0e4b930745278b_recognition_stats_py.html` — Coverage for app/models/recognition_stats.py: 75% (~8740 tok)
- `z_6c0e4b930745278b_user_benefits_py.html` — Coverage for app/models/user_benefits.py: 39% (~11843 tok)
- `z_748a0465d46c2a16_database_utils_py.html` — Coverage for app/utils/database_utils.py: 0% (~25601 tok)
- `z_748a0465d46c2a16_performance_monitor_py.html` — Coverage for app/utils/performance_monitor.py: 0% (~16699 tok)
- `z_8f7e1016f2d37417_config_py.html` — Coverage for app/core/config.py: 97% (~8694 tok)
- `z_8f7e1016f2d37417_database_py.html` — Coverage for app/core/database.py: 69% (~6567 tok)
- `z_8f7e1016f2d37417_security_py.html` — Coverage for app/core/security.py: 0% (~6133 tok)
- `z_8f7e1016f2d37417_token_blacklist_py.html` — Coverage for app/core/token_blacklist.py: 0% (~6287 tok)
- `z_c0f67d75e686303c_recognition_py.html` — Coverage for app/schemas/recognition.py: 61% (~10534 tok)
- `z_c318f3fa19a49f69_ai_service_py.html` — Coverage for app/services/ai_service.py: 12% (~28310 tok)
- `z_c318f3fa19a49f69_auth_service_py.html` — Coverage for app/services/auth_service.py: 0% (~42445 tok)
- `z_c318f3fa19a49f69_cache_service_py.html` — Coverage for app/services/cache_service.py: 10% (~24098 tok)
- `z_c318f3fa19a49f69_content_cache_py.html` — Coverage for app/services/content_cache.py: 0% (~14414 tok)
- `z_c318f3fa19a49f69_content_repo_py.html` — Coverage for app/services/content_repo.py: 0% (~16239 tok)
- `z_c318f3fa19a49f69_image_service_py.html` — Coverage for app/services/image_service.py: 29% (~20108 tok)
- `z_c318f3fa19a49f69_museum_repo_py.html` — Coverage for app/services/museum_repo.py: 0% (~13832 tok)
- `z_c318f3fa19a49f69_object_importer_py.html` — Coverage for app/services/object_importer.py: 81% (~8980 tok)
- `z_e9d3c5ffcd110500_catalog_py.html` — Coverage for app/services/enrichment/catalog.py: 66% (~6197 tok)
- `z_e9d3c5ffcd110500_category_config_py.html` — Coverage for app/services/enrichment/category_config.py: 79% (~12078 tok)
- `z_e9d3c5ffcd110500_content_enricher_py.html` — Coverage for app/services/enrichment/content_enricher.py: 0% (~9738 tok)
- `z_e9d3c5ffcd110500_content_report_py.html` — Coverage for app/services/enrichment/content_report.py: 0% (~7096 tok)
- `z_e9d3c5ffcd110500_fetcher_py.html` — Coverage for app/services/enrichment/fetcher.py: 0% (~7910 tok)
- `z_e9d3c5ffcd110500_identity_py.html` — Coverage for app/services/enrichment/identity.py: 93% (~3888 tok)
- `z_e9d3c5ffcd110500_lang_config_py.html` — Coverage for app/services/enrichment/lang_config.py: 0% (~2932 tok)
- `z_e9d3c5ffcd110500_loader_py.html` — Coverage for app/services/enrichment/loader.py: 0% (~5260 tok)
- `z_e9d3c5ffcd110500_merge_py.html` — Coverage for app/services/enrichment/merge.py: 0% (~5911 tok)
- `z_e9d3c5ffcd110500_pack_store_py.html` — Coverage for app/services/enrichment/pack_store.py: 0% (~4068 tok)
- `z_e9d3c5ffcd110500_pipeline_py.html` — Coverage for app/services/enrichment/pipeline.py: 0% (~12107 tok)
- `z_e9d3c5ffcd110500_prompts_py.html` — Coverage for app/services/enrichment/prompts.py: 0% (~8836 tok)
- `z_e9d3c5ffcd110500_quality_py.html` — Coverage for app/services/enrichment/quality.py: 0% (~7806 tok)
- `z_e9d3c5ffcd110500_report_py.html` — Coverage for app/services/enrichment/report.py: 0% (~5043 tok)

## backend/htmlcov_step2/

- `.gitignore` — Git ignore rules (~8 tok)
- `class_index.html` — Coverage report (~5688 tok)
- `coverage_html_cb_6fb7b396.js` — For details: https://github.com/nedbat/coveragepy/blob/master/NOTICE.txt (~7279 tok)
- `function_index.html` — Coverage report (~18886 tok)
- `index.html` — Coverage report (~3552 tok)
- `status.json` (~2294 tok)
- `style_cb_6b508a39.css` — Styles: 117 rules, 51 media queries (~4468 tok)
- `z_257b53c25398f6ee___init___py.html` — Coverage for app/api/v1/**init**.py: 0% (~2452 tok)
- `z_41f09dac0431399d___init___py.html` — Coverage for app/api/v1/endpoints/**init**.py: 0% (~1587 tok)
- `z_41f09dac0431399d_explanation_py.html` — Coverage for app/api/v1/endpoints/explanation.py: 0% (~16186 tok)
- `z_41f09dac0431399d_recognition_py.html` — Coverage for app/api/v1/endpoints/recognition.py: 0% (~18795 tok)
- `z_5f5a17c013354698_main_py.html` — Coverage for app/main.py: 0% (~6092 tok)
- `z_6c0e4b930745278b_ai_service_log_py.html` — Coverage for app/models/ai_service_log.py: 88% (~9585 tok)
- `z_6c0e4b930745278b_recognition_result_py.html` — Coverage for app/models/recognition_result.py: 95% (~6070 tok)
- `z_6c0e4b930745278b_recognition_stats_py.html` — Coverage for app/models/recognition_stats.py: 75% (~8313 tok)
- `z_748a0465d46c2a16___init___py.html` — Coverage for app/utils/**init**.py: 0% (~2106 tok)
- `z_748a0465d46c2a16_database_utils_py.html` — Coverage for app/utils/database_utils.py: 0% (~24585 tok)
- `z_748a0465d46c2a16_performance_monitor_py.html` — Coverage for app/utils/performance_monitor.py: 0% (~16664 tok)
- `z_8f7e1016f2d37417_config_py.html` — Coverage for app/core/config.py: 96% (~8280 tok)
- `z_8f7e1016f2d37417_database_py.html` — Coverage for app/core/database.py: 69% (~6450 tok)
- `z_c0f67d75e686303c_explanation_py.html` — Coverage for app/schemas/explanation.py: 92% (~13611 tok)
- `z_c0f67d75e686303c_recognition_py.html` — Coverage for app/schemas/recognition.py: 61% (~10273 tok)
- `z_c0f67d75e686303c_tts_py.html` — Coverage for app/schemas/tts.py: 0% (~10169 tok)
- `z_c318f3fa19a49f69_ai_service_py.html` — Coverage for app/services/ai_service.py: 12% (~39310 tok)
- `z_c318f3fa19a49f69_cache_service_py.html` — Coverage for app/services/cache_service.py: 10% (~21894 tok)
- `z_c318f3fa19a49f69_explanation_service_py.html` — Coverage for app/services/explanation_service.py: 62% (~35677 tok)
- `z_c318f3fa19a49f69_image_service_py.html` — Coverage for app/services/image_service.py: 32% (~14408 tok)
- `z_c318f3fa19a49f69_recognition_service_py.html` — Coverage for app/services/recognition_service.py: 17% (~19235 tok)
- `z_c318f3fa19a49f69_tts_service_py.html` — Coverage for app/services/tts_service.py: 0% (~23491 tok)
- `z_cfb6adc3f81c8e3c___init___py.html` — Coverage for app/api/**init**.py: 0% (~1547 tok)

## backend/scripts/

- `__init__.py` (~0 tok)
- `build_museum_pack.py` — 构建博物馆馆包（公开数据，Wikidata/Wikimedia Commons） (~1585 tok)
- `migrate_pack_to_db.py` — 把现有 museum_packs/<slug>.json 灌入 DB（幂等，复用 object_importer）。 (~243 tok)
- `onboard.py` — 上馆 CLI：fetch（抓→R2 pack）/ load（pack→DB，staging 样本/prod 全量）。 (~2028 tok)
- `prewarm_explanations.py` — 预热馆包讲解缓存 (~664 tok)
- `seed_sections.py` — 种子：讲解 tab 词表 + 各类别 tab 集合（幂等 upsert，读 category_config 单一真相源）。 (~403 tok)

## backend/scripts/**pycache**/

- `__init__.cpython-311.pyc` (~46 tok)
- `onboard.cpython-311.pyc` (~2980 tok)
- `seed_sections.cpython-311.pyc` (~828 tok)

## backend/tests/

- `conftest.py` — Pytest 全局配置：测试环境关闭速率限制 (~26 tok)
- `test_main.py` — Tests: import_app_module, import_models, import_schemas, app_creation + 9 more (~1512 tok)

## backend/tests/**pycache**/

- `conftest.cpython-311-pytest-8.4.2.pyc` (~131 tok)
- `test_main.cpython-311-pytest-8.4.2.pyc` (~6702 tok)

## backend/tests/e2e/

- `test_recognition_e2e.py` — Tests: user_uploads_image_and_receives_recognition_result, first_time_recognition_calls_ai_service, second_recognition_returns_cached_result, recog... (~3462 tok)

## backend/tests/e2e/**pycache**/

- `test_recognition_e2e.cpython-311-pytest-8.4.2.pyc` (~5090 tok)

## backend/tests/fixtures/

- `generate_test_images.py` — URL configuration (~584 tok)
- `image_helpers.py` — create_test_image, create_gradient_image, create_pattern_image, create_similar_image + 3 more (~2234 tok)

## backend/tests/fixtures/**pycache**/

- `image_helpers.cpython-311.pyc` (~3025 tok)

## backend/tests/fixtures/test_images/

- `corrupted.dat` (~11 tok)

## backend/tests/integration/

- `test_account_deletion.py` — Tests: export_my_data, delete_account_removes_user_and_benefits, delete_requires_auth (~827 tok)
- `test_auth_security.py` — Tests: refresh_token_rotation, refresh_rejects_access_token (~624 tok)
- `test_content_persist.py` — tests/integration/test_content_persist.py (~1911 tok)
- `test_content_report.py` — Tests: quality_report_counts_and_coverage, quality_report_unknown_museum, quality_report_markdown (~926 tok)
- `test_content_status.py` — Tests: content_status_defaults_to_stub, backfill_sets_ready_for_objects_with_published_sections, backfill_idempotent (~634 tok)
- `test_database.py` — Tests: establishes_connection_to_postgresql, connection_pool_configuration, handles_connection_timeout, closes_connections_gracefully + 24 more (~3348 tok)
- `test_generate_pipeline.py` — Tests: generate_object_persists_en_and_translation, generate_object_skips_when_already_published, generate_object_force_regenerates, generate_objec... (~1589 tok)
- `test_museum_repo.py` — tests/integration/test_museum_repo.py (~897 tok)
- `test_museums_endpoint_db.py` — tests/integration/test_museums_endpoint_db.py (~615 tok)
- `test_object_content_endpoint.py` — tests/integration/test_object_content_endpoint.py (~888 tok)
- `test_object_importer.py` — tests/integration/test_object_importer.py (~770 tok)
- `test_onboard_flow.py` — 集成测试：上馆全流程 fetch → load staging --sample → load prod 全量。 (~1067 tok)
- `test_quota_abuse.py` — Tests: guest_login_reuses_account_for_same_device, benefits_and_consume_require_auth, consume_decrements_account_quota (~774 tok)
- `test_recognition_flow.py` — Tests: complete_recognition_flow_without_cache, complete_recognition_flow_with_cache_hit, recognition_flow_stores_result_in_database, recognition_f... (~2921 tok)
- `test_section_audio.py` — Tests: persist_section_audio_uploads_and_writes_key, persist_section_audio_unknown_qid_returns_none, persist_section_audio_upload_failure_writes_no... (~1116 tok)
- `test_suggested_questions.py` — Tests: suggested_question_roundtrip, persist_suggested_questions_replaces_group, persist_suggested_questions_unknown_qid, get_object_content_includ... (~1144 tok)
- `test_tts_endpoint.py` — Tests: section_mode_generates_and_persists, section_mode_reuses_without_tts, section_mode_unknown_qid_returns_404, ad_hoc_mode_streams_audio (~1092 tok)

## backend/tests/integration/**pycache**/

- `test_account_deletion.cpython-311-pytest-8.4.2.pyc` (~4409 tok)
- `test_auth_security.cpython-311-pytest-8.4.2.pyc` (~2076 tok)
- `test_content_persist.cpython-311-pytest-8.4.2.pyc` (~7420 tok)
- `test_content_report.cpython-311-pytest-8.4.2.pyc` (~4165 tok)
- `test_content_status.cpython-311-pytest-8.4.2.pyc` (~2714 tok)
- `test_database.cpython-311-pytest-8.4.2.pyc` (~5198 tok)
- `test_generate_pipeline.cpython-311-pytest-8.4.2.pyc` (~6033 tok)
- `test_museum_repo.cpython-311-pytest-8.4.2.pyc` (~3083 tok)
- `test_museums_endpoint_db.cpython-311-pytest-8.4.2.pyc` (~2229 tok)
- `test_object_content_endpoint.cpython-311-pytest-8.4.2.pyc` (~2871 tok)
- `test_object_importer.cpython-311-pytest-8.4.2.pyc` (~2931 tok)
- `test_onboard_flow.cpython-311-pytest-8.4.2.pyc` (~3413 tok)
- `test_quota_abuse.cpython-311-pytest-8.4.2.pyc` (~3082 tok)
- `test_recognition_flow.cpython-311-pytest-8.4.2.pyc` (~4620 tok)
- `test_section_audio.cpython-311-pytest-8.4.2.pyc` (~5314 tok)
- `test_suggested_questions.cpython-311-pytest-8.4.2.pyc` (~4898 tok)
- `test_tts_endpoint.cpython-311-pytest-8.4.2.pyc` (~3884 tok)

## backend/tests/unit/api/

- `test_recognition_api.py` — Tests: get_recognition_service_dependency, recognize_artwork_success, recognize_artwork_invalid_content_type, recognize_artwork_content_type_valida... (~3934 tok)

## backend/tests/unit/api/**pycache**/

- `test_recognition_api.cpython-311-pytest-8.4.2.pyc` (~9583 tok)

## backend/tests/unit/models/

- `test_museum_object_sources.py` — Tests: museum_object_has_sources_column_default_dict (~143 tok)
- `test_recognition_result.py` — Tests: creates_recognition_result_instance, has_required_fields, has_timestamp_fields, sets_created_at_automatically + 18 more (~2284 tok)
- `test_step1_models.py` — tests/unit/models/test_step1_models.py (~740 tok)

## backend/tests/unit/models/**pycache**/

- `test_museum_object_sources.cpython-311-pytest-8.4.2.pyc` (~1026 tok)
- `test_recognition_result.cpython-311-pytest-8.4.2.pyc` (~3535 tok)
- `test_step1_models.cpython-311-pytest-8.4.2.pyc` (~1626 tok)

## backend/tests/unit/schemas/

- `test_recognition_schema.py` — Tests: accepts_valid_image_field, requires_image_field, validates_image_is_string, validates_image_not_empty + 15 more (~2529 tok)

## backend/tests/unit/schemas/**pycache**/

- `test_recognition_schema.cpython-311-pytest-8.4.2.pyc` (~3455 tok)

## backend/tests/unit/services/

- `test_ai_service.py` — Tests: calls_openai_gpt4v_as_primary_strategy, returns_recognition_result_on_success, encodes_image_to_base64_before_api_call, includes_proper_prom... (~5773 tok)
- `test_cache_service.py` — Tests: generates_cache_key_using_sha256_hash, same_image_produces_same_cache_key, different_images_produce_different_cache_keys, retrieves_cached_r... (~11042 tok)
- `test_content_cache.py` — Unit tests for ContentCache: TTS 磁盘缓存、讲解缓存键、日预算熔断 (~400 tok)
- `test_image_service.py` — Tests: validates_image_size_less_than_10mb, rejects_images_larger_than_10mb, validates_jpeg_image_format, validates_png_image_format + 18 more (~6056 tok)
- `test_recognition_service.py` — Tests: init_stores_dependencies, recognize_artwork_complete_flow_success, recognize_artwork_cache_hit, recognize_artwork_db_hit_cache_miss + 4 more (~11346 tok)
- `test_seed_sections.py` — Tests: seed_creates_multi_category_skeleton, seed_idempotent (~401 tok)
- `test_tts_service.py` — Tests: generate_audio_reads_sync_iter_bytes (~262 tok)

## backend/tests/unit/services/**pycache**/

- `test_ai_service.cpython-311-pytest-8.4.2.pyc` (~13861 tok)
- `test_cache_service.cpython-311-pytest-8.4.2.pyc` (~24529 tok)
- `test_content_cache.cpython-311-pytest-8.4.2.pyc` (~2711 tok)
- `test_image_service.cpython-311-pytest-8.4.2.pyc` (~22560 tok)
- `test_recognition_service.cpython-311-pytest-8.4.2.pyc` (~21877 tok)
- `test_seed_sections.cpython-311-pytest-8.4.2.pyc` (~2063 tok)
- `test_tts_service.cpython-311-pytest-8.4.2.pyc` (~982 tok)

## backend/tests/unit/services/enrichment/

- `__init__.py` (~0 tok)
- `test_catalog_source.py` — Tests: stubrecord_fields_and_defaults, catalogsource_is_abstract (~180 tok)
- `test_catalog.py` — Tests: get_returns_typed_config, unknown_slug_raises, categories_and_country_lang_parsed, categories_defaults_to_category_filter (~505 tok)
- `test_category_config.py` — Tests: known_qids_map, unknown_falls_back, sections_by_category_and_fallback, section_label_localized_with_en_fallback (~358 tok)
- `test_content_enricher.py` — Tests: build_material_includes_facts_and_wikipedia, build_material_empty_when_no_facts, generate_canonical_parses_sections_and_drops_empty, generat... (~540 tok)
- `test_fetcher.py` — View: get, put, put, put (~1275 tok)
- `test_http_client.py` — Tests: user_agent_required, get_sends_user_agent_and_returns, backoff_on_429_then_succeeds, circuit_breaker_raises_after_repeated_failures + 2 more (~813 tok)
- `test_identity.py` — Tests: merge_distinct_passthrough, merge_dedup_by_inventory_normalized, merge_dedup_by_qid, merge_inventory_namespaced_by_museum (~331 tok)
- `test_joconde_source.py` — Tests: probe_requires_p347, enrich_maps_french_fields, enrich_returns_none_without_p347, enrich_returns_none_when_no_records (~481 tok)
- `test_lang_config.py` — Tests: resolve*languages_defaults_when_no_override, resolve_languages_uses_override, default_languages_all_have_names, museum_config_has_languages*... (~279 tok)
- `test_loader_sampling.py` — Tests: sample_takes_top_n_by_popularity, sample_includes_fixed_qids_dedup (~161 tok)
- `test_merge.py` — Tests: single_source_projects_fields_and_raw, precedence_higher_source_wins_per_field, precedence_param_official_beats_wikidata, non_empty_higher_w... (~778 tok)
- `test_onboard_cli.py` — Tests: parser_fetch, cmd_load_aborts_when_target_mismatches_container_env, parser_load_staging_sample, parser_generate_command + 3 more (~570 tok)
- `test_pack_store.py` — View: put, get (~229 tok)
- `test_pipeline.py` — Tests: row_to_obj_maps_columns_and_attributes, row_to_obj_handles_none_attributes, facts_text_lists_present_hard_facts_only, facts_text_skips_missing (~330 tok)
- `test_prompts.py` — Tests: prompt_lists_requested_sections_and_grounding_rules, entailment_prompt_demands_per_sentence_json_verdicts, fact_consistency_prompt_lists_con... (~970 tok)
- `test_qa_suggester.py` — Tests: suggest_en_gates_answers_and_translates_published, suggest_skips_empty_pairs (~612 tok)
- `test_quality.py` — Tests: split_sentences_basic, split_sentences_strips_empty_and_whitespace, check_section_drops_unsupported_sentence, check_section_all_supported_no... (~1133 tok)
- `test_registry.py` — Tests: registry_routes_by_external_id, registry_get_by_name (~258 tok)
- `test_report.py` — Tests: report_counts_coverage_and_distribution, report_renders_markdown (~394 tok)
- `test_source_base.py` — Tests: contribution_holds_source_qid_fields_raw, source_is_abstract, source_enrich_default_returns_none (~214 tok)
- `test_source_cache.py` — View: put, get (~380 tok)
- `test_translator.py` — Tests: translate*section_returns_stripped_text, check_faithfulness_true_no_issues, check_faithfulness_false_with_issues, translate_object_skips_en*... (~665 tok)
- `test_wikidata_catalog.py` — Tests: wikidata_catalog_lists_stubrecords, wikidata_catalog_dedups_and_stops_on_empty_page (~441 tok)
- `test_wikidata_source.py` — Tests: fetch_yields_contributions_with_qid_fields_raw, category_not_derived_from_category_filter, image_optional_and_external_ids_and_category, cap... (~1088 tok)
- `test_wikipedia_source.py` — Tests: enrich_pulls_extracts_for_en_and_country_lang, enrich_none_when_no_titles, enrich_skips_lang_without_extract (~381 tok)

## backend/tests/unit/services/enrichment/**pycache**/

- `__init__.cpython-311.pyc` (~52 tok)
- `test_catalog_source.cpython-311-pytest-8.4.2.pyc` (~1084 tok)
- `test_catalog.cpython-311-pytest-8.4.2.pyc` (~2496 tok)
- `test_category_config.cpython-311-pytest-8.4.2.pyc` (~3086 tok)
- `test_content_enricher.cpython-311-pytest-8.4.2.pyc` (~2116 tok)
- `test_fetcher.cpython-311-pytest-8.4.2.pyc` (~4403 tok)
- `test_http_client.cpython-311-pytest-8.4.2.pyc` (~3218 tok)
- `test_identity.cpython-311-pytest-8.4.2.pyc` (~2168 tok)
- `test_joconde_source.cpython-311-pytest-8.4.2.pyc` (~3264 tok)
- `test_lang_config.cpython-311-pytest-8.4.2.pyc` (~1878 tok)
- `test_loader_sampling.cpython-311-pytest-8.4.2.pyc` (~1507 tok)
- `test_merge.cpython-311-pytest-8.4.2.pyc` (~2864 tok)
- `test_onboard_cli.cpython-311-pytest-8.4.2.pyc` (~4350 tok)
- `test_pack_store.cpython-311-pytest-8.4.2.pyc` (~1870 tok)
- `test_pipeline.cpython-311-pytest-8.4.2.pyc` (~1638 tok)
- `test_prompts.cpython-311-pytest-8.4.2.pyc` (~8450 tok)
- `test_qa_suggester.cpython-311-pytest-8.4.2.pyc` (~2455 tok)
- `test_quality.cpython-311-pytest-8.4.2.pyc` (~5960 tok)
- `test_registry.cpython-311-pytest-8.4.2.pyc` (~1509 tok)
- `test_report.cpython-311-pytest-8.4.2.pyc` (~1456 tok)
- `test_source_base.cpython-311-pytest-8.4.2.pyc` (~2195 tok)
- `test_source_cache.cpython-311-pytest-8.4.2.pyc` (~1838 tok)
- `test_translator.cpython-311-pytest-8.4.2.pyc` (~3167 tok)
- `test_wikidata_catalog.cpython-311-pytest-8.4.2.pyc` (~3272 tok)
- `test_wikidata_source.cpython-311-pytest-8.4.2.pyc` (~4035 tok)
- `test_wikipedia_source.cpython-311-pytest-8.4.2.pyc` (~2446 tok)

## backend/tests/unit/storage/

- `__init__.py` (~0 tok)
- `test_factory.py` — Tests: factory_returns_local_singleton (~132 tok)
- `test_local_storage.py` — Tests: put_get_exists_delete_and_url (~151 tok)
- `test_r2_storage.py` — Tests: r2_roundtrip (~229 tok)

## backend/tests/unit/storage/**pycache**/

- `__init__.cpython-311.pyc` (~49 tok)
- `test_factory.cpython-311-pytest-8.4.2.pyc` (~733 tok)
- `test_local_storage.cpython-311-pytest-8.4.2.pyc` (~1832 tok)
- `test_r2_storage.cpython-311-pytest-8.4.2.pyc` (~1498 tok)

## backend/tests/unit/utils/

- `test_database_utils.py` — Tests: explain_query_with_analyze, explain_query_without_analyze, explain_query_error_handling, explain_query_logs_results + 9 more (~2854 tok)
- `test_performance_monitor.py` — Tests: initialization, default_initialization, tracks_request_duration, records_latency_metric + 24 more (~4840 tok)

## backend/tests/unit/utils/**pycache**/

- `test_database_utils.cpython-311-pytest-8.4.2.pyc` (~8427 tok)
- `test_performance_monitor.cpython-311-pytest-8.4.2.pyc` (~21906 tok)

## backend/tests/unit/workers/

- `test_recognition_worker.py` — Tests: processes_recognition_task_from_queue, calls_ai_service_for_recognition, saves_result_to_database, caches_result_in_redis + 20 more (~2752 tok)

## backend/tests/unit/workers/**pycache**/

- `test_recognition_worker.cpython-311-pytest-8.4.2.pyc` (~4269 tok)
