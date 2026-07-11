# 识别引擎接入设计（DINOv2 前置 + GPT/OCR 兜底 + 全局端点）

> 2026-07-11 定稿。前置 spec：2026-07-11-recognition-embedding-bench-design.md（benchmark PASS，
> DINOv2 ViT-S/14 胜出：非名作桶 Top-1 95.8%、真实照 78.2%、阈值 0.85 库外零误接受、VPS p50≈700ms）。
> 原则沿用 2026-07-03 识别 spec 的 R1-R6，不重述。

## 目标（一轮四件事）

1. **向量引擎前置**：DINOv2 检索为主引擎，现有 GPT+OCR 链降级为兜底；响应契约不变
   （match/candidates/unrecognized 三档），老前端零改动。
2. **全局识别端点**（加法）：`POST /api/v1/recognize`，`museum` 可选；老端点保留。
3. **雕塑多视角参考图**：benchmark 明确的 3D 短板（真实照 ~33%），补图是 ROI 最高的一分。
4. **墙签/兜底匹配馆藏号**：matcher 增加 inventory_number 精确匹配（墙签常印编号，比标题准）。

## 识别漏斗（定稿流程）

```
拍照 → DINOv2 向量检索（对有向量的件；全局索引，museum 给了则只搜该馆）
 ├─ ≥ HIGH(0.85)      → match（直开讲解页）
 ├─ [LOW(0.72), HIGH) → candidates（Top-3 确认卡 = 标注飞轮）
 └─ < LOW / 无向量     → GPT+OCR 自动兜底（同一张照片，用户无感）
       ├─ 候选名/顺拍墙签文字 → matcher（标题+作者+编号）命中 → match/candidates
       └─ 未命中 → unrecognized：①引导拍墙签(mode=label,已有) ②搜索入口(下一轮)
                    ③自动记需求(museum 可空)
```

- 每层都接地：向量命中=真实目录记录；GPT 候选名必须命中目录；墙签=馆方原文；编号=馆方主键。
- GPT 调用量从"每张必调"降为"仅 miss 时调"（bench miss 率 <10%），成本降一个数量级。

## 架构决策

**① 引擎位置与依赖**
- `onnxruntime` 进主依赖（生产镜像 +~100MB，VPS 内存账已核：模型加载 ~400MB，可用 4.6G）。
  torch/transformers **不进**——线上只跑预导出的 ONNX。
- 推理代码复用 bench 的 `embed.py`（preprocess + OnnxEmbedder）迁至
  `app/services/recognition/embedder.py`；bench 脚本改为从 app 导入（单一来源）。

**② 模型文件分发**
- `dinov2_vits14.onnx`（88MB）上传 R2（`models/dinov2_vits14.onnx`）；
  后端**首次使用时**下载到本地缓存路径并 sha256 校验（懒加载 + 进程内单例）；
  下载失败 → 引擎不可用 → 整链自动走 GPT+OCR 兜底（优雅降级，不 500）。

**③ 向量存储（生成一次永久落库）**
- 新表 `object_embeddings`：`id / object_id(FK) / image_id(FK object_images) / model(str) /
  vec(bytea float32) / created_at`，唯一约束 (image_id, model)。
- 内存索引：首次识别时从 DB 拉全量构建矩阵（~2k×384=3MB），进程内缓存；
  简单 TTL(10min) 失效重建（与 matcher 索引同策略，不做精细失效）。
- **嵌入生成钩子**：富化管线图片入库处（onboard/懒补图）同步嵌入该图（VPS CPU 单张 <1s）；
  失败只记日志不阻断补图。一次性 backfill CLI 嵌入存量 1704 图。
- **部署次序无依赖**：表空/模型未下载时引擎自动跳过走兜底——先部署后 backfill 安全。

**④ 全局端点（加法，老端点保留）**
- `POST /api/v1/recognize`：multipart `image`；query `museum`(slug,可选)、`language`、`mode`。
- 响应 = 现有三档形状 + `match/candidates` 条目内**新增 `museum` 字段**（归属馆 slug，
  前端跳详情页用）——加法字段，老解析不破。
- museum 给了 → 只搜该馆（向量索引按 museum 过滤 + 文字匹配该馆目录），**不做全局回退**。
  ⚠️ 实现时裁决（2026-07-11 review）：老 App 不读新 `museum` 字段，跨馆命中会拿他馆 qid 撞
  `/{slug}/objects/{qid}/content` 404 死胡同（前向兼容硬约束）。全局语义只属于 `museum` 未传的
  调用（新前端即此）；将来带馆提示的调用方要"馆内优先+全局回退"时，加显式参数再开。
  没给 → 直接全局（文字兜底也全目录）。
- 老端点 `/museums/{slug}/recognize` 改为内部委托新实现（museum=slug 强制馆内语义不变）。
- 缓存键升 `recog3:{museum|global}:{language}:{sha}`；计费规则不变
  （match/candidates 扣 1、unrecognized/缓存命中不扣、超额 402）。
- `recognition_demands.museum_slug` 允许 NULL（全局未收录也记需求）。

**⑤ 雕塑多视角补图**
- 富化管线新步骤：`category ∈ {sculpture}` 且 ObjectImage 数 <3 的件，经 Wikidata→Commons
  分类拉他人照片（复用 bench `commons_alt_photos` 逻辑迁into管线），取 ≤4 张，
  `role="view"`、存 license/credit（合规照旧）、下载入 R2、**入库即嵌入**（钩子③）。
- CLI 手动触发（`onboard` 子命令或独立脚本），orsay 存量 136 件雕塑先跑；不进定时任务。

**⑥ 阈值 server-driven**
- `RECOG_HIGH`(默认 0.85)、`RECOG_LOW`(默认 0.72) 环境变量；真实数据校准后改配置即生效，
  不发版。GPT 兜底链沿用 matcher 现有 HIGH/LOW 不变。

**⑦ matcher 加编号匹配**
- 索引加 `inventory_number`；探针（GPT 候选名+墙签行）先做编号精确匹配
  （归一化：去空格/大小写；命中=1.0 满分），再走现有标题模糊匹配。

**⑧ 前端（小改动，同轮）**
- `camera_page.dart` 去掉硬编码 `_slug='orsay'` → 调新全局端点（不传 museum）；
  跳转讲解页用响应里的归属 `museum` 字段。识别按钮前无需选馆（导航逻辑修正）。
- 三档 UI/拍签模式不变。

## 测试

- 单测：编排三档分流（向量 HIGH/LOW/miss→兜底）、无向量件直通兜底、引擎不可用降级、
  编号精确匹配（含归一化）、全局 vs 馆内过滤与回退、demands 可空馆、缓存键、老端点委托等价。
- 嵌入/索引：假 embedder 注入（同 bench 测试模式），不在 CI 跑真模型。
- staging 端到端：真照片（bench testset 里抽真实游客照）打 staging → 三档各验一例；
  backfill 后向量数=图数；雕塑补图跑 136 件抽查 license。

## 不做（YAGNI）

- FAISS/pgvector（2k 量级 numpy 足够）；足迹落库；需求聚合面板；搜索功能（下一轮，含编号手输）；
  DINOv3/更大模型/精排（等真实失败案例）；多语言 CLIP 文搜图；GPU。

## 契约回写

- 完成后主契约补：新端点 API 面（`POST /api/v1/recognize` + `museum` 字段语义）、
  "识别每层必须接地"通用原则已存在不重复；实现细节不进契约。
