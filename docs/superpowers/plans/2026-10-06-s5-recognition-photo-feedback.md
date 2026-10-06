# S5 识别照片反馈 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 认不准的三个时刻(找到了 / 最终没找到 / 返回后换选)请用户**自愿**发来作品照片;照片只进私有桶、只当信号、≤90 天即删,并能自动分诊。

**Architecture:** 后端新表 `recognition_photo_feedbacks` + 独立私有 R2 桶(独立凭据,不绑域名)+ `POST /feedback/recognition-photo`(multipart,匿名可写)+ 每日清理脚本 + 删号/导出配套 + 分诊报告脚本。**服务端开关**:识别响应加法字段 `photo_feedback`(开关打开且私有桶已配才为 true),App 只在它为 true 时弹框——隐私政策上线前功能整体关着,前端代码可以先合。前端先修一个 S4 遗留:拍说明牌后保住原来那张**作品照片**及其 phash(否则「照片=这件」记的是说明牌、无图作品详情页 hero 显示的也是说明牌)。

**Tech Stack:** FastAPI + SQLAlchemy + Alembic + boto3(R2);Flutter + Riverpod + Dio;flutter gen-l10n(10 语)。

**Spec:** `docs/superpowers/specs/2026-10-05-recognition-failure-feedback-design.md` §三 ⑦⑧⑨⑩⑬、§四 S5、§六

## Global Constraints

- 照片**绝不**进 `gomuseum-assets`、绝不写 `object_images`、绝不对外展示;只进私有桶(独立凭据 `PHOTO_FEEDBACK_R2_*`),key 前缀 `recognition-feedback/`。
- 生命周期:`created_at` 超过 90 天或 `status=done` → 删对象 + `image_key` 置空;删号 → 删该用户全部图片 + 清空 `text`/`query_text`/`label_text` + 断开 `user_id`/`device_id`;导出含元数据、不含图片。
- 匿名可写;限流同 `/feedback`(60/hour);单张上限 10 MB;非图片拒收。
- 确认框:默认不勾;不勾 = 本次 App 进程内不再问;不勾不分叉(后续流程与勾选完全一样);补充文字选填;不加「不再询问」、不自动发送;上传在后台,失败静默重试一次,不阻塞跳转。
- 触发时刻(⑦⑧):①找到了(选择页之后经说明牌识别/搜索找到作品,进详情页前)②最终没找到(选择页点「重新拍摄」放弃这张)③换选(从详情页返回候选后改选另一件,进详情页前)。⑨首次就选了第 2、3 名候选不弹。
- **前端功能整体受服务端开关控制**;隐私政策(中英)由我起草、**用户审核后**才上线;Play 数据安全表单由用户在 Console 改。
- 契约只做加法;前端读新字段 `as T?`。
- 测试:后端 `cd backend && poetry run python -m pytest --no-cov <path>`;前端 `cd frontend/gomuseum_app && flutter test <path>`。禁止 `git add <目录>/`;破坏验证前先提交。

## 与 spec 的有意偏离 / 补充

1. **服务端开关**(spec 未写):用识别响应的加法字段 `photo_feedback` 控制,而不是靠「前端晚于隐私政策发版」——S2/S3/S4 的前端和 S5 前端会进同一版 App,只能靠开关保证「政策没上线就不收照片」。
2. **先修 S4 遗留**(spec 未写):拍说明牌后保留作品照片与其 phash,确认/搜索确认/照片反馈/详情页 hero 全部用作品照片。
3. **「最终没找到」的时刻**定为:选择页点「重新拍摄」(放弃这张照片)。离开相机页不算(YAGNI;离开的原因太多,猜不准)。
4. **分诊线索**只做模糊度(拉普拉斯方差)与过曝比例;spec 里的「画布占比」若识别服务已有现成函数可复用就加,没有就不加(ledger 记 Ruling)。
5. `server_result` 由服务端按 phash 查最近一条识别事件生成(outcome/top_qid/top_score/rejected_qids/confirmed_qid),**不收客户端传的结果**。

## 独立评审处理(2026-10-06,Fable)

| 级别 | 意见 | 处理 |
|---|---|---|
| P0 | 政策写「欧盟区域」但没人保证桶在 EU | **已改**:建桶步骤明确要求 R2 jurisdiction = EU,并让用户回报;政策只在用户确认 EU jurisdiction 后写「欧盟」,否则照现行政策不提地区 |
| P0 | `deviceIdProvider.future.catchError((_) => null)` 运行时抛 | **已改**:照 `recognition_provider.dart` 的 try/catch 写法 |
| P0 | `auth_service.py` 没有 logger | **已改**:Task 2 显式在文件顶部加 `import logging` + `logger` |
| P1 | 说明牌路径改选被记成 found、同一张照片反复问 | **已改**:先判「换选」(corrected)再判「找到了」;同一张作品照片「找到了」只问一次(`_foundAsked`);换选允许再问(答案变了) |
| P1 | 桶写成功+库写失败+补偿删除失败 → 孤儿照片永不删 | **已改**:每日清理再扫私有桶:超过 90 天且无行引用的对象一并删(`list_keys`);补测试 |
| P1 | 导出不含照片 | **已改**:导出给 1 小时有效的 `photo_url`(仍在保存期才有值;取链接失败给 null) |
| P2 | 上限与 `MAX_IMAGE_SIZE_MB` 耦合、措辞 | 设置旁加注释;插入点措辞统一 |

## Review Focus

1. **私有桶没配(或开关关着)**:端点 503、识别响应 `photo_feedback=false`、App 不弹 → Task 1 `test_upload_503_when_bucket_unconfigured`、`test_recognize_flag_off_when_unconfigured`。
2. **删号时私有桶删除失败**(网络抖动):DB 侧照样清文本、断链;失败的 key 记日志,不能让删号整体失败 → Task 2 `test_delete_account_survives_storage_error`。
3. **清理脚本对 `image_key` 已空的行**:跳过,不重复删、不报错 → Task 2 `test_purge_skips_already_purged`。
4. **说明牌路径**:拍了说明牌之后找到作品,确认与照片反馈用的是**作品照片**的 phash 与字节,不是说明牌 → Task 4 `artwork shot survives label capture`(纯函数/状态测试)。
5. **用户不勾**:本进程内不再弹;勾了的上传失败不打扰用户、只重试一次 → Task 5 `declined once → never asks again`、`upload retries once then gives up silently`。

---

### Task 1: 后端 —— 表、私有存储、上传端点、识别响应开关

**Files:**
- Modify: `backend/app/core/config.py`(新设置)
- Modify: `backend/app/services/storage/r2.py`(`presigned_url`)
- Create: `backend/app/services/storage/photo_feedback.py`(私有存储工厂)
- Create: `backend/app/models/recognition_photo_feedback.py`
- Modify: `backend/app/models/__init__.py`(若模型在此集中注册,照现有惯例加一行;否则跳过)
- Create: `backend/alembic/versions/s5p1_recognition_photo_feedbacks.py`
- Create: `backend/app/api/v1/endpoints/recognition_photo_feedback.py` + 在 `app/api/v1/__init__.py` 注册路由(照 `feedback` 的注册方式)
- Modify: `backend/app/services/recognition/service.py`(`recognize_billed` 返回前加 `photo_feedback`)
- Test: `backend/tests/unit/api/test_recognition_photo_feedback.py`(新建)

**Interfaces:**
- Produces:
  - 设置:`PHOTO_FEEDBACK_ENABLED: bool = False`、`PHOTO_FEEDBACK_R2_BUCKET: str = ""`、`PHOTO_FEEDBACK_R2_ACCESS_KEY_ID: str = ""`、`PHOTO_FEEDBACK_R2_SECRET_ACCESS_KEY: str = ""`(endpoint 复用 `R2_ENDPOINT_URL`)、`PHOTO_FEEDBACK_MAX_BYTES: int = 10 * 1024 * 1024`。
  - `get_photo_feedback_storage() -> R2ObjectStorage | None`(未配 → None);`photo_feedback_available() -> bool`(开关 ∧ 已配)。
  - `R2ObjectStorage.presigned_url(key: str, expires: int = 3600) -> str`。
  - 模型 `RecognitionPhotoFeedback`,常量 `TRIGGERS = ("found", "not_found", "corrected")`、`TRIAGES = ("fixed_now", "no_reference", "real_failure")`、`KEY_PREFIX = "recognition-feedback/"`、`RETENTION_DAYS = 90`。
  - 端点 `POST /api/v1/feedback/recognition-photo`(multipart:`image` 文件 + 表单字段 `trigger, phash, answer_qid?, museum_slug?, language?, query_text?, label_text?, text?, device_id?, app_version?`)→ 204;未配/关 → 503;非图片/超大 → 422/413。
  - 识别响应加法字段 `photo_feedback: bool`。

