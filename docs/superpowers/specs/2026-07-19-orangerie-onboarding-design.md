# 第二家馆:橘园美术馆上馆设计(零代码主张实证)

> 2026-07-19 定稿。范围:**本轮只上橘园**(用户选定;Rijksmuseum/CC0 适配器/Batch API 留下一轮单独 spec)。
> 双重目标:①产品——奥赛+橘园=巴黎印象派一日双馆,同一批用户;②工程——**"零代码上新馆"契约主张的第一次实证裁决**。

## 数据地基(2026-07-19 实测)

| 源 | 件数 | 说明 |
|---|---|---|
| Wikidata(P195=Q726781) | 19(16 有图) | 名作层(《睡莲》联作等)。⚠️ 橘园正确 QID=**Q726781**(非 Q1094962) |
| Joconde | 133 | 官方名精确=**"musée de l'Orangerie des Tuileries"**;Walter-Guillaume 收藏主体,© RMN 无图→文字层 |
| 合计 | ~150 | ≈ 橘园真实馆藏全量,天生小而全 |

预期形态:图录 ~16 / 档案 ~150;相机识别薄(16 图),搜索/墙签/懒讲解/馆介绍全功能。
成本:names ~150 件×10 语 分钟级 ~$10;intro 几分钱。**llm_usage 表将首次完整记录一次上馆成本**(成本工程①首个完整样本)。

## 方案取舍

- A 纯配置照配方(选定):零核心代码;若中途被迫改码,那就是本轮最有价值的产出(配方缺口→修复→回写契约,#286 模式)。
- B 只上 Wikidata 名作层(否):150 件全量才 ~$10,弃 133 件主体不值。
- C 顺带 P276 兜底扩收录(否):投机代码,YAGNI。

## §1 配置(唯一改动)

`backend/museums.yaml` 加:

```yaml
  orangerie:
    name_zh: 橘园美术馆
    name_en: Musée de l'Orangerie
    city_zh: 巴黎
    city_en: Paris
    country: FR
    wikidata_qid: Q726781
    category_filter: Q3305213
    categories: [Q3305213, Q219423,
                 Q860861, Q179700, Q241045, Q1066288,
                 Q93184, Q18761202, Q12043905, Q15123870, Q2647254, Q5078274,
                 Q125191]
    country_lang: fr
    sources: [joconde, wikipedia]
    joconde_museum: "musée de l'Orangerie des Tuileries"
    fetch_limit: 500
    sample_size: 10
    sample_qids: []
```

## §2 staging 验证(护栏内小样本,分钱级)

`catalog --limit 30`(wikidata)+ `catalog --source joconde`(133 件本来就小)→ `names`(护栏自动 limit=50)→ `intro`。
验证:馆名匹配中/分类映射/合成 qid/去重/介绍生成。staging 数据下轮 slim 刷新自然重置,不留债。

## §3 prod 配方全链(契约配方原样)

`catalog`(wikidata)→ `catalog --source joconde` → `names` → `images` → `backfill_embeddings` → `intro` → `coverage-report`。
全程 detached+日志(批处理纪律⑥);跑前确认无部署在途。

## §4 验收 = 零代码裁决

1. App 探索页**自动出现**橘园(list_museums 读表,前端零改动);馆包含介绍+封面(封面从 16 张有图件里得体性筛选);
2. 搜索命中橘园件、懒讲解可生成、双数字 ~16/~150;
3. `llm_cost_report` 出本次上馆分通路成本(记录进契约变更记录作为基准);
4. **裁决**:全程未改核心代码 → 零代码主张实证成立,回写契约;被迫改码 → 如实记录缺口+修复+回写(配方债,非失败)。

## 契约回写清单(完成后)

- 变更记录:第二家馆落地 + 实测上馆成本基准;
- 若有配方缺口修复,按 #286 模式各自成文。
