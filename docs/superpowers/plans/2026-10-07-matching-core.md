# 匹配核心 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 用一个共用的匹配核心（词元倒排召回 + rapidfuzz 精排 + 判定）替换搜索与识别文字链各写各的匹配，并修好署名判同、补英文匹配别名。

**Architecture:** 新模块 `backend/app/services/matching/`：`normalize.py`（归一化/分词）、`people.py`（是不是同一个人）、`index.py`（在搜索全局索引条目之上建倒排，随索引后台重建）、`core.py`（识别判定）。搜索 `rank()` 与识别 `match()` 签名不变，内部换核；`_photo_credit` 改调 `people`。分 3 个 PR：PR1=Task 1–5，PR2=Task 6–8，PR3=Task 9–11。

**Tech Stack:** Python 3.13、FastAPI、SQLAlchemy、rapidfuzz（新依赖）、pytest（离线 sqlite）。

**Spec:** `docs/superpowers/specs/2026-10-07-matching-core-design.md`

## Global Constraints

- 搜索 `search()` / `rank()`、识别 `match()` / `recognize()` 对外签名与返回形状不变；纯后端升级，App 不发版。
- 识别门槛：作者对上 `ACCEPT_WITH_ARTIST = 0.75`，否则 `ACCEPT_TITLE_ONLY = 0.9`；作者加分 `ARTIST_BONUS = 0.1` 参与排序不封顶，对外 score `min(…, 1.0)`。
- 召回模糊：拉丁词 ≥4 字母才容错，OSA 编辑距离 <7 字母 ≤1、≥7 字母 ≤2；中日韩按二字组。
- 搜索不把 popularity 当权重（只作最末并列键，保持现有测试）。
- 别名只写 `attributes.match_aliases`，只用于匹配、不显示；纪律 37：跑前写入面清单 + 备份 + 音频作废数 = 0；prod 由用户执行或明确授权。
- 加依赖必须走 `poetry add`（更新 `pyproject.toml` + `poetry.lock`），不手改 lock。
- 用户 Mac 同时在跑 TTS：本地跑重活（全量评测、内存测量）一律 `nice -n 19`、单进程。
- 测试命令（在 worktree `backend/` 下）：`PY=/Users/hongyang/Library/Caches/pypoetry/virtualenvs/gomuseum-backend-eWQPCnDy-py3.13/bin/python; $PY -m pytest <path> -p no:cacheprovider --no-cov -q`。
- 不 `git add <目录>/`，逐个文件 add；提交信息 Conventional Commits + 会话署名尾行。

## Review Focus

1. **馆域搜索 / 可见性过滤后的子集索引**：`rank()` 收到的是按馆过滤后的新列表——必须用全局倒排 + 允许集合，不得每次请求重建倒排（Louvre 17K 件在 prod 要 4s）。→ Task 3 `test_core_for_filtered_list_reuses_global_core`。
2. **索引后台重建期间**：新全局索引建好时倒排要在同一后台线程里建好，请求线程不得撞上 4.5s 的冷建。→ Task 3 `test_refresh_builds_core_in_background`。
3. **单字中文 / 两位数字 / 只有标点**这类分词后为空或不在词表的查询：必须走旧档位兜底，结果与现在一致。→ Task 4 `test_single_cjk_char_falls_back_to_substring`、`test_punct_only_query_empty`。
4. **识别 `reason` 两种诊断**：有召回但都不够门槛 → `low_confidence`；什么都没召回 → `not_in_catalog`。→ Task 7 两个测试。
5. **重导入作品冲掉别名**：`upsert_object` 整块覆盖 `attributes`。→ Task 9 `test_upsert_preserves_match_aliases`。

---

### Task 1: 依赖 + `matching/normalize.py`

**Files:**
- Modify: `backend/pyproject.toml`, `backend/poetry.lock`（`poetry add`）
- Create: `backend/app/services/matching/__init__.py`（空）
- Create: `backend/app/services/matching/normalize.py`
- Modify: `backend/app/services/recognition/matcher.py:17-42`（`normalize`/`normalize_inv` 及其正则挪走，改为再导出）
- Test: `backend/tests/unit/services/matching/__init__.py`（空）, `backend/tests/unit/services/matching/test_normalize.py`

**Interfaces:**
- Produces: `normalize(s: str) -> str`、`normalize_inv(s: str | None) -> str`、`tokens(s_normalized: str) -> list[str]`（输入须已归一化）、`is_cjk(tok: str) -> bool`。`matcher.normalize` / `matcher.normalize_inv` 仍可导入（`catalog_loader`、`search.inprocess`、测试在用）。

- [ ] **Step 1: 加依赖**

```bash
cd /Users/hongyang/Projects/GoMuseum-matching/backend
poetry add "rapidfuzz (>=3.14,<4.0)"
PY=/Users/hongyang/Library/Caches/pypoetry/virtualenvs/gomuseum-backend-eWQPCnDy-py3.13/bin/python
$PY -m pip install -q "rapidfuzz==$(grep -A1 '^name = "rapidfuzz"' poetry.lock | sed -n 's/version = "\(.*\)"/\1/p')"
$PY -c "import rapidfuzz; print(rapidfuzz.__version__)"
```

Expected: `poetry add` 改了 `pyproject.toml` 与 `poetry.lock`；最后一行打印版本号。若 `poetry add` 试图重装整个 env（worktree 路径不同会新建 venv），改用 `poetry lock` 后只用上面的 `$PY -m pip install` 装 rapidfuzz。

- [ ] **Step 2: 写失败测试**

```python
# backend/tests/unit/services/matching/test_normalize.py
from app.services.matching.normalize import normalize, normalize_inv, tokens
from app.services.recognition import matcher


def test_normalize_unchanged_behaviour():
    assert normalize("Théodore, Géricault!") == "theodore gericault"
    assert normalize_inv("RF 1668") == "rf1668"
    assert normalize_inv(None) == ""


def test_matcher_reexports_same_functions():
    assert matcher.normalize is normalize
    assert matcher.normalize_inv is normalize_inv


def test_tokens_latin_split_on_space():
    assert tokens("l air du soir") == ["l", "air", "du", "soir"]


def test_tokens_cjk_bigrams():
    assert tokens("世界的起源") == ["世界", "界的", "的起", "起源"]
    assert tokens("梵") == ["梵"]  # 单字保留为一个词
    assert tokens("文森特 梵高") == ["文森", "森特", "梵高"]
```

- [ ] **Step 3: 跑测试确认失败**

Run: `$PY -m pytest tests/unit/services/matching/test_normalize.py -p no:cacheprovider --no-cov -q`
Expected: FAIL，`ModuleNotFoundError: No module named 'app.services.matching'`

- [ ] **Step 4: 实现**

```python
# backend/app/services/matching/normalize.py
"""匹配核心的归一化与分词(搜索/识别/署名共用)。原在 recognition/matcher,matcher 再导出。"""

from __future__ import annotations

import re
import unicodedata

_PUNCT = re.compile(r"[^\w\s]", re.UNICODE)
_WS = re.compile(r"[\s_]+")
_NONALNUM = re.compile(r"[^a-z0-9]+")
_CJK = re.compile(r"[぀-ヿ㐀-鿿가-힯]")


def normalize(s: str) -> str:
    """小写/NFD 去音符/去标点/压空白(Théodore≈Theodore)。"""
    s = unicodedata.normalize("NFD", s or "")
    s = "".join(ch for ch in s if unicodedata.category(ch) != "Mn")
    s = _PUNCT.sub(" ", s.lower())
    return _WS.sub(" ", s).strip()


def normalize_inv(s: str | None) -> str:
    """馆藏号归一化:小写 + 去所有非字母数字("RF 1668"→"rf1668")。空/None 安全。"""
    return _NONALNUM.sub("", (s or "").lower())


def is_cjk(tok: str) -> bool:
    return bool(_CJK.search(tok))


def tokens(s: str) -> list[str]:
    """已归一化串 → 词。拉丁按空格;中日韩无空格,按二字组(单字保留)。"""
    out: list[str] = []
    for w in s.split():
        if is_cjk(w) and len(w) > 1:
            out += [w[i : i + 2] for i in range(len(w) - 1)]
        else:
            out.append(w)
    return out
```

在 `matcher.py` 删掉 `_PUNCT`、`_WS`、`_NONALNUM` 与 `normalize`、`normalize_inv` 的定义（17–19 行与 32–42 行），并在 import 区加：

```python
from app.services.matching.normalize import normalize, normalize_inv  # noqa: F401  再导出
```

- [ ] **Step 5: 跑测试确认通过 + 旧测试不坏**

Run: `$PY -m pytest tests/unit/services/matching tests/unit/services/recognition/test_matcher.py tests/unit/services/search/test_inprocess.py -p no:cacheprovider --no-cov -q`
Expected: 全部 PASS

- [ ] **Step 6: Commit**

```bash
git add backend/pyproject.toml backend/poetry.lock backend/app/services/matching/__init__.py backend/app/services/matching/normalize.py backend/app/services/recognition/matcher.py backend/tests/unit/services/matching/__init__.py backend/tests/unit/services/matching/test_normalize.py
git commit -m "feat(matching): 新建匹配核心模块,归一化/分词挪入并加 rapidfuzz 依赖"
```

---

### Task 2: `people.py` 同一个人 + 署名改调它

**Files:**
- Create: `backend/app/services/matching/people.py`
- Modify: `backend/app/services/museum_repo.py:191-211`（`_photo_credit`）
- Test: `backend/tests/unit/services/matching/test_people.py`

**Interfaces:**
- Consumes: `normalize`（Task 1）
- Produces: `same_person(a: str | None, b: str | None) -> bool`；`is_artist_credit(credit: str, aliases) -> bool`。`_photo_credit(credit, artist_aliases)` 签名不变。

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/unit/services/matching/test_people.py
import pytest

from app.services.matching.people import is_artist_credit, same_person
from app.services.museum_repo import _photo_credit


