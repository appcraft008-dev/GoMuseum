# 交接（后端）：多语内容三件（分类 label / 老件补语种 / 作者国籍·代表作）

> 前端真机测 de/es/it（6 语已开放，PR #138–#140）发现的**后端侧**多语缺口，汇总为本单一文档。
> 三项均为内容/数据本地化，**前端无法修**（前端只呈现后端返回的文本）。均**加法兼容、缺译回退英文、不返 null**（见记忆 `enrichment-data-frontend-contract`）。

## 状态（2026-07-04）

| 项 | 状态 |
|---|---|
| ① 分类 label 本地化 | ✅ **已修**——前端 curl staging 验证通过（it/de/zh 分类名已本地化，含「全部」） |
| ② 老件补 de/es/it 讲解 | ✅ **取消**——前提消失，后端无需做 |
| ③ 作者国籍/代表作本地化 | 🔄 **后端补数据中**（预计 1-2 小时，staging 补完后前端 curl 复验） |

---

## ① 馆藏分类 label 按 language 本地化 — ✅ 已修

**现象**：藏品列表顶部分类栏在非中文界面显中英混杂——`全部`（硬编码中文）、`Painting`/`Sculpture`/`Works on paper`（英文），不随语言切换。而藏品**标题**已本地化，说明通路是通的，只这一处漏了。

**契约现状**：
- 端点 `GET /api/v1/museums/{slug}?language={lang}` 返回 `categories: [{ code, label, count }]`。
- 端点**已收 `language` 参数**（前端 6 语都传），但 `category.label` **不随语言变**：`code=all`→`"全部"`（写死中文）、其余→英文。
- 前端用 `code` 筛选（`?category=painting`，稳定不译）、`label` 显示（应本地化）。

**要做**：让 `category.label` 按请求 `language` 返本地化文本，`code` 不变。分类是**有限固定集**（十来个），只需一张 `code × language → label` 翻译表，一次配齐 6 语，无需 AI。

示例（`language=it`）：
```json
{ "categories": [
  { "code": "painting", "label": "Dipinti", "count": 245 },
  { "code": "sculpture", "label": "Sculture", "count": 11 },
  { "code": "works_on_paper", "label": "Opere su carta", "count": 5 } ] }
```

**注**：`all` 类目可不管——前端已用 `l10n.all` 覆盖 `code=all` 的 label（PR #139）。后端专注真实分类即可。

**验收**：`GET /museums/orsay?language=it` → `categories[].label` 为意语；de/fr/es 同；`code` 不变；缺译回退英文。前端零改动即生效。

前端模型（只读 `label` 显示）：`MuseumCategory { code; label; count }`（`museum_detail_model.dart`）。

---

## ② 老藏品补 de/es/it 讲解内容（批量补语种）— ✅ 取消（前提消失）

**现象**：切到 de/es/it 后，**早期约 243 件老藏品**详情显「待完善」——只生成过 zh/en/fr，缺 de/es/it。

**背景**：
- 新藏品走六语生成，无此问题。
- 前端已有懒生成/轮询：点开 `status != ready` 的件会显「生成中·约 1-3 分钟」并轮询（PR #162），按访问语言懒翻译（~40s）后原地刷新 → **单件被访问时会自愈**。
- 但逐个等 40s 体验差、未被访问的件始终缺；需**主动批量补**。

**要做**：对**已发布**存量藏品跑一次 **de/es/it 增量补语种**（批量懒翻译/回填），把 zh/en/fr 已有内容翻成三语落库。此命令在 backlog 里被提过（原 `six-languages-frontend.md`），本项请求**正式排期执行**。

**验收**：`GET /museums/orsay/objects/{qid}/content?language=de`（任取老件，如 `Q3358957` 奥维里）→ `status=ready` 且 tabs/default_guide 有德语正文（非空、非「待完善」）；es/it 同；抽样老件三语非空覆盖率达标。

---

## ③ 作者卡 `nationality` / `notable_works` 按语言本地化 — 🔄 后端补数据中

**现象**：作者卡的**国籍**与**代表作**在非英语界面仍显英文——`artist.nationality`=`"France"`（应「法国」/…）、`artist.notable_works`=`["Olympia", ...]`（应按语言权威标签，如「奥林匹亚」）。`artist.name`（已本地化）与生卒年不受影响。

**背景**：此限制原在 `artist-card-frontend.md` 标为「留 round2」，本项请求落实。

**要做**：`GET .../content?language={lang}` 返回的 `artist.nationality` 与 `artist.notable_works` 按 `language` 本地化——与标题 `name_i18n` 同机制（Wikidata 权威标签按语言取，缺则翻译回退）。`notable_works` 上游偶有瑕疵标签（截断等），能顺带清洗更好，非阻塞。

**验收**：`GET .../content/{qid}?language=zh` → `artist.nationality` 中文、`notable_works` 中文标签；fr/de/es/it 各自语言；缺译回退英文、不返 null；前端零改动即生效。

---

## 契约与相关

- 三项均**加法**：字段已存在，只改**取值**为本地化；不新增/删字段、不改结构；对老前端无破坏。
- 契约主文档：`docs/architecture/museum-api-contract.md` §端点4（content：artist/tabs/default_guide）、§categories。
- 相关前端 PR：#138/#139/#140（6 语）、#162（懒生成轮询）、#169（识别）。
