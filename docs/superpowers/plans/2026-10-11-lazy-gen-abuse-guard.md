# 懒生成防刷 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 懒生成点火前加"每账号 160 段 / 每 IP 300 段"两道日上限(按估算段数加权:生成 8、翻译 3),超了返回已有的 `daily_cap`。

**Architecture:** `lazy.py` 新增 `_charge()`:Redis 原子 `INCRBY` 两个按 UTC 日期分键的计数,超限即 `DECRBY` 回滚;Redis 不可用放行。`maybe_trigger` 在拿到锁之后、调度之前调用它,超限清锁返回 `"daily_cap"`。内容端点把调用者用户对象和客户端 IP 传进去,`can_preview` 豁免。

**Tech Stack:** FastAPI、SQLAlchemy、redis-py、fakeredis(测试)、pytest。

**Spec:** `docs/superpowers/specs/2026-10-11-lazy-gen-abuse-guard-design.md`

## Global Constraints

- 权重:懒生成 8、懒翻译 3(spec 第二节 prod 实测)。
- 上限:每账号 160 段/天、每 IP 300 段/天;全站 1000 段不改。
- `can_preview` 账号不受 ①② 限制,仍受全站 ③。
- 键:`lazy:u:{user_id}:{YYYYMMDD}`、`lazy:ip:{ip}:{YYYYMMDD}`(UTC 日期);每次 `INCRBY` 后都 `EXPIRE 172800`。
- Redis 不可用或抛异常 → 放行 + ERROR 日志。
- 超限返回 `"daily_cap"`;不新增/修改响应字段(契约零变化)。
- 只改 `backend/app/services/enrichment/lazy.py`、`backend/app/api/v1/endpoints/museums.py` 及测试。
- 测试命令统一:`cd backend && nice -n 19 $PY -m pytest -q --no-cov -p no:cacheprovider <files>`,
  `$PY=~/Library/Caches/pypoetry/virtualenvs/gomuseum-backend-eWQPCnDy-py3.13/bin/python`。

## Review Focus

1. 同一账号两个请求并发、剩余额度只够一次 → 只有一次成功(INCRBY 原子性)。→ Task 1 并发测试。
2. 超限那次被拒后计数不虚增(已回滚),否则用户第二天前就被永久卡死在线上。→ Task 1 回滚测试。
3. 一层超限时另一层也要回滚(账号未超、IP 超 → 账号计数也退回)。→ Task 1。
4. 没拿到锁(同件正在生成)不计数。→ Task 2。
5. 被 `_charge` 拒绝时锁必须清掉,否则这件会被"假生成中"卡 10 分钟。→ Task 2。

---

### Task 1: `_charge` 原子扣额度

**Files:**
- Modify: `backend/app/services/enrichment/lazy.py`(常量放 `_LAZY_DAILY_SECTION_CAP` 下方;函数放 `daily_budget_exhausted` 之后)
- Create: `backend/tests/unit/services/test_lazy_caps.py`

**Interfaces:**
- Produces: `WEIGHT_GENERATION = 8`、`WEIGHT_TRANSLATION = 3`、`CAP_PER_USER = 160`、`CAP_PER_IP = 300`;
  `_redis()` → redis 客户端或 None;
  `_charge(user_id: str | None, ip: str | None, weight: int, redis=None) -> str | None`:
  返回 None=放行;`"user"` / `"ip"`=该层超限(已回滚)。

- [ ] **Step 1: 写失败测试**

