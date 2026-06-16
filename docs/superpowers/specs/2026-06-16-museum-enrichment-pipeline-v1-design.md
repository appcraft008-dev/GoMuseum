# 博物馆富化管线 v1 设计（规模化上馆）

> 状态：草案 v1（2026-06-16）｜作者：hongyang + Claude
> 关联：[../../architecture/data-and-content-architecture.md](../../architecture/data-and-content-architecture.md)

**目标：** 把"加一个新博物馆"变成可靠、可审、可复现、可规模化的流程——抓取（多源可扩、v1 单 Wikidata）→ 落版本化 pack artifact（R2）→ staging 装样本验证 → prod 装全量。**不含**叙事内容生成（GPT）与懒 TTS（那是 v2/B）。

**架构一句话：** 三阶段（FETCH → LOAD →〔GENERATE 留待 v2〕）、源可插拔、环境感知（staging 样本 / prod 全量、各取自同一 artifact）。

---

## 1. 核心原则（继承自数据架构文档）

- **环境隔离的是代码 + schema，不是数据**：staging 只装**样本**、prod 装**全量**，不互拷全量。
- **每个数据有 provenance + 可重现性**：
  - facts（Wikidata/未来官方 API）：可重抓 → 重跑管线即可，不需备份。
  - GPT 叙事 / 人工精修：**precious**（花钱/不可再生）→ 必须保留备份。**本期不产生此类数据**，但 schema/管线为其留位（不碰已有 section 内容）。
- **多源「为演进而生」**：schema 与管线**设计支持多源**（Source 连接器接口 + 合并优先级 + per-源 provenance），**v1 只实现 Wikidata 一个连接器**；加源/加 GPT 皆 additive。

---

## 2. 数据流

```
museums.yaml(馆配置)
      │
      ▼
┌─ FETCH ──────────────────────────────────────────────┐
│ 跑该馆所有 Source 连接器(v1: WikidataSource)         │
│ → 每个 object 收集各源贡献 → 按字段优先级合并         │
│ → 产出 pack(含 canonical 投影 + 各源 raw)            │
│ → 写 R2: museum-packs/<slug>/<timestamp>.json(版本化)│
└──────────────────────────────────────────────────────┘
      │ pack key
      ▼
┌─ LOAD ────────────────────────────────────────────────┐
│ 读 pack → 幂等 upsert(by qid)→ canonical 入列 +      │
│ 各源 raw 入 museum_object.sources(JSONB)              │
│   • staging: --sample(popularity top-N + 固定QID)    │
│        → 出抽样报告 →（人工审核闸 = 金丝雀）          │
│   • prod:   全量(审过后,load 同一 pack)              │
└───────────────────────────────────────────────────────┘
      │
      ▼
  〔GENERATE 叙事 section + 懒 TTS = v2/B,本期不做〕
```

- **抓一次、load 多处**：同一 pack artifact 既给 staging 样本、又给 prod 全量 → **prod 装的就是 staging 审过的同一份数据（强一致）**。
- 管线**在后端容器内执行**（有 DB + R2 凭证，server-driven），不走 CI runner。

---

## 3. Schema 改动（全 additive，一条 alembic 迁移）

`museum_object` 新增一列：

- **`sources` JSONB**（默认 `{}`）：各源原始包 + 元数据，形如
  ```json
  {
    "wikidata": {
      "raw": { /* 该 object 的完整 Wikidata 投影/实体片段 */ },
      "fetched_at": "2026-06-16T08:00:00Z"
    }
  }
  ```
  职责：① 原始包留存（"抓一次投影多次"：以后加字段从此回填，不重抓）② per-object 来源审计 ③ 多源时每源各占一个 key。

- 既有 `attributes`（JSONB）**保留**，职责改为「canonical 的补充结构化属性」（material/location/dimensions 等投影出来的结构化字段），与 `sources`（原始包）职责分清。
- `category` / `qid` / `inventory_number` / title/artist/year/period 等**不动**；`category` 继续作 type 字段（painting/sculpture/...）。
- **无破坏性变更**，对已发布 App 向后兼容（只加列，API 响应可选择性暴露）。

> 馆配置（qid/查询/样本规格）放**配置文件 `museums.yaml`**，不入库（v1 不做 admin 表）。

---

## 4. 组件（各自单一职责、可独立测试）

| 组件 | 职责 | 接口 | 依赖 |
| --- | --- | --- | --- |
| `Source`（抽象） | 抓某馆数据、产出每 object 的字段贡献 + raw | `fetch(museum_cfg) -> Iterable[ObjectContribution]` | 各源外部 API |
| `WikidataSource` | v1 唯一实现：SPARQL 抓取 + 分页 + 限速 | 同上 | Wikidata SPARQL |
| `MuseumCatalog` | 读 `museums.yaml`，提供馆配置 | `get(slug) -> MuseumConfig` | 配置文件 |
| `Merger` | 多源贡献按字段优先级合并成 canonical | `merge(contribs, precedence) -> CanonicalObject` | — |
| `Fetcher` | 编排各源 + 合并 → 组 pack → 写 R2 | `fetch(slug) -> pack_key` | Source、Merger、PackStore |
| `PackStore`（R2） | 版本化 pack 的 put/get | `put(slug, pack)->key` / `get(key)->pack` | R2(已有 storage 抽象) |
| `Loader` | 读 pack → 幂等 upsert → raw 入 `sources` | `load(pack, target, sample?)` | DB、object_importer |
| `SampleReporter` | 算覆盖率/分布/异常报告 | `report(slug, loaded) -> Report` | DB |
| `onboard` CLI | 编排上面，三子命令 | `onboard <slug> fetch\|load` | 全部 |

