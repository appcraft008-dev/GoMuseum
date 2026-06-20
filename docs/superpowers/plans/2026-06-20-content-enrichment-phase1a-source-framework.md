# 内容富化 Phase 1a — 源框架 + 礼貌抓取客户端 + 权威合并升级 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为多连接器富化打地基——礼貌抓取 HTTP 客户端、源缓存、配置驱动的权威合并（§5b：可配优先级 + 字段级覆写 + 冲突标记）、源注册表 + probe + 外部 ID 路由。纯框架，离线可 TDD，1b 的连接器据此插入。

**Architecture:** 全部落在 `backend/app/services/enrichment/`。新增 `http_client.py`（PoliteSession）、`source_cache.py`（抓一次复用）、`registry.py`（SourceRegistry + 外部 ID 路由）；升级既有 `merge.py`（配置优先级 + §5b 冲突）；扩 `sources/base.py` 的 `Source` 加 `probe`。不碰网络（连接器留 1b）。

**Tech Stack:** Python 3.11 / FastAPI 项目 / pytest / requests / 既有 `ObjectStorage` 抽象（本地+R2）。

**分支：** 从最新 `staging` 切 `feature/content-enrichment-phase1a`。

**运行测试：** `cd backend && poetry run pytest <path>`（无 `backend/.venv`；本地若缺 boto3 用 `STORAGE_BACKEND=local`，CI 有 boto3）。

**对应 spec：** §5（礼貌抓取）、§5b（权威性判定与合并）、§18b-6（源自动发现注册表）。设计文档
`docs/superpowers/specs/2026-06-17-artwork-content-enrichment-mechanism-design.md`。

---

## File Structure

| 文件 | 责任 | 改动 |
|---|---|---|
| `backend/app/services/enrichment/http_client.py` | 礼貌 HTTP（UA 强制 + 令牌桶限速 + 429/503 退避遵守 Retry-After） | 新建 |
| `backend/app/services/enrichment/source_cache.py` | 源抓取结果缓存（抓一次复用，键 source+key+date，走 ObjectStorage） | 新建 |
| `backend/app/services/enrichment/merge.py` | 权威合并升级：配置驱动优先级 + 字段级覆写 + §5b 冲突标记 | 改 |
| `backend/app/services/enrichment/registry.py` | `SourceRegistry` + 外部 ID 路由 | 新建 |
| `backend/app/services/enrichment/sources/base.py` | `Source` 加 `probe(context)->bool`（默认 True） | 改 |
| `backend/tests/unit/services/enrichment/test_http_client.py` | 新测试 | 新建 |
| `backend/tests/unit/services/enrichment/test_source_cache.py` | 新测试 | 新建 |
| `backend/tests/unit/services/enrichment/test_merge.py` | 既有，加冲突/配置优先级用例 | 改 |
| `backend/tests/unit/services/enrichment/test_registry.py` | 新测试 | 新建 |

---

## Task 1: 礼貌 HTTP 客户端 `PoliteSession`

**Files:**
- Create: `backend/app/services/enrichment/http_client.py`
- Test: `backend/tests/unit/services/enrichment/test_http_client.py`

- [ ] **Step 1: 写失败测试**

