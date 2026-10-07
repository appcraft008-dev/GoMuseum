# Joconde 目录件的作者 qid 解析（设计）

- 日期：2026-10-07
- 状态：待用户审阅（已过 Opus + Fable 两轮独立评审并按结论改定）
- 出处：橘园 TOP50 内容复核会话,`房子们`(Les maisons)等 38/50 件缺作者简介,手工核实修复后用户要求"通用性问题,需要一个解决方案"

## 1. 问题

作者简介（`artists.bio`）靠 `attributes["artist_qid"]` 关联到 Wikidata 作者实体。这个字段目前只有一条解析路径：

```python
# app/services/enrichment/pipeline.py:195
aqid = (o.attributes or {}).get("artist_qid") or _resolve_creator(o.qid)
```

`_resolve_creator(qid)` → `resolve_creator_qid(qid)` 拿**作品自己的 Wikidata qid** 去查 P170（创作者）。这条路要求作品本身是 Wikidata 实体。Joconde 目录来源的件用的是合成 id（如 `joconde-00000089538`），不是 Wikidata qid，P170 查询天然查不到任何行——即使 `artist_en`/`artist_zh` 字段里已经有原始署名字符串。Joconde 的署名字符串有多种格式混用：常见"姓 名"顺序（`SOUTINE Chaïm`），姓氏不一定全大写（`Cézanne Paul`、`Matisse Henri` 姓也只有首字母大写），约一半还带 `(生年-卒年)` 后缀（原始数据，`_clean_artist` 会剥掉，见 §3.1）。

`artist_qid` 一旦解析不出来，`generate_object` 里整段作者富化（`_enrich_artist_and_titles`，bio/多语名字/国籍/代表作）都被跳过——不是生成了空字段，是**完全没跑**。

**已知影响面**——这一条原稿引用了 `app/services/enrichment/batch_names.py:47-48` 的注释，把"卢浮宫 17283 件里仅 1 件有 `artist_qid`"当成同一个根因的证据。**写这份 spec 的过程中直接查了 prod 数据，发现这条引用是错的**：卢浮宫全部 17283 件都是真实 Wikidata qid（`Q*`），一件 `joconde-*` 合成 id 都没有（`museums.yaml` 里卢浮宫没配 `joconde_museum`，根本不走 `JocondeCatalog` 这条入库路径）。卢浮宫那 6990 件缺 `artist_qid` 的，`artist_en` 基本也是空的——是"Wikidata 本身没有可用的创作者信息"（很可能是大量无名氏古物/装饰艺术品，本来就没有具体作者），不是这份 spec 要解决的问题，引用已订正，不再把卢浮宫当证据。

真正受影响、且已核实的：`museums.yaml` 里配了 `joconde_museum` 的馆（目前只有 orsay、orangerie）会用 `JocondeCatalog` 批量建 `joconde-*` 合成 id 的件。实测 prod 数据：**奥赛 1628 件 joconde 件全部缺 `artist_qid`**（且都有 `artist_en` 可用，新解析器能直接生效）；**橘园 122 件 joconde 件里 84 件缺**（本次 TOP50 复核撞到的 38 件是这 84 件的子集）。背后不是 84+1628 个不同的人——橘园这次手工核实的 8 个作者里 7 个已经在别馆（主要是奥赛）解析过，跨馆共享天然生效。只要未来新馆配了 `joconde_museum`，新入库的件都会撞到同一个缺口。

## 2. 目标与非目标

**目标**：`generate_object` 跑到作者富化这一步、`_resolve_creator(o.qid)` 失败时，追加一级"按原始署名字符串找 Wikidata 作者实体"的解析，解析结果直接落 `attributes["artist_qid"]`，之后流程不变（仍然共享 `artists` 表、仍然只补缺不覆盖）。

**非目标**（本次不做，YAGNI）：
- 不建新表/索引缓存。解析结果落 `artists` 表后天然跨馆复用（本次橘园 7/8 命中已验证），新馆增量远低于需要专建缓存的量级。
- 不做人工审核队列 UI。歧义/查不到 = 留空，维持现状（人工看到缺口再手工处理，就像本次橘园的处理方式）。
- 不特殊处理真正的多作者作品（夫妻合作、工作室联合署名）——§3.1 的拆分+裁决会让这类情况自然落到"两个不同 qid → 留空"，不额外设计"选哪个作者当代表"的规则。
- 不给已入库馆（奥赛等，真正走过 `JocondeCatalog` 的馆）回填限定词信息（历史数据 `artist_en` 已经被清洗过，这次改动后新字段不会神奇地补上已经发生过的清洗）。这不等于"信息永久丢失没法补"——Joconde 是外部开放数据集，随时能重新拉取，回填方式是"重新抓目录 + 重跑这个新函数"，属于 §4 已经排除在外的"跨馆存量回填"运维动作，不在本次设计范围内另行规划。

