# 证据包（阶段1·材料地基）— 设计

> **状态**:设计定稿(2026-06-29 brainstorm)。下一步 writing-plans。
> **主文档**:`docs/architecture/museum-api-contract.md`(路线图阶段1)。本 spec = 阶段1 设计记录,完成后回写主文档。
> **关系**:证据包 = 内容唯一来源,**阶段2** 把生成切到它(去重 lane + 动态模块 + hedge),届时奥赛重生成一次。本期(阶段1)只**建 + 存**证据包,生成暂仍用旧材料。

## 1. 背景与目标

当前生成材料 = `build_material(attributes)` 拼成的文本块(Wikipedia extract + Joconde 字段 + Wikidata 基础)。问题:① 没用上 Wikidata 大量结构化属性(P180 描绘/P135 流派/P88 委托人…);② 材料无类型,无法区分事实 vs 解读 vs 争议 → 无法 hedge,也无法精准分发到各 lane。

**目标**:每件 onboard/生成时,从配全的源抓取、组装成一份**分类证据包**(原子事实 + 标源叙事块 + 争议项)落库,作为后续一切内容生成的唯一来源。"博物馆负责事实,AI 负责讲法"的事实底座。

## 2. 源配全(本期通用源,无需新 key)

- **Wikidata**:现有(标题/作者/年代/类别/图)+ 补 **P180 描绘内容、P135 艺术流派、P136 题材、P88 委托人、P186 材质、P1343 著录文献**(经新 SPARQL 查询取值+标签,run_query 注入式)。
- **Joconde**(法国官方,经 P347,已接):补高价值字段 `domaine/denomination/ecole_pays/periode_de_creation/localisation`(在现有 8+2 字段基础上)。
- **Wikipedia**:作品全文 `extract_*` + 作者全文 `artist_extract_*`(均已在 attributes,直接用)。
- **Europeana**:**本期暂缓**——需用户注册免费 API key;拿到后作为阶段1 快速跟进补一个 EuropeanaSource 连接器。核心三源已足够起步。

## 3. 证据包结构

每件一份,落 `MuseumObject.evidence_pack`(JSONB,新列,加法+迁移):

```json
{
  "facts": [
    {"claim": "委托人", "value": "Khalil Bey", "source": "wikidata:P88", "topic": "background"},
    {"claim": "描绘内容", "value": "female nude", "source": "wikidata:P180", "topic": "analysis"},
    {"claim": "材质", "value": "huile sur toile", "source": "joconde:materiaux_techniques", "topic": "analysis"}
  ],
  "narrative": [
    {"text": "<Wikipedia 作品全文>", "source": "wikipedia:work", "type": "mainstream"},
    {"text": "<Wikipedia 作者全文>", "source": "wikipedia:artist", "type": "mainstream"}
  ],
  "flagged": [
    {"text": "研究者认为模特是 Joanna Hiffernan", "type": "contested", "source": "wikipedia:work"}
  ]
}
```

- **facts**:结构化源每项一个原子,`type` 隐含为 `fact`(规则,不需 LLM);`topic` = lane 提示(structured→lane 的静态映射表,如 P88/P571→background、P180/P186→analysis、P135/P136→significance、P170 作者属性→artist)。
- **narrative**:叙事源整块文本,按源标 `mainstream`(不做原子拆解)。
- **flagged**:**一次轻量 LLM** 扫 narrative,挑出"研究者认为/可能/仍有争议/推测"类句子,标 `contested`/`inference`/`unverified`(供阶段2 hedge)。

## 4. 构建:build_evidence_pack

`build_evidence_pack(obj_row, registry, *, run_query=None, complete=None) -> dict`(注入式,离线可测):
1. **结构化事实**:从 `obj.attributes`(Joconde 字段已在)+ **新 Wikidata 富属性 SPARQL**(P180/P135/P88…取值与标签)→ 组装 `facts` 原子项(各带 source + topic,经静态映射 `_TOPIC_BY_SOURCE`)。
2. **叙事块**:从 `attributes` 取 `extract_*`(作品)、`artist_extract_*`(作者)→ `narrative` 块标 mainstream。
3. **争议抽出**:把 narrative 合并文本喂 `complete`(注入,默认 `default_complete`),prompt = "逐句挑出非主流共识的句子:研究者意见/可能/争议/推测/未证实,分类返回 JSON";空/失败 → `flagged: []`(健壮,不拖垮)。
4. 返回 `{"facts": [...], "narrative": [...], "flagged": [...]}`。