@pytest.mark.parametrize(
    "a,b",
    [
        ("Desportes, Alexandre-François", "Alexandre-François Desportes"),
        ("UTRILLO Maurice", "Maurice Utrillo"),
        ("Jean león gerome", "Jean-Léon Gérôme"),
        ("Workshop of François Clouet", "François Clouet"),
        ("Attributed to Colin Nouailher", "Colin Nouailher"),
        ("Thomas Regnaudin (1622–1706)", "Thomas Regnaudin"),
        ("Carpeaux, Jean-Baptiste (Valenciennes, 11–05–1827 - Courbevoie, 12–10–1875), sculpteur", "Jean-Baptiste Carpeaux"),
        ("Filippino Lippi / Sandro Botticelli", "Sandro Botticelli"),
        ("Gaspard Marsy (1624–1681) &amp; Anselme Flamen (1647–1717)", "Anselme Flamen"),
        ("David Teniers", "David Teniers the Younger"),  # 一边没写代际 → 仍同人
    ],
)
def test_same_person_variants(a, b):
    assert same_person(a, b)


@pytest.mark.parametrize(
    "a,b",
    [
        ("David Teniers the Elder", "David Teniers the Younger"),
        ("Pieter Brueghel l'ancien", "Pieter Brueghel le jeune"),
        ("Claude Monet", "Édouard Manet"),
        ("", "Claude Monet"),
        (None, "Claude Monet"),
    ],
)
def test_not_same_person(a, b):
    assert not same_person(a, b)


def test_master_of_year_still_hidden():
    # 名字带年份:旧的整串相等一路必须保留
    assert _photo_credit("Master of 1518", {"Master of 1518", "1518大師"}) is None


def test_reproduced_by_credit_stays_visible():
    c1 = "Michel Corneille l'ancien (reproduced by : musée des Beaux-Arts de Dijon - François Jay)"
    c2 = "Eustache Le Sueur (reproduced by : RMN-Grand Palais (musée du Louvre) / Franck Raux"
    assert _photo_credit(c1, {"Michel Corneille the Elder", "Michel Corneille l'ancien"}) == c1
    assert _photo_credit(c2, {"Eustache Le Sueur"}) == c2


def test_real_photographers_stay_visible():
    assert _photo_credit("Mbzt", {"Mesha", "메샤"}) == "Mbzt"
    assert _photo_credit("Shonagon", set()) == "Shonagon"


def test_word_order_credit_hidden():
    assert _photo_credit("Desportes, Alexandre-François", {"Alexandre-François Desportes"}) is None
    assert is_artist_credit("Pierre-Auguste Renoir", {"RENOIR Pierre Auguste"})
```

- [ ] **Step 2: 跑测试确认失败**

Run: `$PY -m pytest tests/unit/services/matching/test_people.py -p no:cacheprovider --no-cov -q`
Expected: FAIL，`ModuleNotFoundError: No module named 'app.services.matching.people'`

- [ ] **Step 3: 实现**

```python
# backend/app/services/matching/people.py
"""是不是同一个人(署名判同/识别作者加分/编号+作者直判共用)。

prod 10-07 实测:署名与作者名只差词序/逗号/生卒年/修饰词时整串比较认不出(571 条);
另有两条否决先于判同——
- 摄影/复制归属(reproduced by …)是 CC 要求的署名,哪怕前面写着画家名也要显示;
- 两边代际修饰不同(the Elder vs the Younger)是父子两个人(目录里 8 对)。"""

from __future__ import annotations

import re

from app.services.matching.normalize import normalize

_PHOTO = re.compile(
    r"reproduced by|photo|clich[eé]|©|\(c\)|\brmn\b|uploaded by|derivative work",
    re.IGNORECASE,
)
_PAREN = re.compile(r"\([^()]*\)")
_SPLIT = re.compile(r"\s*(?:/|;|\n|&amp;|&|\band\b|\bet\b)\s*", re.IGNORECASE)
_QUAL = {
    "probably", "possibly", "attributed", "to", "after", "copy", "of", "workshop",
    "circle", "school", "follower", "manner", "studio", "atelier", "d", "apres",
    "attribue", "a", "sculpteur", "peintre", "painter", "sculptor", "the", "le", "l",
}  # fmt: skip
_GEN = {
    "elder": "elder", "ancien": "elder", "pere": "elder", "senior": "elder",
    "younger": "younger", "jeune": "younger", "fils": "younger", "junior": "younger",
}  # fmt: skip


def _words(s: str) -> list[str]:
    return normalize(s).split()


def _generation(s: str) -> set[str]:
    return {_GEN[w] for w in _words(s) if w in _GEN}


def _person(s: str) -> frozenset[str]:
    return frozenset(
        w for w in _words(s) if w not in _QUAL and w not in _GEN and not w.isdigit()
    )


def _people(s: str) -> list[frozenset[str]]:
    """一个署名串 → 每个人的词集合(先剥括号里的生卒年/出生地),外加整串一份。"""
    while _PAREN.search(s):
        s = _PAREN.sub(" ", s)
    parts = [_person(p) for p in _SPLIT.split(s)]
    whole = frozenset(w for p in parts for w in p)
    return [p for p in parts if p] + ([whole] if whole else [])


def same_person(a: str | None, b: str | None) -> bool:
    if not a or not b:
        return False
    if a.strip().casefold() == b.strip().casefold():
        return True
    ga, gb = _generation(a), _generation(b)
    if ga and gb and ga != gb:
        return False
    pb = _people(b)
    return any(x == y for x in _people(a) for y in pb)


def is_artist_credit(credit: str, aliases) -> bool:
    """署名是不是作者本人(是 → 不显示)。旧的整串相等一路保留在最前。"""
    norm = credit.strip().casefold()
    if any(norm == a.strip().casefold() for a in aliases if a):
        return True
    if _PHOTO.search(credit):
        return False
    return any(same_person(credit, a) for a in aliases if a)
```

`museum_repo._photo_credit` 改为（docstring 末尾补一句「判同规则见 matching.people」）：

```python
def _photo_credit(credit: str | None, artist_aliases) -> str | None:
    ...  # 原 docstring 保留
    if not credit:
        return None
    from app.services.matching.people import is_artist_credit

    return None if is_artist_credit(credit, artist_aliases) else credit
```

- [ ] **Step 4: 跑测试确认通过 + 相关旧测试**

Run: `$PY -m pytest tests/unit/services/matching tests/integration/test_museum_repo.py tests/unit/services/recognition/test_service.py -k "credit or people or normalize" -p no:cacheprovider --no-cov -q`
Expected: PASS

- [ ] **Step 5: prod 署名全量对照（读，不写）**

把 Task 2 的 `is_artist_credit` 跑在 scratchpad `credits.jsonl`（prod 导出；若已被清空，按 spec §2.3 用 `cr.sql` 重导）上，输出「旧判不隐藏、新判隐藏」全量清单到 scratchpad `credit_newly_hidden.txt`，**逐条读完**。
Expected: 约 569 条（571 − 2 条 reproduced by），清单里没有摄影师/上传者/机构；有就补否决规则 + 加一条测试再跑。把最终条数写进 ledger。

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/matching/people.py backend/app/services/museum_repo.py backend/tests/unit/services/matching/test_people.py
git commit -m "feat(matching): 同一个人判同(词序/修饰词/生卒年;摄影归属与代际否决),署名改调它"
```

---

### Task 3: 倒排索引 `index.py`（随搜索索引后台建好）

**Files:**
- Create: `backend/app/services/matching/index.py`
- Modify: `backend/app/services/search/inprocess.py`（`_refresh_index_async._run`、`build_search_index` 冷建分支）
- Test: `backend/tests/unit/services/matching/test_index.py`

**Interfaces:**
- Consumes: `normalize`、`tokens`、`is_cjk`（Task 1）；搜索索引条目 dict（字段 `names: set[str]`、`artists: set[str]`）
- Produces:
  - `class Core`：`entries: list[dict]`；`expand(tok: str, field: "title"|"artist", prefix: bool=False) -> dict[str, float]`；`recall(qtoks: list[str], k: int, allowed: set[int] | None, use_artist: bool) -> list[tuple[int, float]]`；`and_hits(qtoks: list[str], allowed: set[int] | None) -> dict[int, float]`（每个词都命中的条目下标 → 加权分；末词按前缀）；`title_df: Counter[str]`。
  - `get_core(index: list[dict]) -> Core`（按 `id(index)` 缓存，最多保留 2 份）。
  - `core_for(index: list[dict]) -> tuple[Core, set[int] | None]`：`index` 是全局缓存索引 → `(全局 core, None)`；是全局索引的子集（同一批 dict 对象）→ `(全局 core, 允许下标集)`；否则（测试自建的列表）→ 为它单建并缓存。

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/unit/services/matching/test_index.py
from app.services.matching import index as mindex
from app.services.search import inprocess


def _e(i, names, artists=()):
    return {"id": i, "qid": f"Q{i}", "museum_id": 1 if i < 3 else 2,
            "names": set(names), "artists": set(artists)}


def _idx():
    return [
        _e(0, {"the starry night"}, {"vincent van gogh"}),
        _e(1, {"starry night over the rhone"}, {"vincent van gogh"}),
        _e(2, {"water lilies"}, {"claude monet"}),
        _e(3, {"le radeau de la meduse"}, {"theodore gericault"}),
    ]


def test_and_hits_requires_every_token():
    core = mindex.get_core(_idx())
    hits = core.and_hits(["gogh", "rhone"], None)
    assert set(hits) == {1}


def test_typo_expands_with_osa():
    core = mindex.get_core(_idx())
    assert "starry" in core.expand("satrry", "title")  # 相邻颠倒=1 次编辑


def test_last_token_prefix():
    core = mindex.get_core(_idx())
    assert set(core.and_hits(["water", "lil"], None)) == {2}


def test_core_for_filtered_list_reuses_global_core(monkeypatch):
    g = _idx()
    monkeypatch.setitem(inprocess._index_cache, None, (0.0, g))
    gcore = mindex.get_core(g)
    scoped = [e for e in g if e["museum_id"] == 1]
    core, allowed = mindex.core_for(scoped)
    assert core is gcore and allowed == {0, 1, 2}
    core2, allowed2 = mindex.core_for(g)
    assert core2 is gcore and allowed2 is None


