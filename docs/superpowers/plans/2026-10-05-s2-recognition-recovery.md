# S2 识别找回 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 用户识别中锁屏/切走/断网,回来时直接看到结果,且不重复扣次。

**Architecture:** 后端在 `recognize()` 里以现有缓存键加 Redis 在途锁:同键第二个请求不重算,轮询等首请求写缓存;锁在独立 `finally` 释放,锁消失仍无缓存或等满 90s 就自己算。前端 `RecognitionNotifier.recognize` 遇到超时/断连/网关 5xx 自动用同一张照片重发一次(后台失败则等回前台再发);加载卡片在 10s/20s 换两段提示文案。

**Tech Stack:** FastAPI + redis-py(测试用 fakeredis,已在 pyproject `test` extras);Flutter + Riverpod + Dio;flutter gen-l10n(10 语 arb)。

**Spec:** `docs/superpowers/specs/2026-10-05-recognition-failure-feedback-design.md` §四 S2、§六测试要点

## Global Constraints

- 契约只做加法:响应形状不变,老 App 不受影响(老 App 重发同图也会享受合并)。
- 计费:重发/等待者拿到首请求结果时**不得再扣次**;其余计费语义完全不变(现有计费测试全绿)。
- 等待者内部上限 90s,必须短于 nginx `proxy_read_timeout` 120s。
- 锁释放不得依赖「缓存里出现了值」(写缓存失败被吞时首请求照常返回)。
- 前端只重发**一次**;402 与 4xx 业务错误不重发;500 仍是失败不重发(现有测试 `recognize maps 500 to ServerException` 保持绿)。
- 等待提示只承诺「切到其他应用」,不承诺离开页面(用户 2026-10-05)。
- Flutter 解析禁止裸 `as String`;Python 过 black/isort;dart format。
- 测试命令:后端 `cd backend && poetry run python -m pytest --no-cov <path>`(系统 python 缺 cv2);前端 `cd frontend/gomuseum_app && flutter test <path>`。
- 按「跨配置维度测试」:Redis 可用(fakeredis)/不可用(conftest 默认 `_get_redis→None`)两侧都要有测试。

## 与 spec 的一处有意偏离

spec 写「finally 释放锁 + 显式写短 TTL 就绪标记」。本计划**不写就绪标记**:`finally` 里删掉锁键本身就是「首请求已结束(成功或失败)」的信号,等待者看到锁消失就最后读一次缓存,读不到就自己算。效果与就绪标记相同,少一个键。评审 P1 的关切(不靠缓存出现值判完成)由「锁消失」满足,测试 `test_inflight_lock_gone_without_cache_waiter_computes` 钉住。

## Review Focus

1. **首请求写缓存失败**(Redis setex 抛错被吞):等待者必须在锁消失后自己算,不能等满 90s → Task 1 `test_inflight_lock_gone_without_cache_waiter_computes` + `test_lock_released_when_cache_write_fails`。
2. **首请求抛异常**(向量检索/GPT 崩):锁必须释放,不能留 150s 死锁让后续同图请求都干等 → Task 1 `test_lock_released_when_compute_raises`。
3. **已登录用户重发撞上首请求还没扣完/没解锁**:等待者若按普通缓存命中走计费会再扣一次 → Task 1 `test_billing_inflight_waiter_not_charged`。
4. **断网时重发仍失败**:只能重发一次,第二次失败落「识别失败」,不能无限重试 → Task 2 `transient twice → error, exactly two sends`。
5. **App 在后台时请求失败**:重发必须等回前台,而不是在后台立刻发(后台网络多半仍不可用)→ Task 2 `waits for foreground before resending`。

## 独立评审处理(2026-10-06,Fable)

| 级别 | 意见 | 处理 |
|---|---|---|
| P1 | notifier 是 autoDispose,「回来时结果还在」未分析;安卓后台杀进程会丢结果 | **不加 keepAlive**:相机页 `build` 里 `ref.watch` 着它,切后台/锁屏不销毁页面,监听不归零;只有用户自己离开相机页才会释放,那时结果本就不需要。**进程被杀**列为已知局限(见下),真机验收若复现再议 |
| P1 | 等满 90s 再自算,可能顶到 nginx 120s 被 502 | **不改上限,理由**:真正卡死用户的是**客户端** 60s receiveTimeout(< nginx 120s)——重发请求 60s 后 App 已放弃,之后服务端 502 与否用户都看不见;上限在 60-90s 间取值不改变用户结果,只影响服务端重复算:90s 让「首请求在 60-90s 间算完」时等待者直接拿缓存、不重算,比更短的上限省钱。超过 60s 的长尾即 spec 已登记的「~180s 长尾」遗留,等 S1 数据 |
| P2 | 等满后多个等待者可能同时自算 | 记为已知局限(首请求真卡死才发生,仍严格优于现状的每次重发必重算) |
| P2 | `untilAppResumed` 真实实现无自动化测试 | **已补**:Task 2 Step 2b 用 `handleAppLifecycleStateChanged` 驱动生命周期测它 |
| P2 | 同步端点 sleep 占线程池 | 同意当前规模可接受,保留 ponytail 注释 |

**已知局限**(Task 4 写进 spec 状态):①安卓在后台因内存压力杀掉进程 → 回来是冷启动,本次识别结果丢失(服务端已算完、已扣次的话结果在足迹里);②首请求卡死时多个等待者 90s 后各自重算;③客户端两次各等 60s,超过的长尾仍失败(spec 原遗留)。