```python
import pytest
from app.services.enrichment.http_client import PoliteSession


class _FakeResp:
    def __init__(self, status, headers=None, body=b"{}"):
        self.status_code = status
        self.headers = headers or {}
        self._body = body
        self.text = body.decode() if isinstance(body, bytes) else body

    def json(self):
        import json
        return json.loads(self._body)


def test_user_agent_required():
    with pytest.raises(ValueError, match="User-Agent"):
        PoliteSession(user_agent="")


def test_get_sends_user_agent_and_returns(monkeypatch):
    seen = {}

    def fake_get(url, params=None, headers=None, timeout=None):
        seen["headers"] = headers
        return _FakeResp(200, body=b'{"ok": 1}')

    s = PoliteSession(user_agent="GoMuseumBot/0.1 (contact)")
    r = s.get_json("https://x/api", params={"q": "1"}, _transport=fake_get)
    assert seen["headers"]["User-Agent"] == "GoMuseumBot/0.1 (contact)"
    assert r == {"ok": 1}


def test_backoff_on_429_then_succeeds(monkeypatch):
    calls = {"n": 0}
    sleeps = []

    def fake_get(url, params=None, headers=None, timeout=None):
        calls["n"] += 1
        if calls["n"] == 1:
            return _FakeResp(429, headers={"Retry-After": "2"})
        return _FakeResp(200, body=b'{"ok": 1}')

    s = PoliteSession(user_agent="UA", max_retries=2, sleep=sleeps.append)
    r = s.get_json("https://x", _transport=fake_get)
    assert r == {"ok": 1}
    assert calls["n"] == 2
    assert sleeps == [2.0]  # 遵守 Retry-After


def test_circuit_breaker_raises_after_repeated_failures():
    def fake_get(url, params=None, headers=None, timeout=None):
        return _FakeResp(503)

    s = PoliteSession(user_agent="UA", max_retries=2, sleep=lambda _: None)
    with pytest.raises(RuntimeError, match="耗尽重试"):
        s.get_json("https://x", _transport=fake_get)
```

- [ ] **Step 2: 跑确认失败**

Run: `cd backend && poetry run pytest tests/unit/services/enrichment/test_http_client.py -v`
Expected: FAIL（`ModuleNotFoundError: app.services.enrichment.http_client`）。

- [ ] **Step 3: 实现 `http_client.py`**

```python
"""礼貌抓取 HTTP 客户端：UA 强制 + 令牌桶限速 + 429/503 退避（遵守 Retry-After）+ 熔断。"""

from __future__ import annotations

import time
from typing import Callable, Optional

import requests


class PoliteSession:
    def __init__(
        self,
        user_agent: str,
        min_interval: float = 1.0,
        max_retries: int = 3,
        timeout: int = 60,
        sleep: Callable[[float], None] = time.sleep,
    ):
        if not user_agent:
            raise ValueError("必须提供描述性 User-Agent（Wikimedia 强制）")
        self._ua = user_agent
        self._min_interval = min_interval
        self._max_retries = max_retries
        self._timeout = timeout
        self._sleep = sleep
        self._last = 0.0

    def _throttle(self) -> None:
        wait = self._min_interval - (time.monotonic() - self._last)
        if wait > 0:
            self._sleep(wait)
        self._last = time.monotonic()

    def get_json(self, url, params=None, _transport=None) -> dict:
        get = _transport or (
            lambda u, params=None, headers=None, timeout=None: requests.get(
                u, params=params, headers=headers, timeout=timeout
            )
        )
        headers = {"User-Agent": self._ua, "Accept": "application/json"}
        for attempt in range(self._max_retries):
            self._throttle()
            resp = get(url, params=params, headers=headers, timeout=self._timeout)
            if resp.status_code == 200:
                return resp.json()
            if resp.status_code in (429, 503):
                retry_after = resp.headers.get("Retry-After")
                delay = float(retry_after) if retry_after else 2.0 * (attempt + 1)
                self._sleep(delay)
                continue
            resp_text = getattr(resp, "text", "")
            raise RuntimeError(f"HTTP {resp.status_code}: {resp_text[:200]}")
        raise RuntimeError(f"耗尽重试（{self._max_retries}）仍失败: {url}")
```

- [ ] **Step 4: 跑确认通过**

Run: `cd backend && poetry run pytest tests/unit/services/enrichment/test_http_client.py -v`
Expected: 4 passed。

- [ ] **Step 5: 格式化 + 提交**

```bash
cd backend && poetry run black app/services/enrichment/http_client.py tests/unit/services/enrichment/test_http_client.py && poetry run isort app/services/enrichment/http_client.py tests/unit/services/enrichment/test_http_client.py
cd /Users/hongyang/Projects/GoMuseum
git add backend/app/services/enrichment/http_client.py backend/tests/unit/services/enrichment/test_http_client.py
git commit -m "feat(enrichment): PoliteSession 礼貌HTTP客户端(UA强制+限速+退避+熔断)"
```

