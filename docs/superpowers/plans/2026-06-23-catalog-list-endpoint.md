# 藏品分页列表端点 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 新增 `GET /museums/{slug}/objects` 分页藏品列表端点，让前端 A2/A3 馆藏列表页（无限滚动 + 分类 tab）能加载（现因端点缺失 404 → "加载失败"）。

**Architecture:** 新增 `museum_repo.list_objects(db, slug, *, language, category, sort, limit, offset)` 产分页响应，端点薄封装。响应严格对齐前端已定契约。纯加法，不动既有 `get_museum_pack`/`get_object_content`，无迁移。

**Tech Stack:** FastAPI + SQLAlchemy + pytest（sqlite 集成）。

**前端确切契约（来自 UI 分支 `object_list_model.dart`，不可改）：**
- 请求：`GET /api/v1/museums/{slug}/objects?category=&sort=popularity&limit=50&offset=0&language=zh`
  （前端只在 `category != 'all'` 时带 category；sort 固定 "popularity"；language 由 languageProvider 传，缺省按端点默认）
- 响应：`{"items": [...], "total": int, "limit": int, "offset": int}`
- item：`{"qid", "title", "artist", "year", "thumbnail", "content_status"}`
  （前端防御解析：title 缺→"未命名"，content_status 缺/未知→ready；故端点须**真给 content_status**，stub 角标才生效）
- `title`/`artist` 按 **language** 选语种：zh→title_zh 回退 en 回退 qid；en/fr→对应语种回退。

---

## File Structure

- **Modify** `backend/app/services/museum_repo.py` — 加 `list_objects(...)`（分页查询 + 按 language 选标题/作者 + content_status + thumbnail）。
- **Modify** `backend/app/api/v1/endpoints/museums.py` — 加 `GET /{slug}/objects` 路由。

测试：
- **Create** `backend/tests/integration/test_list_objects.py`（repo 层分页/过滤/语言/字段）
- **Create** `backend/tests/integration/test_objects_endpoint.py`（HTTP 层参数透传 + 404）

---

### Task 1: museum_repo.list_objects 分页查询

**Files:**
- Modify: `backend/app/services/museum_repo.py`
- Test: `backend/tests/integration/test_list_objects.py`

参考既有：`get_museum_pack`（同文件）已有 `_resolve_image(obj_id, fallback_src)` + 批量主图加载 + storage 模式；`Museum`/`MuseumObject`/`ObjectImage` 已 import。`MuseumObject` 有 `qid/title_zh/title_en/artist_zh/artist_en/year/category/popularity/content_status`。

- [ ] **Step 1: 写失败测试**

Create `backend/tests/integration/test_list_objects.py`：

```python
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.models.museum import Museum
from app.models.museum_object import MuseumObject, ObjectImage
from app.services.museum_repo import list_objects
from app.services.object_importer import upsert_museum, upsert_object


@pytest.fixture()
def session():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(
        bind=engine,
        tables=[Museum.__table__, MuseumObject.__table__, ObjectImage.__table__],
    )
    s = sessionmaker(bind=engine)()
    m = upsert_museum(s, {"slug": "orsay", "name_en": "Orsay"})
    # 3 paintings + 1 sculpture，含中英文与缺字段
    upsert_object(s, m.id, {"qid": "Q1", "title_zh": "世界的起源", "title_en": "Origin",
                            "artist_zh": "库尔贝", "artist_en": "Courbet", "year": "1866",
                            "category": "painting", "popularity": 50, "image": "http://i/1.jpg"})
    upsert_object(s, m.id, {"qid": "Q2", "title_en": "Olympia", "artist_en": "Manet",
                            "category": "painting", "popularity": 40})
    upsert_object(s, m.id, {"qid": "Q3", "title_en": "Low", "category": "painting", "popularity": 10})
    upsert_object(s, m.id, {"qid": "Q4", "title_en": "Statue", "category": "sculpture", "popularity": 30})
    # content_status：Q1 ready，其余默认 stub
    s.query(MuseumObject).filter_by(qid="Q1").one().content_status = "ready"
    s.commit()
    yield s


def test_list_objects_paginates_by_popularity_desc(session):
    page = list_objects(session, "orsay", language="zh", limit=2, offset=0)
    assert page["total"] == 4 and page["limit"] == 2 and page["offset"] == 0
    assert [i["qid"] for i in page["items"]] == ["Q1", "Q4"]  # pop 50,30
    page2 = list_objects(session, "orsay", language="zh", limit=2, offset=2)
    assert [i["qid"] for i in page2["items"]] == ["Q2", "Q3"]  # pop 40,10


def test_list_objects_filters_by_category(session):
    page = list_objects(session, "orsay", language="zh", category="sculpture")
    assert page["total"] == 1 and [i["qid"] for i in page["items"]] == ["Q4"]


def test_list_objects_zh_titles_with_fallback(session):
    items = {i["qid"]: i for i in list_objects(session, "orsay", language="zh")["items"]}
    assert items["Q1"]["title"] == "世界的起源" and items["Q1"]["artist"] == "库尔贝"
    assert items["Q2"]["title"] == "Olympia"  # 无 zh → 回退 en
    assert items["Q2"]["artist"] == "Manet"


def test_list_objects_en_titles(session):
    items = {i["qid"]: i for i in list_objects(session, "orsay", language="en")["items"]}
    assert items["Q1"]["title"] == "Origin" and items["Q1"]["artist"] == "Courbet"


def test_list_objects_item_shape(session):
    i = list_objects(session, "orsay", language="zh", limit=1)["items"][0]
    assert set(i.keys()) == {"qid", "title", "artist", "year", "thumbnail", "content_status"}
    assert i["qid"] == "Q1" and i["content_status"] == "ready"
    assert i["thumbnail"] == "https://i/1.jpg"  # http→https（upsert_object 已转）


def test_list_objects_unknown_museum(session):
    assert list_objects(session, "nope", language="zh") is None
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && python -m pytest tests/integration/test_list_objects.py -q`
Expected: FAIL（`cannot import name 'list_objects'`）

