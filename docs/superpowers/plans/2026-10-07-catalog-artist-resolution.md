# Joconde 目录件作者 qid 解析 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让 Joconde 目录来源的馆藏件（合成 id，如 `joconde-00000089538`）在 P170 查不到创作者时，能按原始署名字符串找到对应的 Wikidata 作者实体，补全跨馆共享的作者简介；查不到/有歧义就留空，绝不猜错写坏共享实体。

**Architecture:** `generate_object` 的作者解析分支新增一级 fallback：`resolve_creator_by_name(name)`（新函数，`material.py`）按 `;`/`/`/`and`/`et` 拆分署名字符串，每段两种词序查 Wikidata `wbsearchentities`，用词集合精确匹配过滤前缀误判，再用 `wbgetentities` 批量查职业（P106）白名单过滤非艺术家候选；每段要求恰好剩一个候选才算成功，所有成功段落的 qid 必须完全一致才采信。整串若命中限定词关键词（"仿作"/"工作室作品"等）直接弃权，不进入拆分流程。入库阶段（`joconde_catalog.py`）同步收紧一个清洗正则，不再把限定词当生卒年一起删掉。

**Tech Stack:** Python 3.13 / FastAPI 后端 / pytest / Wikidata MediaWiki Action API（`wbsearchentities`、`wbgetentities`，与现有 SPARQL 查询服务是不同协议）。

**Spec:** `docs/superpowers/specs/2026-10-07-catalog-artist-resolution-design.md`（已过 Opus + Fable 两轮独立评审，并在写这份计划时用真实 Joconde 数据二次核实订正——执行者应该两份都看，这份计划是 spec 的落地步骤，不重复 spec 里"为什么这样设计"的推理）

## Global Constraints

- 歧义或查不到候选 → 返回 `None`，绝不打分选一个最像的（宁缺毋滥，纪律37：写错共享 `artists` 表的代价远高于暂时缺）。
- 新的按名解析路径只对 `not o.qid.startswith("Q")` 的件生效——不能推翻 `resolve_creator_qid` 对真实 Wikidata 作品"P170 是未知值"这种故意弃权的判断。
- 不改 DB schema、不新增字段、不需要数据库迁移。
- 职业白名单固定为这 7 个 qid（已用 `Special:EntityData` 核实 label+description）：`Q1028181`(painter)、`Q1281618`(sculptor)、`Q329439`(engraver)、`Q15296811`(draughtsman)、`Q10862983`(etcher)、`Q11569986`(printmaker)、`Q7541856`(ceramicist)。
- 限定词弃权关键词固定为这些法语词（从奥赛+橘园真实 `Auteur` 字段核对出来，不是翻译的英文术语）：`d'après`、`d'apres`、`atelier`、`entourage`、`attribué à`、`attribue a`、`attribué`、`attribue`、`attribution incertaine`、`imitation`、`inspiré par`、`inspire par`、`genre de`、`anonyme`、`anonymous`。
- 所有网络调用（Wikidata 搜索/查实体）必须可注入 mock，默认实现才打真实 API——单测离线跑，不触网。

## Review Focus

- **法语限定词的大小写/重音变体扫不到**：Joconde 原始字符串常见全大写段（如 `D'APRÈS`），关键词扫描必须先转小写再比对子串，且要兼容 `d'après`/`d'apres`（有无重音符）两种写法都在关键词表里——这个就是任务 2 的测试要钉住的。
- **多词姓氏重排只试了一种切法**：姓氏本身可能是多个词（如 `DE MACHY Pierre Antoine`，4 个词），只试"第一个词挪到末尾"这一种切法会漏掉真正该用的切法（如 `Pierre Antoine DE MACHY`，把前两个词一起挪）——任务 3 的测试要覆盖一个真正需要 n-1 种切法里非第一种才能命中的多词姓氏案例。
- **Wikidata 搜索响应里 `match` 字段结构不稳定**：不是所有候选都保证有 `match.text`（偶尔只有顶层 `label`），直接 `r["match"]["text"]` 会在缺失时抛 `KeyError` 而不是优雅跳过这个候选——任务 4 的测试要覆盖"候选没有 `match` 字段，退回用 `label` 比较"这条路径。
- **空/无效输入导致崩溃而不是返回 None**：`artist_en` 为空字符串、纯空白、或整串就是一个单独的 `;` 这种退化输入，`resolve_creator_by_name` 必须返回 `None`，不能在 `_SPLIT.split()` 或后续处理里抛异常——任务 5 的测试要覆盖这几种退化输入。
- **已有 `artist_qid` 的件被新路径意外重新解析/覆盖**：接入点的条件判断必须保证"只要 `aqid` 已经非空（不管来自 P170 还是之前 names 回填），新函数完全不会被调用"——任务 6 的测试要断言这一点，不能只测"新函数被调用时行为对不对"，还要测"该不该被调用"。

---

### Task 1: 入库清洗正则收紧——限定词不再被当生卒年删掉

**Files:**
- Modify: `backend/app/services/enrichment/sources/joconde_catalog.py:42`（`_DATES` 常量定义处）
- Test: `backend/tests/unit/services/enrichment/test_joconde_catalog.py`

**Interfaces:**
- Consumes: 无（这是叶子函数，不依赖本计划其它任务）
- Produces: `_clean_artist(raw: str | None) -> str | None`（签名不变，行为变化：只清洗生卒年形态的尾部括号，保留限定词形态的）。后续任务不直接依赖这个函数的输出，但它是"新入库的件 `artist_en` 里能看到限定词"这个前提的唯一来源。

- [ ] **Step 1: 写失败的测试**

在 `backend/tests/unit/services/enrichment/test_joconde_catalog.py` 里找到现有的 `test_cleaners`（约在文件中段，紧跟 `_clean_inv`/`_clean_title`/`_category` 的断言之后），在文件末尾新增一个独立测试函数（不要塞进 `test_cleaners`，这是新行为，给自己的测试名）：