---

### Task 1: 后端同键在途合并 + 等待者不扣次

**Files:**
- Modify: `backend/app/services/recognition/service.py`(`recognize()` 约 302-499 行;`recognize_billed()` 约 552-644 行)
- Test: `backend/tests/unit/services/recognition/test_service.py`(追加)
- Test: `backend/tests/integration/test_recognize_flow.py`(追加)

**Interfaces:**
- Produces: 模块常量 `_INFLIGHT_TTL_S = 150`、`_WAIT_CAP_S = 90`、`_WAIT_POLL_S = 0.5`;函数 `_inflight_key(ckey: str) -> str`、`_wait_inflight(redis, ckey: str) -> str | None`;等待者事件 `engine="cache"` 且 `timings` 含键 `inflight_wait`;等待者结果 `_billed == "inflight"`(内部字段,`recognize_billed` pop 掉,不进响应)。

- [ ] **Step 1: 写失败测试(unit)**

追加到 `backend/tests/unit/services/recognition/test_service.py` 末尾:

```python
# ---------- S2 同键在途合并 ----------
import json
import threading

import fakeredis

from app.services.image_service import ImageService
from app.services.recognition import service as svc


def _ckey(img, slug="orsay", language="zh"):
    return svc._cache_key(slug, ImageService.generate_hash(img), language, None)


@pytest.fixture()
def fast_poll(monkeypatch):
    monkeypatch.setattr(svc, "_WAIT_POLL_S", 0.02)


def test_first_request_takes_and_releases_lock(session):
    r = fakeredis.FakeRedis(decode_responses=True)
    img = _jpeg()
    vq = _FakeVQ([("Q334138", 0.95)])
    recognize(session, "orsay", img, embed_fn=lambda b: "V", vector_query_fn=vq, redis=r)
    assert r.get(_ckey(img)) is not None
    assert not r.exists(svc._inflight_key(_ckey(img)))


def test_inflight_waiter_reuses_first_result(session, fast_poll):
    """同键已在算:第二个请求不重算,拿首请求写进缓存的结果。"""
    r = fakeredis.FakeRedis(decode_responses=True)
    img = _jpeg()
    ck = _ckey(img)
    first_out = {"outcome": "unrecognized", "match": None, "candidates": [],
                 "label_text": None, "reason": "no_candidates", "phash": "x"}
    r.set(svc._inflight_key(ck), "1")

    def finish_first():
        r.setex(ck, 60, json.dumps(first_out))
        r.delete(svc._inflight_key(ck))

    threading.Timer(0.1, finish_first).start()
    embed = _Counter(lambda b: "V")
    out = recognize(session, "orsay", img, embed_fn=embed, redis=r,
                    identify_fn=_vision())
    assert embed.n == 0  # 没重算
    assert out["outcome"] == "unrecognized"
    assert out["_billed"] == "inflight"
    ev = session.query(RecognitionEvent).one()
    assert ev.engine == "cache"
    assert "inflight_wait" in ev.timings


def test_inflight_lock_gone_without_cache_waiter_computes(session, fast_poll):
    """首请求结束但缓存没写上(写缓存异常被吞):等待者看到锁消失就自己算,不等满上限。"""
    r = fakeredis.FakeRedis(decode_responses=True)
    img = _jpeg()
    ck = _ckey(img)
    r.set(svc._inflight_key(ck), "1")
    threading.Timer(0.1, lambda: r.delete(svc._inflight_key(ck))).start()
    vq = _FakeVQ([("Q334138", 0.95)])
    embed = _Counter(lambda b: "V")
    out = recognize(session, "orsay", img, embed_fn=embed, vector_query_fn=vq, redis=r)
    assert embed.n == 1
    assert out["outcome"] == "match"
    assert session.query(RecognitionEvent).one().engine == "vector"


def test_inflight_wait_cap_then_computes(session, fast_poll, monkeypatch):
    """首请求一直不结束(进程卡死):等到上限后自己算。"""
    monkeypatch.setattr(svc, "_WAIT_CAP_S", 0.2)
    r = fakeredis.FakeRedis(decode_responses=True)
    img = _jpeg()
    r.set(svc._inflight_key(_ckey(img)), "1")
    vq = _FakeVQ([("Q334138", 0.95)])
    embed = _Counter(lambda b: "V")
    out = recognize(session, "orsay", img, embed_fn=embed, vector_query_fn=vq, redis=r)
    assert embed.n == 1
    assert out["outcome"] == "match"


def test_lock_released_when_compute_raises(session):
    r = fakeredis.FakeRedis(decode_responses=True)
    img = _jpeg()

    def boom(db, vec, museum_id):
        raise RuntimeError("vector index down")

    with pytest.raises(RuntimeError):
        recognize(session, "orsay", img, embed_fn=lambda b: "V",
                  vector_query_fn=boom, redis=r)
    assert not r.exists(svc._inflight_key(_ckey(img)))


def test_lock_released_when_cache_write_fails(session):
    class _NoWrite(fakeredis.FakeRedis):
        def setex(self, *a, **k):
            raise ConnectionError("write failed")

    r = _NoWrite(decode_responses=True)
    img = _jpeg()
    vq = _FakeVQ([("Q334138", 0.95)])
    out = recognize(session, "orsay", img, embed_fn=lambda b: "V",
                    vector_query_fn=vq, redis=r)
    assert out["outcome"] == "match"  # 写缓存失败不影响首请求
    assert not r.exists(svc._inflight_key(_ckey(img)))
```

