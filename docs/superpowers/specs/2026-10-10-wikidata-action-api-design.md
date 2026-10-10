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

注:作者事实、证据包、多语事实在新实现里是**两跳**(先取语句,再批量取值实体的名称),约为上表单次耗时的 2 倍(~1s);作者资料(维基条目名)的 SPARQL 查询未在本次抽样中单列。结论不变:新实现每路 ≤~1s,远低于 WDQS 的 10–60s 慢尾。

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
- **失败判定看两层**:HTTP 状态(429 / 5xx)、网络(超时 / 连接错误),**以及响应体 `error.code`**——`maxlag`、`toomanyvalues` 等错误是 **HTTP 200 + `{"error": …}` 且没有 `entities` 键**(10-10 实测)。只看状态码会把它当成功,调用方拿到空结果,等于以「实体不存在」的面目重新静默丢资料。规则:响应体有 `error` → `maxlag` 重试,其它 error 直接抛;没有 `entities` 键 → 抛。
- 单次超时 10s;可重试的错误(429 / 5xx / 超时 / 连接错误 / `maxlag`)共试 3 次;有 `Retry-After` 按它等,否则 1s、2s 退避。
  3 次都败 → 抛异常(调用方已有 `except` → `prep: ... failed` warning,行为同今天,但只在真失败时发生)。
- 进程级 `threading.BoundedSemaphore(2)` 限同时在途请求(Wikimedia API 礼仪:不要大并发)。
- 可注入:各调用函数新增 `get_entities=None` 参数(测试/离线注入),替代原 `run_query`。

### 2.2 六个函数换实现(函数名、业务参数、返回结构不变)

**实现策略:转换成旧行、复用旧解析。** 每个函数拆成三层:取数(`get_entities`)→ **转换**(实体 JSON → 与旧 SPARQL 结果**同形的行**)→ **解析**(原有的逐行解析代码原样抽成 `_xxx_from_rows(rows, …)`,一行不改)。这样作者排序(`creator_candidate`)、字形变体、代表作选集、事实提取的语义全部沿用,等价风险只落在「转换」这一层;现有基于行的语义测试改为直接测解析函数而保留。转换层按 SPARQL 的形状造行:年份去掉前导 `+`(旧解析的 `[:4]` 因此得到同样结果)、无英文名的值填原始 QID(旧解析的 `_is_raw_qid` 照旧过滤)、作者语句按 `(artist, rank, cert)` 归组相加引用数(§3.1)。

唯一的签名变化:用于依赖注入的关键字参数 `run_query`(收 SPARQL、回行绑定)改名为 `get_entities`(形状见 2.1)。调用方须同步改:`pipeline.py` 给 `fetch_rich_facts` 的离线开关、`test_material.py` / 流水线等测试的注入。

| 函数(material.py / evidence.py) | 取什么 | Action API 实现 |
|---|---|---|
| `fetch_wikidata_labels(qid, langs)` | 实体标签 | `get_entities([qid], props="labels", languages=_query_langs(langs))` → 原始 `{lang: value}` → 原 `_collapse_variants` |
| `resolve_creator_qid(qid)` | 唯一作者 | `props="claims"` 取 P170 语句;每条语句造与 SPARQL 行同形的候选 → 原 `creator_candidate` 排序规则(见 §3.1) |
| `fetch_artist_material(qid, registry, country_lang, artist_qid)` | 作者维基条目名 | 作者实体 `props="sitelinks"` → `enwiki` / `{cl}wiki` 的 `title`;其后 Wikipedia 抓正文不变 |
| `fetch_artist_facts(qid, artist_qid)` | 生卒/国籍/代表作(英文) | 作者实体 `props="claims"` 取 P569/P570/P27/P800 的主值;P27/P800 的值实体再一次 `props="labels", languages="en"` 批量取名 |
| `fetch_artist_i18n_facts(artist_qid, langs)` | 国籍/代表作多语名 | 同上取 P27/P800 主值,值实体批量取 `wanted` 语言标签;其余(先选作品集合再逐语言取名、字形转换)原样 |
| `fetch_rich_facts(qid)` | 证据包 10 项 | 作品实体 `props="claims"` 取 `_RICH_PROPS` 的主值;值实体批量取 en 标签;每 pid ≤ 5 条、无英文名跳过不变 |

「值实体取名」只对 `datavalue.type == "wikibase-entityid"` 的值做;非实体值(这几项属性理论上不会出现)直接跳过,与旧实现 label 服务的结果一致。

`artist_qid` 为空时:`fetch_artist_material` / `fetch_artist_facts` 返回 `{}`,**不再走「作品→P170 遍历」**。
流水线总是先 `resolve_creator_qid`;它返回空 = 无作者或故意弃权(§3.1),遍历只会绕过这个判断(这正是 §4 假作者卡的来源)。