```python
def test_clean_artist_strips_dates_but_keeps_qualifiers():
    """2026-10-07 实测奥赛+橘园真实 Auteur 字段:120 个生卒年全部是严格
    \\d{3,4}-\\d{3,4} 形态,211 个非日期内容(限定词/角色词)零例外不匹配这个
    形态——两类可以用同一条正则干净分开,不用模糊字符类。"""
    # 生卒年:应该被清洗掉(真实奥赛数据)
    assert _clean_artist("Cassatt Mary (1844-1926)") == "Cassatt Mary"
    assert _clean_artist("Renoir Pierre Auguste (1841-1919)") == "Renoir Pierre Auguste"
    # 限定词:不该被清洗掉(真实奥赛/橘园数据,旧正则会把这些也删掉)
    assert _clean_artist("Boucher François (d'après)") == "Boucher François (d'après)"
    assert _clean_artist("CLOUET François (atelier)") == "CLOUET François (atelier)"
    assert _clean_artist("Gauguin Paul (attribué à)") == "Gauguin Paul (attribué à)"
    assert _clean_artist("anonyme") == "anonyme"
    assert _clean_artist("BENJAMIN-CONSTANT (dit)") == "BENJAMIN-CONSTANT (dit)"
    # 已知局限(spec §3.1):生卒年+限定词是两个独立括号时,末尾那个是限定词,
    # 整串(包括生卒年)都不会被清洗——不影响正确性,下游的限定词扫描是子串
    # 匹配,不管前面夹着什么都能扫到"attribué à"。
    assert (
        _clean_artist("Cézanne Paul (1839-1906) (attribué à)")
        == "Cézanne Paul (1839-1906) (attribué à)"
    )
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && poetry run pytest tests/unit/services/enrichment/test_joconde_catalog.py::test_clean_artist_strips_dates_but_keeps_qualifiers -v`

Expected: FAIL——旧正则 `r"\s*\([^)]*\)\s*$"` 会把 `"Boucher François (d'après)"` 清成 `"Boucher François"`，断言不等。

- [ ] **Step 3: 改正则**

在 `backend/app/services/enrichment/sources/joconde_catalog.py` 找到：

```python
_DATES = re.compile(r"\s*\([^)]*\)\s*$")  # 作者尾部"(1844-1926)"
```

改成：

```python
# 作者尾部"(1844-1926)"——只匹配生卒年形态,不匹配"(atelier)"/"(d'après)"
# 这类限定词(2026-10-07 实测奥赛+橘园全量 Auteur 字段:两类内容零例外可以
# 用这条正则分开)。限定词要留着,resolve_creator_by_name 的弃权判断要用到。
_DATES = re.compile(r"\s*\(\d{3,4}-\d{3,4}\)\s*$")
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd backend && poetry run pytest tests/unit/services/enrichment/test_joconde_catalog.py -v`

Expected: PASS（包括新测试和原有的 `test_cleaners`——原有断言 `_clean_artist("Cassatt Mary (1844-1926)") == "Cassatt Mary"` 本来就是日期形态，新正则照样匹配，不会破坏它）。

- [ ] **Step 5: 跑全文件确认无回归**

Run: `cd backend && poetry run pytest tests/unit/services/enrichment/test_joconde_catalog.py -v`

Expected: 全部 PASS，无新增失败。

- [ ] **Step 6: Commit**

```bash
cd backend
git add app/services/enrichment/sources/joconde_catalog.py tests/unit/services/enrichment/test_joconde_catalog.py
git commit -m "fix(joconde): 清洗正则只匹配生卒年,不再连限定词一起删"
```

---

### Task 2: 限定词前置扫描——`_has_qualifier_marker`

**Files:**
- Modify: `backend/app/services/enrichment/material.py`（文件末尾新增，或靠近 `resolve_creator_qid` 附近）
- Test: `backend/tests/unit/services/enrichment/test_material.py`

**Interfaces:**
- Consumes: 无
- Produces: `_has_qualifier_marker(name: str) -> bool`——任务 5 组装 `resolve_creator_by_name` 时作为第一道弃权闸调用。

- [ ] **Step 1: 写失败的测试**

在 `backend/tests/unit/services/enrichment/test_material.py` 文件末尾新增：

```python
def test_has_qualifier_marker_detects_real_disclaimer_phrases():
    from app.services.enrichment.material import _has_qualifier_marker

    # 真实 Joconde 数据(2026-10-07 实测奥赛+橘园 Auteur 字段):这些都是
    # "这不是作者本人画的"类表述,必须命中。
    assert _has_qualifier_marker("anonyme;VAN GOGH Vincent (d'après)") is True
    assert _has_qualifier_marker("Cézanne Paul (1839-1906) (attribué à)") is True
    assert _has_qualifier_marker("Boucher François (d'après)") is True
    assert _has_qualifier_marker("CLOUET François (atelier)") is True
    assert _has_qualifier_marker("Courbet Gustave (genre de);anonyme") is True
    assert _has_qualifier_marker("anonyme") is True
    assert _has_qualifier_marker("SEGUIN Armand;Gauguin Paul (attribution incertaine)") is True
    # 大小写不敏感(Joconde 惯用全大写姓氏段落,限定词有时跟着一起大写)
    assert _has_qualifier_marker("BOUCHER FRANÇOIS (D'APRÈS)") is True
    # 别名标记(dit/née)和工匠角色词(fondeur)不是弃权信号,不该命中——
    # 这些交给拆分+解析步骤正常处理(spec §3.2 步骤0的说明)。
    assert _has_qualifier_marker("BENJAMIN-CONSTANT (dit);CONSTANT Jean Joseph Benjamin") is False
    assert _has_qualifier_marker("ALLAR André Joseph;MATIFA C (fondeur)") is False
    assert _has_qualifier_marker("BESNARD Charlotte Gabrielle;DUBRAY Charlotte Gabrielle (née)") is False
    # 正常署名,无限定词
    assert _has_qualifier_marker("SOUTINE Chaïm") is False
    assert _has_qualifier_marker("RENOIR Pierre Auguste") is False
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && poetry run pytest tests/unit/services/enrichment/test_material.py::test_has_qualifier_marker_detects_real_disclaimer_phrases -v`

Expected: FAIL with `ImportError: cannot import name '_has_qualifier_marker'`

- [ ] **Step 3: 实现**

在 `backend/app/services/enrichment/material.py` 新增（放在文件靠后位置，`resolve_creator_qid` 之后即可）：

