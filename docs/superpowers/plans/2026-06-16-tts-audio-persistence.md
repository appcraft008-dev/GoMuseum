# TTS 音频落库收口 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让 `/content/tts/generate` 在 section 模式下生成音频后落库到 R2 + `object_content_sections.audio_key`，replay 复用，堵掉每次播放重付 OpenAI TTS 的成本漏洞。

**Architecture:** 对称已有的 `persist_explanation`：`content_repo` 新增 `persist_section_audio`（生成 bytes 由端点提供，repo 负责传 R2 + 写 audio_key）与读侧 `get_section_audio_key`；`persist_explanation` 改为 body 变更时清空 audio_key；端点改双模（section→JSON `audio_url`，ad-hoc→保留流）；前端 datasource section 模式解析 JSON。

**Tech Stack:** FastAPI + SQLAlchemy(SQLite 测试) + pytest（后端）；Flutter + Dio + mocktail（前端）。

设计文档：`docs/superpowers/specs/2026-06-16-tts-audio-persistence-design.md`。

**分支：** `feature/tts-audio-persistence`（已有 spec commit）。

**运行测试的方式：** 后端用 `poetry run pytest`（项目 venv 在 `~/Library/Caches/pypoetry`，无 `backend/.venv`）；命令均在 `backend/` 目录下执行。前端在 `frontend/gomuseum_app/` 下 `flutter test`。

---

## File Structure

| 文件 | 责任 | 改动 |
|---|---|---|
| `backend/app/services/content_repo.py` | 内容落库（讲解+音频） | 新增 `persist_section_audio`、`get_section_audio_key`；改 `persist_explanation` 失效逻辑 |
| `backend/app/api/v1/endpoints/content.py` | content API | `TTSRequest` 加 `qid`/`section_code`；新增 `AudioUrlResponse`；`generate_tts_audio` 改双模 |
| `backend/tests/integration/test_section_audio.py` | 新测试 | `persist_section_audio` + `get_section_audio_key` |
| `backend/tests/integration/test_content_persist.py` | 既有测试 | 加 `persist_explanation` 失效用例 |
| `backend/tests/integration/test_tts_endpoint.py` | 新测试 | 端点双模 |
| `frontend/.../content/data/datasources/content_remote_datasource.dart` | 前端 TTS 调用 | `generateTtsAudio` 加 `qid`/`sectionCode`，section 模式解析 `audio_url` |
| `frontend/.../test/features/content/data/datasources/content_remote_datasource_test.dart` | 新测试 | section 模式解析 |

---

## Task 1: `persist_section_audio`（音频 write-through）

**Files:**
- Modify: `backend/app/services/content_repo.py`
- Test: `backend/tests/integration/test_section_audio.py` (create)

- [ ] **Step 1: 写失败测试**

创建 `backend/tests/integration/test_section_audio.py`：

```python
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.models.content import ObjectContentSection
from app.models.museum import Museum
from app.models.museum_object import MuseumObject, ObjectImage
from app.services.content_repo import get_section_audio_key, persist_section_audio
from app.services.object_importer import upsert_museum, upsert_object


class FakeStorage:
    def __init__(self):
        self.objects = {}

    def put(self, key, data, content_type):
        self.objects[key] = (data, content_type)

    def exists(self, key):
        return key in self.objects

    def public_url(self, key):
        return f"https://cdn.test/{key}"


class BoomStorage(FakeStorage):
    def put(self, key, data, content_type):
        raise RuntimeError("r2 down")


@pytest.fixture()
def session():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(
        bind=engine,
        tables=[
            Museum.__table__,
            MuseumObject.__table__,
            ObjectImage.__table__,
            ObjectContentSection.__table__,
        ],
    )
    s = sessionmaker(bind=engine)()
    m = upsert_museum(s, {"slug": "orsay", "name_en": "Orsay"})
    upsert_object(
        s,
        m.id,
        {"qid": "Q1", "title_en": "A", "image": "http://x/a.jpg", "attributes": {}},
    )
    s.commit()
    yield s


def test_persist_section_audio_uploads_and_writes_key(session):
    storage = FakeStorage()
    key = persist_section_audio(session, "Q1", "en", "overview", b"MP3", storage)
    assert key == "object-audio/Q1/en/overview.mp3"
    assert storage.exists(key)
    row = (
        session.query(ObjectContentSection)
        .filter_by(language="en", section_code="overview")
        .one()
    )
    assert row.audio_key == key


def test_persist_section_audio_unknown_qid_returns_none(session):
    storage = FakeStorage()
    assert persist_section_audio(session, "Q404", "en", "overview", b"x", storage) is None
    assert storage.objects == {}


def test_persist_section_audio_upload_failure_writes_no_key(session):
    with pytest.raises(RuntimeError):
        persist_section_audio(session, "Q1", "en", "overview", b"x", BoomStorage())
    row = (
        session.query(ObjectContentSection)
        .filter_by(language="en", section_code="overview")
        .one_or_none()
    )
    assert row is None or row.audio_key is None
```