## 3. 必须原样保留的语义

### 3.1 作者解析(`creator_candidate` 规则不改,只换输入来源)
- 每条 P170 语句 → 候选 `(rank 序, 不确定性序, -引用数, QID 数字)`,取最小。
- rank:preferred=0、normal=1、deprecated → 排除。
- 不确定性:P1480 限定词无=0、presumably(Q18122778)=1、possibly(Q30230067)=3、其它=2;一条语句多个 P1480 → 每个各成一候选(同 SPARQL 每行)。
- 引用数:该语句 `references` 条数。旧 SPARQL 中 `OPTIONAL pq:P1480` 与 `OPTIONAL prov:wasDerivedFrom` 在同一语句上交叉相乘,再按 `(artist, rank, cert)` 分组 `COUNT(?ref)`——于是**同一作者、同 rank、同 cert 的多条语句合并成一个候选,引用数相加**(如两条重复语句各 2、3 条引用 → 一个候选 refs=5,而不是两个候选)。新实现必须先按 `(artist, rank, cert)` 归组、组内引用数相加,再造候选。这是排序里最容易做错的一处(Q64309678 那类多作者事故就出在这条规则上),§5 与 §6 各有专门样本/夹具。
- P1480 限定词本身是「未知值」:旧 SPARQL 绑定 blank node → `creator_candidate` 视为未知限定词(=2);转换层用一个非 QID 的占位值保持同样结果。限定词「无值」:SPARQL `pq:` 不绑定 → 等同无限定;转换层跳过。
- `snaktype` 为 `somevalue`(未知值)/ `novalue` → 不产候选(旧实现靠 `is_wikidata_qid` 拦 blank node,结果相同)。

### 3.2 「主值」= SPARQL `wdt:` 的 rank 规则 + 额外排除未知值(故意收紧)
对一个属性:排除 deprecated;若有 preferred 则只取 preferred,否则取 normal——这部分与 `wdt:` 完全一致。
**另外**只取 `snaktype=value`:`wdt:` 其实会把「未知值」作为 blank node 返回(这正是 §4.2 存成 `http` 的来源),所以这一条**不是**对 `wdt:` 的忠实翻译,而是修 bug 的收紧;等价验证里因此出现的差异归入「旧 bug 被修」。
**并列时取哪个**:同一 rank 有多条(如拉斐尔 Q5597 有两条 preferred 的出生日期),单值字段(生年/卒年/国籍)取 Wikidata 语句数组中的**第一条**;旧实现取 SPARQL 返回的第一行(顺序不保证),两者可能不同,验证时归入「仅顺序不同」,但要逐条列出是否影响了**年份**。
作者事实、多语事实、证据包都用这个规则。

### 3.3 其它
- `mul` 标签(「适用多语言」伪语言):旧 `FILTER(lang IN …)` 与新 `languages=` 都不含 `mul`,两边同样不回退,等价(10-10 实测)。
- 年份:`time` 去掉前导 `+` 后取前 4 位(旧实现对 SPARQL 的 `1748-01-01T…` 取 `[:4]`,两者结果相同;公元前日期两边一样截出 `-050` 这类值,不在本次范围)。
- 无英文名的值:旧实现(label 服务退回原始 QID 再过滤)= 跳过;新实现 en 标签缺失 = 跳过。
- 字形变体(zh-hans > zh-cn > zh;繁体链;港式垫底)、`_collapse_variants`、代表作「先选同一批作品再逐语言取名、按被标注语言数排序」——原代码不动,只换数据来源。
- 多值属性的**顺序**:旧 SPARQL 行序不保证(多国籍时取哪个是碰运气);新实现按 Wikidata 语句顺序,确定可复现。验证时归为「顺序差异」(§5)。

### 3.4 评审建议未采纳:合并同一作品实体的两次取语句
作者解析与证据包都读作品实体的 claims,可合并成一次请求(评审 M1)。不采纳:两次请求并发、每次 ~0.5s,按 §7 估算即使两件同时生成也在看图耗时之内;合并需要在流水线里引入共享取数,改动面大于收益。若 §7 并发实测超标再做。

### 3.5 非 Wikidata 编号(Joconde 合成 id 等)
旧实现对 `joconde-…` 发 SPARQL 会语法错误 → 异常被调用方吞掉 → 无作者/无富属性。新实现在 `resolve_creator_qid`、`fetch_rich_facts` 入口用 `is_wikidata_qid` 直接返回空(不发请求),结果相同(`fetch_wikidata_labels` 本来就有这道判断)。

## 4. 顺带修复的旧 bug