```python
# 弃权关键词全部是法语(Auteur 字段是法语,不是英语),2026-10-07 实测奥赛
# +橘园真实 Auteur 字段逐个核对出来的"这不是作者本人画的"类表述。不包括
# dit/dite/née/patronyme(这些是别名标记,不是弃权信号)、也不包括
# fondeur/orfèvre/céramiste/éditeur/mouleur/praticien/exécutant(这些是
# 工匠角色词,交给职业过滤自然处理——铸造厂/工坊这类机构名在 Wikidata 搜
# 不出 human 候选,那一段自然解析失败,不需要在这里特殊处理)。
_QUALIFIER_MARKERS = (
    "d'après", "d'apres", "atelier", "entourage", "attribué à", "attribue a",
    "attribué", "attribue", "attribution incertaine", "imitation",
    "inspiré par", "inspire par", "genre de", "anonyme", "anonymous",
)  # fmt: skip


def _has_qualifier_marker(name: str) -> bool:
    """整串扫一遍限定词(仿作/工作室作品等)关键词,子串匹配、大小写不敏感。
    命中就该整体弃权,不进入拆分/按名查找流程(spec §3.2 步骤0)。"""
    low = (name or "").lower()
    return any(marker in low for marker in _QUALIFIER_MARKERS)
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd backend && poetry run pytest tests/unit/services/enrichment/test_material.py::test_has_qualifier_marker_detects_real_disclaimer_phrases -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
cd backend
git add app/services/enrichment/material.py tests/unit/services/enrichment/test_material.py
git commit -m "feat(material): 新增限定词前置扫描_has_qualifier_marker"
```

---

### Task 3: 姓名重排辅助函数——`_reorder_candidates`

**Files:**
- Modify: `backend/app/services/enrichment/material.py`
- Test: `backend/tests/unit/services/enrichment/test_material.py`

**Interfaces:**
- Consumes: 无
- Produces: `_reorder_candidates(segment: str) -> list[str]`——任务 4 的 `_segment_candidates` 会把这个函数的输出和原始字符串一起拿去查 Wikidata。

- [ ] **Step 1: 写失败的测试**

```python
def test_reorder_candidates_tries_every_split_point():
    from app.services.enrichment.material import _reorder_candidates

    # 单词姓氏:3个词,2种切法(k=1,k=2)
    assert _reorder_candidates("SOUTINE Chaïm") == ["Chaïm SOUTINE"]
    # 多词姓氏(真实橘园数据:4个词,3种切法k=1,2,3)——必须覆盖所有切法,
    # 不能只试"第一个词挪到末尾"这一种:k=1 对这个真实案例是错的切法
    # (2026-10-07 实测:"CONSTANT Jean Joseph Benjamin"真正能命中
    # Wikidata 的切法不是只移一个词,而是把 k=1 时整串重排的结果
    # "Jean Joseph Benjamin CONSTANT"——这正是下面要断言在候选列表里的那条)。
    result = _reorder_candidates("CONSTANT Jean Joseph Benjamin")
    assert "Jean Joseph Benjamin CONSTANT" in result
    assert len(result) == 3  # 4个词,n-1=3种切法
    # 单个词:没有可重排的,返回空列表
    assert _reorder_candidates("Anonyme") == []
    assert _reorder_candidates("") == []
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && poetry run pytest tests/unit/services/enrichment/test_material.py::test_reorder_candidates_tries_every_split_point -v`

Expected: FAIL with `ImportError`

- [ ] **Step 3: 实现**

```python
def _reorder_candidates(segment: str) -> list[str]:
    """姓名重排:Joconde 惯用"姓 名"顺序查 Wikidata 常年查不到(wbsearchentities
    对词序敏感),要试"名 姓"顺序。姓氏本身可能是多个词(如"DE MACHY Pierre
    Antoine"),所以试全部 n-1 种切法——把开头 k 个词(k=1..n-1)当姓氏挪到
    末尾,不是只试"第一个词 vs 剩余"这一种(spec §3.2 步骤2)。"""
    words = segment.split()
    if len(words) < 2:
        return []
    return [" ".join(words[k:] + words[:k]) for k in range(1, len(words))]
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd backend && poetry run pytest tests/unit/services/enrichment/test_material.py::test_reorder_candidates_tries_every_split_point -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
cd backend
git add app/services/enrichment/material.py tests/unit/services/enrichment/test_material.py
git commit -m "feat(material): 新增姓名重排辅助函数_reorder_candidates"
```

---

### Task 4: Wikidata 搜索 + 词集合精确匹配——`_segment_candidates`

**Files:**
- Modify: `backend/app/services/enrichment/material.py`
- Test: `backend/tests/unit/services/enrichment/test_material.py`

**Interfaces:**
- Consumes: `_reorder_candidates(segment: str) -> list[str]`（任务 3）；`app.services.matching.normalize.normalize(s: str) -> str` 和 `tokens(s: str) -> list[str]`（已存在）
- Produces: `_segment_candidates(segment: str, *, search_entities, word_set: frozenset) -> list[str]`（任务 5 组装主函数时调用）；`_default_search_entities(text: str, *, limit: int = 5) -> list[dict]`（默认实现，生产环境真实调用，任务 5 的主函数把它当默认值用）

- [ ] **Step 1: 写失败的测试**