## 3. 方案

本节的算法经过两轮独立评审（Opus / Fable，均用 `curl` 实测 Wikidata API 交叉验证，不是纯推理）定稿；原始草案里的几处问题已经在下面直接改掉，不再保留"先错后对"的叙述。

### 3.1 入库阶段的一行修正：`_clean_artist` 别把限定词当生卒年删了

`app/services/enrichment/sources/joconde_catalog.py` 现在的清洗正则：

```python
_DATES = re.compile(r"\s*\([^)]*\)\s*$")  # 作者尾部"(1844-1926)"
```

这个正则**不看括号里是什么**，只要是字符串末尾的括号就删——"(1844-1926)"是生卒年，"(atelier)"/"(d'après)"/"(attribué à)"是**限定词**（说明这件不是作者本人画的），两种一起被删掉，下游（包括这次要加的新解析函数）从清洗后的 `artist_en` 永远看不到限定词存在过。

修法：把正则收紧成只匹配**日期形态**的括号内容（数字、`siècle`、`vers`、`?` 这类年代标记），非日期内容的括号保留：

```python
_DATES = re.compile(r"\s*\((?:\d[\d\s?.,\-–—]*|[^)]*si[eè]cle[^)]*)\)\s*$")
```

（具体字符类在实现时跑一遍奥赛+橘园全量 `Auteur` 字段核对——这两个馆是真正配了 `joconde_museum`、走 `JocondeCatalog` 入库的馆，不是凑出来的，上面只是方向）。这是 `joconde_catalog.py` 里**一行正则**的改动，不新增字段、不动 schema、不需要迁移——新入库的件从此 `artist_en` 会带着"(atelier)"之类的限定词；已入库的历史数据不受影响（见 §2 非目标）。

### 3.2 解析算法：`resolve_creator_by_name(name, category)`

新函数，放 `app/services/enrichment/material.py`（与 `resolve_creator_qid` 并列，同属"作者解析"职责）。

**步骤 0：限定词前置扫描（弃权闸）**。整串（`;` 拆分之前）扫一遍关键词（大小写不敏感，子串匹配即可）：`d'après`、`d'apres`、`atelier`、`école de`、`ecole de`、`entourage`、`suiveur`、`manner of`、`circle of`、`copie`、`copy after`、`attribué à`、`attribue a`、`attributed to`、`anonyme`、`anonymous`。命中任意一条 → 直接返回 `None`，不进入下面的拆分/查询流程。这一步堵住的是最接近本仓库历史事故形态的风险：仿作/工作室作品被错误关联到大师本人的简介（实测复现路径：`anonyme;Boucher François (d'après)` 清洗前如果限定词被保留，这一步就能在拆分之前直接弃权；§3.1 的正则修正是这一步生效的前提）。

**步骤 1：按 `;`/`/`/`&`/`and`/`et` 拆分**（复用 `app/services/matching/people.py` 里已有的 `_SPLIT` 正则，不重写一份）。Joconde 的 `;` 两侧经常是"正式署名 + 绰号"（同一人），偶尔才是真正的联合署名（两个人）——拆开逐段解析，靠后面的"裁决"步骤区分这两种情况。

**步骤 2：每一段两种词序都查，且要求候选词集合完全相等**。
- 实测过 `wbsearchentities` 对词序敏感（`"ROUSSEAU Henri"` 姓-名顺序查 0 结果，`"Henri Rousseau"` 名-姓顺序才有结果），但"查无结果才重排"这个 fallback 条件本身不可靠——`"GERARD Francois"` 姓-名顺序照样返回非空结果（全是噪声："Gérard-François Dumont"经济学家之类），永远不会触发 fallback。
- 所以**两种词序都要查**：原始顺序整段去查一次；再用新写的"姓名重排"函数（不是 `app/services/matching/normalize.py` 的 `normalize()`——那个只做大小写/去音符/压空白，不调换词序）把开头一段当姓氏、剩下当名字，试着重排后再查一次。姓氏本身可能是多个词（`Le Sueur Eustache`、`DE MACHY Pierre Antoine`），实现时对每个切分点都试一次（n-1 种切法），不是只试"第一个词 vs 剩余"这一种。
- 两次查询拿到的候选，都要求 Wikidata 搜索响应自带的 `match.text`，归一化（复用 `normalize()`）后的词集合与这一段输入的词集合**完全相等**才保留，不满足直接丢弃——这一步堵的是 `wbsearchentities` 前缀匹配造成的误判：`"LEON Paul"` 能匹配到 Q599801 Léon-Paul Fargue（法国诗人，P106 里碰巧也挂了 painter），词集合精确匹配能把这种"沾上边但不是同一个人"的候选先滤掉，而不是全靠后面的职业过滤兜底。