- [ ] **Step 3: 实现 list_objects**

在 `museum_repo.py` 末尾追加（复用文件内已 import 的 `Museum/MuseumObject/ObjectImage/get_object_storage`）：

```python
def list_objects(
    db: Session,
    slug: str,
    *,
    language: str = "zh",
    category: str | None = None,
    sort: str = "popularity",
    limit: int = 50,
    offset: int = 0,
) -> dict | None:
    """分页藏品列表（供 A2/A3 列表页）。未知馆→None。纯元数据 + content_status。"""
    m = db.query(Museum).filter_by(slug=slug).one_or_none()
    if not m:
        return None
    q = db.query(MuseumObject).filter_by(museum_id=m.id)
    if category and category != "all":
        q = q.filter(MuseumObject.category == category)
    total = q.count()
    q = q.order_by(MuseumObject.popularity.desc())
    objs = q.limit(limit).offset(offset).all()

    obj_ids = [o.id for o in objs]
    images_by_obj: dict = {}
    if obj_ids:
        for img in (
            db.query(ObjectImage)
            .filter(ObjectImage.object_id.in_(obj_ids), ObjectImage.role == "primary")
            .all()
        ):
            images_by_obj[img.object_id] = img
    storage = get_object_storage()

    def _thumb(obj_id):
        img = images_by_obj.get(obj_id)
        if img and img.image_key:
            return storage.public_url(img.image_key)
        return img.source_url if img else None

    def _title(o):
        if language == "zh":
            return o.title_zh or o.title_en or o.qid
        if language == "fr":
            return (o.attributes or {}).get("title_fr") or o.title_en or o.qid
        return o.title_en or o.title_zh or o.qid

    def _artist(o):
        if language == "zh":
            return o.artist_zh or o.artist_en or ""
        if language == "fr":
            return (o.attributes or {}).get("artist_fr") or o.artist_en or ""
        return o.artist_en or o.artist_zh or ""

    items = [
        {
            "qid": o.qid,
            "title": _title(o),
            "artist": _artist(o),
            "year": o.year,
            "thumbnail": _thumb(o.id),
            "content_status": o.content_status,
        }
        for o in objs
    ]
    return {"items": items, "total": total, "limit": limit, "offset": offset}
```

- [ ] **Step 4: 运行确认通过**

Run: `cd backend && python -m pytest tests/integration/test_list_objects.py -q`
Expected: PASS（6 用例）

- [ ] **Step 5: 提交**

```bash
cd backend && git add app/services/museum_repo.py tests/integration/test_list_objects.py
git commit -m "feat(catalog): museum_repo.list_objects 分页藏品列表"
```

---

### Task 2: GET /{slug}/objects 端点

**Files:**
- Modify: `backend/app/api/v1/endpoints/museums.py`
- Test: `backend/tests/integration/test_objects_endpoint.py`

参考既有：`museums.py` 已有 `get_db`、`object_content` 路由模式（路径参数 + query 参数 + 404）。

- [ ] **Step 1: 写失败测试**

Create `backend/tests/integration/test_objects_endpoint.py`：

