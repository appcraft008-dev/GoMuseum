# Joconde 目录件的作者 qid 解析（设计）

- 日期：2026-10-07
- 状态：待用户审阅
- 出处：橘园 TOP50 内容复核会话,`房子们`(Les maisons)等 38/50 件缺作者简介,手工核实修复后用户要求"通用性问题,需要一个解决方案"

## 1. 问题

作者简介（`artists.bio`）靠 `attributes["artist_qid"]` 关联到 Wikidata 作者实体。这个字段目前只有一条解析路径：

```python
# app/services/enrichment/pipeline.py:195
aqid = (o.attributes or {}).get("artist_qid") or _resolve_creator(o.qid)
```

`_resolve_creator(qid)` → `resolve_creator_qid(qid)` 拿**作品自己的 Wikidata qid** 去查 P170（创作者）。这条路要求作品本身是 Wikidata 实体。Joconde 目录来源的件用的是合成 id（如 `joconde-00000089538`），不是 Wikidata qid，P170 查询天然查不到任何行——即使 `artist_en`/`artist_zh` 字段里已经有原始署名字符串（Joconde 惯用"姓 名"全大写姓氏格式，如 `SOUTINE Chaïm`、`RENOIR Pierre Auguste`）。

`artist_qid` 一旦解析不出来，`generate_object` 里整段作者富化（`_enrich_artist_and_titles`，bio/多语名字/国籍/代表作）都被跳过——不是生成了空字段，是**完全没跑**。

**已知影响面**（`app/services/enrichment/batch_names.py:47-48` 注释）：卢浮宫 17283 件里仅 1 件有 `artist_qid`，10041 件作者名因此没有中文。橘园本次 TOP50 复核实测 38/50 件同样的问题，背后只有 8 个独立作者，手工核实后 7 个已在别馆解析过（跨馆共享生效），只有 1 个（Soutine）是全新作者。只要是走 Joconde 目录（而非 Wikidata 作品清单）铺的馆/件，都会撞到这个缺口，包括未来新上的馆。

## 2. 目标与非目标

**目标**：`generate_object` 跑到作者富化这一步、`_resolve_creator(o.qid)` 失败时，追加一级"按原始署名字符串找 Wikidata 作者实体"的解析，解析结果直接落 `attributes["artist_qid"]`，之后流程不变（仍然共享 `artists` 表、仍然只补缺不覆盖）。

**非目标**（本次不做，YAGNI）：
- 不建新表/索引缓存。解析结果落 `artists` 表后天然跨馆复用（本次橘园 7/8 命中已验证），新馆增量远低于需要专建缓存的量级。
- 不做人工审核队列 UI。歧义/查不到 = 留空，维持现状（人工看到缺口再手工处理，就像本次橘园的处理方式）。
- 不特殊处理真正的多作者作品（夫妻合作、工作室联合署名）——§3.1 的拆分+裁决会让这类情况自然落到"两个不同 qid → 留空"，不额外设计"选哪个作者当代表"的规则。

## 3. 方案

### 3.1 解析算法：`resolve_creator_by_name(name, category)`

新函数，放 `app/services/enrichment/material.py`（与 `resolve_creator_qid` 并列，同属"作者解析"职责）：

用 `curl` 实测过 Wikidata API 的真实行为（不是纯推理），橘园 `ROUSSEAU Henri;LE DOUANIER ROUSSEAU` 这一例正好同时踩中两个坑，定下了下面的步骤：

- 整串（带 `;`）去查 `wbsearchentities` → **0 个结果**（搜索引擎不认分号拼接）。
- 拆开后单独查 `LE DOUANIER ROUSSEAU` → 第一条命中就是 Q156386 Henri Rousseau（French painter, 1844–1910），后面几条是展览条目噪声。
- 原始顺序 `ROUSSEAU Henri`（姓 名）单独查 → **0 个结果**。
- 重排成 `Henri Rousseau`（名 姓）查 → 命中 3 个真人（画家 / 插画师 / "国际义人"称号获得者），**不是整串不敏感，是姓名顺序必须接近自然语序才搜得到，拿到结果后还要看职业才能去重**。

据此，算法是：

1. **先按 `;`/`/`/`&`/`and`/`et` 拆分**（复用 `app/services/matching/people.py` 里已有的 `_SPLIT` 正则，不重写一份）。Joconde 的 `;` 两侧经常是"正式署名 + 绰号"（同一人），偶尔才是真正的联合署名（两个人）——拆开逐段解析，靠后面的"裁决"步骤区分这两种情况。
2. **每一段**：先拿原始字符串整段去查 `wbsearchentities`（`language=en`，`limit=5`）；查无结果（这段大概率是"姓 名"顺序）则用 `app/services/matching/normalize.py` 的 `normalize()` 把词序转成"名 姓"再查一次。
3. **职业过滤**：每一段查到的候选，用 `wbgetentities`（`props=claims`）查 P31（instance of）+ P106（occupation），只留「human **且** P106 命中视觉艺术职业白名单」的候选。白名单：painter(Q1028181)、sculptor(Q1281618)、engraver(Q329439)、printmaker(Q10862983)、draughtsman(Q15296811)、ceramicist(Q13365117)——覆盖面对标"这是不是个做视觉艺术的人"，不用卡具体画种/雕塑种类，也不收"illustrator"这类泛称（Henri Rousseau 案例里插画师候选如果被收进来,过滤后会剩 2 个,无法唯一裁决）。实现前逐个 qid 过 Wikidata 核实（§3.4 单测会把真实查到的职业 qid 钉进断言）；以后遇到白名单漏掉的职业（如金匠、摄影师）按实际案例补，不预先穷举。
4. **每段内裁决**：过滤后**恰好剩一个**候选才算这段解析成功；0 个或 ≥2 个都算这段失败（不打分硬选）。
5. **跨段裁决**：所有解析成功的段落得到的 qid 取**去重后的集合**——集合大小为 1（包括"只有一段解析成功，其余段失败"的情况）才采信、写回 `artist_qid`；集合大小 ≥2（真正不同的两个人，如夫妻合作）则整体返回 `None`，不强行二选一。