```python
def test_segment_candidates_filters_by_exact_word_match():
    from app.services.enrichment.material import _segment_candidates
    from app.services.matching.normalize import normalize, tokens

    # 真实案例(2026-10-07 实测):"LEON Paul"会前缀匹配到 Léon-Paul Fargue
    # (法国诗人),match.text 是"Léon-Paul Fargue",归一化后的词集合是
    # {leon, paul, fargue},和输入词集合 {leon, paul} 不相等——必须被滤掉。
    def fake_search(text, *, limit=5):
        return [
            {"id": "Q599801", "label": "Léon-Paul Fargue",
             "match": {"type": "label", "text": "Léon-Paul Fargue"}},
        ]

    word_set = frozenset(tokens(normalize("LEON Paul")))
    assert _segment_candidates("LEON Paul", search_entities=fake_search, word_set=word_set) == []

    # 词集合精确相等的候选要保留
    def fake_search_exact(text, *, limit=5):
        return [
            {"id": "Q160141", "label": "Chaïm Soutine",
             "match": {"type": "label", "text": "Chaïm Soutine"}},
        ]

    word_set2 = frozenset(tokens(normalize("Chaïm Soutine")))
    assert _segment_candidates(
        "SOUTINE Chaïm", search_entities=fake_search_exact, word_set=word_set2
    ) == ["Q160141"]

    # match 字段缺失时退回用 label 比较,不能抛异常(Review Focus 第3条)
    def fake_search_no_match(text, *, limit=5):
        return [{"id": "Q1", "label": "Chaïm Soutine"}]

    assert _segment_candidates(
        "SOUTINE Chaïm", search_entities=fake_search_no_match, word_set=word_set2
    ) == ["Q1"]

    # 原始顺序+重排都会被尝试,两次查询结果去重合并——注意重排只调换词的
    # 位置,不改每个词自身的大小写(_reorder_candidates 的实现就是这样),
    # 所以"SOUTINE Chaïm"重排后是"Chaïm SOUTINE"(SOUTINE 仍大写),不是
    # "Chaïm Soutine"(这个大小写写法实测跑过一遍脚本才发现:写成后者会让
    # 两次查询的 text 都对不上,fake 函数永远返回空,测试会静默测不出东西
    # 而不是报错——写 fake 查询函数时务必核对 _reorder_candidates 真实
    # 产出的字符串,不要凭感觉拼大小写)。
    calls = []

    def fake_search_both_orders(text, *, limit=5):
        calls.append(text)
        if text == "Chaïm SOUTINE":
            return [{"id": "Q160141", "label": "Chaïm Soutine",
                      "match": {"text": "Chaïm Soutine"}}]
        return []

    result = _segment_candidates(
        "SOUTINE Chaïm", search_entities=fake_search_both_orders, word_set=word_set2
    )
    assert result == ["Q160141"]
    assert "SOUTINE Chaïm" in calls  # 原始顺序查过
    assert "Chaïm SOUTINE" in calls  # 重排后也查过(注意大小写:SOUTINE 仍大写)
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && poetry run pytest tests/unit/services/enrichment/test_material.py::test_segment_candidates_filters_by_exact_word_match -v`

Expected: FAIL with `ImportError`

- [ ] **Step 3: 实现**

在 `material.py` 顶部确认/新增 import（如果文件里还没有）：

```python
from app.services.matching.normalize import normalize, tokens
```

新增函数：

```python
_SEARCH_LIMIT = 5


def _default_search_entities(text, *, limit=_SEARCH_LIMIT):
    """真实打 Wikidata wbsearchentities(与 material.py 其它函数用的 SPARQL
    查询服务是不同的 API,这里是 MediaWiki Action API)。"""
    import requests

    r = requests.get(
        "https://www.wikidata.org/w/api.php",
        params={
            "action": "wbsearchentities",
            "search": text,
            "language": "en",
            "format": "json",
            "limit": limit,
        },
        headers={"User-Agent": _wd.USER_AGENT},
        timeout=30,
    )
    r.raise_for_status()
    return r.json().get("search", [])


def _segment_candidates(segment: str, *, search_entities, word_set: frozenset) -> list[str]:
    """一段署名 -> 两种词序查询后、词集合精确匹配过的候选 qid 列表(未去重
    按发现顺序、未过滤职业)。词集合精确匹配堵的是 wbsearchentities 的前缀
    匹配误判(如"LEON Paul"匹配到诗人 Léon-Paul Fargue,见 spec §3.2 步骤2)。"""
    seen: list[str] = []
    for query in [segment, *_reorder_candidates(segment)]:
        for r in search_entities(query, limit=_SEARCH_LIMIT):
            match_text = (r.get("match") or {}).get("text") or r.get("label") or ""
            if frozenset(tokens(normalize(match_text))) != word_set:
                continue
            qid = r.get("id")
            if qid and qid not in seen:
                seen.append(qid)
    return seen
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd backend && poetry run pytest tests/unit/services/enrichment/test_material.py::test_segment_candidates_filters_by_exact_word_match -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
cd backend
git add app/services/enrichment/material.py tests/unit/services/enrichment/test_material.py
git commit -m "feat(material): 新增Wikidata搜索+词集合精确匹配_segment_candidates"
```

---

### Task 5: 职业过滤 + 组装主函数——`resolve_creator_by_name`

**Files:**
- Modify: `backend/app/services/enrichment/material.py`
- Test: `backend/tests/unit/services/enrichment/test_material.py`

**Interfaces:**
- Consumes: `_has_qualifier_marker`（任务2）、`_segment_candidates`、`_default_search_entities`（任务4）、`app.services.matching.people._SPLIT`（已存在）
- Produces: `resolve_creator_by_name(name: str | None, *, search_entities=None, get_claims=None) -> str | None`——任务 6 在 `pipeline.py` 里调用这个函数（通过薄包装 `_resolve_creator_by_name`）。

- [ ] **Step 1: 写失败的测试（正样本）**

```python
def test_resolve_creator_by_name_real_unambiguous_artists():
    """2026-10-07 橘园 TOP50 内容复核手工核实过的 7 个真实作者,mock HTTP
    响应固定,离线跑,必须原样复现这 7 个 qid。

    ⚠️ `match.text` 必须填**真实会返回的那个字符串**,不能图省事填 Wikidata
    的 canonical label——写这份计划时实测过 Modigliani 这一条,拿 canonical
    label "Amedeo Modigliani" 当 match.text 会让词集合精确匹配(spec §3.2
    步骤2)errors误判失败(因为 Joconde 原串拼的是"Amadeo",跟"Amedeo"差一个
    字母),而真实 Wikidata 搜索返回的 match.text 是**别名**"Amadeo
    Modigliani"(与 Joconde 原串完全一致),所以 Modigliani 这一条的
    match_text 和前面几条的 label 不一样,是故意的,不是打错字。"""
    from app.services.enrichment.material import resolve_creator_by_name

    def make_search(qid, match_text):
        def _search(text, *, limit=5):
            return [{"id": qid, "label": match_text, "match": {"text": match_text}}]
        return _search

    def make_claims(qid):
        def _claims(qids):
            return {qid: {"claims": {
                "P31": [{"mainsnak": {"datavalue": {"value": {"id": "Q5"}}}}],
                "P106": [{"mainsnak": {"datavalue": {"value": {"id": "Q1028181"}}}}],
            }}}
        return _claims

    cases = [
        ("Renoir Pierre Auguste", "Q39931", "Pierre-Auguste Renoir"),
        ("SOUTINE Chaïm", "Q160141", "Chaïm Soutine"),
        ("DERAIN André", "Q156272", "André Derain"),
        ("UTRILLO Maurice", "Q108301", "Maurice Utrillo"),
        ("Matisse Henri", "Q5589", "Henri Matisse"),
        ("ROUSSEAU Henri;LE DOUANIER ROUSSEAU", "Q156386", "Henri Rousseau"),
        # match_text 是别名"Amadeo Modigliani",不是 canonical label——见上面的说明
        ("Modigliani Amadeo", "Q120993", "Amadeo Modigliani"),
    ]
    for raw_name, expected_qid, match_text in cases:
        got = resolve_creator_by_name(
            raw_name,
            search_entities=make_search(expected_qid, match_text),
            get_claims=make_claims(expected_qid),
        )
        assert got == expected_qid, f"{raw_name!r} 应该解析成 {expected_qid},实际是 {got!r}"
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && poetry run pytest tests/unit/services/enrichment/test_material.py::test_resolve_creator_by_name_real_unambiguous_artists -v`