def test_refresh_builds_core_in_background(monkeypatch):
    built = []
    monkeypatch.setattr(inprocess, "_build_global", lambda db: _idx())
    monkeypatch.setattr(mindex, "get_core", lambda ix: built.append(ix) or None)

    class _T:
        def __init__(self, target, **kw):
            self.t = target

        def start(self):
            self.t()

    monkeypatch.setattr(inprocess.threading, "Thread", _T)
    monkeypatch.setattr("app.core.database.SessionLocal", lambda: type("S", (), {"close": lambda s: None})())
    inprocess._refreshing = False
    inprocess._refresh_index_async()
    assert built and built[0] is inprocess._index_cache[None][1]
```

- [ ] **Step 2: 跑测试确认失败**

Run: `$PY -m pytest tests/unit/services/matching/test_index.py -p no:cacheprovider --no-cov -q`
Expected: FAIL，`ImportError: cannot import name 'index'`

- [ ] **Step 3: 实现**

```python
# backend/app/services/matching/index.py
"""倒排索引:在搜索全局索引条目之上建 标题词/作者词 → 条目下标,召回只碰相关的几百件。

prod 10-07:26 万个名字逐个 difflib 一次 15–300s;倒排召回 + 精排 prod 主机 p50 0.23s。
倒排随搜索索引在后台线程里一起建好(prod 主机 4.5s),请求线程不碰冷建。"""

from __future__ import annotations

import bisect
import collections
import math
import threading

from rapidfuzz import process
from rapidfuzz.distance import OSA

from app.services.matching.normalize import is_cjk, tokens

_FUZZY_MIN = 4  # 拉丁词 ≥4 字母才容错
_PREFIX_MIN = 2


class Core:
    def __init__(self, entries: list[dict]):
        self.entries = entries
        self.pos = {id(e): i for i, e in enumerate(entries)}
        post = {"title": collections.defaultdict(set), "artist": collections.defaultdict(set)}
        self.title_df: collections.Counter = collections.Counter()
        for i, e in enumerate(entries):
            for n in e["names"]:
                self.title_df[n] += 1
                for t in tokens(n):
                    post["title"][t].add(i)
            for a in e["artists"]:
                for t in tokens(a):
                    post["artist"][t].add(i)
        n = max(len(entries), 1)
        # ponytail: 倒排用 list 省内存(set 每元素 ~60B);若 prod 每 worker 超 300MB 再换 array('I')
        self.post = {f: {t: sorted(s) for t, s in p.items()} for f, p in post.items()}
        self.idf = {f: {t: math.log(n / len(s)) for t, s in p.items()} for f, p in self.post.items()}
        self.vocab = {f: sorted(p) for f, p in self.post.items()}

    def expand(self, tok: str, field: str, prefix: bool = False) -> dict[str, float]:
        """查询词 → {库词: 相似度 0–1}。精确 1.0;拉丁 ≥4 字母按 OSA 容错;prefix=搜索框末词。"""
        post, vocab = self.post[field], self.vocab[field]
        out: dict[str, float] = {}
        if tok in post:
            out[tok] = 1.0
        if len(tok) >= _FUZZY_MIN and not is_cjk(tok):
            k = 1 if len(tok) < 7 else 2
            for v, d, _ in process.extract(
                tok, vocab, scorer=OSA.distance, score_cutoff=k, limit=8
            ):
                out[v] = max(out.get(v, 0.0), 1 - d / max(len(tok), len(v)))
        if prefix and len(tok) >= _PREFIX_MIN:
            j = bisect.bisect_left(vocab, tok)
            while j < len(vocab) and vocab[j].startswith(tok):
                if vocab[j] != tok:
                    out[vocab[j]] = max(out.get(vocab[j], 0.0), 0.9)
                j += 1
        return out

    def _token_hits(self, tok, fields, prefix, allowed) -> dict[int, float]:
        best: dict[int, float] = {}
        for f in fields:
            idf = self.idf[f]
            for v, s in self.expand(tok, f, prefix).items():
                w = s * idf[v]
                for i in self.post[f][v]:
                    if (allowed is None or i in allowed) and w > best.get(i, 0.0):
                        best[i] = w
        return best

    def recall(self, qtoks, k=200, allowed=None, use_artist=False):
        """各词加权分累加 → 前 k 个 (下标, 分)。识别用(不要求每词都中)。"""
        fields = ("title", "artist") if use_artist else ("title",)
        acc: dict[int, float] = collections.defaultdict(float)
        for t in qtoks:
            for i, w in self._token_hits(t, fields, False, allowed).items():
                acc[i] += w
        return sorted(acc.items(), key=lambda kv: -kv[1])[:k]

    def and_hits(self, qtoks, allowed=None) -> dict[int, float]:
        """搜索用:每个词都要在标题或作者里命中(末词前缀)→ {下标: 加权分}。"""
        acc: dict[int, float] | None = None
        for j, t in enumerate(qtoks):
            hits = self._token_hits(t, ("title", "artist"), j == len(qtoks) - 1, allowed)
            if acc is None:
                acc = hits
            else:
                acc = {i: acc[i] + w for i, w in hits.items() if i in acc}
            if not acc:
                return {}
        return acc or {}


_cores: "collections.OrderedDict[int, tuple[list, Core]]" = collections.OrderedDict()
_lock = threading.Lock()


def get_core(index: list[dict]) -> Core:
    key = id(index)
    with _lock:
        hit = _cores.get(key)
        if hit and hit[0] is index:
            return hit[1]
    core = Core(index)
    with _lock:
        _cores[key] = (index, core)  # 持有 index 引用,id 不会被复用
        while len(_cores) > 2:
            _cores.popitem(last=False)
    return core


def core_for(index: list[dict]) -> tuple[Core, set[int] | None]:
    from app.services.search.inprocess import _index_cache

    hit = _index_cache.get(None)
    g = hit[1] if hit else None
    if g is not None and index is not g:
        gcore = get_core(g)
        pos = gcore.pos
        allowed = {pos[id(e)] for e in index if id(e) in pos}
        if len(allowed) == len(index):
            return gcore, allowed
    return get_core(index), None
```

`search/inprocess.py`：后台重建与冷建两处，在把新索引放进 `_index_cache` 后立即建倒排：

```python
# _refresh_index_async._run 里
                index = _build_global(db2)
                _warm_core(index)  # 倒排同线程建好,请求线程不碰冷建
                _index_cache[None] = (time.time(), index)
```

```python
# build_search_index 冷建分支
        index = _build_global(db)
        _warm_core(index)
        _index_cache[None] = (time.time(), index)
```

```python
# inprocess.py 模块级新增(两处共用;倒排失败绝不拖垮搜索索引——rank 会退回原分档)
def _warm_core(index) -> None:
    try:
        from app.services.matching.index import get_core

        get_core(index)
    except Exception:
        logger.exception("matching core build failed, search falls back to tiers")
```

（建倒排要在写进 `_index_cache` **之前**，测试里 `built[0] is _index_cache[None][1]` 只比对象身份，顺序不影响断言；生产上先建再换，换上去的那一刻倒排已就绪。）

- [ ] **Step 4: 跑测试确认通过**

Run: `$PY -m pytest tests/unit/services/matching tests/unit/services/search/test_inprocess.py -p no:cacheprovider --no-cov -q`
Expected: PASS。`test_cold_start_builds_synchronously` 把 `_build_global` 换成返回 `[{"museum_id": 7}]`（无 `names` 键）——`_warm_core` 吞掉 `KeyError` 只记日志，测试照旧拿到 `[{"museum_id": 7}]`，这正是 `_warm_core` 要包 try 的原因。

- [ ] **Step 5: prod 规模内存与建索引耗时（本地，读）**

```bash
cd /Users/hongyang/Projects/GoMuseum-matching/backend
S=/private/tmp/claude-501/-Users-hongyang-Projects-GoMuseum/e44a5246-76a6-4f1e-9212-505786eba291/scratchpad
nice -n 19 $PY - <<EOF
import sys, json, time, tracemalloc
sys.path.insert(0, "$S"); sys.argv = ["x", "$S"]
import evalset
from app.services.matching.index import Core
ix = evalset.build_index(evalset.cat)
tracemalloc.start(); t = time.time(); c = Core(ix); dt = time.time() - t
cur, peak = tracemalloc.get_traced_memory()
print(f"build {dt:.1f}s  core {cur/1e6:.0f}MB peak {peak/1e6:.0f}MB")
EOF
```

Expected: 打印一行。core ≤ 300MB 记入 ledger；> 300MB 则把 `self.post` 的 list 换成 `array('I', …)` 再测一次，写 Ruling。（若 scratchpad 已清空：按 spec §2 用 `cat2.sql` 重导 `catalog2.jsonl`，`evalset.py` 在 Task 5 已进仓库，改用仓库版。）

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/matching/index.py backend/app/services/search/inprocess.py backend/tests/unit/services/matching/test_index.py
git commit -m "feat(matching): 标题/作者倒排索引,随搜索索引后台重建,馆域子集复用全局倒排"
```

---

### Task 4: 搜索 `rank()` 换核

**Files:**
- Modify: `backend/app/services/search/inprocess.py:208-235`（`rank`）
- Test: `backend/tests/unit/services/search/test_inprocess.py`（追加）

**Interfaces:**
- Consumes: `core_for`、`Core.and_hits`（Task 3）；`normalize`、`tokens`（Task 1）
- Produces: `rank(index, query, limit=20) -> list[tuple[dict, float]]`（不变）。分值档：编号 1.0 / 纯数字编号 0.9 / 标题前缀 0.8 / 标题子串 0.6 / 作者子串 0.4 / **新：词元命中 0.3**（每词都中但不属于以上档）。

- [ ] **Step 1: 写失败测试（追加到 test_inprocess.py 末尾）**

