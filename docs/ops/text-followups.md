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

## 全视图（快照 2026-10-15，prod）

**口径**：各语言的已发布数。导览、问答按件数，深度段按段数，作者简介按作者数（只算有已发布 en 内容的件所关联的作者）。
**粗体**表示比同馆 en 少，是缺口。深度段只标数，差几段不加粗。

### louvre

| 类型 | en | fr | de | es | it | zh | pl | ja | ko | zh-hant |
|---|---|---|---|---|---|---|---|---|---|---|
| 标准导览(件) | 461 | 461 | 461 | **460** | 461 | 461 | 461 | **459** | 461 | 461 |
| 深度段(段) | 1333 | 1331 | 1332 | 1333 | 1333 | 1331 | 1333 | 1330 | 1329 | 1333 |
| 问答(件) | 419 | **417** | **415** | **416** | **416** | **414** | **416** | **416** | **415** | **414** |
| 作者简介(位) | 168 | 168 | 168 | 168 | 168 | 168 | 168 | 168 | 168 | 168 |

### orsay

| 类型 | en | fr | de | es | it | zh | pl | ja | ko | zh-hant |
|---|---|---|---|---|---|---|---|---|---|---|
| 标准导览(件) | 353 | 353 | 353 | **351** | 353 | 353 | 353 | **352** | 353 | 353 |
| 深度段(段) | 1081 | 1078 | 1081 | 1078 | 1080 | 1078 | 1081 | 1078 | 1080 | 1081 |
| 问答(件) | 313 | 313 | 313 | 313 | **312** | **311** | **312** | 313 | **312** | **312** |
| 作者简介(位) | 113 | 113 | 113 | 113 | 113 | 113 | 113 | 113 | 113 | 113 |

### orangerie

| 类型 | en | fr | de | es | it | zh | pl | ja | ko | zh-hant |
|---|---|---|---|---|---|---|---|---|---|---|
| 标准导览(件) | 90 | 90 | 90 | 90 | 90 | 90 | 90 | 90 | 90 | 90 |
| 深度段(段) | 182 | 182 | 182 | 182 | 181 | 183 | 182 | 182 | 182 | 179 |
| 问答(件) | 86 | **85** | **85** | 86 | 86 | 86 | 86 | 86 | 86 | **85** |
| 作者简介(位) | 12 | 12 | 12 | 12 | 12 | 12 | 12 | 12 | 12 | 12 |

### petit_palais

| 类型 | en | fr | de | es | it | zh | pl | ja | ko | zh-hant |
|---|---|---|---|---|---|---|---|---|---|---|
| 标准导览(件) | 130 | 130 | 130 | 130 | **129** | 130 | 130 | 130 | 130 | 130 |
| 深度段(段) | 262 | 262 | 262 | 262 | 262 | 261 | 262 | 262 | 262 | 261 |
| 问答(件) | 120 | 120 | **118** | 120 | **119** | **118** | 120 | **118** | 120 | **118** |
| 作者简介(位) | 86 | 86 | 86 | 86 | 86 | 86 | 86 | 86 | 86 | 86 |

### rijksmuseum（隐身演练馆，不对用户开放，不追缺口）

| 类型 | en | fr | de | es | it | zh | pl | ja | ko | zh-hant |
|---|---|---|---|---|---|---|---|---|---|---|
| 标准导览(件) | 5 | 0 | 0 | 0 | 0 | 5 | 0 | 0 | 0 | 0 |
| 深度段(段) | 9 | 0 | 0 | 0 | 0 | 9 | 0 | 0 | 0 | 0 |
| 问答(件) | 5 | 0 | 0 | 0 | 0 | 5 | 0 | 0 | 0 | 0 |
| 作者简介(位) | 2 | 2 | 2 | 2 | 2 | 2 | 2 | 2 | 2 | 2 |

演练只生成了 en/zh，补语种没在这个馆跑过。正式开馆时跑一遍 translate 即可。

---

## A. 缺口：忠实度闸未过（巴黎四馆，2026-10-15）