Expected: FAIL with `ImportError`

- [ ] **Step 3: 实现（先写出主函数骨架，让正样本能过）**

```python
from app.services.matching.people import _SPLIT

_OCCUPATION_WHITELIST = {
    "Q1028181",  # painter
    "Q1281618",  # sculptor
    "Q329439",   # engraver
    "Q15296811", # draughtsman
    "Q10862983", # etcher
    "Q11569986", # printmaker
    "Q7541856",  # ceramicist
}  # fmt: skip


def _default_get_claims(qids):
    """真实打 Wikidata wbgetentities,批量查 P31/P106——一次请求查完一段
    两种词序凑出来的全部候选,不逐个候选单独查(spec §3.2 步骤3)。"""
    import requests

    if not qids:
        return {}
    r = requests.get(
        "https://www.wikidata.org/w/api.php",
        params={
            "action": "wbgetentities",
            "ids": "|".join(qids),
            "props": "claims",
            "format": "json",
        },
        headers={"User-Agent": _wd.USER_AGENT},
        timeout=30,
    )
    r.raise_for_status()
    return r.json().get("entities", {})


def _claim_ids(entity: dict, prop: str) -> set[str]:
    out = set()
    for c in (entity.get("claims") or {}).get(prop, []):
        v = (c.get("mainsnak") or {}).get("datavalue", {}).get("value")
        if isinstance(v, dict) and v.get("id"):
            out.add(v["id"])
    return out


def resolve_creator_by_name(
    name: str | None,
    *,
    search_entities=None,
    get_claims=None,
) -> str | None:
    """按原始署名字符串找 Wikidata 作者实体——P170 查不到创作者时的第二
    梯队(spec §3.2)。纯函数,网络调用可注入 mock,离线可测。

    歧义/查不到候选 -> None,不打分硬选(纪律37:写错共享 artists 表的
    代价远高于暂时缺,宁缺毋滥)。"""
    if not name or not name.strip() or _has_qualifier_marker(name):
        return None
    search_entities = search_entities or _default_search_entities
    get_claims = get_claims or _default_get_claims

    segments = [s.strip() for s in _SPLIT.split(name) if s.strip()]
    if not segments:
        return None

    segment_candidates: dict[str, list[str]] = {}
    all_candidates: set[str] = set()
    for seg in segments:
        word_set = frozenset(tokens(normalize(seg)))
        cands = _segment_candidates(seg, search_entities=search_entities, word_set=word_set)
        segment_candidates[seg] = cands
        all_candidates.update(cands)

    if not all_candidates:
        return None

    claims = get_claims(sorted(all_candidates))
    artists = {
        qid
        for qid, ent in claims.items()
        if "Q5" in _claim_ids(ent, "P31")
        and _claim_ids(ent, "P106") & _OCCUPATION_WHITELIST
    }

    resolved: set[str] = set()
    for cands in segment_candidates.values():
        survivors = [c for c in cands if c in artists]
        if len(survivors) == 1:
            resolved.add(survivors[0])

    return next(iter(resolved)) if len(resolved) == 1 else None
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd backend && poetry run pytest tests/unit/services/enrichment/test_material.py::test_resolve_creator_by_name_real_unambiguous_artists -v`

Expected: PASS

- [ ] **Step 5: 写反例测试（必须弃权）**

```python
def test_resolve_creator_by_name_abstains_on_known_ambiguous_cases():
    from app.services.enrichment.material import resolve_creator_by_name

    # 真实限定词案例:整串命中"d'après"直接弃权,不会拆分后把
    # "VAN GOGH Vincent"单独解析成功再误采信(真实 Joconde 署名)。
    def search_should_not_be_called(text, *, limit=5):
        raise AssertionError(f"限定词弃权应该在拆分前拦住,不该查询 {text!r}")

    assert resolve_creator_by_name(
        "anonyme;VAN GOGH Vincent (d'après)",
        search_entities=search_should_not_be_called,
    ) is None

    # Cézanne 父子同名同职业撞车:职业过滤后剩两个人,必须弃权。
    def search_cezanne(text, *, limit=5):
        return [
            {"id": "Q35548", "label": "Paul Cézanne", "match": {"text": "Paul Cézanne"}},
            {"id": "Q17277915", "label": "Paul Cézanne", "match": {"text": "Paul Cézanne"}},
        ]

    def claims_both_painters(qids):
        return {
            qid: {"claims": {
                "P31": [{"mainsnak": {"datavalue": {"value": {"id": "Q5"}}}}],
                "P106": [{"mainsnak": {"datavalue": {"value": {"id": "Q1028181"}}}}],
            }}
            for qid in qids
        }

    assert resolve_creator_by_name(
        "Cézanne Paul", search_entities=search_cezanne, get_claims=claims_both_painters
    ) is None

    # 空/退化输入不能崩,必须返回 None(Review Focus 第4条)
    assert resolve_creator_by_name(None) is None
    assert resolve_creator_by_name("") is None
    assert resolve_creator_by_name("   ") is None
    assert resolve_creator_by_name(";") is None
```

