# 识别引擎接入（DINOv2 前置 + 兜底 + 全局端点）实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** DINOv2 向量检索接入线上识别为主引擎（GPT+OCR 降级兜底），加全局识别端点、雕塑多视角补图、matcher 馆藏号匹配；响应契约只加不改，老前端零破坏。

**Architecture:** 嵌入引擎从 bench 迁入 `app/services/recognition/embedder.py`（onnxruntime 进主依赖，模型 88MB 放 R2 懒下载，失败→整链自动走 GPT 兜底优雅降级）。向量落 `object_embeddings` 表（生成一次永久落库），进程内矩阵缓存 TTL 600s。富化 materializer 入库即嵌入 + 一次性 backfill CLI。编排：向量三档 → miss 走现有 GPT+OCR 链 → 同一接地匹配层。spec：docs/superpowers/specs/2026-07-11-recognition-engine-dinov2-design.md。

**Tech Stack:** onnxruntime(主依赖) / numpy / SQLAlchemy+alembic / FastAPI / Flutter。

## Global Constraints

- 契约只加不改：三档响应形状不变；`match`/`candidates` 条目新增 `museum` 字段（归属馆 slug）是加法；老端点 `/museums/{slug}/recognize` 行为语义不变。
- Flutter 解析新字段禁裸 `as String`（`as String?` + 回退）。
- 阈值 server-driven：`RECOG_HIGH` 默认 0.85、`RECOG_LOW` 默认 0.72（Settings 环境变量）。
- 向量模型名常量 `MODEL_NAME = "dinov2-vits14"`（embeddings 行与索引查询一致）。
- 引擎不可用（模型下载失败/表空/onnxruntime 缺失）→ 不 500，整链走 GPT+OCR 兜底。
- 嵌入失败只记日志，绝不阻断补图/onboard 主流程。
- 计费规则不变：match/candidates 扣 1、unrecognized 与缓存命中不扣、超额 402。
- torch/transformers 不进主依赖（线上只跑预导出 ONNX）；onnxruntime 进主依赖。
- Python 过 black+isort；Flutter 过 dart format + flutter analyze。
- 所有单测不加载真模型（fake embedder 注入）。

---

### Task 1: DB——object_embeddings 表 + demands.museum_slug 可空

**Files:**
- Create: `backend/app/models/object_embedding.py`
- Modify: `backend/app/models/recognition_demand.py:18`（nullable=True）
- Create: `backend/alembic/versions/o1l1_add_object_embeddings.py`
- Test: `backend/tests/unit/models/test_object_embedding.py`

**Interfaces:**
- Produces: `ObjectEmbedding(id, object_id FK museum_objects, image_id FK object_images, model str, vec bytes, created_at)`，UniqueConstraint `(image_id, model)`，name=`uq_embedding_image_model`。

- [ ] **Step 1: 写失败测试**

```python
"""object_embeddings 模型:vec bytes 往返 + (image_id, model) 唯一。"""

import numpy as np
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.models.museum import Museum
from app.models.museum_object import MuseumObject, ObjectImage
from app.models.object_embedding import ObjectEmbedding
from app.services.object_importer import upsert_museum, upsert_object


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
            ObjectEmbedding.__table__,
        ],
    )
    s = sessionmaker(bind=engine)()
    m = upsert_museum(s, {"slug": "orsay", "name_en": "Orsay"})
    o = upsert_object(s, m.id, {"qid": "Q1", "title_en": "A"})
    img = ObjectImage(object_id=o.id, source_url="http://x/1.jpg", sort=0)
    s.add(img)
    s.commit()
    return s, o, img


def test_vec_roundtrip(session):
    s, o, img = session
    vec = np.arange(4, dtype=np.float32)
    s.add(
        ObjectEmbedding(
            object_id=o.id, image_id=img.id, model="dinov2-vits14", vec=vec.tobytes()
        )
    )
    s.commit()
    row = s.query(ObjectEmbedding).one()
    assert np.array_equal(np.frombuffer(row.vec, dtype=np.float32), vec)


def test_unique_image_model(session):
    s, o, img = session
    s.add(ObjectEmbedding(object_id=o.id, image_id=img.id, model="m", vec=b"x"))
    s.commit()
    s.add(ObjectEmbedding(object_id=o.id, image_id=img.id, model="m", vec=b"y"))
    with pytest.raises(Exception):
        s.commit()
```

