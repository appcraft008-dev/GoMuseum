# 通用全量藏品目录主干 + Stub 列表 + 懒生成 — 设计

> **状态**：设计定稿（2026-06-22 brainstorm）。下一步 writing-plans 拆实现计划。
> **关系**：扩展/取代 `2026-06-17-artwork-content-enrichment-mechanism-design.md`（下称「机制 spec」）的抓取主干模型、对象身份、列表契约（见末节「Supersedes」）。
> **姊妹话题**：藏品识别机制（CLIP+GPT 兜底+墙签 OCR）= 独立 brainstorm，本 spec 只在懒生成触发点与其对接。

---

## 1. 背景与问题

机制 spec 把"事实"加工成接地讲解的链路已上 prod（生成→闸→翻译→编排→报告→建议问答）。但**抓取主干是 Wikidata**，只列"知名"对象——奥赛只进库 247 件（绘画）。

真实馆藏远不止：奥赛约 15 万件（含 4.5 万摄影、素描、装饰艺术…），长期展出 ~3,000–6,000 件。**用户体验问题**：列表只有 247 件，用户在馆里拍到/想浏览的大量藏品要么不在列表、要么识别"未收录"，体验差。

**核心洞察**：
- 用户注意力**幂律分布**——只拍展出的名作；库房 14 万件用户见不到。
- **"展出概率低 / 知名度低 / 可接地材料薄" = 同一批长尾**（幸运重合）：用"知名度+有图+有材料"这一**通用信号**即可一并切分，无需"是否在展"的专有数据。
- 边界不该是 15 万，也不该是瞬时 3–6k，而是**"知名度/有图/有材料"的可展可接地池（几千量级）**：比瞬时展出宽（含轮展中间带）、比 15 万窄得多。

## 2. 目标与非目标

**目标**
- 藏品**列表覆盖"大多数值得看且可接地的件"（几千 stub）**，而非仅 247。
- **TOP-N 预生成富讲解**；其余 stub **点开/识别命中时懒生成**补全。
- **零核心改动可复制到任意博物馆**——通用机制，非奥赛专用。

**非目标**
- 不追 15 万全量（库房/底片/无材料长尾不预收）。
- 不为覆盖率脑补（接地第一原则不变；薄材料→诚实薄内容/待完善）。
- 识别机制本身（另案）；本 spec 只定义"识别命中 → 触发懒生成"的接口。
- 实时借展/展出状态追踪（无通用数据源，靠识别+需求自适应兜底）。

## 3. 架构总览：两层分离

```
┌─ 目录层 (Catalog) ──────────────────────────────────┐
│  CatalogSource 注册表 → 列 stub 全集 → 身份去重 merge   │
│  = 几千对象,只有元数据(标题/作者/年代/图/馆藏号/类别)    │
└─────────────────────────────────────────────────────┘
                  │ 每对象一个 content_status
                  ▼
┌─ 内容层 (Content,机制 spec 已建) ───────────────────┐
│  stub → generating → ready / empty                    │
│  TOP-N 预生成富讲解;其余懒生成(点开/识别命中触发)        │
└─────────────────────────────────────────────────────┘
```

三个新机件 + 一处解耦：
1. **`CatalogSource` 注册表**（列对象）。
2. **身份去重 `identity`**（多源同一件归并）。
3. **`content_status` 生命周期**（stub→generating→ready，复用机制 spec 懒生成状态机）。
4. **解耦"列目录"与"抓材料"**（列目录批量廉价；材料逐件按需）。

核心管线（生成/闸/翻译/编排）**不变**。

## 4. CatalogSource 接口 + 连接器

**边界**：CatalogSource = **列对象**（产 stub：身份+基本元数据）。富化源（Wikipedia/Joconde）= **抓材料**（供生成），是另一层，不混。

```python
@dataclass
class StubRecord:
    inventory_number: str | None   # 馆藏号 — 身份主键
    qid: str | None                # Wikidata QID — 身份桥接
    title: str | None
    artist: str | None
    year: str | None
    category: str | None           # 复用 category_config 的 P31/edmType→类别
    image_url: str | None          # 参考图(CLIP + 列表展示)
    popularity: int | None         # 知名度信号(排 TOP-N 预生成)
    owning_museum: str             # 拥有馆(从记录的收藏馆字段解析,见 §5)
    source: str                    # 哪个目录源产的
    raw: dict                      # 原始记录留痕

class CatalogSource(ABC):
    name: str
    def list(self, museum_cfg) -> Iterable[StubRecord]: ...
```