- [ ] **Step 6: 跑测试确认通过（不需要改实现——这一步是确认骨架已经对了）**

Run: `cd backend && poetry run pytest tests/unit/services/enrichment/test_material.py::test_resolve_creator_by_name_abstains_on_known_ambiguous_cases -v`

Expected: PASS。如果 FAIL，回头检查 Step 3 的实现（最可能的问题：`_has_qualifier_marker` 调用漏了，或者职业过滤的集合运算写反）。

- [ ] **Step 7: 写真实多段署名正样本测试（验证跨段裁决）**

```python
def test_resolve_creator_by_name_handles_real_multi_segment_signature():
    """真实奥赛署名"BENJAMIN-CONSTANT (dit);CONSTANT Jean Joseph Benjamin"
    (画家 Jean-Joseph Benjamin-Constant 的艺名+本名两段)。第一段带着
    "(dit)"文本直接查,搜不到任何候选(0 个);第二段重排后能命中。跨段裁决:
    一段失败(忽略)+一段成功 -> 集合大小为1 -> 采信。"""
    from app.services.enrichment.material import resolve_creator_by_name

    def search(text, *, limit=5):
        if text == "Jean Joseph Benjamin CONSTANT":
            return [{"id": "Q968357", "label": "Jean-Joseph Benjamin-Constant",
                      "match": {"text": "Jean-Joseph Benjamin-Constant"}}]
        return []  # 其它查询(含"BENJAMIN-CONSTANT (dit)"原串)都搜不到

    def claims(qids):
        return {
            qid: {"claims": {
                "P31": [{"mainsnak": {"datavalue": {"value": {"id": "Q5"}}}}],
                "P106": [{"mainsnak": {"datavalue": {"value": {"id": "Q1028181"}}}}],
            }}
            for qid in qids
        }

    got = resolve_creator_by_name(
        "BENJAMIN-CONSTANT (dit);CONSTANT Jean Joseph Benjamin",
        search_entities=search,
        get_claims=claims,
    )
    assert got == "Q968357"
```

- [ ] **Step 8: 跑测试确认通过**

Run: `cd backend && poetry run pytest tests/unit/services/enrichment/test_material.py::test_resolve_creator_by_name_handles_real_multi_segment_signature -v`

Expected: PASS。如果 FAIL 且原因是"Jean Joseph Benjamin CONSTANT"没出现在 `_reorder_candidates("CONSTANT Jean Joseph Benjamin")` 的结果里，回头检查任务 3 的实现是不是真的试了全部切法。

- [ ] **Step 9: 跑这个文件全部测试，确认不回归**

Run: `cd backend && poetry run pytest tests/unit/services/enrichment/test_material.py -v`

Expected: 全部 PASS。

- [ ] **Step 10: Commit**

```bash
cd backend
git add app/services/enrichment/material.py tests/unit/services/enrichment/test_material.py
git commit -m "feat(material): 新增resolve_creator_by_name,P170查不到时按署名找作者"
```

---

### Task 6: 接入 `generate_object` 的作者解析分支

**Files:**
- Modify: `backend/app/services/enrichment/pipeline.py:33`（`_artist_facts` 之后新增薄包装）、`:195`（作者解析分支起点）、`:222-224`（`artist_qid` 最终写回点）
- Test: `backend/tests/integration/test_generate_pipeline.py`

**Interfaces:**
- Consumes: `resolve_creator_by_name(name, *, search_entities=None, get_claims=None)`（任务5）
- Produces: `_resolve_creator_by_name(name)` 薄包装；`generate_object` 内 `aqid` 解析逻辑新增一级 fallback，且成功时在 `o.attributes` 写入 `artist_qid_source = "name_search"`。这是本功能最终对外可见的集成点，后续没有任务依赖它的内部实现。

- [ ] **Step 1: 写失败的集成测试**

**先读这几行再写测试，否则会写出"假通过"的测试**：作者解析整段代码（我们要改的那块）包在 `if registry is not None:` 里面（`pipeline.py:171`）。这个文件里已有 15 个现成测试通过 `registry=_FakeRegistry()`（文件里已定义，约第 481 行）触发这个分支，并且都额外 `monkeypatch.setattr(pl, "_wikidata_labels", lambda qid, langs: {})`（这个函数不受自动生效的 `_offline_artist_i18n` fixture 保护，不手动打桩会在沙箱里真的发一次网络请求再被 try/except 吞掉，拖慢测试）。**三个新测试都必须传 `registry=_FakeRegistry()` 并打这个桩**——不传的话 `if registry is not None:` 整段（包括我们新加的 fallback）根本不会执行，测试会在"什么都没做"的情况下通过，测不出任何东西。

在 `backend/tests/integration/test_generate_pipeline.py` 文件末尾新增（`_FakeRegistry`/`_FakeEnricher`/`_FakeGate`/`_FakeTranslator`/`MuseumObject`/`upsert_object` 都已经在文件顶部定义过，不用重新 import）：

