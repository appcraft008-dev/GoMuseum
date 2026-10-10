# 文本台账（全视图 + 缺口）

**这张表是干什么的**：记录 prod 上文本内容的覆盖情况，以及各语言还缺哪些。文本内容包括标准导览、深度段、推荐问答和作者简介。
它和音频台账 [`audio-followups.md`](audio-followups.md) 并列：音频台账管"有正文没音频"，这张管"有英文没其他语言"。

**口径**：

- 只算 `status='published'` 且 body 非空的内容。`needs_review` 的不对用户显示，算缺口。
- 以 **en 为轴心**：补语种是从已发布的 en 纯翻译（`onboard.py <slug> translate`）。en 自己没发布的件不在补语种范围，见下文「不算缺口」。
- 共十种语言：en/fr/de/es/it/zh/pl/ja/ko/zh-hant（`lang_config.DEFAULT_LANGUAGES`）。

**数据源**：[`text-inventory.sql`](text-inventory.sql)。第 ① 段出全视图，第 ② 段出缺口明细。文件头写了在 prod 上的跑法。
**刷新**：每次跑完补语种或生成批次，重跑这份 SQL，替换下面两节，并改快照日期。别手改数字，手改的数字没人能倒推。

## 处理触发条件

| 类型 | 攒到多少动手 | 处理方式 |
| --- | --- | --- |
| 忠实度闸缺口（译文 `needs_review`） | 新增 20 条，或某件的 guide 缺 ≥3 种语言 | 先查 en 原文有没有错（下文 Q18663545 就是 en 原文坏了）。原文没问题才重跑 translate，重跑最多两轮 |
| en 本身未发布 | 不主动处理 | 归生成管线（重新生成 en），不归补语种 |

## 记录纪律

- 缺口**不要偷偷补**：手工 UPDATE 不走管线，也不过闸。销账靠重跑管线。
- 改 en 原文会让该件已有的 en 音频作废，并把它的译文降为待审（契约纪律 33/37）。动手前先列影响面问用户。
- 处理完把行**移到「已销账」**并写结论，不要直接删。

---

## 全视图（快照 2026-10-10，prod）

**口径**：各语言的已发布数。导览、问答按件数，深度段按段数，作者简介按作者数（只算有已发布 en 内容的件所关联的作者）。
**粗体**表示比同馆 en 少，是缺口。深度段只标数，差几段不加粗。

### louvre

| 类型 | en | fr | de | es | it | zh | pl | ja | ko | zh-hant |
|---|---|---|---|---|---|---|---|---|---|---|
| 标准导览(件) | 408 | **407** | **407** | **406** | 408 | **407** | 408 | **407** | **407** | **407** |
| 深度段(段) | 1237 | 1235 | 1236 | 1237 | 1237 | 1235 | 1236 | 1236 | 1235 | 1237 |
| 问答(件) | 380 | **377** | **376** | **377** | **376** | **377** | **377** | **377** | **376** | **376** |
| 作者简介(位) | 151 | 151 | 151 | 151 | 151 | 151 | 151 | 151 | 151 | 151 |

### orsay

| 类型 | en | fr | de | es | it | zh | pl | ja | ko | zh-hant |
|---|---|---|---|---|---|---|---|---|---|---|
| 标准导览(件) | 317 | 317 | 317 | **316** | 317 | 317 | 317 | 317 | 317 | **316** |
| 深度段(段) | 999 | 997 | 999 | 997 | 998 | 996 | 999 | 997 | 999 | 998 |
| 问答(件) | 282 | 282 | 282 | 282 | 282 | **279** | 282 | 282 | **281** | **281** |
| 作者简介(位) | 105 | 105 | 105 | 105 | 105 | 105 | 105 | 105 | 105 | 105 |

### orangerie

| 类型 | en | fr | de | es | it | zh | pl | ja | ko | zh-hant |
|---|---|---|---|---|---|---|---|---|---|---|
| 标准导览(件) | 79 | 79 | 79 | 79 | 79 | 79 | 79 | 79 | 79 | **78** |
| 深度段(段) | 158 | 158 | 158 | 158 | 157 | 158 | 158 | 158 | 158 | 158 |
| 问答(件) | 75 | **74** | **74** | 75 | 75 | 75 | **73** | 75 | 75 | **74** |
| 作者简介(位) | 12 | 12 | 12 | 12 | 12 | 12 | 12 | 12 | 12 | 12 |

### petit_palais

| 类型 | en | fr | de | es | it | zh | pl | ja | ko | zh-hant |
|---|---|---|---|---|---|---|---|---|---|---|
| 标准导览(件) | 112 | 112 | 112 | 112 | 112 | 112 | 112 | 112 | 112 | 112 |
| 深度段(段) | 225 | 225 | 225 | 225 | 225 | 225 | 225 | 225 | 225 | 225 |
| 问答(件) | 102 | 102 | **100** | 102 | **101** | **101** | 102 | **101** | 102 | **100** |
| 作者简介(位) | 76 | 76 | 76 | 76 | 76 | 76 | 76 | 76 | 76 | 76 |

### rijksmuseum（隐身演练馆，不对用户开放，不追缺口）

| 类型 | en | fr | de | es | it | zh | pl | ja | ko | zh-hant |
|---|---|---|---|---|---|---|---|---|---|---|
| 标准导览(件) | 5 | 0 | 0 | 0 | 0 | 5 | 0 | 0 | 0 | 0 |
| 深度段(段) | 9 | 0 | 0 | 0 | 0 | 9 | 0 | 0 | 0 | 0 |
| 问答(件) | 5 | 0 | 0 | 0 | 0 | 5 | 0 | 0 | 0 | 0 |
| 作者简介(位) | 2 | 2 | 2 | 2 | 2 | 2 | 2 | 2 | 2 | 2 |