**连接器 1 — `WikidataCatalog`（重构现有主干，行为不变）**
- 把现有 `WikidataSource` 的 SPARQL 主干查询抽成 `WikidataCatalog.list()`，产 StubRecord：标题/作者/年代/qid/图(P18)/馆藏号(P217)/类别(P31)/**热度=sitelink 数**/拥有馆(P195)。
- **行为保持**：同样 247 件出来，只是经新接口成 StubRecord。
- **全球通用基线**：任意馆经 `wikidata_qid`(P195) 可用，永远在线。

**连接器 2 — `EuropeanaCatalog`（新，全欧通用）**
- Europeana Search API：按 `DATA_PROVIDER`（馆名）分页拉 → StubRecord（标题 dcTitle/作者 dcCreator/年代/图 edmPreview/馆藏号 dcIdentifier/类别 edmType→映射/拥有馆=dataProvider）。
- **覆盖**：聚合馆方已发布目录（几千件）= "全量列表"来源。
- 需 **Europeana API key**（免费注册）→ 配置/密钥。
- 通用：任意进 Europeana 的欧洲馆近零代码加馆。

**并行小改（富化源提厚，接金丝雀暴露的 43% needs_review）**——与 CatalogSource 解耦、同期做：
- `WikipediaSource`：抓**全文 extract** 而非 lead 摘要。
- `JocondeSource`：补 `description` / `sujet_represente` / `precisions_sur_l_auteur` 字段。

## 5. 身份去重 merge

**身份键（三级，强键优先）**
1. **(拥有馆, 归一化馆藏号)** — 主键。归一化吸收写法差异（"RF 2772"="RF2772"="rf-2772"）。馆藏号跨馆不唯一 → 永远带拥有馆命名空间。
2. **Wikidata QID** — 桥接。共享 QID = 同件。
3. **模糊(标题+作者+年代)** — 兜底，高阈值，低置信**绝不合并**。

**归并算法**
```
收集所有源 StubRecord
 → 第1遍:按(拥有馆,馆藏号)聚类
 → 第2遍:按 QID 合并聚类（桥接:某条同时有 馆藏号+QID,如 Wikidata P217）
 → 第3遍(保守):剩余孤儿高阈值模糊匹配
 → 每簇 = 一条规范目录条目
```
每条规范条目：字段值按机制 spec **§5b 优先级**（复用 `merge_contributions`：官方/馆方 > Europeana > Wikidata；图取最高清；热度取 max）；**收集全部源 ID**（qid+馆藏号+europeana_id）供后续富化路由 + 留痕。

**拥有馆按收藏馆字段解析、不按位置/吐出源**（借展坑）：每条 StubRecord 的 `owning_museum` 从记录的收藏馆元数据（P195 / dataProvider / Joconde 收藏馆）解析。借入馆若也列出该件，带的仍是拥有者收藏馆字段 + 拥有者馆藏号 → **折叠回同一簇**。⚠️ 不用馆藏号前缀猜归属（法国国家馆 "RF" 前缀共享）。

**头号风险=错并，对策=保守**：只在强键（馆藏号/QID）合并；模糊只高置信；**宁留两条重复，不把两件并成一条**（张冠李戴比重复严重）。

**分工**：新 `identity.py`（对象级聚类）；复用 `merge_contributions`（簇内字段级合并）。

## 6. content_status 生命周期 + 懒生成

**对象级 `content_status`**：`stub`(只元数据) → `generating`(锁) → `ready`(≥1 已发布段) / `empty`(无可接地材料)。列表据此区分；generating 兼作懒生成去重锁。

**🔑 解耦"列目录"与"抓材料"**（全量目录的前提）：
| 步骤 | 范围 | 成本 |
|---|---|---|
| 目录抓取 | CatalogSources 列**全部** stub（元数据+图+身份）→ 去重 → 落库 content_status=stub | 便宜批量 |
| 材料富化 | **逐件、生成时**才抓 Wikipedia/Joconde 材料 | 贵按需 |

**预生成（批量 TOP-N）**：`onboard generate` 跑热度排序 top-N stub：逐件 → 抓材料 → 生成→闸→翻译→落库 → ready。（= 现有管线前加"逐件抓材料"。）