- [ ] **Step 1: 写失败测试**

Create `backend/tests/unit/api/test_recognition_photo_feedback.py`:

```python
"""S5 照片反馈端点。照片只进私有桶;未配置/开关关时整体不可用(隐私政策上线前的闸)。"""

import io
from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import settings
from app.core.database import get_db
from app.main import app
from app.models.recognition_event import RecognitionEvent
from app.models.recognition_photo_feedback import KEY_PREFIX, RecognitionPhotoFeedback
from app.services.storage import photo_feedback as pf


class _FakeStore:
    def __init__(self):
        self.objs = {}

    def put(self, key, data, content_type):
        self.objs[key] = data

    def delete(self, key):
        self.objs.pop(key, None)


def _jpeg(size=(32, 32)):
    buf = io.BytesIO()
    Image.new("RGB", size, (200, 10, 10)).save(buf, format="JPEG")
    return buf.getvalue()


@pytest.fixture()
def env(monkeypatch):
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    RecognitionPhotoFeedback.__table__.create(bind=engine)
    RecognitionEvent.__table__.create(bind=engine)
    s = sessionmaker(bind=engine)()
    store = _FakeStore()
    monkeypatch.setattr(settings, "PHOTO_FEEDBACK_ENABLED", True)
    monkeypatch.setattr(pf, "get_photo_feedback_storage", lambda: store)
    app.dependency_overrides[get_db] = lambda: s
    yield TestClient(app), s, store
    app.dependency_overrides.clear()
    s.close()


def _post(client, image=None, **fields):
    data = {"trigger": "found", "phash": "ph1", **fields}
    return client.post(
        "/api/v1/feedback/recognition-photo",
        data=data,
        files={"image": ("x.jpg", image or _jpeg(), "image/jpeg")},
    )


def test_anonymous_upload_goes_to_private_bucket(env):
    client, s, store = env
    r = _post(client, answer_qid="Q1", museum_slug="orsay", text="说明牌在右边")
    assert r.status_code == 204
    row = s.query(RecognitionPhotoFeedback).one()
    assert row.image_key.startswith(KEY_PREFIX)
    assert list(store.objs) == [row.image_key]
    assert row.trigger == "found" and row.answer_qid == "Q1"
    assert row.user_id is None
    assert row.engine_model == settings.RECOG_MODEL
    assert row.status == "new"


def test_server_result_comes_from_event_not_client(env):
    client, s, _ = env
    s.add(
        RecognitionEvent(
            phash="ph1",
            outcome="candidates",
            top_qid="Q9",
            top_score=0.8,
            engine="vector",
            rejected_qids=["Q9"],
        )
    )
    s.commit()
    _post(client)
    row = s.query(RecognitionPhotoFeedback).one()
    assert row.server_result["top_qid"] == "Q9"
    assert row.server_result["rejected_qids"] == ["Q9"]


def test_upload_503_when_bucket_unconfigured(env, monkeypatch):
    client, s, _ = env
    monkeypatch.setattr(pf, "get_photo_feedback_storage", lambda: None)
    assert _post(client).status_code == 503
    assert s.query(RecognitionPhotoFeedback).count() == 0


def test_upload_503_when_switch_off(env, monkeypatch):
    client, s, _ = env
    monkeypatch.setattr(settings, "PHOTO_FEEDBACK_ENABLED", False)
    assert _post(client).status_code == 503


def test_rejects_non_image(env):
    client, s, store = env
    assert _post(client, image=b"not an image").status_code == 422
    assert not store.objs


def test_rejects_oversized(env, monkeypatch):
    client, s, store = env
    monkeypatch.setattr(settings, "PHOTO_FEEDBACK_MAX_BYTES", 100)
    assert _post(client).status_code == 413
    assert not store.objs


def test_rejects_unknown_trigger(env):
    client, _, store = env
    assert _post(client, trigger="whatever").status_code == 422
    assert not store.objs


def test_storage_failure_leaves_no_row(env, monkeypatch):
    """桶写失败:不能留下一行指向不存在对象的记录;返回 5xx 让 App 重试一次。"""
    client, s, store = env

    def boom(*a, **k):
        raise ConnectionError("r2 down")

    monkeypatch.setattr(store, "put", boom)
    assert _post(client).status_code == 503
    assert s.query(RecognitionPhotoFeedback).count() == 0


def test_recognize_flag_off_when_unconfigured(monkeypatch):
    monkeypatch.setattr(settings, "PHOTO_FEEDBACK_ENABLED", True)
    monkeypatch.setattr(pf, "get_photo_feedback_storage", lambda: None)
    assert pf.photo_feedback_available() is False
    monkeypatch.setattr(pf, "get_photo_feedback_storage", lambda: _FakeStore())
    assert pf.photo_feedback_available() is True
    monkeypatch.setattr(settings, "PHOTO_FEEDBACK_ENABLED", False)
    assert pf.photo_feedback_available() is False
```

并在 `backend/tests/integration/test_recognize_flow.py` 末尾加:

```python
def test_recognize_response_carries_photo_feedback_flag(session, monkeypatch):
    """S5 服务端开关:App 只在识别响应说 true 时才弹「发照片」确认框。"""
    from app.services.recognition.service import recognize_billed
    from app.services.storage import photo_feedback as pf

    _benefits_tables(session)
    kw = dict(user_id=None, device_id="dev1", **_match_kw())
    monkeypatch.setattr(pf, "photo_feedback_available", lambda: False)
    assert recognize_billed(session, "orsay", _jpeg(), **kw)["photo_feedback"] is False
    monkeypatch.setattr(pf, "photo_feedback_available", lambda: True)
    assert recognize_billed(session, "orsay", _jpeg(), **kw)["photo_feedback"] is True
```

Run: `cd backend && poetry run python -m pytest --no-cov tests/unit/api/test_recognition_photo_feedback.py tests/integration/test_recognize_flow.py -k "photo or upload or rejects or server_result or storage_failure or flag" -q`
Expected: FAIL(模块不存在)

- [ ] **Step 2: 设置 + presigned_url + 私有存储工厂**

`config.py` 在 `R2_PUBLIC_BASE_URL` 之后加:

```python
    # S5 识别照片反馈:**独立私有桶 + 独立凭据**,不绑任何公开域名;未配齐 = 功能关闭。
    # 隐私政策上线前保持 PHOTO_FEEDBACK_ENABLED=False(App 据识别响应的 photo_feedback 字段决定弹不弹)。
    PHOTO_FEEDBACK_ENABLED: bool = False
    PHOTO_FEEDBACK_R2_BUCKET: str = ""
    PHOTO_FEEDBACK_R2_ACCESS_KEY_ID: str = ""
    PHOTO_FEEDBACK_R2_SECRET_ACCESS_KEY: str = ""
    # ⚠️ ImageService.validate_image 内部另有 MAX_IMAGE_SIZE_MB 上限;调大这个值时要同步,
    # 否则超过后者的图会被当成「不是图片」返回 422 而不是 413。
    PHOTO_FEEDBACK_MAX_BYTES: int = 10 * 1024 * 1024
```

`r2.py` 末尾加方法:

```python
    def presigned_url(self, key: str, expires: int = 3600) -> str:
        """带时效签名的读链接(私有桶看图用,如分诊报告)。"""
        return self._s3.generate_presigned_url(
            "get_object",
            Params={"Bucket": self._bucket, "Key": key},
            ExpiresIn=expires,
        )
```

Create `backend/app/services/storage/photo_feedback.py`:

```python
"""S5 识别照片反馈的**私有**存储。

与 `get_object_storage()`(公开资产桶 gomuseum-assets)完全分开:独立桶、独立凭据、
不绑域名。public_url 对它没有意义,看图只走 presigned_url。"""

from app.core.config import settings

_instance = None


def get_photo_feedback_storage():
    """未配齐 → None(功能关闭)。"""
    global _instance
    if _instance is None:
        if not (
            settings.PHOTO_FEEDBACK_R2_BUCKET
            and settings.PHOTO_FEEDBACK_R2_ACCESS_KEY_ID
            and settings.PHOTO_FEEDBACK_R2_SECRET_ACCESS_KEY
            and settings.R2_ENDPOINT_URL
        ):
            return None
        from app.services.storage.r2 import R2ObjectStorage

        _instance = R2ObjectStorage(
            settings.R2_ENDPOINT_URL,
            settings.PHOTO_FEEDBACK_R2_ACCESS_KEY_ID,
            settings.PHOTO_FEEDBACK_R2_SECRET_ACCESS_KEY,
            settings.PHOTO_FEEDBACK_R2_BUCKET,
            "",  # 私有桶没有公开地址
        )
    return _instance


def photo_feedback_available() -> bool:
    """开关打开且私有桶已配。识别响应的 photo_feedback 字段、上传端点都看它。"""
    return bool(settings.PHOTO_FEEDBACK_ENABLED) and get_photo_feedback_storage() is not None
```