```python
def test_generate_object_falls_back_to_name_search_for_joconde_ids(session, monkeypatch):
    """P170 查不到(_resolve_creator 打桩成返回 None)、且 qid 不是 Wikidata
    格式时,应该再按 artist_en 试一次按名解析;成功就写 artist_qid 和
    artist_qid_source,且不影响已有的 guide/facts 等内容生成流程。"""
    import app.services.enrichment.pipeline as pl
    from app.services.object_importer import upsert_object
    from app.models.museum import Museum

    monkeypatch.setattr(pl, "_resolve_creator", lambda qid: None)
    monkeypatch.setattr(pl, "_wikidata_labels", lambda qid, langs: {})
    monkeypatch.setattr(
        pl, "_resolve_creator_by_name", lambda name: "Q160141" if name == "SOUTINE Chaïm" else None
    )

    m = session.query(Museum).filter_by(slug="orsay").one()
    upsert_object(
        session, m.id,
        {
            "qid": "joconde-00000089538",
            "title_en": "Les maisons",
            "artist_en": "SOUTINE Chaïm",
            "category": "painting",
            "attributes": {},
        },
    )
    session.commit()

    from app.services.enrichment.pipeline import generate_object

    generate_object(
        session, "joconde-00000089538",
        enricher=_FakeEnricher(), gate=_FakeGate(), translator=_FakeTranslator(),
        target_langs=["en"], model="gpt-4o-mini",
        registry=_FakeRegistry(),
    )

    obj = session.query(MuseumObject).filter_by(qid="joconde-00000089538").one()
    assert obj.attributes.get("artist_qid") == "Q160141"
    assert obj.attributes.get("artist_qid_source") == "name_search"


def test_generate_object_does_not_call_name_search_when_aqid_already_known(session, monkeypatch):
    """已经有 artist_qid(不管来自 P170 还是之前 names 回填)时,新的按名
    解析完全不该被调用——省 HTTP 调用,也避免意外覆盖(Review Focus 第5条)。"""
    import app.services.enrichment.pipeline as pl
    from app.services.object_importer import upsert_object
    from app.models.museum import Museum

    def _should_not_be_called(name):
        raise AssertionError("artist_qid 已知时不该调用按名解析")

    monkeypatch.setattr(pl, "_resolve_creator", lambda qid: None)
    monkeypatch.setattr(pl, "_wikidata_labels", lambda qid, langs: {})
    monkeypatch.setattr(pl, "_resolve_creator_by_name", _should_not_be_called)

    m = session.query(Museum).filter_by(slug="orsay").one()
    upsert_object(
        session, m.id,
        {
            "qid": "joconde-00000099999",
            "title_en": "Already resolved",
            "artist_en": "RENOIR Pierre Auguste",
            "category": "painting",
            "attributes": {"artist_qid": "Q39931"},
        },
    )
    session.commit()

    from app.services.enrichment.pipeline import generate_object

    generate_object(
        session, "joconde-00000099999",
        enricher=_FakeEnricher(), gate=_FakeGate(), translator=_FakeTranslator(),
        target_langs=["en"], model="gpt-4o-mini",
        registry=_FakeRegistry(),
    )
    # 没抛 AssertionError 就说明按名解析确实没被调用
    obj = session.query(MuseumObject).filter_by(qid="joconde-00000099999").one()
    assert obj.attributes.get("artist_qid") == "Q39931"  # 原值没被覆盖


def test_generate_object_does_not_call_name_search_for_wikidata_qid(session, monkeypatch):
    """真实 Wikidata 件(Q 开头)、P170 故意弃权(_resolve_creator 返回 None)
    时,不该落到按名解析这条路——那是 Joconde 合成 id 才该走的(spec §3.3)。"""
    import app.services.enrichment.pipeline as pl
    from app.services.object_importer import upsert_object
    from app.models.museum import Museum

    def _should_not_be_called(name):
        raise AssertionError("Wikidata qid 的件不该走按名解析")

    monkeypatch.setattr(pl, "_resolve_creator", lambda qid: None)
    monkeypatch.setattr(pl, "_wikidata_labels", lambda qid, langs: {})
    monkeypatch.setattr(pl, "_resolve_creator_by_name", _should_not_be_called)

    m = session.query(Museum).filter_by(slug="orsay").one()
    upsert_object(
        session, m.id,
        {
            "qid": "Q99999999",
            "title_en": "Wikidata object, unknown creator",
            "artist_en": "Some Name",
            "category": "painting",
            "attributes": {},
        },
    )
    session.commit()

    from app.services.enrichment.pipeline import generate_object

    generate_object(
        session, "Q99999999",
        enricher=_FakeEnricher(), gate=_FakeGate(), translator=_FakeTranslator(),
        target_langs=["en"], model="gpt-4o-mini",
        registry=_FakeRegistry(),
    )
    obj = session.query(MuseumObject).filter_by(qid="Q99999999").one()
    assert obj.attributes.get("artist_qid") is None  # P170 的弃权判断没被推翻
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && poetry run pytest tests/integration/test_generate_pipeline.py::test_generate_object_falls_back_to_name_search_for_joconde_ids tests/integration/test_generate_pipeline.py::test_generate_object_does_not_call_name_search_when_aqid_already_known tests/integration/test_generate_pipeline.py::test_generate_object_does_not_call_name_search_for_wikidata_qid -v`

Expected: 第一个测试 FAIL（`AttributeError: module 'pipeline' has no attribute '_resolve_creator_by_name'`，因为还没定义）；另外两个因为同样原因在 `monkeypatch.setattr` 那一步就 FAIL。

- [ ] **Step 3: 实现**

在 `backend/app/services/enrichment/pipeline.py` 顶部薄包装函数区（`_artist_facts` 定义之后）新增：

```python
def _resolve_creator_by_name(name):
    """薄包装:P170 查不到时按原始署名字符串找作者(测试 monkeypatch 此处
    避免触网)。"""
    from app.services.enrichment.material import resolve_creator_by_name

    return resolve_creator_by_name(name)
```

找到作者解析分支（第 195 行起）：

```python
        try:
            aqid = (o.attributes or {}).get("artist_qid") or _resolve_creator(o.qid)
        except Exception:
            aqid = (o.attributes or {}).get("artist_qid")
```

改成：

```python
        try:
            aqid = (o.attributes or {}).get("artist_qid") or _resolve_creator(o.qid)
        except Exception:
            aqid = (o.attributes or {}).get("artist_qid")

        # P170 这条路查不到 qid,且不是真 Wikidata 作品(joconde-* 合成 id)
        # 才试第二梯队——不能推翻 resolve_creator_qid 对"Wikidata 作品但
        # P170 是未知值"这种故意弃权的判断(spec §3.3)。
        from_name_search = False
        if not aqid and o.artist_en and not o.qid.startswith("Q"):
            try:
                aqid = _resolve_creator_by_name(o.artist_en)
                from_name_search = bool(aqid)
            except Exception:
                aqid = None
```

然后找到这段函数末尾、真正把 `artist_qid` 写回 `o.attributes` 的那一行（第 222-224 行）：

```python
        aqid = (af or {}).get("artist_qid")
        if aqid:
            o.attributes = {**(o.attributes or {}), "artist_qid": aqid}
            db.flush()
```

改成：

```python
        aqid = (af or {}).get("artist_qid")
        if aqid:
            attrs = {**(o.attributes or {}), "artist_qid": aqid}
            if from_name_search:
                # 留痕:区分开 P170 路径解析出来的 qid,万一后续发现某类
                # 输入系统性解析错,能一条 SQL 把受影响的件找出来(spec §3.4)。
                attrs["artist_qid_source"] = "name_search"
            o.attributes = attrs
            db.flush()
```