```python
# --- 匹配核心(10-07):每词命中 + 容错 + 兜底 ---


def test_artist_surname_plus_title_word(session):
    idx = build_search_index(session, _mid(session))
    out = rank(idx, "gogh rhone")
    assert [e["qid"] for e, _ in out] == ["Q_STUB"]
    assert out[0][1] == 0.3


def test_typo_still_found(session):
    idx = build_search_index(session, _mid(session))
    assert "Q45585" in {e["qid"] for e, _ in rank(idx, "satrry nihgt")}


def test_skipped_word_found(session):
    idx = build_search_index(session, _mid(session))
    assert "Q_STUB" in {e["qid"] for e, _ in rank(idx, "starry rhone")}


def test_single_cjk_char_falls_back_to_substring(session):
    idx = build_search_index(session, _mid(session))
    assert [e["qid"] for e, _ in rank(idx, "星")] == ["Q45585"]


def test_punct_only_query_empty(session):
    idx = build_search_index(session, _mid(session))
    assert rank(idx, "!!!") == []


def test_same_tier_closer_title_first(session):
    # 同为前缀档:整名更接近查询的排前(不靠 popularity)
    m = session.query(Museum).filter_by(slug="orsay").one()
    for qid, t in (("Q_LONG", "Portrait de femme assise dans un jardin"), ("Q_SHORT", "Portrait de femme")):
        upsert_object(session, m.id, {"qid": qid, "title_en": t, "category": "painting", "popularity": 0})
    session.commit()
    inprocess._index_cache.clear()
    idx = build_search_index(session, _mid(session))
    qids = [e["qid"] for e, _ in rank(idx, "portrait de femme")]
    assert qids.index("Q_SHORT") < qids.index("Q_LONG")


def test_scoped_search_uses_global_core(session, monkeypatch):
    from app.services.matching import index as mindex

    build_search_index(session, None)
    built = []
    orig = mindex.Core
    monkeypatch.setattr(mindex, "Core", lambda ix: built.append(1) or orig(ix))
    rank(build_search_index(session, _mid(session)), "gogh rhone")
    assert built == []  # 馆域子集不重建倒排
```

- [ ] **Step 2: 跑测试确认失败**

Run: `$PY -m pytest tests/unit/services/search/test_inprocess.py -p no:cacheprovider --no-cov -q`
Expected: 新增的 `test_artist_surname_plus_title_word`、`test_typo_still_found`、`test_skipped_word_found`、`test_same_tier_closer_title_first` FAIL（空结果或顺序不对）；其余 PASS。

- [ ] **Step 3: 实现**

把现 `rank` 的打分部分抽成 `_tier_scores(index, query) -> dict`（原逻辑一字不改：`_score` + 数字退路），新 `rank`：

```python
_S_TOKEN = 0.3  # 每个词都在标题/作者里命中(含拼错/跳词/姓+标题词),但不属于上面任何一档


def _tier_scores(index, query: str) -> dict:
    """原分档(编号/数字编号/前缀/子串/作者子串)→ {id: (entry, score)}。query 已 NFKC。"""
    qn = normalize(query)
    qinv = normalize_inv(query)
    scored = {e["id"]: (e, s) for e in index if (s := _score(e, qn, qinv)) > 0}
    qd = query.strip()
    if (
        qd.isdigit()
        and len(qd) >= _INV_MIN
        and not any(s == _S_INV for _, s in scored.values())
    ):
        for e in index:
            if e["inv_digits"] == qd:
                prev = scored.get(e["id"], (e, 0.0))[1]
                scored[e["id"]] = (e, max(prev, _S_INV_DIGITS))
    return scored


def rank(index: list[dict], query: str, limit: int = 20) -> list[tuple[dict, float]]:
    """[(entry, score)] 降序,取 top limit。空 query → []。

    两路合并(匹配核心 10-07,spec docs/superpowers/specs/2026-10-07-matching-core-design.md):
    ①原分档(编号/前缀/子串/作者子串)原样保留——现在能搜到的一条不丢;
    ②每个查询词都在标题或作者里命中(允许拼错、末词前缀、跳词、姓+标题词),
      不属于①任何一档的给 0.3。
    排序:分档 → 同档内整名与查询越像越前 → 词元加权分 → popularity(只作最末并列键)。
    ⚠️ 「数字退路全部列出」靠调用方 limit 够大(前端传 60)。"""
    query = unicodedata.normalize("NFKC", query)
    qn = normalize(query)
    if not qn:
        return []
    merged = {k: (e, s, 0.0) for k, (e, s) in _tier_scores(index, query).items()}
    try:
        core, allowed = core_for(index)
        for i, w in core.and_hits(tokens(qn), allowed).items():
            e = core.entries[i]
            prev = merged.get(e["id"])
            merged[e["id"]] = (e, prev[1] if prev else _S_TOKEN, w)
    except Exception:  # 倒排不可用时退回原分档,搜索不 5xx
        logger.exception("matching core unavailable, tier-only search")

    def sim(e):
        return max((fuzz.ratio(qn, n) for n in e["names"]), default=0)

    out = sorted(
        merged.values(),
        key=lambda x: (-x[1], -sim(x[0]), -x[2], -x[0]["popularity"]),
    )
    return [(e, s) for e, s, _ in out[:limit]]
```

import 区加：

```python
from rapidfuzz import fuzz

from app.services.matching.index import core_for
from app.services.matching.normalize import tokens
```

（`normalize`、`normalize_inv` 的 import 改为 `from app.services.matching.normalize import normalize, normalize_inv`。）

- [ ] **Step 4: 跑测试确认通过**

Run: `$PY -m pytest tests/unit/services/search tests/integration/test_search_endpoint.py tests/integration/test_visibility_gate.py -p no:cacheprovider --no-cov -q`
Expected: 全部 PASS（含原有 `test_tie_break_by_popularity`：两件都 0.6，「the starry night」比「starry night over the rhone」更接近「night」，排序不变）。

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/search/inprocess.py backend/tests/unit/services/search/test_inprocess.py
git commit -m "feat(search): 每词命中+拼错容错+同档按整名相似度排,原分档全保留兜底"
```

---

### Task 5: 搜索评测进仓库（回归门槛）

**Files:**
- Create: `backend/tests/eval/__init__.py`、`backend/tests/eval/matching/__init__.py`（空）
- Create: `backend/tests/eval/matching/build_fixture.py`（一次性：从 prod 目录导出抽样 + 构造用例，产物提交）
- Create: `backend/tests/eval/matching/catalog_sample.jsonl`、`search_cases.json`（由上面脚本生成）
- Create: `backend/tests/eval/matching/conftest.py`（加载样本 → 索引条目）
- Create: `backend/tests/eval/matching/test_search_eval.py`

**Interfaces:**
- Consumes: `rank`（Task 4）
- Produces: `conftest.py` 的 fixture `eval_index() -> list[dict]`（条目字段与 `_build_global` 一致：id、qid、museum_id、names、artists、inv、inv_digits、popularity），Task 8 复用；`load_jsonl(path) -> list[dict]`。

- [ ] **Step 1: 写 build_fixture.py**

从 scratchpad `evalset.py` 搬过来（同一套构造逻辑、同一种子 20261007），改动：
- 输入：`--catalog <prod 导出 catalog2.jsonl>`；输出到本目录。
- **抽样目录**：每馆按占比抽共 4000 件（橘园、Rijksmuseum 全收），再并入所有用例目标件，以及「同名作」难例：对每个用例目标，把与它任一名字归一化相同的其它件也收进来（保留 1.0 并列的真实形态）。
- 搜索用例：prefix2 / middle_word / typo / words_skip / artist+word / zh_part，各 ~150 条，外加高频词 16 个（`portrait, vierge, saint jean, femme, paysage, nature morte, louis xiv, christ, rubens, corot, monet, vase, tête, bust of, head of, studio`）作 `kind="hifreq"`、`target=None`。
- 识别用例（Task 8 用）：exact / partial / typo / alias_missing（带 `drop`）/ neg_famous / neg_junk，生成 `recog_cases.json`；外加 Cross 墙签双标题用例 `{"kind": "label_bilingual", "target": "Q17492552", "queries": ["L'Air du soir", "The Evening Air"], "hints": ["Henri-Edmond Cross"], "drop": null}`。
- 只保留公开目录字段：qid、m、en、zh、i18n、a_en、a_zh、a_i18n、a_name_en、inv、pop。

Run:
```bash
S=/private/tmp/claude-501/-Users-hongyang-Projects-GoMuseum/e44a5246-76a6-4f1e-9212-505786eba291/scratchpad
cd /Users/hongyang/Projects/GoMuseum-matching/backend
nice -n 19 $PY tests/eval/matching/build_fixture.py --catalog $S/catalog2.jsonl
ls -la tests/eval/matching/
```
Expected: 生成 `catalog_sample.jsonl`（< 3MB）、`search_cases.json`、`recog_cases.json`。

- [ ] **Step 2: 写 conftest + 评测测试**

```python
# backend/tests/eval/matching/conftest.py
import json
import re
from pathlib import Path

import pytest

from app.services.matching.normalize import normalize, normalize_inv

HERE = Path(__file__).parent


def load_jsonl(p):
    return [json.loads(line) for line in open(p, encoding="utf-8") if line.strip()]


def to_entries(cat):
    out = []
    for d in cat:
        raw = {v for v in (d.get("i18n") or {}).values() if v} | {x for x in (d.get("en"), d.get("zh")) if x}
        arts = {v for v in (d.get("a_i18n") or {}).values() if v} | {x for x in (d.get("a_en"), d.get("a_zh"), d.get("a_name_en")) if x}
        out.append({
            "id": d["qid"], "qid": d["qid"], "museum_id": d["m"],
            "names": {normalize(x) for x in raw} - {""},
            "artists": {normalize(a) for a in arts} - {""},
            "inv": normalize_inv(d.get("inv")) or None,
            "inv_digits": re.sub(r"\D", "", d.get("inv") or "") or None,
            "popularity": d.get("pop") or 0,
        })
    return out


@pytest.fixture(scope="session")
def eval_catalog():
    return load_jsonl(HERE / "catalog_sample.jsonl")


@pytest.fixture()
def eval_index(eval_catalog):
    return to_entries(eval_catalog)
```

```python
# backend/tests/eval/matching/test_search_eval.py
"""搜索回归门槛(spec §2.2/§7)。数字来自 Task 5 Step 3 实测,门槛=实测-3pp;旧算法另跑一遍,
每类新≥旧。目录是 prod 抽样快照(公开目录字段),用例固定种子。"""

import collections
import json

import pytest

from app.services.search import inprocess
from tests.eval.matching.conftest import HERE

FLOOR_AT20 = {}  # Step 3 填:{"prefix2": 0.74, ...}