---

## Task 2: 源缓存 `SourceCache`（抓一次复用）

**Files:**
- Create: `backend/app/services/enrichment/source_cache.py`
- Test: `backend/tests/unit/services/enrichment/test_source_cache.py`

- [ ] **Step 1: 写失败测试**

```python
from app.services.enrichment.source_cache import SourceCache


class FakeStorage:
    def __init__(self):
        self.objects = {}

    def put(self, key, data, content_type):
        self.objects[key] = data

    def get(self, key):
        return self.objects.get(key)

    def exists(self, key):
        return key in self.objects


def test_cache_miss_calls_fetch_then_hit_reuses():
    storage = FakeStorage()
    cache = SourceCache(storage, day="2026-06-20")
    calls = {"n": 0}

    def fetch():
        calls["n"] += 1
        return {"v": 42}

    a = cache.get_or_fetch("wikipedia", "Q1", fetch)
    b = cache.get_or_fetch("wikipedia", "Q1", fetch)
    assert a == b == {"v": 42}
    assert calls["n"] == 1  # 第二次命中缓存，不再 fetch


def test_cache_key_includes_source_and_day():
    storage = FakeStorage()
    SourceCache(storage, day="2026-06-20").get_or_fetch("joconde", "REF9", lambda: {"x": 1})
    assert any("joconde" in k and "REF9" in k and "2026-06-20" in k for k in storage.objects)
```

- [ ] **Step 2: 跑确认失败**

Run: `cd backend && STORAGE_BACKEND=local poetry run pytest tests/unit/services/enrichment/test_source_cache.py -v`
Expected: FAIL（模块不存在）。

- [ ] **Step 3: 实现 `source_cache.py`**

```python
"""源抓取结果缓存：抓一次复用（键 source+key+day），走 ObjectStorage（本地/R2）。
重跑/生成/翻译/再生成都不再打源 → 既礼貌又省。"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Callable


class SourceCache:
    def __init__(self, storage, day: str | None = None):
        self._storage = storage
        self._day = day or datetime.now(timezone.utc).strftime("%Y-%m-%d")

    def _key(self, source: str, ident: str) -> str:
        return f"source-cache/{source}/{self._day}/{ident}.json"

    def get_or_fetch(self, source: str, ident: str, fetch: Callable[[], dict]) -> dict:
        key = self._key(source, ident)
        cached = self._storage.get(key)
        if cached is not None:
            return json.loads(cached if isinstance(cached, str) else cached.decode())
        data = fetch()
        self._storage.put(key, json.dumps(data, ensure_ascii=False).encode(), "application/json")
        return data
```

- [ ] **Step 4: 跑确认通过**

Run: `cd backend && STORAGE_BACKEND=local poetry run pytest tests/unit/services/enrichment/test_source_cache.py -v`
Expected: 2 passed。

- [ ] **Step 5: 格式化 + 提交**

```bash
cd backend && poetry run black app/services/enrichment/source_cache.py tests/unit/services/enrichment/test_source_cache.py && poetry run isort app/services/enrichment/source_cache.py tests/unit/services/enrichment/test_source_cache.py
cd /Users/hongyang/Projects/GoMuseum
git add backend/app/services/enrichment/source_cache.py backend/tests/unit/services/enrichment/test_source_cache.py
git commit -m "feat(enrichment): SourceCache 源抓取抓一次复用(键 source+key+day)"
```

---

## Task 3: `merge.py` 配置驱动优先级

**Files:**
- Modify: `backend/app/services/enrichment/merge.py`
- Test: `backend/tests/unit/services/enrichment/test_merge.py`（既有，追加）

- [ ] **Step 1: 写失败测试（追加到 test_merge.py）**