- [ ] **Step 2: 跑测试确认失败**

`cd backend && python -m pytest tests/unit/models/test_object_embedding.py -v` → FAIL（模块不存在）。

- [ ] **Step 3: 模型 + 迁移**

`backend/app/models/object_embedding.py`：

```python
"""展品参考图向量(生成一次永久落库;model 字段版本化,换模型共存不冲突)。"""

import uuid

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    LargeBinary,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID

from app.core.database import Base


class ObjectEmbedding(Base):
    __tablename__ = "object_embeddings"
    __table_args__ = (
        UniqueConstraint("image_id", "model", name="uq_embedding_image_model"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    object_id = Column(
        UUID(as_uuid=True), ForeignKey("museum_objects.id"), nullable=False, index=True
    )
    image_id = Column(
        UUID(as_uuid=True), ForeignKey("object_images.id"), nullable=False, index=True
    )
    model = Column(String(64), nullable=False)
    vec = Column(LargeBinary, nullable=False)  # float32 bytes
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
```

`recognition_demand.py:18` 改 `nullable=True`（全局识别未收录也记需求，馆未知）。

迁移 `o1l1_add_object_embeddings.py`（`down_revision` 指向当前 head，先 `alembic heads` 确认是 `n1k0`）：

```python
"""object_embeddings 表 + recognition_demands.museum_slug 可空(全局识别)。"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "o1l1"
down_revision = "n1k0"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "object_embeddings",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "object_id",
            UUID(as_uuid=True),
            sa.ForeignKey("museum_objects.id"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "image_id",
            UUID(as_uuid=True),
            sa.ForeignKey("object_images.id"),
            nullable=False,
            index=True,
        ),
        sa.Column("model", sa.String(64), nullable=False),
        sa.Column("vec", sa.LargeBinary(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("image_id", "model", name="uq_embedding_image_model"),
    )
    op.alter_column(
        "recognition_demands", "museum_slug", existing_type=sa.String(64), nullable=True
    )


def downgrade():
    op.alter_column(
        "recognition_demands", "museum_slug", existing_type=sa.String(64), nullable=False
    )
    op.drop_table("object_embeddings")
```

- [ ] **Step 4: 跑测试确认通过**（2 passed）
- [ ] **Step 5: Commit** `feat(recognition): object_embeddings表+demands馆可空(迁移o1l1)`

---

### Task 2: embedder 迁入 app + 模型 R2 懒下载

**Files:**
- Create: `backend/app/services/recognition/embedder.py`
- Modify: `backend/scripts/recognition_bench/embed.py`（改为 re-export，单一来源）
- Modify: `backend/app/core/config.py`（Settings 加 5 个字段，插在 Cache 段前）
- Modify: `backend/pyproject.toml`（onnxruntime 进主依赖：`poetry add onnxruntime`；bench group 里的保留不冲突则删去 bench 组重复项——以 poetry 实际解析为准，目标：主依赖含 onnxruntime）
- Test: `backend/tests/unit/services/recognition/test_embedder.py`

**Interfaces:**
- Produces:
  - `MODEL_NAME = "dinov2-vits14"`；`PRESETS`、`preprocess(img, preset)`、`OnnxEmbedder`（从 bench 原样迁入）。
  - `get_embedder() -> OnnxEmbedder | None`：进程内单例；本地缓存无文件 → `get_object_storage().get(settings.RECOG_MODEL_KEY)` 下载写盘（sha256 校验，`RECOG_MODEL_SHA256` 为空则跳过校验）；任何失败 → 记日志返回 None，60s 内不重试（`_retry_after` 时间戳）。
  - Settings 新增：`RECOG_HIGH: float = 0.85`、`RECOG_LOW: float = 0.72`、`RECOG_MODEL_KEY: str = "models/dinov2_vits14.onnx"`、`RECOG_MODEL_SHA256: str = ""`、`RECOG_MODEL_CACHE: str = "/tmp/gomuseum_models"`。

- [ ] **Step 1: 失败测试**（不 import onnxruntime——测 get_embedder 的失败路径与缓存命中路径，用 monkeypatch 假 storage/假 OnnxEmbedder）

