# 藏品识别机制设计（P1：GPT+OCR 接地闭环）

> 2026-07-03 brainstorm 定稿。拍照→识别→讲解闭环；替代老的裸 GPT 识别流（其把模型猜测当事实展示，违反接地第一原则）。
> 原则(R1-R6)随本 spec 回写主契约；实现完成后契约补机制细节。

## 原则（通用，任何馆零代码）

- **R1 识别接地第一原则**：AI 视觉输出是**查询不是答案**——候选名必须匹配到真实目录记录才展示身份；不中就诚实"未收录"，绝不把模型猜测当事实。
- **R2 墙签 OCR = 权威接地源，但是增强不是依赖**：照片常无签是常态；主路靠画面内容；"引导补拍说明牌"是未收录 UX 的组成部分（专用拍签模式：按钮+示意+取景提示，`mode=label` 纯转写）。
- **R3 三档呈现**：高置信直开讲解页 / 中置信确认卡(1-3 候选带缩略图) / 低置信未收录+引导拍签。**确认卡=免费人工标注**（真实照片→确认QID，数据飞轮）。
- **R4 引擎可替换，匹配/接地层是不变核心**：演进顺序由数据依赖决定——GPT 闭环先行生产标注数据，才能校准 CLIP（P2 以 ONNX CLIP 插到引擎位，接口不变）。
- **R5 需求自适应**：未收录拍摄聚合成需求信号 → 目录跟真实需求生长，不预测轮换。
- **R6 足迹 vs 归属两轴分离**：用户到访足迹用物理位置（GPS/App 选馆），绝不用识别到藏品的拥有馆（借展场景两轴背离）。v1 单馆暂不落地足迹，原则先立。

## 端点（加法；老 `/api/v1/recognition` 标记 deprecated 留给老 App）

`POST /api/v1/museums/{slug}/recognize`
- 入参：multipart `image`；query `language`（默认 zh）、`mode=artwork|label`（默认 artwork）
- 识别范围 = 该馆目录（museum-scoped）
- 响应（`outcome/reason` 是机器码，文案前端本地化；`title/artist` 按 language 走显示名规则）：

```json
{ "outcome": "match | candidates | unrecognized",
  "match": {"qid": "...", "title": "...", "artist": "...", "thumbnail": "...", "confidence": 0.93},
  "candidates": [{"qid": "...", "title": "...", "artist": "...", "thumbnail": "...", "score": 0.71}],
  "label_text": "OCR到的墙签文字或null",
  "reason": "not_in_catalog | low_confidence | no_candidates | null" }
```
- match 时 `candidates=[]`；candidates 时 `match=null`（1-3 个）；unrecognized 时两者皆空 + reason。
- 命中后前端跳详情页 → 既有懒生成/懒翻译/懒补图钩子自动接管。

## 组件

**① 识别器（vision.py）**：一次 GPT-4o-mini 视觉调用，STRICT JSON：
`{"candidates": [{"title": "...", "artist": "..."}], "label_text": "...", "self_confidence": "high|medium|low"}`
- `mode=label`：换纯转写 prompt（只抄写可见文字，不猜测）。
- complete 注入，离线可测。self_confidence 只作排序参考，绝不单独决定展示。

**② 匹配层（matcher.py，不变核心）**：候选名+墙签文字 → 该馆目录多语模糊匹配：
- 归一化：小写、去音符（unicodedata NFD 剥离）、去标点。
- 比对面：`title_i18n` 全语种 + `title_en/zh` 列 + 作者 `name_i18n/name_en`（作者一致加分）。
- 墙签文字按行拆开逐行试（墙签格式=标题/作者/年代各一行）。
- 实现：stdlib difflib.SequenceMatcher（~1900 件毫秒级，不引新依赖）；馆目录名字索引进程内缓存（TTL 或按目录版本失效——v1 简单 TTL 10min）。
- 产出 `[(qid, score)]` → 三档阈值分流（常量 HIGH/LOW，真实数据校准；初值 HIGH=0.85, LOW=0.5）。

**③ 需求记录（recognition_demands 表）**：
`id / museum_slug / phash / label_text / gpt_candidates(jsonb) / language / hit_count / created_at / updated_at`
- unrecognized 即记；同 (museum_slug, phash) 幂等计数 +1。聚合运营面 = P2。

**④ 成本护栏**：复用现有 cache_service 文件哈希+感知哈希缓存（新命名空间 v2，缓存新响应形状）——同图/近似图重复识别零成本零延迟。GPT 调用带超时。配额沿用现有鉴权，不新建。

## 分期

- **P1（本轮）**：①-④ + 端点 + 前端交接（相机流程三档 UI + 引导拍签模式）。
- **P2**：CLIP（ONNX ViT-B/32，~350MB 磁盘共享/300-400MB 内存懒加载/查询 50-150ms）前置引擎 + 需求聚合视图 + 足迹记录。资源账已核（VPS 11G 可用 4.6G，够）。

## 测试

- 识别器/匹配层注入离线 TDD：多语查询命中（zh 查询名中 fr 目录件）、墙签多行解析、音符归一化（Théodore≈Theodore）、三档分流、需求记录幂等计数、label 模式纯转写。
- staging 端到端：真实名画照片打真 GPT → match 直开；伪造冷门查询 → unrecognized+记需求。
- 阈值校准依赖真实用户照片（上线后收集）。

## 不做（YAGNI）

- 向量库/pgvector（2k 量级暴力就够，P2 CLIP 也一样）；跨馆全局识别（单馆 scope 参数天然可扩）；需求聚合面板（P2）；足迹落库（P2）。