```python
"""懒生成每账号/每 IP 日上限(spec 2026-10-11 方案 A)。"""

import threading

import fakeredis
import pytest

from app.services.enrichment import lazy
from app.services.enrichment.lazy import (
    CAP_PER_IP,
    CAP_PER_USER,
    WEIGHT_GENERATION,
    _charge,
)


@pytest.fixture()
def r():
    return fakeredis.FakeRedis(decode_responses=True)


def _used(r, layer, ident):
    keys = r.keys(f"lazy:{layer}:{ident}:*")
    return int(r.get(keys[0])) if keys else 0


def test_under_cap_passes_and_counts_both_layers(r):
    assert _charge("u1", "1.2.3.4", 8, redis=r) is None
    assert _used(r, "u", "u1") == 8
    assert _used(r, "ip", "1.2.3.4") == 8
    assert 0 < r.ttl(r.keys("lazy:u:u1:*")[0]) <= 172800


def test_user_cap_blocks_and_rolls_back_both(r):
    for _ in range(CAP_PER_USER // WEIGHT_GENERATION):  # 20 次 = 160 段,正好到线
        assert _charge("u1", "1.2.3.4", 8, redis=r) is None
    assert _charge("u1", "1.2.3.4", 8, redis=r) == "user"
    assert _used(r, "u", "u1") == CAP_PER_USER  # 被拒那次已回滚
    assert _used(r, "ip", "1.2.3.4") == CAP_PER_USER  # 另一层也回滚


def test_ip_cap_blocks_across_accounts(r):
    n = 0
    while _charge(f"u{n}", "9.9.9.9", 8, redis=r) is None:  # 换号同 IP
        n += 1
    assert n == CAP_PER_IP // WEIGHT_GENERATION  # 37 件
    assert _used(r, "ip", "9.9.9.9") <= CAP_PER_IP
    assert _used(r, "u", f"u{n}") == 0  # 被拒账号的计数已回滚


def test_translation_weight_is_lighter(r):
    for _ in range(CAP_PER_USER // 3):  # 53 次翻译
        assert _charge("u1", "1.2.3.4", 3, redis=r) is None
    assert _charge("u1", "1.2.3.4", 3, redis=r) == "user"


def test_missing_ip_only_counts_user(r):
    assert _charge("u1", None, 8, redis=r) is None
    assert r.keys("lazy:ip:*") == []


def test_redis_unavailable_fails_open(monkeypatch):
    monkeypatch.setattr(lazy, "_redis", lambda: None)
    assert _charge("u1", "1.2.3.4", 8) is None


def test_redis_error_fails_open():
    class Boom:
        def pipeline(self):
            raise ConnectionError("down")

    assert _charge("u1", "1.2.3.4", 8, redis=Boom()) is None


def test_keys_are_per_utc_day(r, monkeypatch):
    from datetime import datetime, timezone

    class D:
        @staticmethod
        def now(tz=None):
            return datetime(2026, 10, 11, 23, 59, tzinfo=timezone.utc)

    monkeypatch.setattr(lazy, "datetime", D)
    _charge("u1", None, 8, redis=r)
    D.now = staticmethod(lambda tz=None: datetime(2026, 10, 12, 0, 1, tzinfo=timezone.utc))
    _charge("u1", None, 8, redis=r)
    assert sorted(r.keys("lazy:u:u1:*")) == ["lazy:u:u1:20261011", "lazy:u:u1:20261012"]


def test_concurrent_charges_never_exceed_cap(r):
    r.set("lazy:u:u1:" + lazy._today(), CAP_PER_USER - 8)  # 只剩一次的额度
    results = []
    barrier = threading.Barrier(2)

    def go():
        barrier.wait()
        results.append(_charge("u1", None, 8, redis=r))

    ts = [threading.Thread(target=go) for _ in range(2)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    assert sorted(results, key=str) == [None, "user"]
    assert _used(r, "u", "u1") == CAP_PER_USER
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && nice -n 19 $PY -m pytest -q --no-cov -p no:cacheprovider tests/unit/services/test_lazy_caps.py`
Expected: FAIL,`ImportError: cannot import name 'CAP_PER_IP'`

- [ ] **Step 3: 实现**

`lazy.py` 常量(放 `LAZY_SOURCE` 之后):

```python
# 每账号 / 每 IP 日上限(2026-10-11 方案 A)。单位与全站上限相同 = 段,
# 点火时按估算段数扣:prod 10-01~10-10 实测懒生成 7.2-8.9 段/件、懒翻译 2.7-3.0 段/次。
# 按"次数"计会让单 IP 100 次新生成 ≈ 800 段吃掉全站 80%(spec 第二节)。
WEIGHT_GENERATION = 8
WEIGHT_TRANSLATION = 3
CAP_PER_USER = 160  # ≈20 件新生成;挡单账号,也挡同一 WiFi 下一个人吃光整个 IP
CAP_PER_IP = 300  # ≈37 件;单 IP 最多吃全站 30%。⚠️对 IPv6/代理轮换无效,分布式只靠全站上限
_CAP_TTL_S = 2 * 86400
```

函数(放 `daily_budget_exhausted` 之后):