- [ ] **Step 2: 跑测试确认失败**

Run: `poetry run pytest tests/integration/test_section_audio.py -v`
Expected: FAIL — `ImportError: cannot import name 'persist_section_audio'`（`get_section_audio_key` 也尚未存在，Task 3 补；本任务先让 `persist_section_audio` 的三条过）。

- [ ] **Step 3: 实现 `persist_section_audio`**

在 `backend/app/services/content_repo.py` 末尾追加（沿用文件已 import 的 `Session`/`ObjectContentSection`/`MuseumObject`）：

```python
def persist_section_audio(
    db: Session,
    qid: str,
    language: str,
    section_code: str,
    audio_bytes: bytes,
    storage,
) -> str | None:
    """把一段已生成的音频落库：传 R2 + 写 object_content_sections.audio_key。

    返回 audio_key；qid 不存在返回 None。上传失败时异常上抛，绝不写 audio_key
    （避免指向缺失对象的悬空指针）。
    """
    obj = db.query(MuseumObject).filter_by(qid=qid).one_or_none()
    if not obj:
        return None
    key = f"object-audio/{qid}/{language}/{section_code}.mp3"
    storage.put(key, audio_bytes, "audio/mpeg")  # 失败则下方不执行，不写 key
    row = db.query(ObjectContentSection).filter_by(
        object_id=obj.id, language=language, section_code=section_code
    ).one_or_none() or ObjectContentSection(
        object_id=obj.id, language=language, section_code=section_code
    )
    row.audio_key = key
    db.add(row)
    db.commit()
    return key
```

- [ ] **Step 4: 跑测试确认通过**

Run: `poetry run pytest tests/integration/test_section_audio.py -k persist_section_audio -v`
Expected: 3 passed。

- [ ] **Step 5: 提交**

```bash
git add backend/app/services/content_repo.py backend/tests/integration/test_section_audio.py
git commit -m "feat(content): persist_section_audio 把 TTS 音频落库到 R2+audio_key"
```

---

## Task 2: `persist_explanation` body 变更失效 audio_key

**Files:**
- Modify: `backend/app/services/content_repo.py:18-40` (`persist_explanation`)
- Test: `backend/tests/integration/test_content_persist.py` (append)

- [ ] **Step 1: 写失败测试**

在 `backend/tests/integration/test_content_persist.py` 末尾追加：

```python
def test_persist_explanation_clears_audio_on_body_change(session):
    payload = {"summary": "s1", "interesting_facts": []}
    persist_explanation(session, "Q1", "en", payload)
    row = (
        session.query(ObjectContentSection)
        .filter_by(language="en", section_code="overview")
        .one()
    )
    row.audio_key = "object-audio/Q1/en/overview.mp3"
    session.commit()

    persist_explanation(session, "Q1", "en", {"summary": "s2", "interesting_facts": []})
    session.refresh(row)
    assert row.body == "s2"
    assert row.audio_key is None


def test_persist_explanation_keeps_audio_on_same_body(session):
    payload = {"summary": "same", "interesting_facts": []}
    persist_explanation(session, "Q1", "en", payload)
    row = (
        session.query(ObjectContentSection)
        .filter_by(language="en", section_code="overview")
        .one()
    )
    row.audio_key = "object-audio/Q1/en/overview.mp3"
    session.commit()

    persist_explanation(session, "Q1", "en", payload)
    session.refresh(row)
    assert row.audio_key == "object-audio/Q1/en/overview.mp3"
```

> 注：测试 import 已含 `ObjectContentSection`（文件顶部第 8 行）。`persist_explanation` 只对非空 body 的 section 写入，`summary→overview`，故只断言 overview 行。

