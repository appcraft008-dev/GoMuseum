# 生成流程 Wikidata 单实体查询改走 Action API — 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 生成流程(懒生成 + 批量生成共用的 `generate_object`)里 6 个 Wikidata 单实体查询从 WDQS SPARQL 换成 Action API `wbgetentities`,数据逐字段等价,首屏准备阶段 ≤ 6s。

**Architecture:** 新客户端 `wikidata_api.get_entities`(批量 50、10s 超时、3 次重试含响应体 error 判定、进程级 2 并发闸)。每个函数拆三层:取数 → **转换**(实体 JSON → 与旧 SPARQL 结果同形的行)→ **解析**(旧逐行解析代码原样抽成 `_xxx_from_rows`)。旧 SPARQL 查询文本移入等价验证脚本作参照。

**Tech Stack:** Python 3.13、requests、pytest、SQLAlchemy(只读取样本)。

**Spec:** `docs/superpowers/specs/2026-10-10-wikidata-action-api-design.md`

## Global Constraints

- 工作区 `/Users/hongyang/Projects/GoMuseum-wdapi`,分支 `feature/wikidata-action-api`;命令在 `backend/` 下跑。
- Python:`PY=/Users/hongyang/Library/Caches/pypoetry/virtualenvs/gomuseum-backend-eWQPCnDy-py3.13/bin/python`;单测 `$PY -m pytest -q --no-cov <path>`;全套 `nice -n 19 $PY -m pytest -q --no-cov -p no:cacheprovider tests`。
- 格式:提交前 `$PY -m black -q <改动的 .py>`;Conventional Commits;提交信息结尾带会话给出的 Co-Authored-By / Claude-Session 两行。
- 只 `git add` 具体文件,不 `git add <dir>/`。
- **不动** 批量/目录类 SPARQL:`fetch_wikidata_labels_batch`、`backfill._fetch_creators`、`sources/wikidata.py`、`sources/wikidata_catalog.py`、`fetch_museum_building_photo`、`_default_artist_query`(后两者仍被它们使用)。
- 函数名、业务参数、返回结构不变;注入参数 `run_query` → `get_entities`(spec §2.2)。
- User-Agent 用 `sources/wikidata.USER_AGENT`;请求带 `maxlag=5`。
- **本计划不写任何 prod/staging 数据库。** 等价验证只读;61 件哈希作者清理只记待办。
- 解析函数(`_xxx_from_rows`)从旧函数体**原样**搬出,除 Task 4 明确删除的 P170 遍历分支外不改逻辑。

## Review Focus

1. 响应 HTTP 200 但正文是 `{"error": {"code": "maxlag"}}` → 必须重试,不能当空结果(Task 1 `test_maxlag_is_http_200_error_body_and_retried`)。
2. 值实体超过 50 个(蒙娜丽莎 P180 有 9 个、名作更多)→ 取名必须分批,不能 `toomanyvalues`(Task 1 `test_batches_ids_by_50_and_drops_missing`)。
3. Joconde 合成 id → 不发请求、返回空(Task 3 `test_resolve_creator_skips_non_wikidata_id`、Task 6 `test_fetch_rich_facts_skips_non_wikidata_id`)。
4. 作者解析里「同作者同 rank 同 cert 多条语句」的引用数归组相加会改变胜者(Task 3 `test_creator_refs_summed_across_duplicate_statements_changes_winner`)。
5. `artist_qid` 为空时作者资料/事实不再遍历 P170、不产出哈希作者(Task 4 `test_artist_facts_and_material_empty_without_artist_qid`)。

---

### Task 1: Action API 客户端

**Files:**
- Create: `backend/app/services/enrichment/wikidata_api.py`
- Test: `backend/tests/unit/services/enrichment/test_wikidata_api.py`

**Interfaces:**
- Produces:
  - `get_entities(ids, *, props: str, languages=None, http_get=requests.get, sleep=time.sleep) -> dict[str, dict]`(缺失实体不出现)
  - `class WikidataApiError(RuntimeError)`
  - `best_statements(entity: dict, pid: str) -> list[dict]`(spec §3.2 主值)
  - `entity_id(statement: dict) -> str | None`、`time_value(statement: dict) -> str | None`
  - `labels_of(ids, languages, fetch) -> dict[str, dict[str, str]]`

- [ ] **Step 1: 写失败测试**

`backend/tests/unit/services/enrichment/test_wikidata_api.py`:

```python
import threading
import time

import pytest

from app.services.enrichment import wikidata_api as wa


class _Resp:
    def __init__(self, status=200, body=None, headers=None):
        self.status_code = status
        self._body = body if body is not None else {}
        self.headers = headers or {}

    def json(self):
        return self._body

    def raise_for_status(self):
        if self.status_code >= 400:
            raise wa.requests.HTTPError(str(self.status_code))


def _seq(*resps):
    calls = []
    it = iter(resps)

    def get(url, params=None, headers=None, timeout=None):
        calls.append(params)
        return next(it)

    return get, calls


def _ok(ents):
    return _Resp(body={"entities": ents})


def test_sends_props_languages_maxlag_and_user_agent():
    seen = {}

    def get(url, params=None, headers=None, timeout=None):
        seen.update(url=url, params=params, headers=headers, timeout=timeout)
        return _ok({"Q1": {"id": "Q1"}})

    wa.get_entities(["Q1"], props="labels", languages=["en", "zh"], http_get=get)
    p = seen["params"]
    assert seen["url"] == "https://www.wikidata.org/w/api.php"
    assert p["action"] == "wbgetentities" and p["format"] == "json"
    assert p["ids"] == "Q1" and p["props"] == "labels" and p["languages"] == "en|zh"
    assert p["maxlag"] == 5 and seen["timeout"] == 10
    assert seen["headers"]["User-Agent"] == wa._wd.USER_AGENT


def test_batches_ids_by_50_and_drops_missing():
    sizes = []

    def get(url, params=None, headers=None, timeout=None):
        ids = params["ids"].split("|")
        sizes.append(len(ids))
        ents = {q: {"id": q} for q in ids}
        ents[ids[0]] = {"id": ids[0], "missing": ""}
        return _ok(ents)

    out = wa.get_entities(
        [f"Q{i}" for i in range(1, 121)], props="labels", http_get=get
    )
    assert sizes == [50, 50, 20]
    assert "Q1" not in out and "Q51" not in out and "Q101" not in out
    assert len(out) == 117


def test_429_retry_after_then_success():
    waits = []
    get, calls = _seq(_Resp(429, headers={"Retry-After": "3"}), _ok({"Q1": {}}))
    assert wa.get_entities(["Q1"], props="claims", http_get=get, sleep=waits.append) == {
        "Q1": {}
    }
    assert waits == [3.0] and len(calls) == 2


def test_maxlag_is_http_200_error_body_and_retried():
    waits = []
    get, calls = _seq(
        _Resp(body={"error": {"code": "maxlag", "info": "lagged"}}), _ok({"Q1": {}})
    )
    assert wa.get_entities(["Q1"], props="claims", http_get=get, sleep=waits.append) == {
        "Q1": {}
    }
    assert waits == [1.0] and len(calls) == 2


def test_other_error_body_raises_without_retry():
    get, calls = _seq(_Resp(body={"error": {"code": "toomanyvalues", "info": "x"}}))
    with pytest.raises(wa.WikidataApiError):
        wa.get_entities(["Q1"], props="claims", http_get=get, sleep=lambda s: None)
    assert len(calls) == 1


def test_200_without_entities_raises():
    get, _ = _seq(_Resp(body={"success": 1}))
    with pytest.raises(wa.WikidataApiError):
        wa.get_entities(["Q1"], props="claims", http_get=get, sleep=lambda s: None)


def test_gives_up_after_three_tries_with_backoff():
    waits = []
    get, calls = _seq(_Resp(503), _Resp(503), _Resp(503))
    with pytest.raises(wa.WikidataApiError):
        wa.get_entities(["Q1"], props="claims", http_get=get, sleep=waits.append)
    assert len(calls) == 3 and waits == [1.0, 2.0]


def test_timeout_is_retried():
    n = [0]

    def get(url, params=None, headers=None, timeout=None):
        n[0] += 1
        if n[0] == 1:
            raise wa.requests.Timeout()
        return _ok({})

    assert wa.get_entities(["Q1"], props="claims", http_get=get, sleep=lambda s: None) == {}
    assert n[0] == 2


def test_at_most_two_requests_in_flight():
    lock = threading.Lock()
    cur, peak = [0], [0]

    def get(url, params=None, headers=None, timeout=None):
        with lock:
            cur[0] += 1
            peak[0] = max(peak[0], cur[0])
        time.sleep(0.05)
        with lock:
            cur[0] -= 1
        return _ok({})

    ts = [
        threading.Thread(
            target=wa.get_entities, args=(["Q1"],), kwargs={"props": "claims", "http_get": get}
        )
        for _ in range(6)
    ]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    assert peak[0] == 2


def _st(value, rank="normal", snaktype="value", dtype="wikibase-entityid"):
    snak = {"snaktype": snaktype, "property": "P1"}
    if snaktype == "value":
        if dtype == "time":
            snak["datavalue"] = {"value": {"time": value}, "type": "time"}
        else:
            snak["datavalue"] = {
                "value": {"entity-type": "item", "id": value},
                "type": "wikibase-entityid",
            }
    return {"mainsnak": snak, "rank": rank}


def test_best_statements_preferred_only_if_any():
    e = {"claims": {"P1": [_st("Q1"), _st("Q2", rank="preferred"), _st("Q3", rank="deprecated")]}}
    assert [wa.entity_id(s) for s in wa.best_statements(e, "P1")] == ["Q2"]


def test_best_statements_normal_when_no_preferred_and_excludes_deprecated():
    e = {"claims": {"P1": [_st("Q1"), _st("Q3", rank="deprecated"), _st("Q4")]}}
    assert [wa.entity_id(s) for s in wa.best_statements(e, "P1")] == ["Q1", "Q4"]


def test_best_statements_drops_unknown_and_no_value():
    e = {"claims": {"P1": [_st(None, snaktype="somevalue"), _st(None, snaktype="novalue"), _st("Q5")]}}
    assert [wa.entity_id(s) for s in wa.best_statements(e, "P1")] == ["Q5"]
    assert wa.best_statements({}, "P1") == []


def test_time_value_and_entity_id_by_type():
    assert wa.time_value(_st("+1483-04-06T00:00:00Z", dtype="time")) == "+1483-04-06T00:00:00Z"
    assert wa.entity_id(_st("+1483-04-06T00:00:00Z", dtype="time")) is None
    assert wa.time_value(_st("Q1")) is None


def test_labels_of_maps_and_skips_empty():
    def fetch(ids, *, props, languages=None):
        assert props == "labels" and languages == ["en"]
        return {"Q1": {"labels": {"en": {"language": "en", "value": "France"}}}, "Q2": {}}

    assert wa.labels_of(["Q1", "Q2"], ["en"], fetch) == {"Q1": {"en": "France"}, "Q2": {}}
    assert wa.labels_of([], ["en"], fetch) == {}
```