def _hit_rates(index, rank_fn, cases):
    by = collections.defaultdict(lambda: [0, 0])
    for c in cases:
        if c["target"] is None:
            continue
        got = [e["qid"] for e, _ in rank_fn(index, c["q"], 60)[:20]]
        b = by[c["kind"]]
        b[0] += 1
        b[1] += c["target"] in got
    return {k: h / n for k, (n, h) in by.items()}


@pytest.fixture(scope="module")
def cases():
    return json.load(open(HERE / "search_cases.json", encoding="utf-8"))


def test_search_not_worse_than_tier_only(eval_index, cases, monkeypatch):
    inprocess._index_cache.clear()
    new = _hit_rates(eval_index, inprocess.rank, cases)

    def tier_only(ix, q, limit):
        return [(e, s) for e, s in sorted(inprocess._tier_scores(ix, q).values(), key=lambda es: (-es[1], -es[0]["popularity"]))[:limit]]

    old = _hit_rates(eval_index, tier_only, cases)
    for k in old:
        assert new[k] >= old[k] - 0.01, (k, old[k], new[k])
    for k, floor in FLOOR_AT20.items():
        assert new[k] >= floor, (k, new[k], floor)


def test_hifreq_exact_or_prefix_titles_first(eval_index, cases):
    for c in [c for c in cases if c["kind"] == "hifreq"]:
        out = inprocess.rank(eval_index, c["q"], 60)
        scores = [s for _, s in out]
        assert scores == sorted(scores, reverse=True), c["q"]
```

- [ ] **Step 3: 跑、记数、填门槛**

Run: `nice -n 19 $PY -m pytest tests/eval/matching/test_search_eval.py -p no:cacheprovider --no-cov -q -s`
Expected: PASS。在 `_hit_rates` 后临时 `print(new, old)` 拿到实测数，填 `FLOOR_AT20 = {k: round(v - 0.03, 2)}`，删掉 print 再跑一次 PASS。新旧数字写进 ledger；任何一类 new < old 先查原因，不准调低门槛过关。

- [ ] **Step 4: Commit**

```bash
git add backend/tests/eval/__init__.py backend/tests/eval/matching/__init__.py backend/tests/eval/matching/build_fixture.py backend/tests/eval/matching/catalog_sample.jsonl backend/tests/eval/matching/search_cases.json backend/tests/eval/matching/recog_cases.json backend/tests/eval/matching/conftest.py backend/tests/eval/matching/test_search_eval.py
git commit -m "test(matching): 搜索评测集进仓库(prod 目录抽样+固定种子),新≥旧+门槛回归"
```

**PR1**：Task 1–5 完成后，全量后端测试 `nice -n 19 $PY -m pytest tests -p no:cacheprovider --no-cov -q -x` 绿 → 推分支 `feature/matching-core`（从本 spec 分支继续）→ `/pr` 提到 staging → CI 绿（含 Docker build 装 rapidfuzz）→ 合 staging → staging 实测 3 个查询（`gogh rhone` 类、拼错、中文）。上 prod 由用户点。

---

### Task 6: 识别 `core.recognize()` + `matcher.match` 换核

**Files:**
- Create: `backend/app/services/matching/core.py`
- Modify: `backend/app/services/recognition/matcher.py`（`match` 变薄包装；新增 `match_with_trace`；`inv_artist_hit` 作者比对改 `same_person`；`_inv_probes`、`_INV_TOKEN`、`_DIM`、`_INV_MIN` 保留在 matcher 供 core 导入）
- Test: `backend/tests/unit/services/matching/test_core.py`；`backend/tests/unit/services/recognition/test_matcher.py`（改 1 个用例，见 Step 5）

**Interfaces:**
- Consumes: `core_for`、`Core.recall`、`Core.title_df`（Task 3）；`same_person`（Task 2）；`normalize`、`tokens`（Task 1）
- Produces:
  - `core.recognize(index, queries, label_lines, artist_hints=None, limit=5, label_lines_inv_only=False) -> tuple[list[tuple[str, float]], list[list]]`：`(accepted, raw_top5)`；`accepted` 按排序键降序、score=`min(标题分+0.1·作者对上, 1.0)`；`raw_top5` 为 `[[qid, round(score,3), artist_ok]]`，不论是否过门槛。
  - `matcher.match_with_trace(...)` = `core.recognize(...)`；`matcher.match(...)` = `match_with_trace(...)[0]`（签名不变）。
  - 常量 `ACCEPT_WITH_ARTIST=0.75`、`ACCEPT_TITLE_ONLY=0.9`、`ARTIST_BONUS=0.1`、`REVSUB_MIN=8`、`REVSUB_SCORE=0.8`。

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/unit/services/matching/test_core.py
from app.services.matching.core import recognize


def _e(qid, names, artists=(), inv=None):
    return {"id": qid, "qid": qid, "museum_id": 1, "names": set(names),
            "artists": set(artists), "inv": inv, "inv_digits": None, "popularity": 0}


IDX = [
    _e("Q_A", {"madonna and child"}, {"giovanni bellini"}),
    _e("Q_B", {"madonna and child"}, {"cima da conegliano"}),
    _e("Q_C", {"composition"}, {"piet mondrian"}),
    _e("Q_D", {"l air du soir"}, {"henri edmond cross"}),
    _e("Q_E", {"portrait of woman with dove"}, {"marie laurencin"}),
]


def test_artist_breaks_exact_title_tie():
    acc, _ = recognize(IDX, ["Madonna and Child"], [], ["Giovanni Bellini"])
    assert acc[0][0] == "Q_A" and acc[0][1] == 1.0
    assert acc[1][0] == "Q_B"


def test_short_catalog_title_not_swallowed_by_long_query():
    acc, raw = recognize(IDX, ["Composition VIII"], [], ["Wassily Kandinsky"])
    assert "Q_C" not in dict(acc)


def test_junk_returns_nothing_but_raw_kept():
    acc, raw = recognize(IDX, ["Pixelated House", "Green House Illustration"], [], ["Unknown"])
    assert acc == []


def test_partial_title_accepted():
    acc, _ = recognize(IDX, ["Portrait of Woman"], [], ["Marie Laurencin"])
    assert acc[0][0] == "Q_E"


def test_no_artist_needs_high_title():
    # 「Woman with a Dog」vs 库名「portrait of woman with dove」:partial≈0.8,作者没对上 → 不出
    # (⚠️ 别用「Portrait of Woman with a Dog」:整串 ratio≈0.91 会过 0.9)
    acc, _ = recognize(IDX, ["Woman with a Dog"], [], [])
    assert acc == []


def test_low_confidence_has_raw():
    acc, raw = recognize(IDX, ["Madona Chlid"], [], [])
    assert acc == [] and raw  # 有召回但不够门槛 → service 判 low_confidence


def test_inv_hit_full_score():
    idx = IDX + [_e("Q_INV", {"nothing alike"}, (), inv="rf1668")]
    acc, _ = recognize(idx, [], ["RF 1668"])
    assert acc[0] == ("Q_INV", 1.0)


def test_reverse_substring_needs_artist():
    line = "Henri-Edmond Cross L'Air du soir vers 1893 huile sur toile"
    acc, _ = recognize(IDX, [], [line])
    assert acc and acc[0][0] == "Q_D"
```

- [ ] **Step 2: 跑测试确认失败**

Run: `$PY -m pytest tests/unit/services/matching/test_core.py -p no:cacheprovider --no-cov -q`
Expected: FAIL，`ModuleNotFoundError: No module named 'app.services.matching.core'`

- [ ] **Step 3: 实现 core.py**

```python
# backend/app/services/matching/core.py
"""识别文字链的判定:候选名/墙签行 → [(qid, score)](只含过门槛的)+ 原始前 5(诊断)。

门槛来自 10-07 评测(spec §2.1):对半切,一半网格调参、另一半留出复验——
0.75/0.9 在留出集:标题对 97%/100%(排第1/进前3)、半标题 89%/94%、垃圾输入 0% 出候选、
库外名作 20% 出候选。作者加分参与排序不封顶(原 min(…,1.0) 让作者打破不了同名并列)。"""

from __future__ import annotations

from rapidfuzz import fuzz

from app.services.matching.index import core_for
from app.services.matching.normalize import normalize, tokens
from app.services.matching.people import same_person

ACCEPT_WITH_ARTIST = 0.75
ACCEPT_TITLE_ONLY = 0.9
ARTIST_BONUS = 0.1
REVSUB_MIN = 8  # 反向子串:目录名 ≥8 字符整串出现在墙签里
REVSUB_SCORE = 0.8  # 只有作者也对上才够门槛
_PER_QUERY = 200


def title_sim(q: str, n: str) -> float:
    """ratio;查询比库名短(且 ≥40%)时另取 0.95×partial_ratio。只单向——
    反过来短库名(「Composition」)会吃进长查询(10-07 原型误报来源)。"""
    r = fuzz.ratio(q, n)
    if len(n) * 0.4 <= len(q) <= len(n):
        r = max(r, 0.95 * fuzz.partial_ratio(q, n))
    return r / 100


def recognize(index, queries, label_lines, artist_hints=None, limit=5, label_lines_inv_only=False):
    from app.services.recognition.matcher import _inv_probes

    queries = [q for q in queries if q]
    label_lines = [x for x in label_lines if x]
    fuzzy_src = queries if label_lines_inv_only else queries + label_lines
    probes = [p for p in (normalize(q) for q in fuzzy_src) if p]
    inv = _inv_probes(queries + label_lines)
    ocr_norm = "" if label_lines_inv_only else normalize(" ".join(label_lines))
    hints = [h for h in (artist_hints or []) if h]
    if not label_lines_inv_only:
        # 墙签里单独成行的作者名(「Henri-Edmond Cross」)同样是作者证据;整行长句命中不了
        # same_person(词集合要相等),长句靠下面「作者名是墙签原文子串」那一路
        hints += label_lines
    core, allowed = core_for(index)

    cand: dict[int, float] = {}
    for p in probes:
        for i, _ in core.recall(tokens(p), _PER_QUERY, allowed):
            e = core.entries[i]
            s = max((title_sim(p, n) for n in e["names"]), default=0.0)
            if ocr_norm and any(len(n) >= REVSUB_MIN and n in ocr_norm for n in e["names"]):
                s = max(s, REVSUB_SCORE)
            cand[i] = max(cand.get(i, 0.0), s)
    if inv:
        for i, e in enumerate(core.entries):
            if (allowed is None or i in allowed) and e.get("inv") in inv:
                cand[i] = 1.0

    rows = []
    for i, s in cand.items():
        e = core.entries[i]
        ok = any(same_person(h, a) for h in hints for a in e["artists"]) or bool(
            ocr_norm and any(len(a) >= 6 and a in ocr_norm for a in e["artists"])
        )
        rows.append((s + ARTIST_BONUS * ok, s, ok, e["qid"]))
    rows.sort(key=lambda r: -r[0])

    raw = [[q, round(min(k, 1.0), 3), ok] for k, _, ok, q in rows[:5]]
    best: dict[str, float] = {}
    for k, s, ok, q in rows:
        if s >= 1.0 or s >= (ACCEPT_WITH_ARTIST if ok else ACCEPT_TITLE_ONLY):
            best.setdefault(q, min(k, 1.0))
    accepted = list(best.items())[:limit]
    return accepted, raw
```

