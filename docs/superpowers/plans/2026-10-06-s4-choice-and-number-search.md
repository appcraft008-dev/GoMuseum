# S4 选择页 + 编号搜索 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 「都不是」与「没认出来」后给两条并列主路(拍说明牌 / 输入编号或名称);只输数字也能按馆藏号找到;从搜索找到的作品带着本机照片进详情页,并把「这张照片=这件作品」记下来。

**Architecture:** 后端搜索索引预算「馆藏号只留数字」字段,`rank()` 两段式:纯数字查询且无人拿到整串精确档时,按数字匹配给独立分值档 0.9;搜索结果加法字段 `inventory`。`POST /recognize/confirm` 加可选 `source`("search" 只记答案、不计费)。前端未收录态带上 `phash`,选择页两个主按钮,搜索 sheet 的结果点选走相机页自己的跳转(带照片、记答案、返回仍回选择页)。

**Tech Stack:** FastAPI;Flutter + Riverpod + go_router;flutter gen-l10n(10 语)。

**Spec:** `docs/superpowers/specs/2026-10-05-recognition-failure-feedback-design.md` §四 S4(含并入的 S6)、§六

## Global Constraints

- 契约只做加法:`inventory` 新字段、`source` 可选字段(缺省=现行候选确认语义,计费不变);前端读新字段 `as T?`。
- **计费不变**:搜索找到作品**不扣次、不解锁**(现状:搜索免费,听讲解走详情页手动解锁)。`source="search"` 只回填 `confirmed_qid`。
- 数字退路分值档 0.9:高于标题前缀 0.8、低于整串精确 1.0;只在 query 为纯数字(≥3 位)且无任何条目拿到 1.0 时启用。
- 选择页:「拍说明牌」「输入编号/名称」并列主按钮(用户 2026-10-05 定);「重新拍作品」小字。
- 测试:后端 `cd backend && poetry run python -m pytest --no-cov <path>`;前端 `cd frontend/gomuseum_app && flutter test <path>`。禁止 `git add <目录>/`;破坏验证前先提交。

## 与 spec 的有意偏离 / 补充

1. spec 说「从选择页找到作品 = 通过 S3 的 confirm 回传」。现有 confirm **会扣次并解锁语音**,原样复用会让「搜索找到」变成收费动作——改变计费,未经用户同意。本计划加可选 `source="search"`:只记答案、不计费,与现状(搜索免费)一致。
2. 输入框占位文案:现有 `camTagExample`「如：INV 3692 / 在阿尔的卧室」已经引导「编号或名称」,不另改(避免 10 语文案改动)。
3. 搜索结果里的完整编号:只在**查询含数字**时显示(用户在按编号找时才需要对照说明牌;探索页按名字搜时不加噪音)。
4. 从搜索进详情页**不自动播放**语音(候选/命中路径已扣次解锁才自动播;搜索路径未解锁,自动播会立刻弹付费墙)。

## 独立评审处理(2026-10-06,Fable)

| 级别 | 意见 | 处理 |
|---|---|---|
| P0 | 搜索点选对同一 Navigator 连 pop 两次(sheet 的 `onNavigate` 已关 sheet,`onPick` 又 pop)→ 把相机页顶掉 | **已改**:`onPick` 里不再 pop,只调 `_goGuide` |
| P0 | `source=search` 写了 `confirmed_qid` → 同 phash 之后的候选确认 `first_time=False`,既不扣也不解锁 | **已改**:新增列 `confirm_source`(迁移 `s4c1`);`first_time` 只看**计过费的**确认(source≠search;老行 NULL 视为计过费);补测试 `test_search_confirm_does_not_spend_the_first_time_lock` |
| P1 | 数字退路「全部列出」实际靠前端 `limit: 60` 撑住,无测试 | **已改**:`rank` 注释写明依赖;测试钉住「数字退路档整体排在低档之前」(截断只会先砍低档) |
| P1 | 全角数字(中日韩输入法)搜不到 | **已改**:`rank` 入口对 query 做 NFKC;补测试 `test_fullwidth_digits` |
| P2 | `id(e)` 当键 | **已改**:用条目已有的 `e["id"]` |
| P2 | `RF779` 本身整串命中 1.0,钉不住「混合查询不走退路」 | **已改**:换成 `A779X` |

## Review Focus

1. **`779` 同时命中 `INV 779` 与标题含 779 的件**:数字退路必须排在标题子串前,且不出现在整串精确命中之前 → Task 1 `test_digit_fallback_tier_order`。
2. **字母数字混合(`RF779`、`INV 779`)**:不走数字退路 → Task 1 `test_alnum_query_no_digit_fallback`。
3. **有件的馆藏号就是纯数字 `779`**:它拿 1.0,其他 `RF 779` 不再被数字退路拉进来 → Task 1 `test_exact_digit_inventory_suppresses_fallback`。
4. **搜索路径确认被当成候选确认扣次** → Task 2 `test_confirm_from_search_records_but_never_charges`。
5. **未收录态没有 phash(老后端/老缓存)**:搜索点选仍能进详情页,只是不回传 → Task 3 `confirm from search without phash is a no-op`。