**来由**：10-10 补齐后,懒生成只出 en+zh(偶有 fr),4 天里又积了 113 件新作品(109 件是运营账号识别触发)。10-14/15 对四馆再跑 translate:段缺口 2793 → 39,问答 828 → 50,作者简介 230 → 0。剩下的全是译文写了但没过忠实度闸(`needs_review`),没有整行缺失。
**用户定（2026-10-10）：这类先不清，记账。** 懒生成后其余语言长期空着的根治方案在 backlog「等你拍板」。

**已知原因**：`Q18663545`（卢浮宫《三美神》）10-14 随作者修正整件重生成，7 组已全部发布，已出缺口表。其余条目还没逐条查原因；backlog 里「主讲解译文两次没过忠实度闸」一条在跟 guide 段。

### A1. 讲解段

| 馆 | 件 | 段 | 缺的语言 | 现有行状态 |
| --- | --- | --- | --- | --- |
| louvre | `Q115672481` | guide | ja | needs_review |
| louvre | `Q11770763` | significance | fr | needs_review |
| louvre | `Q15280947` | guide | ja | needs_review |
| louvre | `Q16928482` | background | fr | needs_review |
| louvre | `Q19005132` | background | ko | needs_review |
| louvre | `Q19421105` | facts | ja,ko,zh | needs_review |
| louvre | `Q24283` | background | ko | needs_review |
| louvre | `Q29649084` | analysis | ja | needs_review |
| louvre | `Q29649084` | facts | ja | needs_review |
| louvre | `Q29855229` | guide | es | needs_review |
| louvre | `Q29862653` | facts | ko | needs_review |
| louvre | `Q405814` | background | de | needs_review |
| louvre | `Q87483677` | facts | zh | needs_review |
| orangerie | `joconde-00000089476` | facts | zh-hant | needs_review |
| orangerie | `joconde-00000089512` | analysis | it | needs_review |
| orangerie | `joconde-00000089566` | analysis | zh-hant | needs_review |
| orangerie | `joconde-00000089566` | background | zh-hant | needs_review |
| orsay | `Q136029544` | background | ja | needs_review |
| orsay | `Q16696928` | background | zh | needs_review |
| orsay | `Q17493337` | facts | fr | needs_review |
| orsay | `Q17493365` | guide | es | needs_review |
| orsay | `Q17495145` | facts | ja,zh | needs_review |
| orsay | `Q17495459` | analysis | es | needs_review |
| orsay | `Q3563746` | background | ja | needs_review |
| orsay | `Q3766165` | guide | es | needs_review |
| orsay | `Q3818018` | analysis | es,fr | needs_review |
| orsay | `Q3820705` | guide | ja | needs_review |
| orsay | `Q3985182` | facts | ko | needs_review |
| orsay | `Q5287337` | background | es,fr,it,zh | needs_review |
| petit_palais | `Q104445111` | guide | it | needs_review |
| petit_palais | `Q104445393` | background | zh,zh-hant | needs_review |

合计 39 段 / 29 件（guide 7 段，深度段 32 段）。

### A2. 问答

| 馆 | 件 | 缺的语言 | 现有行状态 |
| --- | --- | --- | --- |
| louvre | `Q115672867` | de,fr,it | needs_review |
| louvre | `Q11931734` | ja,zh,zh-hant | needs_review |
| louvre | `Q139564920` | pl,zh | needs_review |
| louvre | `Q19005175` | zh,zh-hant | needs_review |
| louvre | `Q19117698` | ko | needs_review |
| louvre | `Q19308202` | ko | needs_review |
| louvre | `Q21406865` | de,es,fr,it,pl | needs_review |
| louvre | `Q29656195` | zh | needs_review |
| louvre | `Q29839727` | ko | needs_review |
| louvre | `Q29862653` | zh-hant | needs_review |
| louvre | `Q29863003` | de,es | needs_review |
| louvre | `Q29863311` | es,it,pl | needs_review |
| louvre | `Q29864681` | de | needs_review |
| louvre | `Q29864760` | ja | needs_review |
| louvre | `Q55873828` | ja,ko,zh,zh-hant | needs_review |
| louvre | `Q87456734` | zh-hant | needs_review |
| orangerie | `Q121160206` | de,zh-hant | needs_review |
| orangerie | `joconde-00000089551` | fr | needs_review |
| orsay | `Q17491841` | it,pl | needs_review |
| orsay | `Q17494069` | zh | needs_review |
| orsay | `Q17495461` | zh-hant | needs_review |
| orsay | `Q5745603` | ko | needs_review |
| orsay | `Q76450701` | zh | needs_review |
| petit_palais | `Q104444056` | ja | needs_review |
| petit_palais | `Q104445794` | de,zh-hant | needs_review |
| petit_palais | `Q104445860` | ja,zh,zh-hant | needs_review |
| petit_palais | `Q104454170` | de | needs_review |
| petit_palais | `Q106462056` | it | needs_review |
| petit_palais | `Q65784521` | zh | needs_review |