```python
from app.services.enrichment.merge import merge_contributions
from app.services.enrichment.sources.base import ObjectContribution


def test_precedence_param_official_beats_wikidata():
    wd = ObjectContribution(source="wikidata", qid="Q1", fields={"medium": "oil"})
    jo = ObjectContribution(source="official", qid="Q1", fields={"medium": "huile sur toile"})
    merged = merge_contributions([wd, jo], precedence=["wikidata", "official", "manual"])
    assert merged["medium"] == "huile sur toile"  # official 高于 wikidata


def test_non_empty_higher_wins_empty_does_not_overwrite():
    wd = ObjectContribution(source="wikidata", qid="Q1", fields={"medium": "oil"})
    jo = ObjectContribution(source="official", qid="Q1", fields={"medium": None})
    merged = merge_contributions([wd, jo], precedence=["wikidata", "official", "manual"])
    assert merged["medium"] == "oil"  # 高权威该字段为空 → 不覆盖好数据
```

- [ ] **Step 2: 跑确认失败**

Run: `cd backend && poetry run pytest tests/unit/services/enrichment/test_merge.py -k precedence_param -v`
Expected: FAIL（`merge_contributions()` 不接受 `precedence` 参数）。

- [ ] **Step 3: 改 `merge.py` 让优先级可传入**

把 `merge_contributions` 签名与 `_rank` 改为：

```python
DEFAULT_PRECEDENCE = ["wikidata", "official", "manual"]


def _rank(source: str, precedence: list[str]) -> int:
    return precedence.index(source) if source in precedence else -1


def merge_contributions(
    contribs: list[ObjectContribution], precedence: list[str] | None = None
) -> dict:
    """同一 object 的多源贡献 → canonical dict（含 sources 原始包）。
    precedence：越靠后越高；默认 DEFAULT_PRECEDENCE。"""
    precedence = precedence or DEFAULT_PRECEDENCE
    if not contribs:
        raise ValueError("空贡献")
    qid = contribs[0].qid
    now = datetime.now(timezone.utc).isoformat()

    canonical: dict = {"qid": qid}
    field_source: dict[str, str] = {}
    sources: dict[str, dict] = {}

    for c in sorted(contribs, key=lambda x: _rank(x.source, precedence)):
        sources[c.source] = {"raw": c.raw, "fetched_at": now}
        for k, v in c.fields.items():
            if v is None:
                continue
            canonical[k] = v
            field_source[k] = c.source

    canonical["sources"] = sources
    return canonical
```

> 注：原 `PRECEDENCE` 常量改名 `DEFAULT_PRECEDENCE`；若别处 import 了 `PRECEDENCE`，一并改（`grep -rn "PRECEDENCE" backend`）。同级冲突告警逻辑移到 Task 4 重做。

- [ ] **Step 4: 跑确认通过**

Run: `cd backend && poetry run pytest tests/unit/services/enrichment/test_merge.py -v`
Expected: 全部 passed（含既有用例）。

- [ ] **Step 5: 格式化 + 提交**

```bash
cd backend && poetry run black app/services/enrichment/merge.py tests/unit/services/enrichment/test_merge.py && poetry run isort app/services/enrichment/merge.py tests/unit/services/enrichment/test_merge.py
cd /Users/hongyang/Projects/GoMuseum
git add backend/app/services/enrichment/merge.py backend/tests/unit/services/enrichment/test_merge.py
git commit -m "feat(enrichment): merge 优先级配置驱动(precedence 参数)"
```

---

## Task 4: `merge.py` §5b 冲突标记（不静默覆盖）

**Files:**
- Modify: `backend/app/services/enrichment/merge.py`
- Test: `backend/tests/unit/services/enrichment/test_merge.py`（追加）

- [ ] **Step 1: 写失败测试（追加）**

```python
def test_same_rank_conflict_recorded_not_silent():
    # 两个同级源(都 official)对 medium 给不同非空值 → 记进 _conflicts，不静默
    a = ObjectContribution(source="official", qid="Q1", fields={"medium": "huile"})
    b = ObjectContribution(source="official", qid="Q1", fields={"medium": "tempera"})
    merged = merge_contributions([a, b], precedence=["wikidata", "official", "manual"])
    assert "_conflicts" in merged
    assert any(c["field"] == "medium" for c in merged["_conflicts"])


def test_no_conflict_when_values_agree():
    a = ObjectContribution(source="official", qid="Q1", fields={"medium": "huile"})
    b = ObjectContribution(source="official", qid="Q1", fields={"medium": "huile"})
    merged = merge_contributions([a, b], precedence=["wikidata", "official", "manual"])
    assert not merged.get("_conflicts")
```