---

### Task 1: 后端搜索 —— 数字退路 + `inventory` 字段

**Files:**
- Modify: `backend/app/services/search/inprocess.py`
- Test: `backend/tests/unit/services/search/test_inprocess.py`(追加)

**Interfaces:**
- Produces: 索引条目新增 `"inventory"`(原始馆藏号)与 `"inv_digits"`(只留数字,无则 None);常量 `_S_INV_DIGITS = 0.9`;搜索结果对象新增 `"inventory": str | None`。

- [ ] **Step 1: 写失败测试**

追加到 `test_inprocess.py` 末尾:

```python
# --- S4:只输数字按馆藏号找 ---


@pytest.fixture()
def inv_session(session):
    """在基础夹具上加几件带馆藏号的作品。"""
    mid = _mid(session)
    for qid, title, inv, pop in [
        ("Q_INV779", "Portrait of a Man", "INV 779", 5),
        ("Q_RF779", "Landscape", "RF 779", 5),
        ("Q_INV7790", "Still Life", "INV 7790", 5),
        ("Q_T779", "Salon 779", None, 50),  # 标题子串含 779,高人气
    ]:
        upsert_object(
            session,
            mid,
            {"qid": qid, "title_en": title, "inventory_number": inv, "popularity": pop},
        )
    session.commit()
    inprocess._index_cache.clear()
    return session


def test_digit_query_finds_inventories(inv_session):
    idx = build_search_index(inv_session, _mid(inv_session))
    out = {e["qid"]: s for e, s in rank(idx, "779")}
    assert out["Q_INV779"] == 0.9 and out["Q_RF779"] == 0.9
    assert "Q_INV7790" not in out  # 数字整串相等,不是子串


def test_digit_fallback_tier_order(inv_session):
    """数字退路 0.9 排在标题子串(0.6,且人气更高)之前。"""
    idx = build_search_index(inv_session, _mid(inv_session))
    qids = [e["qid"] for e, _ in rank(idx, "779")]
    assert qids.index("Q_INV779") < qids.index("Q_T779")
    assert qids.index("Q_RF779") < qids.index("Q_T779")


def test_full_inventory_query_returns_one(inv_session):
    idx = build_search_index(inv_session, _mid(inv_session))
    out = rank(idx, "INV 779")
    assert [(e["qid"], s) for e, s in out] == [("Q_INV779", 1.0)]


def test_alnum_query_no_digit_fallback(inv_session):
    idx = build_search_index(inv_session, _mid(inv_session))
    assert not any(s == 0.9 for _, s in rank(idx, "A779X"))


def test_exact_digit_inventory_suppresses_fallback(inv_session):
    """有件馆藏号就是 "779" → 它拿 1.0,数字退路不启用,RF 779 不被拉进来。"""
    upsert_object(
        inv_session,
        _mid(inv_session),
        {"qid": "Q_BARE", "title_en": "Bare", "inventory_number": "779"},
    )
    inv_session.commit()
    inprocess._index_cache.clear()
    idx = build_search_index(inv_session, _mid(inv_session))
    out = {e["qid"]: s for e, s in rank(idx, "779")}
    assert out["Q_BARE"] == 1.0
    assert "Q_RF779" not in out


def test_short_digit_query_no_fallback(inv_session):
    idx = build_search_index(inv_session, _mid(inv_session))
    assert not any(s == 0.9 for _, s in rank(idx, "77"))


def test_fullwidth_digits(inv_session):
    """中日韩输入法常切成全角数字:「７７９」也要按馆藏号找到。"""
    idx = build_search_index(inv_session, _mid(inv_session))
    out = {e["qid"]: s for e, s in rank(idx, "７７９")}
    assert out.get("Q_INV779") == 0.9


def test_search_result_carries_inventory(inv_session):
    _, objs = search(inv_session, _FakeStorage(), "INV 779", language="en")
    assert objs[0]["inventory"] == "INV 779"
```

> `search`、`rank`、`build_search_index`、`upsert_object`、`inprocess`、`pytest` 在该文件已导入;缺哪个按文件顶部现有导入补。若 `upsert_object` 对 `inventory_number` 键名不同,按 `object_importer.upsert_object` 实际键名改(语义:写 `MuseumObject.inventory_number`)。

Run: `cd backend && poetry run python -m pytest --no-cov tests/unit/services/search/test_inprocess.py -q`
Expected: 新增用例 FAIL(0.9 档不存在 / `inventory` KeyError),旧用例 PASS。

- [ ] **Step 2: 实现**

`inprocess.py`:

1. 顶部加 `import re` 与 `import unicodedata`;常量区在 `_S_INV = 1.0` 之后加:

```python
_S_INV_DIGITS = 0.9  # 只输数字时按馆藏号数字匹配(S4):高于标题前缀,低于整串精确
_NONDIGIT = re.compile(r"\D")
```

2. `_build_global` 的条目里 `"inv": normalize_inv(inv) or None,` 之后加:

```python
                "inv_digits": _NONDIGIT.sub("", inv or "") or None,
                "inventory": inv,  # 原样展示,用户拿它对照说明牌
```

3. `rank` 改为:

```python
def rank(index: list[dict], query: str, limit: int = 20) -> list[tuple[dict, float]]:
    """[(entry, score)] 降序,同分按 popularity 降序,取 top limit。空 query → []。

    两段式(S4):先走常规打分;query 为纯数字(≥3 位)且**没有任何条目拿到整串精确档**时,
    再按「馆藏号只留数字」整串相等补一档 0.9 —— 说明牌上 `INV 779`,用户只敲了 `779`。
    ⚠️ 「数字退路全部列出」靠调用方 limit 够大:前端 searchProvider 传 60(search_api.dart),
    prod 已知同数字最多 23 件;0.9 档整体排在低档之前,截断只会先砍低档。"""
    # 全角→半角(中日韩输入法常切成全角数字/字母)
    query = unicodedata.normalize("NFKC", query)
    qn = normalize(query)
    if not qn:
        return []
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
    out = sorted(scored.values(), key=lambda es: (-es[1], -es[0]["popularity"]))
    return out[:limit]
```

4. `search()` 输出对象 dict 里 `"has_image": thumbnail is not None,` 之后加 `"inventory": entry["inventory"],`。

- [ ] **Step 3: 跑测试通过**

Run: `cd backend && poetry run python -m pytest --no-cov tests/unit/services/search tests/unit/api -q`
Expected: 全 PASS(含 `test_build_index_skips_heavy_columns` —— 只多用了已在查询列里的 `inventory_number`)。

- [ ] **Step 4: 提交 + 破坏验证**

```bash
cd /Users/hongyang/Projects/GoMuseum
F=(backend/app/services/search/inprocess.py backend/tests/unit/services/search/test_inprocess.py)
black -q $F && isort -q $F && git add $F && git commit -m "feat(search): 只输数字按馆藏号匹配 + 结果带完整编号(S4)"
```

破坏:①去掉 `and not any(s == _S_INV ...)` → `test_exact_digit_inventory_suppresses_fallback` 红;②把 `_S_INV_DIGITS` 改成 0.5 → `test_digit_fallback_tier_order` 红。各自还原,ledger 记结果。

---

### Task 2: 后端 —— confirm `source="search"` 只记答案不计费

**Files:**
- Create: `backend/alembic/versions/s4c1_recognition_events_confirm_source.py`
- Modify: `backend/app/models/recognition_event.py`(`confirm_source` 列)
- Modify: `backend/app/services/recognition/events.py`(`confirm_event` 加 `source` 参数,`first_time` 只看计过费的确认)
- Modify: `backend/app/api/v1/endpoints/recognize_global.py`(`ConfirmRequest`、`recognize_confirm`)
- Test: `backend/tests/unit/api/test_recognize_global.py`(追加)

**Interfaces:**
- Produces: `ConfirmRequest.source: Literal["candidates", "search"] = "candidates"`。

- [ ] **Step 1: 写失败测试**

```python
def test_confirm_from_search_records_but_never_charges(monkeypatch):
    """S4:选择页搜到作品 = 记下「这张照片是这件」,但搜索免费:不扣次、不解锁。"""
    from app.core.config import settings
    from app.models.user_benefits import UserBenefits
    from app.services import entitlement_service as es

    headers = _as_user(monkeypatch, "u-search")
    client, s = _confirm_client()
    try:
        _event(s, "ph-search")
        r = client.post(
            "/api/v1/recognize/confirm",
            json={"phash": "ph-search", "qid": "Q1", "source": "search"},
            headers=headers,
        )
        assert r.status_code == 204
        assert _row(s, "ph-search").confirmed_qid == "Q1"
        ub = s.query(UserBenefits).filter_by(user_id="u-search").one_or_none()
        assert ub is None or ub.recognition_quota == settings.FREE_RECOGNITION_QUOTA
        assert es.audio_access(s, "u-search", "Q1") != "allowed"
    finally:
        app.dependency_overrides.pop(get_db, None)


def test_search_confirm_does_not_spend_the_first_time_lock(monkeypatch):
    """评审 P0:search 确认写了 confirmed_qid,之后同一张照片的候选确认仍要正常扣 1 次并解锁
    (「一次拍照只扣一次」的锁只能被**计过费的**确认占用)。"""
    from app.core.config import settings
    from app.models.user_benefits import UserBenefits

    headers = _as_user(monkeypatch, "u-mix")
    client, s = _confirm_client()
    try:
        _event(s, "ph-mix")
        client.post(
            "/api/v1/recognize/confirm",
            json={"phash": "ph-mix", "qid": "Q1", "source": "search"},
            headers=headers,
        )
        client.post(
            "/api/v1/recognize/confirm",
            json={"phash": "ph-mix", "qid": "Q2"},
            headers=headers,
        )
        ub = s.query(UserBenefits).filter_by(user_id="u-mix").one()
        assert ub.recognition_quota == settings.FREE_RECOGNITION_QUOTA - 1
    finally:
        app.dependency_overrides.pop(get_db, None)


def test_confirm_unknown_source_rejected():
    client, s = _confirm_client()
    try:
        r = client.post(
            "/api/v1/recognize/confirm",
            json={"phash": "x", "qid": "Q1", "source": "hack"},
        )
        assert r.status_code == 422
    finally:
        app.dependency_overrides.pop(get_db, None)
```