**懒生成（按需长尾，复用机制 spec 状态机）**：点开 stub / 识别命中 → 触发这一件：
- stub →（Redis 去重锁）→ generating → 抓材料 → 生成→闸→翻译→落库 → ready/empty。
- 异步（BackgroundTasks）、幂等、限速。
- **渐进 UX**：元数据+图秒出 → 当前语言文字逐段 → 音频跟后 → 其他语言不阻塞。
- **客户端解耦**：用户离开仍落库（一次触发永久受益）。

**逐件材料富化（新小件）**：给一件（带源 ID:qid/馆藏号）按需抓富化材料，复用现有富化源（Wikipedia 经 wiki_titles、Joconde 经 P347）。Europeana-only 件（无 qid）材料较薄 → 诚实薄内容。

## 7. 通用性（零改动复制）

- 核心管线（目录抓取/merge/逐件材料/生成/闸/翻译/编排）跨馆不变。
- **上新馆 = 纯配置**（连接器已存在时）：`catalog_sources:[wikidata,europeana]` + 富化源 + 类别 + 语言 + country_lang。
- `WikidataCatalog`=全球基线；`EuropeanaCatalog`=任意进 Europeana 的欧洲馆。
- **诚实边界**：上第一个新源的馆（如美国 Met）要**一次性写个 CatalogSource 连接器**；核心零改、纯加插件（同富化源注册表模式）。
- 身份规则（按拥有馆、馆藏号键）通用。

## 8. Schema / 契约 / 测试

**Schema 迁移**
- `MuseumObject` 加 `inventory_number`（可空,index）、`content_status`（默认 stub）。
- **qid 从全局唯一改 partial-unique（where qid not null）**；加唯一约束 `(museum_id, inventory_number)`（where not null）。
- **upsert 改**：按 (馆,馆藏号) **或** qid 匹配既有对象（现仅按 qid）。
- **既有 247 回填**：有段落 → ready，否则 stub；inventory_number 从 attributes 提取。

**契约（加法、前向兼容）**
- 列表端点：每件加 `content_status`。
- `get_object_content`：`status` 字段（机制 spec §15 已有 absent/generating/published/needs_review）驱动 stub→generating→ready；stub 触发懒生成。
- 全加法，老 App 容忍多余字段。

**测试**
- 连接器：mock HTTP → StubRecord（Wikidata SPARQL fixture / Europeana JSON fixture）。
- `identity.py`：馆藏号匹配 / QID 桥接 / 模糊高阈值 / 保守不错并 / 借展按拥有馆键。
- merge：复用 `merge_contributions` 测试。
- 生命周期集成：目录抓取→stub；预生成→ready；懒触发→generating→ready；stub 内容端点返 status。
- 逐件材料富化：mock。

## 9. 分期（本 spec → 多个实现计划）

- **Phase A**：CatalogSource 抽象 + `WikidataCatalog` 重构（**行为不变**,仍 247）+ identity 骨架（单源 no-op dedup）+ `content_status` 列 + 迁移 + 247 回填。
- **Phase B**：真身份去重（馆藏号/QID/模糊 + 拥有馆解析）+ **列目录/抓材料解耦** + 预生成改（逐件抓材料）。
- **Phase C**：`EuropeanaCatalog` 连接器 + 多源并集去重 → 列表涨到几千 stub。
- **Phase D**：懒生成接线（点开触发 stub→generate）。**识别触发依赖另案识别 spec**，需协调。
- **并行小改**：富化提厚（Wikipedia 全文 + Joconde description/sujet/precisions）——独立、随时可上、改 43% 质量。

**依赖**：Phase D 的"识别触发懒生成"依赖识别子系统（独立 brainstorm）。A–C + 点开懒生成可先落；识别触发待识别定稿。

## 10. Supersedes / Extends（对机制 spec 的变更）

| 机制 spec 处 | 本 spec 如何变 |
|---|---|
| §5/§17 抓取主干（Wikidata 单主干） | → **取代**：CatalogSource 注册表 + 列目录/抓材料解耦 |
| 对象身份（qid 唯一） | → **取代**：(拥有馆,馆藏号) 主键 + qid partial-unique |
| §15/附录 列表契约 | → **加法扩展**：列表加 `content_status`；对象可为 stub |
| §11 懒生成状态机 | → **复用并具体化**：stub=新的"absent"（带元数据） |
| §12 识别接入 | → **拆出**：独立识别 brainstorm，本 spec 只定义触发接口 |
| 富化源（Wikipedia lead / Joconde 部分字段） | → **加法提厚**：Wikipedia 全文 + Joconde description/sujet/precisions |

原 spec 受影响处加指针指向本 spec；契约附录列表端点补 `content_status`（纯加法）。