- [ ] **Step 2: 跑测试确认失败**

Run: `poetry run pytest tests/integration/test_content_persist.py -k audio -v`
Expected: FAIL — `test_persist_explanation_clears_audio_on_body_change` 断言 `row.audio_key is None` 失败（当前实现不清 audio_key，仍为旧值）。

- [ ] **Step 3: 实现失效逻辑**

把 `backend/app/services/content_repo.py` 的 `persist_explanation` 循环体（第 27-38 行）改为：

```python
    for code, body in sections.items():
        if not body:
            continue
        existing = (
            db.query(ObjectContentSection)
            .filter_by(object_id=obj.id, language=language, section_code=code)
            .one_or_none()
        )
        row = existing or ObjectContentSection(
            object_id=obj.id, language=language, section_code=code
        )
        if existing is not None and existing.body != body:
            row.audio_key = None  # body 变更 → 旧音频失效，下次请求重生成
        row.body, row.status, row.source = body, "published", "ai_generated"
        row.model = model
        row.generated_at = datetime.now(timezone.utc)
        db.add(row)
```

- [ ] **Step 4: 跑测试确认通过**

Run: `poetry run pytest tests/integration/test_content_persist.py -v`
Expected: 全部 passed（含原 `test_persist_explanation` 与两条新用例）。

- [ ] **Step 5: 提交**

```bash
git add backend/app/services/content_repo.py backend/tests/integration/test_content_persist.py
git commit -m "feat(content): persist_explanation 在 body 变更时清空 audio_key"
```

---

## Task 3: `get_section_audio_key`（读侧复用查询）

**Files:**
- Modify: `backend/app/services/content_repo.py`
- Test: `backend/tests/integration/test_section_audio.py` (append)

- [ ] **Step 1: 写失败测试**

在 `backend/tests/integration/test_section_audio.py` 末尾追加：

```python
def test_get_section_audio_key_returns_key_after_persist(session):
    storage = FakeStorage()
    persist_section_audio(session, "Q1", "en", "overview", b"MP3", storage)
    assert (
        get_section_audio_key(session, "Q1", "en", "overview")
        == "object-audio/Q1/en/overview.mp3"
    )


def test_get_section_audio_key_none_when_absent(session):
    assert get_section_audio_key(session, "Q1", "en", "overview") is None
    assert get_section_audio_key(session, "Q404", "en", "overview") is None
```

- [ ] **Step 2: 跑测试确认失败**

Run: `poetry run pytest tests/integration/test_section_audio.py -k get_section_audio_key -v`
Expected: FAIL — `ImportError`/`AttributeError`（`get_section_audio_key` 不存在）。

- [ ] **Step 3: 实现 `get_section_audio_key`**

在 `backend/app/services/content_repo.py` 追加：

```python
def get_section_audio_key(
    db: Session, qid: str, language: str, section_code: str
) -> str | None:
    """返回该 section 已落库的 audio_key；对象不存在/无行/无音频均返回 None。"""
    obj = db.query(MuseumObject).filter_by(qid=qid).one_or_none()
    if not obj:
        return None
    row = (
        db.query(ObjectContentSection)
        .filter_by(object_id=obj.id, language=language, section_code=section_code)
        .one_or_none()
    )
    return row.audio_key if row else None
```

- [ ] **Step 4: 跑测试确认通过**

Run: `poetry run pytest tests/integration/test_section_audio.py -v`
Expected: 5 passed。

- [ ] **Step 5: 提交**

```bash
git add backend/app/services/content_repo.py backend/tests/integration/test_section_audio.py
git commit -m "feat(content): get_section_audio_key 读侧复用查询"
```

---

## Task 4: `/content/tts/generate` 双模端点

**Files:**
- Modify: `backend/app/api/v1/endpoints/content.py`
- Test: `backend/tests/integration/test_tts_endpoint.py` (create)

- [ ] **Step 1: 写失败测试**

创建 `backend/tests/integration/test_tts_endpoint.py`：