> 若 `es.audio_access` 在该夹具下因缺表报错,改为断言 `free_audio_qids` 不含 Q1,语义是「没解锁」;参照同文件 `test_confirm_charges_one_and_unlocks_audio` 的断言写法。

Run: `cd backend && poetry run python -m pytest --no-cov tests/unit/api/test_recognize_global.py -k "from_search or unknown_source" -q`
Expected: FAIL(第一条被扣次/解锁;第二条 204 而非 422)

- [ ] **Step 2: 实现**

1. 模型 `recognition_event.py`,`confirmed_qid` 之后加:

```python
    # S4:这次确认从哪来。"candidates"(计过费)/ "search"(选择页搜到,不计费)。
    # 老行 NULL = 候选确认(计过费)。confirm_event 的「一次拍照只扣一次」只认计过费的确认。
    confirm_source = Column(String(16), nullable=True)
```

2. 迁移 `s4c1_recognition_events_confirm_source.py`(`revision = "s4c1"`, `down_revision = "s3r1"`;先 `alembic heads` 确认),`upgrade` 加 `sa.Column("confirm_source", sa.String(16), nullable=True)`,`downgrade` drop。docstring 写:加法、只存来源标签、不含用户标识。

3. `events.py` `confirm_event(db, phash, qid, source: str = "candidates") -> bool`:

```python
        prev = next((r.confirmed_qid for r in rows if r.confirmed_qid), None)
        # 「一次拍照只扣一次」只认计过费的确认:search 来源只记答案,不占这把锁
        first_time = not any(
            r.confirmed_qid and r.confirm_source != "search" for r in rows
        )
```

(替换原 `first_time = prev is None`;写行处 `row.confirmed_qid = qid` 之后加 `row.confirm_source = source`。)

4. 端点:

```python
class ConfirmRequest(BaseModel):
    phash: str
    qid: str
    # S4:"search" = 用户在选择页搜到这件(识别没认出来)。只记答案,不计费 ——
    # 搜索一直是免费的,听讲解走详情页手动解锁。缺省=候选确认(现行计费语义)。
    source: Literal["candidates", "search"] = "candidates"
```

(补 `from typing import Annotated, Literal`。)`recognize_confirm` 中改为 `first_time = confirm_event(db, body.phash, body.qid, body.source)`,之后加:

```python
    if body.source == "search":
        return Response(status_code=204)
```

- [ ] **Step 3: 测试 + 提交**

Run: `cd backend && poetry run python -m pytest --no-cov tests/unit/api/test_recognize_global.py tests/integration -q`
Expected: 全 PASS。

```bash
F=(backend/alembic/versions/s4c1_recognition_events_confirm_source.py backend/app/models/recognition_event.py backend/app/services/recognition/events.py backend/app/api/v1/endpoints/recognize_global.py backend/tests/unit/api/test_recognize_global.py)
black -q $F && isort -q $F && git add $F && git commit -m "feat(recognize): confirm 加 source=search,只记答案不计费(S4)"
```

破坏:①删掉 `if body.source == "search": return` → `test_confirm_from_search_records_but_never_charges` 红;②`first_time` 改回 `prev is None` → `test_search_confirm_does_not_spend_the_first_time_lock` 红;各自还原。

---

### Task 3: 前端数据层 —— 未收录态带 phash、搜索确认、`inventory`

**Files:**
- Modify: `frontend/gomuseum_app/lib/features/recognition/presentation/providers/recognition_provider.dart`
- Modify: `frontend/gomuseum_app/lib/features/recognition/data/datasources/recognition_remote_datasource.dart`(`confirm` 加可选 `source`)
- Modify: `frontend/gomuseum_app/lib/features/search/data/search_api.dart`(`SearchObject.inventory`)
- Modify(假类签名): 实现 `RecognitionRemoteDataSource` 的测试假类(`recognition_quota_state_test.dart`、`recognition_refreshes_footprints_test.dart`、`recognition_retry_test.dart`、`recognition_reject_test.dart`)
- Test: 新建 `test/features/recognition/presentation/providers/recognition_search_confirm_test.dart`;`test/features/recognition/data/datasources/recognition_remote_datasource_test.dart`(追加);新建 `test/features/search/search_object_inventory_test.dart`