```python
"""embedder:模型懒下载/校验失败降级 None/单例;不加载真模型。"""

import hashlib

import app.services.recognition.embedder as emb


class _Storage:
    def __init__(self, data):
        self.data = data

    def get(self, key):
        return self.data


def test_download_verify_and_singleton(monkeypatch, tmp_path):
    emb._reset_for_test()
    blob = b"fake-onnx"
    monkeypatch.setattr(emb, "_get_storage", lambda: _Storage(blob))
    monkeypatch.setattr(emb.settings, "RECOG_MODEL_CACHE", str(tmp_path))
    monkeypatch.setattr(
        emb.settings, "RECOG_MODEL_SHA256", hashlib.sha256(blob).hexdigest()
    )
    created = []
    monkeypatch.setattr(
        emb, "OnnxEmbedder", lambda path, preset: created.append(path) or "ENGINE"
    )
    assert emb.get_embedder() == "ENGINE"
    assert emb.get_embedder() == "ENGINE"  # 单例
    assert len(created) == 1
    assert (tmp_path / "dinov2_vits14.onnx").read_bytes() == blob


def test_bad_sha_returns_none(monkeypatch, tmp_path):
    emb._reset_for_test()
    monkeypatch.setattr(emb, "_get_storage", lambda: _Storage(b"corrupt"))
    monkeypatch.setattr(emb.settings, "RECOG_MODEL_CACHE", str(tmp_path))
    monkeypatch.setattr(emb.settings, "RECOG_MODEL_SHA256", "deadbeef")
    assert emb.get_embedder() is None


def test_storage_failure_returns_none(monkeypatch, tmp_path):
    emb._reset_for_test()

    def boom():
        raise RuntimeError("no storage")

    monkeypatch.setattr(emb, "_get_storage", boom)
    monkeypatch.setattr(emb.settings, "RECOG_MODEL_CACHE", str(tmp_path))
    assert emb.get_embedder() is None
```

- [ ] **Step 2: 确认失败** → FAIL（模块不存在）。

- [ ] **Step 3: 实现 embedder.py**

```python
"""线上 embedding 引擎:DINOv2 ONNX 推理 + 模型 R2 懒下载。
引擎不可用一律返回 None → 编排层自动走 GPT+OCR 兜底(优雅降级,不 500)。
preprocess/OnnxEmbedder 与 bench 同源(bench re-export 本模块)。"""

from __future__ import annotations

import hashlib
import logging
import threading
import time
from pathlib import Path

import numpy as np
from PIL import Image

from app.core.config import settings

logger = logging.getLogger(__name__)

MODEL_NAME = "dinov2-vits14"

PRESETS = {
    "dinov2": {
        "resize": 256,
        "mean": [0.485, 0.456, 0.406],
        "std": [0.229, 0.224, 0.225],
    },
    "clip": {
        "resize": 224,
        "mean": [0.48145466, 0.4578275, 0.40821073],
        "std": [0.26862954, 0.26130258, 0.27577711],
    },
}


def preprocess(img: Image.Image, preset: str) -> np.ndarray:
    cfg = PRESETS[preset]
    img = img.convert("RGB")
    w, h = img.size
    scale = cfg["resize"] / min(w, h)
    img = img.resize((round(w * scale), round(h * scale)), Image.BICUBIC)
    w, h = img.size
    left, top = (w - 224) // 2, (h - 224) // 2
    img = img.crop((left, top, left + 224, top + 224))
    x = np.asarray(img, dtype=np.float32) / 255.0
    x = (x - np.array(cfg["mean"], dtype=np.float32)) / np.array(
        cfg["std"], dtype=np.float32
    )
    return x.transpose(2, 0, 1)[None]


class OnnxEmbedder:
    def __init__(self, onnx_path: str, preset: str):
        import onnxruntime as ort  # 懒加载

        self.preset = preset
        self.sess = ort.InferenceSession(
            onnx_path, providers=["CPUExecutionProvider"]
        )
        self.input_name = self.sess.get_inputs()[0].name

    def embed(self, img: Image.Image) -> np.ndarray:
        out = self.sess.run(None, {self.input_name: preprocess(img, self.preset)})
        v = out[0][0].astype(np.float32)
        return v / np.linalg.norm(v)


def _get_storage():
    from app.services.storage import get_object_storage

    return get_object_storage()


_lock = threading.Lock()
_engine = None
_retry_after = 0.0
_RETRY_COOLDOWN = 60.0


def _reset_for_test():
    global _engine, _retry_after
    _engine, _retry_after = None, 0.0


def get_embedder():
    """单例;失败返回 None 且 60s 内不重试(避免每请求重复打 R2)。"""
    global _engine, _retry_after
    if _engine is not None:
        return _engine
    if time.time() < _retry_after:
        return None
    with _lock:
        if _engine is not None:
            return _engine
        try:
            cache = Path(settings.RECOG_MODEL_CACHE)
            local = cache / Path(settings.RECOG_MODEL_KEY).name
            if not local.exists():
                data = _get_storage().get(settings.RECOG_MODEL_KEY)
                if not data:
                    raise RuntimeError(f"model missing in storage: {settings.RECOG_MODEL_KEY}")
                want = settings.RECOG_MODEL_SHA256
                if want and hashlib.sha256(data).hexdigest() != want:
                    raise RuntimeError("model sha256 mismatch")
                cache.mkdir(parents=True, exist_ok=True)
                local.write_bytes(data)
            _engine = OnnxEmbedder(str(local), "dinov2")
            logger.info("recognition embedder ready: %s", local)
            return _engine
        except Exception:
            logger.exception("embedder unavailable, falling back to GPT chain")
            _retry_after = time.time() + _RETRY_COOLDOWN
            return None
```

