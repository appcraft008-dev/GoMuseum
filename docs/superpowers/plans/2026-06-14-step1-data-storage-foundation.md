# 第 1 步：数据与存储地基 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把馆藏目录/讲解/音频从「JSON 文件 + 仅 Redis + 本地磁盘」迁到「PostgreSQL 唯一真相源 + R2 对象存储 + Redis 仅缓存」，并把数据模型泛化成通用展品。

**Architecture:** SQLAlchemy ORM（沿用 `app/core/database.py` 的 `Base`）建 6 张表；一个 `ObjectStorage` 抽象（local/r2 双实现，工厂按 `STORAGE_BACKEND` 切换）；`build_museum_pack.py` 升级为 Wikidata→DB 导入器；一次性脚本把现有 `orsay.json` 与 Redis 讲解灌库；`museums.py`/`content.py` 改读 DB 但**保持返回 JSON 形状不变**。

**Tech Stack:** FastAPI · SQLAlchemy · Alembic · PostgreSQL · Redis · boto3(S3/R2) · pytest（SQLite 内存库做单测，沿用 `tests/integration` 模式）。

**关键基线（实现前必读）：**
- 模型基类：`from app.core.database import Base`；会话 `SessionLocal` / 依赖 `get_db`（`app/core/database.py`）。
- 模型范式见 `app/models/recognition_result.py`：UUID 主键 `Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)`，含 `to_dict()`。
- 新模型必须：①加到 `app/models/__init__.py`；②在 `alembic/env.py` import 以注册 metadata。
- **SQLite 兼容**（单测用）：JSON 字段用 `JSON().with_variant(JSONB, "postgresql")`；时间默认用 `server_default=func.now()`（建表时只建本用例相关表，参考 `tests/integration/test_account_deletion.py`）。
- 设置类在 `app/core/config.py`（pydantic Settings）；DB URL 由 `settings.get_database_url()` 提供。
- R2 已联通：`.env` 含 `STORAGE_BACKEND/R2_ENDPOINT_URL/R2_ACCESS_KEY_ID/R2_SECRET_ACCESS_KEY/R2_BUCKET/R2_PUBLIC_BASE_URL`，桶 `gomuseum-assets`。

**章节词表对齐（基于现有数据，保证迁移无损）：**
现有 Redis 讲解 payload 字段 → section_code 映射：
`summary→overview`、`historical_context→background`、`artistic_analysis→analysis`、`cultural_significance→significance`、`interesting_facts→facts`（list 存为 JSON 文本）。另预留 `artist`（作者介绍，暂无内容）。

---

## 文件结构

| 文件 | 职责 |
|---|---|
| `app/core/config.py`(改) | 新增 storage / R2 设置字段 |
| `app/services/storage/base.py`(建) | `ObjectStorage` 抽象接口 |
| `app/services/storage/local.py`(建) | 本地文件实现 |
| `app/services/storage/r2.py`(建) | R2(boto3) 实现 |
| `app/services/storage/__init__.py`(建) | `get_object_storage()` 工厂（单例） |
| `app/models/museum.py`(建) | `Museum` |
| `app/models/museum_object.py`(建) | `MuseumObject` + `ObjectImage` |
| `app/models/content.py`(建) | `SectionType` + `CategorySection` + `ObjectContentSection` |
| `app/models/__init__.py`(改) | 导出新模型 |
| `alembic/env.py`(改) | import 新模型注册 metadata |
| `alembic/versions/xxxx_step1_foundation.py`(生成) | 建表迁移 |
| `app/services/museum_repo.py`(建) | 读 DB 拼回 pack JSON 形状的序列化器 |
| `scripts/build_museum_pack.py`(改) | Wikidata→DB 导入器（含 P217 等硬事实） |
| `scripts/migrate_pack_to_db.py`(建) | 现有 orsay.json → DB |
| `scripts/migrate_redis_explanations.py`(建) | Redis 讲解 → object_content_section |
| `app/api/v1/endpoints/museums.py`(改) | 改读 DB，返回形状不变 |
| `app/api/v1/endpoints/content.py`(改) | 讲解读 DB→未命中生成→落库+缓存 |
| `tests/unit/storage/`、`tests/unit/models/`、`tests/integration/`(建) | 各层测试 |

---

## Phase 0 · 设置与依赖

### Task 0.1: 新增 storage/R2 设置字段

**Files:**
- Modify: `app/core/config.py`
- Modify: `pyproject.toml`（依赖区加 `boto3`）

- [ ] **Step 1: 在 `Settings` 类中加字段**（紧跟现有 AI 字段后，照搬现有字段写法）

```python
    # Object storage (images / audio)
    STORAGE_BACKEND: str = "local"            # "local" | "r2"
    STORAGE_LOCAL_DIR: str = "var/assets"     # local 实现落盘目录
    STORAGE_PUBLIC_BASE_URL: str = "http://localhost:8000/assets"  # local public_url 前缀
    R2_ENDPOINT_URL: str = ""
    R2_ACCESS_KEY_ID: str = ""
    R2_SECRET_ACCESS_KEY: str = ""
    R2_BUCKET: str = "gomuseum-assets"
    R2_PUBLIC_BASE_URL: str = ""
```

- [ ] **Step 2: 在 `pyproject.toml` 运行依赖里加 `boto3`**

在 `dependencies = [...]` 中加一行：`"boto3>=1.34.0",`

- [ ] **Step 3: 验证设置加载**

Run: `cd backend && .venv/bin/python -c "from app.core.config import settings; print(settings.STORAGE_BACKEND, settings.R2_BUCKET)"`
Expected: 输出 `local gomuseum-assets`

- [ ] **Step 4: Commit**

```bash
git add backend/app/core/config.py backend/pyproject.toml
git commit -m "feat(config): add object storage / R2 settings"
```

---

## Phase 1 · 存储抽象

### Task 1.1: `ObjectStorage` 抽象接口

**Files:**
- Create: `app/services/storage/__init__.py`（暂空，工厂在 Task 1.4 补）
- Create: `app/services/storage/base.py`
- Test: `tests/unit/storage/test_local_storage.py`（Task 1.2 写）

- [ ] **Step 1: 写接口**

```python
# app/services/storage/base.py
"""对象存储统一抽象：图片/音频。实现见 local.py（本地）、r2.py（Cloudflare R2）。"""
from abc import ABC, abstractmethod
from typing import Optional


class ObjectStorage(ABC):
    @abstractmethod
    def put(self, key: str, data: bytes, content_type: str) -> None:
        """写入对象。key 形如 'images/Q12418/primary.jpg'。"""

    @abstractmethod
    def get(self, key: str) -> Optional[bytes]:
        """读取对象；不存在返回 None。"""

    @abstractmethod
    def exists(self, key: str) -> bool:
        ...

    @abstractmethod
    def delete(self, key: str) -> None:
        ...

    @abstractmethod
    def public_url(self, key: str) -> str:
        """返回可直接给客户端展示的 URL。"""
```

- [ ] **Step 2: 建包占位**

`app/services/storage/__init__.py` 内容暂为：`from app.services.storage.base import ObjectStorage  # noqa: F401`

- [ ] **Step 3: 验证可导入**

