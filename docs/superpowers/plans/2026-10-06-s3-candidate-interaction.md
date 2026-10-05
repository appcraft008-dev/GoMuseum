# S3 候选交互 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 候选图能放大比对、选错能退回候选重选,且「第一次选错」和「都不是」都被记下来。

**Architecture:** 后端给 `recognition_events` 加 `rejected_qids` 列:改选时由服务端把此前确认过的那件记进去(不信客户端传的 previous),「都不是」走新端点 `POST /recognize/reject`;候选摘要加法字段 `image`(大图)与 `credit`(署名)。前端复用详情页已有的全屏画廊 `showImageGallery`(加一个底部插槽放标题和「就是这件」),候选进详情页改 `push`(进之前放掉相机、回来再开)。

**Tech Stack:** FastAPI + SQLAlchemy + Alembic;Flutter + Riverpod + go_router;flutter gen-l10n(10 语)。

**Spec:** `docs/superpowers/specs/2026-10-05-recognition-failure-feedback-design.md` §四 S3、§六

## Global Constraints

- 契约只做加法:新端点、新可选字段;老 App 不读新字段也不受影响;前端读新字段必须 `as T?` 并回落(`image` 缺 → 用 `thumbnail`)。
- 改选**不重复扣次**(现状 `confirm_event` 的 24h 幂等保持;现有计费测试全绿)。
- 「都不是」上报 fire-and-forget:任何失败都吞掉,绝不打扰界面。
- 图片署名:CC 协议要求的署名不能丢;作者本人不算署名(沿用 `_photo_credit`)。
- 相机:进详情页期间不得占着相机(隐私指示灯/耗电);回来恢复取景器。
- 测试:后端 `cd backend && poetry run python -m pytest --no-cov <path>`;前端 `cd frontend/gomuseum_app && flutter test <path>`。
- 禁止 `git add <目录>/`;破坏验证前先提交。

## 与 spec 的有意偏离

1. spec 写「`/recognize/confirm` 增加可选 `previous_qid`」。本计划**不加这个参数**:服务端在 24h 窗口里本来就存着上一次 `confirmed_qid`,改选时直接拿它记进 `rejected_qids`。好处:契约不变、不信任客户端(用户原则「不能完全依赖用户点击」)、老 App 改选也被记下。
2. spec 写「候选缩略图点击可放大」。缩略图是 `_thumb` 小图,放大是糊的 → 后端加 `image`(large 档)与 `credit`,并在画廊里配「就是这件」按钮(放大比对后直接选,少一步返回)。

## 独立评审处理(2026-10-06,Fable)

| 级别 | 意见 | 处理 |
|---|---|---|
| P1 | push/pop + 相机重开 + 状态保留无集成测试 | **不加**:评审已核实 `/camera`、`/guide` 都是 ShellRoute 外的顶层 GoRoute、同一根 Navigator,push 后 `isCurrent` 为 false;相机页的 widget 测试要替身 camera 插件,成本高、且测的是自建路由而非 app 路由,钉不住「有人把相机挪进 shell」。改为在 `didChangeAppLifecycleState` 注释里写明该前提,真机验收 Task 5 Step 5 兜底 |
| P1 | reject 不校验 qid 存在于目录,匿名可写垃圾 | **已改**:`reject_event` 静默丢弃目录里没有的 qid(同 `confirm_event` 纪律);补测试 `test_reject_drops_unknown_qids` |
| P2 | footer 空白处点击透传到「点任意处关闭」 | **已改**:footer 外包 `GestureDetector(behavior: opaque, onTap: () {})`;补测试「点标题不关闭」 |
| P2 | footer `bottom: 36` 与两行署名可能压线 | **已改**:有 footer 时署名与 footer 放进同一个底部 Column |
| P2 | GmTicketButton 黑底可读性、ObjectImage 命名冲突 | 评审核实均不成立,删掉计划里的「视情况」分支 |

## Review Focus

1. **从详情页返回后 App 切后台再回来**:相机页不在栈顶时不能重开相机(否则详情页底下占着相机)→ Task 4 `shouldRestartCamera` 新增 `isTopRoute` 用例。
2. **用户先选 A、返回、点「都不是」**:A 必须进 `rejected_qids`;`confirmed_qid` 仍是 A(不清,保计费幂等与足迹),分析口径「rejected 覆盖 confirmed」写进模型注释 → Task 1 `test_reject_after_confirm_records_all`。
3. **改选回原来那件(A→B→A)**:`rejected_qids` 不能把最终答案 A 留在里面 → Task 1 `test_reselect_back_removes_from_rejected`。
4. **老缓存条目无 `image`/`credit`**(缓存 30 天):前端回落到 `thumbnail`、不显示署名 → Task 3 `RecognizedItem falls back`。
5. **reject 请求 qids 超长/超量**:拒绝(422)而不是写进库 → Task 1 `test_reject_rejects_oversized_payload`。

---

### Task 1: 后端 —— rejected_qids、改选记录、`POST /recognize/reject`