```python
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.api.v1.endpoints.content as content_ep
from app.core.database import Base
from app.main import app
from app.models.content import ObjectContentSection
from app.models.museum import Museum
from app.models.museum_object import MuseumObject, ObjectImage
from app.services.object_importer import upsert_museum, upsert_object
from app.services.tts_service import get_tts_service


class FakeStorage:
    def __init__(self):
        self.objects = {}

    def put(self, key, data, content_type):
        self.objects[key] = data

    def exists(self, key):
        return key in self.objects

    def public_url(self, key):
        return f"https://cdn.test/{key}"


class FakeTTS:
    def __init__(self):
        self.calls = 0

    async def generate_audio(self, text, language="en", voice=None, speed=1.0):
        self.calls += 1
        return {
            "audio_data": b"MP3BYTES",
            "content_type": "audio/mpeg",
            "duration_estimate": 1.0,
            "voice": "x",
            "language": language,
            "text_hash": "h",
            "size_bytes": 8,
        }


@pytest.fixture()
def ctx(monkeypatch):
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(
        bind=engine,
        tables=[
            Museum.__table__,
            MuseumObject.__table__,
            ObjectImage.__table__,
            ObjectContentSection.__table__,
        ],
    )
    Session = sessionmaker(bind=engine)
    s = Session()
    m = upsert_museum(s, {"slug": "orsay", "name_en": "Orsay"})
    upsert_object(
        s,
        m.id,
        {"qid": "Q1", "title_en": "A", "image": "http://x/a.jpg", "attributes": {}},
    )
    s.commit()
    s.close()

    storage = FakeStorage()
    fake_tts = FakeTTS()
    # 端点 section 模式用 SessionLocal()（非 Depends(get_db)），故直接替身工厂
    monkeypatch.setattr(content_ep, "SessionLocal", Session)
    monkeypatch.setattr(content_ep, "get_object_storage", lambda: storage)
    app.dependency_overrides[get_tts_service] = lambda: fake_tts
    client = TestClient(app)
    yield client, fake_tts, storage
    app.dependency_overrides.clear()


SECTION_BODY = {"text": "hello", "language": "en", "qid": "Q1", "section_code": "overview"}


def test_section_mode_generates_and_persists(ctx):
    client, fake_tts, storage = ctx
    r = client.post("/api/v1/content/tts/generate", json=SECTION_BODY)
    assert r.status_code == 200
    body = r.json()
    assert body["cached"] is False
    assert body["audio_url"] == "https://cdn.test/object-audio/Q1/en/overview.mp3"
    assert storage.exists("object-audio/Q1/en/overview.mp3")
    assert fake_tts.calls == 1


def test_section_mode_reuses_without_tts(ctx):
    client, fake_tts, storage = ctx
    client.post("/api/v1/content/tts/generate", json=SECTION_BODY)
    r2 = client.post("/api/v1/content/tts/generate", json=SECTION_BODY)
    assert r2.status_code == 200
    assert r2.json()["cached"] is True
    assert fake_tts.calls == 1  # 第二次未再调 TTS


def test_section_mode_unknown_qid_returns_404(ctx):
    client, fake_tts, storage = ctx
    r = client.post(
        "/api/v1/content/tts/generate",
        json={"text": "x", "language": "en", "qid": "Q404", "section_code": "overview"},
    )
    assert r.status_code == 404


def test_ad_hoc_mode_streams_audio(ctx):
    client, fake_tts, storage = ctx
    r = client.post(
        "/api/v1/content/tts/generate", json={"text": "hi", "language": "en"}
    )
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("audio/")
    assert r.content == b"MP3BYTES"
```

- [ ] **Step 2: 跑测试确认失败**

Run: `poetry run pytest tests/integration/test_tts_endpoint.py -v`
Expected: FAIL —— section 用例因端点尚未支持 `qid`/`section_code`（返回流而非 JSON）而失败；`content_ep.get_object_storage` 属性不存在导致 monkeypatch 报错。

- [ ] **Step 3: 实现双模端点**

3a. `backend/app/api/v1/endpoints/content.py` 顶部 import 区，把 content_repo import 扩成：

```python
from app.services.content_repo import (
    get_section_audio_key,
    persist_explanation,
    persist_section_audio,
)
```

并新增 storage import（放在其它 service import 旁）：

```python
from app.services.storage import get_object_storage
```

3b. 给 `TTSRequest` 加两个可选字段（在 `speed` 后）：

```python
    qid: Optional[str] = Field(
        None, description="Wikidata QID；与 section_code 同时提供时音频落库并返回 audio_url"
    )
    section_code: Optional[str] = Field(
        None, description="内容段落 code（如 overview）；section 模式必填"
    )
```