**落库**:`MuseumObject.evidence_pack = pack`,在 `generate_object` 里(stub 抓材料/作者材料之后)产出并 flush;`try/except` 包裹(任一源/LLM 抖动不拖垮生成)。

## 5. 富属性 SPARQL(新)

新查询(`build_evidence_pack` 内,run_query 注入):给定 work qid,取 P180/P135/P136/P88/P186/P1343 的值与 en 标签(`wikibase:label` 服务)。镜像 `material.fetch_artist_material` 的注入式模式(默认真实 SPARQL,测试注入 fake)。

## 5b. facts 面板策展 + 人性化(本期一起做)

现状(草地上的午餐截图):"作品信息"面板**直接倒 Joconde 学术原始数据**——法语收藏链、法语展览清单、`Tabarant 66` 这类参考文献代号、未译材质 `peinture à l'huile`、原始尺寸 `H. 208, l. 264.5`。对普通游客无意义甚至劝退。

**改造(区分"展示级"与"材料级"事实)**:
- **`get_object_content.facts` 只返展示级、且人性化**:`artist / date / medium / dimensions / inventory / location`。
  - **medium**:优先取 **Wikidata P186 材质标签**(按 language 干净:油画/Oil on canvas)→ 回退 Joconde 归一化。
  - **dimensions**:优先取 **Wikidata P2048 高 + P2049 宽**(干净数字)→ 拼 `宽 × 高 cm`;回退解析 Joconde mesures。
- **参考文献(bibliography)→ 彻底不进展示**(只在 evidence_pack 留作溯源)。
- **provenance / exhibitions → 本期从 facts 面板移除**(返 null/空,前端已容错不显示);它们进 evidence_pack 的材料级,**阶段2 由 background lane 讲成流转/首展故事**。
- 契约形状不变(`facts` 字段还在),只是 provenance/exhibitions/bibliography 返空 + medium/dimensions 人性化 → 前端面板自动变干净,**无需前端改**。

**证据包据此分级**:`facts` 原子加 `display: bool`(或 `tier: "wall_label" | "material"`)——wall_label 级供面板,material 级只喂生成。

## 6. 非目标(本期)

- **生成切到证据包**(去重 lane/动态模块/hedge)= **阶段2**。本期证据包**只建+存**,旧生成路径不变。
- **Europeana**:暂缓(需 key)。
- **全原子抽取**(LLM 拆 Wikipedia 成原子)= 否(用块+争议抽出,够且省)。
- **prod 重生成**:阶段2 做完后一次性重生成,本期不动 prod 内容。

## 7. 契约 / 迁移

- `MuseumObject` 加 `evidence_pack` JSONB 列(nullable,加法)。Alembic 迁移。
- **不改任何 API 端点**(evidence_pack 是后台中间产物,不进 content 契约)。前向兼容。

## 8. 测试

- **build_evidence_pack 单测(注入式)**:结构字段→facts 原子(含 topic 映射);extract_*→narrative 块;fake complete 返争议→flagged 标类;源缺失/LLM 异常→优雅降级(facts 仍在,flagged 空)。
- **富属性 SPARQL**:fake run_query 返 P180/P88 行 → facts 含描绘/委托人。
- **集成**:generate_object 跑完 `evidence_pack` 落库(JSONB),旧 content 路径不回归。
- **迁移**:升级加列、降级删列。

## 9. 改动文件

- `backend/app/models/museum_object.py`(`evidence_pack` 列)+ Alembic 迁移
- `backend/app/services/enrichment/evidence.py`(**新**:`build_evidence_pack` + 富属性 SPARQL + 争议抽出 prompt + topic 映射)
- `backend/app/services/enrichment/sources/joconde.py`(补字段)
- `backend/app/services/enrichment/pipeline.py`(generate_object 产出+落 evidence_pack,try/except)
- `backend/app/services/museum_repo.py`(get_object_content.facts 策展+人性化:medium←P186、dimensions←P2048/P2049、bibliography/provenance/exhibitions 移出面板)
- 测试:`tests/unit/services/enrichment/test_evidence.py`(新)、`test_joconde_source.py`、`tests/integration/test_generate_pipeline.py`、`tests/integration/test_pack_and_content_facts.py`(facts 策展)
- 完成后**回写主文档**(evidence_pack 列 + 证据包结构确认)
