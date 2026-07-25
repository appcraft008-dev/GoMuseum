# 卢浮宫 v1 上馆(第三家)设计

日期:2026-07-21 · 状态:已批准(三问逐项确认)
前置:Batch names(成本工程②,#301)已上 prod,本案是其首个规模消费者。

## 目标

卢浮宫作为第三家馆上线,**规模检验零代码上馆配方**(18.5k 件,是奥赛的 3.5 倍)。
v1 口径 = **Wikidata 全收**(~18.5k 件,~10.9k 有图),分层懒生成自动消化;
**不碰 Joconde 142k**(留给 Meilisearch 换代项目)。前端零改动(馆列表自动出现)。

## 范围内唯一代码变更:多 QID 收藏锚点

卢浮宫藏品的 P195(collection)挂在**部门 QID** 而非馆 QID——这是配方现有的
单锚点假设(`?item wdt:P195 wd:{museum}`,wikidata.py)覆盖不了的。

**配置(已批准方案 1)**:`MuseumConfig` 加可选 `collection_qids: list[str]`,
缺省回退 `[wikidata_qid]`。馆身份(`wikidata_qid`,用于建筑照 P18/intro 材料/
对外把手)与收藏锚点(`collection_qids`)分离,orsay/orangerie 不写此键、
行为逐字不变(单元素 VALUES 语义等价)。

**SPARQL**:`?item wdt:P195 wd:{museum}` → `VALUES ?mus {{ {mus_values} }}` +
`?item wdt:P195 ?mus`。

## 卢浮宫配置条目(QID 实测于 2026-07-21 WDQS)

```yaml
louvre:
  name_zh: 卢浮宫
  name_en: Louvre Museum
  city_zh: 巴黎
  city_en: Paris
  country: FR
  wikidata_qid: Q19675
  collection_qids: [
    Q19675,      # 馆本体直挂(17件)
    Q3044768,    # 绘画部(10,303)
    Q3044772,    # 雕塑部(2,024)
    Q3044751,    # 近东古物部(1,475)
    Q3044747,    # 希腊伊特鲁里亚罗马古物部(1,346)
    Q3044749,    # 埃及古物部(1,193)
    Q3044767,    # 装饰艺术部(889)
    Q3044748,    # 伊斯兰艺术部(538)
    Q3044753,    # 版画素描部(449)
    Q106349126,  # 花园雕塑(106)
    Q121354106,  # 拜占庭与东方基督教艺术部(100)
    Q683074,     # 博尔盖塞收藏(63)
    Q106824040,  # 卢浮宫历史部(26)
  ]
  category_filter: Q3305213
  categories: [同 orsay 通用四大类列表]
  country_lang: fr
  sources: [wikipedia]        # 无 joconde(v1 不碰 142k)
  fetch_limit: 40000          # 18.5k 条目 × 多 P31 重复行余量
  sample_size: 30
  sample_qids: []
```

注意:古物/装饰艺术部藏品的 P31 多为 category 列表外类型(雕像/器物等已在
通用列表;若抓取实测显著低于 18.5k,属 P31 类型缺口,在 staging 小样阶段
发现并补 categories,不改架构)。

## 执行方式(已批准方案 A)

- **images 物化一把后台跑**:materialize 幂等(R2 key 存在即跳过)=天然断点
  续传,中断重跑即续。~10.9k 张 ≈ 3-4h。无需低峰(当前线上单用户)。
  嵌入(DINOv2)CPU 占用为已知代价,一次性。
- **names 用 `--use-batch`**(A 已上 prod):~18.5k 件 ≈ $37,免盯守。
- **names Batch ‖ images 并行**:Batch 远端异步(24h SLA)、images 本地 CPU,
  互不相干,提交 Batch 后立即启动 images,省约半天。

## 上线顺序(已批准)

1. **代码 PR**(collection_qids + SPARQL VALUES + louvre yaml + 测试)→ CI → 合 staging
2. **staging 护栏内小样验证**(轻量化护栏 limit=50 正好用):catalog 限量 →
   names 小样 → images 限量 → intro——端到端验证多 QID 配方,不跑全量
3. 用户点 staging→main → prod 部署
4. **prod 全量数据操作**(纯数据非代码,按橘园惯例直接连跑+事后报账):
   catalog(分钟级)→ names --use-batch 提交 ‖ images(3-4h)→
   Batch apply → intro → coverage-report 收官

## 预算

names Batch ~$37 + intro/封面几分钱 ≈ **$40 以内**;llm_usage 账本全程可查。

## 附录:collect_all_types 决策(2026-07-25 prod catalog 实测后)

首次 prod catalog 只落 10372 件(非 18.5k):`categories` 的 13 个"美术类" P31
过滤把**古物部+装饰艺术部** ~8k 件挡在外(P31 是"钻石/石碑/花瓶/石棺"等)。
类型呈长尾(top30 仅覆盖 36%),逐个列 category QID 到不了 18k。

**决策(用户 2026-07-25 选"扩类目补古物到~18k"):**
- `MuseumConfig.collect_all_types: bool`(缺省 False,存量馆零影响)。为 True 时
  catalog SPARQL 去掉 category 过滤子句(`build_cat_filter` 返回空串),整部门全收。
- category_config 补 top ~25 古物/装饰艺术 P31 → decorative_arts/artifact/textile/
  sculpture/manuscript(架构早预留这 8 大类,仅缺 P31 映射);长尾稀有类型留
  unknown 走 _FALLBACK 段落(宁缺毋滥,讲解仍接地)。
- louvre yaml 加 `collect_all_types: true`。实测新 query 形态返回 **18379 件**。
- 惠及未来百科式大馆(大英/Met)零代码上馆。

## 验收

- staging 小样:catalog 抓到多部门件、names/images/intro 全链通
- prod:archive ≈18.5k、catalog(有图)≈10.9k、封面=馆建筑照(Q19675 有 P18)、
  intro 3 段、探索页出现卢浮宫、懒讲解任抽一件端到端通
- 契约回写:配方多 QID 扩展写入 museum-api-contract(上新馆配方章)