```python
def _redis():
    """复用识别缓存的 Redis 单例(自带连接失败冷却,Redis 挂了不会每次请求等超时)。"""
    from app.services.recognition.service import _get_redis

    return _get_redis()


def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d")


def _charge(user_id, ip, weight: int, redis=None) -> str | None:
    """按账号、按 IP 扣当日额度。None=放行;"user"/"ip"=该层超限(已全部回滚)。

    先 INCRBY 再判断:INCRBY 原子,两个 worker 并发也不会越线(先查后加会)。
    超限就把本次加上的全部退回,被拒的请求不占额度。
    Redis 不可用 → 放行(fail open):全站上限在 DB,照样兜底;反过来 Redis 一抖全站懒生成就停了。
    """
    layers = [
        (name, f"lazy:{name}:{ident}:{_today()}", cap)
        for name, ident, cap in (("u", user_id, CAP_PER_USER), ("ip", ip, CAP_PER_IP))
        if ident
    ]
    if not layers:
        return None
    r = redis if redis is not None else _redis()
    if r is None:
        logger.error("lazy caps: redis unavailable, allowing (global cap still applies)")
        return None
    try:
        pipe = r.pipeline()
        for _, key, _cap in layers:
            pipe.incrby(key, weight)
            pipe.expire(key, _CAP_TTL_S)  # 每次都设:键里带日期,重复设无害,不会漏设成永不过期
        used = pipe.execute()[0::2]
        over = [name for (name, _, cap), u in zip(layers, used) if int(u) > cap]
        if not over:
            return None
        pipe = r.pipeline()
        for _, key, _cap in layers:
            pipe.decrby(key, weight)
        pipe.execute()
        layer = "user" if "u" in over else "ip"
        logger.warning(
            "lazy: cap hit layer=%s user=%s ip=%s used=%s", layer, user_id, ip, used
        )
        return layer
    except Exception:
        logger.exception("lazy caps: redis error, allowing (global cap still applies)")
        return None
```

- [ ] **Step 4: 跑测试确认通过**

Run: 同 Step 2
Expected: 9 passed

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/enrichment/lazy.py backend/tests/unit/services/test_lazy_caps.py
git commit -m "feat(lazy): 每账号/每IP懒生成日上限的原子扣额度 _charge"
```

---

### Task 2: `maybe_trigger` 接入 `_charge`

**Files:**
- Modify: `backend/app/services/enrichment/lazy.py`(`maybe_trigger`)
- Modify: `backend/tests/integration/test_lazy_generation.py`(文件末尾追加)

**Interfaces:**
- Consumes: Task 1 的 `_charge`、`WEIGHT_GENERATION`、`WEIGHT_TRANSLATION`。
- Produces: `maybe_trigger(db, qid, *, schedule, environment=None, language=None, user_id=None, ip=None, exempt=False, redis=None) -> str | None`(新增参数全部可选、关键字)。

- [ ] **Step 1: 写失败测试**(追加到 `test_lazy_generation.py`)

```python
import fakeredis  # noqa: E402

from app.services.enrichment.lazy import CAP_PER_USER  # noqa: E402


def _full_user(r, uid="u1"):
    from app.services.enrichment.lazy import _today

    r.set(f"lazy:u:{uid}:{_today()}", CAP_PER_USER)


def test_per_user_cap_blocks_generation_and_clears_lock(session):
    r = fakeredis.FakeRedis(decode_responses=True)
    _full_user(r)
    scheduled = []
    reason = maybe_trigger(
        session, "Q1", schedule=lambda fn, *a: scheduled.append(fn),
        environment="staging", user_id="u1", ip="1.2.3.4", redis=r,
    )
    assert reason == "daily_cap"
    assert scheduled == []
    assert not _obj(session).attributes.get("lazy_lock_at")  # 锁已清,不会"假生成中"


def test_generation_charges_weight_8(session):
    from app.services.enrichment.lazy import _today

    r = fakeredis.FakeRedis(decode_responses=True)
    maybe_trigger(
        session, "Q1", schedule=lambda *a: None,
        environment="staging", user_id="u1", ip="1.2.3.4", redis=r,
    )
    assert r.get(f"lazy:u:u1:{_today()}") == "8"


def test_translation_charges_weight_3(session):
    from app.services.enrichment.lazy import _today

    o = _obj(session)
    o.content_status = "ready"
    session.commit()
    _publish(session, "Q1", "en")  # 文件里已有的 helper
    r = fakeredis.FakeRedis(decode_responses=True)
    maybe_trigger(
        session, "Q1", schedule=lambda *a: None, environment="staging",
        language="fr", user_id="u1", ip="1.2.3.4", redis=r,
    )
    assert r.get(f"lazy:u:u1:{_today()}") == "3"


def test_no_charge_when_lock_not_acquired(session):
    r = fakeredis.FakeRedis(decode_responses=True)
    try_acquire_lock(session, _obj(session))  # 别人正在生成
    maybe_trigger(
        session, "Q1", schedule=lambda *a: None,
        environment="staging", user_id="u1", ip="1.2.3.4", redis=r,
    )
    assert r.keys("lazy:*") == []