- [ ] **Step 2: 跑确认失败**

Run: `cd backend && poetry run pytest tests/unit/services/enrichment/test_merge.py -k conflict -v`
Expected: FAIL（无 `_conflicts`）。

- [ ] **Step 3: 在 merge 循环里加冲突检测**

把 Task 3 的循环体替换为（新增 `conflicts` 收集 + 同级不同值检测）：

```python
    canonical: dict = {"qid": qid}
    field_source: dict[str, str] = {}
    sources: dict[str, dict] = {}
    conflicts: list[dict] = []

    for c in sorted(contribs, key=lambda x: _rank(x.source, precedence)):
        sources[c.source] = {"raw": c.raw, "fetched_at": now}
        for k, v in c.fields.items():
            if v is None:
                continue
            prev = canonical.get(k)
            if (
                k in field_source
                and _rank(c.source, precedence) == _rank(field_source[k], precedence)
                and prev != v
            ):
                conflicts.append(
                    {"field": k, "values": [prev, v], "sources": [field_source[k], c.source]}
                )
            canonical[k] = v
            field_source[k] = c.source

    canonical["sources"] = sources
    if conflicts:
        canonical["_conflicts"] = conflicts
    return canonical
```

> `_conflicts` 由 loader 在落库时用来给冲突字段所在对象标 `needs_review`（loader 改动属 1c）。本期只产出 `_conflicts`。

- [ ] **Step 4: 跑确认通过**

Run: `cd backend && poetry run pytest tests/unit/services/enrichment/test_merge.py -v`
Expected: 全部 passed。

- [ ] **Step 5: 格式化 + 提交**

```bash
cd backend && poetry run black app/services/enrichment/merge.py tests/unit/services/enrichment/test_merge.py && poetry run isort app/services/enrichment/merge.py tests/unit/services/enrichment/test_merge.py
cd /Users/hongyang/Projects/GoMuseum
git add backend/app/services/enrichment/merge.py backend/tests/unit/services/enrichment/test_merge.py
git commit -m "feat(enrichment): merge §5b 同级冲突标记(_conflicts，不静默覆盖)"
```

---

## Task 5: `Source.probe` + `SourceRegistry` + 外部 ID 路由

**Files:**
- Modify: `backend/app/services/enrichment/sources/base.py`
- Create: `backend/app/services/enrichment/registry.py`
- Test: `backend/tests/unit/services/enrichment/test_registry.py`

- [ ] **Step 1: 写失败测试**

```python
from app.services.enrichment.registry import SourceRegistry


class FakeSource:
    def __init__(self, name, ext_pid=None):
        self.name = name
        self._ext_pid = ext_pid

    def probe(self, external_ids: dict) -> bool:
        # 无外部 ID 要求(如 wikidata/wikipedia) → 总适用；有要求 → 看是否带该 PID
        return self._ext_pid is None or self._ext_pid in external_ids

    def fetch(self, cfg):  # 本期不调用
        return []


def test_registry_routes_by_external_id():
    wikidata = FakeSource("wikidata")  # 总适用
    joconde = FakeSource("joconde", ext_pid="P347")  # 需 P347
    reg = SourceRegistry([wikidata, joconde])

    has = reg.route({"P347": "000PE004070"})
    assert {s.name for s in has} == {"wikidata", "joconde"}

    without = reg.route({})  # 无 P347
    assert {s.name for s in without} == {"wikidata"}


def test_registry_get_by_name():
    reg = SourceRegistry([FakeSource("wikidata")])
    assert reg.get("wikidata").name == "wikidata"
    assert reg.get("nope") is None
```

- [ ] **Step 2: 跑确认失败**