演练只生成了 en/zh，补语种没在这个馆跑过。正式开馆时跑一遍 translate 即可。

---

## A. 缺口：忠实度闸连续未过（巴黎四馆，2026-10-10）

**来由**：2026-10-10 对巴黎四馆跑 translate 补齐九种语言。段缺口 4438 → 32，问答缺口（件 × 语言）1470 → 48，作者简介缺口 538 → 0。
剩下的条目在同一份 en 上重跑了三轮，救回率逐轮下降（段 55 → 40 → 32），已经不是随机波动。
**用户定（2026-10-10）：先不清，记账。**

**已知原因**：`Q18663545`（卢浮宫《三美神》）的 en 导览原文写着 "created this piece in 150"，年份是坏的，所以各语言译文都过不了闸。
要修得先重新生成 en，会让它的 en 音频作废。其余条目还没逐条查原因。

### A1. 讲解段

| 馆 | 件 | 类型 | 段 | 缺的语言 | 现有行状态 |
| --- | --- | --- | --- | --- | --- |
| louvre | `Q11770763` | 段 | significance | fr,pl | needs_review |
| louvre | `Q16928482` | 段 | background | fr | needs_review |
| louvre | `Q18663545` | 段 | guide | de,es,fr,ja,ko,zh,zh-hant | needs_review |
| louvre | `Q19421105` | 段 | facts | ja,ko,zh | needs_review |
| louvre | `Q24283` | 段 | background | ko | needs_review |
| louvre | `Q29855229` | 段 | guide | es | needs_review |
| louvre | `Q405814` | 段 | background | de | needs_review |
| louvre | `Q87483677` | 段 | facts | zh | needs_review |
| orangerie | `joconde-00000089441` | 段 | guide | zh-hant | needs_review |
| orangerie | `joconde-00000089512` | 段 | analysis | it | needs_review |
| orsay | `Q136029544` | 段 | background | ja | needs_review |
| orsay | `Q14900433` | 段 | background | zh | needs_review |
| orsay | `Q14900433` | 段 | guide | zh-hant | needs_review |
| orsay | `Q16696928` | 段 | background | zh | needs_review |
| orsay | `Q17493337` | 段 | facts | fr | needs_review |
| orsay | `Q17493365` | 段 | guide | es | needs_review |
| orsay | `Q17495459` | 段 | analysis | es | needs_review |
| orsay | `Q17495513` | 段 | facts | zh-hant | needs_review |
| orsay | `Q3563746` | 段 | background | ja | needs_review |
| orsay | `Q5287337` | 段 | background | es,fr,it,zh | needs_review |

合计 32 段 / 19 件。

### A2. 问答

| 馆 | 件 | 缺的语言 | 现有行状态 |
| --- | --- | --- | --- |
| louvre | `Q115672867` | de,fr,it | needs_review |
| louvre | `Q19005175` | zh,zh-hant | needs_review |
| louvre | `Q19117698` | ko | needs_review |
| louvre | `Q19308202` | ko | needs_review |
| louvre | `Q21406865` | de,es,fr,it,pl | needs_review |
| louvre | `Q29656195` | zh | needs_review |
| louvre | `Q29863311` | es,it,pl | needs_review |
| louvre | `Q29864681` | de | needs_review |
| louvre | `Q29864760` | ja | needs_review |
| louvre | `Q55873828` | ja,ko,zh,zh-hant | needs_review |
| louvre | `Q87456734` | zh-hant | needs_review |
| orangerie | `joconde-00000089535` | pl | needs_review |
| orangerie | `joconde-00000089551` | fr | needs_review |
| orangerie | `joconde-00000089564` | pl | needs_review |
| orangerie | `Q121160206` | de,zh-hant | needs_review |
| orsay | `Q17494069` | zh | needs_review |
| orsay | `Q3821388` | zh | needs_review |
| orsay | `Q5745603` | ko | needs_review |
| orsay | `Q76450701` | zh,zh-hant | needs_review |
| petit_palais | `Q104445794` | de,zh-hant | needs_review |
| petit_palais | `Q104445860` | ja,zh,zh-hant | needs_review |
| petit_palais | `Q104454170` | de | needs_review |
| petit_palais | `Q106462056` | it | needs_review |

合计 40 组 / 23 件（件 × 语言算一组）。缺口指该语言一条已发布的问答都没有。

### A3. 作者简介

无缺口（2026-10-10 补齐，538 → 0）。

---

## 不算缺口（SQL 第 ② 段会列出，但不归补语种）

| 馆 | 件 | 现象 | 为什么不算 |
| --- | --- | --- | --- |
| louvre | `Q123234813`（陶罐） | en 问答已发布，其他 8 种语言没有问答行 | 它的 en 讲解段全是 `needs_review`，用户看不到这件的讲解；translate 只处理有已发布 en 段的件，按设计跳过。要救它得重新生成 en |

---

## C. 已销账

| 日期 | 范围 | 结论 |
| --- | --- | --- |
| 2026-10-10 | 巴黎四馆补语种 | 段 4406 / 问答 1422 组 / 作者简介 538 条补齐。音频作废 0 条；写前快照 `ops-snapshots/production/20261010T*_translate_<slug>.json.gz`；服务器日志在 `/opt/gomuseum/runs/translate_*.log` |