def test_exempt_skips_user_and_ip_caps(session):
    r = fakeredis.FakeRedis(decode_responses=True)
    _full_user(r)
    scheduled = []
    reason = maybe_trigger(
        session, "Q1", schedule=lambda fn, *a: scheduled.append(fn),
        environment="staging", user_id="u1", ip="1.2.3.4", exempt=True, redis=r,
    )
    assert reason is None
    assert len(scheduled) == 1


def test_exempt_still_bound_by_global_cap(session, monkeypatch):
    import app.services.enrichment.lazy as lazy

    monkeypatch.setattr(lazy, "daily_budget_exhausted", lambda db, **k: True)
    reason = maybe_trigger(
        session, "Q1", schedule=lambda *a: None, environment="staging",
        user_id="u1", exempt=True, redis=fakeredis.FakeRedis(decode_responses=True),
    )
    assert reason == "daily_cap"
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && nice -n 19 $PY -m pytest -q --no-cov -p no:cacheprovider tests/integration/test_lazy_generation.py`
Expected: 新增 6 条 FAIL(`TypeError: maybe_trigger() got an unexpected keyword argument 'user_id'`),原有全过。

- [ ] **Step 3: 实现**(改 `maybe_trigger` 签名与末尾两个分支)

签名:

```python
def maybe_trigger(
    db,
    qid: str,
    *,
    schedule,
    environment=None,
    language=None,
    user_id=None,
    ip=None,
    exempt=False,
    redis=None,
) -> str | None:
```

docstring 末尾追加一行:

```
    - user_id/ip:按账号/IP 扣当日额度(拿到锁后才扣,超了清锁返回 "daily_cap");
      exempt=运营预览账号,只受全站上限。
```

末尾替换为:

```python
    if wants_generation:
        if try_acquire_lock(db, o):
            if not exempt and _charge(user_id, ip, WEIGHT_GENERATION, redis):
                _clear_lock(db, o)
                return "daily_cap"
            schedule(run_lazy_generation, qid, language)
        return
    if try_acquire_lock(db, o, require_status=("ready",)):
        if not exempt and _charge(user_id, ip, WEIGHT_TRANSLATION, redis):
            _clear_lock(db, o)
            return "daily_cap"
        schedule(run_lazy_translation, qid, language)
```

- [ ] **Step 4: 跑测试确认通过**

Run: 同 Step 2
Expected: 全部 passed(原有 + 新增 6)

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/enrichment/lazy.py backend/tests/integration/test_lazy_generation.py
git commit -m "feat(lazy): maybe_trigger 拿锁后按账号/IP扣额度,超限清锁返回daily_cap"
```

---

### Task 3: 内容端点传入身份与 IP

**Files:**
- Modify: `backend/app/api/v1/endpoints/museums.py`(`_caller_id` → `_caller`;`object_content` 加 `request: Request`)
- Modify: `backend/tests/integration/test_object_content_endpoint.py`(末尾追加)

**Interfaces:**
- Consumes: Task 2 的 `maybe_trigger(..., user_id=, ip=, exempt=)`。
- Produces: `_caller(db, credentials) -> User | None`(坏/过期令牌 → None,绝不 401)。

- [ ] **Step 1: 写失败测试**(追加)