这是纯函数（给定 name + category，返回 qid 或 None），不读写 DB，方便单独测。网络调用全部走 `material.py` 已有的 `run_query`/HTTP 封装模式（可注入 mock，离线可测）。

### 3.2 接入点

`pipeline.py:195` 改成：

```python
aqid = (o.attributes or {}).get("artist_qid") or _resolve_creator(o.qid)
if not aqid and o.artist_en:
    try:
        aqid = _resolve_creator_by_name(o.artist_en, o.category)
    except Exception:
        aqid = None
```

`_resolve_creator_by_name` 作为新的薄包装函数加在 `pipeline.py` 顶部（与 `_resolve_creator`/`_artist_facts` 并列，同样的"测试 monkeypatch 此处避免触网"模式）。失败（网络抖动/查询异常）当无法解析，不拖垮整件生成——与现有 `_resolve_creator` 调用处的异常处理策略一致。

下游不用改：`aqid` 一旦非空，`_enrich_artist_and_titles` 原有逻辑（建/补 `Artist` 行、纪律 37 只补缺不覆盖）照常跑。

### 3.3 风险与防呆

- **误判代价**：写错 `artist_qid` 会把错误的人物简介关联到共享实体上，污染所有引用该作者的馆藏（本仓库历史教训，见纪律 37 事故记录）。防呆 = §3.1 第 4 步的"唯一候选才采信"，没有"按分数选最高"的路径。
- **性能**：只有「P170 查不到 **且** `artist_qid` 原本为空」的件才会走这条新路径，且结果写回 `attributes` 后幂等（下次 `generate` 直接读到，不重复查）。单件最多增加 2-3 次 Wikidata HTTP 调用，量级与现有 `fetch_artist_material`/`fetch_artist_facts` 相当。
- **白名单遗漏**：职业白名单覆盖不全（比如摄影师、金匠类作者）会导致误报"查不到"（留空），不会导致误判——偏保守是故意的,符合宁缺毋滥。

### 3.4 验证计划

1. **正样本回归**：本次橘园手工核实的 8 个作者（Renoir Q39931 / Soutine Q160141 / Derain Q156272 / Utrillo Q108301 / Cézanne Q35548 / Matisse Q5589 / Rousseau(Le Douanier) Q156386 / Modigliani Q120993）写成单测固定输入输出，`resolve_creator_by_name` 必须原样复现这 8 个 qid（mock HTTP 响应，离线跑）。
2. **反例（弃权）**：实测过 `curl` 验证的真实歧义——单独姓氏 `"ROUSSEAU"` 在 Wikidata 一次搜索就命中 4 个不同的画家（Henri / Théodore / Philippe / Jacques Rousseau，各自独立的 qid，P106 职业过滤一个都排不掉）。虽然 Joconde 实际数据里几乎总带名字（不会真传入裸姓氏），但这个真实存在的歧义场景钉成边界单测：输入裸姓氏时必须返回 `None`，断言算法在真有多个合法候选时弃权，不是瞎猜其中一个。
   另外验证过的反面结论（别踩同一个坑）：原计划拿"ROUSSEAU Henri"（姓 名顺序,不带别名）当弃权反例，实测发现重排成"Henri Rousseau"后职业过滤恰好只剩画家 Q156386 一个——这其实是正样本，不是反例,已改用上面真正验证过歧义的裸姓氏输入。
3. **真实数据抽查**：改完后在橘园全馆（141 件，不只 TOP50）跑一次 dry-run（只打印会解析出什么 qid，不落库），人工过一遍输出名单，确认没有明显张冠李戴,再正式跑写库。
4. 现有 `tests/unit/services/enrichment/` 下的 material/pipeline 相关测试跑一遍确认不回归。

## 4. 实施范围

改动文件：
- `backend/app/services/enrichment/material.py`：新增 `resolve_creator_by_name`
- `backend/app/services/enrichment/pipeline.py`：新增薄包装 `_resolve_creator_by_name`，接入 `generate_object` 的作者解析分支
- 新增单测：`backend/tests/unit/services/enrichment/test_material.py`（或同目录新文件）覆盖 §3.4 的正样本+反例
- 不改 DB schema、不改 CLI 参数、不改任何既有已发布内容

跨馆存量回填（卢浮宫等已上线馆的历史缺口）不在本次范围——那是"用这个新函数跑一遍存量"的运维动作,设计落地后按 `docs/ops/backlog.md` 的既有节奏另行安排,不在这份 spec 里规划执行细节。
