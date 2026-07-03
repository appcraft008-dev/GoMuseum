# 图像 R2 自存实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 全馆图片自存 R2（thumb 480 / large 1600 两档），端点字段零变化前端零改；多角度图入库；懒补漏自愈。

**Architecture:** 采集层（catalog 收 P18 全部值 → 多行 ObjectImage）与物化层（`images` 命令扫"有 source_url 无 image_key"行 → 下载/Pillow 两档/R2/署名）解耦；`image_key` 存基础键 `images/{qid}/{sort}`，端点按档位拼 `_thumb.jpg`/`_large.jpg`；懒生成触发点顺手补单件缺图。

**Tech Stack:** Pillow（已有依赖）、boto3 R2（已有）、PoliteSession（已有）、Commons imageinfo API。

## Global Constraints

- spec: `docs/superpowers/specs/2026-07-03-image-r2-selfhost-design.md`
- 不存原图；SVG / >60MB 跳过记日志；JPEG q82
- 物化逐行 try/except 幂等（失败留空重跑重试）
- 端点字段名不变（`image`/`thumbnail`/`images[].url`）；无 image_key 回退 source_url 行为不变
- 所有网络/存储依赖注入，测试离线

---

### Task 1: 采集层——P18 全收 + 多行 ObjectImage

**Files:**
- Modify: `backend/app/services/enrichment/catalog_source.py`（StubRecord 加 `image_urls: list`）
- Modify: `backend/app/services/enrichment/sources/wikidata_catalog.py`（缓冲区累积同 qid 的多个 ?image）
- Modify: `backend/app/services/enrichment/catalog_loader.py`（art 加 `"images"`）
- Modify: `backend/app/services/object_importer.py`（多行 upsert：首张 primary，其余 view，sort=序号）
- Test: `backend/tests/unit/services/enrichment/test_wikidata_catalog.py`、`backend/tests/integration/test_onboard_flow.py`（或就近既有文件）

**Interfaces:**
- Produces: `StubRecord.image_urls: list[str]`（含首张）；`upsert_object` 的 `art["images"]: list[str]` → ObjectImage 行（role primary/view, sort 0..n, source_url https 化）

- [ ] 测试1：同 qid 两行不同 ?image → StubRecord.image_urls 含两个、image_url=首个（RED→GREEN）
- [ ] 测试2：upsert_object(art={"images": [u1,u2]}) → 两行 ObjectImage（primary/view, sort 0/1）；重跑幂等不翻倍
- [ ] 实现：wikidata_catalog 缓冲 upgrade 块里 `rec.image_urls.append(新图)`（去重）；loader/importer 透传
- [ ] 全量测试绿 → commit `feat(catalog): P18 全收多角度图(多行 ObjectImage primary/view)`

### Task 2: 物化器 materializer.py

**Files:**
- Create: `backend/app/services/enrichment/materializer.py`
- Test: `backend/tests/integration/test_image_materializer.py`

**Interfaces:**
- Produces:
  - `image_base_key(qid, sort) -> str`（`images/{qid}/{sort}`）
  - `materialize_row(db, row, *, fetch_bytes, storage, fetch_meta=None) -> bool`（成功填 image_key/license/credit）
  - `materialize_images(db, slug, *, limit=None, fetch_bytes=None, storage=None, fetch_meta=None) -> dict`（扫全馆缺 key 行；返回 {"done": n, "failed": m, "skipped": k}）
  - 默认 `fetch_bytes`=PoliteSession GET（UA 合规,1req/s）；默认 `fetch_meta`=Commons imageinfo extmetadata（LicenseShortName/Artist，剥 HTML 标签）
- 内部：Pillow 打开 → RGB → `.thumbnail((480,480))`/`.thumbnail((1600,1600))`（不放大）→ JPEG q82 → `storage.put(f"{base}_thumb.jpg", ...)` ×2