**Files:**
- Create: `backend/alembic/versions/s3r1_recognition_events_rejected.py`
- Modify: `backend/app/models/recognition_event.py`
- Modify: `backend/app/services/recognition/events.py`(`confirm_event`,新增 `reject_event`)
- Modify: `backend/app/api/v1/endpoints/recognize_global.py`(新增 `RejectRequest` + 端点)
- Test: `backend/tests/unit/api/test_recognize_global.py`(追加)

**Interfaces:**
- Produces: 列 `RecognitionEvent.rejected_qids`(JSON list[str],nullable);`reject_event(db, phash: str, qids: list[str]) -> None`;端点 `POST /api/v1/recognize/reject` body `{"phash": str, "qids": [str]}` → 恒 204(校验失败 422)。

- [ ] **Step 1: 写失败测试**

追加到 `backend/tests/unit/api/test_recognize_global.py` 末尾:

```python
# --- S3:改选与「都不是」记录(rejected_qids) ---


def _row(s, phash):
    from app.models.recognition_event import RecognitionEvent

    s.expire_all()
    return s.query(RecognitionEvent).filter_by(phash=phash).one()


def test_reselect_records_previous_as_rejected():
    """选了 A、返回、改选 B:A 进 rejected_qids,答案是 B。previous 由服务端推出,不靠客户端。"""
    client, s = _confirm_client()
    try:
        _event(s, "ph-re")
        client.post("/api/v1/recognize/confirm", json={"phash": "ph-re", "qid": "Q1"})
        client.post("/api/v1/recognize/confirm", json={"phash": "ph-re", "qid": "Q2"})
        row = _row(s, "ph-re")
        assert row.confirmed_qid == "Q2"
        assert row.rejected_qids == ["Q1"]
    finally:
        app.dependency_overrides.pop(get_db, None)


def test_reselect_back_removes_from_rejected():
    """A→B→A:最终答案 A 不能还挂在 rejected 里。"""
    client, s = _confirm_client()
    try:
        _event(s, "ph-aba")
        for q in ("Q1", "Q2", "Q1"):
            client.post(
                "/api/v1/recognize/confirm", json={"phash": "ph-aba", "qid": q}
            )
        row = _row(s, "ph-aba")
        assert row.confirmed_qid == "Q1"
        assert row.rejected_qids == ["Q2"]
    finally:
        app.dependency_overrides.pop(get_db, None)


def test_reject_records_candidates():
    client, s = _confirm_client()
    try:
        _event(s, "ph-none")
        r = client.post(
            "/api/v1/recognize/reject", json={"phash": "ph-none", "qids": ["Q1", "Q2"]}
        )
        assert r.status_code == 204
        assert _row(s, "ph-none").rejected_qids == ["Q1", "Q2"]
    finally:
        app.dependency_overrides.pop(get_db, None)


def test_reject_after_confirm_records_all():
    """先选 A 进详情、返回点「都不是」:A 也进 rejected;confirmed 不清(保计费幂等/足迹),
    分析时 rejected 覆盖 confirmed。"""
    client, s = _confirm_client()
    try:
        _event(s, "ph-ac")
        client.post("/api/v1/recognize/confirm", json={"phash": "ph-ac", "qid": "Q1"})
        client.post(
            "/api/v1/recognize/reject", json={"phash": "ph-ac", "qids": ["Q1", "Q2"]}
        )
        row = _row(s, "ph-ac")
        assert row.rejected_qids == ["Q1", "Q2"]
        assert row.confirmed_qid == "Q1"
    finally:
        app.dependency_overrides.pop(get_db, None)


def test_reject_drops_unknown_qids():
    client, s = _confirm_client()
    try:
        _event(s, "ph-junk")
        client.post(
            "/api/v1/recognize/reject",
            json={"phash": "ph-junk", "qids": ["Q1", "Qnope"]},
        )
        assert _row(s, "ph-junk").rejected_qids == ["Q1"]
    finally:
        app.dependency_overrides.pop(get_db, None)


def test_reject_garbage_phash_still_204():
    client, s = _confirm_client()
    try:
        r = client.post(
            "/api/v1/recognize/reject", json={"phash": "nope", "qids": ["Q1"]}
        )
        assert r.status_code == 204
    finally:
        app.dependency_overrides.pop(get_db, None)


def test_reject_rejects_oversized_payload():
    client, s = _confirm_client()
    try:
        _event(s, "ph-big")
        too_many = client.post(
            "/api/v1/recognize/reject",
            json={"phash": "ph-big", "qids": [f"Q{i}" for i in range(11)]},
        )
        too_long = client.post(
            "/api/v1/recognize/reject", json={"phash": "ph-big", "qids": ["Q" * 40]}
        )
        assert too_many.status_code == 422
        assert too_long.status_code == 422
        assert _row(s, "ph-big").rejected_qids is None
    finally:
        app.dependency_overrides.pop(get_db, None)
```