（`inv` 全表扫是 O(N) 的整数/短串比较，2.7 万件 <5ms；`s >= 1.0` 让编号命中不受作者门槛限制，保留原「编号精确给满分」语义。）

- [ ] **Step 4: matcher 接线**

`matcher.py` 里删掉 `_sim_above`、`_FLOOR`、`_ARTIST_BONUS`、`_REVSUB_*` 与旧 `match` 实现，改为：

```python
def match_with_trace(
    index, queries, label_lines, artist_hints=None, limit: int = 5,
    label_lines_inv_only: bool = False,
):
    """→ (过门槛的 [(qid, score)], 原始前 5 [[qid, score, 作者对上]])。见 matching.core。"""
    from app.services.matching.core import recognize

    return recognize(index, queries, label_lines, artist_hints, limit, label_lines_inv_only)


def match(index, queries, label_lines, artist_hints=None, limit: int = 5, label_lines_inv_only: bool = False) -> list:
    """签名不变;只返回过门槛的候选。原 docstring 的肖像劫持/墙签只抽编号说明保留。"""
    return match_with_trace(index, queries, label_lines, artist_hints, limit, label_lines_inv_only)[0]
```

`inv_artist_hit` 里作者判定改为：

```python
        if any(
            an and (an in text_norm or any(same_person(h, an) for h in hints))
            for an in e["artists"]
        ):
```

（同时把该函数里 `hints = [normalize(a) for a in (artist_hints or []) if a]` 改为 `hints = [a for a in (artist_hints or []) if a]`（`same_person` 自己会归一化）；import `from app.services.matching.people import same_person`。）

- [ ] **Step 5: 跑匹配测试，处理一条预期内的行为变化**

Run: `$PY -m pytest tests/unit/services/matching tests/unit/services/recognition/test_matcher.py -p no:cacheprovider --no-cov -q`
Expected: 新测试 PASS；`test_label_lines_match_with_artist_bonus` FAIL（`plain` 现在是 `[]`：「Radeau Méduse」跳词、无作者，标题分 <0.9 被判不出——spec §3.3 预期行为）。把它改为保留原意图「作者行加分」的写法并记 Ruling：

```python
def test_label_lines_match_with_artist_bonus(session):
    # 标题够近(无作者也能出) + 作者行 → 分数更高;只有跳词标题且无作者 → 不出(spec §3.3)
    idx = build_index(session, _mid(session))
    plain = match(idx, [], ["Radeau de la Méduse"])
    boosted = match(idx, [], ["Radeau de la Méduse", "Théodore Géricault", "1819"])
    assert boosted[0][0] == "Q778242"
    assert boosted[0][1] > plain[0][1]
    assert match(idx, [], ["Radeau Méduse"]) == []
```

其余旧用例必须不改即通过；有别的失败先查是不是 bug，不准顺手改断言。

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/matching/core.py backend/app/services/recognition/matcher.py backend/tests/unit/services/matching/test_core.py backend/tests/unit/services/recognition/test_matcher.py
git commit -m "feat(recognize): 文字链换匹配核心——倒排召回+单向 partial+作者不封顶+门槛判定"
```

---

### Task 7: `service.py` 接 `match_with_trace` + 提示词 `original_title`

**Files:**
- Modify: `backend/app/services/recognition/service.py:22, 433-489`
- Modify: `backend/app/services/recognition/vision.py:34-52, 96-105`
- Test: `backend/tests/unit/services/recognition/test_service.py`（追加）、`backend/tests/unit/services/recognition/test_vision.py`（追加）

**Interfaces:**
- Consumes: `matcher.match_with_trace`（Task 6）
- Produces: `identify()` 返回的每个 candidate 多一个可选键 `original_title: str | None`；`text_trace["matched"]` 改为 raw 前 5 `[[qid, score, artist_ok]]`；`reason` 仍是 `no_candidates|not_in_catalog|low_confidence`。

- [ ] **Step 1: 写失败测试**

`test_vision.py` 追加（沿用该文件已有的假 `complete` 写法）：

```python
def test_original_title_passed_through():
    raw = '{"candidates":[{"title":"The Evening Air","original_title":"L\'Air du soir","artist":"Henri-Edmond Cross"}],"label_text":null,"self_confidence":"medium"}'
    out = identify("b64", complete=lambda s, u: raw)
    assert out["candidates"][0]["original_title"] == "L'Air du soir"


def test_prompts_ask_for_original_title():
    from app.services.recognition.vision import _ARTWORK_SYSTEM, _LABEL_SYSTEM

    assert "original_title" in _ARTWORK_SYSTEM and "original_title" in _LABEL_SYSTEM
```

`test_service.py` 追加（沿用该文件 `session` fixture 与假 `identify_fn` 的既有写法；先读 `test_text_path_event_keeps_vision_and_match_trace` 照抄调用方式）：

```python
def test_original_title_used_as_query(session):
    # AI 英文名对不上,但给了原文标题 → 能认出
    vis = {"candidates": [{"title": "The Beginning of the Earth", "original_title": "L'Origine du monde", "artist": "Gustave Courbet"}], "label_text": None, "self_confidence": "low"}
    out = _recognize_text(session, vis)  # 本文件里已有的文字链调用 helper;没有就照 test_text_path_event 写
    assert out["candidates"][0]["qid"] == "Q334138"


def test_reason_low_confidence_when_recalled_but_below_threshold(session):
    vis = {"candidates": [{"title": "Origin", "artist": None}], "label_text": None, "self_confidence": "low"}
    out = _recognize_text(session, vis)
    assert out["outcome"] == "unrecognized" and out["reason"] == "low_confidence"


def test_reason_not_in_catalog_when_nothing_recalled(session):
    vis = {"candidates": [{"title": "Pixelated House", "artist": "Unknown"}], "label_text": None, "self_confidence": "low"}
    out = _recognize_text(session, vis)
    assert out["reason"] == "not_in_catalog"
```

- [ ] **Step 2: 跑测试确认失败**

Run: `$PY -m pytest tests/unit/services/recognition/test_vision.py tests/unit/services/recognition/test_service.py -k "original_title or reason" -p no:cacheprovider --no-cov -q`
Expected: FAIL（无 `original_title`；`low_confidence` 断言失败——现在低分被挡在 match 里返回空 → `not_in_catalog`）

- [ ] **Step 3: 实现**

`vision.py` 两个提示词的 JSON 形状加字段：

```python
_ARTWORK_SYSTEM = (
    "You are a museum artwork recognizer. Look at the photo and try to identify the "
    "artwork. Your guesses are CANDIDATE QUERIES for a catalog search, not final answers "
    "— include up to 3 candidates even if unsure. For each candidate, if you know the "
    "artwork's title in its original language (e.g. the French title of a French "
    "painting), give it as original_title; otherwise null. Also transcribe any visible "
    "text in the frame (wall label, plaque) verbatim. Return STRICT JSON: "
    '{"candidates": [{"title": "...", "original_title": "... or null", "artist": "..."}], '
    '"label_text": "verbatim text or null", "self_confidence": "high|medium|low"}. '
    "No commentary."
)

_LABEL_SYSTEM = (
    "You are an OCR assistant. Transcribe ALL visible text in this photo of a museum "
    "wall label verbatim, preserving line breaks. Also extract the artwork title(s) "
    "and artist name(s) exactly as printed on the label (main artwork first, at most 3); "
    "if the label prints the same title in two languages, put the original-language one "
    "in original_title. Do NOT guess or add anything that is not printed. Return STRICT JSON: "
    '{"candidates": [{"title": "as printed", "original_title": "as printed or null", '
    '"artist": "as printed or null"}], '
    '"label_text": "verbatim text or null", '
    '"self_confidence": "high|medium|low"}. No commentary.'
)
```

`identify()` 解析处：

```python
            cands.append(
                {
                    "title": c["title"],
                    "original_title": c.get("original_title") or None,
                    "artist": c.get("artist"),
                }
            )
```

`service.py`：import 改为 `from app.services.recognition.matcher import LOW, build_index, inv_artist_hit, match_with_trace`；文字链：

```python
        queries = [c["title"] for c in vis["candidates"] if c.get("title")]
        # 原文标题(如法语原名)一起匹配:库里 13% 作品只有法语标题(spec §2.4)
        queries += [c["original_title"] for c in vis["candidates"] if c.get("original_title")]
        ...
            if inv_hit:
                results, raw = [(inv_hit, 1.0)], [[inv_hit, 1.0, True]]
            else:
                results, raw = match_with_trace(
                    index, queries, label_lines, artist_hints,
                    label_lines_inv_only=mode == "label" and bool(queries),
                )
            text_trace["matched"] = raw
            top = results[0] if results else None
            ...
            elif top and top[1] >= LOW:
                ...  # 不变
            elif raw:
                out["reason"] = "low_confidence"  # 有召回,但都不够门槛
            else:
                out["reason"] = "not_in_catalog"