- [ ] 测试1：fake fetch_bytes 返回真实小 JPEG bytes（Pillow 现造 8x8）→ materialize_row 后 storage 收到 `{base}_thumb.jpg`+`{base}_large.jpg` 两个 put、row.image_key=base、license/credit 从 fake fetch_meta 填入
- [ ] 测试2：fetch_bytes 抛异常 → 返回 False、image_key 仍空、不抛出（幂等重试）
- [ ] 测试3：materialize_images 只处理缺 key 的行；重跑 done=0（幂等）
- [ ] 测试4：SVG/超大（fake 返回 >60MB 或 Pillow 打不开）→ skipped 计数、留空
- [ ] 实现 → 全量测试绿 → commit `feat(images): 物化器(下载/两档/R2/署名,幂等)`

### Task 3: 端点档位接线

**Files:**
- Modify: `backend/app/services/museum_repo.py`（`_resolve_image`/`_thumb` → thumb 档；`get_object_content` images[] → large 档）
- Test: `backend/tests/integration/test_list_objects.py`、`test_pack_and_content_facts.py`（就近加断言）

**Interfaces:**
- Consumes: image_key 基础键约定（Task 2 的 `image_base_key`）
- 实现：`def _sized(storage, key, size): return storage.public_url(f"{key}_{size}.jpg")`；三处取图改 `_sized(..., "thumb"| "large")`；key 为空回退 source_url 不变

- [ ] 测试：ObjectImage(image_key="images/Q1/0") → list thumbnail 以 `_thumb.jpg` 结尾、detail images[].url 以 `_large.jpg` 结尾；无 key 行回退 source_url（既有测试保绿）
- [ ] 实现 → 全量绿 → commit `feat(api): 图片按档位出 R2 直链(列表thumb/详情large,字段不变)`

### Task 4: onboard `images` 子命令 + 懒补漏钩子

**Files:**
- Modify: `backend/scripts/onboard.py`（`images --target <env> [--limit N]`，环境守卫同 names）
- Modify: `backend/app/services/enrichment/lazy.py`（maybe_trigger 末尾：该件有缺 key 行 → `schedule(run_lazy_images, qid)`；`run_lazy_images` 调 materialize 单件，无内容锁，幂等）
- Test: `backend/tests/integration/test_lazy_generation.py`（钩子测试）

**Interfaces:**
- Consumes: `materialize_images`/`materialize_row`
- Produces: `run_lazy_images(qid, *, session_factory=None, close=True)`；`materialize_object_images(db, obj, **inj) -> int`（materializer 内补一个单件包装）

- [ ] 测试1：maybe_trigger 对"有缺图行"的对象额外调度 run_lazy_images（与懒生成/懒翻译互不排斥；ready 且语言齐但缺图 → 只调度补图）
- [ ] 测试2：图齐的对象不调度
- [ ] 实现（钩子不占 lazy_lock——图物化与内容生成可并行，撞了最多重复下载一张，ponytail 注释）
- [ ] 全量绿 → commit `feat(images): onboard images 命令 + 懒补漏钩子`

### Task 5: 契约回写 + PR + staging 样本验证

**Files:**
- Modify: `docs/architecture/museum-api-contract.md`（图片字段节改写 + 变更记录）

- [ ] 契约：图片字段节——R2 直链兑现、档位语义（thumbnail/image=thumb, images[].url=large）、role 多角度、"图=目录门面必须预物化 vs 内容=懒生成"成本分界、Commons 挖掘留识别轮、上新馆步骤加 `images`（第 4 步，names 后）
- [ ] 全量测试 + black → PR → staging（自动合并）
- [ ] staging 部署后：`onboard.py orsay images --target staging --limit 30` → 验证：缩略图/大图 URL 200、雕塑多图（catalog 需先重跑收 P18 增量）、credit 有值
- [ ] 汇报；prod 全量跑等用户指示

## Self-Review

- spec 覆盖：两档✓(T2) 署名✓(T2) 解耦✓(T1/T2) 多角度✓(T1) key约定+端点✓(T3) 懒补漏✓(T4) 契约✓(T5) 不存原图✓ SVG/60MB✓(T2)
- 类型一致：image_base_key/materialize_row/materialize_images/run_lazy_images 签名各任务一致
- 无占位符