合计 50 组 / 29 件（件 × 语言算一组）。缺口指该语言一条已发布的问答都没有。

### A3. 作者简介

无缺口（10-15 补齐，230 → 0）。

### A4. 2026-10-17 收尾后剩余（用户批准用 gpt-4o 判官/重译，缺口 106 → 6）

**以下为 10-17 收尾后的手记，上面 A1/A2 的明细与全视图仍是 10-15 快照，下次重跑 SQL 时整体替换。**

| 馆 | 件 | 段/语言 | 原因 | 处理 |
| --- | --- | --- | --- | --- |
| louvre | `Q29863311` | 问答 es/it/pl | 问句夹法语机构名，语言检测误判 | PR #992 已修检测；**上 prod 后补跑 translate** |
| louvre | `Q115672867` | 问答 it | 答案法语人名多，同上 | 同上 |
| orsay | `Q3820705` | guide ja | gpt-4o 固定把 "muted blues" 译成「mutedな青」，残留英文被正确拦下 | 真缺陷，待定：改翻译提示词，或接受缺这一种语言 |
| louvre | `Q11770763` | significance fr | 判官不认「guerre d'indépendance espagnole」= Peninsular War（误判）；**en 原文也残缺**，"Instead, Goya imbues them…" 没有前文 | 根在 en：要修得重生成 en 意义段，会作废 en 音频，动手前先查有没有音频并问用户 |

另：`GAP_BIO` 里的 Q213612、Q541976 是 rijksmuseum 件，非巴黎缺口（SQL 第 ③ 段未按馆过滤）。

---

## 不算缺口（SQL 第 ② 段会列出，但不归补语种）

目前没有。2026-10-10 记的 `Q123234813`（卢浮宫陶罐）现在有 1 段已发布 en，10-14 补语种时已一并翻译，出表。

---

## C. 已销账

| 日期 | 范围 | 结论 |
| --- | --- | --- |
| 2026-10-10 | 巴黎四馆补语种 | 段 4406 / 问答 1422 组 / 作者简介 538 条补齐。音频作废 0 条；写前快照 `ops-snapshots/production/20261010T*_translate_<slug>.json.gz`；服务器日志在 `/opt/gomuseum/runs/translate_*.log` |
| 2026-10-15 | 巴黎四馆补语种(第二次) | 段 2738 / 问答 1581 组 / 作者简介 230 条补齐(含奥赛 Q17495685 单件出错后单独补跑 ja/ko/pl/zh-hant)。音频作废 0 条;写前快照 `ops-snapshots/production/20261014T*_translate_<slug>.json.gz`;日志 `/opt/gomuseum/runs/translate_paris_1014.log`、`translate_orsay_1015.log` |
| 2026-10-17 | 巴黎四馆补齐收尾(用户批准) | 106 处 → 6 处：Q5287337 en 末尾残句已删并重译 9 语（作废 1 条 en 音频，经批准）；26 段 needs_review 中 21 段 gpt-4o 判官连判两次通过发布；其余与缺问答的用 gpt-4o 重译补约 50 组。写前备份 `/opt/gomuseum/backups/pre-fixgaps-{sections,qa}-20261017.csv`；日志 `/opt/gomuseum/runs/fix_gaps_bc_1017.log`。剩余 6 处见 A4 |