- [ ] **Step 2: 跑测试确认失败**

Run: `$PY -m pytest -q --no-cov tests/unit/services/enrichment/test_wikidata_api.py`
Expected: FAIL / ERROR,`ModuleNotFoundError: app.services.enrichment.wikidata_api`

- [ ] **Step 3: 实现**

`backend/app/services/enrichment/wikidata_api.py`:

```python
"""Wikidata Action API(wbgetentities)单实体读取 —— 生成流程专用。

spec 2026-10-10-wikidata-action-api:生成流程里「查一个实体的几项属性」原先走 WDQS SPARQL,
负载高时卡满 60s 超时并静默丢资料(10-10 抽样:多语标题 5/28 超时)。wbgetentities 走缓存,
同批 28 件 p50 0.49s、最慢 0.67s、0 失败。批量/目录类查询仍走 SPARQL,不在此处。
"""

from __future__ import annotations

import logging
import threading
import time

import requests

from app.services.enrichment.sources import wikidata as _wd

logger = logging.getLogger(__name__)

API = "https://www.wikidata.org/w/api.php"
_BATCH = 50  # wbgetentities 匿名调用上限(超了返回 200 + error toomanyvalues)
_TIMEOUT = 10
_TRIES = 3
# ponytail: 进程级同时在途 ≤2(Wikimedia API 礼仪);prod 2 worker → ≤4。量大再上跨进程令牌。
_GATE = threading.BoundedSemaphore(2)


class WikidataApiError(RuntimeError):
    pass


def _retry_after(resp) -> float | None:
    try:
        v = resp.headers.get("Retry-After")
        return float(v) if v else None
    except (AttributeError, ValueError):
        return None


def _get(params: dict, http_get, sleep) -> dict:
    """一次 wbgetentities(带重试)。返回 entities 字典。

    ⚠️ 失败看两层:HTTP 状态,以及**响应体 error.code** —— maxlag/toomanyvalues 等是
    HTTP 200 + {"error": …}、没有 entities 键,只看状态码会当成「实体不存在」静默丢资料。
    """
    last: Exception | None = None
    for attempt in range(_TRIES):
        wait = float(2**attempt)  # 1s, 2s
        try:
            with _GATE:
                r = http_get(
                    API,
                    params=params,
                    headers={"User-Agent": _wd.USER_AGENT},
                    timeout=_TIMEOUT,
                )
            if r.status_code == 429 or r.status_code >= 500:
                last = WikidataApiError(f"HTTP {r.status_code}")
                wait = _retry_after(r) or wait
            else:
                r.raise_for_status()
                body = r.json()
                err = body.get("error")
                if err:
                    if err.get("code") != "maxlag":
                        raise WikidataApiError(f"{err.get('code')}: {err.get('info')}")
                    last = WikidataApiError("maxlag")
                    wait = _retry_after(r) or wait
                elif "entities" not in body:
                    raise WikidataApiError("response has no entities")
                else:
                    return body["entities"]
        except (requests.Timeout, requests.ConnectionError) as e:
            last = e
        if attempt < _TRIES - 1:
            sleep(wait)
    raise last if isinstance(last, WikidataApiError) else WikidataApiError(str(last))


def get_entities(
    ids, *, props: str, languages=None, http_get=requests.get, sleep=time.sleep
) -> dict[str, dict]:
    """wbgetentities。ids 按 50 个一批;返回 {qid: entity},缺失实体不出现。"""
    ids = list(dict.fromkeys(ids))
    out: dict[str, dict] = {}
    for i in range(0, len(ids), _BATCH):
        params = {
            "action": "wbgetentities",
            "format": "json",
            "maxlag": 5,
            "ids": "|".join(ids[i : i + _BATCH]),
            "props": props,
        }
        if languages:
            params["languages"] = "|".join(languages)
        for q, e in _get(params, http_get, sleep).items():
            if "missing" not in e:
                out[q] = e
    return out


def best_statements(entity: dict, pid: str) -> list[dict]:
    """spec §3.2 主值:排除 deprecated;有 preferred 只取 preferred,否则 normal(= SPARQL wdt:),
    另外只取 snaktype=value —— wdt: 会把「未知值」当 blank node 返回,这里故意收紧(修 §4.2)。"""
    sts = [
        s
        for s in ((entity or {}).get("claims") or {}).get(pid, [])
        if s.get("rank") != "deprecated"
    ]
    pref = [s for s in sts if s.get("rank") == "preferred"]
    return [s for s in (pref or sts) if (s.get("mainsnak") or {}).get("snaktype") == "value"]


def _datavalue(statement: dict) -> dict:
    snak = statement.get("mainsnak") or {}
    return (snak.get("datavalue") or {}) if snak.get("snaktype") == "value" else {}


def entity_id(statement: dict) -> str | None:
    dv = _datavalue(statement)
    return (dv.get("value") or {}).get("id") if dv.get("type") == "wikibase-entityid" else None


def time_value(statement: dict) -> str | None:
    dv = _datavalue(statement)
    return (dv.get("value") or {}).get("time") if dv.get("type") == "time" else None


def labels_of(ids, languages, fetch) -> dict[str, dict[str, str]]:
    """{qid: {lang: label}}(只含有的)。fetch = get_entities 或测试注入。"""
    ids = list(ids)
    if not ids:
        return {}
    ents = fetch(ids, props="labels", languages=list(languages))
    return {
        q: {lang: v["value"] for lang, v in (e.get("labels") or {}).items()}
        for q, e in ents.items()
    }
```

- [ ] **Step 4: 跑测试确认通过**

Run: `$PY -m pytest -q --no-cov tests/unit/services/enrichment/test_wikidata_api.py`
Expected: 14 passed

- [ ] **Step 5: 提交**

```bash
$PY -m black -q app/services/enrichment/wikidata_api.py tests/unit/services/enrichment/test_wikidata_api.py
git add app/services/enrichment/wikidata_api.py tests/unit/services/enrichment/test_wikidata_api.py
git commit -m "feat(enrichment): Wikidata Action API 客户端(批量50/响应体error判定/重试/2并发闸)"
```

---

### Task 2: 真实夹具 + 测试迁移工具 + 多语标题

**Files:**
- Create: `backend/tests/fixtures/wikidata/fetch_fixtures.py`、`backend/tests/fixtures/wikidata/entities.json`
- Create: `backend/tests/fixtures/wikidata/migrate_run_query_tests.py`(一次性迁移工具,Task 2–6 用,Task 8 删除)
- Modify: `backend/app/services/enrichment/material.py`(`fetch_wikidata_labels`)
- Test: `backend/tests/unit/services/enrichment/test_material.py`、`backend/tests/unit/services/enrichment/test_joconde_catalog.py`

**Interfaces:**
- Consumes: Task 1 `get_entities`
- Produces: `material._label_rows(entity) -> list[dict]`、`material._labels_from_rows(rows, langs) -> dict`、`fetch_wikidata_labels(qid, langs, *, get_entities=None)`;夹具加载 `tests/fixtures/wikidata/entities.json`(`{qid: entity}`)

- [ ] **Step 1: 抓真实夹具(只读 Wikidata,一次性)**

`backend/tests/fixtures/wikidata/fetch_fixtures.py`:

```python
"""一次性:从 Wikidata 实取并裁剪测试夹具(spec §6:夹具取真实返回,不手编)。
重跑会刷新数据,测试里的期望值以提交进库的 entities.json 为准。"""

import json
from pathlib import Path

import requests

UA = "GoMuseum/0.1 (enrichment; contact: dev@gomuseum.app)"
API = "https://www.wikidata.org/w/api.php"
LANGS = ["en", "fr", "de", "es", "it", "ja", "ko", "pt", "zh", "zh-hans", "zh-cn", "zh-hant", "zh-tw", "zh-hk"]
KEEP_PROPS = {"P170", "P569", "P570", "P27", "P800",
              "P88", "P180", "P186", "P135", "P136", "P1343", "P4969", "P144", "P941", "P361"}
FULL = ["Q64309678", "Q104479426", "Q12418", "Q35548", "Q5597"]


def get(ids, props, langs=None):
    p = {"action": "wbgetentities", "format": "json", "ids": "|".join(ids), "props": props}
    if langs:
        p["languages"] = "|".join(langs)
    r = requests.get(API, params=p, headers={"User-Agent": UA}, timeout=30)
    r.raise_for_status()
    return r.json()["entities"]


out = {}
for q, e in get(FULL, "labels|claims|sitelinks", LANGS).items():
    e["claims"] = {p: v for p, v in e.get("claims", {}).items() if p in KEEP_PROPS}
    e["sitelinks"] = {k: v for k, v in e.get("sitelinks", {}).items() if k in ("enwiki", "frwiki", "itwiki")}
    out[q] = e
value_ids = sorted({
    s["mainsnak"]["datavalue"]["value"]["id"]
    for e in out.values() for p, sts in e["claims"].items() if p != "P170"
    for s in sts
    if s["mainsnak"].get("snaktype") == "value" and s["mainsnak"]["datavalue"]["type"] == "wikibase-entityid"
})
for i in range(0, len(value_ids), 50):
    for q, e in get(value_ids[i:i + 50], "labels", LANGS).items():
        out.setdefault(q, {"id": q, "labels": e.get("labels", {})})
Path(__file__).with_name("entities.json").write_text(json.dumps(out, ensure_ascii=False, indent=1, sort_keys=True))
print(len(out), "entities")
```

Run: `cd backend && $PY tests/fixtures/wikidata/fetch_fixtures.py`
Expected: 打印 `N entities`(N ≈ 40–60),生成 `entities.json`。

然后核对夹具与本计划期望一致(数据若已被 Wikidata 改动,以夹具为准改后续测试期望,并在 ledger 记 Ruling):

```bash
$PY - <<'EOF'
import json
E = json.load(open("tests/fixtures/wikidata/entities.json"))
def st(q, p): return [(s["rank"], s["mainsnak"]["snaktype"], (s["mainsnak"].get("datavalue") or {}).get("value")) for s in E[q]["claims"].get(p, [])]
print(st("Q64309678", "P170"))       # 期望:两条 normal value,Q35548(P1480 Q18122778,1 引用)/ Q1369513(P1480 Q30230067,0 引用)
print(st("Q104479426", "P170"))      # 期望:[('normal','somevalue',None)]
print(st("Q35548", "P570"))          # 期望:normal +1906-10-22 与 deprecated +1906-10-23
print(st("Q5597", "P569")[:2])       # 期望:两条 preferred +1483-04-06 / +1483-03-28
print(st("Q5597", "P27"))            # 期望:normal Q12548 与 deprecated Q38
print(st("Q12418", "P186"))          # 期望:preferred Q296955、preferred Q106857865、normal Q287
print(len(st("Q12418", "P180")))     # 期望:9
print(E["Q142"]["labels"]["en"]["value"], E["Q35548"]["sitelinks"]["frwiki"]["title"])  # 期望:France Paul Cézanne
EOF
```