注意：测试 monkeypatch 的是 `emb.OnnxEmbedder` 与 `emb._get_storage`，实现必须经这两个名字调用（如上）。

- [ ] **Step 4: Settings 五字段**（config.py Cache 段前插入，含注释 `# Recognition (向量引擎)`）。

- [ ] **Step 5: bench/embed.py 改 re-export**

```python
"""bench 复用线上引擎实现(单一来源,见 app/services/recognition/embedder.py)。"""

from app.services.recognition.embedder import (  # noqa: F401
    PRESETS,
    OnnxEmbedder,
    preprocess,
)
```

- [ ] **Step 6: onnxruntime 进主依赖** `cd backend && poetry add onnxruntime`（lock 提交；确认生产镜像 `--only main` 会装到它）。

- [ ] **Step 7: 全部相关测试**

`python -m pytest tests/unit/services/recognition/ tests/unit/scripts/test_bench_embed.py -v` → 全绿（bench 预处理测试经 re-export 仍过）。

- [ ] **Step 8: Commit** `feat(recognition): embedding引擎迁入app(R2懒下载+sha校验+失败降级None)+onnxruntime进主依赖`

---

### Task 3: 入库即嵌入钩子 + backfill CLI

**Files:**
- Create: `backend/app/services/recognition/embeddings.py`
- Modify: `backend/app/services/enrichment/materializer.py`（materialize_row 成功路径末尾调钩子）
- Create: `backend/scripts/backfill_embeddings.py`
- Test: `backend/tests/unit/services/recognition/test_embeddings.py`

**Interfaces:**
- Produces:
  - `embed_image_row(db, row: ObjectImage, image_bytes: bytes, embedder=None) -> bool`：
    embedder 默认 `get_embedder()`；None → False；已有 (image_id, MODEL_NAME) 行 → True 幂等；
    否则 PIL 解码 → embed → 插 ObjectEmbedding（**不 commit**，随调用方事务）；异常 → log+False。
  - backfill CLI：`python -m scripts.backfill_embeddings [--limit N]`——扫 `image_key` 非空且无
    (image_id, MODEL_NAME) 嵌入的 ObjectImage，`storage.get(f"{image_key}_large.jpg")` → embed_image_row，
    每 20 行 commit + 打印进度。
- Consumes: `get_embedder/MODEL_NAME`（Task 2）、`ObjectEmbedding`（Task 1）。

- [ ] **Step 1: 失败测试**（fixture 沿用 Task 1 的 session 模式；fake embedder 返回固定向量）