**步骤 3：职业过滤**。把两轮查询存活的候选 qid 去重后，**合并成一次** `wbgetentities`（`ids=Q1|Q2|Q3...`，`props=claims`）调用查 P31（instance of）+ P106（occupation）——不要每个候选单独查一次，一个有歧义的段落两种词序都查、各 5 条候选，不合并的话一段最多发 10 次请求。只留「human **且** P106 命中视觉艺术职业白名单」的候选。白名单（已逐个用 `Special:EntityData` 核实 label+description，不是抄来的）：

| 职业 | qid |
|---|---|
| painter | Q1028181 |
| sculptor | Q1281618 |
| engraver | Q329439 |
| draughtsman | Q15296811 |
| etcher | Q10862983 |
| printmaker | Q11569986 |
| ceramicist | Q7541856 |

不收"illustrator"（Q644687）这类泛称——Henri Rousseau 案例里真实存在一个"French illustrator"的同名候选，如果收进白名单，职业过滤后会剩两个人，唯一候选规则就救不回来了。以后遇到白名单漏掉的真实职业（金匠、摄影师等）按实际案例补，不预先穷举。

**步骤 4：每段内裁决**。过滤后**恰好剩一个**候选才算这段解析成功；0 个或 ≥2 个都算这段失败（不打分硬选）。

**步骤 5：跨段裁决**。所有解析成功的段落得到的 qid 取**去重后的集合**——集合大小为 1（包括"只有一段解析成功，其余段失败"的情况）才采信、写回 `artist_qid`；集合大小 ≥2（真正不同的两个人）则整体返回 `None`，不强行二选一。

这是纯函数（给定 name + category，返回 qid 或 None），不读写 DB，方便单独测。网络调用全部走 `material.py` 已有的 `run_query`/HTTP 封装模式（可注入 mock，离线可测）。

### 3.3 接入点

`pipeline.py:195` 改成：

```python
aqid = (o.attributes or {}).get("artist_qid") or _resolve_creator(o.qid)
if not aqid and o.artist_en and not o.qid.startswith("Q"):
    try:
        aqid = _resolve_creator_by_name(o.artist_en, o.category)
    except Exception:
        aqid = None
```

**`not o.qid.startswith("Q")` 这个限定不能漏**：`resolve_creator_qid` 对真正的 Wikidata 作品、但 P170（创作者）是"未知值"（blank node）的情况，会故意返回 `None`——这本身就是"宁缺毋滥"的弃权，不是查询失败。新的按名查找路径只应该补 Joconde 合成 id（`joconde-*`，天生不是 Wikidata qid）这一种"P170 这条路根本不存在"的情况，不能顺手把前者那种"存在但故意不猜"的判断也推翻了。

`_resolve_creator_by_name` 作为新的薄包装函数加在 `pipeline.py` 顶部（与 `_resolve_creator`/`_artist_facts` 并列，同样的"测试 monkeypatch 此处避免触网"模式）。失败（网络抖动/查询异常）当无法解析，不拖垮整件生成——与现有 `_resolve_creator` 调用处的异常处理策略一致。

下游不用改：`aqid` 一旦非空，`_enrich_artist_and_titles` 原有逻辑（建/补 `Artist` 行、纪律 37 只补缺不覆盖）照常跑。

### 3.4 风险与防呆