- [ ] **Step 2: 写测试迁移工具**

`backend/tests/fixtures/wikidata/migrate_run_query_tests.py`(用 ast 定位调用,把 `fn(..., run_query=<rows>)` 改为直接调解析函数;只处理没有 `artist_qid=` 关键字的调用;同时清理函数内因此不再使用的局部 import):

```python
"""一次性迁移:旧测试 fn(..., run_query=lambda s: ROWS) → 解析函数(ROWS[, langs])。
用法:python migrate_run_query_tests.py <file> <fn> [<fn>...]"""

import ast
import sys
from pathlib import Path

TARGET = {
    "fetch_wikidata_labels": ("_labels_from_rows", True),
    "fetch_artist_i18n_facts": ("_artist_i18n_from_rows", True),
    "resolve_creator_qid": ("_creator_from_rows", False),
    "fetch_artist_facts": ("_artist_facts_from_rows", False),
    "fetch_rich_facts": ("_rich_from_rows", False),
}


def offsets(src):
    starts, pos = [0], 0
    for line in src.splitlines(keepends=True):
        pos += len(line)
        starts.append(pos)
    return lambda ln, col: starts[ln - 1] + col


def main(path, fns):
    src = Path(path).read_text()
    off = offsets(src)
    tree = ast.parse(src)
    edits = []  # (start, end, text)
    # 只处理顶层测试函数(嵌套的 fake 函数里没有目标调用;ast.walk 嵌套会重复处理)
    for fdef in [n for n in tree.body if isinstance(n, ast.FunctionDef)]:
        replaced = []  # (call, new_name)
        for call in [n for n in ast.walk(fdef) if isinstance(n, ast.Call)]:
            name = getattr(call.func, "id", None)
            if name not in fns:
                continue
            kws = {k.arg: k.value for k in call.keywords}
            if "run_query" not in kws or "artist_qid" in kws:
                continue
            rq = kws["run_query"]
            if isinstance(rq, ast.Lambda):
                rows = ast.get_source_segment(src, rq.body)
            else:
                rows = f"{ast.get_source_segment(src, rq)}(None)"
            new, with_langs = TARGET[name]
            args = [rows]
            if with_langs:
                args.append(ast.get_source_segment(src, call.args[1]))
            edits.append(
                (
                    off(call.lineno, call.col_offset),
                    off(call.end_lineno, call.end_col_offset),
                    f"{new}({', '.join(args)})",
                )
            )
            replaced.append((call, new))
        if not replaced:
            continue
        skip = {id(c.func) for c, _ in replaced}
        for imp in [
            n
            for n in ast.walk(fdef)
            if isinstance(n, ast.ImportFrom)
            and (n.module or "").endswith(("material", "evidence"))
        ]:
            still = [
                a.name
                for a in imp.names
                if any(
                    isinstance(x, ast.Name) and x.id == a.name and id(x) not in skip
                    for x in ast.walk(fdef)
                )
            ]
            is_ev = imp.module.endswith("evidence")
            add = {nm for _, nm in replaced if (nm == "_rich_from_rows") == is_ev}
            final = sorted(set(still) | add)
            edits.append(
                (
                    off(imp.lineno, imp.col_offset),
                    off(imp.end_lineno, imp.end_col_offset),
                    f"from {imp.module} import {', '.join(final)}",
                )
            )
    for s, e, t in sorted(edits, reverse=True):
        src = src[:s] + t + src[e:]
    Path(path).write_text(src)
    print(f"{path}: {len(edits)} edits")


if __name__ == "__main__":
    main(sys.argv[1], set(sys.argv[2:]))
```

(迁移后用 black 格式化,并用 `git diff` 人工核对每处改动:调用改成解析函数、局部 import 只留仍在用的名字。)

- [ ] **Step 3: 迁移标题相关旧测试 + 写新测试**

```bash
$PY tests/fixtures/wikidata/migrate_run_query_tests.py tests/unit/services/enrichment/test_material.py fetch_wikidata_labels
$PY -m black -q tests/unit/services/enrichment/test_material.py
git diff tests/unit/services/enrichment/test_material.py
```

`test_fetch_labels_batch_matches_single_semantics` 里的单件调用会被改成 `_labels_from_rows([...], ["en", "zh"])`,核对它仍断言 `single == batch["Q12418"]`。

`tests/unit/services/enrichment/test_joconde_catalog.py:239` 手改:`run_query=_boom` → `get_entities=_boom`,并把 `_boom` 的签名改成 `def _boom(*a, **k):`。

在 `test_material.py` 末尾追加:

```python
import json as _json
from pathlib import Path as _Path

_E = _json.loads(
    (_Path(__file__).parents[3] / "fixtures" / "wikidata" / "entities.json").read_text()
)


def _fake_get(calls=None):
    def get(ids, *, props, languages=None):
        if calls is not None:
            calls.append((tuple(ids), props, tuple(languages or ())))
        return {q: _E[q] for q in ids if q in _E}

    return get


def test_fetch_wikidata_labels_real_shape_zh_variants():
    """真实夹具 Q35548(塞尚):zh 取 zh-hans→简体;zh-hant 链(无 zh-hant/zh-tw 时)取 zh 转繁,港式垫底。"""
    from app.services.enrichment.material import fetch_wikidata_labels

    calls = []
    out = fetch_wikidata_labels("Q35548", ["en", "zh", "zh-hant"], get_entities=_fake_get(calls))
    assert out["en"] == "Paul Cézanne"
    assert out["zh"] == _labels_expected_zh()
    assert calls[0][1] == "labels" and "zh-hans" in calls[0][2]


def _labels_expected_zh():
    from app.services.enrichment.material import _collapse_variants

    raw = {k: v["value"] for k, v in _E["Q35548"]["labels"].items()}
    return _collapse_variants(raw, ["zh"])["zh"]


def test_label_rows_match_sparql_shape():
    from app.services.enrichment.material import _label_rows

    rows = _label_rows(_E["Q35548"])
    assert {"l": {"xml:lang": "en", "value": "Paul Cézanne"}} in rows
```

- [ ] **Step 4: 跑测试确认失败**

Run: `$PY -m pytest -q --no-cov tests/unit/services/enrichment/test_material.py tests/unit/services/enrichment/test_joconde_catalog.py`
Expected: FAIL,`ImportError: cannot import name '_labels_from_rows'` / `_label_rows`

- [ ] **Step 5: 实现**

`material.py` 顶部 import 区加:

```python
from app.services.enrichment import wikidata_api as _wa
```

把 `fetch_wikidata_labels` 整个替换为:

```python
def _label_rows(entity: dict) -> list[dict]:
    """转换层:实体 labels → 与旧 _LABELS_QUERY 同形的行(spec §2.2)。"""
    return [
        {"l": {"xml:lang": v["language"], "value": v["value"]}}
        for v in ((entity or {}).get("labels") or {}).values()
    ]


def _labels_from_rows(rows, langs: list) -> dict:
    """解析层(原 fetch_wikidata_labels 逐行解析,原样搬出)。"""
    raw: dict = {}
    for row in rows:
        lv = row.get("l") or {}
        lang = lv.get("xml:lang") or lv.get("lang")
        val = lv.get("value")
        if lang and val and lang not in raw:
            raw[lang] = val
    return _collapse_variants(raw, langs)


def fetch_wikidata_labels(qid: str, langs: list, *, get_entities=None) -> dict:
    """Wikidata 实体在 langs 的官方标签 → {lang: label}(只含有的)。
    zh 按 zh-hans > zh-cn > zh 取(修繁简混杂:愛德華·馬奈类)。
    非 Wikidata 对外把手(joconde-<ref> 等)→ 直接 {}(无真 QID,names 回退机翻 title_en)。"""
    from app.services.enrichment.identity import is_wikidata_qid

    if not is_wikidata_qid(qid):
        return {}
    get_entities = get_entities or _wa.get_entities
    ent = get_entities([qid], props="labels", languages=_query_langs(langs)).get(qid)
    return _labels_from_rows(_label_rows(ent), langs)
```

`_LABELS_QUERY` 常量保留到 Task 7(验证脚本要用)。

- [ ] **Step 6: 跑测试确认通过**

Run: `$PY -m pytest -q --no-cov tests/unit/services/enrichment/test_material.py tests/unit/services/enrichment/test_joconde_catalog.py`
Expected: 全部 passed

- [ ] **Step 7: 提交**

```bash
$PY -m black -q app/services/enrichment/material.py tests/unit/services/enrichment/test_material.py tests/unit/services/enrichment/test_joconde_catalog.py tests/fixtures/wikidata/fetch_fixtures.py tests/fixtures/wikidata/migrate_run_query_tests.py
git add app/services/enrichment/material.py tests/unit/services/enrichment/test_material.py tests/unit/services/enrichment/test_joconde_catalog.py tests/fixtures/wikidata/fetch_fixtures.py tests/fixtures/wikidata/migrate_run_query_tests.py tests/fixtures/wikidata/entities.json
git commit -m "refactor(enrichment): 多语标题改走 wbgetentities(转换成旧行、复用旧解析)+ 真实夹具"
```

---

### Task 3: 作者解析

**Files:**
- Modify: `backend/app/services/enrichment/material.py`(`resolve_creator_qid`)
- Test: `backend/tests/unit/services/enrichment/test_material.py`

**Interfaces:**
- Consumes: Task 1 `entity_id`;Task 2 `_E`、`_fake_get`(测试)
- Produces: `material._creator_rows(entity) -> list[dict]`、`material._creator_from_rows(rows) -> str | None`、`resolve_creator_qid(qid, *, get_entities=None) -> str | None`

- [ ] **Step 1: 迁移旧测试 + 写新测试**

```bash
$PY tests/fixtures/wikidata/migrate_run_query_tests.py tests/unit/services/enrichment/test_material.py resolve_creator_qid
$PY -m black -q tests/unit/services/enrichment/test_material.py && git diff tests/unit/services/enrichment/test_material.py
```

(`test_resolve_creator_prefers_better_sourced_claim` / `rank_beats_qualifier` / `skips_blank_node_and_deprecated` 变为调 `_creator_from_rows(rows)`;`test_fetch_creators_batch_picks_same_winner_as_single` 不涉及,不变。)

追加:

```python
import copy as _copy


def _p170(aq, rank="normal", certs=(), refs=0, snaktype="value"):
    """按真实夹具形状造 P170 语句(形状由 test_p170_helper_matches_real_shape 钉住)。"""
    st = _copy.deepcopy(_E["Q64309678"]["claims"]["P170"][0])
    st["rank"] = rank
    st["mainsnak"]["snaktype"] = snaktype
    if snaktype == "value":
        st["mainsnak"]["datavalue"]["value"]["id"] = aq
        st["mainsnak"]["datavalue"]["value"]["numeric-id"] = int(aq[1:])
    else:
        st["mainsnak"].pop("datavalue", None)
    q0 = _copy.deepcopy(_E["Q64309678"]["claims"]["P170"][0]["qualifiers"]["P1480"][0])
    quals = []
    for kind, val in certs:
        q = _copy.deepcopy(q0)
        q["snaktype"] = kind
        if kind == "value":
            q["datavalue"]["value"]["id"] = val
        else:
            q.pop("datavalue", None)
        quals.append(q)
    st["qualifiers"] = {"P1480": quals} if quals else {}
    ref0 = _E["Q64309678"]["claims"]["P170"][0]["references"][0]
    st["references"] = [_copy.deepcopy(ref0) for _ in range(refs)]
    return st


def _work(*sts):
    return {"Qw": {"id": "Qw", "claims": {"P170": list(sts)}}}


def _resolve(ents):
    from app.services.enrichment.material import resolve_creator_qid

    return resolve_creator_qid("Qw", get_entities=lambda ids, **k: ents)


def test_p170_helper_matches_real_shape():
    real = _E["Q64309678"]["claims"]["P170"][0]
    made = _p170("Q35548", certs=[("value", "Q18122778")], refs=1)
    assert made["mainsnak"] == real["mainsnak"]
    assert made["qualifiers"]["P1480"][0]["datavalue"] == real["qualifiers"]["P1480"][0]["datavalue"]


def test_resolve_creator_real_q64309678_prefers_cezanne():
    from app.services.enrichment.material import resolve_creator_qid

    assert resolve_creator_qid("Q64309678", get_entities=_fake_get()) == "Q35548"


def test_resolve_creator_real_unknown_value_is_none():
    from app.services.enrichment.material import resolve_creator_qid

    assert resolve_creator_qid("Q104479426", get_entities=_fake_get()) is None


def test_creator_refs_summed_across_duplicate_statements_changes_winner():
    """spec §3.1:同作者同 rank 同 cert 两条语句(2、3 条引用)→ 一个 refs=5 候选,胜过 refs=4 的 B。
    若不相加,A 最多 3 < 4,胜者会变成 B。"""
    ents = _work(_p170("Q1", refs=2), _p170("Q1", refs=3), _p170("Q2", refs=4))
    assert _resolve(ents) == "Q1"


def test_creator_multi_p1480_on_one_statement_uses_best():
    ents = _work(
        _p170("Q1", certs=[("value", "Q30230067"), ("value", "Q18122778")]),  # possibly + presumably
        _p170("Q2", certs=[("value", "Q30230067")], refs=5),  # possibly
    )
    assert _resolve(ents) == "Q1"


def test_creator_p1480_unknown_value_ranks_between_presumably_and_possibly():
    ents = _work(_p170("Q1", certs=[("somevalue", None)]), _p170("Q2", certs=[("value", "Q30230067")]))
    assert _resolve(ents) == "Q1"
    ents = _work(_p170("Q1", certs=[("somevalue", None)]), _p170("Q3", certs=[("value", "Q18122778")]))
    assert _resolve(ents) == "Q3"


def test_creator_p1480_novalue_counts_as_no_qualifier():
    ents = _work(_p170("Q1", certs=[("novalue", None)]), _p170("Q2", certs=[("value", "Q18122778")], refs=9))
    assert _resolve(ents) == "Q1"


def test_creator_deprecated_and_unknown_statements_excluded():
    ents = _work(_p170("Q1", rank="deprecated", refs=9), _p170(None, snaktype="somevalue"), _p170("Q2"))
    assert _resolve(ents) == "Q2"


def test_resolve_creator_skips_non_wikidata_id():
    from app.services.enrichment.material import resolve_creator_qid

    def boom(*a, **k):
        raise AssertionError("不该对非 Wikidata 编号发请求")

    assert resolve_creator_qid("joconde-00000089446", get_entities=boom) is None
```

- [ ] **Step 2: 跑测试确认失败**

Run: `$PY -m pytest -q --no-cov tests/unit/services/enrichment/test_material.py -k "creator or p170"`
Expected: FAIL,`cannot import name '_creator_from_rows'` 与 `unexpected keyword argument 'get_entities'`

- [ ] **Step 3: 实现**

`material.py` 里把 `resolve_creator_qid` 整个替换为(`_CREATOR_QUERY`、`creator_candidate` 保留不动):

```python
_ENTITY_IRI = "http://www.wikidata.org/entity/"
_RANK_IRI = {
    "preferred": "PreferredRank",
    "normal": "NormalRank",
    "deprecated": "DeprecatedRank",
}


def _creator_rows(entity: dict) -> list[dict]:
    """转换层:P170 语句 → 与旧 _CREATOR_QUERY 同形的行(spec §3.1)。

    旧 SPARQL 对同一语句的 P1480 × 引用交叉相乘,再按 (artist, rank, cert) 分组 COUNT(?ref):
    同组多条语句的引用数**相加**;一条语句多个 P1480 各成一组。P1480 本身是「未知值」时
    旧查询绑到 blank node → creator_candidate 视为未知限定词(_CERT_UNKNOWN),这里用非 QID
    占位值复现;P1480「无值」旧查询不绑定 → 等同无限定。作者本身未知/无值 → 不产行。"""
    groups: dict = {}
    for st in ((entity or {}).get("claims") or {}).get("P170", []):
        aq = _wa.entity_id(st)
        if not aq:
            continue
        certs = []
        for q in (st.get("qualifiers") or {}).get("P1480", []):
            if q.get("snaktype") == "value":
                certs.append(q["datavalue"]["value"]["id"])
            elif q.get("snaktype") == "somevalue":
                certs.append("somevalue")
        rank = _RANK_IRI.get(st.get("rank"), "NormalRank")
        refs = len(st.get("references") or [])
        for cert in certs or [None]:
            groups[(aq, rank, cert)] = groups.get((aq, rank, cert), 0) + refs
    rows = []
    for (aq, rank, cert), n in groups.items():
        row = {
            "artist": {"value": _ENTITY_IRI + aq},
            "rank": {"value": "http://wikiba.se/ontology#" + rank},
            "refs": {"value": str(n)},
        }
        if cert:
            row["cert"] = {"value": _ENTITY_IRI + cert}
        rows.append(row)
    return rows


def _creator_from_rows(rows) -> str | None:
    """解析层(原 resolve_creator_qid 的择优,原样搬出)。"""
    cands = [c for c in (creator_candidate(r) for r in rows or []) if c]
    return min(cands)[1] if cands else None


def resolve_creator_qid(qid, *, get_entities=None) -> str | None:
    """作品 QID → **唯一**作者 QID。多值时按 (rank, 不确定性限定词, 引用数) 择优。

    全流程只应调这一次,结果传给 fetch_artist_facts / fetch_artist_material。
    无作者、或 P170 是"未知值"→ None(宁缺毋滥,不猜)。非 Wikidata 编号 → None,不发请求。
    """
    from app.services.enrichment.identity import is_wikidata_qid

    if not is_wikidata_qid(qid):
        return None
    get_entities = get_entities or _wa.get_entities
    ent = get_entities([qid], props="claims").get(qid)
    return _creator_from_rows(_creator_rows(ent))
```

- [ ] **Step 4: 跑测试确认通过**

Run: `$PY -m pytest -q --no-cov tests/unit/services/enrichment/test_material.py tests/integration/test_backfill_names.py`
Expected: 全部 passed

- [ ] **Step 5: 提交**

```bash
$PY -m black -q app/services/enrichment/material.py tests/unit/services/enrichment/test_material.py
git add app/services/enrichment/material.py tests/unit/services/enrichment/test_material.py
git commit -m "refactor(enrichment): 作者解析改走 wbgetentities(引用数按 (artist,rank,cert) 归组,复用 creator_candidate)"
```

---

### Task 4: 作者资料 + 作者事实(去掉 P170 遍历)

**Files:**
- Modify: `backend/app/services/enrichment/material.py`(`fetch_artist_material`、`fetch_artist_facts`)
- Test: `backend/tests/unit/services/enrichment/test_material.py`

**Interfaces:**
- Consumes: Task 1 `best_statements`、`entity_id`、`time_value`、`labels_of`
- Produces: `material._artist_fact_rows(entity, fetch) -> list[dict]`、`material._artist_facts_from_rows(rows, artist_qid=None) -> dict`、`fetch_artist_facts(qid, *, get_entities=None, artist_qid=None)`、`fetch_artist_material(qid, registry, *, get_entities=None, country_lang="fr", artist_qid=None)`

- [ ] **Step 1: 迁移旧测试 + 写新测试**

```bash
$PY tests/fixtures/wikidata/migrate_run_query_tests.py tests/unit/services/enrichment/test_material.py fetch_artist_facts
```

然后手改 `test_material.py`:
- 删除 `test_fetch_artist_facts_returns_artist_qid`(P170 遍历分支被删,spec §4.1)。
- 删除 `test_fetch_artist_facts_with_artist_qid_does_not_traverse_p170`、`test_fetch_artist_material_with_artist_qid_does_not_traverse_p170`、`test_fetch_artist_material_empty_when_no_artist`(由下面新测试取代)。
- `test_fetch_artist_material_via_injected_query` 改为:

```python
def test_fetch_artist_material_uses_sitelink_titles():
    from app.services.enrichment.material import fetch_artist_material

    seen = {}

    class _Wiki(Source):
        name = "wikipedia"

        def fetch(self, cfg):
            return []

        def enrich(self, qid, ext, ctx):
            seen["titles"] = ctx.get("wiki_titles")
            return ObjectContribution(source="wikipedia", qid=qid, fields={"extract_en": "bio"}, raw={})

    calls = []
    out = fetch_artist_material(
        "Q64309678", SourceRegistry([_Wiki()]), get_entities=_fake_get(calls), country_lang="fr", artist_qid="Q35548"
    )
    assert seen["titles"] == {"en": "Paul Cézanne", "fr": "Paul Cézanne"}
    assert out == {"artist_extract_en": "bio"}
    assert calls == [(("Q35548",), "sitelinks", ())]
```

追加:

```python
def test_artist_facts_and_material_empty_without_artist_qid():
    """spec §2.2/§4.1:artist_qid 为空 = 无作者或故意弃权,不再遍历 P170(哈希作者的来源)。"""
    from app.services.enrichment.material import fetch_artist_facts, fetch_artist_material

    def boom(*a, **k):
        raise AssertionError("artist_qid 为空时不该发请求")

    assert fetch_artist_facts("Q104479426", get_entities=boom) == {}
    assert fetch_artist_material("Q104479426", SourceRegistry([]), get_entities=boom) == {}


def test_fetch_artist_facts_real_cezanne_skips_deprecated_death():
    from app.services.enrichment.material import fetch_artist_facts

    f = fetch_artist_facts("Q64309678", get_entities=_fake_get(), artist_qid="Q35548")
    assert f["artist_qid"] == "Q35548"
    assert f["artist_birth"] == "1839" and f["artist_death"] == "1906"
    assert f["artist_nationality"] == "France"
    expected = [
        _E[s["mainsnak"]["datavalue"]["value"]["id"]]["labels"]["en"]["value"]
        for s in _E["Q35548"]["claims"]["P800"]
        if s["rank"] != "deprecated" and _E.get(s["mainsnak"]["datavalue"]["value"]["id"], {}).get("labels", {}).get("en")
    ][:5]
    assert f["artist_notable_works"] == expected


def test_fetch_artist_facts_real_raphael_tied_preferred_and_deprecated_nationality():
    """拉斐尔:P569 两条 preferred(同为 1483),P27 normal 意大利城邦 + deprecated Q38 → 取第一条、排除 deprecated。"""
    from app.services.enrichment.material import fetch_artist_facts

    f = fetch_artist_facts("Qx", get_entities=_fake_get(), artist_qid="Q5597")
    assert f["artist_birth"] == "1483" and f["artist_death"] == "1520"
    assert f["artist_nationality"] == _E["Q12548"]["labels"]["en"]["value"]


def test_fetch_artist_facts_unknown_birth_not_stored_as_http():
    """spec §4.2:生年是「未知值」时不再存成 'http'。"""
    from app.services.enrichment.material import fetch_artist_facts

    art = _copy.deepcopy(_E["Q35548"])
    art["claims"]["P569"][0]["mainsnak"]["snaktype"] = "somevalue"
    art["claims"]["P569"][0]["mainsnak"].pop("datavalue")
    f = fetch_artist_facts("Qx", get_entities=lambda ids, **k: {"Q35548": art, **{q: _E[q] for q in ids if q in _E and q != "Q35548"}}, artist_qid="Q35548")
    assert "artist_birth" not in f and f["artist_death"] == "1906"


def test_artist_fact_rows_fill_raw_qid_when_no_english_label():
    from app.services.enrichment.material import _artist_fact_rows

    art = {"claims": {"P800": [_copy.deepcopy(_E["Q35548"]["claims"]["P800"][0])]}}
    art["claims"]["P800"][0]["mainsnak"]["datavalue"]["value"]["id"] = "Q999999999"
    rows = _artist_fact_rows(art, lambda ids, **k: {})
    assert rows == [{"workLabel": {"value": "Q999999999"}}]
```

- [ ] **Step 2: 跑测试确认失败**

Run: `$PY -m pytest -q --no-cov tests/unit/services/enrichment/test_material.py -k "artist_facts or artist_material or fact_rows"`
Expected: FAIL(`cannot import name '_artist_facts_from_rows'` / `_artist_fact_rows`、`unexpected keyword argument 'get_entities'`)

- [ ] **Step 3: 实现**

`fetch_artist_material` 替换为:

```python
def fetch_artist_material(
    qid, registry, *, get_entities=None, country_lang="fr", artist_qid=None
) -> dict:
    """抓作者实体 Wikipedia(作者→维基条目名→extract)。无作者/无维基→{}。

    artist_qid 必须由 resolve_creator_qid 先定好;为空 = 无作者或故意弃权 → {}
    (不再遍历 P170,spec §2.2/§4)。条目名直接用 sitelinks 完整 title(旧实现 rsplit("/")
    会截断含 / 的条目名,spec §4.3)。
    """
    if not artist_qid:
        return {}
    get_entities = get_entities or _wa.get_entities
    cl = country_lang or "fr"
    ent = get_entities([artist_qid], props="sitelinks").get(artist_qid) or {}
    sl = ent.get("sitelinks") or {}
    titles = {}
    if (sl.get("enwiki") or {}).get("title"):
        titles["en"] = sl["enwiki"]["title"]
    if (sl.get(f"{cl}wiki") or {}).get("title"):
        titles[cl] = sl[f"{cl}wiki"]["title"]
    if not titles:
        return {}
    wiki = registry.get("wikipedia")
    if wiki is None:
        return {}
    contrib = wiki.enrich(qid, {}, {"wiki_titles": titles})
    if contrib is None:
        return {}
    return {
        f"artist_{k}": v
        for k, v in contrib.fields.items()
        if k.startswith("extract_") and v
    }
```

`fetch_artist_facts` 替换为(下面的 `_artist_facts_from_rows` 是旧循环原样搬出,只删掉 `if "artist_qid" not in out:` 那个遍历分支):

```python
def _wd_time(t: str) -> str:
    """wbgetentities 的 '+1483-04-06T…' → SPARQL 同形 '1483-04-06T…'(旧解析取 [:4])。"""
    return t[1:] if t.startswith("+") else t


def _artist_fact_rows(entity: dict, fetch) -> list[dict]:
    """转换层:作者实体 → 与旧 _ARTIST_FACTS_BY_ARTIST_QUERY 同形的行。
    主值规则见 wikidata_api.best_statements;无英文名的值填原始 QID(旧 label 服务行为,
    解析层 _is_raw_qid 照旧过滤)。"""
    births = [t for t in map(_wa.time_value, _wa.best_statements(entity, "P569")) if t]
    deaths = [t for t in map(_wa.time_value, _wa.best_statements(entity, "P570")) if t]
    nats = [q for q in map(_wa.entity_id, _wa.best_statements(entity, "P27")) if q]
    works = [q for q in map(_wa.entity_id, _wa.best_statements(entity, "P800")) if q]
    en = _wa.labels_of(list(dict.fromkeys(nats + works)), ["en"], fetch)

    def lab(q):
        return (en.get(q) or {}).get("en") or q

    cols = {
        "birth": [_wd_time(t) for t in births],
        "death": [_wd_time(t) for t in deaths],
        "natLabel": [lab(q) for q in nats],
        "workLabel": [lab(q) for q in works],
    }
    n = max((len(v) for v in cols.values()), default=0)
    return [{k: {"value": v[i]} for k, v in cols.items() if i < len(v)} for i in range(n)]


def _artist_facts_from_rows(rows, artist_qid=None) -> dict:
    """解析层(原 fetch_artist_facts 逐行解析;删去 P170 遍历的 artist 列分支,spec §4.1)。"""
    if not rows:
        return {"artist_qid": artist_qid} if artist_qid else {}
    out = {"artist_qid": artist_qid} if artist_qid else {}
    works = []
    for row in rows:
        b = (row.get("birth") or {}).get("value")
        d = (row.get("death") or {}).get("value")
        nat = (row.get("natLabel") or {}).get("value")
        w = (row.get("workLabel") or {}).get("value")
        # 标签服务对无本地化标签的实体退回原始 QID → 无意义,跳过
        if nat and _is_raw_qid(nat):
            nat = None
        if w and _is_raw_qid(w):
            w = None
        if b and "artist_birth" not in out:
            out["artist_birth"] = b[:4]
        if d and "artist_death" not in out:
            out["artist_death"] = d[:4]
        if nat and "artist_nationality" not in out:
            out["artist_nationality"] = nat
        if w and w not in works:
            works.append(w)
    if works:
        out["artist_notable_works"] = works[:5]
    return out


def fetch_artist_facts(qid, *, get_entities=None, artist_qid=None) -> dict:
    """作者 Wikidata 实体结构化属性 → {artist_birth/death/nationality/notable_works}。

    artist_qid 必须由 resolve_creator_qid 定好;为空 → {}。旧实现为空时遍历作品 P170,
    「未知值」的 blank node 哈希会被当作者 QID 写回(prod 61 件假作者卡,spec §4.1)。
    """
    if not artist_qid:
        return {}
    get_entities = get_entities or _wa.get_entities
    ent = get_entities([artist_qid], props="claims").get(artist_qid) or {}
    return _artist_facts_from_rows(_artist_fact_rows(ent, get_entities), artist_qid)
```

迁移后的旧测试 `test_fetch_artist_facts_empty_on_no_rows` 现在调 `_artist_facts_from_rows([])`,期望 `{}` 不变。

- [ ] **Step 4: 跑测试确认通过**

Run: `$PY -m pytest -q --no-cov tests/unit/services/enrichment/test_material.py tests/integration/test_generate_pipeline.py`
Expected: 全部 passed。若 `test_generate_pipeline.py` 里 `fake_artist_material(qid, registry, *, run_query=None, …)` 失败,把形参 `run_query=None` 改为 `get_entities=None`。

- [ ] **Step 5: 提交**

```bash
$PY -m black -q app/services/enrichment/material.py tests/unit/services/enrichment/test_material.py tests/integration/test_generate_pipeline.py
git add app/services/enrichment/material.py tests/unit/services/enrichment/test_material.py tests/integration/test_generate_pipeline.py
git commit -m "refactor(enrichment): 作者资料/事实改走 wbgetentities;去掉 P170 遍历(堵假作者卡)"
```

---

### Task 5: 作者国籍/代表作多语名

**Files:**
- Modify: `backend/app/services/enrichment/material.py`(`fetch_artist_i18n_facts`)
- Test: `backend/tests/unit/services/enrichment/test_material.py`

**Interfaces:**
- Consumes: Task 1 `best_statements`、`entity_id`、`labels_of`
- Produces: `material._artist_i18n_rows(entity, wanted, fetch) -> list[dict]`、`material._artist_i18n_from_rows(rows, langs) -> dict`、`fetch_artist_i18n_facts(artist_qid, langs, *, get_entities=None)`

- [ ] **Step 1: 迁移旧测试 + 写新测试**

```bash
$PY tests/fixtures/wikidata/migrate_run_query_tests.py tests/unit/services/enrichment/test_material.py fetch_artist_i18n_facts
```

删除 `test_artist_i18n_query_selects_every_binding_the_parser_reads`(查询移入验证脚本;它防的「转换出的行缺 work 字段」由下面真实夹具测试覆盖)。追加:

```python
def test_fetch_artist_i18n_real_cezanne_same_works_every_language():
    from app.services.enrichment.material import fetch_artist_i18n_facts

    calls = []
    out = fetch_artist_i18n_facts("Q35548", ["en", "zh", "zh-hant"], get_entities=_fake_get(calls))
    assert out["nationality_i18n"]["en"] == "France"
    assert out["nationality_i18n"]["zh"] == "法国"
    en, zh = out["notable_works_i18n"]["en"], out["notable_works_i18n"]["zh"]
    assert len(en) == len(zh) == len(out["notable_works_labels"]) <= 5
    assert "Mont Sainte-Victoire" in en and "圣维克多山" in zh
    assert calls[0][1] == "claims" and calls[1][1] == "labels" and "zh-hans" in calls[1][2]


def test_artist_i18n_rows_carry_work_qid_for_grouping():
    from app.services.enrichment.material import _artist_i18n_rows

    rows = _artist_i18n_rows(_E["Q35548"], ["en"], _fake_get())
    work_rows = [r for r in rows if "work" in r]
    assert work_rows and all(r["work"]["value"].startswith("http://www.wikidata.org/entity/Q") for r in work_rows)
```

- [ ] **Step 2: 跑测试确认失败**

Run: `$PY -m pytest -q --no-cov tests/unit/services/enrichment/test_material.py -k "i18n or notable or zh_converted"`
Expected: FAIL(`cannot import name '_artist_i18n_from_rows'` / `_artist_i18n_rows`)

- [ ] **Step 3: 实现**