```python
def test_embed_image_row_and_idempotent(session):
    s, o, img = session
    fake = type("E", (), {"embed": lambda self, im: np.ones(4, dtype=np.float32)})()
    png = _tiny_png_bytes()  # PIL 生成 8x8 RGB 存内存
    assert embed_image_row(s, img, png, embedder=fake) is True
    s.commit()
    assert embed_image_row(s, img, png, embedder=fake) is True  # 幂等不重插
    s.commit()
    assert s.query(ObjectEmbedding).count() == 1


def test_no_embedder_returns_false(session):
    s, o, img = session
    assert embed_image_row(s, img, b"whatever", embedder=None) is False


def test_bad_bytes_logged_not_raised(session):
    s, o, img = session
    fake = type("E", (), {"embed": lambda self, im: np.ones(4, dtype=np.float32)})()
    assert embed_image_row(s, img, b"not-an-image", embedder=fake) is False
```

（`_tiny_png_bytes`：`io.BytesIO` + `Image.new("RGB",(8,8)).save(buf,"PNG")`。embedder=None 显式传时**不回退 get_embedder**——用哨兵 `_UNSET` 区分"未传"与"显式 None"。）

- [ ] **Step 2: 确认失败。**

- [ ] **Step 3: 实现 embeddings.py**

```python
"""入库即嵌入(生成一次永久落库):补图/backfill 共用。失败只记日志不阻断主流程。"""

from __future__ import annotations

import io
import logging

from app.models.object_embedding import ObjectEmbedding
from app.services.recognition.embedder import MODEL_NAME, get_embedder

logger = logging.getLogger(__name__)

_UNSET = object()


def embed_image_row(db, row, image_bytes: bytes, embedder=_UNSET) -> bool:
    if embedder is _UNSET:
        embedder = get_embedder()
    if embedder is None:
        return False
    try:
        existing = (
            db.query(ObjectEmbedding)
            .filter_by(image_id=row.id, model=MODEL_NAME)
            .one_or_none()
        )
        if existing is not None:
            return True
        from PIL import Image

        vec = embedder.embed(Image.open(io.BytesIO(image_bytes)))
        db.add(
            ObjectEmbedding(
                object_id=row.object_id,
                image_id=row.id,
                model=MODEL_NAME,
                vec=vec.astype("float32").tobytes(),
            )
        )
        return True
    except Exception:
        logger.exception("embed_image_row failed (image_id=%s)", row.id)
        return False
```

- [ ] **Step 4: materializer 钩子**——`materialize_row` 中 `storage.put` 两档成功后（`already` 分支也要，若 large 可取）：在函数末尾 `return "done"` 前加：

```python
    try:  # 入库即嵌入(R2 已有文件时从 storage 取 large;失败不阻断)
        from app.services.recognition.embeddings import embed_image_row

        large_bytes = large if not already else storage.get(f"{base}_large.jpg")
        if large_bytes:
            embed_image_row(db, row, large_bytes)
    except Exception:
        logger.exception("embed hook failed: %s", base)
```

（注意 `large` 仅在 `not already` 分支存在——按此处代码取值顺序写，先看清 materialize_row 现有控制流再插。）

- [ ] **Step 5: backfill CLI scripts/backfill_embeddings.py**

