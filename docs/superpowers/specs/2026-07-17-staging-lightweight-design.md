# staging 轻量化设计（机制验证平台,不是 prod 副本）

> 2026-07-17 定稿。问题:staging 已是 prod 近镜像(6569 件),随馆数×语言膨胀,
> 每次机制变更后在 staging 重跑回填(names 走 gpt-4o)的 LLM 费与时间不可持续
> (十万件×10 语 ≈ 百万级强模型调用/次)。目标:staging 永不为数据规模付 LLM 费。

## 原则(回写契约,收录策略⑤升格)

**staging = 机制验证平台**:

- 机制验证用 `--limit` 小样本(护栏强制,手滑跑不了全量);
- 规模数据一律**从 prod 搬运**——内容是 prod 已付费资产,同 VPS 双 postgres 分钟级,
  **共 R2 桶**(`gomuseum-assets`)故 image_key/audio_key 复制即解析,零 LLM 成本;
- **用户表永不跨环境**(隐私红线);
- 日常瘦(金样本 ~300-500 件),发版前/大特性验收按需拉真(full 模式)。

## §1 金样本白名单(瘦基线)

从 prod 按**规则自动选**(可重跑,不手工点名):

- 每分类热度 top-30;
- 强制边界样本:合成 qid 带图 5 件(樱桃)+ 无图文字层 ~30 件、多视角雕塑(有 view 行)、
  多音译作者件(Seurat/Renoir)、无 title_en 裸 stub 2 件、`empty` 状态件;
- 目标 ~300-500 件:覆盖全部代码路径 + APK 真机手感不空。

## §2 同步脚本 `backend/scripts/sync_staging_from_prod.py`

一个工具两档:

```
--mode slim (默认)  dump prod 内容表 → restore 进 staging → 按 §1 规则删余行
--mode full         同流程不裁剪(发版前拉真)
```

- **搬**:museums / museum_objects / object_images / object_embeddings /
  object_content_sections / object_suggested_questions / artists;
- **不搬(红线)**:users、benefits、devices 等一切用户身份表(staging 留测试账号);
  recognition_events(用户行为,staging 自产);
- 破坏性刷新:跑前打印摘要,须 `--yes` 确认;
- 实现:VPS 上 `pg_dump`(prod 容器)→ `psql restore`(staging 容器),FK 完整性靠
  "先全进再删"(不手工理依赖图);
- 全程零 LLM 调用。

## §3 护栏(纪律变代码)

`onboard.py` 带 LLM 的子命令(names/generate/translate)与 rescan 系脚本:

- `--target staging` 默认注入 `limit=50`;全量须显式 `--allow-full`(打印成本警告);
- `--target prod` 行为不变。

## §4 方案取舍记录

- A 整库 dump+裁剪(选定):FK 零心智负担,一工具两档;同机传输量无所谓;
- B 白名单选择性导出(否):FK 依赖图手工维护,每加表改脚本;
- C postgres_fdw 联邦(否):staging 写操作撞只读边界,测试压 prod 库,风险方向反了。

## 验收

1. slim 刷新后 staging ~300-500 件,APK 列表/搜索/详情/懒生成全可用;
2. `onboard names --target staging` 不带 `--allow-full` 最多处理 50 件;
3. full 拉真后与 prod 件数一致;staging users 表刷新前后不变(零泄漏);
4. 同步全程零 LLM 调用(日志可验)。