```python
def test_endpoint_passes_user_ip_and_preview_flag(client, monkeypatch):
    """端点把账号、客户端 IP、can_preview 交给 maybe_trigger(额度闸的输入)。"""
    import app.services.enrichment.lazy as lazy
    from app.services.auth_service import AuthService

    _make_stub(monkeypatch)
    seen = {}

    def spy(db, qid, **kw):
        seen.update(kw)
        return None

    monkeypatch.setattr(lazy, "maybe_trigger", spy)
    monkeypatch.setattr(
        AuthService,
        "get_current_user",
        staticmethod(lambda db, t: type("U", (), {"id": "user-9", "can_preview": True})()),
    )
    r = client.get(
        "/api/v1/museums/orsay/objects/Q1/content?language=zh",
        headers={"Authorization": "Bearer x"},
    )
    assert r.status_code == 200
    assert seen["user_id"] == "user-9"
    assert seen["exempt"] is True
    assert seen["ip"]  # TestClient 的 client.host("testclient"),非空即可


def test_per_user_cap_reaches_app_as_daily_cap(client, monkeypatch):
    """额度满 → 响应带 unavailable_reason=daily_cap,且一分钱不花。"""
    import fakeredis

    import app.services.enrichment.lazy as lazy

    _make_stub(monkeypatch)
    headers = _as_logged_in(monkeypatch)
    calls = []
    monkeypatch.setattr(lazy, "run_lazy_generation", lambda *a, **k: calls.append(a))
    r_ = fakeredis.FakeRedis(decode_responses=True)
    r_.set(f"lazy:u:user-1:{lazy._today()}", lazy.CAP_PER_USER)
    monkeypatch.setattr(lazy, "_redis", lambda: r_)

    r = client.get(
        "/api/v1/museums/orsay/objects/Q1/content?language=zh", headers=headers
    )
    assert r.status_code == 200
    assert r.json()["unavailable_reason"] == "daily_cap"
    assert r.json()["generating"] is False
    assert calls == []
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && nice -n 19 $PY -m pytest -q --no-cov -p no:cacheprovider tests/integration/test_object_content_endpoint.py`
Expected: 新增 2 条 FAIL(`KeyError: 'user_id'`;第二条 `unavailable_reason` 为 None)。

- [ ] **Step 3: 实现**

import 行加 `Request`:

```python
from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    HTTPException,
    Request,
    UploadFile,
)
```

`_caller_id` 改为:

```python
def _caller(db: Session, credentials: HTTPAuthorizationCredentials | None):
    """令牌 → 用户对象，**坏/过期令牌一律当匿名(None)，绝不 401**。

    与 `recognize_global._user_id` 同款。401 在这里是不能出的:老 App 拿着过期
    token 打探索页/详情页,一旦 401 整页就崩了 —— 而这两个端点本来就允许匿名读。
    """
    if not credentials:
        return None
    try:
        from app.services.auth_service import AuthService

        return AuthService.get_current_user(db, credentials.credentials)
    except Exception:
        return None
```

`object_content` 签名在 `background_tasks` 之后加 `request: Request,`;调用处改为:

```python
    reason = None
    user = _caller(db, credentials)
    if user is not None:
        reason = maybe_trigger(
            db,
            qid,
            schedule=background_tasks.add_task,
            language=language,
            user_id=str(user.id),
            # ProxyHeadersMiddleware(main.py)已把它解析成真实客户端 IP
            ip=request.client.host if request.client else None,
            exempt=bool(getattr(user, "can_preview", False)),
        )
```

- [ ] **Step 4: 跑相关全部测试**

Run: `cd backend && nice -n 19 $PY -m pytest -q --no-cov -p no:cacheprovider tests/integration/test_object_content_endpoint.py tests/integration/test_lazy_generation.py tests/unit/services/test_lazy_caps.py tests/unit/services/test_lazy_daily_budget.py tests/integration/test_visibility_gate.py tests/integration/test_share.py`
Expected: 全部 passed

- [ ] **Step 5: 跑后端全量 + 格式**

Run: `cd backend && nice -n 19 $PY -m pytest -q -p no:cacheprovider -x 2>&1 | tail -5 && $PY -m black --check app tests && $PY -m isort --check-only app tests`
Expected: 全部 passed、覆盖率闸通过;black/isort 无改动(有则 `black`/`isort` 后重跑)。

- [ ] **Step 6: Commit**

```bash
git add backend/app/api/v1/endpoints/museums.py backend/tests/integration/test_object_content_endpoint.py
git commit -m "feat(lazy): 内容端点把账号/IP/预览身份交给懒生成额度闸"
```

---

### Task 4: backlog 与契约回写

**Files:**
- Modify: `docs/ops/backlog.md`(第三节「游客令牌谁都能领」那行状态改为:已加每账号/每 IP 额度(#PR),剩 IPv6/代理分布式只靠全站上限;「数据源探活失败只写日志」那行补"Redis 故障时懒生成额度闸 fail-open 也无告警")

- [ ] **Step 1:** 改上述两行。
- [ ] **Step 2:** 按 [[contract-governance]] 判断是否回写 `docs/architecture/museum-api-contract.md`:本改动无新字段、无端点变化 → 只在懒生成相关纪律(搜 `daily_cap`)补一句"另有每账号 160 / 每 IP 300 段的日额度(Redis,fail-open)";若无相关纪律则不写。
- [ ] **Step 3: Commit**

```bash
git add docs/ops/backlog.md docs/architecture/museum-api-contract.md
git commit -m "docs: 懒生成每账号/每IP额度回写 backlog 与契约"
```