- [ ] **Step 3: 模型 + 迁移**

Create `backend/app/models/recognition_photo_feedback.py`:

```python
"""S5 识别照片反馈(spec 2026-10-05 §四 S5)。

**照片只当信号不当资产**(用户 2026-10-05 定):只用于补录未收录作品、给无图作品找授权图
并核对、诊断识别失败原因。绝不入识别库、绝不对外展示;≤90 天或处理完即删(取先到);
删号即删。删后只留不含图像的元数据(分数/答案/归因标签)。

不复用 `feedbacks`:有图片、有分诊状态、有 90 天生命周期。"""

import uuid

from sqlalchemy import JSON, Column, DateTime, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID

from app.core.database import Base

TRIGGERS = ("found", "not_found", "corrected")
TRIAGES = ("fixed_now", "no_reference", "real_failure")
KEY_PREFIX = "recognition-feedback/"
RETENTION_DAYS = 90
TEXT_MAX = 1000


class RecognitionPhotoFeedback(Base):
    __tablename__ = "recognition_photo_feedbacks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
    # 同 feedbacks:令牌解析得出才填 user_id,前端不传
    user_id = Column(String(255), nullable=True, index=True)
    device_id = Column(String(255), nullable=True, index=True)

    phash = Column(String(64), nullable=False, index=True)
    museum_slug = Column(String(64), nullable=True)
    language = Column(String(8), nullable=True)
    app_version = Column(String(64), nullable=True)
    engine_model = Column(String(64), nullable=True)

    trigger = Column(String(16), nullable=False, index=True)  # TRIGGERS
    answer_qid = Column(String(32), nullable=True, index=True)  # not_found 为空
    query_text = Column(Text, nullable=True)  # 用户在选择页搜的词
    label_text = Column(Text, nullable=True)  # 说明牌转写
    # 服务端按 phash 查最近识别事件得出(不收客户端传的)
    server_result = Column(JSON().with_variant(JSONB, "postgresql"), nullable=True)
    text = Column(Text, nullable=True)  # 选填补充文字

    image_key = Column(String(255), nullable=True)  # 私有桶 key;删图后置空
    triage = Column(String(16), nullable=True, index=True)  # TRIAGES(自动分诊)
    cause = Column(String(64), nullable=True)  # 人工归因标签
    status = Column(
        String(16), nullable=False, server_default="new", default="new", index=True
    )  # new → triaged → done
```

Create `backend/alembic/versions/s5p1_recognition_photo_feedbacks.py`(`revision="s5p1"`,`down_revision="s4c1"`;先 `poetry run alembic heads` 确认 head):`op.create_table("recognition_photo_feedbacks", ...)` 列与模型一一对应(`server_result` 用 `postgresql.JSONB()`、`id` 用 `postgresql.UUID(as_uuid=True)`、`created_at` `server_default=sa.func.now()`、`status` `server_default="new"`),并为 `created_at, user_id, device_id, phash, trigger, answer_qid, triage, status` 建索引(`op.create_index(op.f("ix_recognition_photo_feedbacks_<col>"), ...)`);`downgrade` drop 索引与表。docstring:新表、存用户主动发送的照片元数据、隐私政策已披露(上线前开关关闭)。

- [ ] **Step 4: 端点**

Create `backend/app/api/v1/endpoints/recognition_photo_feedback.py`:

```python
"""S5 识别照片反馈上传(加法端点)。

只在用户**勾选同意**后由 App 调用。照片进私有桶(独立凭据,不绑域名),
DB 只存 key 与元数据。开关关/桶未配 → 503(隐私政策上线前的闸)。"""

import logging
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.rate_limit import limiter
from app.models.recognition_event import RecognitionEvent
from app.models.recognition_photo_feedback import (
    KEY_PREFIX,
    TEXT_MAX,
    TRIGGERS,
    RecognitionPhotoFeedback,
)
from app.services.storage import photo_feedback as pf

logger = logging.getLogger(__name__)
router = APIRouter()
security = HTTPBearer(auto_error=False)


def _server_result(db, phash: str) -> Optional[dict]:
    ev = (
        db.query(RecognitionEvent)
        .filter(RecognitionEvent.phash == phash)
        .order_by(RecognitionEvent.created_at.desc())
        .first()
    )
    if ev is None:
        return None
    return {
        "outcome": ev.outcome,
        "engine": ev.engine,
        "top_qid": ev.top_qid,
        "top_score": ev.top_score,
        "confirmed_qid": ev.confirmed_qid,
        "rejected_qids": ev.rejected_qids,
    }


def _clip(s: Optional[str]) -> Optional[str]:
    s = (s or "").strip()
    return s[:TEXT_MAX] or None


@router.post("/feedback/recognition-photo", status_code=204)
@limiter.limit("60/hour")
def submit_recognition_photo(
    request: Request,
    image: UploadFile = File(...),
    trigger: str = Form(...),
    phash: str = Form(..., max_length=64),
    answer_qid: Optional[str] = Form(None, max_length=32),
    museum_slug: Optional[str] = Form(None, max_length=64),
    language: Optional[str] = Form(None, max_length=8),
    query_text: Optional[str] = Form(None),
    label_text: Optional[str] = Form(None),
    text: Optional[str] = Form(None),
    device_id: Optional[str] = Form(None, max_length=255),
    app_version: Optional[str] = Form(None, max_length=64),
    db: Session = Depends(get_db),
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
):
    if not pf.photo_feedback_available():
        raise HTTPException(status_code=503, detail="photo_feedback_disabled")
    if trigger not in TRIGGERS:
        raise HTTPException(status_code=422, detail="unknown trigger")
    data = image.file.read(settings.PHOTO_FEEDBACK_MAX_BYTES + 1)
    if len(data) > settings.PHOTO_FEEDBACK_MAX_BYTES:
        raise HTTPException(status_code=413, detail="image too large")
    from app.services.image_service import ImageService

    try:
        ImageService.validate_image(data)
    except Exception:
        raise HTTPException(status_code=422, detail="not an image")

    user_id = None
    if credentials is not None:
        try:
            from app.services.auth_service import AuthService

            user_id = str(AuthService.get_current_user(db, credentials.credentials).id)
        except Exception:
            logger.info("recognition-photo: invalid token, storing anonymously")

    key = f"{KEY_PREFIX}{uuid.uuid4()}.jpg"
    try:
        pf.get_photo_feedback_storage().put(key, data, "image/jpeg")
    except Exception:
        # 先写桶再写库:桶失败就不留指向空对象的行;5xx 让 App 静默重试一次
        logger.exception("recognition-photo: private bucket put failed")
        raise HTTPException(status_code=503, detail="storage_unavailable")
    db.add(
        RecognitionPhotoFeedback(
            user_id=user_id,
            device_id=device_id,
            phash=phash,
            museum_slug=museum_slug,
            language=language,
            app_version=app_version,
            engine_model=settings.RECOG_MODEL,
            trigger=trigger,
            answer_qid=answer_qid,
            query_text=_clip(query_text),
            label_text=_clip(label_text),
            server_result=_server_result(db, phash),
            text=_clip(text),
            image_key=key,
        )
    )
    try:
        db.commit()
    except Exception:
        db.rollback()
        try:
            pf.get_photo_feedback_storage().delete(key)  # 库写失败:别留孤儿照片
        except Exception:
            logger.exception("recognition-photo: orphan cleanup failed: %s", key)
        raise
```

在 `app/api/v1/__init__.py` 照 `feedback.router` 的注册方式加一行注册本 router(同 prefix/tags 惯例)。

> `ImageService.validate_image` 对非图片抛什么异常以实际实现为准;这里统一兜成 422。若 SQLite 测试里 `max_length` 对 `Form` 不生效,不影响(仅防御)。

- [ ] **Step 5: 识别响应开关**

`service.py` `recognize_billed` 中,紧接 `cached = out.pop("_billed", None)` 之后加(之后的每条 `return out` 都会带上):

```python
    # S5 服务端开关(加法字段):App 只在它为 true 时才弹「发照片」确认框。
    # 隐私政策上线前 PHOTO_FEEDBACK_ENABLED=False → 恒 false,前端代码可以先发版。
    from app.services.storage import photo_feedback as pf

    out["photo_feedback"] = pf.photo_feedback_available()
```

(缓存里不存它——`recognize()` 写缓存时还没有这个键;缓存命中时也会被赋上当前开关值。)

- [ ] **Step 6: 测试 + 全量**