- [ ] **Step 2: 写失败测试(计费,integration)**

追加到 `backend/tests/integration/test_recognize_flow.py` 末尾:

```python
def test_billing_inflight_waiter_not_charged(session, monkeypatch):
    """⭐ S2:已登录用户超时后重发同一张照片,首请求还在服务端算 → 重发变成等待者。
    首请求自己会扣次+解锁;等待者若按普通缓存命中走计费,此刻首请求的解锁还没提交
    → `free_audio_qids` 里没有这件 → 再扣一次 = 一张照片扣两次。"""
    import json
    import threading

    import fakeredis

    from app.services.image_service import ImageService
    from app.services.recognition import service as svc
    from app.services.recognition.service import recognize_billed

    monkeypatch.setattr(svc, "_WAIT_POLL_S", 0.02)
    UB = _benefits_tables(session)
    img = _jpeg()
    r = fakeredis.FakeRedis(decode_responses=True)
    # 先造一份首请求的 match 结果(不经计费),再把它挪成「首请求还在算」的现场
    recognize(session, "orsay", img, redis=r, **_match_kw())
    ck = svc._cache_key("orsay", ImageService.generate_hash(img), "zh", None)
    first_json = r.get(ck)
    r.delete(ck)
    r.set(svc._inflight_key(ck), "1")

    def finish_first():
        r.setex(ck, 60, first_json)
        r.delete(svc._inflight_key(ck))

    threading.Timer(0.1, finish_first).start()
    out = recognize_billed(
        session, "orsay", img, user_id="u-resend", device_id="dev1",
        redis=r, **_match_kw(),
    )
    assert out["outcome"] == "match"
    assert "_billed" not in out  # 内部字段不进响应
    ub = session.query(UB).filter_by(user_id="u-resend").one_or_none()
    assert ub is None or ub.recognition_quota == FREE  # 没扣
```

> 注:若 `UserBenefits` 的用户列名不是 `user_id`,按 `app/models/user_benefits.py` 实际列名改这一行断言;语义是「u-resend 的额度没动」。

- [ ] **Step 3: 跑测试确认失败**

Run: `cd backend && poetry run python -m pytest --no-cov tests/unit/services/recognition/test_service.py -k "inflight or lock_released or takes_and_releases" tests/integration/test_recognize_flow.py::test_billing_inflight_waiter_not_charged -v`
Expected: FAIL(`AttributeError: module ... has no attribute '_inflight_key'` 等)

- [ ] **Step 4: 实现 —— 常量与等待函数**

在 `service.py` 中 `_get_redis()` 定义之后加:

```python
# S2 同键在途合并:App 超时后用同一张照片重发时,首请求在服务端往往还在算
# (同步端点不随客户端断开而停)。第二个同键请求不重算,等首请求的结果。
_INFLIGHT_TTL_S = 150  # 锁自身过期:进程被杀也不留死锁;须长于最慢一次识别
_WAIT_CAP_S = 90  # 等待者上限:短于 nginx proxy_read_timeout 120s
_WAIT_POLL_S = 0.5


def _inflight_key(ckey: str) -> str:
    return ckey + ":inflight"


def _wait_inflight(redis, ckey: str) -> str | None:
    """轮询等首请求写缓存。锁消失(首请求已结束)仍无缓存、或到上限 → None,调用方自己算。
    不靠「缓存里出现值」判完成:写缓存失败被吞时首请求照常返回,缓存永远不会出现。
    ponytail: 等待占一个线程池线程(同步端点),最多 90s;并发重发多到占满线程池时改异步等待。
    """
    deadline = time.monotonic() + _WAIT_CAP_S
    while time.monotonic() < deadline:
        time.sleep(_WAIT_POLL_S)
        hit = redis.get(ckey)
        if hit:
            return hit
        if not redis.exists(_inflight_key(ckey)):
            return redis.get(ckey)  # 两次读之间首请求恰好写完缓存并释放锁
    return None
```

- [ ] **Step 5: 实现 —— 把缓存之后的计算段原样抽成 `_compute`**

把 `recognize()` 里从 `from app.services.storage import get_object_storage` 到函数末尾 `return out` 的整段**原样剪切**(缩进不变,一行不改)到一个新函数体内,放在 `recognize()` 之前:

```python
def _compute(
    db,
    slug,
    museum,
    image_bytes: bytes,
    *,
    phash,
    language,
    mode,
    identify_fn,
    embed_fn,
    vector_query_fn,
    embed_crops_fn,
    embed_canvas_fn,
    user_id,
    visible,
    redis,
    ckey,
    clock,
) -> dict:
    """缓存未命中后的真识别:向量三档 → GPT+文字兜底 → 记事件 → 写缓存。"""
    from app.services.storage import get_object_storage
    # ……(原样剪切过来的代码,直到 return out)
```

- [ ] **Step 6: 实现 —— `recognize()` 的缓存段加锁/等待,计算段包 try/finally**

把 `recognize()` 中从 `redis = redis if redis is not None else _get_redis()` 起到原缓存 `except` 结束的部分,替换为:

```python
    redis = redis if redis is not None else _get_redis()
    ckey = _cache_key(slug, sha, language, visible)
    owns_lock = False
    if redis is not None:
        try:
            hit = redis.get(ckey)
            clock.mark("cache_get")
            if not hit:
                owns_lock = bool(
                    redis.set(_inflight_key(ckey), "1", nx=True, ex=_INFLIGHT_TTL_S)
                )
                if not owns_lock:
                    hit = _wait_inflight(redis, ckey)
                    clock.mark("inflight_wait")
            if hit:
                cached_out = json.loads(hit)
                # 缓存命中:计费层据此不扣次。等来的是在途首请求的结果 → "inflight",
                # 计费层对它一律不扣(首请求自己会扣/解锁,见 recognize_billed)
                cached_out["_billed"] = (
                    "inflight" if "inflight_wait" in clock.stages else True
                )
                cached_out["phash"] = phash  # 升级前旧缓存条目无 phash,命中时补齐
                tq, ts = _top_of(cached_out)
                record_event(
                    db,
                    museum_slug=slug,
                    phash=phash,
                    outcome=cached_out.get("outcome"),
                    top_qid=tq,
                    top_score=ts,
                    language=language,
                    engine="cache",
                    user_id=user_id,
                    duration_ms=clock.total_ms(),
                    timings=clock.stages,
                )
                return cached_out
        except Exception:
            # 缓存不可用不阻断识别;超时那段也记在 cache_get,别算到下一阶段头上
            clock.mark("cache_get")

    try:
        return _compute(
            db,
            slug,
            museum,
            image_bytes,
            phash=phash,
            language=language,
            mode=mode,
            identify_fn=identify_fn,
            embed_fn=embed_fn,
            vector_query_fn=vector_query_fn,
            embed_crops_fn=embed_crops_fn,
            embed_canvas_fn=embed_canvas_fn,
            user_id=user_id,
            visible=visible,
            redis=redis,
            ckey=ckey,
            clock=clock,
        )
    finally:
        # 独立 finally:首请求成功、异常、写缓存失败,锁都必须放掉(等待者靠它判结束)
        if owns_lock:
            try:
                redis.delete(_inflight_key(ckey))
            except Exception:
                logger.warning("recognition inflight lock release failed: %s", ckey)
```

注意:旧测试里手写的 `_FakeRedis` 只有 `get/setex`、没有 `set` → 未命中时 `redis.set` 抛 AttributeError → 落进 `except` 照常计算,`owns_lock` 仍为 False。这是预期行为(Redis 半坏也不阻断识别),旧测试应保持绿。

- [ ] **Step 7: 实现 —— 计费层不给等待者扣次**

`recognize_billed()` 中,在 `if out.get("outcome") != "match": return out` 之后紧接着加:

```python
    if cached == "inflight":
        # S2:等来的是同一张照片在途首请求的结果,首请求自己会按规则扣次/解锁。
        # 这里再判就会撞上「首请求的解锁还没提交」→ 一张照片扣两次。
        # ponytail: 不区分首请求是不是同一个人(不同人同一时刻传同一份字节≈不存在);
        # 真要区分时把 user_id/device_id 写进锁值再比对。
        return out
```

- [ ] **Step 8: 跑新测试确认通过**

Run: 同 Step 3 的命令
Expected: PASS(7 个)

- [ ] **Step 9: 跑识别与计费全量,确认旧测试全绿**

Run: `cd backend && poetry run python -m pytest --no-cov tests/unit/services/recognition tests/integration/test_recognize_flow.py tests/integration/test_pass_scope_by_museum.py tests/integration/test_visibility_gate.py tests/unit/api/test_recognize_global.py -q`
Expected: 全部 PASS;`test_default_redis_cache_actually_hits` 在本机无 Redis 时 SKIP 属正常。

- [ ] **Step 10: 破坏验证(先提交再破坏,纪律:破坏验证前先提交)**

```bash
cd /Users/hongyang/Projects/GoMuseum
black backend/app/services/recognition/service.py backend/tests/unit/services/recognition/test_service.py backend/tests/integration/test_recognize_flow.py
isort backend/app/services/recognition/service.py backend/tests/unit/services/recognition/test_service.py backend/tests/integration/test_recognize_flow.py
git add backend/app/services/recognition/service.py backend/tests/unit/services/recognition/test_service.py backend/tests/integration/test_recognize_flow.py
git commit -m "feat(recognize): 同键在途合并,重发不重算不重复扣次(S2)"
```

然后逐个临时破坏、确认对应测试变红、再 `git checkout backend/app/services/recognition/service.py` 还原:
1. 删掉 `finally` 里的 `redis.delete(...)` → `test_lock_released_when_compute_raises`、`test_lock_released_when_cache_write_fails`、`test_first_request_takes_and_releases_lock` 红。
2. `_wait_inflight` 里删掉 `if not redis.exists(...)` 分支 → `test_inflight_lock_gone_without_cache_waiter_computes` 红(等满 90s 超时,可加 `--timeout` 或观察耗时)。
3. 删掉 Step 7 的 `if cached == "inflight": return out` → `test_billing_inflight_waiter_not_charged` 红。

在 ledger 记下三次破坏的结果。

---

### Task 2: 前端失败即重发一次(后台失败等回前台)