**Interfaces:**
- Produces: `RecognitionUnrecognized(labelText, reason, slug, {String? phash})` + 字段 `phash`;`RecognitionNotifier.confirmRecognition(String qid, {bool fromSearch = false})`;`RecognitionRemoteDataSource.confirm({required String phash, required String qid, String? source})`;`SearchObject.inventory`(String?)。

- [ ] **Step 1: 写失败测试**

`recognition_remote_datasource_test.dart` 追加:

```dart
  test('confirm sends source only when given (search path)', () async {
    when(() => dio.post(any(),
            data: any(named: 'data'), options: any(named: 'options')))
        .thenAnswer((_) async => Response(
            requestOptions: RequestOptions(path: '/api/v1/recognize/confirm'),
            statusCode: 204));

    await ds.confirm(phash: 'ph', qid: 'Q1', source: 'search');
    await ds.confirm(phash: 'ph', qid: 'Q2');

    final data = verify(() => dio.post(any(),
            data: captureAny(named: 'data'), options: any(named: 'options')))
        .captured;
    expect(data[0], {'phash': 'ph', 'qid': 'Q1', 'source': 'search'});
    expect(data[1], {'phash': 'ph', 'qid': 'Q2'}); // 缺省不带,老语义
  });
```

Create `test/features/search/search_object_inventory_test.dart`:

```dart
import 'package:flutter_test/flutter_test.dart';
import 'package:gomuseum_app/features/search/data/search_api.dart';

void main() {
  test('SearchObject reads inventory, tolerates absence', () {
    expect(
        SearchObject.fromJson(const {'qid': 'Q1', 'inventory': 'INV 779'})
            .inventory,
        'INV 779');
    expect(SearchObject.fromJson(const {'qid': 'Q1'}).inventory, isNull);
  });
}
```

Create `test/features/recognition/presentation/providers/recognition_search_confirm_test.dart`:

```dart
import 'dart:typed_data';

import 'package:cross_file/cross_file.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gomuseum_app/features/payment/presentation/providers/benefits_provider.dart';
import 'package:gomuseum_app/features/recognition/data/datasources/recognition_remote_datasource.dart';
import 'package:gomuseum_app/features/recognition/data/models/recognize_response.dart';
import 'package:gomuseum_app/features/recognition/presentation/providers/recognition_provider.dart';
import 'package:gomuseum_app/features/recognition/presentation/providers/recognition_providers.dart';

class _Ds implements RecognitionRemoteDataSource {
  _Ds(this.resp);
  final Map<String, dynamic> resp;
  final confirms = <List<String?>>[];

  @override
  Future<RecognizeResponse> recognize({
    String? slug,
    required XFile image,
    required String language,
    String mode = 'artwork',
    String? deviceId,
  }) async =>
      RecognizeResponse.fromJson(resp);

  @override
  Future<void> confirm(
          {required String phash, required String qid, String? source}) async =>
      confirms.add([phash, qid, source]);

  @override
  Future<void> reject(
      {required String phash, required List<String> qids}) async {}

  @override
  Future<Never> recognizeArtwork(XFile imageFile) async =>
      throw UnimplementedError();
}

Future<(ProviderContainer, _Ds)> _run(Map<String, dynamic> resp) async {
  final ds = _Ds(resp);
  final c = ProviderContainer(overrides: [
    recognitionRemoteDataSourceProvider.overrideWithValue(ds),
    deviceIdProvider.overrideWith((ref) async => 'dev-1'),
  ]);
  await c.read(recognitionNotifierProvider.notifier).recognize(
      image: XFile.fromData(Uint8List.fromList(const [0]), name: 'x.jpg'),
      language: 'en');
  return (c, ds);
}

void main() {
  test('unrecognized state carries phash', () async {
    final (c, _) =
        await _run(const {'outcome': 'unrecognized', 'phash': 'ph-u'});
    addTearDown(c.dispose);
    final st = c.read(recognitionNotifierProvider);
    expect(st, isA<RecognitionUnrecognized>());
    expect((st as RecognitionUnrecognized).phash, 'ph-u');
  });

  test('「都不是」后的未收录态也带 phash', () async {
    final (c, _) = await _run(const {
      'outcome': 'candidates',
      'phash': 'ph-c',
      'candidates': [
        {'qid': 'Q1', 'museum': 'orsay', 'title': 'A'}
      ],
    });
    addTearDown(c.dispose);
    c.read(recognitionNotifierProvider.notifier).rejectCandidates();
    expect((c.read(recognitionNotifierProvider) as RecognitionUnrecognized).phash,
        'ph-c');
  });

  test('confirm from search sends source=search with unrecognized phash',
      () async {
    final (c, ds) =
        await _run(const {'outcome': 'unrecognized', 'phash': 'ph-u'});
    addTearDown(c.dispose);
    await c
        .read(recognitionNotifierProvider.notifier)
        .confirmRecognition('Q9', fromSearch: true);
    expect(ds.confirms, [
      ['ph-u', 'Q9', 'search']
    ]);
  });

  test('confirm from search without phash is a no-op (old backend)', () async {
    final (c, ds) = await _run(const {'outcome': 'unrecognized'});
    addTearDown(c.dispose);
    await c
        .read(recognitionNotifierProvider.notifier)
        .confirmRecognition('Q9', fromSearch: true);
    expect(ds.confirms, isEmpty);
  });
}
```