```

- [ ] **Step 4: 跑识别全部测试，处理一条预期内的行为变化**

Run: `$PY -m pytest tests/unit/services/recognition tests/integration/test_recognize_flow.py -p no:cacheprovider --no-cov -q`
Expected: 除下面一条外全部 PASS（`test_text_path_event_keeps_vision_and_match_trace` 读 `tr["matched"][0][0]`，新格式第一个元素仍是 qid）。

`tests/integration/test_recognize_flow.py::test_mid_confidence_returns_candidates` 会 FAIL：它用 `"Origin of World painting"`、无作者，标题分实测 0.638——旧逻辑 ≥LOW(0.5) 出候选，新逻辑无作者要 ≥0.9 → `unrecognized/low_confidence`。**这是 spec §3.3 的有意变化**（评测里库外名作与垃圾输入的分数正落在 0.5–0.9 这段，靠它切掉 100%→20%/0% 的误报），不是 bug。改写为两条，并记 Ruling「候选档语义:无作者佐证的半对猜测不再出卡」：

```python
def test_mid_confidence_returns_candidates(...):  # 沿用原 fixture/调用方式
    # 半对的标题 + 作者对上 → 出候选(作者 ≥0.75 门槛)
    vis = {"candidates": [{"title": "Origin of the World study", "artist": "Gustave Courbet"}], ...}
    ...
    assert out["outcome"] == "candidates" and 0 < out["candidates"][0]["score"] <= 1


def test_half_right_title_without_artist_is_low_confidence(...):
    # spec §3.3:无作者佐证、标题分 <0.9 → 不出卡,诊断 low_confidence
    vis = {"candidates": [{"title": "Origin of World painting", "artist": None}], ...}
    ...
    assert out["outcome"] == "unrecognized" and out["reason"] == "low_confidence"
```

（先读原测试 118–140 行照抄 fixture 与调用；`"origin of the world study"` vs `"the origin of the world"` 的标题分在实现时实算一次，必须 ≥0.75，否则换成 `"The Origin of the World"` 并在注释说明。）其余测试有失败先查 bug，不准顺手改断言。

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/recognition/service.py backend/app/services/recognition/vision.py backend/tests/unit/services/recognition/test_service.py backend/tests/unit/services/recognition/test_vision.py
git commit -m "feat(recognize): 提示词要原文标题并一起匹配;trace 记原始前5,保住 low_confidence 诊断"
```

---

### Task 8: 识别评测进仓库（留出集门槛）

**Files:**
- Create: `backend/tests/eval/matching/test_recog_eval.py`

**Interfaces:**
- Consumes: `eval_index`、`HERE`（Task 5 conftest）；`recog_cases.json`（Task 5 生成）；`matcher.match`

- [ ] **Step 1: 写测试**

```python
# backend/tests/eval/matching/test_recog_eval.py
"""识别文字链回归门槛(spec §2.1/§7)。门槛只在偶数下标(调参半边)上定过;
这里只用奇数下标(留出半边)报数和断言。FLOOR 来自 Step 2 实测-3pp。"""

import collections
import json

from app.services.matching.normalize import normalize
from app.services.recognition.matcher import match
from tests.eval.matching.conftest import HERE

FLOOR_TOP3 = {}  # Step 2 填:{"exact": 0.97, "partial": 0.9, "typo": 0.97, "alias_missing": ...}
MAX_SHOWN = {"neg_junk": 0.0, "neg_famous": 0.34}


def test_recognition_holdout(eval_index):
    cases = json.load(open(HERE / "recog_cases.json", encoding="utf-8"))[1::2]
    pos = {e["qid"]: i for i, e in enumerate(eval_index)}
    for c in cases:  # 别名缺失:把目标件的英文名从索引里删掉
        if c.get("drop"):
            e = eval_index[pos[c["target"]]]
            e["names"] = e["names"] - {normalize(x) for x in c["drop"]}
    by = collections.defaultdict(lambda: [0, 0, 0])  # n, top3, shown
    for c in cases:
        r = match(eval_index, c["queries"], [], c["hints"])[:3]
        b = by[c["kind"]]
        b[0] += 1
        b[1] += any(q == c["target"] for q, _ in r)
        b[2] += bool(r)
    rate = {k: (t / n, s / n) for k, (n, t, s) in by.items()}
    for k, floor in FLOOR_TOP3.items():
        assert rate[k][0] >= floor, (k, rate[k])
    for k, cap in MAX_SHOWN.items():
        assert rate[k][1] <= cap, (k, rate[k])
    assert rate["label_bilingual"][0] == 1.0 if "label_bilingual" in rate else True
```

（`label_bilingual` 只有 1 条，可能落在偶数半边；Step 2 若 `rate` 里没有它，把该用例在 `recog_cases.json` 里挪到奇数位，记 Ruling。）

- [ ] **Step 2: 跑、记数、填门槛**

Run: `nice -n 19 $PY -m pytest tests/eval/matching/test_recog_eval.py -p no:cacheprovider --no-cov -q -s`
Expected: PASS。临时 print `rate` 拿实测数，填 `FLOOR_TOP3 = {k: round(v - 0.03, 2)}`（只填正例类），再跑 PASS。数字与 spec §2.1 留出集对照写进 ledger：同方向即可（样本目录比全量小，绝对值会不同）；若 `neg_junk` > 0 或 exact 进前 3 < 0.95，停下查原因。

- [ ] **Step 3: 本地全量目录一次（读，非 CI）**

用 scratchpad `run_proto.py` 的同一批用例，把打分换成仓库里的 `matcher.match`，对全量 27K 目录跑一次（单进程 nice），确认与 spec §2.1 原型列同量级（exact top3 ≥ 98%，junk 0%，p50 < 0.1s）。结果写进 ledger。

- [ ] **Step 4: Commit**

```bash
git add backend/tests/eval/matching/test_recog_eval.py backend/tests/eval/matching/recog_cases.json
git commit -m "test(recognize): 识别文字链评测进仓库(留出半边断言门槛)"
```

**PR2**：Task 6–8 → 全量后端测试绿 → `/pr` 到 staging → CI 绿 → 合 staging → staging 上用 10-06 的 Cross 墙签照片与一张垃圾图各打一次 `/recognize`（`mode=label` 与 artwork），看 `text_trace.matched` 与耗时 → 合 main 前先查 prod 有无长跑任务 → 上 prod 由用户点 → 上线后拉 `recognition_events` 对照前后（文字链 p50 目标 < 0.5s 的 `match` 段）。

---

### Task 9: 索引读 `match_aliases` + 导入器保留它

**Files:**
- Modify: `backend/app/services/search/inprocess.py`（`_build_global` 的 `names`）
- Modify: `backend/app/services/object_importer.py:74-76`
- Test: `backend/tests/unit/services/search/test_inprocess.py`（追加）、`backend/tests/unit/services/test_object_importer.py`（若不存在就新建，fixture 抄 test_inprocess 的 session）

**Interfaces:**
- Produces: 索引条目 `names` 含 `attributes.match_aliases` 里的每个串（归一化后）；`upsert_object` 重导入时 `attributes.match_aliases` 不丢。

- [ ] **Step 1: 写失败测试**

```python
# test_inprocess.py 追加
def test_match_aliases_searchable(session):
    m = session.query(Museum).filter_by(slug="orsay").one()
    upsert_object(session, m.id, {"qid": "Q_AIR", "title_en": "L'air du soir", "category": "painting",
                                  "attributes": {"match_aliases": ["The Evening Air"]}})
    session.commit()
    inprocess._index_cache.clear()
    idx = build_search_index(session, _mid(session))
    assert "Q_AIR" in {e["qid"] for e, _ in rank(idx, "evening air")}
```

```python
# test_object_importer.py
def test_upsert_preserves_match_aliases(session):
    m = session.query(Museum).filter_by(slug="orsay").one()
    o = upsert_object(session, m.id, {"qid": "Q_X", "title_en": "L'air du soir", "category": "painting",
                                      "attributes": {"title_i18n": {"fr": "L'Air du soir"}}})
    o.attributes = {**o.attributes, "match_aliases": ["The Evening Air"]}
    session.commit()
    upsert_object(session, m.id, {"qid": "Q_X", "title_en": "L'air du soir", "category": "painting",
                                  "attributes": {"title_i18n": {"fr": "L'Air du soir"}}})
    session.commit()
    assert session.query(MuseumObject).filter_by(qid="Q_X").one().attributes["match_aliases"] == ["The Evening Air"]
```

- [ ] **Step 2: 跑确认失败**

Run: `$PY -m pytest tests/unit/services/search/test_inprocess.py::test_match_aliases_searchable tests/unit/services/test_object_importer.py -p no:cacheprovider --no-cov -q`
Expected: 两个都 FAIL

- [ ] **Step 3: 实现**

`_build_global`：

```python
        names = {normalize(v) for v in title_i18n.values() if v}
        names |= {normalize(v) for v in attrs.get("match_aliases") or [] if v}  # 只用于匹配,不显示(spec §5)
```

`object_importer.upsert_object`：

```python
    keep = {k: v for k, v in (obj.attributes or {}).items() if k == "match_aliases"}
    obj.attributes = {
        **keep,  # 匹配别名是离线一次性生成的,重导入不能冲掉(spec §5)
        **{k: v for k, v in (art.get("attributes") or {}).items() if v is not None},
    }
```

- [ ] **Step 4: 跑确认通过 + 导入相关旧测试**

Run: `$PY -m pytest tests/unit/services -k "importer or inprocess or onboard" tests/unit/test_onboard_cli.py -p no:cacheprovider --no-cov -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/search/inprocess.py backend/app/services/object_importer.py backend/tests/unit/services/search/test_inprocess.py backend/tests/unit/services/test_object_importer.py
git commit -m "feat(matching): 索引收 attributes.match_aliases,重导入保留该键"
```

---

### Task 10: 别名生成脚本 `scripts/add_match_aliases.py`

**Files:**
- Create: `backend/scripts/add_match_aliases.py`
- Test: `backend/tests/unit/scripts/test_add_match_aliases.py`

**Interfaces:**
- Produces: `targets(db) -> list[MuseumObject]`（`title_i18n.en` 归一化 == `title_i18n.fr` 且无 `match_aliases`）；`translate_batch(titles: list[str], complete) -> list[str | None]`；`run(db, complete, apply: bool, backup: str | None, batch: int = 40) -> dict`（返回 `{"targets", "written", "same_as_source", "failed"}`）。

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/unit/scripts/test_add_match_aliases.py
import json

from scripts.add_match_aliases import run, targets, translate_batch
# session fixture:抄 tests/unit/services/search/test_inprocess.py 的 sqlite session,建 orsay 馆