> `_event(s, phash, qid="Q1")` 是该文件已有的造事件辅助函数;若签名不同按实际调整,语义是「造一条 24h 内的 candidates 事件」。

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && poetry run python -m pytest --no-cov tests/unit/api/test_recognize_global.py -k "reselect or reject" -q`

(`_confirm_client` 目录里只有 Q1、Q2:测试里用到的 qid 都在其中,`Qnope` 用来验丢弃。)
Expected: FAIL(`rejected_qids` 属性不存在 / reject 端点 404)

- [ ] **Step 3: 模型 + 迁移**

`backend/app/models/recognition_event.py`,在 `confirmed_qid` 那行之后加:

```python
    # S3:用户否定过的候选(改选时服务端把上一次确认记进来;「都不是」时整组记进来)。
    # 分析口径:qid 出现在这里就不算答案,即使 confirmed_qid 还是它 —— confirmed 不清,
    # 因为它兼做 24h 计费幂等(confirm_event)与足迹。
    rejected_qids = Column(JSON().with_variant(JSONB, "postgresql"), nullable=True)
```

(文件已导入 `JSON`/`JSONB`,`timings` 列在用;若没有按 `timings` 的导入补齐。)

Create `backend/alembic/versions/s3r1_recognition_events_rejected.py`:

```python
"""识别事件记「用户否定过的候选」(spec 2026-10-05 S3)。

**加法**:一列 nullable JSONB,老行 NULL。只存作品 qid,不含用户标识,
隐私政策/删号/导出无需配套。
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "s3r1"
down_revision = "f1t1"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "recognition_events",
        sa.Column("rejected_qids", postgresql.JSONB(), nullable=True),
    )


def downgrade():
    op.drop_column("recognition_events", "rejected_qids")
```

先确认 head:`cd backend && poetry run alembic heads` 应为 `f1t1 (head)`;不是的话把 `down_revision` 改成实际 head 并在 ledger 记 Ruling。

- [ ] **Step 4: events.py**

`confirm_event` 中把

```python
        first_time = not any(r.confirmed_qid for r in rows)
        rows[0].confirmed_qid = qid
        db.commit()
        return first_time
```

改为

```python
        prev = next((r.confirmed_qid for r in rows if r.confirmed_qid), None)
        first_time = prev is None
        row = rows[0]
        # S3 改选:上一次确认的那件就是「第一次选错」。服务端自己知道,不收客户端的 previous。
        rejected = [q for q in (row.rejected_qids or []) if q != qid]
        if prev and prev != qid and prev not in rejected:
            rejected.append(prev)
        row.rejected_qids = rejected or None
        row.confirmed_qid = qid
        db.commit()
        return first_time
```

文件末尾新增:

```python
def reject_event(db, phash: str, qids: list[str]) -> None:
    """「都不是」:把这组候选并进最近 24h 该 phash 最新一条事件的 rejected_qids。
    无匹配事件静默返回;任何异常吞掉(fire-and-forget)。"""
    try:
        cutoff = datetime.utcnow() - timedelta(hours=24)
        row = (
            db.query(RecognitionEvent)
            .filter(
                RecognitionEvent.phash == phash,
                RecognitionEvent.created_at >= cutoff,
            )
            .order_by(RecognitionEvent.created_at.desc())
            .first()
        )
        if row is None:
            return
        from app.models.museum_object import MuseumObject

        # 匿名可调:只收目录里真有的 qid(同 confirm_event),防垃圾数据污染分析
        known = {
            q
            for (q,) in db.query(MuseumObject.qid).filter(MuseumObject.qid.in_(qids))
        }
        merged = list(row.rejected_qids or [])
        merged += [q for q in qids if q in known and q not in merged]
        row.rejected_qids = merged
        db.commit()
    except Exception:
        logger.exception("reject_event failed")
        try:
            db.rollback()
        except Exception:
            pass
```

注意:JSON 列原地 append 不会被 SQLAlchemy 判为脏数据,上面两处都是**整列重新赋值新 list**,别改成 `.append`。

- [ ] **Step 5: 端点**

`recognize_global.py` 在 `ConfirmRequest` 之后加:

```python
class RejectRequest(BaseModel):
    phash: str = Field(max_length=64)
    # 候选恒 ≤3;上限放宽到 10 防客户端变化,qid 长度同列宽 32
    qids: list[Annotated[str, Field(max_length=32)]] = Field(max_length=10)
```

(按文件现有导入补 `from typing import Annotated` 与 `from pydantic import BaseModel, Field`。)

在 `recognize_confirm` 之后加:

```python
@router.post("/recognize/reject", status_code=204)
def recognize_reject(body: RejectRequest, db: Session = Depends(get_db)) -> Response:
    """候选卡「都不是」(S3):记下被否定的候选,喂识别质量分析。fire-and-forget 恒 204。
    不计费、不需身份 —— 只写作品 qid,不含用户信息。"""
    from app.services.recognition.events import reject_event

    reject_event(db, body.phash, body.qids)
    return Response(status_code=204)
```

- [ ] **Step 6: 跑测试通过 + 识别/计费全量**

Run: `cd backend && poetry run python -m pytest --no-cov tests/unit/api/test_recognize_global.py tests/unit/services/recognition tests/integration/test_recognize_flow.py tests/integration/test_pass_scope_by_museum.py tests/integration/test_visibility_gate.py tests/unit/api/test_visibility_routes.py -q`
Expected: 全 PASS(含原有 `test_confirm_same_photo_twice_charges_once`)

- [ ] **Step 7: 迁移在真 Postgres 上跑一遍**

Run: `cd backend && poetry run alembic upgrade head && poetry run alembic downgrade -1 && poetry run alembic upgrade head`(本机 docker Postgres;没有就在 ledger 记「迁移仅 CI/staging 验证」)
Expected: 三步都成功。

- [ ] **Step 8: 提交 + 破坏验证**

```bash
cd /Users/hongyang/Projects/GoMuseum
F=(backend/alembic/versions/s3r1_recognition_events_rejected.py backend/app/models/recognition_event.py backend/app/services/recognition/events.py backend/app/api/v1/endpoints/recognize_global.py backend/tests/unit/api/test_recognize_global.py)
black -q $F && isort -q $F && git add $F && git commit -m "feat(recognize): 改选与「都不是」记进 rejected_qids(S3)"
```

破坏:①删掉 `if prev and prev != qid ...: rejected.append(prev)` → `test_reselect_records_previous_as_rejected` 红;②把 `[q for q in (row.rejected_qids or []) if q != qid]` 改成 `list(row.rejected_qids or [])` → `test_reselect_back_removes_from_rejected` 红。各自 `git checkout` 还原,ledger 记结果。

---

### Task 2: 后端 —— 候选摘要加 `image` 与 `credit`

**Files:**
- Modify: `backend/app/services/recognition/service.py`(`_summary_of`)
- Test: `backend/tests/unit/services/recognition/test_service.py`(追加)

**Interfaces:**
- Produces: 候选/命中摘要新增 `image: str | None`(large 档 R2 直链;无 R2 时为 `source_url`)、`credit: str | None`(经 `_photo_credit`,作者本人不算)。

- [ ] **Step 1: 写失败测试**

追加到 `test_service.py`:

```python
def test_summary_has_large_image_and_credit(session):
    """S3 候选放大:缩略图放大是糊的 → 摘要给 large 档;署名按 _photo_credit(作者本人不算)。"""
    from app.services.recognition.service import _summary

    o = session.query(MuseumObject).filter_by(qid="Q334138").one()
    session.add_all(
        [
            ObjectImage(
                object_id=o.id,
                sort=0,
                role="primary",
                source_url="https://commons/x.jpg",
                image_key="images/Q334138/0",
                credit="Photo Studio X",
            ),
        ]
    )
    session.commit()

    class _S:
        def public_url(self, key):
            return f"https://r2/{key}"

    s = _summary(session, _S(), o, "en")
    assert s["thumbnail"] == "https://r2/images/Q334138/0_thumb.jpg"
    assert s["image"] == "https://r2/images/Q334138/0_large.jpg"
    assert s["credit"] == "Photo Studio X"


def test_summary_credit_hidden_when_it_is_the_artist(session):
    from app.services.recognition.service import _summary

    o = session.query(MuseumObject).filter_by(qid="Q334138").one()
    session.add(
        ObjectImage(
            object_id=o.id,
            sort=0,
            role="primary",
            source_url="https://commons/x.jpg",
            credit="Gustave Courbet",
        )
    )
    session.commit()

    class _S:
        def public_url(self, key):
            return f"https://r2/{key}"

    s = _summary(session, _S(), o, "en")
    assert s["image"] == "https://commons/x.jpg"  # 无 R2 → 原链
    assert s["credit"] is None
```

> `ObjectImage` 的必填列以 `app/models/museum_object.py` 为准(如还需 `url` 等列就补上);`_summary` 选图口径若不是 role=primary,按 `_summary` 实际查询造数据。

Run: `cd backend && poetry run python -m pytest --no-cov tests/unit/services/recognition/test_service.py -k summary_ -q`
Expected: FAIL(`KeyError: 'image'`)

- [ ] **Step 2: 实现**

`service.py` 顶部 `from app.services.museum_repo import _resolve_name, _sized` 改为 `from app.services.museum_repo import _photo_credit, _resolve_name, _sized`。

`_summary_of` 中把

```python
    thumbnail = None
    if img and img.image_key:
        thumbnail = _sized(storage, img.image_key, "thumb")
    elif img:
        thumbnail = img.source_url
```

改为

```python
    thumbnail = image = credit = None
    if img and img.image_key:
        thumbnail = _sized(storage, img.image_key, "thumb")
        image = _sized(storage, img.image_key, "large")
    elif img:
        thumbnail = image = img.source_url
    if img:
        # 同详情页图集:CC 署名要留,作者本人不算署名(见 _photo_credit)
        credit = _photo_credit(
            img.credit,
            {
                *((art.name_i18n or {}).values() if art else ()),
                *((art.name_zh, art.name_en) if art else ()),
                o.artist_zh,
                o.artist_en,
            },
        )
```

返回 dict 里 `"thumbnail": thumbnail,` 之后加:

```python
        # S3 加法字段:候选全屏比对用大图 + 署名(老 App 不读)
        "image": image,
        "credit": credit,
```

- [ ] **Step 3: 跑测试 + 全量**

Run: `cd backend && poetry run python -m pytest --no-cov tests/unit/services/recognition tests/integration/test_recognize_flow.py tests/unit/api -q`
Expected: 全 PASS。若有断言摘要 dict **完全相等**的旧测试因多了两个键而红,改成断言子集并在 ledger 记 Ruling。

- [ ] **Step 4: 提交**

```bash
F=(backend/app/services/recognition/service.py backend/tests/unit/services/recognition/test_service.py)
black -q $F && isort -q $F && git add $F && git commit -m "feat(recognize): 候选摘要加大图 image 与署名 credit(S3)"
```

---

### Task 3: 前端 —— 数据层(image/credit、reject 上报)

**Files:**
- Modify: `frontend/gomuseum_app/lib/features/recognition/data/models/recognize_response.dart`(`RecognizedItem`)
- Modify: `frontend/gomuseum_app/lib/features/recognition/data/datasources/recognition_remote_datasource.dart`(接口 + 实现加 `reject`)
- Modify: `frontend/gomuseum_app/lib/features/recognition/presentation/providers/recognition_provider.dart`(`rejectCandidates`)
- Modify(补接口方法): `test/features/recognition/presentation/providers/recognition_quota_state_test.dart`、`recognition_refreshes_footprints_test.dart`、`recognition_retry_test.dart` 里实现 `RecognitionRemoteDataSource` 的假类
- Test: `test/features/recognition/data/models/recognize_response_image_test.dart`(新建)、`recognition_remote_datasource_test.dart`(追加)、新建 `test/features/recognition/presentation/providers/recognition_reject_test.dart`

**Interfaces:**
- Produces: `RecognizedItem.image`(String?,缺则回落 thumbnail)、`RecognizedItem.credit`(String?);`RecognitionRemoteDataSource.reject({required String phash, required List<String> qids}) -> Future<void>`(吞异常)。

- [ ] **Step 1: 写失败测试**

Create `test/features/recognition/data/models/recognize_response_image_test.dart`:

```dart
import 'package:flutter_test/flutter_test.dart';
import 'package:gomuseum_app/features/recognition/data/models/recognize_response.dart';

void main() {
  test('RecognizedItem reads image + credit', () {
    final c = RecognizedItem.fromJson(const {
      'qid': 'Q1',
      'museum': 'orsay',
      'thumbnail': 't.jpg',
      'image': 'L.jpg',
      'credit': 'Studio X',
    });
    expect(c.image, 'L.jpg');
    expect(c.credit, 'Studio X');
  });

  test('RecognizedItem falls back to thumbnail when image missing (old cache)',
      () {
    final c = RecognizedItem.fromJson(
        const {'qid': 'Q1', 'museum': 'orsay', 'thumbnail': 't.jpg'});
    expect(c.image, 't.jpg');
    expect(c.credit, isNull);
  });
}
```

追加到 `recognition_remote_datasource_test.dart` 的 `main()`:

```dart
  test('reject posts phash+qids to /api/v1/recognize/reject', () async {
    when(() => dio.post(any(),
            data: any(named: 'data'), options: any(named: 'options')))
        .thenAnswer((_) async => Response(
            requestOptions: RequestOptions(path: '/api/v1/recognize/reject'),
            statusCode: 204));

    await ds.reject(phash: 'ph', qids: const ['Q1', 'Q2']);

    final v = verify(() => dio.post(captureAny(),
        data: captureAny(named: 'data'), options: any(named: 'options')));
    expect(v.captured[0], '/api/v1/recognize/reject');
    expect(v.captured[1], {
      'phash': 'ph',
      'qids': ['Q1', 'Q2']
    });
  });

  test('reject swallows all exceptions (fire-and-forget)', () async {
    when(() => dio.post(any(),
            data: any(named: 'data'), options: any(named: 'options')))
        .thenThrow(Exception('boom'));
    await ds.reject(phash: 'ph', qids: const ['Q1']);
  });
```

Create `test/features/recognition/presentation/providers/recognition_reject_test.dart`:

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
  final rejects = <(String, List<String>)>[];

  @override
  Future<RecognizeResponse> recognize({
    String? slug,
    required XFile image,
    required String language,
    String mode = 'artwork',
    String? deviceId,
  }) async =>
      RecognizeResponse.fromJson(const {
        'outcome': 'candidates',
        'phash': 'ph1',
        'candidates': [
          {'qid': 'Q1', 'museum': 'orsay', 'title': 'A'},
          {'qid': 'Q2', 'museum': 'orsay', 'title': 'B'},
        ],
      });

  @override
  Future<void> confirm({required String phash, required String qid}) async {}

  @override
  Future<void> reject(
          {required String phash, required List<String> qids}) async =>
      rejects.add((phash, qids));

  @override
  Future<Never> recognizeArtwork(XFile imageFile) async =>
      throw UnimplementedError();
}

void main() {
  test('「都不是」上报这组候选,并落未收录态', () async {
    final ds = _Ds();
    final c = ProviderContainer(overrides: [
      recognitionRemoteDataSourceProvider.overrideWithValue(ds),
      deviceIdProvider.overrideWith((ref) async => 'dev-1'),
    ]);
    addTearDown(c.dispose);
    final n = c.read(recognitionNotifierProvider.notifier);
    await n.recognize(
        image: XFile.fromData(Uint8List.fromList(const [0]), name: 'x.jpg'),
        language: 'en');
    expect(c.read(recognitionNotifierProvider), isA<RecognitionCandidates>());

    n.rejectCandidates();

    expect(c.read(recognitionNotifierProvider), isA<RecognitionUnrecognized>());
    expect(ds.rejects, [
      ('ph1', ['Q1', 'Q2'])
    ]);
  });
}
```

Run: `cd frontend/gomuseum_app && flutter test test/features/recognition`
Expected: FAIL(编译错误:`image`/`credit`/`reject` 未定义)

- [ ] **Step 2: 实现模型**

`RecognizedItem` 构造函数加 `this.image, this.credit,`(可选具名),字段:

```dart
  /// 候选全屏比对用的大图(S3 加法字段;老后端/老缓存没有 → 回落 thumbnail)。
  final String? image;

  /// 图片署名(CC 协议要求;作者本人已由后端剔除)。
  final String? credit;
```

`fromJson` 里:

```dart
    final thumb = j['thumbnail'] as String?;
    return RecognizedItem(
      qid: j['qid'] as String? ?? '',
      title: j['title'] as String? ?? '',
      artist: j['artist'] as String? ?? '',
      thumbnail: thumb,
      image: j['image'] as String? ?? thumb,
      credit: j['credit'] as String?,
      score: rawScore is num ? rawScore.toDouble() : 0.0,
      museum: j['museum'] as String?,
    );
```

`props` 追加 `image, credit`。

- [ ] **Step 3: 实现数据源**

抽象类 `RecognitionRemoteDataSource` 在 `confirm` 之后加:

```dart
  /// 候选卡「都不是」→ 上报被否定的这组候选(S3)。fire-and-forget:吞掉所有异常。
  Future<void> reject({required String phash, required List<String> qids});
```

实现类在 `confirm` 实现之后加:

```dart
  @override
  Future<void> reject(
      {required String phash, required List<String> qids}) async {
    try {
      await dio.post(
        '/api/v1/recognize/reject',
        data: {'phash': phash, 'qids': qids},
        options: Options(headers: {'Accept': 'application/json'}),
      );
    } catch (_) {
      // fire-and-forget:任何失败都吞掉,绝不打扰 UX。
    }
  }
```

三个测试假类(`recognition_quota_state_test.dart` 的 `_ThrowingDs`、`recognition_refreshes_footprints_test.dart` 里的实现类、`recognition_retry_test.dart` 的 `_ScriptedDs`)各加:

```dart
  @override
  Future<void> reject(
      {required String phash, required List<String> qids}) async {}
```

- [ ] **Step 4: 实现 notifier**

`rejectCandidates()` 改为:

```dart
  /// 候选卡「都不是」→ 转未收录 UI（保留已识别的墙签文字），并把这组候选上报为被否定(S3)。
  void rejectCandidates() {
    final s = state;
    if (s is RecognitionCandidates) {
      final phash = s.phash;
      if (phash != null) {
        unawaited(ref.read(recognitionRemoteDataSourceProvider).reject(
            phash: phash, qids: [for (final c in s.candidates) c.qid]));
      }
      state = RecognitionUnrecognized(s.labelText, 'rejected', s.slug);
    }
  }
```

- [ ] **Step 5: 测试 + analyze + 提交**

Run: `cd frontend/gomuseum_app && flutter test test/features/recognition && flutter analyze lib/features/recognition test/features/recognition`
Expected: 全 PASS;改动文件无新增 issue。

```bash
cd /Users/hongyang/Projects/GoMuseum/frontend/gomuseum_app && dart format lib/features/recognition test/features/recognition
cd /Users/hongyang/Projects/GoMuseum
git add <本任务列出的每个文件,逐个写路径>
git commit -m "feat(recognition): 候选大图/署名字段 + 「都不是」上报(S3)"
```

---

### Task 4: 前端 —— 候选放大比对 + 返回候选重选

**Files:**
- Modify: `frontend/gomuseum_app/lib/features/guide/presentation/widgets/image_gallery.dart`(`showImageGallery` 加可选 `footerBuilder`)
- Modify: `frontend/gomuseum_app/lib/features/recognition/presentation/pages/camera_page.dart`(`shouldRestartCamera`、`didChangeAppLifecycleState`、`_goGuide`、`_candidateRow`)
- Modify: 10 个 `lib/l10n/app_*.arb` + 重新生成 `app_localizations*.dart`(新键 `recThisIsIt`)
- Test: `test/features/recognition/camera_lifecycle_test.dart`(追加)、新建 `test/features/guide/image_gallery_footer_test.dart`

**Interfaces:**
- Consumes: Task 3 的 `RecognizedItem.image` / `.credit`。
- Produces: `showImageGallery(context, {required images, initialIndex = 0, Widget Function(BuildContext, int)? footerBuilder})`;`shouldRestartCamera(state, {required bool hasController, bool isTopRoute = true})`。

- [ ] **Step 1: l10n**

每个 arb 在 `"recNoneOfThese"` 行之后加 `"recThisIsIt"`(en 另加 `"@recThisIsIt": {"description": "Button in the full-screen candidate viewer: pick this candidate"}`):

| arb | recThisIsIt |
|---|---|
| zh | 就是这件 |
| zh_Hant | 就是這件 |
| en | This is it |
| fr | C'est celle-ci |
| de | Das ist es |
| es | Es esta |
| it | È questa |
| ja | これです |
| ko | 이 작품이에요 |
| pl | To ta |

Run: `cd frontend/gomuseum_app && flutter gen-l10n`

- [ ] **Step 2: 写失败测试**

`camera_lifecycle_test.dart` 的 group 内追加:

```dart
    // S3:候选进详情页改 push,相机页还在栈里。详情页在上时切后台再回来,
    // 不能在详情页底下把相机重新打开(占相机、亮隐私指示灯)。
    test('相机页不在栈顶 → 回前台也不重建', () {
      expect(
          shouldRestartCamera(AppLifecycleState.resumed,
              hasController: false, isTopRoute: false),
          isFalse);
    });
```

Create `test/features/guide/image_gallery_footer_test.dart`:

```dart
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gomuseum_app/features/content/data/models/object_content_model.dart';
import 'package:gomuseum_app/features/guide/presentation/widgets/image_gallery.dart';

void main() {
  testWidgets('footerBuilder renders per page and its button is tappable',
      (tester) async {
    int? picked;
    await tester.pumpWidget(MaterialApp(
      home: Builder(
        builder: (ctx) => TextButton(
          onPressed: () => showImageGallery(
            ctx,
            images: const [
              ObjectImage(url: 'a.jpg', credit: null),
              ObjectImage(url: 'b.jpg', credit: null),
            ],
            footerBuilder: (_, i) => TextButton(
                onPressed: () => picked = i, child: Text('pick $i')),
          ),
          child: const Text('open'),
        ),
      ),
    ));
    await tester.tap(find.text('open'));
    await tester.pumpAndSettle();
    expect(find.text('pick 0'), findsOneWidget);
    await tester.tap(find.text('pick 0'));
    expect(picked, 0);
  });

  testWidgets('tapping footer blank area does not close the gallery',
      (tester) async {
    await tester.pumpWidget(MaterialApp(
      home: Builder(
        builder: (ctx) => TextButton(
          onPressed: () => showImageGallery(
            ctx,
            images: const [ObjectImage(url: 'a.jpg', credit: null)],
            footerBuilder: (_, i) => const SizedBox(
                width: 300, height: 80, child: Text('title here')),
          ),
          child: const Text('open'),
        ),
      ),
    ));
    await tester.tap(find.text('open'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('title here'));
    await tester.pumpAndSettle();
    expect(find.text('title here'), findsOneWidget); // 画廊还开着
  });
}
```

Run: `cd frontend/gomuseum_app && flutter test test/features/recognition/camera_lifecycle_test.dart test/features/guide/image_gallery_footer_test.dart`
Expected: FAIL(`isTopRoute` / `footerBuilder` 参数不存在)

- [ ] **Step 3: 画廊加底部插槽**

`image_gallery.dart`:`showImageGallery` 与 `_ImageGallery` 各加可选参数 `final Widget Function(BuildContext context, int index)? footerBuilder;` 并透传。

`build` 里现有「credit 署名」那个 `Positioned(left:16,right:16,bottom:0, child: ...署名...)`:把它的 child(署名 widget)提取成局部变量 `creditWidget`(无署名时为 null),然后:

- `footerBuilder == null` → 原样渲染(行为不变)。
- `footerBuilder != null` → 不再单独渲染署名,改为一个底部 Column,footer 在上、署名在下,不会压线:

```dart
          if (widget.footerBuilder != null)
            Positioned(
              left: 16,
              right: 16,
              bottom: 0,
              child: SafeArea(
                top: false,
                // 吞掉 footer 空白处的点击:否则透传到下层「未放大时点任意处关闭」,
                // 用户想看标题、没点准按钮,整个比对视图就关了
                child: GestureDetector(
                  behavior: HitTestBehavior.opaque,
                  onTap: () {},
                  child: Column(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      widget.footerBuilder!(context, _i),
                      if (creditWidget != null) creditWidget,
                    ],
                  ),
                ),
              ),
            ),
```

- [ ] **Step 4: 相机页**

1. `shouldRestartCamera` 改为:

```dart
@visibleForTesting
bool shouldRestartCamera(AppLifecycleState state,
        {required bool hasController, bool isTopRoute = true}) =>
    state == AppLifecycleState.resumed && !hasController && isTopRoute;
```

2. `didChangeAppLifecycleState` 里调用处改为 `shouldRestartCamera(state, hasController: controller != null, isTopRoute: ModalRoute.of(context)?.isCurrent ?? true)`;把 `inactive` 分支里「置 null → setState → dispose」三行抽成 `void _releaseCamera()`(原分支改调它,行为不变):

```dart
  /// 放掉相机(切后台 / 进详情页前)。先置 null 再 dispose:build 里会读它。
  void _releaseCamera() {
    final controller = _controller;
    if (controller == null) return;
    _controller = null;
    if (mounted) setState(() {}); // 不重建的话 CameraPreview 还挂着死纹理
    controller.dispose();
  }
```

3. `_goGuide(String slug, String qid)` 改为 `Future<void> _goGuide(String slug, String qid, {bool fromCandidates = false}) async`,把末尾 `context.pushReplacement(...)` 改为:

```dart
    final args = GuideArgs(
      slug: slug,
      qid: qid,
      imagePath: _captured?.path,
      // 识别成功即自动播讲解:这是"保证送达的首体验",
      // 也是现场"边看边听"的产品形态
      autoPlayAudio: true,
    );
    if (!fromCandidates) {
      context.pushReplacement('/guide', extra: args);
      return;
    }
    // S3:候选点进详情页用 push —— 用户常在详情页点开大图才发现选错,返回要回到候选列表
    // (识别状态还在,不用重拍)。进去前放掉相机(否则详情页底下一直占着相机),回来再开。
    _releaseCamera();
    await context.push('/guide', extra: args);
    if (mounted && _controller == null) _initCamera();
```

同时把注释「这个页马上 pushReplacement 被销毁」改为「这个页可能马上被销毁(命中走 pushReplacement)」。

4. `_candidateRow` 的 `onTap` 改 `() => _goGuide(c.museum!, c.qid, fromCandidates: true)`;把缩略图 `SizedBox(width: 92, height: 92, child: ...)` 包一层:

```dart
            GestureDetector(
              // 缩略图单独可点:全屏放大比对(S3),整行点击仍是直接选
              onTap: () => _openCandidateViewer(c),
              child: Stack(children: [
                SizedBox(/* 原 92×92 缩略图,原样 */),
                Positioned(
                  right: 4,
                  bottom: 4,
                  child: Container(
                    padding: const EdgeInsets.all(3),
                    decoration: const BoxDecoration(
                        color: Colors.black45, shape: BoxShape.circle),
                    child: const GmIcon(GmIcons.search,
                        size: 12, color: Colors.white),
                  ),
                ),
              ]),
            ),
```

(若 `GmIcons` 有更贴切的放大图标如 `zoom`/`expand` 就用它;没有就用 `search`。)

5. 新增方法:

```dart
  /// 候选全屏比对(S3):复用详情页画廊,左右切换三个候选,底部给标题和「就是这件」。
  void _openCandidateViewer(RecognizedItem tapped) {
    final st = ref.read(recognitionNotifierProvider);
    if (st is! RecognitionCandidates) return;
    final cands = st.candidates;
    final l10n = AppLocalizations.of(context)!;
    showImageGallery(
      context,
      images: [
        for (final c in cands)
          ObjectImage(url: c.image ?? c.thumbnail ?? '', credit: c.credit),
      ],
      initialIndex: cands.indexOf(tapped),
      footerBuilder: (ctx, i) => Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Text(cands[i].title,
              textAlign: TextAlign.center,
              style: GmText.serif(
                  size: 16, weight: FontWeight.w600, color: Colors.white)),
          const SizedBox(height: 10),
          GmTicketButton(
            label: l10n.recThisIsIt,
            icon: GmIcons.chevR,
            onTap: () {
              Navigator.of(ctx).pop();
              _goGuide(cands[i].museum!, cands[i].qid, fromCandidates: true);
            },
          ),
        ],
      ),
    );
  }
```

导入 `image_gallery.dart` 与 `object_content_model.dart`(按相机页现有 package 导入风格)。`didChangeAppLifecycleState` 的 `isTopRoute` 处加注释:前提是 `/camera` 与 `/guide` 同在根 Navigator(ShellRoute 外);把相机挪进 shell/嵌套 Navigator 时这个判断要重查。

- [ ] **Step 5: 测试 + analyze**

Run: `cd frontend/gomuseum_app && flutter test test/features/recognition test/features/guide && flutter analyze`
Expected: 全 PASS;改动文件无新增 issue(与改动前 `git stash` 基线对比总数)。

- [ ] **Step 6: 提交 + 破坏验证**

逐个文件 `git add` 后提交 `feat(recognition): 候选全屏比对 + 详情页返回候选重选(S3)`。破坏:①去掉 `&& isTopRoute` → 新 lifecycle 用例红;②去掉 footer 外层 `onTap: () {}` → 「点标题不关闭」红;各自还原。

---

### Task 5: PR → staging 实测

- [ ] **Step 1**: 推分支 `feature/recognition-s3-candidates`,PR → staging,CI 绿后 squash 合并删分支。
- [ ] **Step 2**: 部署后确认 staging 迁移到 `s3r1`(`docker exec gomuseum_staging_backend alembic current` 或查 `alembic_version`)。
- [ ] **Step 3**: 实测:拿一张能出候选的图(或直接造事件)→ `POST /recognize/confirm` Q_A → 再 confirm Q_B → 查该 phash 行 `confirmed_qid=Q_B, rejected_qids=[Q_A]`;另一个 phash 调 `/recognize/reject` → `rejected_qids` 落库;`POST /recognize` 候选响应含 `image`/`credit` 键。
- [ ] **Step 4**: spec 状态行更新(S3 ✅ 合 staging;前端随 S2/S4 同一版 App)。
- [ ] **Step 5**(随包,用户执行):真机走一遍——候选缩略图点开全屏、左右切换、「就是这件」进详情;详情页返回回到候选列表;返回后改选另一件不再扣次;详情页时切后台再回来,系统状态栏不应出现相机占用指示。