把 `fetch_artist_i18n_facts` 替换为下面三段(`_artist_i18n_from_rows` 的函数体 = 旧函数从 `nat_i18n: dict = {}` 到 `return {...}` 原样搬出,`wanted` 的计算前移成参数):

```python
def _i18n_wanted(langs) -> list:
    # 变体语言要连它的兜底源一起取:zh-hant 的链里有 zh,若只按 langs 过滤,
    # 请求 zh-hant 而没请求 zh 时链就断了、只能掉到英文。
    return list(
        dict.fromkeys(
            [*langs, *(v for x in langs for v in (_SCRIPT_VARIANTS.get(x) or ((),))[0])]
        )
    )


def _artist_i18n_rows(entity: dict, wanted: list, fetch) -> list[dict]:
    """转换层:作者 P27/P800 主值 × 各语言标签 → 与旧 _ARTIST_I18N_FACTS_QUERY 同形的行。"""
    nats = [q for q in map(_wa.entity_id, _wa.best_statements(entity, "P27")) if q]
    works = [q for q in map(_wa.entity_id, _wa.best_statements(entity, "P800")) if q]
    labels = _wa.labels_of(list(dict.fromkeys(nats + works)), wanted, fetch)
    rows = []
    for q in nats:
        for lang, v in (labels.get(q) or {}).items():
            rows.append({"natLabel": {"xml:lang": lang, "value": v}})
    for q in works:
        for lang, v in (labels.get(q) or {}).items():
            rows.append(
                {"work": {"value": _ENTITY_IRI + q}, "workLabel": {"xml:lang": lang, "value": v}}
            )
    return rows


def _artist_i18n_from_rows(rows, langs) -> dict:
    """解析层(原 fetch_artist_i18n_facts 逐行解析与选集,原样搬出)。"""
    wanted = _i18n_wanted(langs)
    nat_i18n: dict = {}
    works: dict = {}  # 作品 qid -> {lang: label}
    for row in rows:
        nl = row.get("natLabel") or {}
        wl = row.get("workLabel") or {}
        nlang, nv = nl.get("xml:lang") or nl.get("lang"), nl.get("value")
        wlang, wv = wl.get("xml:lang") or wl.get("lang"), wl.get("value")
        if nv and nlang in langs and not _is_raw_qid(nv) and nlang not in nat_i18n:
            nat_i18n[nlang] = _variant_convert(nlang, nv)
        wq = ((row.get("work") or {}).get("value") or "").rsplit("/", 1)[-1]
        if wq and wv and wlang in wanted and not _is_raw_qid(wv):
            works.setdefault(wq, {}).setdefault(wlang, _variant_convert(wlang, wv))
    # ⚠️ 先选作品(语言无关)、再逐语言取标签。此前是每个语言各自 append 再各自 [:5] ——
    # 于是**不同语言展示的是不同的画**,不是同一批的不同译名。实测莫迪利亚尼:
    # P800 十语共 10 件,西语那 4 幅和英语那 5 幅没有交集,用户换个 App 语言
    # 作者卡就换了一批作品。排序判据:被这些语言标注得最全的排前(近似"最知名"),
    # 同分按 qid 稳定排 —— 必须与语言无关,否则又回到各挑各的。
    top = sorted(works.items(), key=lambda kv: (-len(kv[1]), kv[0]))[:5]
    works_i18n: dict = {}
    for lang in langs:
        vals = [v for v in (_pick_work_label(ls, lang) for _, ls in top) if v]
        if vals:
            works_i18n[lang] = vals
    return {
        "nationality_i18n": nat_i18n,
        "notable_works_i18n": works_i18n,
        # 逐件的原始标签(有序,与上面各语言列表一一对应)。调用方靠它分辨
        # "这一件本来就有权威译名"和"这一件是回退的英文名,该翻" —— 只比对
        # 字符串猜不出来(法语的 Olympia 就等于英语的 Olympia)。
        "notable_works_labels": [ls for _, ls in top],
    }


def fetch_artist_i18n_facts(artist_qid, langs, *, get_entities=None) -> dict:
    """作者国籍(P27)/代表作(P800)的多语权威标签(交接③:作者卡本地化)。
    返回 {"nationality_i18n": {lang: label}, "notable_works_i18n": {lang: [labels]},
    "notable_works_labels": [...]}。代表作**先选作品集合再逐语言取标签**,各语言同一批作品。"""
    get_entities = get_entities or _wa.get_entities
    ent = get_entities([artist_qid], props="claims").get(artist_qid) or {}
    rows = _artist_i18n_rows(ent, _i18n_wanted(langs), get_entities)
    return _artist_i18n_from_rows(rows, langs)
```

注意:旧代码中 `_variant_convert(nlang, nv)` 等以及 `nat_i18n`/`works` 的判断一字不改;确认 `git diff` 中这一段只是缩进/位置变化。

- [ ] **Step 4: 跑测试确认通过**

Run: `$PY -m pytest -q --no-cov tests/unit/services/enrichment/test_material.py tests/integration/test_backfill_names.py tests/integration/test_generate_pipeline.py`
Expected: 全部 passed

- [ ] **Step 5: 提交**

```bash
$PY -m black -q app/services/enrichment/material.py tests/unit/services/enrichment/test_material.py
git add app/services/enrichment/material.py tests/unit/services/enrichment/test_material.py
git commit -m "refactor(enrichment): 作者国籍/代表作多语名改走 wbgetentities(复用同批作品选集)"
```

---

### Task 6: 证据包富属性 + 流水线离线开关

**Files:**
- Modify: `backend/app/services/enrichment/evidence.py`(`fetch_rich_facts`、`build_evidence_pack` 注入参数)
- Modify: `backend/app/services/enrichment/pipeline.py`(`f_rich` 提交处)
- Test: `backend/tests/unit/services/enrichment/test_evidence.py`、`backend/tests/integration/test_generate_pipeline.py`

**Interfaces:**
- Consumes: Task 1 `best_statements`、`entity_id`、`labels_of`
- Produces: `evidence._rich_rows(entity, fetch) -> list[dict]`、`evidence._rich_from_rows(rows) -> list[dict]`、`fetch_rich_facts(qid, *, get_entities=None)`、`build_evidence_pack(obj, *, get_entities=None, complete=None, rich_facts=None)`

- [ ] **Step 1: 迁移旧测试 + 写新测试**

```bash
$PY tests/fixtures/wikidata/migrate_run_query_tests.py tests/unit/services/enrichment/test_evidence.py fetch_rich_facts
```

`test_evidence.py` 里 `build_evidence_pack(obj, run_query=…, …)` 的 4 处手改为 `get_entities=…`:`lambda s: []` → `lambda ids, **k: {}`;`boom` 改签名 `def boom(*a, **k):`。
`test_generate_pipeline.py` 里 `lambda qid, run_query=None: [...]` → `lambda qid, get_entities=None: [...]`。

`test_evidence.py` 末尾追加:

```python
import json as _json
from pathlib import Path as _Path

_E = _json.loads(
    (_Path(__file__).parents[3] / "fixtures" / "wikidata" / "entities.json").read_text()
)


def _fake_get(ids, *, props, languages=None):
    return {q: _E[q] for q in ids if q in _E}


def test_fetch_rich_facts_real_mona_lisa():
    """真实夹具 Q12418:P186 两条 preferred 压过 normal(Q287 不出现);P180 9 条限 5。"""
    from app.services.enrichment.evidence import fetch_rich_facts

    facts = fetch_rich_facts("Q12418", get_entities=_fake_get)
    by = {}
    for f in facts:
        by.setdefault(f["source"], []).append(f["value"])
    en = lambda q: _E[q]["labels"]["en"]["value"]  # noqa: E731
    assert by["wikidata:P186"] == [en("Q296955"), en("Q106857865")]
    assert len(by["wikidata:P180"]) == 5
    assert by["wikidata:P88"] == [en("Q1395822")]


def test_fetch_rich_facts_skips_non_wikidata_id():
    from app.services.enrichment.evidence import fetch_rich_facts

    def boom(*a, **k):
        raise AssertionError("不该对非 Wikidata 编号发请求")

    assert fetch_rich_facts("joconde-00000089446", get_entities=boom) == []


def test_rich_rows_raw_qid_when_no_english_label():
    from app.services.enrichment.evidence import _rich_rows

    ent = {"claims": {"P88": [_E["Q12418"]["claims"]["P88"][0]]}}
    assert _rich_rows(ent, lambda ids, **k: {}) == [
        {"pid": {"value": "P88"}, "vLabel": {"value": "Q1395822"}}
    ]
```

- [ ] **Step 2: 跑测试确认失败**

Run: `$PY -m pytest -q --no-cov tests/unit/services/enrichment/test_evidence.py`
Expected: FAIL(`cannot import name '_rich_from_rows'` / `_rich_rows`、`unexpected keyword argument 'get_entities'`)

- [ ] **Step 3: 实现**

`evidence.py` 顶部 import 加 `from app.services.enrichment import wikidata_api as _wa`。把 `fetch_rich_facts` 替换为(`_rich_from_rows` = 旧函数从 `out = []` 起的循环原样搬出;`_RICH_QUERY`、`_default_run_query` 保留到 Task 7):

```python
def _rich_rows(entity: dict, fetch) -> list[dict]:
    """转换层:作品实体 _RICH_PROPS 主值 → 与旧 _RICH_QUERY 同形的行(无英文名填原始 QID)。
    只对实体值取名(这几项属性都是 wikibase-item);非实体值跳过。"""
    pairs = [
        (pid, q)
        for pid in _RICH_PROPS
        for q in map(_wa.entity_id, _wa.best_statements(entity, pid))
        if q
    ]
    en = _wa.labels_of(list(dict.fromkeys(q for _, q in pairs)), ["en"], fetch)
    return [
        {"pid": {"value": pid}, "vLabel": {"value": (en.get(q) or {}).get("en") or q}}
        for pid, q in pairs
    ]


def _rich_from_rows(rows) -> list[dict]:
    """解析层(原 fetch_rich_facts 逐行解析,原样搬出)。"""
    out = []
    per_prop: dict[str, int] = {}
    for row in rows:
        pid = (row.get("pid") or {}).get("value", "")
        val = (row.get("vLabel") or {}).get("value")
        # 标签服务对无本地化标签的实体退回原始 QID(如 "Q137160517")→ 无意义,跳过
        if val and val[0] in "QP" and val[1:].isdigit():
            val = None
        if pid in _RICH_PROPS and val:
            if per_prop.get(pid, 0) >= _RICH_MAX_PER_PROP:
                continue  # 每属性限 _RICH_MAX_PER_PROP 条
            per_prop[pid] = per_prop.get(pid, 0) + 1
            claim, topic = _RICH_PROPS[pid]
            out.append(
                {
                    "claim": claim,
                    "value": val,
                    "source": f"wikidata:{pid}",
                    "topic": topic,
                }
            )
    return out


def fetch_rich_facts(qid: str, *, get_entities=None) -> list[dict]:
    """Wikidata 富属性 → 事实原子 [{claim,value,source,topic}]。无→[]。非 Wikidata 编号不发请求。"""
    from app.services.enrichment.identity import is_wikidata_qid

    if not is_wikidata_qid(qid):
        return []
    get_entities = get_entities or _wa.get_entities
    ent = get_entities([qid], props="claims").get(qid) or {}
    return _rich_from_rows(_rich_rows(ent, get_entities))
```