> `ds.confirms` 里放的是 `List<String?>`(不是 record):record 内含 List 时 `==` 比的是引用(S3 踩过)。

Run: `cd frontend/gomuseum_app && flutter test test/features/recognition test/features/search`
Expected: FAIL(编译错误:`source`/`phash`/`fromSearch`/`inventory` 未定义)

- [ ] **Step 2: 实现**

1. `RecognitionUnrecognized`:

```dart
class RecognitionUnrecognized extends RecognitionState {
  const RecognitionUnrecognized(this.labelText, this.reason, this.slug,
      {this.phash});
  final String? labelText;
  final String? reason;
  final String? slug;

  /// 这张照片的感知哈希(S4:选择页搜到作品时用它回传「照片=这件」)。老后端没有 → null。
  final String? phash;
}
```

`recognize()` 里 `_ => RecognitionUnrecognized(resp.labelText, resp.reason, slug),` 改为 `_ => RecognitionUnrecognized(resp.labelText, resp.reason, slug, phash: resp.phash),`;`rejectCandidates()` 里改为 `RecognitionUnrecognized(s.labelText, 'rejected', s.slug, phash: s.phash)`。

2. `confirmRecognition`:

```dart
  Future<void> confirmRecognition(String qid, {bool fromSearch = false}) async {
    final s = state;
    final phash = switch (s) {
      RecognitionCandidates() => s.phash,
      // S4:选择页搜到的作品 = 用户告诉我们「这张照片是这件」。只记答案,后端不计费。
      RecognitionUnrecognized() when fromSearch => s.phash,
      _ => null,
    };
    if (phash == null) return;
    await ref.read(recognitionRemoteDataSourceProvider).confirm(
        phash: phash, qid: qid, source: fromSearch ? 'search' : null);
    if (fromSearch) return; // 没扣次:不用刷权益/足迹
    _refreshFootprints(); // 放在权益刷新之前:那边抛了不该连带足迹
    // 确认扣掉了 1 次额度，权益缓存必须失效 —— 否则设置页还显示旧的剩余次数。
    ref.invalidate(entitlementsProvider);
    ref.invalidate(museumEntitlementsProvider);
    await ref.read(benefitsStateProvider.notifier).refresh();
  }
```

(保留原有文档注释,补一句 S4 说明。)

3. 数据源 `confirm`:接口改 `Future<void> confirm({required String phash, required String qid, String? source});`;实现里 `data: {'phash': phash, 'qid': qid, if (source != null) 'source': source},`。四个测试假类的 `confirm` 签名同步加 `String? source`。

4. `SearchObject`:加 `this.inventory,` 构造参数、字段 `/// 完整馆藏号(S4;用户拿它对照说明牌)。 final String? inventory;`,`fromJson` 加 `inventory: j['inventory'] as String?,`。

- [ ] **Step 3: 测试 + analyze + 提交**

Run: `cd frontend/gomuseum_app && flutter test test/features/recognition test/features/search && flutter analyze lib/features/recognition lib/features/search`
Expected: 全 PASS;改动文件无新增 issue。逐个文件 `git add`,提交 `feat(recognition): 未收录态带 phash,搜索确认只记答案;搜索结果带编号(S4)`。

---

### Task 4: 前端 —— 选择页 + 搜索点选带照片

**Files:**
- Modify: `frontend/gomuseum_app/lib/features/search/presentation/search_results_view.dart`(`onPickObject`、编号显示)
- Modify: `frontend/gomuseum_app/lib/features/recognition/presentation/pages/camera_page.dart`(`_unrecognizedContent`、`_goGuide`、`_showTagSearchSheet`、`_TagSearchSheet`)
- Modify: 10 个 arb + 重新生成(新键 `recTypeNumberOrName`)
- Test: 新建 `test/features/search/search_results_pick_test.dart`

**Interfaces:**
- Consumes: Task 3 的 `confirmRecognition(qid, fromSearch: true)`、`SearchObject.inventory`。
- Produces: `SearchResultsView({..., void Function(SearchObject obj)? onPickObject})`。