```python
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.v1.endpoints import museums
from app.core.database import Base, get_db
from app.models.museum import Museum
from app.models.museum_object import MuseumObject, ObjectImage
from app.services.object_importer import upsert_museum, upsert_object


@pytest.fixture()
def client():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(
        bind=engine,
        tables=[Museum.__table__, MuseumObject.__table__, ObjectImage.__table__],
    )
    TestingSession = sessionmaker(bind=engine)
    s = TestingSession()
    m = upsert_museum(s, {"slug": "orsay", "name_en": "Orsay"})
    upsert_object(s, m.id, {"qid": "Q1", "title_en": "A", "category": "painting", "popularity": 9})
    s.commit()
    s.close()

    app = FastAPI()
    app.include_router(museums.router, prefix="/museums")
    app.dependency_overrides[get_db] = lambda: TestingSession()
    return TestClient(app)


def test_objects_endpoint_returns_page(client):
    r = client.get("/museums/orsay/objects", params={"limit": 10, "offset": 0})
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 1 and body["limit"] == 10
    assert body["items"][0]["qid"] == "Q1"
    assert "content_status" in body["items"][0]


def test_objects_endpoint_unknown_museum_404(client):
    assert client.get("/museums/nope/objects").status_code == 404
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && python -m pytest tests/integration/test_objects_endpoint.py -q`
Expected: FAIL（404 路由不存在 → 第一个用例拿到 404）

> 注：本地 venv 有 `python_multipart` 弃用导致部分 TestClient 收集报错（预存在，与本改动无关）。若本测试文件因该问题无法收集，记录现象但以 CI 全新依赖为准；可临时 `pip install -U python-multipart` 本地验证。

- [ ] **Step 3: 加端点**

在 `museums.py` 的 `object_content` 路由**之前**（即 `/{slug}` catch-all 之前，避免路由吞掉）加：

```python
@router.get("/{slug}/objects")
def list_objects(
    slug: str,
    language: str = "zh",
    category: str | None = None,
    sort: str = "popularity",
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
) -> dict:
    """分页藏品列表（A2/A3 列表页）"""
    page = repo_list_objects(
        db, slug, language=language, category=category, sort=sort,
        limit=limit, offset=offset,
    )
    if page is None:
        raise HTTPException(status_code=404, detail=f"museum not found: {slug}")
    return page
```

并在文件顶部 import 区加：

```python
from app.services.museum_repo import list_objects as repo_list_objects
```

（注意：端点函数名 `list_objects` 与既有 `@router.get("")` 的 `list_museums` 不冲突；但避免与 import 名撞，故 import 用别名 `repo_list_objects`。）

- [ ] **Step 4: 运行确认通过**

Run: `cd backend && python -m pytest tests/integration/test_objects_endpoint.py -q`
Expected: PASS

- [ ] **Step 5: 全量回归 + 提交**

Run: `cd backend && python -m pytest tests/integration/test_list_objects.py tests/integration/test_objects_endpoint.py tests/integration/test_generate_pipeline.py tests/unit/services/enrichment/ -q`
Expected: PASS（无回归）

```bash
cd backend && git add app/api/v1/endpoints/museums.py tests/integration/test_objects_endpoint.py
git commit -m "feat(catalog): GET /museums/{slug}/objects 分页列表端点"
```

---

## Self-Review

- **契约对齐**：响应 `{items,total,limit,offset}` + item `{qid,title,artist,year,thumbnail,content_status}` 严格匹配前端 `ObjectListPage`/`ObjectListItem.fromJson`（Task 1 用例锁字段集）。
- **content_status 真给**：item 直读 `o.content_status`（解决 pack 里全 null 的问题），stub 角标生效。
- **language 选语种**：zh/en/fr 各自回退链（Task 1 用例覆盖 zh 回退 + en）。
- **路由顺序**：`/{slug}/objects` 必须在 `/{slug}` 之前注册，否则被 catch-all 吞（Step 3 明确位置）。
- **前向兼容**：纯加法新端点，不动 `get_museum_pack`/`get_object_content`/`list_museums`，无迁移。
- **YAGNI**：sort 仅 popularity（前端固定传它）；不实现多 sort、不做游标分页（offset 够用）。

## 验证（合 staging 后）

1. `curl 'http://127.0.0.1:8101/api/v1/museums/orsay/objects?limit=5&language=zh'` → 200，items 有 content_status、中文标题。
2. 前端切到此分支对应后端，点奥赛馆 → 列表加载、stub 角标显示、无限滚动翻页。
3. category tab 过滤（painting/sculpture）正确。