Run: `cd backend && poetry run python -m pytest --no-cov tests/unit/api/test_recognition_photo_feedback.py tests/integration/test_recognize_flow.py tests/unit/api tests/unit/services/recognition -q`
Expected: 全 PASS。

- [ ] **Step 7: 提交 + 破坏验证**

逐个文件 `git add`,提交 `feat(feedback): 识别照片反馈 —— 私有桶上传端点 + 服务端开关(S5)`。破坏:①`photo_feedback_available` 去掉 `settings.PHOTO_FEEDBACK_ENABLED and` → `test_upload_503_when_switch_off`、`test_recognize_flag_off_when_unconfigured` 红;②把「先写桶再写库」顺序颠倒(先 `db.add` + `commit` 再 put)→ `test_storage_failure_leaves_no_row` 红;各自还原。

---

### Task 2: 后端 —— 90 天/done 清理、删号删图、导出

**Files:**
- Create: `backend/scripts/purge_recognition_photos.py`
- Create: `deployment/production/purge-recognition-photos.sh`
- Modify: `backend/app/services/auth_service.py`(`delete_user_account`、`export_user_data`)
- Modify: `backend/tests/conftest.py`(`account_tables()` 加新表)
- Test: `backend/tests/unit/scripts/test_purge_recognition_photos.py`(新建;若 `tests/unit/scripts` 不存在就放 `tests/unit/`)、`backend/tests/integration/test_account_deletion.py`(追加)

**Interfaces:**
- Produces: `purge(db, store, now=None) -> int`(返回删掉的图片数);`delete_user_account` 删该用户全部照片对象;导出键 `recognition_photos`(不含 `image_key`)。

- [ ] **Step 1: 写失败测试**

```python
# tests/unit/scripts/test_purge_recognition_photos.py
"""S5 照片生命周期:超过 90 天或 status=done → 删对象 + image_key 置空;行(元数据)保留。"""

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models.recognition_photo_feedback import RecognitionPhotoFeedback as R
from scripts.purge_recognition_photos import purge


class _Store:
    def __init__(self, keys):
        self.objs = set(keys)
        self.deleted = []

    def delete(self, key):
        self.deleted.append(key)
        self.objs.discard(key)


@pytest.fixture()
def db():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    R.__table__.create(bind=engine)
    return sessionmaker(bind=engine)()


NOW = datetime(2026, 10, 6, tzinfo=timezone.utc)


def _row(db, key, age_days, status="new"):
    r = R(
        phash="p",
        trigger="found",
        image_key=key,
        status=status,
        created_at=NOW - timedelta(days=age_days),
    )
    db.add(r)
    db.commit()
    return r


def test_purges_old_and_done_keeps_fresh(db):
    old = _row(db, "k-old", 91)
    done = _row(db, "k-done", 3, status="done")
    fresh = _row(db, "k-fresh", 3)
    store = _Store({"k-old", "k-done", "k-fresh"})
    assert purge(db, store, now=NOW) == 2
    db.expire_all()
    assert old.image_key is None and done.image_key is None
    assert fresh.image_key == "k-fresh"
    assert store.objs == {"k-fresh"}
    assert db.query(R).count() == 3  # 元数据保留


def test_purge_skips_already_purged(db):
    _row(db, None, 200)
    store = _Store(set())
    assert purge(db, store, now=NOW) == 0
    assert store.deleted == []


def test_purge_sweeps_orphan_objects_older_than_retention(db):
    """桶写成功、库写失败、补偿删除也失败 → 桶里有对象但没有行。
    「最长 90 天」不能有例外:超过保存期且无行引用的对象也要删。"""
    _row(db, "k-ref", 100)  # 有行引用,走正常路径

    class _Listing(_Store):
        def list_keys(self, prefix):
            assert prefix == "recognition-feedback/"
            yield "recognition-feedback/orphan-old.jpg", 1, NOW - timedelta(days=95)
            yield "recognition-feedback/orphan-new.jpg", 1, NOW - timedelta(days=2)

    store = _Listing(
        {"k-ref", "recognition-feedback/orphan-old.jpg", "recognition-feedback/orphan-new.jpg"}
    )
    purge(db, store, now=NOW)
    assert "recognition-feedback/orphan-old.jpg" in store.deleted
    assert "recognition-feedback/orphan-new.jpg" not in store.deleted


def test_purge_continues_after_one_delete_fails(db):
    a = _row(db, "k-a", 100)
    b = _row(db, "k-b", 100)

    class _Flaky(_Store):
        def delete(self, key):
            if key == "k-a":
                raise ConnectionError("r2")
            super().delete(key)

    store = _Flaky({"k-a", "k-b"})
    assert purge(db, store, now=NOW) == 1
    db.expire_all()
    assert a.image_key == "k-a"  # 删失败的留着,下次再删
    assert b.image_key is None
```

`test_account_deletion.py` 追加(`_register` 已有):

```python
def _leave_photo(db, uid, key="recognition-feedback/a.jpg"):
    from app.models.recognition_photo_feedback import RecognitionPhotoFeedback

    db.add(
        RecognitionPhotoFeedback(
            user_id=uid,
            device_id="dev-p",
            phash="p",
            trigger="found",
            answer_qid="Q1",
            query_text="INV 779",
            label_text="Portrait",
            text="右下角",
            image_key=key,
        )
    )
    db.commit()


def test_delete_account_removes_photos_and_free_text(client_db, monkeypatch):
    from app.models.recognition_photo_feedback import RecognitionPhotoFeedback
    from app.services.storage import photo_feedback as pf

    deleted = []

    class _S:
        def delete(self, key):
            deleted.append(key)

    monkeypatch.setattr(pf, "get_photo_feedback_storage", lambda: _S())
    client, db = client_db
    t = _register(client, "photo-del@test.com")
    _leave_photo(db, t["user"]["id"])
    assert (
        client.delete(
            "/api/v1/auth/me", headers={"Authorization": f"Bearer {t['access_token']}"}
        ).status_code
        == 204
    )
    db.expire_all()
    row = db.query(RecognitionPhotoFeedback).one()
    assert deleted == ["recognition-feedback/a.jpg"]
    assert row.image_key is None
    assert row.text is None and row.query_text is None and row.label_text is None
    assert row.user_id is None and row.device_id is None
    assert row.answer_qid == "Q1"  # 不含个人信息的答案保留


def test_delete_account_survives_storage_error(client_db, monkeypatch):
    from app.models.recognition_photo_feedback import RecognitionPhotoFeedback
    from app.services.storage import photo_feedback as pf

    class _S:
        def delete(self, key):
            raise ConnectionError("r2 down")

    monkeypatch.setattr(pf, "get_photo_feedback_storage", lambda: _S())
    client, db = client_db
    t = _register(client, "photo-del2@test.com")
    _leave_photo(db, t["user"]["id"])
    r = client.delete(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {t['access_token']}"}
    )
    assert r.status_code == 204
    db.expire_all()
    row = db.query(RecognitionPhotoFeedback).one()
    assert row.user_id is None and row.text is None
    # 对象没删掉:image_key 保留,交给每日清理(断链后它不指向任何人,≤90 天必删)
    assert row.image_key == "recognition-feedback/a.jpg"


def test_export_includes_photo_metadata_not_image(client_db):
    client, db = client_db
    t = _register(client, "photo-exp@test.com")
    _leave_photo(db, t["user"]["id"])
    data = client.get(
        "/api/v1/auth/me/export",
        headers={"Authorization": f"Bearer {t['access_token']}"},
    ).json()
    [p] = data["recognition_photos"]
    assert p["answer_qid"] == "Q1" and p["text"] == "右下角"
    assert "image_key" not in p
```

`conftest.py` 的 `account_tables()` 列表加 `RecognitionPhotoFeedback.__table__`(并在函数内 import)。

Run: `cd backend && poetry run python -m pytest --no-cov tests/unit/scripts/test_purge_recognition_photos.py tests/integration/test_account_deletion.py -q`
Expected: FAIL

- [ ] **Step 2: 清理脚本**

Create `backend/scripts/purge_recognition_photos.py`:

```python
"""S5 识别照片生命周期(每日 cron):超过 90 天或 status=done → 删私有桶对象 + image_key 置空。

照片只当信号不当资产(spec §三⑬):最长 90 天、处理完即删(取先到)。行本身(不含图像的
元数据:分数/答案/归因)保留。单个对象删失败不中断,留着下次再删。

用法:docker exec gomuseum_prod_backend python scripts/purge_recognition_photos.py
"""

import logging
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import or_  # noqa: E402

from app.models.recognition_photo_feedback import (  # noqa: E402
    KEY_PREFIX,
    RETENTION_DAYS,
    RecognitionPhotoFeedback,
)

logger = logging.getLogger("purge_recognition_photos")


def purge(db, store, now=None) -> int:
    now = now or datetime.now(timezone.utc)
    cutoff = now - timedelta(days=RETENTION_DAYS)
    rows = (
        db.query(RecognitionPhotoFeedback)
        .filter(RecognitionPhotoFeedback.image_key.isnot(None))
        .filter(
            or_(
                RecognitionPhotoFeedback.created_at < cutoff,
                RecognitionPhotoFeedback.status == "done",
            )
        )
        .all()
    )
    n = 0
    for r in rows:
        try:
            store.delete(r.image_key)
        except Exception:
            logger.exception("delete failed, will retry next run: %s", r.image_key)
            continue
        r.image_key = None
        n += 1
    db.commit()
    # 孤儿兜底:桶写成功但库写失败(且补偿删除也失败)的对象没有行指向它,上面扫不到。
    # 超过保存期且无行引用 → 删。list_keys 不可用(测试替身/本地存储)就跳过。
    referenced = {
        k
        for (k,) in db.query(RecognitionPhotoFeedback.image_key).filter(
            RecognitionPhotoFeedback.image_key.isnot(None)
        )
    }
    try:
        listing = list(store.list_keys(KEY_PREFIX))
    except (AttributeError, NotImplementedError):
        listing = []
    for key, _size, mtime in listing:
        if key in referenced:
            continue
        if mtime.tzinfo is None:
            mtime = mtime.replace(tzinfo=timezone.utc)
        if mtime < cutoff:
            try:
                store.delete(key)
                n += 1
            except Exception:
                logger.exception("orphan delete failed: %s", key)
    return n


def main() -> int:
    logging.basicConfig(level=logging.INFO)
    from app.core.database import SessionLocal
    from app.services.storage.photo_feedback import get_photo_feedback_storage

    store = get_photo_feedback_storage()
    if store is None:
        print("photo feedback bucket not configured; nothing to purge")
        return 0
    db = SessionLocal()
    try:
        n = purge(db, store)
    finally:
        db.close()
    print(f"purged {n} photo(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

> SQLite 下 `created_at` 带时区比较:若测试因 naive/aware 混比报错,`cutoff` 与测试 `NOW` 统一成 naive UTC(`.replace(tzinfo=None)`)并在 ledger 记 Ruling;Postgres `timestamptz` 两种都能比。

Create `deployment/production/purge-recognition-photos.sh`(照 `reconcile-refunds.sh` 的头注释写安装方法:scp 到 `/opt/gomuseum/`、chmod、crontab `37 4 * * * /opt/gomuseum/purge-recognition-photos.sh >> /var/log/gomuseum-photo-purge.log 2>&1`;正文 `docker exec gomuseum_prod_backend python scripts/purge_recognition_photos.py`,打印退出码)。**安装到 VPS 由用户授权后执行,不在本任务做。**

- [ ] **Step 3: 删号 + 导出**

`delete_user_account`:在 Feedback 那段之后加:

```python
        # S5 识别照片:**图片真删**(私有桶),自由文本真删,断链;答案/分数元数据保留。
        # 桶删失败不让删号整体失败:断链后这行不指向任何人,每日清理 ≤90 天内必删。
        from app.models.recognition_photo_feedback import RecognitionPhotoFeedback
        from app.services.storage.photo_feedback import get_photo_feedback_storage

        store = get_photo_feedback_storage()
        for r in db.query(RecognitionPhotoFeedback).filter(
            RecognitionPhotoFeedback.user_id == uid
        ):
            if r.image_key and store is not None:
                try:
                    store.delete(r.image_key)
                    r.image_key = None
                except Exception:
                    logger.exception("delete account: photo delete failed %s", r.image_key)
            r.user_id = None
            r.device_id = None
            r.text = None
            r.query_text = None
            r.label_text = None
```

**`auth_service.py` 目前没有任何 logging**:在文件顶部 import 区加 `import logging`,模块级加 `logger = logging.getLogger(__name__)`(否则存储异常会变成 NameError,正好打断 Review Focus 2 要保护的删号路径)。

`export_user_data`:查询 `RecognitionPhotoFeedback.user_id == uid` 按 `created_at desc`,返回 dict 加键:

```python
            "recognition_photos": [
                {
                    "trigger": p.trigger,
                    "answer_qid": p.answer_qid,
                    "museum": p.museum_slug,
                    "language": p.language,
                    "query_text": p.query_text,
                    "label_text": p.label_text,
                    "text": p.text,
                    "status": p.status,
                    "photo_stored": p.image_key is not None,
                    # 数据可携:仍在保存期 → 给 1 小时有效的签名链接;取不到给 None
                    "photo_url": _photo_url(p.image_key),
                    "created_at": p.created_at.isoformat() if p.created_at else None,
                }
                for p in photos
            ],
```

`_photo_url` 写成 `export_user_data` 内部小函数:

```python
        from app.services.storage.photo_feedback import get_photo_feedback_storage

        store = get_photo_feedback_storage()

        def _photo_url(key):
            if not key or store is None:
                return None
            try:
                return store.presigned_url(key, expires=3600)
            except Exception:
                return None
```

导出测试 `test_export_includes_photo_metadata_not_image` 改名 `test_export_includes_photo_metadata_and_link`,monkeypatch 一个带 `presigned_url` 的假存储,断言 `p["photo_url"]` 是它返回的串、`"image_key" not in p`。

- [ ] **Step 4: 测试 + 全量 + 提交 + 破坏验证**

Run: `cd backend && poetry run python -m pytest --no-cov tests -q -x`(全量:`account_tables()` 改动会影响所有删号 fixture)
Expected: 全 PASS(已知与本改动无关的单跑 fileno 失败不在全量里出现)。

逐个文件 `git add`,提交 `feat(feedback): 照片 90 天/done 清理 + 删号删图 + 导出(S5)`。破坏:①purge 去掉 `status == "done"` 条件 → `test_purges_old_and_done_keeps_fresh` 红;②删号去掉 `r.text = None` → `test_delete_account_removes_photos_and_free_text` 红;各自还原。

---

### Task 3: 后端 —— 自动分诊报告脚本

**Files:**
- Create: `backend/scripts/recognition_photo_report.py`
- Test: `backend/tests/unit/scripts/test_recognition_photo_report.py`

**Interfaces:**
- Produces: `classify(answer_qid, rerun_out, answer_has_image) -> str`(返回 TRIAGES 之一或 None);`clues(image_bytes) -> dict`(`blur`、`overexposed`);`main()`:对 `status='new'` 且有图的行用当前引擎重跑 `recognize`(slug=None,不计费、不写缓存:传 `redis=None` 之外的现有参数照默认)→ 写 `triage`,`status='triaged'`;`fixed_now` 的删图;打印 Markdown 报告(按 triage 分组,每条:触发时刻、答案、server_result、线索、presigned 链接 1 小时)。

- [ ] **Step 1: 写失败测试**

```python
"""分诊口径:用当前引擎重跑这张照片,结果已经指向答案 → fixed_now;
答案作品库里没图(=没向量,拍照不可能认出)→ no_reference;其余 → real_failure。
not_found(没有答案)只能是 real_failure。"""

import io

import numpy as np
from PIL import Image

from scripts.recognition_photo_report import classify, clues


def test_fixed_now_when_match_is_answer():
    out = {"outcome": "match", "match": {"qid": "Q1"}, "candidates": []}
    assert classify("Q1", out, answer_has_image=True) == "fixed_now"


def test_fixed_now_when_answer_is_top_candidate():
    out = {"outcome": "candidates", "match": None, "candidates": [{"qid": "Q1"}]}
    assert classify("Q1", out, answer_has_image=True) == "fixed_now"


def test_answer_lower_candidate_is_still_failure():
    out = {"outcome": "candidates", "match": None,
           "candidates": [{"qid": "Q2"}, {"qid": "Q1"}]}
    assert classify("Q1", out, answer_has_image=True) == "real_failure"


def test_no_reference_when_answer_has_no_image():
    out = {"outcome": "unrecognized", "match": None, "candidates": []}
    assert classify("Q1", out, answer_has_image=False) == "no_reference"


def test_not_found_is_real_failure():
    out = {"outcome": "unrecognized", "match": None, "candidates": []}
    assert classify(None, out, answer_has_image=False) == "real_failure"


def _jpeg(arr):
    buf = io.BytesIO()
    Image.fromarray(arr.astype("uint8")).save(buf, format="JPEG")
    return buf.getvalue()


def test_clues_flag_blur_and_overexposure():
    flat_white = _jpeg(np.full((64, 64, 3), 255))
    noisy = _jpeg(np.random.default_rng(0).integers(0, 255, (64, 64, 3)))
    c_white, c_noisy = clues(flat_white), clues(noisy)
    assert c_white["overexposed"] > 0.9
    assert c_white["blur"] < c_noisy["blur"]  # 纯色=最「糊」(拉普拉斯方差≈0)