Run: `cd backend && .venv/bin/python -c "from app.services.storage import ObjectStorage; print('ok')"`
Expected: `ok`

- [ ] **Step 4: Commit**

```bash
git add backend/app/services/storage/base.py backend/app/services/storage/__init__.py
git commit -m "feat(storage): add ObjectStorage abstract interface"
```

### Task 1.2: `LocalObjectStorage` 实现（TDD）

**Files:**
- Create: `app/services/storage/local.py`
- Test: `tests/unit/storage/test_local_storage.py`
- Create: `tests/unit/storage/__init__.py`（空）

- [ ] **Step 1: 写失败测试**

```python
# tests/unit/storage/test_local_storage.py
from app.services.storage.local import LocalObjectStorage


def test_put_get_exists_delete_and_url(tmp_path):
    s = LocalObjectStorage(root_dir=str(tmp_path), public_base_url="http://x/assets")
    key = "images/Q1/primary.jpg"
    assert s.exists(key) is False
    assert s.get(key) is None

    s.put(key, b"hello", "image/jpeg")
    assert s.exists(key) is True
    assert s.get(key) == b"hello"
    assert s.public_url(key) == "http://x/assets/images/Q1/primary.jpg"

    s.delete(key)
    assert s.exists(key) is False
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && .venv/bin/python -m pytest tests/unit/storage/test_local_storage.py -v`
Expected: FAIL（`ModuleNotFoundError: app.services.storage.local`）

- [ ] **Step 3: 写实现**

```python
# app/services/storage/local.py
"""本地文件实现：落盘到 root_dir/key，public_url 走后端静态前缀。"""
from pathlib import Path
from typing import Optional
from app.services.storage.base import ObjectStorage


class LocalObjectStorage(ObjectStorage):
    def __init__(self, root_dir: str, public_base_url: str):
        self._root = Path(root_dir)
        self._base = public_base_url.rstrip("/")

    def _path(self, key: str) -> Path:
        return self._root / key

    def put(self, key: str, data: bytes, content_type: str) -> None:
        p = self._path(key)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)

    def get(self, key: str) -> Optional[bytes]:
        p = self._path(key)
        return p.read_bytes() if p.exists() else None

    def exists(self, key: str) -> bool:
        return self._path(key).exists()

    def delete(self, key: str) -> None:
        p = self._path(key)
        if p.exists():
            p.unlink()

    def public_url(self, key: str) -> str:
        return f"{self._base}/{key}"
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd backend && .venv/bin/python -m pytest tests/unit/storage/test_local_storage.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/storage/local.py backend/tests/unit/storage/
git commit -m "feat(storage): add LocalObjectStorage with tests"
```

### Task 1.3: `R2ObjectStorage` 实现

**Files:**
- Create: `app/services/storage/r2.py`
- Test: `tests/unit/storage/test_r2_storage.py`（仅在配置了凭证时跑真连，否则跳过）

- [ ] **Step 1: 写实现**

```python
# app/services/storage/r2.py
"""Cloudflare R2（S3 兼容）实现。public_url 走 R2_PUBLIC_BASE_URL。"""
from typing import Optional
import boto3
from botocore.config import Config
from botocore.exceptions import ClientError
from app.services.storage.base import ObjectStorage


class R2ObjectStorage(ObjectStorage):
    def __init__(self, endpoint_url: str, access_key_id: str, secret_access_key: str,
                 bucket: str, public_base_url: str):
        self._bucket = bucket
        self._base = public_base_url.rstrip("/")
        self._s3 = boto3.client(
            "s3", endpoint_url=endpoint_url,
            aws_access_key_id=access_key_id, aws_secret_access_key=secret_access_key,
            region_name="auto", config=Config(signature_version="s3v4"),
        )

    def put(self, key: str, data: bytes, content_type: str) -> None:
        self._s3.put_object(Bucket=self._bucket, Key=key, Body=data, ContentType=content_type)

    def get(self, key: str) -> Optional[bytes]:
        try:
            return self._s3.get_object(Bucket=self._bucket, Key=key)["Body"].read()
        except ClientError as e:
            if e.response["Error"]["Code"] in ("NoSuchKey", "404"):
                return None
            raise

    def exists(self, key: str) -> bool:
        try:
            self._s3.head_object(Bucket=self._bucket, Key=key)
            return True
        except ClientError:
            return False

    def delete(self, key: str) -> None:
        self._s3.delete_object(Bucket=self._bucket, Key=key)

    def public_url(self, key: str) -> str:
        return f"{self._base}/{key}"
```

- [ ] **Step 2: 写测试（无凭证则跳过）**

```python
# tests/unit/storage/test_r2_storage.py
import os
import uuid
import pytest
from app.core.config import settings


@pytest.mark.skipif(not settings.R2_ACCESS_KEY_ID, reason="R2 凭证未配置")
def test_r2_roundtrip():
    from app.services.storage.r2 import R2ObjectStorage
    s = R2ObjectStorage(
        settings.R2_ENDPOINT_URL, settings.R2_ACCESS_KEY_ID,
        settings.R2_SECRET_ACCESS_KEY, settings.R2_BUCKET, settings.R2_PUBLIC_BASE_URL,
    )
    key = f"diagnostics/test_{uuid.uuid4().hex}.txt"
    assert s.exists(key) is False
    s.put(key, b"r2 ok", "text/plain")
    assert s.get(key) == b"r2 ok"
    assert s.exists(key) is True
    s.delete(key)
    assert s.exists(key) is False
```

- [ ] **Step 3: 跑测试（本地 .env 有凭证 → 真连；CI 无凭证 → skip）**

Run: `cd backend && set -a && . .env && set +a && .venv/bin/python -m pytest tests/unit/storage/test_r2_storage.py -v`
Expected: PASS（或 SKIPPED）

- [ ] **Step 4: Commit**

```bash
git add backend/app/services/storage/r2.py backend/tests/unit/storage/test_r2_storage.py
git commit -m "feat(storage): add R2ObjectStorage with live-credential test"
```

### Task 1.4: 工厂 `get_object_storage()`

**Files:**
- Modify: `app/services/storage/__init__.py`
- Test: `tests/unit/storage/test_factory.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/unit/storage/test_factory.py
import app.services.storage as storage_mod
from app.services.storage.local import LocalObjectStorage


def test_factory_returns_local_singleton(monkeypatch):
    storage_mod._instance = None  # 重置单例
    monkeypatch.setattr("app.services.storage.settings.STORAGE_BACKEND", "local", raising=False)
    s1 = storage_mod.get_object_storage()
    s2 = storage_mod.get_object_storage()
    assert isinstance(s1, LocalObjectStorage)
    assert s1 is s2
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && .venv/bin/python -m pytest tests/unit/storage/test_factory.py -v`
Expected: FAIL（`get_object_storage` 不存在）

- [ ] **Step 3: 写工厂**