**Files:**
- Modify: `frontend/gomuseum_app/lib/features/recognition/data/datasources/recognition_remote_datasource.dart`(`recognize()` 的 `on DioException` 分支)
- Modify: `frontend/gomuseum_app/lib/features/recognition/presentation/providers/recognition_provider.dart`
- Test: `frontend/gomuseum_app/test/features/recognition/data/datasources/recognition_remote_datasource_test.dart`(追加)
- Test: Create `frontend/gomuseum_app/test/features/recognition/presentation/providers/recognition_retry_test.dart`

**Interfaces:**
- Produces: `final foregroundWaiterProvider = Provider<Future<void> Function()>(...)`(recognition_provider.dart,测试里覆盖成立即返回);`Future<void> untilAppResumed()`。
- 数据源:502/503/504 → `NetworkException`;500 仍 `ServerException`。

- [ ] **Step 1: 写失败测试(数据源 502)**

追加到 `recognition_remote_datasource_test.dart` 的 `main()` 内(紧跟 500 那条之后):

```dart
  // 部署重启时 nginx 回 502:与断网同类,交给上层重发(S2)。500 是真错误,仍是失败。
  test('recognize maps 502 to NetworkException (retryable)', () async {
    when(() => dio.post(any(),
            data: any(named: 'data'),
            queryParameters: any(named: 'queryParameters'),
            options: any(named: 'options')))
        .thenThrow(DioException(
            requestOptions: RequestOptions(path: '/api/v1/recognize'),
            type: DioExceptionType.badResponse,
            response: Response(
                requestOptions: RequestOptions(path: '/api/v1/recognize'),
                statusCode: 502)));

    await expectLater(ds.recognize(slug: null, image: image(), language: 'en'),
        throwsA(isA<NetworkException>()));
  });
```

- [ ] **Step 2: 写失败测试(notifier 重发)**

Create `test/features/recognition/presentation/providers/recognition_retry_test.dart`:

```dart
import 'dart:typed_data';

import 'package:cross_file/cross_file.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gomuseum_app/core/error/exceptions.dart';
import 'package:gomuseum_app/features/payment/presentation/providers/benefits_provider.dart';
import 'package:gomuseum_app/features/recognition/data/datasources/recognition_remote_datasource.dart';
import 'package:gomuseum_app/features/recognition/data/models/recognize_response.dart';
import 'package:gomuseum_app/features/recognition/presentation/providers/recognition_provider.dart';
import 'package:gomuseum_app/features/recognition/presentation/providers/recognition_providers.dart';

/// 按调用序依次抛错/返回;记录调用次数与发生顺序。
class _ScriptedDs implements RecognitionRemoteDataSource {
  _ScriptedDs(this.script, this.log);
  final List<Object> script; // Exception = 抛;RecognizeResponse = 返回
  final List<String> log;
  int calls = 0;

  @override
  Future<RecognizeResponse> recognize({
    String? slug,
    required XFile image,
    required String language,
    String mode = 'artwork',
    String? deviceId,
  }) async {
    final step = script[calls++];
    log.add('send');
    if (step is RecognizeResponse) return step;
    throw step;
  }

  @override
  Future<void> confirm({required String phash, required String qid}) async {}

  @override
  Future<Never> recognizeArtwork(XFile imageFile) async =>
      throw UnimplementedError();
}

final _unrecognized =
    RecognizeResponse.fromJson(const {'outcome': 'unrecognized'});

void main() {
  late List<String> log;

  Future<(RecognitionState, _ScriptedDs)> run(List<Object> script) async {
    final ds = _ScriptedDs(script, log);
    final container = ProviderContainer(overrides: [
      recognitionRemoteDataSourceProvider.overrideWithValue(ds),
      deviceIdProvider.overrideWith((ref) async => 'dev-1'),
      foregroundWaiterProvider.overrideWithValue(() async => log.add('fg')),
    ]);
    addTearDown(container.dispose);
    await container.read(recognitionNotifierProvider.notifier).recognize(
          image: XFile.fromData(Uint8List.fromList(const [0, 1]),
              name: 'x.jpg', mimeType: 'image/jpeg'),
          language: 'en',
        );
    return (container.read(recognitionNotifierProvider), ds);
  }

  setUp(() => log = []);

  test('timeout then success → result, sent twice', () async {
    final (st, ds) = await run([const TimeoutException(), _unrecognized]);
    expect(st, isA<RecognitionUnrecognized>());
    expect(ds.calls, 2);
  });

  test('network error then success → result', () async {
    final (st, ds) = await run([const NetworkException(), _unrecognized]);
    expect(st, isA<RecognitionUnrecognized>());
    expect(ds.calls, 2);
  });

  test('transient twice → error, exactly two sends (only one retry)',
      () async {
    final (st, ds) = await run(
        [const NetworkException(), const NetworkException(), _unrecognized]);
    expect(st, isA<RecognitionError>());
    expect(ds.calls, 2);
  });

  test('waits for foreground before resending', () async {
    await run([const TimeoutException(), _unrecognized]);
    expect(log, ['send', 'fg', 'send']);
  });

  test('server error (500) is not retried', () async {
    final (st, ds) = await run([const ServerException('boom'), _unrecognized]);
    expect(st, isA<RecognitionError>());
    expect(ds.calls, 1);
  });

  test('402 is not retried', () async {
    final (st, ds) =
        await run([const QuotaExceededException(), _unrecognized]);
    expect(st, isA<RecognitionQuotaExceeded>());
    expect(ds.calls, 1);
  });
}
```