- **误判代价**：写错 `artist_qid` 会把错误的人物简介关联到共享实体上，污染所有引用该作者的馆藏（本仓库历史教训，见纪律 37 事故记录）。防呆 = §3.2 步骤 0 的限定词前置弃权 + 步骤 2 的词集合精确匹配 + 步骤 4 的"唯一候选才采信"，三层叠加，没有"按分数选最高"的路径。
- **性能**：只有「P170 查不到 **且** `artist_qid` 原本为空**且**不是 Wikidata qid」的件才会走这条新路径，且结果写回 `attributes` 后幂等（下次 `generate` 直接读到，不重复查）。单件最多两种词序各一次搜索 + 一次合并后的 `wbgetentities`，一段 3 次请求；多段署名（罕见）按段数线性增加。量级与现有 `fetch_artist_material`/`fetch_artist_facts` 相当，单件生成可接受；将来做存量回填要注意限速（`PoliteSession` 已有节流）。
- **白名单遗漏**：职业白名单覆盖不全（比如摄影师、金匠类作者）会导致误报"查不到"（留空），不会导致误判——偏保守是故意的，符合宁缺毋滥。
- **留痕**：解析结果写回时同时写 `attributes["artist_qid_source"] = "name_search"`（区分开 `resolve_creator_qid` 走的 P170 路径），万一后续发现某类输入系统性解析错，能一条 SQL 把受影响的件找出来，不用全库重新判断是谁写的。

### 3.5 验证计划

1. **正样本回归**：7 个无歧义的真实作者（Renoir Q39931 / Soutine Q160141 / Derain Q156272 / Utrillo Q108301 / Matisse Q5589 / Rousseau(Le Douanier) Q156386 / Modigliani Q120993）写成单测固定输入输出，`resolve_creator_by_name` 必须原样复现这 7 个 qid（mock HTTP 响应，离线跑）。**不收 Cézanne 当正样本**——下面第 2 条说明原因。
2. **反例（必须弃权）**，全部是实测验证过的真实歧义/陷阱，不是构造出来的假想场景：
   - `Cézanne Paul`：Wikidata 上同名同职业的父子两人（Q35548 父 1839–1906、Q17277915 子 1872–1947，P106 都含 painter），职业过滤排不掉，必须返回 `None`。
   - `LEON Paul`：会前缀匹配到 Q599801 Léon-Paul Fargue（法国诗人，P106 碰巧也挂了 painter）——验证 §3.2 步骤 2 的词集合精确匹配能把这个候选滤掉，不依赖"唯一候选"兜底。
   - `anonyme;Boucher François (d'après)`（假设 §3.1 的正则修正已生效、限定词没被清洗掉）：验证步骤 0 的前置扫描直接弃权，不会拆分后把 "Boucher François" 这一段单独解析成功再误采信。
   - 裸姓氏 `"ROUSSEAU"`：`limit=5` 下真实能搜出 2 个画家（Henri、Théodore Rousseau，P106 都过得了职业过滤）——数字订正为 2（原稿写的"4 个"是 `limit≥8` 才出现的，已核实订正），2 个已经足够验证"≥2 个合法候选 → 弃权"这条规则，不用追加 limit。Joconde 真实数据里几乎不会出现裸姓氏输入，这条测试是防御性的边界覆盖，不代表预期会被真实数据触发。
3. **真实数据抽查**：改完后在橘园全馆（141 件，不只 TOP50）+ 奥赛全馆（1628 件 joconde 件，覆盖更多限定词/多段署名形态，样本量也大得多）各跑一次 dry-run（只打印会解析出什么 qid，不落库），人工过一遍输出名单，确认没有明显张冠李戴，再正式跑写库。
4. 现有 `tests/unit/services/enrichment/` 下的 material/pipeline 相关测试跑一遍确认不回归。

## 4. 实施范围

改动文件：
- `backend/app/services/enrichment/sources/joconde_catalog.py`：收紧 `_DATES` 正则（§3.1），只此一行逻辑变化，不新增字段、不动 schema
- `backend/app/services/enrichment/material.py`：新增 `resolve_creator_by_name`（含姓名重排辅助函数）
- `backend/app/services/enrichment/pipeline.py`：新增薄包装 `_resolve_creator_by_name`，接入 `generate_object` 的作者解析分支（带 `not o.qid.startswith("Q")` 限定）
- 新增单测：`backend/tests/unit/services/enrichment/test_material.py`（或同目录新文件）覆盖 §3.5 的正样本+反例
- 不改 DB schema、不改 CLI 参数、不改任何既有已发布内容

跨馆存量回填（奥赛/橘园等已走过 `JocondeCatalog` 的馆的历史缺口，包括重新抓取 Joconde 目录以拿到未清洗的限定词信息）不在本次范围——那是"重新抓目录 + 跑这个新函数"的运维动作，设计落地后按 `docs/ops/backlog.md` 的既有节奏另行安排，不在这份 spec 里规划执行细节。