- [ ] **Step 1: l10n**

每个 arb 在 `"recShootLabelBtn"` 行之后加 `"recTypeNumberOrName"`(en 另加 `"@recTypeNumberOrName": {"description": "Primary button on the not-recognized choice card: type the inventory number or the title from the wall label"}`):

| arb | 值 |
|---|---|
| zh | 输入编号或名称 |
| zh_Hant | 輸入編號或名稱 |
| en | Type the number or title |
| fr | Saisir le numéro ou le titre |
| de | Nummer oder Titel eingeben |
| es | Escribir el número o el título |
| it | Inserisci numero o titolo |
| ja | 番号か作品名を入力 |
| ko | 번호나 작품명 입력 |
| pl | Wpisz numer lub tytuł |

Run: `cd frontend/gomuseum_app && flutter gen-l10n`

- [ ] **Step 2: 写失败测试**

Create `test/features/search/search_results_pick_test.dart`:

```dart
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gomuseum_app/features/search/data/search_api.dart';
import 'package:gomuseum_app/features/search/presentation/search_results_view.dart';
import 'package:gomuseum_app/l10n/app_localizations.dart';

void main() {
  Future<void> pump(WidgetTester t, String q, {void Function(SearchObject)? onPick}) {
    const query = (slug: null, q: 'Q', lang: 'en');
    final realQuery = (slug: null, q: q, lang: 'en');
    return t.pumpWidget(ProviderScope(
      overrides: [
        searchProvider(realQuery).overrideWith((ref) async => SearchResult(
              museums: const [],
              objects: const [
                SearchObject(
                    qid: 'Q1',
                    title: 'Portrait',
                    artist: 'X',
                    museum: 'orsay',
                    inventory: 'INV 779'),
              ],
            )),
      ],
      child: MaterialApp(
        localizationsDelegates: AppLocalizations.localizationsDelegates,
        supportedLocales: AppLocalizations.supportedLocales,
        home: Scaffold(
            body: SearchResultsView(
                query: realQuery, showMuseums: false, onPickObject: onPick)),
      ),
    ));
  }

  testWidgets('onPickObject replaces default navigation', (t) async {
    SearchObject? picked;
    await pump(t, '779', onPick: (o) => picked = o);
    await t.pumpAndSettle();
    await t.tap(find.text('Portrait'));
    expect(picked?.qid, 'Q1');
  });

  testWidgets('inventory shown when query has digits, hidden otherwise',
      (t) async {
    await pump(t, '779');
    await t.pumpAndSettle();
    expect(find.textContaining('INV 779'), findsOneWidget);

    await pump(t, 'portrait');
    await t.pumpAndSettle();
    expect(find.textContaining('INV 779'), findsNothing);
  });
}
```

> `SearchResult` / `searchProvider` / `SearchQuery` 的实际名称与构造以 `lib/features/search/data/search_api.dart` 为准(删掉上面多余的 `const query` 行);provider 是 family 时按参数覆盖。若该 provider 不便覆盖,改为覆盖其依赖的 API provider,语义不变。

Run: `cd frontend/gomuseum_app && flutter test test/features/search/search_results_pick_test.dart`
Expected: FAIL(`onPickObject` / `inventory` 未定义或未显示)

- [ ] **Step 3: SearchResultsView**

1. 加参数:

```dart
  /// 调用方接管藏品点选(识别选择页:带本机照片进详情、回传答案)。给了就不走默认跳转。
  final void Function(SearchObject obj)? onPickObject;
```

并透传给 `_ObjectHitRow(obj: o, fallbackSlug: fallbackSlug, onNavigate: onNavigate, onPick: onPickObject, showInventory: query.q.contains(RegExp(r'\d')))`。

2. `_ObjectHitRow` 加 `final void Function(SearchObject)? onPick; final bool showInventory;`;`onTap` 改为:

```dart
      onTap: slug == null
          ? null
          : () {
              onNavigate?.call();
              if (onPick != null) {
                onPick!(obj);
                return;
              }
              context.push('/guide',
                  extra: GuideArgs(slug: slug, qid: obj.qid));
            },
```

3. 副标题那行的 list 最前面加 `if (showInventory && obj.inventory != null) obj.inventory!,`(用户在按编号找时把完整编号露出来对照说明牌;按名字搜时不加噪音)。

- [ ] **Step 4: 相机页**

1. `_goGuide` 签名改为 `Future<void> _goGuide(String slug, String qid, {bool fromCandidates = false, bool fromSearch = false}) async`。其中:
   - confirm 调用改为 `ref.read(recognitionNotifierProvider.notifier).confirmRecognition(qid, fromSearch: fromSearch)`。
   - `autoPlayAudio: true` 改为 `autoPlayAudio: !fromSearch,`,并在上方注释补一句「搜索路径没扣次解锁,自动播会立刻弹付费墙」。
   - `if (!fromCandidates) { pushReplacement ...; return; }` 改为 `if (!fromCandidates && !fromSearch) { ... }`,注释补「搜索路径同样 push:返回回到选择页」。