Run: `cd backend && poetry run pytest tests/unit/services/enrichment/test_registry.py -v`
Expected: FAIL（`registry` 模块不存在）。

- [ ] **Step 3a: `Source` 加 `probe`（默认 True）**

在 `backend/app/services/enrichment/sources/base.py` 的 `Source` 类里加（在 `fetch` 之后）：

```python
    def probe(self, external_ids: dict) -> bool:
        """该源是否适用于带这些 Wikidata 外部 ID 的对象。
        默认 True（如 Wikidata/Wikipedia 普适）；按外部 ID 路由的源(如 Joconde)重写。"""
        return True
```

- [ ] **Step 3b: 实现 `registry.py`**

```python
"""源注册表 + 外部 ID 路由：读对象 Wikidata 外部 ID → 自动选适用连接器（零管理员配置）。"""

from __future__ import annotations


class SourceRegistry:
    def __init__(self, sources: list):
        self._sources = list(sources)

    def route(self, external_ids: dict) -> list:
        """返回 probe(external_ids) 为真的源（按注册顺序）。"""
        return [s for s in self._sources if s.probe(external_ids)]

    def get(self, name: str):
        for s in self._sources:
            if getattr(s, "name", None) == name:
                return s
        return None
```

- [ ] **Step 4: 跑确认通过**

Run: `cd backend && poetry run pytest tests/unit/services/enrichment/test_registry.py -v`
Expected: 3 passed。

- [ ] **Step 5: 格式化 + 提交**

```bash
cd backend && poetry run black app/services/enrichment/registry.py app/services/enrichment/sources/base.py tests/unit/services/enrichment/test_registry.py && poetry run isort app/services/enrichment/registry.py app/services/enrichment/sources/base.py tests/unit/services/enrichment/test_registry.py
cd /Users/hongyang/Projects/GoMuseum
git add backend/app/services/enrichment/registry.py backend/app/services/enrichment/sources/base.py backend/tests/unit/services/enrichment/test_registry.py
git commit -m "feat(enrichment): SourceRegistry + Source.probe 外部ID自动路由地基"
```

---

## 收尾：整体验证

- [ ] **跑全部 enrichment 单测无回归**

Run: `cd backend && STORAGE_BACKEND=local poetry run pytest tests/unit/services/enrichment/ -v`
Expected: 全部 passed（既有 + 本期新增 http_client/source_cache/registry/merge）。

- [ ] **提 PR**：`feature/content-enrichment-phase1a → staging`（用 `/pr`）。CI 绿后 squash 合并。本期纯后端、无网络、无迁移、不改部署。

---

## Self-Review（计划对照 spec）

- **§5 礼貌抓取**：PoliteSession（UA/限速/退避/熔断，Task 1）+ SourceCache（抓一次复用，Task 2）✓。批量/熔断的"批量"属连接器查询层（1b），本期客户端含熔断（耗尽重试抛错）。
- **§5b 权威性合并**：配置驱动优先级（Task 3）+ 非空才覆盖（Task 3）+ 同级冲突标记 `_conflicts`（Task 4）✓。字段级覆写（per-field precedence）较少用，下放 1c 按需（spec 标"可选配置"）。
- **§18b-6 源自动发现注册表**：`Source.probe` + `SourceRegistry.route` 外部 ID 路由（Task 5）✓。
- **不在本期**（明确）：连接器实现（WikipediaSource/JocondeSource/WikidataSource 多类别）= 1b；多类别骨架 seed + 抓取整合（图片可选/sitelinks 阈值/QID redirect）+ loader 用 `_conflicts` 标 needs_review + 馆名城市多语言补全 = 1c。
- **类型一致**：`merge_contributions(contribs, precedence=None)`、`ObjectContribution(source,qid,fields,raw)`、`SourceRegistry(sources).route(external_ids)/.get(name)`、`Source.probe(external_ids)`、`PoliteSession(user_agent,...).get_json(url,params,_transport)`、`SourceCache(storage,day).get_or_fetch(source,ident,fetch)` 跨任务一致 ✓。