```

Run: `cd backend && poetry run python -m pytest --no-cov tests/unit/scripts/test_recognition_photo_report.py -q`
Expected: FAIL(模块不存在)

- [ ] **Step 2: 实现**

`recognition_photo_report.py`:顶部 docstring 写分诊口径与用法(`docker exec gomuseum_prod_backend python scripts/recognition_photo_report.py [--dry-run]`,`--dry-run` 只打印不写库不删图);`sys.path` 插入同 `purge_recognition_photos.py`。

```python
def classify(answer_qid, rerun_out, answer_has_image) -> str:
    if answer_qid is None:
        return "real_failure"
    m = (rerun_out or {}).get("match") or {}
    cands = (rerun_out or {}).get("candidates") or []
    top = m.get("qid") or (cands[0].get("qid") if cands else None)
    if top == answer_qid:
        return "fixed_now"
    if not answer_has_image:
        return "no_reference"
    return "real_failure"


def clues(image_bytes: bytes) -> dict:
    """拉普拉斯方差(越小越糊)与过曝像素占比(灰度 ≥250)。只做线索,不当判据。"""
    import numpy as np
    from PIL import Image, ImageFilter

    g = Image.open(io.BytesIO(image_bytes)).convert("L")
    g.thumbnail((512, 512))
    lap = np.asarray(g.filter(ImageFilter.FIND_EDGES), dtype=float)
    arr = np.asarray(g)
    return {
        "blur": round(float(lap.var()), 1),
        "overexposed": round(float((arr >= 250).mean()), 3),
    }