1. **假作者卡**:作者为「未知值」时,`resolve_creator_qid` 正确返回空,但随后 `fetch_artist_facts` 走 P170 遍历,把 blank node
   的哈希当作者 QID 写回(`out["artist_qid"]`),流水线据此建出空作者卡。prod 现有 **61 件作品**(卢浮宫 59 / 小皇宫 2,均 ready)
   挂着 32 位哈希作者 QID 和对应的 61 张空作者卡。新实现不再遍历(§2.2),从源头堵住。
   **存量清理不在本设计**:属 prod 写操作,记待办,按纪律 37 单独列写入面报用户确认。
2. **「未知值」日期**:同一机制下生卒年会被存成 `http`(blank node URL 的前 4 位)。prod 目前 0 条;新实现按 §3.2 只取 `snaktype=value`,一并堵住。
3. **作者维基条目名含 `/` 被截断**:旧实现对条目名做 `rsplit("/")`(把它当 URL 处理),含 `/` 的条目名只剩最后一段,抓不到正文。新实现直接用 sitelinks 的完整 `title`。等价验证中归入「旧 bug 被修」。

## 5. 等价验证(切换的硬门槛)

脚本 `backend/scripts/verify_wikidata_api_parity.py`(只读,不写库):对样本逐件分别调旧 SPARQL 实现(保留在脚本内作参照)与新实现,逐字段比对。

**样本 ≈100 件**,跨 5 馆,刻意覆盖:多 P170 作者、P170 未知值、无 P170、Joconde 合成 id、证据包满的名作、无中文标签、有繁体/港式标签、作者有多国籍/多代表作,以及:
- **同一作者两条以上 P170 语句、同 rank、同 cert**(检验引用数归组相加,§3.1);
- **作者的生年或卒年有 ≥2 条并列主值**(如 Q5597,检验 §3.2 并列规则对年份的影响);
- **作者自己的生卒年在 Wikidata 是「未知值」**(检验 §4.2 修复;区别于「作品的作者未知」那一类);
- 本地 prod 那 61 件哈希作者 QID 的作品(检验 §4.1:新实现不再产出作者)。
若真实数据里找不到某类,用 WDQS 搜出符合条件的 Wikidata 实体补进样本,并在结果里注明。

**每处差异必须归类**:
- 完全一致;
- 仅顺序不同(多值集合相等);
- 旧 bug 被修(§4);
- WDQS 滞后(SPARQL 副本落后于实时数据,复查 Wikidata 页面确认新值为当前值);
- **无法解释:必须 0 件,否则不切换。**

验证结果写进 PR 描述(各类计数 + 每条非「完全一致」的明细)。

## 6. 测试

- `wikidata_api`:批量切分(>50)、429 带 Retry-After 重试后成功、**HTTP 200 + `error.code=maxlag` 重试、200 + 其它 error 抛出、200 但无 `entities` 抛出**、3 次失败抛出、信号量同时在途 ≤ 2。
- 六个函数各用**真实形状的 entity JSON 夹具**(从 Wikidata 实取后裁剪,不手编)测:主值规则(preferred 压 normal、deprecated 排除)、
  未知值不产候选/不产日期、多 P1480、**同作者同 rank 同 cert 两条语句(引用数 2 与 3)合并为一个 refs=5 的候选,且该合并会改变胜者的反例**、并列主值取数组第一条、字形变体、无英文名跳过、每 pid ≤5。
- 回归:`artist_qid` 为空时作者资料/事实返回 `{}`,不再产出哈希作者。
- 现有调用方测试改为注入 `get_entities`;生成流水线全套保持绿。

## 7. 上线与复测

1. staging 合并后用 `ttfc.py` 复测 ≥3 件未生成件(含首次出现的作者):准备阶段 ≤ 6s、首屏 15–17s。
   另做**一组 2 件同时生成**(= 每进程懒生成并发上限):每件约 7 次 Action API 请求,两件 ~14 次挤 2 个名额,按 ~0.5s/次估约 3.5s,仍应低于看图(~5s);实测准备阶段 ≤ 6s 才算过。
2. 与 #881–#883 一起提 staging→main(用户合并);上 prod 前查有无长任务在跑。
3. prod 上线后看 `prep: ... failed` warning 与懒生成首屏耗时。

## 8. 改动文件

- 新增 `backend/app/services/enrichment/wikidata_api.py`
- 改 `backend/app/services/enrichment/material.py`(5 个函数)、`evidence.py`(`fetch_rich_facts`)
- 改 `backend/app/services/enrichment/pipeline.py`(离线开关由 `run_query` 换为 `get_entities`)
- 新增 `backend/scripts/verify_wikidata_api_parity.py`
- 测试:新增 `tests/unit/services/enrichment/test_wikidata_api.py`;更新 `test_material.py`、证据包与流水线相关测试
- `docs/ops/backlog.md`:加「61 件哈希作者 QID 清理」