- `ObjectContribution`：`{ source, qid, fields: {...}, raw: {...} }`。
- `MuseumConfig`：`{ slug, name_*, qid, category_filter, fetch_limit, sample_size, sample_qids: [...] }`。

> 复用现有 `object_importer.upsert_museum/upsert_object`（已幂等 by qid），Loader 在其上加「raw 入 `sources`」与 sample/full 控制。`build_museum_pack.py` 的 SPARQL 逻辑迁入 `WikidataSource`。

---

## 5. 合并 / 优先级

- 字段级优先级，配置默认 `manual > official > wikidata`。
- canonical 每个字段取「优先级最高且有值」的源；多源同字段冲突时**记日志**（不静默）。
- v1 只有 wikidata，合并平凡；机制先建好，加源即生效。

---

## 6. pack artifact（R2）

- key：`museum-packs/<slug>/<ISO8601-timestamp>.json`（版本化，不覆盖历史）。
- 内容：`{ museum: {...}, objects: [ { canonical..., sources: {wikidata:{raw,fetched_at}} } ], fetched_at, source_versions }`。
- 大馆 JSON 可较大 → R2 对象存储天然 scale；load 流式/分批读。
- artifact 是**单份抓取产物**（非第二份 DB）；与 DB `sources` 分属 fetch 中间态 vs 入库后状态。

---

## 7. 上馆流程 + CLI（在后端容器内）

```bash
# ① 抓取 → 落 R2 pack,打印 key
onboard <slug> fetch
# → museum-packs/orsay/2026-06-16T08-00-00Z.json

# ② staging 装样本 + 出报告(金丝雀闸)
onboard <slug> load --target staging --pack <key> --sample
# → 打印抽样报告;人工审

# ③ 审过 → prod 装全量(同一 pack)
onboard <slug> load --target prod --pack <key>
```

- `--target` 决定连哪个 DB（各环境各自的 DB URL/凭证）。
- 不传 `--pack` 时默认取该 slug 最新 artifact。
- **金丝雀** = ②③ 之间的人工审核（审抽样报告 + 在 staging App 上看渲染/识别/讲解链路），无人工放行不进 prod。

---

## 8. 样本选取 + 抽样报告

**样本（staging）**

- 默认：该馆 `popularity` top-N（`sample_size`，如 30）。
- 附加：`museums.yaml` 的 `sample_qids` 固定 QID（刻意纳入边界 case：缺字段的/雕塑/冷门多语言），与 top-N 合并去重。

**报告（markdown，打印 + 存档）**

- 计数：object 总数、样本数。
- 覆盖率：含图 / 作者 / 年代 / 中文标签 / 英文标签 各占比。
- 分布：`category` 分布。
- 异常：重复 qid、缺主图、缺中英标签的清单（前若干条）。
- 用途：人工一眼判断"这个馆的数据形状对不对、能不能上 prod"。

---

## 9. 规模化（大馆 / 限流）

- WikidataSource 分页：SPARQL `LIMIT/OFFSET` 或按属性分块，应对 10 万+ 馆藏；当前写死 `LIMIT 60` → 改 `fetch_limit` 可配 + 自动翻页。
- 限速：请求间 sleep + 重试退避，遵守 Wikidata 礼貌策略（User-Agent 已有）。
- LOAD 分批 commit（避免单事务过大）。

---

## 10. 幂等 / 可重跑

- upsert by `qid`（现有逻辑，匹配 qid → (museum, inventory_number)）。
- 重 FETCH → 产出**新 pack 版本**（不覆盖旧 artifact）。
- 重 LOAD → 只更新变化/新增 object；`sources` 按源更新；**绝不触碰已有 `object_content_sections`（叙事/人工内容）**——load 只管 facts + raw。
- `category` 只在 pack 显式提供时覆盖（避免把已标的 sculpture 改回默认 painting）。

---

## 11. 测试

- **单元**：
  - `WikidataSource.fetch`（mock SPARQL 响应 → 贡献 + raw）。
  - `Merger.merge`（多源、优先级、冲突日志）。
  - `Loader` 幂等（同 pack load 两次结果一致；不碰 sections）。
  - 样本选取（top-N + 固定 QID 去重）。
  - `SampleReporter`（给定库内对象算出正确覆盖率/异常）。
  - `MuseumCatalog`（解析 yaml）。
- **集成**：tiny fixture 馆（mock Wikidata）走完 `fetch → staging --sample → 报告 → prod 全量`，断言 DB 状态 + 报告内容。**CI 不打真 Wikidata**（fixture 响应）。
- 复用现有 `backend/tests` 结构与 fixtures。

---

## 12. 不在本期（v2 / B）

叙事 section 生成（GPT）、懒 TTS + R2 音频缓存、其他 Source 连接器（官方 API/Wikipedia）、人工精修后台、多语言叙事生成、admin UI。

---

## 13. 验收标准

- `onboard orsay fetch` 在容器内跑通，R2 出现版本化 pack。
- `onboard orsay load --target staging --sample` 在 staging 装入样本 + 打印可读抽样报告；staging DB 只含样本。
- `onboard orsay load --target prod` 用同一 pack 装入全量；prod `/api/v1/museums/orsay` 返回全量馆藏；staging 仍只样本。
- 重跑 load 幂等（无重复行、不动 sections）。
- 全部单元 + 集成测试通过；CI 不依赖真 Wikidata。
- schema 迁移 additive、`alembic upgrade head` 单 head 通过。
