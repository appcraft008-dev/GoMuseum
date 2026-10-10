# 生成流程的 Wikidata 单实体查询改走 Action API — 设计

> **状态**:设计定稿(2026-10-10 会话,用户同意方向 A)。下一步 writing-plans。
> **关系**:懒生成首屏提速专题的第 ① 步。前置已合 staging:#881(作者卡已查过跳过事实查询)、
> #882(准备阶段并发预取)、#883(证据包在拼材料之前建)。**#881–#883 等本设计做完一起上 prod**(用户 10-10 定)。

## 1. 背景与目标

懒生成首屏(用户语言讲解可见)staging 实测 27–42s,其中 AI 写+核查+翻译只占 9–12s,其余是 AI 之前的联网取数。
#882 把取数改成并发后,首屏取决于**最慢的那一次 Wikidata 查询**。

2026-10-10 服务器上对 28 件 stub 串行抽样(同 IP,同一批 qid):

| 查询(WDQS SPARQL) | 中位 | p90 | 失败 |
|---|---|---|---|
| 多语标题 | 2.2s | 60s(卡满超时) | **5/28 超时 → 资料被静默丢掉** |
| 作者解析(P170) | 1.4s | 12.9s | 1/28 |
| 证据包富属性 | 4.1s | 19.8s | 0 |
| 作者事实 | 2.7s | 10.4s | 1/28 |
| **`wbgetentities` 一次取 labels+claims+sitelinks** | **0.49s** | **0.55s** | **0/28** |

根因:这些都是「查一个实体的几项属性」,却用了为复杂查询设计、负载高时会卡住的 SPARQL 服务(WDQS)。
Action API `wbgetentities` 正是单实体读取接口,走缓存,且不受 WDQS「每 IP 5 并发 / 每分钟 60s 处理时间」的限制。

**目标**
1. 速度:准备阶段 ≤ 6s(瓶颈变成看图),首屏约 15–17s,不再有 Wikidata 60s 慢尾。
2. 质量不降:取到的数据与旧实现**逐字段等价**(§5 验证);失败先重试,重试都失败才放弃并记日志——消除今天「超时即静默丢资料」。
3. 顺带修旧 bug(§4)。

**非目标**:批量/目录类 SPARQL(`fetch_wikidata_labels_batch`、`backfill._fetch_creators`、目录抓取 `sources/wikidata.py`、
`fetch_museum_building_photo`)不动——一次查几百件正是 SPARQL 擅长的;61 件假作者卡的数据清理另起(§4)。

## 2. 方案 A:函数签名不变,内部换 Action API

### 2.1 新客户端 `app/services/enrichment/wikidata_api.py`

```python
def get_entities(ids, *, props, languages=None) -> dict[str, dict]:
    """wbgetentities。ids 按 50 个一批;返回 {qid: entity_json},缺失/不存在的实体不出现在结果里。"""
```

- 端点 `https://www.wikidata.org/w/api.php`,`action=wbgetentities&format=json`,`props` / `languages` 用 `|` 连接,
  User-Agent 复用 `sources/wikidata.USER_AGENT`,带 `maxlag=5`(Wikimedia 推荐的礼貌参数)。
- 单次超时 10s;429 / 5xx / 超时 / 连接错误 / `maxlag` 错误 → 重试,共 3 次;有 `Retry-After` 按它等,否则 1s、2s 退避。
  3 次都败 → 抛异常(调用方已有 `except` → `prep: ... failed` warning,行为同今天,但只在真失败时发生)。
- 进程级 `threading.BoundedSemaphore(2)` 限同时在途请求(Wikimedia API 礼仪:不要大并发)。
- 可注入:各调用函数新增 `get_entities=None` 参数(测试/离线注入),替代原 `run_query`。

### 2.2 六个函数换实现(函数名、参数、返回结构不变)

| 函数(material.py / evidence.py) | 取什么 | Action API 实现 |
|---|---|---|
| `fetch_wikidata_labels(qid, langs)` | 实体标签 | `get_entities([qid], props="labels", languages=_query_langs(langs))` → 原始 `{lang: value}` → 原 `_collapse_variants` |
| `resolve_creator_qid(qid)` | 唯一作者 | `props="claims"` 取 P170 语句;每条语句造与 SPARQL 行同形的候选 → 原 `creator_candidate` 排序规则(见 §3.1) |
| `fetch_artist_material(qid, registry, country_lang, artist_qid)` | 作者维基条目名 | 作者实体 `props="sitelinks"` → `enwiki` / `{cl}wiki` 的 `title`;其后 Wikipedia 抓正文不变 |
| `fetch_artist_facts(qid, artist_qid)` | 生卒/国籍/代表作(英文) | 作者实体 `props="claims"` 取 P569/P570/P27/P800 的主值;P27/P800 的值实体再一次 `props="labels", languages="en"` 批量取名 |
| `fetch_artist_i18n_facts(artist_qid, langs)` | 国籍/代表作多语名 | 同上取 P27/P800 主值,值实体批量取 `wanted` 语言标签;其余(先选作品集合再逐语言取名、字形转换)原样 |
| `fetch_rich_facts(qid)` | 证据包 10 项 | 作品实体 `props="claims"` 取 `_RICH_PROPS` 的主值;值实体批量取 en 标签;每 pid ≤ 5 条、无英文名跳过不变 |

`artist_qid` 为空时:`fetch_artist_material` / `fetch_artist_facts` 返回 `{}`,**不再走「作品→P170 遍历」**。
流水线总是先 `resolve_creator_qid`;它返回空 = 无作者或故意弃权(§3.1),遍历只会绕过这个判断(这正是 §4 假作者卡的来源)。