`build_evidence_pack` 签名与调用改:

```python
def build_evidence_pack(
    obj: dict, *, get_entities=None, complete=None, rich_facts=None
) -> dict:
```

函数体内 `fetch_rich_facts(obj["qid"], run_query=run_query)` → `fetch_rich_facts(obj["qid"], get_entities=get_entities)`。

`pipeline.py` 的 `f_rich` 提交处:

```python
            run_query=None if registry is not None else (lambda _sparql: []),
```

改为:

```python
            get_entities=None if registry is not None else (lambda ids, **kw: {}),
```

- [ ] **Step 4: 跑测试确认通过**

Run: `$PY -m pytest -q --no-cov tests/unit/services/enrichment/test_evidence.py tests/integration/test_generate_pipeline.py tests/integration/test_pack_and_content_facts.py`
Expected: 全部 passed

- [ ] **Step 5: 提交**

```bash
$PY -m black -q app/services/enrichment/evidence.py app/services/enrichment/pipeline.py tests/unit/services/enrichment/test_evidence.py tests/integration/test_generate_pipeline.py
git add app/services/enrichment/evidence.py app/services/enrichment/pipeline.py tests/unit/services/enrichment/test_evidence.py tests/integration/test_generate_pipeline.py
git commit -m "refactor(enrichment): 证据包富属性改走 wbgetentities;流水线离线开关改 get_entities"
```

---

### Task 7: 等价验证脚本(旧 SPARQL 参照移入脚本)

**Files:**
- Create: `backend/scripts/verify_wikidata_api_parity.py`
- Modify: `backend/app/services/enrichment/material.py`、`evidence.py`(删除已无生产调用的 SPARQL 常量)

**Interfaces:**
- Consumes: Task 2–6 的 `_xxx_from_rows`、`_xxx_rows`、六个 fetch 函数
- Produces: CLI `python scripts/verify_wikidata_api_parity.py <qids.txt> <out.jsonl>`,输出逐件逐字段比对与分类汇总

- [ ] **Step 1: 搬常量**

在 `material.py`、`evidence.py` 里确认下列常量已无生产调用(`grep -rn "<NAME>" app scripts` 只剩定义):`_CREATOR_QUERY`、`_ARTIST_QUERY`、`_ARTIST_TITLES_QUERY`、`_ARTIST_FACTS_BY_ARTIST_QUERY`、`_ARTIST_FACTS_QUERY`、`_LABELS_QUERY`、`_ARTIST_I18N_FACTS_QUERY`、`_RICH_QUERY`、`evidence._default_run_query`。把它们的文本**原样**复制进验证脚本,然后从生产模块删除。删除后 `evidence.py` 顶部的 `from app.services.enrichment.sources import wikidata as _wd` 若已无引用(`grep -n "_wd\." app/services/enrichment/evidence.py` 为空)一并删掉。`_LABELS_BATCH_QUERY`、`_default_artist_query`、`_BUILDING_PHOTO_QUERY` 仍有调用,保留。

- [ ] **Step 2: 写脚本**

`backend/scripts/verify_wikidata_api_parity.py`:

```python
"""等价验证(spec 2026-10-10 §5):同一批作品,旧 SPARQL(行)与新 wbgetentities(转换成行)
喂同一套解析函数,逐字段比对。只读,不写库。

用法:python scripts/verify_wikidata_api_parity.py qids.txt out.jsonl
qids.txt 每行一个作品 qid(可附 "\t说明")。
"""

import json
import sys
import time

import requests

from app.services.enrichment import material as m
from app.services.enrichment import evidence as ev
from app.services.enrichment.sources import wikidata as _wd

LANGS = ["en", "zh", "zh-hant", "fr", "de", "es", "it", "ja", "ko", "pt"]

# ---- 旧 SPARQL 参照(从生产模块原样移来)----
_CREATOR_QUERY = """
SELECT ?artist ?rank ?cert (COUNT(?ref) AS ?refs) WHERE {{
  wd:{qid} p:P170 ?st .
  ?st ps:P170 ?artist ; wikibase:rank ?rank .
  OPTIONAL {{ ?st pq:P1480 ?cert . }}
  OPTIONAL {{ ?st prov:wasDerivedFrom ?ref . }}
}} GROUP BY ?artist ?rank ?cert
"""
_ARTIST_TITLES_QUERY = """
SELECT ?al_en ?al_cl WHERE {{
  OPTIONAL {{ ?a_en schema:about wd:{aqid} ; schema:isPartOf <https://en.wikipedia.org/> ; schema:name ?al_en . }}
  OPTIONAL {{ ?a_cl schema:about wd:{aqid} ; schema:isPartOf <https://{cl}.wikipedia.org/> ; schema:name ?al_cl . }}
}} LIMIT 1
"""
_ARTIST_FACTS_BY_ARTIST_QUERY = """
SELECT ?birth ?death ?natLabel ?workLabel WHERE {{
  OPTIONAL {{ wd:{aqid} wdt:P569 ?birth. }}
  OPTIONAL {{ wd:{aqid} wdt:P570 ?death. }}
  OPTIONAL {{ wd:{aqid} wdt:P27 ?nat. }}
  OPTIONAL {{ wd:{aqid} wdt:P800 ?work. }}
  SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
}}
"""
_ARTIST_FACTS_QUERY = """
SELECT ?artist ?birth ?death ?natLabel ?workLabel WHERE {{
  wd:{qid} wdt:P170 ?artist .
  OPTIONAL {{ ?artist wdt:P569 ?birth. }}
  OPTIONAL {{ ?artist wdt:P570 ?death. }}
  OPTIONAL {{ ?artist wdt:P27 ?nat. }}
  OPTIONAL {{ ?artist wdt:P800 ?work. }}
  SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
}}
"""
_LABELS_QUERY = """
SELECT ?l WHERE {{ wd:{qid} rdfs:label ?l . FILTER(lang(?l) IN ({langs})) }}
"""
_ARTIST_I18N_FACTS_QUERY = """
SELECT ?natLabel ?work ?workLabel WHERE {{
  OPTIONAL {{ wd:{qid} wdt:P27 ?nat . ?nat rdfs:label ?natLabel .
             FILTER(lang(?natLabel) IN ({langs})) }}
  OPTIONAL {{ wd:{qid} wdt:P800 ?work . ?work rdfs:label ?workLabel .
             FILTER(lang(?workLabel) IN ({langs})) }}
}}
"""
_RICH_QUERY = """
SELECT ?pid ?vLabel WHERE {{
  VALUES ?prop {{ wdt:P88 wdt:P180 wdt:P186 wdt:P135 wdt:P136 wdt:P1343
                  wdt:P4969 wdt:P144 wdt:P941 wdt:P361 }}
  wd:{qid} ?prop ?v .
  ?p wikibase:directClaim ?prop . BIND(STRAFTER(STR(?p), "entity/") AS ?pid)
  SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
}}
"""


def sparql(q):
    for attempt in range(3):
        try:
            r = requests.get(
                _wd.SPARQL_ENDPOINT,
                params={"query": q, "format": "json"},
                headers={"User-Agent": _wd.USER_AGENT, "Accept": "application/sparql-results+json"},
                timeout=60,
            )
            r.raise_for_status()
            return r.json()["results"]["bindings"]
        except Exception:
            if attempt == 2:
                raise
            time.sleep(5)


def old(qid):
    """旧实现语义:SPARQL 行 → 同一套解析函数;旧 P170 遍历与 rsplit 截断照旧复现。"""
    o = {}
    o["labels"] = m._labels_from_rows(
        sparql(_LABELS_QUERY.format(qid=qid, langs=", ".join('"%s"' % x for x in m._query_langs(LANGS)))), LANGS
    )
    aq = m._creator_from_rows(sparql(_CREATOR_QUERY.format(qid=qid)))
    o["creator"] = aq
    if aq:
        rows = sparql(_ARTIST_TITLES_QUERY.format(aqid=aq, cl="fr"))
        r0 = rows[0] if rows else {}
        o["artist_titles"] = {
            k: (r0.get(c) or {}).get("value", "").rsplit("/", 1)[-1]
            for k, c in (("en", "al_en"), ("fr", "al_cl"))
            if (r0.get(c) or {}).get("value")
        }
        o["artist_facts"] = m._artist_facts_from_rows(sparql(_ARTIST_FACTS_BY_ARTIST_QUERY.format(aqid=aq)), aq)
        wanted = m._i18n_wanted(LANGS)
        o["artist_i18n"] = m._artist_i18n_from_rows(
            sparql(_ARTIST_I18N_FACTS_QUERY.format(qid=aq, langs=", ".join('"%s"' % x for x in wanted))), LANGS
        )
    else:
        # 旧流水线:aqid 为空仍走 P170 遍历 —— 这里只记它会不会产出作者 qid(§4.1 假作者卡)
        rows = sparql(_ARTIST_FACTS_QUERY.format(qid=qid))
        au = next(((r.get("artist") or {}).get("value", "") for r in rows if r.get("artist")), "")
        o["traversal_artist_qid"] = au.rsplit("/", 1)[-1] if au else None
    o["rich"] = ev._rich_from_rows(sparql(_RICH_QUERY.format(qid=qid)))
    return o


def new(qid):
    o = {"labels": m.fetch_wikidata_labels(qid, LANGS), "creator": m.resolve_creator_qid(qid)}
    aq = o["creator"]
    if aq:
        ent = m._wa.get_entities([aq], props="sitelinks").get(aq) or {}
        sl = ent.get("sitelinks") or {}
        o["artist_titles"] = {k: sl[w]["title"] for k, w in (("en", "enwiki"), ("fr", "frwiki")) if sl.get(w)}
        o["artist_facts"] = m.fetch_artist_facts(qid, artist_qid=aq)
        o["artist_i18n"] = m.fetch_artist_i18n_facts(aq, LANGS)
    else:
        o["traversal_artist_qid"] = m.fetch_artist_facts(qid).get("artist_qid")
    o["rich"] = ev.fetch_rich_facts(qid)
    return o


def _norm(v):
    """顺序无关的规范形:列表排序、字典递归。"""
    if isinstance(v, dict):
        return {k: _norm(x) for k, x in sorted(v.items())}
    if isinstance(v, list):
        return sorted((_norm(x) for x in v), key=lambda x: json.dumps(x, ensure_ascii=False, sort_keys=True))
    return v


def classify(a, b):
    if a == b:
        return "identical"
    if _norm(a) == _norm(b):
        return "order_only"
    return "DIFF"


def main(qfile, out):
    qids = [line.split("\t")[0].strip() for line in open(qfile) if line.strip()]
    summary = {}
    with open(out, "w") as f:
        for qid in qids:
            rec = {"qid": qid}
            try:
                a, b = old(qid), new(qid)
            except Exception as e:  # 记录并继续;报告里单列
                rec["error"] = repr(e)
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
                summary["error"] = summary.get("error", 0) + 1
                continue
            for k in sorted(set(a) | set(b)):
                c = classify(a.get(k), b.get(k))
                rec[k] = c
                summary[(k, c)] = summary.get((k, c), 0) + 1
                if c == "DIFF":
                    rec[k + "_old"], rec[k + "_new"] = a.get(k), b.get(k)
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            f.flush()
    for k, v in sorted(summary.items(), key=str):
        print(k, v)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
```