3c. 新增响应模型（放在 `TTSInfoResponse` 旁）：

```python
class AudioUrlResponse(BaseModel):
    """section 模式 TTS 响应：音频已落库，返回 R2 URL"""

    audio_url: str
    cached: bool
```

3d. 把 `generate_tts_audio` 的装饰器从 `@router.post("/tts/generate", response_class=StreamingResponse)` 改为：

```python
@router.post("/tts/generate")
```

3e. 在 `generate_tts_audio` 函数体最前面（`logger.info(...)` 之前）插入 section 分支：

```python
    # section 模式：qid + section_code 同时存在 → 落库 R2 + 返回 audio_url（懒写复用）
    if request.qid and request.section_code:
        db = SessionLocal()
        try:
            storage = get_object_storage()
            existing = get_section_audio_key(
                db, request.qid, request.language, request.section_code
            )
            if existing:
                return AudioUrlResponse(
                    audio_url=storage.public_url(existing), cached=True
                )
            result = await tts_service.generate_audio(
                text=request.text, language=request.language
            )
            key = persist_section_audio(
                db,
                request.qid,
                request.language,
                request.section_code,
                result["audio_data"],
                storage,
            )
            if key is None:
                raise HTTPException(
                    status_code=404,
                    detail={"error": "ObjectNotFound", "qid": request.qid},
                )
            return AudioUrlResponse(audio_url=storage.public_url(key), cached=False)
        finally:
            db.close()
```

> ad-hoc 模式（原有 `logger.info` + `tts_service.generate_audio` + `StreamingResponse` 整段）保持不动——FastAPI 见到返回的 `StreamingResponse` 对象会直接用它，不受去掉 `response_class` 影响。`SessionLocal` 已在文件顶部 import（讲解落库用）。

- [ ] **Step 4: 跑测试确认通过**

Run: `poetry run pytest tests/integration/test_tts_endpoint.py -v`
Expected: 4 passed。

- [ ] **Step 5: 跑后端相关测试确认无回归**

Run: `poetry run pytest tests/integration/test_section_audio.py tests/integration/test_content_persist.py tests/integration/test_tts_endpoint.py -v`
Expected: 全部 passed。

- [ ] **Step 6: 提交**

```bash
git add backend/app/api/v1/endpoints/content.py backend/tests/integration/test_tts_endpoint.py
git commit -m "feat(content): /tts/generate 双模——section 落库返回 audio_url，ad-hoc 保留流"
```

---

## Task 5: 前端 datasource section 模式解析 audio_url

**Files:**
- Modify: `frontend/gomuseum_app/lib/features/content/data/datasources/content_remote_datasource.dart`
- Test: `frontend/gomuseum_app/test/features/content/data/datasources/content_remote_datasource_test.dart` (create)

- [ ] **Step 1: 写失败测试**

创建 `frontend/gomuseum_app/test/features/content/data/datasources/content_remote_datasource_test.dart`：

```dart
import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:gomuseum_app/features/content/data/datasources/content_remote_datasource.dart';

class MockDio extends Mock implements Dio {}

void main() {
  late MockDio dio;
  late ContentRemoteDataSourceImpl ds;

  setUp(() {
    dio = MockDio();
    ds = ContentRemoteDataSourceImpl(dio: dio);
  });

  test('section 模式解析 JSON 的 audio_url', () async {
    when(() => dio.post(
          any(),
          data: any(named: 'data'),
          options: any(named: 'options'),
        )).thenAnswer((_) async => Response(
          data: {'audio_url': 'https://cdn.test/x.mp3', 'cached': false},
          statusCode: 200,
          requestOptions:
              RequestOptions(path: '/api/v1/content/tts/generate'),
        ));

    final url = await ds.generateTtsAudio(
      text: 't',
      language: 'en',
      qid: 'Q1',
      sectionCode: 'overview',
    );

    expect(url, 'https://cdn.test/x.mp3');
  });
}
```

- [ ] **Step 2: 跑测试确认失败**

Run（在 `frontend/gomuseum_app/`）: `flutter test test/features/content/data/datasources/content_remote_datasource_test.dart`
Expected: 编译失败 —— `generateTtsAudio` 不接受 `qid`/`sectionCode` 命名参数。

- [ ] **Step 3: 加参数到抽象接口**