2. `_showTagSearchSheet({String? initialQuery})`:`builder: (_) => _TagSearchSheet(...)` 增加参数 `onPick: (obj) => _goGuide(obj.museum!, obj.qid, fromSearch: true)`。**不要再 pop**:sheet 里 `SearchResultsView` 的 `onNavigate` 已经关过 sheet,这里再 pop 会把相机页本身弹掉(评审 P0)。`obj.museum` 由 `_ObjectHitRow` 的 `slug == null → onTap null` 保证非空。

3. `_TagSearchSheet` 加可选 `final void Function(SearchObject obj)? onPick;`,构造参数 `this.onPick`;`SearchResultsView(... onPickObject: widget.onPick)`。

4. `_unrecognizedContent` 整体替换为(两种情况共用一张选择卡;有墙签文字时预填):

```dart
  /// 「没认出来」与「都不是」共用的选择卡(S4,用户 2026-10-05 定):
  /// 「拍说明牌」「输入编号/名称」两个并列主按钮 —— 说明牌上的馆藏号唯一、名称比 AI
  /// 猜的准;拍不了(禁拍/反光/太远)就手输。「重新拍作品」降为小字。
  /// 绝不显示 AI 猜测的名字(契约 R1)。
  List<Widget> _unrecognizedContent(
      GmPalette gm, RecognitionUnrecognized state) {
    final l10n = AppLocalizations.of(context)!;
    final label = state.labelText;
    return [
      if (label != null)
        Text(l10n.recLabelSeen(label), style: GmText.sans(size: 13, height: 1.5))
      else
        Text(l10n.recNotRecognized,
            style: GmText.serif(size: 16.5, weight: FontWeight.w700)),
      const SizedBox(height: 14),
      GmTicketButton(
        label: l10n.recShootLabelBtn,
        icon: GmIcons.camera,
        onTap: _startLabelCapture,
      ),
      const SizedBox(height: 10),
      GmTicketButton(
        label: l10n.recTypeNumberOrName,
        icon: GmIcons.search,
        // 墙签已拍、OCR 出了文字 → 预填,免得用户再手打一遍
        onTap: () => _showTagSearchSheet(
            initialQuery: label == null ? null : labelSearchQuery(label)),
      ),
      if (label == null) ...[
        const SizedBox(height: 8),
        Text(l10n.recShootLabelHint,
            textAlign: TextAlign.center,
            style: GmText.sans(size: 11.5, color: gm.sub)),
      ],
      const SizedBox(height: 12),
      Center(
        child: GestureDetector(
          onTap: _retake,
          child: Text(l10n.camRetake,
              style: GmText.sans(size: 12.5, color: gm.accent)),
        ),
      ),
    ];
  }
```

`recSearchWithLabel` 键若因此不再被引用,保留在 arb 里不删(10 语 arb 删键是独立清理,不在本任务)。

- [ ] **Step 5: 测试 + analyze + 提交**

Run: `cd frontend/gomuseum_app && flutter test test/features/recognition test/features/search test/features/guide && flutter analyze`
Expected: 全 PASS;改动文件无新增 issue(对比 `git stash` 基线总数)。逐个文件 `git add`,提交 `feat(recognition): 选择页两个主按钮 + 搜索点选带照片进详情并记答案(S4)`。

破坏:`SearchResultsView` 里去掉 `if (onPick != null) {...}` → `onPickObject replaces default navigation` 红;还原。

---

### Task 5: PR → staging 实测

- [ ] **Step 1**: 推分支 `feature/recognition-s4-choice-search`,PR → staging,CI 绿后 squash 合并删分支。
- [ ] **Step 2**: staging 实测:`GET /api/v1/search?q=779&language=zh` 看是否返回多件、每件带 `inventory`、排序在标题子串之前;`q=INV 779`(或 staging 上真实存在的某个「字母+空格+数字」馆藏号)只回 1 件。先 SQL 找一个真实存在、数字部分在库里重复的馆藏号再测,别假设 779 在 staging 有。
- [ ] **Step 2b**: 确认 staging 迁移到 `s4c1`。
- [ ] **Step 3**: `POST /recognize/confirm {"phash":..., "qid":..., "source":"search"}` 带一个测试账号令牌 → 该账号额度不变、`confirmed_qid` 落库。
- [ ] **Step 4**: spec 状态行更新(S4 ✅ 合 staging;S2/S3/S4 前端同一版 App 待出包 + 真机验收清单)。
- [ ] **Step 5**(随包,用户执行):「都不是」→ 选择页两个按钮;「输入编号或名称」→ 只输数字能找到 → 点进详情页 hero 是自己拍的照片(无图作品)、不自动播放、不扣次;返回回到选择页。