```python
"""一次性:嵌入存量参考图(image_key 非空且缺 MODEL_NAME 向量)。容器内跑,可重复。"""

from __future__ import annotations

import argparse

from app.core.database import SessionLocal
from app.models.museum_object import ObjectImage
from app.models.object_embedding import ObjectEmbedding
from app.services.recognition.embedder import MODEL_NAME, get_embedder
from app.services.recognition.embeddings import embed_image_row
from app.services.storage import get_object_storage


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()
    db, storage = SessionLocal(), get_object_storage()
    embedder = get_embedder()
    if embedder is None:
        raise SystemExit("embedder unavailable (model not in R2?)")
    done_ids = {
        r[0]
        for r in db.query(ObjectEmbedding.image_id).filter_by(model=MODEL_NAME).all()
    }
    q = db.query(ObjectImage).filter(ObjectImage.image_key.isnot(None))
    rows = [r for r in q.all() if r.id not in done_ids]
    if args.limit:
        rows = rows[: args.limit]
    ok = fail = 0
    for i, row in enumerate(rows, 1):
        data = storage.get(f"{row.image_key}_large.jpg")
        if data and embed_image_row(db, row, data, embedder=embedder):
            ok += 1
        else:
            fail += 1
        if i % 20 == 0:
            db.commit()
            print(f"{i}/{len(rows)} ok={ok} fail={fail}", flush=True)
    db.commit()
    print(f"DONE {len(rows)} ok={ok} fail={fail}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 6: 测试全绿 → Commit** `feat(recognition): 入库即嵌入钩子+存量backfill CLI`

---

### Task 4: 向量索引服务 vector_index.py

**Files:**
- Create: `backend/app/services/recognition/vector_index.py`
- Test: `backend/tests/unit/services/recognition/test_vector_index.py`

**Interfaces:**
- Produces: `query_index(db, vec: np.ndarray, museum_id=None) -> list[tuple[str, float]]`
  ——加载 (vec, qid, museum_id) 全量矩阵（`model=MODEL_NAME`，join MuseumObject 取 qid/museum_id），
  进程内缓存 TTL 600s（`_cache`，`invalidate()` 供测试/钩子）；museum_id 给了先掩码过滤；
  同 qid 取最大分降序（与 bench metrics.rank 同语义，实现独立、不 import bench）。空表 → `[]`。

- [ ] **Step 1: 失败测试**：sqlite fixture 插 2 件 3 向量（含同 qid 两图取 max 断言、馆过滤断言、空表 `[]`、TTL 缓存生效（插新行不 invalidate 不可见、invalidate 后可见））。向量用单位化 float32 tobytes 写入。
- [ ] **Step 2: 确认失败。**
- [ ] **Step 3: 实现**（numpy 矩阵点积；缓存结构 `(ts, mat, qids, museum_ids)`；`invalidate()` 清空）。
- [ ] **Step 4: 通过 → Commit** `feat(recognition): 向量索引服务(全局矩阵+馆过滤+TTL缓存)`

---

### Task 5: matcher 馆藏号匹配 + 全目录索引

**Files:**
- Modify: `backend/app/services/recognition/matcher.py`
- Test: `backend/tests/unit/services/recognition/test_matcher.py`（追加用例，不改既有）

**Interfaces:**
- `build_index(db, museum_id)`：`museum_id=None` → 全部馆的对象（filter 去掉）；entry 增加
  `"inv"`（`normalize_inv(o.inventory_number)`，无则 None）。
- `normalize_inv(s) -> str`：小写 + 去所有非字母数字（`RF 1668` ≈ `rf1668`）。
- `match(...)`：对每个探针（候选名+墙签行）先做 `normalize_inv(probe) == entry["inv"]` 精确匹配
  → 该件直接记 1.0 满分；再走现有模糊逻辑（取 max）。探针归一化后长度 <3 不做编号匹配（防误伤）。

- [ ] **Step 1: 追加失败测试**：墙签行含 `"RF 1668"` → 命中 inventory_number=`"RF1668"` 的件且分=1.0；
  `museum_id=None` 全目录含两馆对象；短探针不触发编号匹配。
- [ ] **Step 2: 确认失败 → Step 3 实现 → Step 4 全 matcher 测试绿（含既有）。**
- [ ] **Step 5: Commit** `feat(recognition): matcher编号精确匹配+全目录索引(museum_id可空)`

---

### Task 6: 编排改造 service.py（向量前置 + 全局 + 兜底）

**Files:**
- Modify: `backend/app/services/recognition/service.py`
- Modify: `backend/app/services/recognition/demands.py`（slug 参数允许 None，逻辑不变——filter_by(museum_slug=None) 即 IS NULL）
- Test: `backend/tests/unit/services/recognition/test_service.py`（追加向量路径用例；既有 GPT 链用例必须原样全过）

**Interfaces:**
- `recognize(db, slug, image_bytes, *, language, mode, identify_fn=None, redis=None, embed_fn=None, vector_query_fn=None) -> dict | None`
  - `slug=None` → 全局：不查 Museum、matcher/向量都不过滤馆。`slug` 给了但馆不存在 → 仍返回 None（老语义）。
  - 新流程（mode=artwork 时）：
    1. `embed_fn = embed_fn or (get_embedder() 包装)`；引擎 None → 直接 GPT 链（现状代码）。
    2. `vec = embed_fn(image_bytes)`（内部 PIL 解码）；`ranked = vector_query_fn(db, vec, museum.id if museum else None)`。
    3. `top ≥ settings.RECOG_HIGH` → match；`[RECOG_LOW, HIGH)` → candidates（top3 ≥ LOW）；
    4. 馆内查询且 `top < RECOG_LOW` → **再查全局一次**（`museum_id=None`）；全局 top ≥ HIGH/LOW 同样出 match/candidates（条目 `museum` 字段自然是归属馆）；
    5. 仍 miss → GPT+OCR 链（现有代码原样，matcher 索引改 `build_index(db, museum.id if museum else None)`）。
  - `mode=label` 不走向量（纯转写场景），直接现有链。
  - `_summary` 增加 `"museum": <归属馆 slug>`（object.museum_id → Museum.slug，批量查一次做映射）。
  - 缓存键 `recog3:{slug or "global"}:{language}:{sha}`；TTL 策略不变。
  - unrecognized → `record_demand(db, slug, ...)`（slug 可 None）。
- `recognize_billed(...)`：透传 slug 可空；计费逻辑零改动。

- [ ] **Step 1: 追加失败测试**（fake embed_fn/vector_query_fn 注入，identify_fn 用既有 fake）：
  - 向量 HIGH 命中 → outcome=match、GPT 不被调用（identify_fn 上装计数断言 0 次）、match 带 museum 字段；
  - 向量中分 → candidates（≥LOW 的 top3）；
  - 馆内 miss → 全局命中（vector_query_fn 记录两次调用：先馆 id 再 None）；
  - 向量全 miss → 走 GPT 链且行为与既有用例一致；
  - embed_fn=None（引擎不可用）→ 纯 GPT 链；
  - slug=None 全局 + unrecognized → record_demand 收到 museum_slug=None；
  - 缓存键前缀 recog3。
- [ ] **Step 2: 确认失败 → Step 3 实现 → Step 4 recognition 全部测试绿（既有 + 新增）。**
- [ ] **Step 5: Commit** `feat(recognition): 编排接DINOv2前置(三档+馆内回退全局+GPT兜底降级)`

---

### Task 7: 全局端点 + 老端点委托

**Files:**
- Create: `backend/app/api/v1/endpoints/recognize_global.py`
- Modify: v1 router 注册处（`app/api/v1/api.py` 或等价文件，按现状 include_router）
- Modify: `backend/app/api/v1/endpoints/museums.py::recognize_artwork`（内部改调同一 service，行为不变）
- Test: `backend/tests/unit/api/test_recognize_global.py`

**Interfaces:**
- `POST /api/v1/recognize`：multipart `image`；query `museum`(可选 slug)、`language`、`mode`、`device_id`；
  auth 与老端点完全一致（HTTPBearer optional + device_id → recognize_billed；402 语义不变）。
  `museum` 给了但不存在 → 404（与老端点一致）。响应 = service 输出原样。
- 老端点：函数体改为调用与新端点相同的 service 入口（slug 必填路径参数），响应形状不变。

- [ ] **Step 1: 失败 API 测试**（dependency override / identify_fn 注入模式抄既有 test_recognition_api.py）：全局 200、museum 过滤 404、402 超额、老端点仍 200 且响应含新增 museum 字段。
- [ ] **Step 2-4: RED → 实现 → GREEN（api 目录全绿）。**
- [ ] **Step 5: Commit** `feat(api): 全局识别端点POST /api/v1/recognize(museum可选)+老端点内部委托`

---

### Task 8: 雕塑多视角补图（管线 + onboard 子命令）

**Files:**
- Create: `backend/app/services/enrichment/views.py`
- Modify: `backend/scripts/onboard.py`（加 `views` 子命令）
- Test: `backend/tests/unit/services/enrichment/test_views.py`

**Interfaces:**
- `fetch_view_urls(qid, *, max_n=4, http_get=None) -> list[str]`：Wikidata P373/commonswiki sitelink →
  Commons categorymembers(file) → 排除 P18 本尊、只收 jpg/jpeg/png → imageinfo `iiurlwidth=1600` thumburl。
  逻辑参照 bench `commons_alt_photos`（独立实现于管线，带 http_get 注入可测；UA/sleep 同规范）。
- `add_view_images(db, obj, *, max_total=5, fetch=None) -> int`：`category=="sculpture"` 且现有图 <3 才动作；
  插 `ObjectImage(role="view", source_url=url, sort=<顺延>)` 至总数 ≤ max_total；已有同 source_url 跳过；
  **不 commit**。返回新插行数。license/credit 留空——materializer 物化时经既有 `fetch_meta` 补。
- onboard 子命令：`python -m scripts.onboard views --museum orsay [--max 4]` →
  遍历该馆 sculpture 件调 add_view_images，逐件 commit + 打印；结束后提示跑既有物化步骤
  （物化会自动触发 Task 3 的嵌入钩子）。

- [ ] **Step 1: 失败测试**（fake fetch 注入）：非 sculpture 不动作；已有 ≥3 图不动作；插入 role/sort 正确、
  同 url 幂等、cap 生效。
- [ ] **Step 2-4: RED → 实现 → GREEN。**
- [ ] **Step 5: Commit** `feat(enrichment): 雕塑多视角参考图(Commons views+onboard子命令,物化即嵌入)`

---

### Task 9: 前端切全局端点

**Files:**
- Modify: `frontend/gomuseum_app/lib/features/recognition/data/datasources/recognition_remote_datasource.dart`
- Modify: `frontend/gomuseum_app/lib/features/recognition/data/models/recognize_response.dart`
- Modify: `frontend/gomuseum_app/lib/features/recognition/presentation/pages/camera_page.dart`
- Modify: 相应 providers/usecase 若签名传导（以 flutter analyze 为准，最小传导）
- Test: `frontend/gomuseum_app/test/` 下既有识别相关测试更新 + 新增 museum 字段解析用例

**Interfaces:**
- datasource `recognize({String? slug, ...})`：slug null → `POST /api/v1/recognize`（无路径馆段）；
  非 null → 老 URL 不变（兼容留路）。
- `RecognizedItem` 加 `final String? museum;`，解析 `j['museum'] as String?`（**禁裸 as String**）。
- `camera_page.dart`：删 `static const String _slug = 'orsay'` 与 ponytail 注释；调用 `recognize(slug: null, ...)`；
  `_goGuide(item.museum ?? 'orsay', item.qid)`（缺字段回退 orsay——契约容错，老后端也不炸）。
- [ ] **Step 1: 更新/新增测试（RED）→ Step 2 实现 → Step 3 `flutter analyze && flutter test` 全绿。**
- [ ] **Step 4: Commit** `feat(app): 识别切全局端点(拍前不选馆,跳转用归属馆,契约容错回退)`

---

### Task 10: 实跑部署与端到端验证（inline 运维，不派码农）

- [ ] **Step 1: 模型上 R2**：`docker cp` 本地 `dinov2_vits14.onnx` 进 staging 容器 →
  容器内 `python -c "storage.put('models/dinov2_vits14.onnx', ...)"`；本地算 sha256，
  写入 VPS 两环境 `.env` 的 `RECOG_MODEL_SHA256`（staging 先，prod 发布时用户批）。
- [ ] **Step 2: PR → staging 合并**（CI 绿后 squash）；确认部署后迁移 o1l1 已应用
  （查 deploy 流程是否自动 `alembic upgrade head`，否则容器内手跑）。
- [ ] **Step 3: backfill**：staging 容器 `python -m scripts.backfill_embeddings`（1704 图，~20-40min）；
  完成后 SQL 抽查 `count(*) from object_embeddings` ≈ 图数。
- [ ] **Step 4: 雕塑补图**：`python -m scripts.onboard views --museum orsay` → 物化 → 抽查 license/credit
  非空、object_embeddings 增量 ≈ 新图数。
- [ ] **Step 5: 端到端三档**：bench testset 真实游客照抽 3 张（高分名画/中分/库外）curl 打
  staging `POST /api/v1/recognize`：match 带 museum 字段；candidates Top-3；unrecognized+demand 落库
  （SQL 查 museum_slug NULL 行）；老端点同图等价；配额 402 快速验证。
- [ ] **Step 6: 契约回写**：主契约文档（repo 内 API 契约文件，执行时定位）加新端点 API 面与
  `museum` 字段语义；本轮实现细节不进。
- [ ] **Step 7: 记忆/ledger 更新 + 汇报用户**（prod 发布留给用户）。