> 若 `RecognizeResponse.fromJson` 对只含 `outcome` 的 map 报错,按 `recognize_response.dart` 补齐必需键(如 `'candidates': []`),保持 outcome=unrecognized 语义。

- [ ] **Step 2b: 写失败测试(真实的等前台实现)**

在 `recognition_retry_test.dart` 顶部加 `import 'dart:async' hide TimeoutException;` 与 `import 'package:flutter/widgets.dart';`,`main()` 末尾追加:

```dart
  testWidgets('untilAppResumed: completes immediately when resumed',
      (tester) async {
    tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.resumed);
    var done = false;
    unawaited(untilAppResumed().then((_) => done = true));
    await tester.pump();
    expect(done, isTrue);
  });

  testWidgets('untilAppResumed: waits while paused, completes on resume',
      (tester) async {
    tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.inactive);
    tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.hidden);
    tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.paused);
    var done = false;
    unawaited(untilAppResumed().then((_) => done = true));
    await tester.pump();
    expect(done, isFalse);
    tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.hidden);
    tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.inactive);
    tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.resumed);
    await tester.pump();
    expect(done, isTrue);
  });
```

(Flutter 对生命周期跳变有合法性断言,所以按 inactive→hidden→paused 逐级走;若断言仍报非法跳变,按报错提示补齐中间态。)

- [ ] **Step 3: 跑测试确认失败**

Run: `cd frontend/gomuseum_app && flutter test test/features/recognition/presentation/providers/recognition_retry_test.dart test/features/recognition/data/datasources/recognition_remote_datasource_test.dart`
Expected: FAIL(`foregroundWaiterProvider` 未定义编译错误)

- [ ] **Step 4: 实现数据源 502/503/504 映射**

`recognition_remote_datasource.dart` 的 `recognize()` 里,在 402 分支 `}` 之后、`throw ServerException('Server error: ${e.message}');` 之前加:

```dart
      // 网关类 5xx(部署重启时 nginx 502 等)= 服务暂时不可用,与断网同类:交给上层重发(S2)。
      // 500 是服务端真错误,重发也没用,仍按失败处理。
      const gateway = {502, 503, 504};
      if (gateway.contains(e.response?.statusCode)) {
        throw const NetworkException('Server temporarily unavailable');
      }
```

- [ ] **Step 5: 实现 notifier 重发**

`recognition_provider.dart`:

1. 顶部导入改为(本文件用到 `unawaited`;我们自己的 `TimeoutException` 与 dart:async 同名,必须 hide):

```dart
import 'dart:async' hide TimeoutException;

import 'package:cross_file/cross_file.dart';
import 'package:flutter/widgets.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';
```

(其余原有 import 保留。)

2. 在 `class RecognitionNotifier` 之前加:

```dart
/// 等到 App 回到前台(S2:后台里失败的请求,切回来再重发)。测试里覆盖成立即返回。
final foregroundWaiterProvider =
    Provider<Future<void> Function()>((ref) => untilAppResumed);

Future<void> untilAppResumed() {
  final s = WidgetsBinding.instance.lifecycleState;
  if (s == null || s == AppLifecycleState.resumed) return Future.value();
  final done = Completer<void>();
  late final AppLifecycleListener listener;
  listener = AppLifecycleListener(onResume: () {
    listener.dispose();
    done.complete();
  });
  return done.future;
}

/// 值得用同一张照片重发的失败:超时、断连、网关 5xx(数据源已映射成 NetworkException)。
bool _isTransient(Object e) => e is TimeoutException || e is NetworkException;
```

3. `recognize()` 内把

```dart
      final resp = await ds.recognize(
          slug: slug,
          image: image,
          language: language,
          mode: mode,
          deviceId: deviceId);
```

替换为:

```dart
      final waitForeground = ref.read(foregroundWaiterProvider);
      Future<RecognizeResponse> send() => ds.recognize(
          slug: slug,
          image: image,
          language: language,
          mode: mode,
          deviceId: deviceId);
      RecognizeResponse resp;
      try {
        resp = await send();
      } catch (e) {
        if (!_isTransient(e)) rethrow;
        // S2 失败即重发:锁屏/切后台时系统会不会断连,代码里判断不了、各厂商也不同,
        // 两种情况都兜住。同一张照片 → 服务端同键在途合并或缓存命中,不重算不重复扣。
        // 只重发一次;后台失败先等回前台(后台网络多半还不通)。
        await waitForeground();
        resp = await send();
      }
```

(外层原有的 `on QuotaExceededException` / `catch (_)` 不动:第二次失败照常落 `RecognitionError`。)

- [ ] **Step 6: 跑测试确认通过 + 旧测试全绿**

Run: `cd frontend/gomuseum_app && flutter test test/features/recognition && flutter analyze lib/features/recognition`
Expected: 全 PASS;analyze 无新增 issue。

- [ ] **Step 7: 提交**