def _add(session, qid, en, fr, aliases=None):
    from app.services.object_importer import upsert_object
    from app.models.museum import Museum

    m = session.query(Museum).filter_by(slug="orsay").one()
    attrs = {"title_i18n": {"en": en, "fr": fr}}
    if aliases:
        attrs["match_aliases"] = aliases
    upsert_object(session, m.id, {"qid": qid, "title_en": en, "category": "painting", "attributes": attrs})
    session.commit()


def fake_complete(system, user):
    titles = json.loads(user)
    table = {"L'Air du soir": "The Evening Air", "Sarah Bernhardt": "Sarah Bernhardt"}
    return json.dumps([table.get(t) for t in titles])


def test_targets_only_french_as_english(session):
    _add(session, "Q1", "L'air du soir", "L'Air du soir")
    _add(session, "Q2", "Luncheon on the Grass", "Le Déjeuner sur l'herbe")
    _add(session, "Q3", "L'air du soir", "L'Air du soir", aliases=["x"])  # 已有 → 跳过
    assert [o.qid for o in targets(session)] == ["Q1"]


def test_translate_batch_shape():
    assert translate_batch(["L'Air du soir"], fake_complete) == ["The Evening Air"]


def test_dry_run_writes_nothing(session):
    _add(session, "Q1", "L'air du soir", "L'Air du soir")
    rep = run(session, fake_complete, apply=False, backup=None)
    assert rep["targets"] == 1 and rep["written"] == 0
    assert "match_aliases" not in session.query(MuseumObject).filter_by(qid="Q1").one().attributes


def test_apply_writes_alias_and_skips_same_form(session, tmp_path):
    _add(session, "Q1", "L'air du soir", "L'Air du soir")
    _add(session, "Q4", "Sarah Bernhardt", "Sarah Bernhardt")
    bk = tmp_path / "bk.json"
    rep = run(session, fake_complete, apply=True, backup=str(bk))
    o1 = session.query(MuseumObject).filter_by(qid="Q1").one()
    assert o1.attributes["match_aliases"] == ["The Evening Air"]
    assert rep["same_as_source"] == 1  # 译文与原文同形 → 不写
    assert "match_aliases" not in session.query(MuseumObject).filter_by(qid="Q4").one().attributes
    saved = json.loads(bk.read_text())
    assert {r["qid"] for r in saved} == {"Q1", "Q4"}  # 备份=写入面全部行的原 attributes


def test_apply_is_idempotent(session):
    _add(session, "Q1", "L'air du soir", "L'Air du soir")
    run(session, fake_complete, apply=True, backup=None)
    assert run(session, fake_complete, apply=True, backup=None)["targets"] == 0
```

（文件顶部补 `from app.models.museum_object import MuseumObject` 与 sqlite `session` fixture。）

- [ ] **Step 2: 跑确认失败**

Run: `$PY -m pytest tests/unit/scripts/test_add_match_aliases.py -p no:cacheprovider --no-cov -q`
Expected: FAIL，`ModuleNotFoundError: No module named 'scripts.add_match_aliases'`

- [ ] **Step 3: 实现**

```python
# backend/scripts/add_match_aliases.py
"""一次性:给「英文标题其实是法语」的作品补英文匹配别名(spec §5)。

只写 museum_objects.attributes.match_aliases(只用于匹配,不显示);不碰标题、作者等共享实体、
不碰任何 audio_key。跑前 dry-run 看件数与样例;--apply 必带 --backup(写入面全部行的原
attributes)。幂等:已有 match_aliases 的件跳过。译文与原文归一化相同(人名/同形词)不写。

用法(容器内):
    python scripts/add_match_aliases.py                       # dry-run
    python scripts/add_match_aliases.py --apply --backup /tmp/match_aliases_backup.json
"""

import argparse
import json
import sys

sys.path.insert(0, "/app")

from sqlalchemy.orm.attributes import flag_modified  # noqa: E402

from app.core.database import SessionLocal  # noqa: E402
from app.models.museum_object import MuseumObject  # noqa: E402
from app.services.matching.normalize import normalize  # noqa: E402

_SYSTEM = (
    "Translate each French artwork title in the JSON array into the English title an "
    "English-speaking museum visitor would most likely use. Keep proper names as they are. "
    "Return ONLY a JSON array of strings, same length and order. No commentary."
)
MODEL = "gpt-4o-mini"


def targets(db):
    out = []
    for o in db.query(MuseumObject).order_by(MuseumObject.qid):
        a = o.attributes or {}
        ti = a.get("title_i18n") or {}
        if a.get("match_aliases") or not ti.get("fr") or not ti.get("en"):
            continue
        if normalize(ti["en"]) == normalize(ti["fr"]):
            out.append(o)
    return out


def translate_batch(titles, complete):
    try:
        data = json.loads(complete(_SYSTEM, json.dumps(titles, ensure_ascii=False)))
    except Exception:
        return [None] * len(titles)
    if not isinstance(data, list) or len(data) != len(titles):
        return [None] * len(titles)
    return [t if isinstance(t, str) and t.strip() else None for t in data]


def run(db, complete, apply, backup, batch=40):
    objs = targets(db)
    rep = {"targets": len(objs), "written": 0, "same_as_source": 0, "failed": 0}
    if backup:
        with open(backup, "w", encoding="utf-8") as f:
            json.dump([{"qid": o.qid, "attributes": o.attributes} for o in objs], f, ensure_ascii=False)
    for k in range(0, len(objs), batch):
        chunk = objs[k : k + batch]
        frs = [o.attributes["title_i18n"]["fr"] for o in chunk]
        for o, fr, en in zip(chunk, frs, translate_batch(frs, complete)):
            if en is None:
                rep["failed"] += 1
            elif normalize(en) == normalize(fr):
                rep["same_as_source"] += 1
            elif apply:
                o.attributes = {**o.attributes, "match_aliases": [en]}
                flag_modified(o, "attributes")
                rep["written"] += 1
            if not apply and k == 0:
                print(f"  {o.qid}: {fr!r} -> {en!r}")
        if apply:
            db.commit()
        if not apply:
            break  # dry-run 只译第一批看样例,不花全量的钱
    return rep


def _complete():
    import asyncio

    from app.services.content_generation_service import _get_openai_client
    from app.services.llm_usage import record_llm_usage

    client = _get_openai_client()

    def complete(system, user):
        async def _run():
            r = await client.chat.completions.create(
                model=MODEL, temperature=0,
                messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
                timeout=60,
            )
            u = r.usage
            record_llm_usage("names", MODEL, u.prompt_tokens if u else 0, u.completion_tokens if u else 0)
            return r.choices[0].message.content or ""

        return asyncio.run(_run())

    return complete


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--backup")
    args = ap.parse_args()
    if args.apply and not args.backup:
        sys.exit("--apply 必须带 --backup(纪律 37)")
    db = SessionLocal()
    try:
        print(run(db, _complete(), args.apply, args.backup))
    finally:
        db.close()
```

注：`test_dry_run_writes_nothing` 断言 `written == 0`——dry-run 分支不计 written，符合上面实现。`SessionLocal` 带音频损失闸（纪律 37 ⑦），本脚本不碰 audio_key，闸应静默；若它拦了，说明写入面判断错了，停下查。

- [ ] **Step 4: 跑确认通过**

Run: `$PY -m pytest tests/unit/scripts/test_add_match_aliases.py -p no:cacheprovider --no-cov -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/scripts/add_match_aliases.py backend/tests/unit/scripts/test_add_match_aliases.py
git commit -m "feat(scripts): 一次性补英文匹配别名(dry-run/备份/幂等/同形不写)"
```

---

### Task 11: PR3 上线与数据操作（运维，无新代码）

- [ ] **Step 1**：全量后端测试绿 → `/pr` 到 staging → CI 绿 → 合 staging（CD 自动部署 staging）。
- [ ] **Step 2：staging dry-run**：`ssh … docker exec gomuseum_staging_backend sh -c "cd /app && PYTHONPATH=/app python scripts/add_match_aliases.py"`。Expected：打印 targets ≈ staging 库对应数 + 第一批样例译文；读样例，译文离谱就改 `_SYSTEM` 回到 Task 10。
- [ ] **Step 3：staging apply**：带 `--backup /tmp/match_aliases_backup_staging.json`。Expected：`written + same_as_source + failed == targets`，`failed` < 2%；随后 `/search?q=evening air` 能搜到 L'Air du soir。
- [ ] **Step 4：prod 写入面清单（纪律 37）发给用户**：表=`museum_objects`；行=prod dry-run 打印的 targets 件（10-07 计 3,504）；列=`attributes` 仅新增键 `match_aliases`；共享实体=无；音频作废=0（不碰 sections/qa/artists）；备份=`/opt/gomuseum/backups/manual/match_aliases_<日期>.json`（脚本 `--backup` 写容器内路径后 `docker cp` 出来）；成本估 < $1。等用户执行或明确授权。合 main 前先查 prod 有无长跑任务。
- [ ] **Step 5：prod 执行后核对**：`select count(*) from museum_objects where attributes ? 'match_aliases'` 等于 written；`llm_usage` 当天 `names` 通道多出的调用数 ≈ targets/40；拉之后几天的 `recognition_events.text_trace` 看 `original_title` 与别名命中情况，写进 `docs/ops/backlog.md` 专题行并关闭该专题。

---

## Self-Review 记录

- Spec 覆盖：§3.1 索引→T3/T9；§3.2 召回→T3；§3.3 识别→T6；§3.3 reason→T7；§3.4 搜索→T4；§3.5 署名→T2；§4 提示词→T7；§5 数据→T9/T10/T11；§6 三个 PR→PR1/PR2/PR3 分界；§7 评测进仓库/留出集→T5/T8，单测反向样本分布在 T2/T4/T6/T7，署名逐条读→T2 Step 5，prod 实测→T8 Step 3 + PR2 说明；§8 不做→已在待办清单（spec 分支同提交）。
- 名称一致：`core_for`、`get_core`、`Core.and_hits`、`Core.recall`、`recognize`、`match_with_trace`、`same_person`、`is_artist_credit`、`_tier_scores`、`translate_batch` 在定义与使用处一致。