```python
# app/services/storage/__init__.py
"""存储工厂：按 settings.STORAGE_BACKEND 返回单例 ObjectStorage。"""
from app.services.storage.base import ObjectStorage  # noqa: F401
from app.core.config import settings

_instance: ObjectStorage | None = None


def get_object_storage() -> ObjectStorage:
    global _instance
    if _instance is None:
        if settings.STORAGE_BACKEND == "r2":
            from app.services.storage.r2 import R2ObjectStorage
            _instance = R2ObjectStorage(
                settings.R2_ENDPOINT_URL, settings.R2_ACCESS_KEY_ID,
                settings.R2_SECRET_ACCESS_KEY, settings.R2_BUCKET, settings.R2_PUBLIC_BASE_URL,
            )
        else:
            from app.services.storage.local import LocalObjectStorage
            _instance = LocalObjectStorage(
                settings.STORAGE_LOCAL_DIR, settings.STORAGE_PUBLIC_BASE_URL,
            )
    return _instance
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd backend && .venv/bin/python -m pytest tests/unit/storage/ -v`
Expected: PASS（local/factory 通过，r2 PASS 或 SKIP）

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/storage/__init__.py backend/tests/unit/storage/test_factory.py
git commit -m "feat(storage): add get_object_storage factory"
```

---

## Phase 2 · 数据模型与迁移

### Task 2.1: `Museum` 模型

**Files:**
- Create: `app/models/museum.py`
- Test: `tests/unit/models/test_museum_models.py`（Task 2.4 统一测）

- [ ] **Step 1: 写模型**

```python
# app/models/museum.py
"""博物馆实体。"""
import uuid
from sqlalchemy import Column, String, DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from app.core.database import Base