```bash
cd /Users/hongyang/Projects/GoMuseum/frontend/gomuseum_app
dart format lib/features/recognition test/features/recognition
cd /Users/hongyang/Projects/GoMuseum
git add frontend/gomuseum_app/lib/features/recognition/data/datasources/recognition_remote_datasource.dart frontend/gomuseum_app/lib/features/recognition/presentation/providers/recognition_provider.dart frontend/gomuseum_app/test/features/recognition/data/datasources/recognition_remote_datasource_test.dart frontend/gomuseum_app/test/features/recognition/presentation/providers/recognition_retry_test.dart
git commit -m "feat(recognition): 超时/断连自动用同一张照片重发一次,后台失败等回前台(S2)"
```

- [ ] **Step 8: 破坏验证**

临时把 `_isTransient` 改成恒 `false` → `timeout then success`、`waits for foreground` 红;改回。临时去掉 `await waitForeground();` → `waits for foreground` 红;改回。ledger 记结果。

---

### Task 3: 等待分段提示(10s / 20s)

**Files:**
- Create: `frontend/gomuseum_app/lib/features/recognition/presentation/widgets/recognition_wait_hint.dart`
- Modify: `frontend/gomuseum_app/lib/features/recognition/presentation/pages/camera_page.dart`(`_loadingContent`,约 810-830 行)
- Modify: `frontend/gomuseum_app/lib/l10n/app_{zh,zh_Hant,en,fr,de,es,it,ja,ko,pl}.arb` + 重新生成 `app_localizations*.dart`
- Test: Create `frontend/gomuseum_app/test/features/recognition/presentation/recognition_wait_hint_test.dart`

**Interfaces:**
- Produces: `class RecognitionWaitHint extends StatefulWidget { const RecognitionWaitHint({super.key, required this.style}); final TextStyle style; }`;l10n 键 `recWaitSlow`、`recWaitSwitchApp`。

- [ ] **Step 1: 加 l10n 文案(10 语)**

在每个 arb 的 `"camComparing"` 行之后加两行(zh/en 带 `@` 描述按该文件既有惯例,其余只加值):

| arb | recWaitSlow | recWaitSwitchApp |
|---|---|---|
| zh | 比平时多花了点时间，还在找 | 可以先切到其他应用，回来时结果还在 |
| zh_Hant | 比平時多花了點時間，還在找 | 可以先切到其他應用程式，回來時結果還在 |
| en | Taking a bit longer than usual — still looking | You can switch to another app — the result will be here when you come back |
| fr | Un peu plus long que d'habitude — on cherche encore | Vous pouvez passer à une autre app : le résultat sera là à votre retour |
| de | Dauert etwas länger als sonst – wir suchen noch | Sie können zu einer anderen App wechseln – das Ergebnis ist da, wenn Sie zurückkommen |
| es | Está tardando un poco más de lo normal; seguimos buscando | Puedes cambiar a otra app: el resultado seguirá aquí cuando vuelvas |
| it | Ci vuole un po' più del solito, stiamo ancora cercando | Puoi passare a un'altra app: il risultato sarà qui al tuo ritorno |
| ja | いつもより少し時間がかかっています。検索を続けています | ほかのアプリに切り替えても大丈夫です。戻ったときに結果が表示されます |
| ko | 평소보다 조금 오래 걸리고 있어요. 계속 찾는 중입니다 | 다른 앱으로 전환해도 괜찮아요. 돌아오면 결과가 그대로 있어요 |
| pl | Trwa to trochę dłużej niż zwykle — wciąż szukamy | Możesz przełączyć się na inną aplikację — wynik będzie czekał po powrocie |

Run: `cd frontend/gomuseum_app && flutter gen-l10n`
Expected: `lib/l10n/app_localizations*.dart` 出现 `recWaitSlow`/`recWaitSwitchApp`。

- [ ] **Step 2: 写失败测试**

Create `test/features/recognition/presentation/recognition_wait_hint_test.dart`:

```dart
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gomuseum_app/features/recognition/presentation/widgets/recognition_wait_hint.dart';
import 'package:gomuseum_app/l10n/app_localizations.dart';

void main() {
  testWidgets('hint escalates at 10s and 20s', (tester) async {
    await tester.pumpWidget(const MaterialApp(
      locale: Locale('zh'),
      localizationsDelegates: AppLocalizations.localizationsDelegates,
      supportedLocales: AppLocalizations.supportedLocales,
      home: Scaffold(body: RecognitionWaitHint(style: TextStyle())),
    ));
    await tester.pump();
    expect(find.text('AI 正在比对馆藏与公开艺术数据库'), findsOneWidget);

    await tester.pump(const Duration(seconds: 10));
    expect(find.text('比平时多花了点时间，还在找'), findsOneWidget);

    await tester.pump(const Duration(seconds: 10));
    expect(find.text('可以先切到其他应用，回来时结果还在'), findsOneWidget);
  });

  testWidgets('timers cancelled on dispose (no pending timer error)',
      (tester) async {
    await tester.pumpWidget(const MaterialApp(
      localizationsDelegates: AppLocalizations.localizationsDelegates,
      supportedLocales: AppLocalizations.supportedLocales,
      home: Scaffold(body: RecognitionWaitHint(style: TextStyle())),
    ));
    await tester.pumpWidget(const SizedBox());
  });
}
```

Run: `flutter test test/features/recognition/presentation/recognition_wait_hint_test.dart`
Expected: FAIL(文件不存在)

- [ ] **Step 3: 实现组件**

Create `lib/features/recognition/presentation/widgets/recognition_wait_hint.dart`:

```dart
import 'dart:async';

import 'package:flutter/widgets.dart';
import 'package:gomuseum_app/l10n/app_localizations.dart';

/// 识别等待中的说明行,随等待时长换文案(S2 ⑪):
/// 0s 现文案 → 10s「还在找」→ 20s「可以先切到其他应用」。
/// 只承诺「切到其他应用」,不承诺离开页面(用户 2026-10-05:说「离开」分不清是页面还是 App)。
/// 重发期间识别状态一直是 Loading,本组件不重建,计时连续。
class RecognitionWaitHint extends StatefulWidget {
  const RecognitionWaitHint({super.key, required this.style});
  final TextStyle style;

  @override
  State<RecognitionWaitHint> createState() => _RecognitionWaitHintState();
}

class _RecognitionWaitHintState extends State<RecognitionWaitHint> {
  int _stage = 0;
  late final List<Timer> _timers = [
    Timer(const Duration(seconds: 10), () => setState(() => _stage = 1)),
    Timer(const Duration(seconds: 20), () => setState(() => _stage = 2)),
  ];

  @override
  void initState() {
    super.initState();
    _timers; // 触发 late 初始化,开始计时
  }

  @override
  void dispose() {
    for (final t in _timers) {
      t.cancel();
    }
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context)!;
    final text = switch (_stage) {
      0 => l10n.camComparing,
      1 => l10n.recWaitSlow,
      _ => l10n.recWaitSwitchApp,
    };
    return Text(text, style: widget.style);
  }
}
```

- [ ] **Step 4: 接到相机页**

`camera_page.dart` 的 `_loadingContent` 里把

```dart
      Text(l10n.camComparing, style: GmText.sans(size: 12, color: gm.sub)),
```

换成

```dart
      RecognitionWaitHint(style: GmText.sans(size: 12, color: gm.sub)),
```

并在文件顶部加 `import 'package:gomuseum_app/features/recognition/presentation/widgets/recognition_wait_hint.dart';`(按该文件现有 import 风格:相对或 package 路径,与邻居一致)。若 `l10n` 在 `_loadingContent` 里因此不再被使用,保留(`camRecognizing` 仍在用)。

- [ ] **Step 5: 跑测试 + analyze**

Run: `cd frontend/gomuseum_app && flutter test test/features/recognition && flutter analyze`
Expected: 全 PASS;analyze 无新增 issue。

- [ ] **Step 6: 提交**

```bash
cd /Users/hongyang/Projects/GoMuseum/frontend/gomuseum_app && dart format lib/features/recognition test/features/recognition
cd /Users/hongyang/Projects/GoMuseum
git add frontend/gomuseum_app/lib/features/recognition/presentation/widgets/recognition_wait_hint.dart frontend/gomuseum_app/lib/features/recognition/presentation/pages/camera_page.dart frontend/gomuseum_app/test/features/recognition/presentation/recognition_wait_hint_test.dart frontend/gomuseum_app/lib/l10n/*.arb frontend/gomuseum_app/lib/l10n/app_localizations*.dart
git commit -m "feat(recognition): 识别等待 10s/20s 分段提示,10 语(S2)"
```

---

### Task 4: PR → staging 实测在途合并

**Files:** 无代码改动;更新 `docs/superpowers/specs/2026-10-05-recognition-failure-feedback-design.md` 状态行。

- [ ] **Step 1: 推分支、提 PR 到 staging、等 CI 绿、squash 合并并删分支**

```bash
git push -u origin feature/recognition-s2-recovery
gh pr create --base staging --title "feat: S2 识别找回(在途合并 + 失败重发 + 分段提示)" --body "..."
gh pr checks --watch
gh pr merge --squash --delete-branch
```

- [ ] **Step 2: 等 staging 部署健康**

Run: `curl -s https://staging-api.gomuseum.app/health`(502 是容器在加载模型,等 healthy)

- [ ] **Step 3: staging 并发同图实测**

在 scratchpad 生成一张目录里没有的随机噪声 JPEG(走 GPT 慢路径,首请求要几秒,够第二个请求撞上),**同时**发两次:

```bash
python3 -c "import os;from PIL import Image;Image.frombytes('RGB',(256,256),os.urandom(256*256*3)).save('$SCRATCH/s2.jpg')"
for i in 1 2; do curl -s -o /dev/null -w "%{http_code} %{time_total}\n" -F image=@$SCRATCH/s2.jpg "https://staging-api.gomuseum.app/api/v1/recognize?language=zh&device_id=s2-probe" & done; wait
```

再到 staging 库查最近两条事件:

```sql
select engine, outcome, duration_ms, timings from recognition_events order by created_at desc limit 2;
```

Expected:一条 `engine=text`(或 vector*),一条 `engine=cache` 且 `timings` 含 `inflight_wait`;两个 curl 都 200、耗时相近。

- [ ] **Step 4: 更新 spec 状态行**(S2 后端 ✅ 上 staging;前端随 S3/S4 同一版 App;真机验收待出包),并把本计划「已知局限」三条补进 spec S2 节,走 docs PR 合 staging。

- [ ] **Step 5: 真机验收(随 S3/S4 那版包,用户执行)**:识别中①锁屏 90s 后解锁 ②切到别的 App 90s 后切回 ③开飞行模式再关 —— 三种都直接看到结果、且不重复扣次。