## 3. 必须原样保留的语义

### 3.1 作者解析(`creator_candidate` 规则不改,只换输入来源)
- 每条 P170 语句 → 候选 `(rank 序, 不确定性序, -引用数, QID 数字)`,取最小。
- rank:preferred=0、normal=1、deprecated → 排除。
- 不确定性:P1480 限定词无=0、presumably(Q18122778)=1、possibly(Q30230067)=3、其它=2;一条语句多个 P1480 → 每个各成一候选(同 SPARQL 每行)。
- 引用数:该语句 `references` 条数。旧 SPARQL 按 `(artist, rank, cert)` 分组计数——同一作者两条同 rank 语句时会相加;新实现按同样分组相加,保证等价。
- `snaktype` 为 `somevalue`(未知值)/ `novalue` → 不产候选(旧实现靠 `is_wikidata_qid` 拦 blank node,结果相同)。

### 3.2 「主值」= SPARQL `wdt:`(truthy)
对一个属性:排除 deprecated;若有 preferred 则只取 preferred,否则取 normal;只取 `snaktype=value` 的。
作者事实、多语事实、证据包都用这个规则。

### 3.3 其它
- 年份:`time` 去掉前导 `+` 后取前 4 位(旧实现对 SPARQL 的 `1748-01-01T…` 取 `[:4]`,两者结果相同;公元前日期两边一样截出 `-050` 这类值,不在本次范围)。
- 无英文名的值:旧实现(label 服务退回原始 QID 再过滤)= 跳过;新实现 en 标签缺失 = 跳过。
- 字形变体(zh-hans > zh-cn > zh;繁体链;港式垫底)、`_collapse_variants`、代表作「先选同一批作品再逐语言取名、按被标注语言数排序」——原代码不动,只换数据来源。
- 多值属性的**顺序**:旧 SPARQL 行序不保证(多国籍时取哪个是碰运气);新实现按 Wikidata 语句顺序,确定可复现。验证时归为「顺序差异」(§5)。

## 4. 顺带修复的旧 bug

1. **假作者卡**:作者为「未知值」时,`resolve_creator_qid` 正确返回空,但随后 `fetch_artist_facts` 走 P170 遍历,把 blank node
   的哈希当作者 QID 写回(`out["artist_qid"]`),流水线据此建出空作者卡。prod 现有 **61 件作品**(卢浮宫 59 / 小皇宫 2,均 ready)
   挂着 32 位哈希作者 QID 和对应的 61 张空作者卡。新实现不再遍历(§2.2),从源头堵住。
   **存量清理不在本设计**:属 prod 写操作,记待办,按纪律 37 单独列写入面报用户确认。
2. **「未知值」日期**:同一机制下生卒年会被存成 `http`(blank node URL 的前 4 位)。prod 目前 0 条;新实现按 §3.2 只取 `snaktype=value`,一并堵住。

## 5. 等价验证(切换的硬门槛)

脚本 `backend/scripts/verify_wikidata_api_parity.py`(只读,不写库):对样本逐件分别调旧 SPARQL 实现(保留在脚本内作参照)与新实现,逐字段比对。

**样本 ≈100 件**,跨 5 馆,刻意覆盖:多 P170 作者、P170 未知值、无 P170、Joconde 合成 id、证据包满的名作、无中文标签、有繁体/港式标签、作者有多国籍/多代表作。

**每处差异必须归类**:
- 完全一致;
- 仅顺序不同(多值集合相等);
- 旧 bug 被修(§4);
- WDQS 滞后(SPARQL 副本落后于实时数据,复查 Wikidata 页面确认新值为当前值);
- **无法解释:必须 0 件,否则不切换。**

验证结果写进 PR 描述(各类计数 + 每条非「完全一致」的明细)。

## 6. 测试

- `wikidata_api`:批量切分(>50)、429 带 Retry-After 重试后成功、3 次失败抛出、信号量同时在途 ≤ 2。
- 六个函数各用**真实形状的 entity JSON 夹具**(从 Wikidata 实取后裁剪,不手编)测:主值规则(preferred 压 normal、deprecated 排除)、
  未知值不产候选/不产日期、多 P1480、同作者多语句引用数相加、字形变体、无英文名跳过、每 pid ≤5。
- 回归:`artist_qid` 为空时作者资料/事实返回 `{}`,不再产出哈希作者。
- 现有调用方测试改为注入 `get_entities`;生成流水线全套保持绿。

## 7. 上线与复测

1. staging 合并后用 `ttfc.py` 复测 ≥3 件未生成件(含首次出现的作者):准备阶段 ≤ 6s、首屏 15–17s。
2. 与 #881–#883 一起提 staging→main(用户合并);上 prod 前查有无长任务在跑。
3. prod 上线后看 `prep: ... failed` warning 与懒生成首屏耗时。

## 8. 改动文件

- 新增 `backend/app/services/enrichment/wikidata_api.py`
- 改 `backend/app/services/enrichment/material.py`(5 个函数)、`evidence.py`(`fetch_rich_facts`)
- 改 `backend/app/services/enrichment/pipeline.py`(离线开关由 `run_query` 换为 `get_entities`)
- 新增 `backend/scripts/verify_wikidata_api_parity.py`
- 测试:新增 `tests/unit/services/enrichment/test_wikidata_api.py`;更新 `test_material.py`、证据包与流水线相关测试
- `docs/ops/backlog.md`:加「61 件哈希作者 QID 清理」