class Museum(Base):
    __tablename__ = "museums"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    slug = Column(String(64), unique=True, index=True, nullable=False)
    qid = Column(String(32), nullable=True)
    name_zh = Column(String(255))
    name_en = Column(String(255))
    city_zh = Column(String(128))
    city_en = Column(String(128))
    country = Column(String(8))
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)
```

- [ ] **Step 2: 验证导入**

Run: `cd backend && .venv/bin/python -c "from app.models.museum import Museum; print(Museum.__tablename__)"`
Expected: `museums`

- [ ] **Step 3: Commit**

```bash
git add backend/app/models/museum.py
git commit -m "feat(models): add Museum"
```

### Task 2.2: `MuseumObject` + `ObjectImage` 模型

**Files:**
- Create: `app/models/museum_object.py`

- [ ] **Step 1: 写模型**

```python
# app/models/museum_object.py
"""通用展品（MuseumObject）+ 展品图片（ObjectImage，一对多）。"""
import uuid
from sqlalchemy import (
    Column, String, Integer, Text, DateTime, ForeignKey, UniqueConstraint, func, JSON,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from app.core.database import Base


class MuseumObject(Base):
    __tablename__ = "museum_objects"
    __table_args__ = (
        UniqueConstraint("museum_id", "inventory_number", name="uq_object_museum_inventory"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    museum_id = Column(UUID(as_uuid=True), ForeignKey("museums.id"), nullable=False, index=True)
    qid = Column(String(32), unique=True, nullable=True, index=True)   # Wikidata QID
    inventory_number = Column(String(128), nullable=True)              # 馆藏号
    category = Column(String(32), nullable=False, default="painting")
    title_zh = Column(String(512))
    title_en = Column(String(512))
    artist_zh = Column(String(255))
    artist_en = Column(String(255))
    year = Column(String(64))
    period_zh = Column(String(128))
    period_en = Column(String(128))
    popularity = Column(Integer, default=0, index=True)
    attributes = Column(JSON().with_variant(JSONB, "postgresql"), default=dict)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)


class ObjectImage(Base):
    __tablename__ = "object_images"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    object_id = Column(UUID(as_uuid=True), ForeignKey("museum_objects.id"), nullable=False, index=True)
    role = Column(String(32), default="primary")   # primary | detail | view | back
    source_url = Column(Text)
    image_key = Column(Text, nullable=True)         # R2 自存副本 key
    license = Column(String(128), nullable=True)
    credit = Column(String(255), nullable=True)
    sort = Column(Integer, default=0)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)
```

- [ ] **Step 2: 验证导入**

Run: `cd backend && .venv/bin/python -c "from app.models.museum_object import MuseumObject, ObjectImage; print(MuseumObject.__tablename__, ObjectImage.__tablename__)"`
Expected: `museum_objects object_images`

- [ ] **Step 3: Commit**

```bash
git add backend/app/models/museum_object.py
git commit -m "feat(models): add MuseumObject and ObjectImage"
```

### Task 2.3: 内容三表模型

**Files:**
- Create: `app/models/content.py`

- [ ] **Step 1: 写模型**

```python
# app/models/content.py
"""讲解内容：SectionType（tab 词表）+ CategorySection（类→tab 映射）+ ObjectContentSection（实际内容）。"""
import uuid
from sqlalchemy import (
    Column, String, Integer, Text, DateTime, ForeignKey, UniqueConstraint, func,
)
from sqlalchemy.dialects.postgresql import UUID
from app.core.database import Base


class SectionType(Base):
    __tablename__ = "section_types"

    code = Column(String(32), primary_key=True)     # overview | artist | background | analysis | significance | facts
    label_zh = Column(String(64))
    label_en = Column(String(64))
    icon = Column(String(64), nullable=True)
    default_sort = Column(Integer, default=0)


class CategorySection(Base):
    __tablename__ = "category_sections"

    category = Column(String(32), primary_key=True)
    section_code = Column(String(32), ForeignKey("section_types.code"), primary_key=True)
    sort_order = Column(Integer, default=0)


class ObjectContentSection(Base):
    __tablename__ = "object_content_sections"
    __table_args__ = (
        UniqueConstraint("object_id", "language", "section_code", name="uq_content_obj_lang_section"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    object_id = Column(UUID(as_uuid=True), ForeignKey("museum_objects.id"), nullable=False, index=True)
    language = Column(String(8), nullable=False)
    section_code = Column(String(32), ForeignKey("section_types.code"), nullable=False)
    body = Column(Text)
    audio_key = Column(Text, nullable=True)
    status = Column(String(16), default="published")   # draft | published | needs_review
    model = Column(String(64), nullable=True)
    source = Column(String(32), default="ai_generated")  # ai_generated | manual
    generated_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)
```

- [ ] **Step 2: 注册到 `app/models/__init__.py`**

在文件末尾追加 import 与 `__all__`：

```python
from app.models.museum import Museum
from app.models.museum_object import MuseumObject, ObjectImage
from app.models.content import SectionType, CategorySection, ObjectContentSection

__all__ += ["Museum", "MuseumObject", "ObjectImage",
            "SectionType", "CategorySection", "ObjectContentSection"]
```

- [ ] **Step 3: 在 `alembic/env.py` 注册模型**（在现有 `from app.models import recognition_result` 行后加）

```python
from app.models import museum, museum_object, content  # noqa: F401  Step1 模型
```

- [ ] **Step 4: 验证全部模型可注册**

Run: `cd backend && .venv/bin/python -c "import app.models; from app.core.database import Base; print(sorted(Base.metadata.tables)[:8])"`
Expected: 输出含 `museums, museum_objects, object_images, section_types, category_sections, object_content_sections`

- [ ] **Step 5: Commit**

```bash
git add backend/app/models/content.py backend/app/models/__init__.py backend/alembic/env.py
git commit -m "feat(models): add content section tables + register models"
```

### Task 2.4: 模型单测（SQLite 内存库）

**Files:**
- Test: `tests/unit/models/test_step1_models.py`

- [ ] **Step 1: 写测试**

```python
# tests/unit/models/test_step1_models.py
import uuid
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from sqlalchemy.exc import IntegrityError

from app.core.database import Base
from app.models.museum import Museum
from app.models.museum_object import MuseumObject, ObjectImage
from app.models.content import SectionType, CategorySection, ObjectContentSection


@pytest.fixture()
def session():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(bind=engine, tables=[
        Museum.__table__, MuseumObject.__table__, ObjectImage.__table__,
        SectionType.__table__, CategorySection.__table__, ObjectContentSection.__table__,
    ])
    Session = sessionmaker(bind=engine)
    s = Session()
    yield s
    s.close()


def test_object_with_attributes_and_image(session):
    m = Museum(slug="orsay", name_en="Musée d'Orsay")
    session.add(m); session.flush()
    obj = MuseumObject(museum_id=m.id, qid="Q12418", category="painting",
                       title_en="Mona Lisa", attributes={"material": "oil on panel"})
    session.add(obj); session.flush()
    session.add(ObjectImage(object_id=obj.id, role="primary", source_url="http://x/a.jpg"))
    session.commit()
    got = session.query(MuseumObject).filter_by(qid="Q12418").one()
    assert got.attributes["material"] == "oil on panel"


def test_qid_unique(session):
    m = Museum(slug="orsay"); session.add(m); session.flush()
    session.add(MuseumObject(museum_id=m.id, qid="Q1")); session.commit()
    session.add(MuseumObject(museum_id=m.id, qid="Q1"))
    with pytest.raises(IntegrityError):
        session.commit()


def test_content_section_unique_per_obj_lang_section(session):
    m = Museum(slug="orsay"); session.add(m); session.flush()
    obj = MuseumObject(museum_id=m.id, qid="Q2"); session.add(obj); session.flush()
    session.add(SectionType(code="overview", label_en="Overview")); session.flush()
    session.add(ObjectContentSection(object_id=obj.id, language="en", section_code="overview", body="a"))
    session.commit()
    session.add(ObjectContentSection(object_id=obj.id, language="en", section_code="overview", body="b"))
    with pytest.raises(IntegrityError):
        session.commit()
```

- [ ] **Step 2: 跑测试确认通过**

Run: `cd backend && .venv/bin/python -m pytest tests/unit/models/test_step1_models.py -v`
Expected: PASS（3 个用例）

- [ ] **Step 3: Commit**

```bash
git add backend/tests/unit/models/test_step1_models.py
git commit -m "test(models): step1 models constraints"
```

### Task 2.5: 生成并校验 Alembic 迁移

**Files:**
- Generate: `alembic/versions/<hash>_step1_foundation.py`

- [ ] **Step 1: 自动生成迁移**

Run: `cd backend && set -a && . .env && set +a && .venv/bin/alembic revision --autogenerate -m "step1 data foundation"`
Expected: 生成 versions 下新文件，`upgrade()` 含 6 个 `create_table`

- [ ] **Step 2: 人工核对迁移文件**

打开生成的文件，确认：6 张表都在；`uq_object_museum_inventory`、`uq_content_obj_lang_section`、`museum_objects.qid` unique 都生成；无误删其它表的语句。如有 JSONB/variant 异常手动修正为 `sa.JSON()`。

- [ ] **Step 3: 应用迁移到本地库并回滚验证**

Run:
```bash
cd backend && set -a && . .env && set +a && \
  .venv/bin/alembic upgrade head && \
  .venv/bin/python -c "from sqlalchemy import create_engine, inspect; from app.core.config import settings; print('object_content_sections' in inspect(create_engine(settings.get_database_url())).get_table_names())" && \
  .venv/bin/alembic downgrade -1 && .venv/bin/alembic upgrade head
```
Expected: 打印 `True`；downgrade/upgrade 无报错

- [ ] **Step 4: Commit**

```bash
git add backend/alembic/versions/
git commit -m "feat(db): step1 foundation migration (6 tables)"
```

### Task 2.6: 种子数据（section_types + painting 的 category_sections）

**Files:**
- Create: `scripts/seed_sections.py`
- Test: `tests/integration/test_seed_sections.py`

- [ ] **Step 1: 写种子脚本**

```python
# scripts/seed_sections.py
"""种子：讲解 tab 词表 + 绘画类的 tab 集合（幂等 upsert）。"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.core.database import SessionLocal
from app.models.content import SectionType, CategorySection

SECTION_TYPES = [
    ("overview",     "通用描述", "Overview",     10),
    ("artist",       "作者介绍", "The Artist",   20),
    ("background",   "创作背景", "Background",   30),
    ("analysis",     "艺术分析", "Analysis",     40),
    ("significance", "文化意义", "Significance", 50),
    ("facts",        "趣闻轶事", "Facts",        60),
]
PAINTING_SECTIONS = ["overview", "artist", "background", "analysis", "significance", "facts"]


def seed():
    db = SessionLocal()
    try:
        for code, zh, en, sort in SECTION_TYPES:
            st = db.get(SectionType, code) or SectionType(code=code)
            st.label_zh, st.label_en, st.default_sort = zh, en, sort
            db.merge(st)
        for i, code in enumerate(PAINTING_SECTIONS):
            db.merge(CategorySection(category="painting", section_code=code, sort_order=(i + 1) * 10))
        db.commit()
        print(f"✓ seeded {len(SECTION_TYPES)} section_types, painting -> {len(PAINTING_SECTIONS)} sections")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
```

- [ ] **Step 2: 跑脚本（幂等）**

Run: `cd backend && set -a && . .env && set +a && .venv/bin/python scripts/seed_sections.py && .venv/bin/python scripts/seed_sections.py`
Expected: 两次都打印 `✓ seeded 6 section_types, painting -> 6 sections`，无报错（第二次不报唯一冲突）

- [ ] **Step 3: Commit**

```bash
git add backend/scripts/seed_sections.py
git commit -m "feat(db): seed section_types and painting category_sections"
```

---

## Phase 3 · Wikidata 导入器

### Task 3.1: 扩展 SPARQL 拉硬事实 + 馆藏号

**Files:**
- Modify: `scripts/build_museum_pack.py`（`QUERY_TEMPLATE` 与 `build_pack` 的字段抽取）

- [ ] **Step 1: 在 `QUERY_TEMPLATE` 的 SELECT 加变量、WHERE 末尾加 OPTIONAL**

SELECT 行追加 `?inventory ?material_en ?location_en ?width ?height`，并在最后一个 OPTIONAL 后加：

```sparql
  OPTIONAL { ?item wdt:P217 ?inventory }
  OPTIONAL { ?item wdt:P186 ?material . OPTIONAL { ?material rdfs:label ?material_en . FILTER(LANG(?material_en)="en") } }
  OPTIONAL { ?item wdt:P276 ?location . OPTIONAL { ?location rdfs:label ?location_en . FILTER(LANG(?location_en)="en") } }
  OPTIONAL { ?item wdt:P2049 ?width }
  OPTIONAL { ?item wdt:P2048 ?height }
```

- [ ] **Step 2: 在 `build_pack` 的 artwork dict 里增加字段**

在 `"popularity": ...` 之后加：

```python
                "inventory_number": _value(row, "inventory"),
                "attributes": {
                    "material": _value(row, "material_en"),
                    "current_location": _value(row, "location_en"),
                    "width_cm": _value(row, "width"),
                    "height_cm": _value(row, "height"),
                },
```

- [ ] **Step 3: 验证仍能生成 pack（小 limit 冒烟）**

Run: `cd backend && .venv/bin/python scripts/build_museum_pack.py --museum orsay --limit 5`
Expected: 打印 5 件，`museum_packs/orsay.json` 内出现 `inventory_number` 与 `attributes`

> ⚠️ 本步只新建字段，**不要覆盖**已有的生产 `orsay.json`（先备份 `cp museum_packs/orsay.json museum_packs/orsay.bak.json`，或用 `--limit` 后 `git checkout` 还原）。

- [ ] **Step 4: Commit**

```bash
git add backend/scripts/build_museum_pack.py
git commit -m "feat(import): pull inventory number + hard facts from Wikidata"
```

### Task 3.2: 幂等 upsert 入库函数

**Files:**
- Create: `app/services/object_importer.py`
- Test: `tests/integration/test_object_importer.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/integration/test_object_importer.py
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.core.database import Base
from app.models.museum import Museum
from app.models.museum_object import MuseumObject, ObjectImage
from app.services.object_importer import upsert_museum, upsert_object


@pytest.fixture()
def session():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(bind=engine, tables=[
        Museum.__table__, MuseumObject.__table__, ObjectImage.__table__])
    yield sessionmaker(bind=engine)()


def _art():
    return {"qid": "Q12418", "title_zh": "蒙娜丽莎", "title_en": "Mona Lisa",
            "artist_zh": "达芬奇", "artist_en": "Leonardo", "year": "1503",
            "period_zh": "文艺复兴", "period_en": "Renaissance", "popularity": 99,
            "inventory_number": "INV. 779", "image": "http://x/a.jpg",
            "attributes": {"material": "oil on panel"}}


def test_upsert_is_idempotent(session):
    m = upsert_museum(session, {"slug": "orsay", "qid": "Q23402", "name_en": "Orsay",
                                "name_zh": "奥赛", "city_en": "Paris", "city_zh": "巴黎", "country": "FR"})
    upsert_object(session, m.id, _art()); session.commit()
    upsert_object(session, m.id, _art()); session.commit()   # 第二次不应重复
    assert session.query(MuseumObject).count() == 1
    assert session.query(ObjectImage).count() == 1
    obj = session.query(MuseumObject).one()
    assert obj.inventory_number == "INV. 779"
    assert obj.attributes["material"] == "oil on panel"
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && .venv/bin/python -m pytest tests/integration/test_object_importer.py -v`
Expected: FAIL（`app.services.object_importer` 不存在）

- [ ] **Step 3: 写实现**

```python
# app/services/object_importer.py
"""把一条馆/展品数据幂等 upsert 进库。匹配优先级：qid → (museum, inventory_number)。"""
from sqlalchemy.orm import Session
from app.models.museum import Museum
from app.models.museum_object import MuseumObject, ObjectImage


def upsert_museum(db: Session, m: dict) -> Museum:
    obj = db.query(Museum).filter_by(slug=m["slug"]).one_or_none() or Museum(slug=m["slug"])
    for k in ("qid", "name_zh", "name_en", "city_zh", "city_en", "country"):
        if m.get(k) is not None:
            setattr(obj, k, m[k])
    db.add(obj); db.flush()
    return obj


def _find_object(db: Session, museum_id, art: dict) -> MuseumObject | None:
    if art.get("qid"):
        hit = db.query(MuseumObject).filter_by(qid=art["qid"]).one_or_none()
        if hit:
            return hit
    if art.get("inventory_number"):
        return db.query(MuseumObject).filter_by(
            museum_id=museum_id, inventory_number=art["inventory_number"]).one_or_none()
    return None


def upsert_object(db: Session, museum_id, art: dict) -> MuseumObject:
    obj = _find_object(db, museum_id, art) or MuseumObject(museum_id=museum_id)
    obj.museum_id = museum_id
    for k in ("qid", "inventory_number", "title_zh", "title_en", "artist_zh",
              "artist_en", "year", "period_zh", "period_en", "popularity"):
        if art.get(k) is not None:
            setattr(obj, k, art[k])
    obj.category = art.get("category", "painting")
    obj.attributes = {k: v for k, v in (art.get("attributes") or {}).items() if v is not None}
    db.add(obj); db.flush()

    # 主图：按 (object, role=primary) 幂等
    src = art.get("image")
    if src:
        img = db.query(ObjectImage).filter_by(object_id=obj.id, role="primary").one_or_none() \
            or ObjectImage(object_id=obj.id, role="primary")
        img.source_url = src.replace("http://", "https://")
        db.add(img)
    db.flush()
    return obj
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd backend && .venv/bin/python -m pytest tests/integration/test_object_importer.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/object_importer.py backend/tests/integration/test_object_importer.py
git commit -m "feat(import): idempotent upsert by qid / inventory number"
```

---

## Phase 4 · 一次性数据迁移

### Task 4.1: 现有 orsay.json → DB

**Files:**
- Create: `scripts/migrate_pack_to_db.py`

- [ ] **Step 1: 写脚本**

```python
# scripts/migrate_pack_to_db.py
"""把现有 museum_packs/<slug>.json 灌入 DB（幂等，复用 object_importer）。"""
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.core.database import SessionLocal
from app.services.object_importer import upsert_museum, upsert_object

PACK_DIR = Path(__file__).resolve().parents[1] / "museum_packs"


def migrate(slug: str):
    pack = json.loads((PACK_DIR / f"{slug}.json").read_text())
    db = SessionLocal()
    try:
        m = upsert_museum(db, pack)
        n = 0
        for art in pack["artworks"]:
            upsert_object(db, m.id, art); n += 1
        db.commit()
        print(f"✓ {slug}: 1 museum, {n} objects 入库")
    finally:
        db.close()


if __name__ == "__main__":
    migrate(sys.argv[1] if len(sys.argv) > 1 else "orsay")
```

- [ ] **Step 2: 跑迁移（幂等：连跑两次行数应一致）**

Run:
```bash
cd backend && set -a && . .env && set +a && \
  .venv/bin/python scripts/migrate_pack_to_db.py orsay && \
  .venv/bin/python scripts/migrate_pack_to_db.py orsay && \
  .venv/bin/python -c "from app.core.database import SessionLocal; from app.models.museum_object import MuseumObject; db=SessionLocal(); print('objects:', db.query(MuseumObject).count()); db.close()"
```
Expected: 两次都打印 `1 museum, 60 objects`；最终 `objects: 60`（不是 120）

- [ ] **Step 3: Commit**

```bash
git add backend/scripts/migrate_pack_to_db.py
git commit -m "feat(migrate): load existing orsay pack into DB"
```

### Task 4.2: Redis 讲解 → object_content_section

**Files:**
- Create: `scripts/migrate_redis_explanations.py`
- 参考：`app/services/content_cache.py`（键 `explanation:<md5(artwork|artist|lang)>`，值为 explanation dict）

- [ ] **Step 1: 写脚本（按 (title, artist, lang) 反查展品；payload 子字段映射到 section）**

```python
# scripts/migrate_redis_explanations.py
"""把 Redis 里已生成的讲解永久落库到 object_content_section（无损：5 子字段→5 section）。
匹配展品：按 title_zh/title_en + 语言扫描所有展品，命中其讲解键则落库。"""
import sys
from datetime import datetime
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.core.database import SessionLocal
from app.models.museum_object import MuseumObject
from app.models.content import ObjectContentSection
from app.services.content_cache import get_content_cache

# Redis payload 子字段 → section_code
FIELD_MAP = {
    "summary": "overview",
    "historical_context": "background",
    "artistic_analysis": "analysis",
    "cultural_significance": "significance",
}


def _facts_text(payload: dict) -> str | None:
    facts = payload.get("interesting_facts")
    if not facts:
        return None
    return "\n".join(f"- {f}" for f in facts)


def migrate(languages=("zh", "en")):
    cache = get_content_cache()
    db = SessionLocal()
    written = 0
    try:
        for obj in db.query(MuseumObject).all():
            for lang in languages:
                title = obj.title_zh if lang == "zh" else obj.title_en
                artist = obj.artist_zh if lang == "zh" else obj.artist_en
                if not title:
                    continue
                payload = cache.get_explanation(title, artist or "", lang)
                if not payload:
                    continue
                sections = {sec: payload.get(field) for field, sec in FIELD_MAP.items()}
                sections["facts"] = _facts_text(payload)
                for code, body in sections.items():
                    if not body:
                        continue
                    existing = db.query(ObjectContentSection).filter_by(
                        object_id=obj.id, language=lang, section_code=code).one_or_none()
                    row = existing or ObjectContentSection(
                        object_id=obj.id, language=lang, section_code=code)
                    row.body = body
                    row.status = "published"
                    row.source = "ai_generated"
                    row.generated_at = row.generated_at or datetime.utcnow()
                    db.add(row); written += 1
        db.commit()
        print(f"✓ 迁移落库 {written} 条讲解 section")
    finally:
        db.close()


if __name__ == "__main__":
    migrate()
```

- [ ] **Step 2: 跑迁移（需本地 Redis 有预热讲解；幂等）**

Run: `cd backend && set -a && . .env && set +a && .venv/bin/python scripts/migrate_redis_explanations.py`
Expected: 打印 `✓ 迁移落库 N 条讲解 section`（N>0 取决于 Redis 现有量）；连跑两次条数稳定

- [ ] **Step 3: 抽查落库结果**

Run:
```bash
cd backend && set -a && . .env && set +a && .venv/bin/python -c "
from app.core.database import SessionLocal
from app.models.content import ObjectContentSection
db=SessionLocal(); rows=db.query(ObjectContentSection).limit(3).all()
[print(r.language, r.section_code, (r.body or '')[:40]) for r in rows]; db.close()"
```
Expected: 打印若干 (语言, section_code, 正文片段)

- [ ] **Step 4: Commit**

```bash
git add backend/scripts/migrate_redis_explanations.py
git commit -m "feat(migrate): persist Redis explanations into DB sections"
```

---

## Phase 5 · 接口改造（保持返回形状不变）

### Task 5.1: DB→pack 形状序列化器

**Files:**
- Create: `app/services/museum_repo.py`
- Test: `tests/integration/test_museum_repo.py`

- [ ] **Step 1: 写失败测试（断言形状与旧 pack 一致）**

```python
# tests/integration/test_museum_repo.py
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.core.database import Base
from app.models.museum import Museum
from app.models.museum_object import MuseumObject, ObjectImage
from app.services.object_importer import upsert_museum, upsert_object
from app.services.museum_repo import list_museums, get_museum_pack


@pytest.fixture()
def session():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(bind=engine, tables=[
        Museum.__table__, MuseumObject.__table__, ObjectImage.__table__])
    s = sessionmaker(bind=engine)()
    m = upsert_museum(s, {"slug": "orsay", "qid": "Q23402", "name_zh": "奥赛", "name_en": "Orsay",
                          "city_zh": "巴黎", "city_en": "Paris", "country": "FR"})
    upsert_object(s, m.id, {"qid": "Q1", "title_zh": "甲", "title_en": "A", "artist_zh": "X",
                            "artist_en": "X", "year": "1880", "period_zh": "现实主义",
                            "period_en": "Realism", "popularity": 50, "image": "http://x/a.jpg",
                            "attributes": {}})
    s.commit()
    yield s


def test_list_shape(session):
    rows = list_museums(session)
    assert rows[0].keys() >= {"slug", "name_zh", "name_en", "city_zh", "city_en", "country", "artwork_count"}
    assert rows[0]["artwork_count"] == 1


def test_pack_shape(session):
    pack = get_museum_pack(session, "orsay")
    assert pack["slug"] == "orsay" and pack["artwork_count"] == 1
    art = pack["artworks"][0]
    assert art.keys() >= {"qid", "title_zh", "title_en", "artist_zh", "artist_en",
                          "year", "period_zh", "period_en", "image", "popularity"}
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && .venv/bin/python -m pytest tests/integration/test_museum_repo.py -v`
Expected: FAIL（`app.services.museum_repo` 不存在）

- [ ] **Step 3: 写实现（image 用 R2 公共 URL，回落 source_url）**

```python
# app/services/museum_repo.py
"""从 DB 读馆藏并拼回与旧 museum_packs JSON 完全一致的形状（保接口兼容）。"""
from sqlalchemy.orm import Session
from app.models.museum import Museum
from app.models.museum_object import MuseumObject, ObjectImage
from app.services.storage import get_object_storage

_PACK_FIELDS = ("slug", "name_zh", "name_en", "city_zh", "city_en", "country")


def _count(db: Session, museum_id) -> int:
    return db.query(MuseumObject).filter_by(museum_id=museum_id).count()


def list_museums(db: Session) -> list[dict]:
    out = []
    for m in db.query(Museum).order_by(Museum.slug).all():
        row = {f: getattr(m, f) for f in _PACK_FIELDS}
        row["artwork_count"] = _count(db, m.id)
        out.append(row)
    return out


def _image_url(db: Session, obj_id, fallback_src):
    img = db.query(ObjectImage).filter_by(object_id=obj_id, role="primary").one_or_none()
    if img and img.image_key:
        return get_object_storage().public_url(img.image_key)
    return (img.source_url if img else None) or fallback_src


def get_museum_pack(db: Session, slug: str) -> dict | None:
    m = db.query(Museum).filter_by(slug=slug).one_or_none()
    if not m:
        return None
    objs = db.query(MuseumObject).filter_by(museum_id=m.id) \
             .order_by(MuseumObject.popularity.desc()).all()
    artworks = [{
        "qid": o.qid,
        "title_zh": o.title_zh, "title_en": o.title_en,
        "artist_zh": o.artist_zh, "artist_en": o.artist_en,
        "year": o.year,
        "period_zh": o.period_zh, "period_en": o.period_en,
        "image": _image_url(db, o.id, None),
        "popularity": o.popularity,
    } for o in objs]
    pack = {f: getattr(m, f) for f in _PACK_FIELDS}
    pack.update({"qid": m.qid, "source": "DB", "artwork_count": len(artworks), "artworks": artworks})
    return pack
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd backend && .venv/bin/python -m pytest tests/integration/test_museum_repo.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/museum_repo.py backend/tests/integration/test_museum_repo.py
git commit -m "feat(api): DB-backed museum pack serializer (shape-compatible)"
```

### Task 5.2: `museums.py` 改读 DB

**Files:**
- Modify: `app/api/v1/endpoints/museums.py`
- Test: `tests/integration/test_museums_endpoint_db.py`

- [ ] **Step 1: 改端点用 repo + get_db**

把 `_PACK_DIR`/`_load_pack`/文件读取整体替换为：

```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.services.museum_repo import list_museums as repo_list, get_museum_pack as repo_pack

router = APIRouter()


@router.get("")
def list_museums(db: Session = Depends(get_db)) -> list[dict]:
    return repo_list(db)


@router.get("/{slug}")
def get_museum_pack(slug: str, db: Session = Depends(get_db)) -> dict:
    pack = repo_pack(db, slug)
    if pack is None:
        raise HTTPException(status_code=404, detail=f"museum pack not found: {slug}")
    return pack
```

- [ ] **Step 2: 写端点测试（override get_db，断言形状）**

```python
# tests/integration/test_museums_endpoint_db.py
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.core.database import Base, get_db
from app.main import app
from app.models.museum import Museum
from app.models.museum_object import MuseumObject, ObjectImage
from app.services.object_importer import upsert_museum, upsert_object


@pytest.fixture()
def client():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(bind=engine, tables=[
        Museum.__table__, MuseumObject.__table__, ObjectImage.__table__])
    Session = sessionmaker(bind=engine)
    s = Session()
    m = upsert_museum(s, {"slug": "orsay", "name_zh": "奥赛", "name_en": "Orsay",
                          "city_zh": "巴黎", "city_en": "Paris", "country": "FR", "qid": "Q23402"})
    upsert_object(s, m.id, {"qid": "Q1", "title_zh": "甲", "title_en": "A", "artist_zh": "X",
                            "artist_en": "X", "year": "1880", "period_zh": "现实主义",
                            "period_en": "Realism", "popularity": 50, "image": "http://x/a.jpg",
                            "attributes": {}})
    s.commit()
    app.dependency_overrides[get_db] = lambda: (yield s)
    yield TestClient(app)
    app.dependency_overrides.pop(get_db, None)
    s.close()


def test_list_endpoint(client):
    r = client.get("/api/v1/museums")
    assert r.status_code == 200
    assert r.json()[0]["slug"] == "orsay"
    assert r.json()[0]["artwork_count"] == 1


def test_pack_endpoint(client):
    r = client.get("/api/v1/museums/orsay")
    assert r.status_code == 200
    body = r.json()
    assert body["artwork_count"] == 1
    assert body["artworks"][0]["title_en"] == "A"


def test_pack_404(client):
    assert client.get("/api/v1/museums/nope").status_code == 404
```

> 注：路由前缀以 `app/api/v1/__init__.py` 实际注册为准，若不是 `/api/v1/museums` 则相应调整。

- [ ] **Step 3: 跑测试确认通过**

Run: `cd backend && .venv/bin/python -m pytest tests/integration/test_museums_endpoint_db.py -v`
Expected: PASS（3 用例）

- [ ] **Step 4: Commit**

```bash
git add backend/app/api/v1/endpoints/museums.py backend/tests/integration/test_museums_endpoint_db.py
git commit -m "refactor(api): museums endpoint reads from DB, shape unchanged"
```

### Task 5.3: 新增「展品讲解（按 tab）」读接口

**Files:**
- Modify: `app/api/v1/endpoints/museums.py`（加一个 `/{slug}/objects/{qid}/content` 路由）或新建 `content` 子路由
- Test: `tests/integration/test_object_content_endpoint.py`

- [ ] **Step 1: 写读函数（repo 层）**——在 `app/services/museum_repo.py` 追加：

```python
from app.models.content import SectionType, CategorySection, ObjectContentSection


def get_object_content(db: Session, qid: str, language: str) -> dict | None:
    obj = db.query(MuseumObject).filter_by(qid=qid).one_or_none()
    if not obj:
        return None
    mapping = db.query(CategorySection, SectionType).join(
        SectionType, CategorySection.section_code == SectionType.code
    ).filter(CategorySection.category == obj.category) \
     .order_by(CategorySection.sort_order).all()
    bodies = {c.section_code: c for c in db.query(ObjectContentSection).filter_by(
        object_id=obj.id, language=language).all()}
    tabs = []
    for cs, st in mapping:
        row = bodies.get(cs.section_code)
        tabs.append({
            "section_code": cs.section_code,
            "label": st.label_zh if language == "zh" else st.label_en,
            "icon": st.icon,
            "body": row.body if row else None,
            "audio_url": (get_object_storage().public_url(row.audio_key)
                          if row and row.audio_key else None),
        })
    return {"qid": qid, "category": obj.category, "language": language, "tabs": tabs}
```

- [ ] **Step 2: 在 `museums.py` 加路由**

```python
from app.services.museum_repo import get_object_content


@router.get("/{slug}/objects/{qid}/content")
def object_content(slug: str, qid: str, language: str = "zh", db: Session = Depends(get_db)) -> dict:
    data = get_object_content(db, qid, language)
    if data is None:
        raise HTTPException(status_code=404, detail=f"object not found: {qid}")
    return data
```

- [ ] **Step 3: 写测试**

```python
# tests/integration/test_object_content_endpoint.py
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.core.database import Base, get_db
from app.main import app
from app.models.museum import Museum
from app.models.museum_object import MuseumObject, ObjectImage
from app.models.content import SectionType, CategorySection, ObjectContentSection
from app.services.object_importer import upsert_museum, upsert_object


@pytest.fixture()
def client():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(bind=engine, tables=[
        Museum.__table__, MuseumObject.__table__, ObjectImage.__table__,
        SectionType.__table__, CategorySection.__table__, ObjectContentSection.__table__])
    s = sessionmaker(bind=engine)()
    m = upsert_museum(s, {"slug": "orsay", "name_en": "Orsay"})
    obj = upsert_object(s, m.id, {"qid": "Q1", "title_en": "A", "category": "painting",
                                  "image": "http://x/a.jpg", "attributes": {}})
    s.add(SectionType(code="overview", label_zh="通用描述", label_en="Overview", default_sort=10))
    s.add(CategorySection(category="painting", section_code="overview", sort_order=10))
    s.add(ObjectContentSection(object_id=obj.id, language="zh", section_code="overview", body="讲解正文"))
    s.commit()
    app.dependency_overrides[get_db] = lambda: (yield s)
    yield TestClient(app)
    app.dependency_overrides.pop(get_db, None); s.close()


def test_object_content_tabs(client):
    r = client.get("/api/v1/museums/orsay/objects/Q1/content?language=zh")
    assert r.status_code == 200
    tabs = r.json()["tabs"]
    assert tabs[0]["section_code"] == "overview"
    assert tabs[0]["label"] == "通用描述"
    assert tabs[0]["body"] == "讲解正文"
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd backend && .venv/bin/python -m pytest tests/integration/test_object_content_endpoint.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/museum_repo.py backend/app/api/v1/endpoints/museums.py backend/tests/integration/test_object_content_endpoint.py
git commit -m "feat(api): object content-by-tab endpoint"
```

### Task 5.4: 讲解生成落库（content.py 写穿到 DB）

**Files:**
- Modify: `app/api/v1/endpoints/content.py`（`generate_explanation` 末尾，生成成功后除写 Redis 外，按 qid 落 `object_content_section`）
- Create: `app/services/content_repo.py`（封装"按 qid+lang 写 5 个 section"）
- Test: `tests/integration/test_content_persist.py`

- [ ] **Step 1: 写落库函数**

```python
# app/services/content_repo.py
"""把一次生成的讲解（含 5 子字段）落库到 object_content_section（按 qid + 语言）。"""
from datetime import datetime
from sqlalchemy.orm import Session
from app.models.museum_object import MuseumObject
from app.models.content import ObjectContentSection

FIELD_MAP = {"summary": "overview", "historical_context": "background",
             "artistic_analysis": "analysis", "cultural_significance": "significance"}


def persist_explanation(db: Session, qid: str, language: str, payload: dict, model: str | None = None) -> bool:
    obj = db.query(MuseumObject).filter_by(qid=qid).one_or_none()
    if not obj:
        return False
    sections = {sec: payload.get(field) for field, sec in FIELD_MAP.items()}
    facts = payload.get("interesting_facts")
    sections["facts"] = "\n".join(f"- {f}" for f in facts) if facts else None
    for code, body in sections.items():
        if not body:
            continue
        row = db.query(ObjectContentSection).filter_by(
            object_id=obj.id, language=language, section_code=code).one_or_none() \
            or ObjectContentSection(object_id=obj.id, language=language, section_code=code)
        row.body, row.status, row.source = body, "published", "ai_generated"
        row.model = model
        row.generated_at = datetime.utcnow()
        db.add(row)
    db.commit()
    return True
```

- [ ] **Step 2: 在 `content.py` 接 DB**（`ExplanationRequest` 加可选 `qid`；生成成功后调用）

`ExplanationRequest` 增字段：`qid: Optional[str] = Field(None, description="Wikidata QID，用于落库")`

在 `generate_explanation` 里 `cache.set_explanation(...)` 之后追加：

```python
        if request.qid and not result.get("fallback"):
            from app.core.database import SessionLocal
            from app.services.content_repo import persist_explanation
            db = SessionLocal()
            try:
                persist_explanation(db, request.qid, request.language, result, model="gpt-4o-mini")
            finally:
                db.close()
```

- [ ] **Step 3: 写测试（DB 命中后有 section）**

```python
# tests/integration/test_content_persist.py
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.core.database import Base
from app.models.museum import Museum
from app.models.museum_object import MuseumObject, ObjectImage
from app.models.content import ObjectContentSection
from app.services.object_importer import upsert_museum, upsert_object
from app.services.content_repo import persist_explanation


@pytest.fixture()
def session():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(bind=engine, tables=[
        Museum.__table__, MuseumObject.__table__, ObjectImage.__table__, ObjectContentSection.__table__])
    s = sessionmaker(bind=engine)()
    m = upsert_museum(s, {"slug": "orsay", "name_en": "Orsay"})
    upsert_object(s, m.id, {"qid": "Q1", "title_en": "A", "image": "http://x/a.jpg", "attributes": {}})
    s.commit()
    yield s


def test_persist_explanation(session):
    payload = {"summary": "s", "historical_context": "h", "artistic_analysis": "a",
               "cultural_significance": "c", "interesting_facts": ["f1", "f2"]}
    assert persist_explanation(session, "Q1", "en", payload, model="gpt-4o-mini") is True
    rows = session.query(ObjectContentSection).all()
    codes = {r.section_code for r in rows}
    assert codes == {"overview", "background", "analysis", "significance", "facts"}
    assert persist_explanation(session, "Q404", "en", payload) is False  # 无此展品
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd backend && .venv/bin/python -m pytest tests/integration/test_content_persist.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/content_repo.py backend/app/api/v1/endpoints/content.py backend/tests/integration/test_content_persist.py
git commit -m "feat(content): persist generated explanations into DB sections"
```

---

## Phase 6 · 收尾验证

### Task 6.1: 全量回归 + 覆盖率

- [ ] **Step 1: 跑 Step1 相关全部测试**

Run: `cd backend && set -a && . .env && set +a && .venv/bin/python -m pytest tests/unit/storage tests/unit/models tests/integration/test_object_importer.py tests/integration/test_museum_repo.py tests/integration/test_museums_endpoint_db.py tests/integration/test_object_content_endpoint.py tests/integration/test_content_persist.py -v`
Expected: 全 PASS（R2 用例 PASS 或 SKIP）

- [ ] **Step 2: 跑整库回归，确认没破坏既有用例**

Run: `cd backend && set -a && . .env && set +a && .venv/bin/python -m pytest -q`
Expected: 既有用例全绿（与本分支起点一致）

- [ ] **Step 3: 更新 OpenWolf anatomy/memory**

把新增文件（6 模型、storage 包、3 脚本、museum_repo、content_repo、迁移）登记到 `.wolf/anatomy.md`，并在 `.wolf/memory.md` 追加一行 Step1 完成记录。

- [ ] **Step 4: Commit**

```bash
git add backend/.wolf .wolf
git commit -m "chore(wolf): log step1 data foundation completion"
```

---

## Self-Review 记录（写作者已自检）

- **Spec 覆盖**：6 表 ✅(Task 2.1-2.3)、身份模型(qid unique + museum/inventory unique) ✅(2.2,2.4)、object_image 一对多 ✅(2.2)、content status/model ✅(2.3,5.4)、存储抽象+R2 ✅(Phase1)、DB 唯一真相源(museums 改读 DB) ✅(5.2)、Wikidata 硬事实+P217 ✅(3.1)、导入器幂等 ✅(3.2)、orsay.json 迁移 ✅(4.1)、Redis→DB ✅(4.2)、接口形状兼容 ✅(5.1-5.2)、tab 读接口 ✅(5.3)、测试 ✅(各任务)。pgvector 明确不做 ✅。
- **词表对齐**：section_code 统一用 overview/artist/background/analysis/significance/facts；FIELD_MAP 在 4.2 与 5.4 一致（summary→overview 等），避免不一致。
- **占位扫描**：无 TBD/TODO；每个写代码步骤均含完整代码与可跑命令。
- **类型/命名一致**：`upsert_museum`/`upsert_object`/`persist_explanation`/`get_object_content`/`get_object_storage` 全程同名；模型字段名在测试与实现间一致。
- **已知风险**：①路由前缀 `/api/v1/museums` 需以 `app/api/v1/__init__.py` 实际注册为准（5.2 已注明）；②SQLite 单测对 JSONB 用 variant、对 server_default 仅建相关表规避；③导入器覆盖生产 `orsay.json` 风险已在 3.1 标注备份。