```

`main()`:`SessionLocal`;`store = get_photo_feedback_storage()`(None → 打印未配置,退出 0);对 `status == "new"` 且 `image_key` 非空的行:`data = store.get(key)`;`out = recognize(db, None, data, language=row.language or "en")`(全局、无计费);`answer_has_image` = `db.query(ObjectImage).join(MuseumObject).filter(MuseumObject.qid == answer, ObjectImage.role == "primary").first() is not None`;`tri = classify(...)`;非 dry-run 时写 `row.triage = tri; row.status = "triaged"`,`tri == "fixed_now"` → `store.delete(key); row.image_key = None`;每条收集报告行(含 `store.presigned_url(key)`,已删的不给链接)。最后按 triage 分组打印 Markdown,`db.commit()`。

> 画布占比:先 `grep -n "def .*canvas" backend/app/services/recognition/*.py`,若有直接返回占比的现成函数就加进 `clues`,没有就不加并在 ledger 记 Ruling(spec 偏离 4)。⚠️ 重跑 `recognize` 会写一条识别事件(`record_event`)—— 在 docstring 写明这是已知副作用(engine 值照常),不为它改识别服务签名。

- [ ] **Step 3: 测试 + 提交**

Run: `cd backend && poetry run python -m pytest --no-cov tests/unit/scripts -q`
Expected: PASS。提交 `feat(feedback): 识别照片自动分诊报告脚本(S5)`。

---

### Task 4: 前端 —— 拍说明牌后保住作品照片(修 S4 遗留)

**Files:**
- Modify: `frontend/gomuseum_app/lib/features/recognition/presentation/providers/recognition_provider.dart`(`confirmRecognition` 加 `phashOverride`)
- Modify: `frontend/gomuseum_app/lib/features/recognition/presentation/pages/camera_page.dart`
- Test: `test/features/recognition/presentation/providers/recognition_search_confirm_test.dart`(追加)

**Interfaces:**
- Produces: `confirmRecognition(String qid, {bool fromSearch = false, String? phashOverride})`;相机页字段 `XFile? _artworkShot; String? _artworkPhash;`。

- [ ] **Step 1: 写失败测试**

追加到 `recognition_search_confirm_test.dart`:

```dart
  test('phashOverride wins (label path confirms the ARTWORK photo)', () async {
    final (c, ds) =
        await _run(const {'outcome': 'unrecognized', 'phash': 'ph-label'});
    addTearDown(c.dispose);
    await c.read(recognitionNotifierProvider.notifier).confirmRecognition('Q9',
        fromSearch: true, phashOverride: 'ph-artwork');
    expect(ds.confirms, [
      ['ph-artwork', 'Q9', 'search']
    ]);
  });
```

Run: `cd frontend/gomuseum_app && flutter test test/features/recognition/presentation/providers/recognition_search_confirm_test.dart`
Expected: FAIL(`phashOverride` 未定义)

- [ ] **Step 2: 实现**

1. notifier:`confirmRecognition(String qid, {bool fromSearch = false, String? phashOverride})`,`final phash = phashOverride ?? switch (s) {...}`(原 switch 不变)。

2. 相机页:
   - 加字段:

```dart
  /// 用户拍的**作品**照片及其 phash。拍说明牌会覆盖 `_captured`,而「照片=这件」的答案、
  /// 照片反馈、无图作品详情页的 hero 要的都是作品照片,不是说明牌(S5 修 S4 遗留)。
  XFile? _artworkShot;
  String? _artworkPhash;
```

   - `_recognizeImage` 里 `await ...recognize(...)` 之后、`final st = ...` 之后加:非 label 模式(`mode == 'artwork'`)时记下 `_artworkShot = shot; _artworkPhash = switch (st) { RecognitionCandidates() => st.phash, RecognitionUnrecognized() => st.phash, _ => null };`(match 态的 phash 不需要:直接进详情)。
   - `_retake()` 里清空两者(新的一张作品);`_startLabelCapture()` **不清**。
   - `_goGuide`:confirm 调用加 `phashOverride: _artworkPhash`;`GuideArgs.imagePath: (_artworkShot ?? _captured)?.path`。

   > 注意 `_artworkPhash` 在作品识别直接 match 时是 null → override 为 null → 走原 switch(match 态本来也不 confirm),行为不变。

- [ ] **Step 3: 测试 + 提交**

Run: `cd frontend/gomuseum_app && flutter test test/features/recognition && flutter analyze lib/features/recognition`
Expected: 全 PASS。提交 `fix(recognition): 拍说明牌后保住作品照片,答案与详情页 hero 用作品照片(S5 前置)`。

---

### Task 5: 前端 —— 确认框、触发时刻、后台上传

**Files:**
- Modify: `frontend/gomuseum_app/lib/features/recognition/data/models/recognize_response.dart`(`photoFeedback`)
- Create: `frontend/gomuseum_app/lib/features/recognition/data/photo_feedback_repository.dart`
- Create: `frontend/gomuseum_app/lib/features/recognition/presentation/widgets/photo_feedback_dialog.dart`
- Modify: `frontend/gomuseum_app/lib/features/recognition/presentation/providers/recognition_provider.dart`(状态带 `photoFeedback` 开关值)
- Modify: `frontend/gomuseum_app/lib/features/recognition/presentation/pages/camera_page.dart`(三个触发点)
- Modify: 10 个 arb + 重新生成
- Test: `test/features/recognition/data/photo_feedback_repository_test.dart`、`test/features/recognition/presentation/photo_feedback_dialog_test.dart`(新建)

**Interfaces:**
- Consumes: Task 4 的 `_artworkShot` / `_artworkPhash`;后端字段 `photo_feedback` 与端点表单字段名(见 Task 1)。
- Produces:
  - `RecognizeResponse.photoFeedback`(bool,缺 → false);`RecognitionCandidates/RecognitionUnrecognized.photoFeedback`(bool,默认 false)。
  - `class PhotoFeedbackRepository { Future<void> send({required XFile image, required String trigger, required String phash, String? answerQid, String? museumSlug, String? language, String? queryText, String? labelText, String? text, String? deviceId}) }`——失败重试一次,最终失败静默。
  - `final photoFeedbackRepositoryProvider`。
  - `Future<PhotoFeedbackChoice?> showPhotoFeedbackDialog(BuildContext, {required XFile photo})`,`class PhotoFeedbackChoice { final bool send; final String text; }`。
  - 进程级 `bool photoFeedbackDeclinedThisSession`(顶层可写变量,`@visibleForTesting` 可重置)。

- [ ] **Step 1: l10n**

在每个 arb 的 `"recTypeNumberOrName"` 之后加 4 个键(en 各加 `@` 描述):

| 键 | zh | en |
|---|---|---|
| `photoFbTitle` | 把这张照片发给我们? | Send us this photo? |
| `photoFbBody` | 只用来补录作品、改进识别,最多保存 90 天,不对外展示。 | Used only to add missing works and improve recognition. Kept up to 90 days, never shown to anyone. |
| `photoFbConsent` | 发送这张照片 | Send this photo |
| `photoFbNoteHint` | 补充说明(选填) | Add a note (optional) |

其余 8 语(zh_Hant/fr/de/es/it/ja/ko/pl)按同义翻译,**语气与 zh/en 一致、不得新增承诺**(「最多 90 天」「不对外展示」两个承诺必须都在,不得出现「永久」「分享」等词)。按钮沿用已有 `camContinue`/通用「继续」键;没有就加 `photoFbContinue`(继续 / Continue …)。

Run: `flutter gen-l10n`

- [ ] **Step 2: 写失败测试**

Create `test/features/recognition/data/photo_feedback_repository_test.dart`:

```dart
import 'dart:typed_data';

import 'package:cross_file/cross_file.dart';
import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gomuseum_app/features/recognition/data/photo_feedback_repository.dart';
import 'package:mocktail/mocktail.dart';

class _Dio extends Mock implements Dio {}

void main() {
  setUpAll(() => registerFallbackValue(Options()));
  final img = XFile.fromData(Uint8List.fromList(const [1, 2, 3]),
      name: 'a.jpg', mimeType: 'image/jpeg');

  test('posts multipart with trigger/phash/answer to the photo endpoint',
      () async {
    final dio = _Dio();
    when(() => dio.post(any(), data: any(named: 'data'))).thenAnswer((_) async =>
        Response(requestOptions: RequestOptions(path: ''), statusCode: 204));
    await PhotoFeedbackRepository(dio).send(
        image: img, trigger: 'found', phash: 'ph', answerQid: 'Q1', text: 'x');
    final cap = verify(() => dio.post(captureAny(), data: captureAny(named: 'data')))
        .captured;
    expect(cap[0], '/api/v1/feedback/recognition-photo');
    final form = cap[1] as FormData;
    final fields = Map.fromEntries(form.fields);
    expect(fields['trigger'], 'found');
    expect(fields['phash'], 'ph');
    expect(fields['answer_qid'], 'Q1');
    expect(form.files.single.key, 'image');
  });

  test('upload retries once then gives up silently', () async {
    final dio = _Dio();
    when(() => dio.post(any(), data: any(named: 'data')))
        .thenThrow(DioException(requestOptions: RequestOptions(path: '')));
    await PhotoFeedbackRepository(dio, retryDelay: Duration.zero)
        .send(image: img, trigger: 'not_found', phash: 'ph');
    verify(() => dio.post(any(), data: any(named: 'data'))).called(2);
  });
}
```

Create `test/features/recognition/presentation/photo_feedback_dialog_test.dart`:

```dart
import 'dart:typed_data';

import 'package:cross_file/cross_file.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gomuseum_app/features/recognition/presentation/widgets/photo_feedback_dialog.dart';
import 'package:gomuseum_app/l10n/app_localizations.dart';

void main() {
  // 1×1 透明 PNG
  final png = Uint8List.fromList(const [
    0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A, 0, 0, 0, 13, 0x49, 0x48,
    0x44, 0x52, 0, 0, 0, 1, 0, 0, 0, 1, 8, 6, 0, 0, 0, 0x1F, 0x15, 0xC4,
    0x89, 0, 0, 0, 13, 0x49, 0x44, 0x41, 0x54, 0x78, 0x9C, 0x63, 0, 1, 0, 0,
    5, 0, 1, 0x0D, 0x0A, 0x2D, 0xB4, 0, 0, 0, 0, 0x49, 0x45, 0x4E, 0x44,
    0xAE, 0x42, 0x60, 0x82
  ]);

  Future<PhotoFeedbackChoice?> open(WidgetTester t,
      Future<void> Function(WidgetTester) act) async {
    PhotoFeedbackChoice? result;
    await t.pumpWidget(MaterialApp(
      locale: const Locale('en'),
      localizationsDelegates: AppLocalizations.localizationsDelegates,
      supportedLocales: AppLocalizations.supportedLocales,
      home: Builder(
        builder: (ctx) => TextButton(
          onPressed: () async => result = await showPhotoFeedbackDialog(ctx,
              photo: XFile.fromData(png, name: 'p.png')),
          child: const Text('go'),
        ),
      ),
    ));
    await t.tap(find.text('go'));
    await t.pumpAndSettle();
    await act(t);
    await t.pumpAndSettle();
    return result;
  }

  testWidgets('unchecked by default → continue = not send', (t) async {
    final r = await open(t, (t) async {
      expect(t.widget<Checkbox>(find.byType(Checkbox)).value, isFalse);
      await t.tap(find.byKey(const Key('photoFbContinue')));
    });
    expect(r?.send, isFalse);
  });

  testWidgets('checked + note → send with text', (t) async {
    final r = await open(t, (t) async {
      await t.tap(find.byType(Checkbox));
      await t.enterText(find.byType(TextField), 'label on the right');
      await t.tap(find.byKey(const Key('photoFbContinue')));
    });
    expect(r?.send, isTrue);
    expect(r?.text, 'label on the right');
  });
}
```

另在 `recognize_response_test.dart`(已有)追加:`photo_feedback` 缺省 false、`true` 时为 true。

Run: `cd frontend/gomuseum_app && flutter test test/features/recognition`
Expected: FAIL(未定义)

- [ ] **Step 3: 实现数据层**

- `RecognizeResponse`:字段 `final bool photoFeedback;`,`fromJson` 读 `j['photo_feedback'] as bool? ?? false`;构造参数默认 false。
- `RecognitionCandidates` / `RecognitionUnrecognized` 加具名 `{this.photoFeedback = false}`;`recognize()` 构造这两态时传 `photoFeedback: resp.photoFeedback`;`rejectCandidates` 透传 `s.photoFeedback`。
- `photo_feedback_repository.dart`(照 `feedback_repository.dart` 的轻量范式;`kVersionFootnote` 同样附带 `app_version`):

```dart
/// S5 识别照片反馈上传。**只在用户勾选后调用**;后台进行,失败重试一次后静默放弃 ——
/// 绝不打扰用户(他已经去看详情页了)。
class PhotoFeedbackRepository {
  PhotoFeedbackRepository(this._dio,
      {this.retryDelay = const Duration(seconds: 3)});
  final Dio _dio;
  final Duration retryDelay;

  Future<void> send({
    required XFile image,
    required String trigger,
    required String phash,
    String? answerQid,
    String? museumSlug,
    String? language,
    String? queryText,
    String? labelText,
    String? text,
    String? deviceId,
  }) async {
    final bytes = await image.readAsBytes();
    FormData form() => FormData.fromMap({
          'image': MultipartFile.fromBytes(bytes,
              filename: 'photo.jpg', contentType: MediaType('image', 'jpeg')),
          'trigger': trigger,
          'phash': phash,
          if (answerQid != null) 'answer_qid': answerQid,
          if (museumSlug != null) 'museum_slug': museumSlug,
          if (language != null) 'language': language,
          if (queryText != null && queryText.trim().isNotEmpty)
            'query_text': queryText.trim(),
          if (labelText != null) 'label_text': labelText,
          if (text != null && text.trim().isNotEmpty) 'text': text.trim(),
          if (deviceId != null) 'device_id': deviceId,
          'app_version': kVersionFootnote,
        });
    for (var attempt = 0; attempt < 2; attempt++) {
      try {
        // FormData 只能发一次:每次重建
        await _dio.post<void>('/api/v1/feedback/recognition-photo', data: form());
        return;
      } catch (_) {
        if (attempt == 0) await Future<void>.delayed(retryDelay);
      }
    }
  }
}

final photoFeedbackRepositoryProvider = Provider<PhotoFeedbackRepository>(
    (ref) => PhotoFeedbackRepository(ref.watch(dioProvider)));
```

(`dioProvider` 用识别数据源同一个;`MediaType` 来自 `http_parser`,识别数据源已在用;Provider 的导入照 Task S2 已用的方式。)

- [ ] **Step 4: 确认框组件**

`photo_feedback_dialog.dart`:

```dart
/// 本次 App 进程内用户拒绝过(没勾就继续)→ 不再问(spec ⑩)。进程重启即重置。
bool photoFeedbackDeclinedThisSession = false;

class PhotoFeedbackChoice {
  const PhotoFeedbackChoice({required this.send, this.text = ''});
  final bool send;
  final String text;
}

/// 「把这张照片发给我们?」——缩略图 + 一句用途 + 选填补充 + **默认不勾**的勾选框 + 继续。
/// 只有一个「继续」按钮:不勾不分叉,后续流程与勾选完全一样(spec ⑦⑩)。
/// 返回 null = 用户用系统返回关掉了(按不发处理)。
Future<PhotoFeedbackChoice?> showPhotoFeedbackDialog(BuildContext context,
    {required XFile photo}) { ... }
```

实现要点:`showDialog`,`StatefulBuilder` 持 `bool checked=false` 与 `TextEditingController`;内容依次:标题 `photoFbTitle`;`Image.memory`(`FutureBuilder` 读 `photo.readAsBytes()`,高 120,`BoxFit.cover`);`photoFbBody`;`CheckboxListTile`(`photoFbConsent`,`value: checked`);`TextField`(`hintText: photoFbNoteHint`,`maxLength: 300`,仅 `checked` 时可编辑);底部 `TextButton(key: Key('photoFbContinue'))` → `Navigator.pop(PhotoFeedbackChoice(send: checked, text: ctrl.text))`。样式用相机页已在用的 `GmText`/`context.gm`。

- [ ] **Step 5: 相机页三个触发点**

加一个私有方法(所有触发点共用):

```dart
  /// S5 照片反馈。服务端开关关着、本进程已拒绝过、没有作品照片 → 不弹,直接返回。
  /// 不勾不分叉:无论选什么,调用方之后的流程完全一样;上传在后台,不 await。
  Future<void> _maybeAskPhoto(String trigger,
      {String? answerQid, String? museum, String? queryText}) async {
    final st = ref.read(recognitionNotifierProvider);
    final shot = _artworkShot;
    final phash = _artworkPhash;
    if (!_photoFeedbackEnabled ||
        photoFeedbackDeclinedThisSession ||
        shot == null ||
        phash == null) {
      return;
    }
    final choice = await showPhotoFeedbackDialog(context, photo: shot);
    if (choice == null || !choice.send) {
      photoFeedbackDeclinedThisSession = true;
      return;
    }
    final labelText = st is RecognitionUnrecognized ? st.labelText : null;
    // 照 recognition_provider 的写法:Future<String> 上 catchError 返回 null 会运行时抛
    String? deviceId;
    try {
      deviceId = await ref.read(deviceIdProvider.future);
    } catch (_) {
      deviceId = null;
    }
    unawaited(ref.read(photoFeedbackRepositoryProvider).send(
          image: shot,
          trigger: trigger,
          phash: phash,
          answerQid: answerQid,
          museumSlug: museum,
          language: apiLanguage(ref.read(resolvedLocaleProvider)),
          queryText: queryText,
          labelText: labelText,
          text: choice.text,
          deviceId: deviceId,
        ));
  }
```

`_photoFeedbackEnabled`:相机页字段(`bool`,默认 false),在作品识别结果落态时(Task 4 记 `_artworkPhash` 的同一处)记下该态的 `photoFeedback`——说明牌识别后状态换了,开关值要从作品那次带过来。

追踪「经过了选择页」与「换选」:

```dart
  /// 这张作品照片走到过选择页(「没认出来」或「都不是」)——之后找到作品 = 触发 ①。
  bool _reachedChoice = false;

  /// 候选路径上用户已进过详情页的那件 —— 返回后改选另一件 = 触发 ③。
  String? _candidateOpened;
```

- 状态变为 `RecognitionUnrecognized` 且当前不是说明牌模式(作品照片那次)时 `_reachedChoice = true`——在 `build` 里读状态不合适,放在 `_recognizeImage` 落态后判断 + `rejectCandidates` 调用处(候选卡「都不是」的 `onTap` 改为先调 notifier 再 `setState(() => _reachedChoice = true)`)。
- `_retake()`:**先**判断 `_reachedChoice && 当前状态是 Unrecognized` → `await _maybeAskPhoto('not_found')`(触发 ②),再清空 `_artworkShot/_artworkPhash/_reachedChoice/_candidateOpened/_photoFeedbackEnabled`。`_retake` 改为 `Future<void> _retake() async`,调用处 `onTap: _retake` 不变。402 路径里的 `_retake()` 调用不受影响(那时 `_reachedChoice` 为 false)。
- `_goGuide`:在 confirm 调用**之前**:

```dart
    if (fromSearch || (_reachedChoice && !fromCandidates)) {
      await _maybeAskPhoto('found', answerQid: qid, museum: slug, queryText: queryText);
    } else if (fromCandidates && _candidateOpened != null && _candidateOpened != qid) {
      await _maybeAskPhoto('corrected', answerQid: qid, museum: slug);
    }
    if (fromCandidates) _candidateOpened = qid;
```

  `_goGuide` 新增具名参数 `String? queryText`。判定(**先判换选,再判找到了**):

```dart
    final corrected =
        fromCandidates && _candidateOpened != null && _candidateOpened != qid;
    if (corrected) {
      // 返回后改选另一件(含说明牌出的候选):答案变了,允许再问一次
      await _maybeAskPhoto('corrected', answerQid: qid, museum: slug);
    } else if ((fromSearch || _reachedChoice) && !_foundAsked) {
      // 走过选择页之后找到了作品(搜索 / 说明牌 match / 说明牌候选);同一张照片只问一次
      _foundAsked = true;
      await _maybeAskPhoto('found',
          answerQid: qid, museum: slug, queryText: queryText);
    }
    if (fromCandidates) _candidateOpened = qid;
    if (!mounted) return;
```

  新字段 `bool _foundAsked = false;`,`_retake()` 里与其它字段一起清。说明牌直接 match 走 pushReplacement 分支前同样经过上面的判定(`_reachedChoice` 为 true → found)。同一张照片可能产生两行(found A、corrected B):分诊与人工复核按 phash 取最新一行,写进分诊脚本 docstring。

  ⑨ 首次就选第 2、3 名:`_candidateOpened == null` → 不弹(满足)。
- `_TagSearchSheet` 的 `onPick` 签名改为 `void Function(SearchObject obj, String query)`,sheet 内 `onPickObject: widget.onPick == null ? null : (o) => widget.onPick!(o, _q)`;相机页 `onPick: (obj, q) => _goGuide(obj.museum!, obj.qid, fromSearch: true, queryText: q)`。
- 弹框是 `await` 的:用户点「继续」后才跳转;`await` 之后检查 `if (!mounted) return;`。

- [ ] **Step 6: 测试 + analyze + 提交**

Run: `cd frontend/gomuseum_app && flutter test test/features/recognition test/features/search test/features/guide && flutter analyze`
Expected: 全 PASS;改动文件无新增 issue。逐个文件 `git add`,提交 `feat(recognition): 识别照片反馈确认框 + 三个触发时刻 + 后台上传(S5,服务端开关控制)`。

破坏:①repository 去掉重试循环(只发一次)→ `upload retries once` 红;②确认框 `checked` 初值改 true → `unchecked by default` 红;各自还原。

---

### Task 6: 隐私政策草稿(不上线)

**Files:**
- Modify: `deployment/website/privacy.html`(中英两处;`deployment/website/fr/` 若有隐私页同步法语,没有就不新建)

- [ ] **Step 1**: 第 2 节表格「展品照片」那行改为:拍照识别的照片**默认不存储**(临时处理即丢弃);**仅当你在「把这张照片发给我们?」中主动勾选发送时**保存,用于补录作品、核对授权图片、改进识别;**最长 90 天**、处理完即删;**不对外展示、不用于训练识别模型的参考库**;删号即删。英文段落同义补一句。第 3 节处理者补:你主动发送的照片存放在 Cloudflare R2 的**私有**存储(仅我们凭密钥访问)。**只有用户确认建桶时选了 R2 jurisdiction = EU,才加「欧盟区域」**;没确认就不提地区(与现行政策对公开桶的写法一致)。第 4 节删除权补:删号时你发送过的照片一并删除。第 5 节「Cloudflare R2(不含个人数据)」改为「内容资产(不含个人数据)与你主动发送的照片(私有存储)」。第 7 节更新日期。
- [ ] **Step 2**: 提交 `docs(privacy): 草稿 —— 识别照片反馈(待用户审核后上线)`。**不部署网站;不改 PHOTO_FEEDBACK_ENABLED。**把改动的中英文段落原文贴给用户审核。

---

### Task 7: PR → staging(开关关着)

- [ ] **Step 1**: 推分支 `feature/recognition-s5-photo-feedback`,PR → staging,CI 绿后 squash 合并删分支。
- [ ] **Step 2**: staging 部署后:迁移到 `s5p1`;`POST /api/v1/feedback/recognition-photo` 返回 503(开关关);识别响应含 `"photo_feedback": false`。
- [ ] **Step 3**: 用户给出私有桶凭据后(另行):写进 **staging** `.env` 并在 staging 打开 `PHOTO_FEEDBACK_ENABLED=true`(staging 不对真实用户);实测上传 → 私有桶有对象、行落库;`presigned_url` 能取图、公开域名取不到;清理脚本对 `status=done` 行删图。prod 打开开关要等:①隐私政策上线 ②用户确认 ③用户改 Play 数据安全表单。
- [ ] **Step 4**: spec 状态行更新(S5 合 staging,开关关;待:用户建桶、审政策、改 Play 表单、装 cron)。
