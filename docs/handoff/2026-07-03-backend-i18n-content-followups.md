# 交接（后端）：多语内容收尾（老件补语种 + 作者国籍/代表作本地化）

> 前端在真机测 de/es/it（6 语已开放，PR #138–#140）时发现两处**后端侧**多语缺口。
> 均为内容/数据本地化，前端无法修（前端只呈现后端返回的文本）。
> 另有一处分类 label 本地化已单独交接，见文末「相关」。

---

## ① 老藏品补 de/es/it 讲解内容（批量补语种）

**现象**：切到 de/es/it 后，**早期约 243 件老藏品**的详情显示「待完善」——它们只生成过 zh/en/fr 讲解，缺 de/es/it。

**背景**：
- 新藏品走六语生成，无此问题。
- 前端已有懒生成/轮询：点开 `status != ready` 的件会显「生成中·约 1-3 分钟」并轮询（PR #162），**按访问语言懒翻译（~40s）后原地刷新**。所以**单件被访问时会自愈**。
- 但对存量老件逐个等 40s 体验差、且未被访问的件始终缺；需要**主动批量补**。

**要做**：对**已发布**的存量藏品，跑一次 **de/es/it 增量补语种**（批量懒翻译/回填），把 zh/en/fr 已有内容翻成三语落库。此命令在后端 backlog 里被提过（见 `six-languages-frontend.md`），本交接是请求**正式排期执行**。

**验收**：
- `GET /museums/orsay/objects/{qid}/content?language=de`（任取老件，如 `Q3358957` 奥维里）→ `status=ready` 且 tabs/default_guide 有德语正文（非空、非「待完善」）。
- es/it 同。
- 抽样老件三语内容非空覆盖率达标（建议 ≥ 现 zh/en/fr 的覆盖）。

---

## ② 作者卡 `nationality` / `notable_works` 按语言本地化

**现象**：作者卡的**国籍**与**代表作**在非英语界面仍显英文——
- `artist.nationality` = `"France"`（应「法国」/「Francia」/…）
- `artist.notable_works` = `["Olympia", ...]`（应按语言的权威标签，如「奥林匹亚」）

**背景**：`artist.name`（已本地化）和生卒年不受影响；仅 `nationality`/`notable_works` 是 en 标签。此限制在 `artist-card-frontend.md` 标为「留 round2」，本交接请求落实 round2。

**要做**：`GET .../content?language={lang}` 返回的 `artist.nationality` 与 `artist.notable_works` 按 `language` 本地化——与藏品标题 `name_i18n` 同机制（Wikidata 权威标签按语言取，缺则翻译回退）。

**契约约束（遵循项目硬规则）**：
- **加法/前向兼容**：字段已存在，只改**取值**为本地化文本；不新增/删字段、不改结构。老前端照显、只是显对应语言。
- **缺翻译回退英文**（勿返 null；见记忆 `enrichment-data-frontend-contract`）。
- `notable_works` 上游 Wikidata 偶有瑕疵标签（如截断），本地化时若能顺带清洗更好，但非阻塞（v1 前端直显）。

**验收**：
- `GET .../content/{qid}?language=zh` → `artist.nationality` 为中文、`notable_works` 为中文标签。
- fr/de/es/it 同各自语言；缺译回退英文、不返 null。
- 前端零改动即生效（server-driven）。

---

## 相关

- **③ 分类 label 本地化**（Painting/Sculpture…）→ 已单独交接：`docs/handoff/2026-07-03-backend-category-label-i18n.md`
- 契约主文档：`docs/architecture/museum-api-contract.md` §端点4（content：artist / tabs / default_guide）
- 前端 6 语 PR：#138 / #139 / #140；懒生成轮询：#162