`content_remote_datasource.dart` 的抽象方法（第 18-22 行附近）改为：

```dart
  Future<String> generateTtsAudio({
    required String text,
    required String language,
    String? voice,
    double? speed,
    String? qid,
    String? sectionCode,
  });
```

- [ ] **Step 4: 实现 section 分支**

在 `ContentRemoteDataSourceImpl.generateTtsAudio` 的实现里：4a. 把方法签名同样加上 `String? qid, String? sectionCode,`；4b. 在方法体 `try {` 之后、现有 `final requestData = {` 之前插入 section 分支：

```dart
      // section 模式：qid + sectionCode → 后端落库并返回 JSON audio_url
      if (qid != null && sectionCode != null) {
        final response = await dio.post(
          '/api/v1/content/tts/generate',
          data: {
            'text': text,
            'language': language,
            'qid': qid,
            'section_code': sectionCode,
          },
          options: Options(
            headers: {
              'Accept': 'application/json',
              'Content-Type': 'application/json',
            },
            sendTimeout: const Duration(seconds: 60),
            receiveTimeout: const Duration(seconds: 60),
          ),
        );
        if (response.statusCode == 200) {
          return (response.data as Map)['audio_url'] as String;
        }
        throw ServerException(
            'Server returned status code: ${response.statusCode}');
      }
```

> ad-hoc 路径（现有 `final requestData = {...}` 起的字节流逻辑）保持不动。`ServerException` 已在文件内使用，无需新增 import。

- [ ] **Step 5: 跑测试确认通过**

Run: `flutter test test/features/content/data/datasources/content_remote_datasource_test.dart`
Expected: 1 test passed。

- [ ] **Step 6: format + analyze**

Run: `dart format lib/features/content/data/datasources/content_remote_datasource.dart test/features/content/data/datasources/content_remote_datasource_test.dart`
Run: `flutter analyze lib/features/content/data/datasources/content_remote_datasource.dart`
Expected: No issues。

- [ ] **Step 7: 提交**

```bash
git add frontend/gomuseum_app/lib/features/content/data/datasources/content_remote_datasource.dart frontend/gomuseum_app/test/features/content/data/datasources/content_remote_datasource_test.dart
git commit -m "feat(content): 前端 TTS datasource 支持 section 模式解析 audio_url"
```

---

## 收尾：整体验证

- [ ] **后端全量内容相关测试**

Run（`backend/`）: `poetry run pytest tests/integration/test_section_audio.py tests/integration/test_content_persist.py tests/integration/test_tts_endpoint.py tests/integration/test_object_content_endpoint.py -v`
Expected: 全部 passed（含既有 object_content 端点无回归）。

- [ ] **前端 content 测试**

Run（`frontend/gomuseum_app/`）: `flutter test test/features/content/`
Expected: passed。

- [ ] **提 PR**：`feature/tts-audio-persistence → staging`（用 `/pr`）。CI 绿后 squash 合并，按 path-aware 自动部署 staging；staging→main PR 合并后自动部署 prod。

---

## Self-Review（计划对照 spec）

- **spec §4 组件**：`persist_section_audio`(T1)、`persist_explanation` 失效(T2)、`get_section_audio_key`(T3)、端点双模(T4)、`museum_repo` 不动 ✓。
- **spec §5 决策**：key 方案 `object-audio/{qid}/{language}/{section_code}.mp3`(T1 实现+断言)、规范化单 voice（端点只传 `text`+`language`，不透传 voice/speed，T4 3e）、上传失败不写 key(T1 BoomStorage 用例) ✓。
- **spec §6 数据流 / §7 契约**：section→`{audio_url,cached}` JSON、ad-hoc→流(T4 四用例覆盖) ✓。
- **spec §8 错误**：未知 qid→404(T4)、上传失败不写 key(T1) ✓。
- **spec §9 前端**：section 模式解析 audio_url(T5) ✓。
- **spec §10 测试**：后端复用/生成/上传失败/upsert/失效/端点四模、前端解析——均有对应任务 ✓。
- **类型一致**：`persist_section_audio(db,qid,language,section_code,audio_bytes,storage)->str|None`、`get_section_audio_key(db,qid,language,section_code)->str|None`、`AudioUrlResponse{audio_url,cached}`、前端 `generateTtsAudio({...,qid,sectionCode})` 在各任务间一致 ✓。