**注意**：`af`（结构化作者属性）在新的 `aqid` 解析出来之后会被重新赋值（`af = {"artist_qid": aqid, **af}`，紧跟在 `_artist_facts` 调用之后——这段已有逻辑不用动，`aqid` 的值会原样透传下去，`from_name_search` 这个新增的局部变量只在本函数（`generate_object`）作用域内，赋值点和使用点之间不会被这段已有代码清空）。

- [ ] **Step 4: 跑测试确认通过**

Run: `cd backend && poetry run pytest tests/integration/test_generate_pipeline.py::test_generate_object_falls_back_to_name_search_for_joconde_ids tests/integration/test_generate_pipeline.py::test_generate_object_does_not_call_name_search_when_aqid_already_known tests/integration/test_generate_pipeline.py::test_generate_object_does_not_call_name_search_for_wikidata_qid -v`

Expected: 全部 PASS。

- [ ] **Step 5: 跑 `test_generate_pipeline.py` 全文件确认不回归**

Run: `cd backend && poetry run pytest tests/integration/test_generate_pipeline.py -v`

Expected: 全部 PASS（包括本计划 Task 1 之前就存在的、2026-10-07 为 `has_image_clause` 加的那批测试——那次改动和这次不冲突）。

- [ ] **Step 6: Commit**

```bash
cd backend
git add app/services/enrichment/pipeline.py tests/integration/test_generate_pipeline.py
git commit -m "feat(pipeline): P170查不到时接入按名解析,仅对非Wikidata qid生效"
```

---

### Task 7: 真实数据 dry-run 验证（奥赛全馆 + 橘园全馆）

**Files:**
- Create: `backend/scripts/dry_run_artist_name_resolution.py`（一次性运维脚本，不是产品代码，但要进仓库方便复跑/留痕——这个脚本只读不写，不碰 prod 数据）

**Interfaces:**
- Consumes: `resolve_creator_by_name`（任务5）
- Produces: 终端打印报告，不产出给后续任务消费的接口（这是本计划的最后一步，纯验证）

- [ ] **Step 1: 写脚本**

```python
"""只读 dry-run:在奥赛+橘园全馆跑一遍 resolve_creator_by_name,打印会解析
出什么,不写库。人工过一遍输出,确认没有明显张冠李戴,再决定要不要正式
跑存量回填(spec §4:存量回填本身不在这次设计范围,这个脚本只是验证新
函数在真实规模数据上的表现)。

用法(需要在能连 prod 只读副本或 prod 容器内跑,示例假设已有 DB session):
    python scripts/dry_run_artist_name_resolution.py --slug orsay
    python scripts/dry_run_artist_name_resolution.py --slug orangerie
"""

import argparse

from app.core.database import SessionLocal
from app.models.museum import Museum
from app.models.museum_object import MuseumObject
from app.services.enrichment.material import resolve_creator_by_name


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--slug", required=True)
    args = parser.parse_args()

    db = SessionLocal()
    try:
        m = db.query(Museum).filter_by(slug=args.slug).one()
        objs = (
            db.query(MuseumObject)
            .filter_by(museum_id=m.id)
            .filter(MuseumObject.artist_en.isnot(None))
            .all()
        )
        resolved = skipped_has_aqid = skipped_qid_format = abstained = 0
        for o in objs:
            attrs = o.attributes or {}
            if attrs.get("artist_qid"):
                skipped_has_aqid += 1
                continue
            if o.qid.startswith("Q"):
                skipped_qid_format += 1
                continue
            aqid = resolve_creator_by_name(o.artist_en)
            if aqid:
                resolved += 1
                print(f"RESOLVED\t{o.qid}\t{o.artist_en!r}\t-> {aqid}")
            else:
                abstained += 1
                print(f"ABSTAIN \t{o.qid}\t{o.artist_en!r}")
        print(
            f"\n--- {args.slug} 汇总 ---\n"
            f"resolved={resolved} abstained={abstained} "
            f"skipped(已有artist_qid)={skipped_has_aqid} "
            f"skipped(Wikidata qid)={skipped_qid_format}"
        )
    finally:
        db.close()


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: 本地语法/导入检查**

Run: `cd backend && poetry run python -c "import ast; ast.parse(open('scripts/dry_run_artist_name_resolution.py').read())"`

Expected: 无报错（只是语法检查，这个脚本要连真实 DB，不在这一步跑）。

- [ ] **Step 3: 在 staging 容器内跑一遍橘园**

这一步需要人工在 staging 环境执行（不是自动化测试），命令：

```bash
docker exec gomuseum_staging_backend python scripts/dry_run_artist_name_resolution.py --slug orangerie
```

Expected: 打印出的 `RESOLVED` 行里，人工抽查几条 artist_en 和解析出的 qid 对不对得上（参考 §3.5 已验证过的 7 个作者作为基准）；`ABSTAIN` 行里不该出现本应该能解析的大名家（如果出现，回头检查 `_has_qualifier_marker` 是不是误伤，或者该作者确实有真实歧义）。

- [ ] **Step 4: 在 staging 容器内跑一遍奥赛（样本量大，更能暴露边界情况）**

```bash
docker exec gomuseum_staging_backend python scripts/dry_run_artist_name_resolution.py --slug orsay
```

Expected: 同上人工抽查。奥赛 1628 件规模更大，这一步是真正检验这个函数在生产规模数据上表现的地方——如果 abstain 率异常高（比如 >50%），回头看是不是白名单漏了什么常见职业，或者关键词扫描过度敏感误伤了太多正常署名。

- [ ] **Step 5: 把人工抽查结论记录进 PR 描述**（不是代码改动，是给 reviewer 的佐证）

在最终提 PR 时，把 Step 3/4 的汇总数字（resolved/abstained/skipped）和几条抽查样例贴进 PR 描述，说明"这不只是单测绿，在真实数据规模上跑过一遍"。

- [ ] **Step 6: Commit**

```bash
cd backend
git add scripts/dry_run_artist_name_resolution.py
git commit -m "chore: 新增按名解析dry-run脚本,供真实数据抽查(只读不写)"
```