- [ ] **Step 3: 本地冒烟(3 件)**

```bash
printf "Q64309678\nQ104479426\nQ12418\n" > /tmp/parity_smoke.txt
$PY scripts/verify_wikidata_api_parity.py /tmp/parity_smoke.txt /tmp/parity_smoke.jsonl
```

Expected:无 `error`;Q104479426 的 `traversal_artist_qid` 为 DIFF(旧 = 32 位哈希,新 = None,即 §4.1 旧 bug);其余 identical / order_only。

- [ ] **Step 4: 全套测试 + 提交**

Run: `nice -n 19 $PY -m pytest -q --no-cov -p no:cacheprovider tests`
Expected: 全部 passed(含删除常量后无遗漏引用)

```bash
$PY -m black -q scripts/verify_wikidata_api_parity.py app/services/enrichment/material.py app/services/enrichment/evidence.py
git add scripts/verify_wikidata_api_parity.py app/services/enrichment/material.py app/services/enrichment/evidence.py
git commit -m "test(enrichment): Wikidata 新旧取数等价验证脚本;旧 SPARQL 参照移入脚本"
```

---

### Task 8: 跑等价验证(约 100 件)并归类

**Files:**
- Create: `docs/ops/2026-10-10-wikidata-api-parity.md`(结果报告)
- Delete: `backend/tests/fixtures/wikidata/migrate_run_query_tests.py`(一次性工具已用完)

- [ ] **Step 1: 取样本**

从 prod 只读取样(5 馆各 ready/stub 混合 + 61 件哈希作者件中的 5 件):

```bash
ssh -i ~/.ssh/deepmeeting_deploy root@38.242.207.219 'docker exec gomuseum_prod_postgres psql -U gomuseum -d gomuseum -At -c "
(select o.qid from museum_objects o join museums m on m.id=o.museum_id where o.qid ~ \$\$^Q[0-9]+\$\$ and m.slug=\$\$louvre\$\$ order by random() limit 25)
union all (select o.qid from museum_objects o join museums m on m.id=o.museum_id where o.qid ~ \$\$^Q[0-9]+\$\$ and m.slug=\$\$orsay\$\$ order by random() limit 25)
union all (select o.qid from museum_objects o join museums m on m.id=o.museum_id where o.qid ~ \$\$^Q[0-9]+\$\$ and m.slug=\$\$petit_palais\$\$ order by random() limit 15)
union all (select o.qid from museum_objects o join museums m on m.id=o.museum_id where o.qid ~ \$\$^Q[0-9]+\$\$ and m.slug=\$\$orangerie\$\$ order by random() limit 10)
union all (select o.qid from museum_objects o join museums m on m.id=o.museum_id where o.qid ~ \$\$^Q[0-9]+\$\$ and m.slug=\$\$rijksmuseum\$\$ order by random() limit 5)
union all (select qid from museum_objects where attributes->>\$\$artist_qid\$\$ !~ \$\$^Q[0-9]+\$\$ order by qid limit 5);"' </dev/null > /tmp/parity_qids.txt
wc -l /tmp/parity_qids.txt
```

Expected:约 85 行。

- [ ] **Step 2: 补齐专门样本类(spec §5)**

逐条跑下面 WDQS 查询(串行,只读),各取 1–3 件作品 qid 追加进 `/tmp/parity_qids.txt`(行尾 `\t<类名>`):

同一作者多条 P170 语句(卢浮宫 Q19675 / 奥赛 Q23402):

```sparql
SELECT DISTINCT ?item WHERE { VALUES ?coll { wd:Q19675 wd:Q23402 }
  ?item wdt:P195 ?coll ; p:P170 ?s1, ?s2 . ?s1 ps:P170 ?a . ?s2 ps:P170 ?a . FILTER(?s1 != ?s2) } LIMIT 3
```

作者生年有并列主值:

```sparql
SELECT DISTINCT ?item WHERE { VALUES ?coll { wd:Q19675 wd:Q23402 }
  ?item wdt:P195 ?coll ; wdt:P170 ?a . ?a wdt:P569 ?b1, ?b2 . FILTER(?b1 != ?b2) } LIMIT 3
```

作者自己的生卒年是「未知值」:

```sparql
SELECT DISTINCT ?item WHERE { VALUES ?coll { wd:Q19675 wd:Q23402 }
  ?item wdt:P195 ?coll ; wdt:P170 ?a . ?a wdt:P569|wdt:P570 ?d . FILTER(wikibase:isSomeValue(?d)) } LIMIT 3
```

(`wikibase:isSomeValue` 报错时改用 `FILTER(STRSTARTS(STR(?d), "http://www.wikidata.org/.well-known/genid/"))`。)
再追加:`Q64309678\t多P170+P1480`、`Q12418\t证据包满`、`Q104479426\tP170未知值`、`joconde-00000089446\tJoconde编号`。
某类查不到 → 报告里注明「无样本」及所用查询。

- [ ] **Step 3: 跑验证**

```bash
cd backend && nice -n 19 $PY scripts/verify_wikidata_api_parity.py /tmp/parity_qids.txt /tmp/parity_out.jsonl | tee /tmp/parity_summary.txt
```

Expected:跑完 ~100 件(串行,约 10–20 分钟);打印各字段 × 分类计数。

- [ ] **Step 4: 逐条归类 DIFF**

对 `/tmp/parity_out.jsonl` 里每条 `DIFF`,打开 `<field>_old` / `<field>_new`,归入且仅归入一类,写进报告表格:
- 旧 bug 被修(§4:哈希作者 / http 日期 / 条目名含 `/`);
- WDQS 滞后:到 `https://www.wikidata.org/wiki/<qid>` 核对,新值 = 页面当前值;
- 并列主值取第一条(§3.2):注明是否影响年份;
- **无法解释** —— 只要有 1 条:停下,不切换,带明细报给用户。

`error` 行:单独重跑该 qid;仍错则写明原因。

- [ ] **Step 5: 写报告并提交**

`docs/ops/2026-10-10-wikidata-api-parity.md`:样本构成(每类件数、所用查询)、汇总计数表(字段 × identical / order_only / DIFF)、DIFF 逐条明细与归类、结论(无法解释 = 0 才写「可切换」)。

```bash
git rm tests/fixtures/wikidata/migrate_run_query_tests.py
git add ../docs/ops/2026-10-10-wikidata-api-parity.md
git commit -m "docs(ops): Wikidata Action API 等价验证报告"
```

---

### Task 9: 待办、PR、staging 复测

**Files:**
- Modify: `docs/ops/backlog.md`

- [ ] **Step 1: 待办加一条**

在「三、技术债」表里、`| 存量 152 件证据包具名事实没用上` 那行之后插入:

```markdown
| prod 61 件作品挂着哈希作者 QID(空作者卡) | 旧 `fetch_artist_facts` 在作者为「未知值」时遍历 P170,把 blank node 哈希当作者 QID 写回(卢浮宫 59 / 小皇宫 2,均 ready,对应 61 张空 `artists` 行)。生成侧已由 Wikidata 换接口堵住。**存量清理待你确认**:按纪律 37 列写入面(museum_objects.attributes.artist_qid / artist_qid_source 置空 + 删 61 张空作者卡,先查有无音频/被别处引用)+ 备份后执行 | 10-10 spec 2026-10-10-wikidata-action-api §4.1 |
```

```bash
git add ../docs/ops/backlog.md
git commit -m "docs(ops): 待办加 61 件哈希作者 QID 存量清理"
```

- [ ] **Step 2: 全套测试、推送、PR**

Run: `nice -n 19 $PY -m pytest -q --no-cov -p no:cacheprovider tests`
Expected: 全部 passed

```bash
git push -u origin feature/wikidata-action-api
```

把 PR 描述写到 `/tmp/pr_wdapi.md`,结构固定为:

```markdown
## 背景
懒生成首屏准备阶段受 WDQS 慢尾支配(10-10 抽样:多语标题 5/28 卡满 60s 超时并静默丢资料)。spec:`docs/superpowers/specs/2026-10-10-wikidata-action-api-design.md`

## 改动
- 新 `wikidata_api.get_entities`(批量 50 / 10s 超时 / 3 次重试含响应体 error / 进程级 2 并发)
- 6 个函数改走 wbgetentities:取数 → 转换成旧 SPARQL 同形行 → 旧解析原样复用
- 去掉 artist_qid 为空时的 P170 遍历(堵假作者卡);条目名不再 rsplit 截断;未知值日期不再存 http

## 等价验证
<从 docs/ops/2026-10-10-wikidata-api-parity.md 粘贴:样本构成、字段×分类计数表、DIFF 归类明细、结论>

## 测试
- 后端全套:<N> passed

与 #881–#884 一起上 prod(用户 10-10 定)。

🤖 Generated with [Claude Code](https://claude.com/claude-code)

<会话 URL>
```

```bash
gh pr create --base staging --title "perf(enrichment): 生成流程 Wikidata 单实体查询改走 Action API" --body-file /tmp/pr_wdapi.md
```

CI 绿后 `gh pr merge --squash`,`git push origin --delete feature/wikidata-action-api`。

- [ ] **Step 3: staging 复测(串行 + 并发)**

等 staging 部署完成(`gh run watch`),确认容器里新代码:`docker exec gomuseum_staging_backend grep -c "wbgetentities" /app/app/services/enrichment/wikidata_api.py`(期望 ≥1)。

串行:用会话 scratchpad 里的 `ttfc.py`(把 `wrap(evidence, "fetch_rich_facts")` 保留,另加 `from app.services.enrichment import wikidata_api; wrap(wikidata_api, "get_entities")`)对 3 件 staging stub(至少 1 件作者首次出现)逐件跑。
Expected:每件准备阶段(第一个 `enricher.generate_default_guide` 的起点)≤ 6s;中文讲解落库(第二个 `persist_gated_sections`)约 15–17s;无 `get_entities` 单次 > 10s。

并发:同时起 2 个 `docker exec … ttfc.py <qid> zh &`,`wait`。
Expected:两件准备阶段都 ≤ 6s。超标 → 报告用户(spec §3.4:再考虑合并同实体请求)。

把结果(逐件逐步耗时)发给用户,并提醒:#881–#884 + 本 PR 一起提 staging→main 由用户合并;合并前查 prod 有无长任务在跑。
