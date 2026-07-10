# 识别引擎离线评测原型（DINOv2 vs CLIP benchmark）实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 离线验证"向量检索能否解决识别不准"——orsay 全目录建索引，分层测试集（非名作 70%）评测 DINOv2-S vs CLIP ViT-B/32 的 Top-1/Top-3/库外误接受/延迟，产出阈值校准依据与是否接引擎位的裁决。

**Architecture:** 全部代码在 `backend/scripts/recognition_bench/`（scripts 已是 package），纯离线不碰线上流程。数据流：VPS 容器内导出目录 manifest（唯一碰 DB 的一步，只读）→ 本地下载参考图/Commons 游客照/库外干扰图 → PIL 合成畸变 → transformers 一次性导出两个 ONNX → onnxruntime 向量化建索引（.npz）→ 评测脚本按 模型×真实/合成×名作/非名作×平面/3D 分桶出 markdown 报告。

**Tech Stack:** onnxruntime + numpy 精确余弦（2k 量级，无 FAISS/pgvector）；torch+transformers 仅用于一次性 ONNX 导出；PIL 畸变；Wikidata/Commons/SPARQL 公共 API 取测试照片。

## Global Constraints

- 新依赖只进 poetry `bench` group（`poetry add --group bench`，必须提交 poetry.lock）；生产镜像与主依赖零变化。
- 所有产物（图片/向量/报告）落 `backend/scripts/recognition_bench/data/`，整目录 gitignore。
- 采样/畸变一律固定 seed=42，可复现。
- 访问 Wikidata/Commons/SPARQL 必须带 UA `GoMuseumBench/1.0 (appcraft008@gmail.com)`，请求间 sleep ≥0.2s。
- 纯逻辑模块（distort/metrics/采样/预处理）不得 import onnxruntime/torch——CI 单测无重依赖也能跑。
- Python 代码过 black + isort（pre-commit 钩子自动跑）。
- 判定线（来自 spec）：同组阈值下 Top-1 ≥ 85%、Top-3 ≥ 95%、库外误接受 ≤ 5%，且非名作桶单独达标。
- 名作线：馆内 popularity 降序前 200 名；3D 类目 = {sculpture, decorative_arts, textile, artifact}，其余为 2D。

---

### Task 1: 骨架 + bench 依赖组

**Files:**
- Create: `backend/scripts/recognition_bench/__init__.py`（空文件）
- Modify: `backend/pyproject.toml` + `backend/poetry.lock`（poetry 命令生成）
- Modify: `backend/.gitignore`（或仓库根 `.gitignore`，看 `scripts` 已有忽略规则放哪，跟随现状）

**Interfaces:**
- Produces: 包路径 `scripts.recognition_bench`；依赖组 `bench`（onnxruntime、torch、transformers）；`backend/scripts/recognition_bench/data/` 被 git 忽略。

- [ ] **Step 1: 建包与忽略规则**

```bash
touch backend/scripts/recognition_bench/__init__.py
mkdir -p backend/scripts/recognition_bench/data
echo "scripts/recognition_bench/data/" >> backend/.gitignore
```

- [ ] **Step 2: 加 bench 依赖组**

```bash
cd backend && poetry add --group bench onnxruntime torch transformers
```

预期：pyproject.toml 出现 `[tool.poetry.group.bench.dependencies]`，poetry.lock 更新。若 poetry 用的是 PEP621 布局（本项目是 `requires-python` 风格），确认 group 语法生成正确、`poetry install --with bench` 可用。

- [ ] **Step 3: 验证主依赖未变**

```bash
cd backend && git diff pyproject.toml | head -40
```

预期：diff 只新增 bench group 段落，主 dependencies 无变化。

- [ ] **Step 4: Commit**

```bash
git add backend/pyproject.toml backend/poetry.lock backend/.gitignore backend/scripts/recognition_bench/__init__.py
git commit -m "chore(bench): recognition_bench 骨架 + poetry bench 依赖组(onnxruntime/torch/transformers,不进生产)"
```

---

### Task 2: 合成畸变模块 distort.py

**Files:**
- Create: `backend/scripts/recognition_bench/distort.py`
- Test: `backend/tests/unit/scripts/test_bench_distort.py`（`backend/tests/unit/scripts/__init__.py` 一并创建）

**Interfaces:**
- Produces: `distort_all(img: Image.Image, seed: int) -> dict[str, Image.Image]`，key 固定为 `{"perspective", "glare", "crop", "blur", "dark"}`，输出尺寸与输入一致，RGB。

- [ ] **Step 1: 写失败测试**

```python
"""合成畸变:官方图→伪游客照(透视/反光/裁切/模糊/暗光),固定seed可复现。"""

import numpy as np
from PIL import Image

from scripts.recognition_bench.distort import distort_all


def _img():
    # 必须非纯色(纯色图 blur 后逐字节相同)且确定性(effect_noise 无 seed 不可用)
    a = (np.arange(320 * 240 * 3) % 255).astype("uint8").reshape(240, 320, 3)
    return Image.fromarray(a)


def test_five_variants_same_size_rgb():
    out = distort_all(_img(), seed=42)
    assert set(out) == {"perspective", "glare", "crop", "blur", "dark"}
    for v in out.values():
        assert v.size == (320, 240) and v.mode == "RGB"


def test_deterministic():
    a = distort_all(_img(), seed=42)["perspective"].tobytes()
    b = distort_all(_img(), seed=42)["perspective"].tobytes()
    assert a == b


def test_actually_changes_pixels():
    src = _img().tobytes()
    out = distort_all(_img(), seed=42)
    assert all(v.tobytes() != src for v in out.values())
```

- [ ] **Step 2: 跑测试确认失败**

```bash
cd backend && python -m pytest tests/unit/scripts/test_bench_distort.py -v
```

预期：FAIL（ModuleNotFoundError: scripts.recognition_bench.distort）。

- [ ] **Step 3: 最小实现**

```python
"""合成畸变:官方图 → 伪游客照。纯 PIL+numpy,禁 import torch/onnxruntime。
非名作在 Commons 无他人照片,合成畸变是其测试照的主要来源(spec ③)。"""

from __future__ import annotations

import random

import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter


def _perspective_coeffs(src_pts, dst_pts):
    # PIL PERSPECTIVE 需要 8 系数:解 8 元线性方程(标准做法)
    a = []
    for (x, y), (u, v) in zip(dst_pts, src_pts):
        a.append([x, y, 1, 0, 0, 0, -u * x, -u * y])
        a.append([0, 0, 0, x, y, 1, -v * x, -v * y])
    b = np.array(src_pts, dtype=np.float64).reshape(8)
    return np.linalg.solve(np.array(a, dtype=np.float64), b).tolist()


def _perspective(img: Image.Image, rng: random.Random) -> Image.Image:
    w, h = img.size
    j = lambda lim: rng.uniform(0.02, 0.10) * lim  # 角点抖动 2-10%
    dst = [(j(w), j(h)), (w - j(w), j(h)), (w - j(w), h - j(h)), (j(w), h - j(h))]
    src = [(0, 0), (w, 0), (w, h), (0, h)]
    coeffs = _perspective_coeffs(src, dst)
    return img.transform((w, h), Image.PERSPECTIVE, coeffs, Image.BICUBIC)


def _glare(img: Image.Image, rng: random.Random) -> Image.Image:
    w, h = img.size
    cx, cy = rng.uniform(0.2, 0.8) * w, rng.uniform(0.1, 0.5) * h
    r = rng.uniform(0.15, 0.3) * max(w, h)
    overlay = Image.new("L", (w, h), 0)
    draw = ImageDraw.Draw(overlay)
    for i in range(int(r), 0, -2):  # 同心圆近似径向渐变
        draw.ellipse([cx - i, cy - i, cx + i, cy + i], fill=int(200 * (1 - i / r)))
    white = Image.new("RGB", (w, h), (255, 255, 240))
    return Image.composite(white, img, overlay)


def _crop(img: Image.Image, rng: random.Random) -> Image.Image:
    w, h = img.size
    f = rng.uniform(0.75, 0.85)
    cw, ch = int(w * f), int(h * f)
    x, y = rng.randint(0, w - cw), rng.randint(0, h - ch)
    return img.crop((x, y, x + cw, y + ch)).resize((w, h), Image.BICUBIC)


def distort_all(img: Image.Image, seed: int) -> dict[str, Image.Image]:
    img = img.convert("RGB")
    rng = random.Random(seed)
    return {
        "perspective": _perspective(img, rng),
        "glare": _glare(img, rng),
        "crop": _crop(img, rng),
        "blur": img.filter(ImageFilter.GaussianBlur(2.5)),
        "dark": ImageEnhance.Brightness(img).enhance(0.45),
    }
```

- [ ] **Step 4: 跑测试确认通过**

```bash
cd backend && python -m pytest tests/unit/scripts/test_bench_distort.py -v
```

预期：3 passed。

- [ ] **Step 5: Commit**

```bash
git add backend/scripts/recognition_bench/distort.py backend/tests/unit/scripts/
git commit -m "feat(bench): 合成畸变模块(透视/反光/裁切/模糊/暗光,seed可复现)"
```

---

### Task 3: 检索与指标模块 metrics.py

**Files:**
- Create: `backend/scripts/recognition_bench/metrics.py`
- Test: `backend/tests/unit/scripts/test_bench_metrics.py`

**Interfaces:**
- Produces（后续 Task 7/8 依赖，签名精确）：
  - `rank(q: np.ndarray, vecs: np.ndarray, qids: list[str]) -> list[tuple[str, float]]`
    —— q 为单位向量 [D]，vecs [N,D] 已单位化；余弦=点积；**同 qid 多参考图取最大分**；按分降序。
  - `topk_hit(ranked, true_qid: str, k: int) -> bool`
  - `sweep(in_top1: list[float], ooc_top1: list[float]) -> list[dict]`
    —— 阈值 0.50→0.95 步长 0.05，每行 `{"threshold", "in_accept_rate", "ooc_accept_rate"}`。
  - `margins(ranked_list: list[list[tuple[str, float]]]) -> list[float]` —— 每条查询 top1-top2 分差（不足两名给 top1 分）。
  - `pctl(values: list[float], p: float) -> float` —— 线性插值百分位。

- [ ] **Step 1: 写失败测试**

```python
"""检索(同qid多图取最大分)与指标(topk/阈值扫/间距/百分位),纯numpy。"""

import numpy as np

from scripts.recognition_bench.metrics import margins, pctl, rank, sweep, topk_hit


def _unit(v):
    v = np.asarray(v, dtype=np.float32)
    return v / np.linalg.norm(v)


def test_rank_aggregates_max_per_qid():
    vecs = np.stack([_unit([1, 0]), _unit([0.9, 0.1]), _unit([0, 1])])
    ranked = rank(_unit([1, 0]), vecs, ["A", "A", "B"])
    assert ranked[0][0] == "A" and ranked[1][0] == "B"
    assert abs(ranked[0][1] - 1.0) < 1e-6  # A 取两张图中的最大分
    assert len(ranked) == 2  # 去重


def test_topk_hit():
    ranked = [("A", 0.9), ("B", 0.8)]
    assert topk_hit(ranked, "B", 3) and not topk_hit(ranked, "B", 1)


def test_sweep_rates():
    rows = sweep(in_top1=[0.9, 0.9, 0.6], ooc_top1=[0.55, 0.85])
    row_08 = next(r for r in rows if abs(r["threshold"] - 0.80) < 1e-9)
    assert abs(row_08["in_accept_rate"] - 2 / 3) < 1e-9
    assert abs(row_08["ooc_accept_rate"] - 1 / 2) < 1e-9


def test_margins_and_pctl():
    assert margins([[("A", 0.9), ("B", 0.7)], [("C", 0.5)]]) == [
        0.9 - 0.7,
        0.5,
    ]
    assert pctl([1.0, 2.0, 3.0, 4.0], 50) == 2.5
```

- [ ] **Step 2: 跑测试确认失败**

```bash
cd backend && python -m pytest tests/unit/scripts/test_bench_metrics.py -v
```

预期：FAIL（模块不存在）。

- [ ] **Step 3: 最小实现**

```python
"""检索与指标:余弦近邻(同qid多参考图取最大分)+Top-k/阈值扫/Top1-Top2间距/百分位。
纯 numpy,2k 量级精确搜索毫秒级(spec:不上 FAISS/pgvector)。"""

from __future__ import annotations

import numpy as np


def rank(q: np.ndarray, vecs: np.ndarray, qids: list[str]) -> list[tuple[str, float]]:
    scores = vecs @ q  # 均已单位化,点积即余弦
    best: dict[str, float] = {}
    for qid, s in zip(qids, scores):
        if s > best.get(qid, -2.0):
            best[qid] = float(s)
    return sorted(best.items(), key=lambda kv: -kv[1])


def topk_hit(ranked: list[tuple[str, float]], true_qid: str, k: int) -> bool:
    return any(qid == true_qid for qid, _ in ranked[:k])


def sweep(in_top1: list[float], ooc_top1: list[float]) -> list[dict]:
    rows = []
    for t in [round(0.50 + 0.05 * i, 2) for i in range(10)]:
        rows.append(
            {
                "threshold": t,
                "in_accept_rate": (
                    sum(s >= t for s in in_top1) / len(in_top1) if in_top1 else 0.0
                ),
                "ooc_accept_rate": (
                    sum(s >= t for s in ooc_top1) / len(ooc_top1) if ooc_top1 else 0.0
                ),
            }
        )
    return rows


def margins(ranked_list: list[list[tuple[str, float]]]) -> list[float]:
    out = []
    for ranked in ranked_list:
        if len(ranked) >= 2:
            out.append(ranked[0][1] - ranked[1][1])
        elif ranked:
            out.append(ranked[0][1])
    return out


def pctl(values: list[float], p: float) -> float:
    return float(np.percentile(np.asarray(values, dtype=np.float64), p))
```

- [ ] **Step 4: 跑测试确认通过**

```bash
cd backend && python -m pytest tests/unit/scripts/test_bench_metrics.py -v
```

预期：4 passed。

- [ ] **Step 5: Commit**

```bash
git add backend/scripts/recognition_bench/metrics.py backend/tests/unit/scripts/test_bench_metrics.py
git commit -m "feat(bench): 检索与指标模块(同qid最大分聚合/topk/阈值扫/间距/百分位)"
```

---

### Task 4: 目录 manifest 导出 export_manifest.py

**Files:**
- Create: `backend/scripts/recognition_bench/export_manifest.py`
- Test: `backend/tests/unit/scripts/test_bench_export_manifest.py`

**Interfaces:**
- Produces:
  - `export_manifest(db, slug: str) -> dict` —— 形如
    `{"museum": "orsay", "objects": [{"qid", "popularity", "category", "title_en", "images": [url, ...]}]}`；
    只含 `qid 非空且至少 1 张图` 的件；图 URL 规则：有 `image_key` 且 storage 可用 → `_sized(storage, key, "large")`，否则 `source_url`；按 `ObjectImage.sort` 排序。
  - CLI：`python -m scripts.recognition_bench.export_manifest orsay > manifest.json`（在 VPS 容器内跑，只读 DB）。
- Consumes: `app.services.museum_repo._sized`、`app.models.*`（既有）。

- [ ] **Step 1: 写失败测试**（fixture 模式抄 `tests/unit/services/recognition/test_matcher.py`：sqlite StaticPool + upsert_museum/upsert_object）

```python
"""manifest 导出:只含有图有qid的件;storage 不可用时回退 source_url。"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.models.artist import Artist
from app.models.museum import Museum
from app.models.museum_object import MuseumObject, ObjectImage
from app.services.object_importer import upsert_museum, upsert_object
from scripts.recognition_bench.export_manifest import export_manifest


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
            Artist.__table__,
        ],
    )
    s = sessionmaker(bind=engine)()
    m = upsert_museum(s, {"slug": "orsay", "name_en": "Orsay"})
    o1 = upsert_object(
        s, m.id, {"qid": "Q1", "title_en": "A", "category": "painting", "popularity": 9}
    )
    o2 = upsert_object(
        s, m.id, {"qid": "Q2", "title_en": "B", "category": "sculpture", "popularity": 5}
    )
    upsert_object(s, m.id, {"qid": "Q3", "title_en": "no-image", "popularity": 1})
    s.add(ObjectImage(object_id=o1.id, source_url="http://x/1.jpg", sort=0))
    s.add(ObjectImage(object_id=o1.id, source_url="http://x/2.jpg", sort=1))
    s.add(ObjectImage(object_id=o2.id, source_url="http://x/3.jpg", sort=0))
    s.commit()
    return s


def test_manifest_shape_and_filtering(session):
    m = export_manifest(session, "orsay")
    assert m["museum"] == "orsay"
    qids = [o["qid"] for o in m["objects"]]
    assert qids == ["Q1", "Q2"]  # popularity 降序;Q3 无图被滤掉
    assert m["objects"][0]["images"] == ["http://x/1.jpg", "http://x/2.jpg"]
    assert m["objects"][1]["category"] == "sculpture"
```

（注：若 `upsert_object` 不接受某字段名，以 `app/services/object_importer.py:59` 附近的字段白名单为准调整测试数据的构造方式，必要时直接构造 `MuseumObject` 行。）

- [ ] **Step 2: 跑测试确认失败**

```bash
cd backend && python -m pytest tests/unit/scripts/test_bench_export_manifest.py -v
```

预期：FAIL（模块不存在）。

- [ ] **Step 3: 最小实现**

```python
"""orsay 目录 → manifest.json(qid/popularity/category/图URL)。唯一碰 DB 的一步,只读。
在 VPS staging 容器内跑: python -m scripts.recognition_bench.export_manifest orsay。"""

from __future__ import annotations

import json
import sys

from app.models.museum import Museum
from app.models.museum_object import MuseumObject, ObjectImage
from app.services.museum_repo import _sized


def _storage():
    try:
        from app.services.storage import get_object_storage

        return get_object_storage()
    except Exception:
        return None  # 本地无 R2 配置时回退 source_url


def export_manifest(db, slug: str) -> dict:
    museum = db.query(Museum).filter_by(slug=slug).one()
    storage = _storage()
    objects = []
    rows = (
        db.query(MuseumObject)
        .filter_by(museum_id=museum.id)
        .order_by(MuseumObject.popularity.desc())
        .all()
    )
    for o in rows:
        if not o.qid:
            continue
        imgs = (
            db.query(ObjectImage)
            .filter_by(object_id=o.id)
            .order_by(ObjectImage.sort)
            .all()
        )
        urls = []
        for i in imgs:
            if i.image_key and storage:
                urls.append(_sized(storage, i.image_key, "large"))
            elif i.source_url:
                urls.append(i.source_url)
        if not urls:
            continue
        objects.append(
            {
                "qid": o.qid,
                "popularity": o.popularity or 0,
                "category": o.category,
                "title_en": o.title_en,
                "images": urls,
            }
        )
    return {"museum": slug, "objects": objects}


if __name__ == "__main__":
    from app.core.database import SessionLocal

    db = SessionLocal()
    try:
        print(json.dumps(export_manifest(db, sys.argv[1]), ensure_ascii=False))
    finally:
        db.close()
```

- [ ] **Step 4: 跑测试确认通过**

```bash
cd backend && python -m pytest tests/unit/scripts/test_bench_export_manifest.py -v
```

预期：1 passed。

- [ ] **Step 5: Commit**

```bash
git add backend/scripts/recognition_bench/export_manifest.py backend/tests/unit/scripts/test_bench_export_manifest.py
git commit -m "feat(bench): 目录manifest导出(只读DB,VPS容器内跑,storage缺失回退source_url)"
```

---

### Task 5: 测试集构建 build_testset.py

**Files:**
- Create: `backend/scripts/recognition_bench/build_testset.py`
- Test: `backend/tests/unit/scripts/test_bench_testset.py`（只测纯逻辑：分层抽样、分桶标注）

**Interfaces:**
- Produces:
  - `stratified_sample(objects: list[dict], n: int = 100, famous_cut: int = 200, famous_frac: float = 0.3, seed: int = 42) -> list[dict]`
    —— objects 已按 popularity 降序（manifest 顺序即是）；前 `famous_cut` 为名作池；返回 ~n 件，名作占 `famous_frac`；每件 dict 添加 `"fame": "famous"|"nonfamous"` 和 `"dim": "2d"|"3d"`（3D 类目集合见 Global Constraints）。某池不足时取该池全部，不跨池补齐。
  - CLI：`python -m scripts.recognition_bench.build_testset`
    —— 读 `data/manifest.json`，产出：
    - `data/testset/{qid}/real_{i}.jpg`（Commons 他人照片，每件 ≤5 张，排除该件已在 manifest 的参考图文件名）
    - `data/testset/{qid}/syn_{name}.jpg`（对官方图第一张跑 `distort_all`，5 张）
    - `data/ooc/{qid}.jpg`（卢浮宫 SPARQL 拉 60、排除 orsay qid、下载前 50）
    - `data/testset.json`：行形如 `{"path", "true_qid"(库外为 null), "source": "real"|"synthetic"|"ooc", "fame", "dim"}`
- Consumes: `distort.distort_all(img, seed)`（Task 2）。

- [ ] **Step 1: 写失败测试（纯逻辑部分）**

```python
"""分层抽样:名作线=前200;非名作占70%;fame/dim 标注。"""

from scripts.recognition_bench.build_testset import stratified_sample


def _objects(n):
    return [
        {"qid": f"Q{i}", "popularity": n - i, "category": "painting" if i % 2 else "sculpture", "images": ["u"]}
        for i in range(n)
    ]


def test_stratified_ratio_and_tags():
    sample = stratified_sample(_objects(1000), n=100, seed=42)
    famous = [o for o in sample if o["fame"] == "famous"]
    nonfamous = [o for o in sample if o["fame"] == "nonfamous"]
    assert len(sample) == 100 and len(famous) == 30 and len(nonfamous) == 70
    assert all(o["dim"] in ("2d", "3d") for o in sample)


def test_small_pool_takes_what_pools_allow():
    # 40 件全落名作池(前200):名作配额取 30,非名作池空 → 共 30
    sample = stratified_sample(_objects(40), n=100, seed=42)
    assert len(sample) == 30
    assert all(o["fame"] == "famous" for o in sample)


def test_deterministic():
    a = [o["qid"] for o in stratified_sample(_objects(1000), n=100, seed=42)]
    b = [o["qid"] for o in stratified_sample(_objects(1000), n=100, seed=42)]
    assert a == b
```

- [ ] **Step 2: 跑测试确认失败**

```bash
cd backend && python -m pytest tests/unit/scripts/test_bench_testset.py -v
```

预期：FAIL（模块不存在）。

- [ ] **Step 3: 实现**

```python
"""测试集构建:分层抽样(非名作70%) + Commons他人照片 + 合成畸变 + 库外干扰组。
网络部分(Commons/SPARQL/下载)幂等:文件已存在即跳过,可断点续跑。"""

from __future__ import annotations

import io
import json
import random
import time
from pathlib import Path

import requests
from PIL import Image

from scripts.recognition_bench.distort import distort_all

DATA = Path(__file__).parent / "data"
UA = {"User-Agent": "GoMuseumBench/1.0 (appcraft008@gmail.com)"}
_3D = {"sculpture", "decorative_arts", "textile", "artifact"}
WD_API = "https://www.wikidata.org/w/api.php"
COMMONS_API = "https://commons.wikimedia.org/w/api.php"
SPARQL = "https://query.wikidata.org/sparql"


def stratified_sample(objects, n=100, famous_cut=200, famous_frac=0.3, seed=42):
    rng = random.Random(seed)
    famous_pool, nonfamous_pool = objects[:famous_cut], objects[famous_cut:]
    n_famous = min(round(n * famous_frac), len(famous_pool))
    n_non = min(n - n_famous, len(nonfamous_pool))
    picked = rng.sample(famous_pool, n_famous) + rng.sample(nonfamous_pool, n_non)
    out = []
    for o in picked:
        fame = "famous" if o in famous_pool else "nonfamous"
        out.append(
            {**o, "fame": fame, "dim": "3d" if o["category"] in _3D else "2d"}
        )
    return out


def _get(url, **params):
    time.sleep(0.2)
    r = requests.get(url, params=params, headers=UA, timeout=30)
    r.raise_for_status()
    return r


def _download(url: str, dest: Path) -> bool:
    if dest.exists():
        return True
    try:
        r = _get(url)
        img = Image.open(io.BytesIO(r.content)).convert("RGB")
        img.thumbnail((1024, 1024))
        dest.parent.mkdir(parents=True, exist_ok=True)
        img.save(dest, "JPEG", quality=90)
        return True
    except Exception as e:  # 单张失败不断整体
        print(f"  skip {url}: {e}")
        return False


def commons_alt_photos(qid: str, max_n: int = 5) -> list[str]:
    """qid → P18 官方图文件名 + P373/commons 分类 → 分类内其他图片文件的缩略 URL。"""
    ent = _get(
        WD_API, action="wbgetentities", ids=qid, props="claims|sitelinks",
        format="json",
    ).json()["entities"][qid]
    claims = ent.get("claims", {})

    def _claim_str(pid):
        c = claims.get(pid)
        return c[0]["mainsnak"]["datavalue"]["value"] if c else None

    p18 = _claim_str("P18")
    cat = _claim_str("P373")
    if not cat:
        link = (ent.get("sitelinks") or {}).get("commonswiki", {}).get("title", "")
        cat = link.removeprefix("Category:") if link.startswith("Category:") else None
    if not cat:
        return []
    members = _get(
        COMMONS_API, action="query", list="categorymembers",
        cmtitle=f"Category:{cat}", cmtype="file", cmlimit=50, format="json",
    ).json()["query"]["categorymembers"]
    urls = []
    for m in members:
        title = m["title"]
        fname = title.removeprefix("File:")
        if p18 and fname.replace(" ", "_") == p18.replace(" ", "_"):
            continue  # 排除官方图本尊
        if not fname.lower().endswith((".jpg", ".jpeg", ".png")):
            continue
        info = _get(
            COMMONS_API, action="query", titles=title, prop="imageinfo",
            iiprop="url", iiurlwidth=1024, format="json",
        ).json()["query"]["pages"]
        page = next(iter(info.values()))
        ii = (page.get("imageinfo") or [{}])[0]
        if ii.get("thumburl"):
            urls.append(ii["thumburl"])
        if len(urls) >= max_n:
            break
    return urls


def louvre_distractors(exclude: set[str], n: int = 50) -> list[tuple[str, str]]:
    """卢浮宫(Q19675)有图画作 → [(qid, image_url)],排除 orsay 目录 qid。"""
    query = (
        "SELECT ?item ?image WHERE { ?item wdt:P195 wd:Q19675; wdt:P31 wd:Q3305213; "
        "wdt:P18 ?image } LIMIT 120"
    )
    rows = _get(SPARQL, query=query, format="json").json()["results"]["bindings"]
    out = []
    for r in rows:
        qid = r["item"]["value"].rsplit("/", 1)[-1]
        if qid in exclude:
            continue
        out.append((qid, r["image"]["value"]))
        if len(out) >= n:
            break
    return out


def main():
    manifest = json.loads((DATA / "manifest.json").read_text())
    objects = manifest["objects"]
    sample = stratified_sample(objects)
    rows = []
    for o in sample:
        qdir = DATA / "testset" / o["qid"]
        tags = {"true_qid": o["qid"], "fame": o["fame"], "dim": o["dim"]}
        # 真实游客照(Commons 他人照片;冷门件常为 0,如实分桶)
        try:
            for i, url in enumerate(commons_alt_photos(o["qid"])):
                dest = qdir / f"real_{i}.jpg"
                if _download(url, dest):
                    rows.append({"path": str(dest), "source": "real", **tags})
        except Exception as e:
            print(f"commons fail {o['qid']}: {e}")
        # 合成畸变(官方图第一张)
        ref = DATA / "testset" / o["qid"] / "_ref.jpg"
        if _download(o["images"][0], ref):
            img = Image.open(ref)
            for name, v in distort_all(img, seed=42).items():
                dest = qdir / f"syn_{name}.jpg"
                if not dest.exists():
                    v.save(dest, "JPEG", quality=90)
                rows.append({"path": str(dest), "source": "synthetic", **tags})
        print(f"{o['qid']} done ({len(rows)} rows)")
    # 库外干扰组
    exclude = {o["qid"] for o in objects}
    for qid, url in louvre_distractors(exclude):
        dest = DATA / "ooc" / f"{qid}.jpg"
        if _download(url, dest):
            rows.append(
                {"path": str(dest), "true_qid": None, "source": "ooc",
                 "fame": None, "dim": None}
            )
    (DATA / "testset.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1))
    print(f"testset.json: {len(rows)} rows")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: 跑测试确认通过**

```bash
cd backend && python -m pytest tests/unit/scripts/test_bench_testset.py -v
```

预期：3 passed。（网络部分不进单测，Task 9 实跑验证。）

- [ ] **Step 5: Commit**

```bash
git add backend/scripts/recognition_bench/build_testset.py backend/tests/unit/scripts/test_bench_testset.py
git commit -m "feat(bench): 测试集构建(分层抽样70%非名作+Commons游客照+合成畸变+卢浮库外组)"
```

---

### Task 6: ONNX 导出 + embedding 引擎 embed.py

**Files:**
- Create: `backend/scripts/recognition_bench/export_onnx.py`（一次性，torch/transformers 只在这里 import）
- Create: `backend/scripts/recognition_bench/embed.py`（onnxruntime 推理 + 预处理；预处理纯 numpy/PIL 可单测）
- Test: `backend/tests/unit/scripts/test_bench_embed.py`（只测预处理，不 import onnxruntime）

**Interfaces:**
- Produces:
  - `PRESETS: dict[str, dict]` —— `{"dinov2": {...}, "clip": {...}}`，含 resize/crop/mean/std。
  - `preprocess(img: Image.Image, preset: str) -> np.ndarray` —— [1,3,224,224] float32。
  - `class OnnxEmbedder: __init__(onnx_path: str, preset: str)`；`embed(img: Image.Image) -> np.ndarray` —— [D] float32 已 L2 单位化。onnxruntime 在 `__init__` 内 import（懒加载）。
  - CLI：`python -m scripts.recognition_bench.export_onnx` → `data/dinov2_vits14.onnx`、`data/clip_vitb32.onnx`。
- 预处理常量（写死，来源为两模型官方 processor 配置）：
  - dinov2：resize 短边 256 (BICUBIC) → center-crop 224 → mean `[0.485, 0.456, 0.406]`、std `[0.229, 0.224, 0.225]`
  - clip：resize 短边 224 (BICUBIC) → center-crop 224 → mean `[0.48145466, 0.4578275, 0.40821073]`、std `[0.26862954, 0.26130258, 0.27577711]`

- [ ] **Step 1: 写失败测试（预处理）**

```python
"""预处理:形状/归一化常量/确定性。不 import onnxruntime/torch。"""

import numpy as np
from PIL import Image

from scripts.recognition_bench.embed import PRESETS, preprocess


def test_shapes_and_dtype():
    img = Image.new("RGB", (500, 300), (128, 128, 128))
    for preset in PRESETS:
        x = preprocess(img, preset)
        assert x.shape == (1, 3, 224, 224) and x.dtype == np.float32


def test_normalization_applied():
    img = Image.new("RGB", (300, 300), (255, 255, 255))
    x = preprocess(img, "dinov2")
    expected = (1.0 - 0.485) / 0.229  # 白图 R 通道
    assert abs(float(x[0, 0, 0, 0]) - expected) < 1e-3
```

- [ ] **Step 2: 跑测试确认失败**

```bash
cd backend && python -m pytest tests/unit/scripts/test_bench_embed.py -v
```

预期：FAIL（模块不存在）。

- [ ] **Step 3: 实现 embed.py**

```python
"""embedding 引擎:ONNX CPU 推理 + 各模型预处理。接口 embed(img)->单位向量。
这块将来直接搬线上引擎位(spec ①);onnxruntime 懒 import,纯逻辑可无重依赖单测。"""

from __future__ import annotations

import numpy as np
from PIL import Image

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
    x = np.asarray(img, dtype=np.float32) / 255.0  # HWC
    x = (x - np.array(cfg["mean"], dtype=np.float32)) / np.array(
        cfg["std"], dtype=np.float32
    )
    return x.transpose(2, 0, 1)[None]  # 1CHW


class OnnxEmbedder:
    def __init__(self, onnx_path: str, preset: str):
        import onnxruntime as ort  # 懒加载:单测预处理不需要它

        self.preset = preset
        self.sess = ort.InferenceSession(
            onnx_path, providers=["CPUExecutionProvider"]
        )
        self.input_name = self.sess.get_inputs()[0].name

    def embed(self, img: Image.Image) -> np.ndarray:
        out = self.sess.run(None, {self.input_name: preprocess(img, self.preset)})
        v = out[0][0].astype(np.float32)
        return v / np.linalg.norm(v)
```

- [ ] **Step 4: 跑测试确认通过**

```bash
cd backend && python -m pytest tests/unit/scripts/test_bench_embed.py -v
```

预期：2 passed。

- [ ] **Step 5: 实现 export_onnx.py**

```python
"""一次性:HF transformers → 两个 ONNX(dinov2-small CLS 塔 / CLIP ViT-B/32 图像塔)。
torch/transformers 只许在本文件 import(bench group,不进生产)。"""

from __future__ import annotations

from pathlib import Path

import torch

DATA = Path(__file__).parent / "data"


class _Dinov2Wrap(torch.nn.Module):
    def __init__(self, m):
        super().__init__()
        self.m = m

    def forward(self, pixel_values):
        # last_hidden_state 已过最终 layernorm;[:,0]=CLS token(384维)
        return self.m(pixel_values=pixel_values).last_hidden_state[:, 0]


class _ClipWrap(torch.nn.Module):
    def __init__(self, m):
        super().__init__()
        self.m = m

    def forward(self, pixel_values):
        return self.m(pixel_values=pixel_values).image_embeds  # 512维投影

    
def _export(model, path: Path):
    model.eval()
    dummy = torch.zeros(1, 3, 224, 224)
    torch.onnx.export(
        model, dummy, str(path),
        input_names=["pixel_values"], output_names=["emb"],
        dynamic_axes={"pixel_values": {0: "b"}, "emb": {0: "b"}}, opset_version=17,
    )
    print(f"exported {path} ({path.stat().st_size/1e6:.0f} MB)")


def main():
    from transformers import AutoModel, CLIPVisionModelWithProjection

    DATA.mkdir(exist_ok=True)
    _export(
        _Dinov2Wrap(AutoModel.from_pretrained("facebook/dinov2-small")),
        DATA / "dinov2_vits14.onnx",
    )
    _export(
        _ClipWrap(
            CLIPVisionModelWithProjection.from_pretrained(
                "openai/clip-vit-base-patch32"
            )
        ),
        DATA / "clip_vitb32.onnx",
    )


if __name__ == "__main__":
    main()
```

- [ ] **Step 6: 实跑导出 + 自检（非 CI；需 `poetry install --with bench` 和联网拉权重）**

```bash
cd backend && poetry install --with bench
poetry run python -m scripts.recognition_bench.export_onnx
poetry run python -c "
from PIL import Image
from scripts.recognition_bench.embed import OnnxEmbedder
import numpy as np
for preset, path in [('dinov2','scripts/recognition_bench/data/dinov2_vits14.onnx'),('clip','scripts/recognition_bench/data/clip_vitb32.onnx')]:
    e = OnnxEmbedder(path, preset)
    img = Image.effect_noise((300,300), 64).convert('RGB')
    v1, v2 = e.embed(img), e.embed(img)
    assert v1.shape[0] in (384,512) and abs(np.linalg.norm(v1)-1) < 1e-5
    assert float(v1 @ v2) > 0.9999  # 同图自相似≈1
    print(preset, 'OK', v1.shape)
"
```

预期：两个 ONNX 文件生成（dinov2 约 85MB、clip 约 350MB），自检打印两行 OK。

- [ ] **Step 7: Commit**

```bash
git add backend/scripts/recognition_bench/embed.py backend/scripts/recognition_bench/export_onnx.py backend/tests/unit/scripts/test_bench_embed.py
git commit -m "feat(bench): ONNX导出(dinov2-s/clip-b32)+embedding引擎(onnxruntime懒加载,预处理可单测)"
```

---

### Task 7: 索引构建 build_index.py

**Files:**
- Create: `backend/scripts/recognition_bench/build_index.py`
- Test: `backend/tests/unit/scripts/test_bench_index.py`（npz 读写往返，用假 embedder）

**Interfaces:**
- Produces:
  - `build_index(manifest: dict, embed_fn, img_loader) -> tuple[np.ndarray, list[str]]` —— 遍历全目录所有参考图（不只抽样件），`embed_fn(Image)->vec`、`img_loader(url)->Image|None`（None 跳过）；返回 (vecs [N,D] float32, qids [N])。
  - `save_index(path, vecs, qids, model: str)` / `load_index(path) -> (vecs, qids, model)` —— np.savez_compressed，含 `model` 字段（向量版本化，spec 要求）。
  - CLI：`python -m scripts.recognition_bench.build_index dinov2|clip` —— 读 `data/manifest.json`，下载参考图缓存到 `data/refimgs/`（幂等），产出 `data/index_{preset}.npz`。

- [ ] **Step 1: 写失败测试**

```python
"""索引构建:全目录全图入索引;npz 读写往返带模型版本。"""

import numpy as np
from PIL import Image

from scripts.recognition_bench.build_index import build_index, load_index, save_index


def test_build_and_roundtrip(tmp_path):
    manifest = {
        "objects": [
            {"qid": "Q1", "images": ["u1", "u2"]},
            {"qid": "Q2", "images": ["u3", "bad"]},
        ]
    }
    fake_vec = {"u1": [1, 0], "u2": [0.9, 0.1], "u3": [0, 1]}
    urls_seen = []

    def loader(url):
        urls_seen.append(url)
        return Image.new("RGB", (8, 8)) if url != "bad" else None

    def embed(img):
        v = np.array(fake_vec[urls_seen[-1]], dtype=np.float32)  # loader 刚看过的 url
        return v / np.linalg.norm(v)

    vecs, qids = build_index(manifest, embed, loader)
    assert vecs.shape == (3, 2) and qids == ["Q1", "Q1", "Q2"]  # bad 被跳过

    p = tmp_path / "i.npz"
    save_index(p, vecs, qids, model="dinov2")
    v2, q2, m2 = load_index(p)
    assert np.allclose(v2, vecs) and q2 == qids and m2 == "dinov2"
```

- [ ] **Step 2: 跑测试确认失败**

```bash
cd backend && python -m pytest tests/unit/scripts/test_bench_index.py -v
```

预期：FAIL（模块不存在）。

- [ ] **Step 3: 实现**

```python
"""索引构建:manifest 全目录所有参考图 → 向量矩阵 .npz(带模型名版本化)。
每件全部 ObjectImage 入索引——多视角对雕塑关键(查询时同 qid 取最大分)。"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import numpy as np

DATA = Path(__file__).parent / "data"


def build_index(manifest: dict, embed_fn, img_loader):
    vecs, qids = [], []
    for o in manifest["objects"]:
        for url in o["images"]:
            img = img_loader(url)
            if img is None:
                continue
            vecs.append(embed_fn(img))
            qids.append(o["qid"])
    return np.stack(vecs).astype(np.float32), qids


def save_index(path, vecs, qids, model: str):
    np.savez_compressed(path, vecs=vecs, qids=np.array(qids), model=model)


def load_index(path):
    z = np.load(path, allow_pickle=False)
    return z["vecs"], [str(q) for q in z["qids"]], str(z["model"])


def _cached_loader():
    """URL → PIL.Image,磁盘缓存 data/refimgs/(幂等,断点续跑)。"""
    from PIL import Image

    from scripts.recognition_bench.build_testset import _download

    refdir = DATA / "refimgs"

    def load(url):
        dest = refdir / (hashlib.sha1(url.encode()).hexdigest()[:16] + ".jpg")
        if _download(url, dest):
            return Image.open(dest)
        return None

    return load


def main():
    preset = sys.argv[1]  # dinov2 | clip
    from scripts.recognition_bench.embed import OnnxEmbedder

    onnx = {"dinov2": "dinov2_vits14.onnx", "clip": "clip_vitb32.onnx"}[preset]
    embedder = OnnxEmbedder(str(DATA / onnx), preset)
    manifest = json.loads((DATA / "manifest.json").read_text())
    vecs, qids = build_index(manifest, embedder.embed, _cached_loader())
    save_index(DATA / f"index_{preset}.npz", vecs, qids, model=preset)
    print(f"index_{preset}.npz: {vecs.shape[0]} vecs, {len(set(qids))} objects")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: 跑测试确认通过**

```bash
cd backend && python -m pytest tests/unit/scripts/test_bench_index.py -v
```

预期：1 passed。

- [ ] **Step 5: Commit**

```bash
git add backend/scripts/recognition_bench/build_index.py backend/tests/unit/scripts/test_bench_index.py
git commit -m "feat(bench): 索引构建(全目录全参考图入索引,npz带模型版本,下载幂等)"
```

---

### Task 8: 评测与报告 run_eval.py

**Files:**
- Create: `backend/scripts/recognition_bench/run_eval.py`
- Test: `backend/tests/unit/scripts/test_bench_eval.py`（合成向量端到端小样）

**Interfaces:**
- Produces:
  - `evaluate(index: tuple[np.ndarray, list[str]], queries: list[dict]) -> dict`
    —— queries 行：`{"vec": np.ndarray, "true_qid": str|None, "source", "fame", "dim", "ms": float}`；
    返回：
    ```python
    {"buckets": {bucket_key: {"n", "top1", "top3"}},   # bucket_key 如 "real|famous|2d"、"ALL"、"fame=nonfamous"
     "sweep": [...],            # metrics.sweep 输出(库内正确top1分 vs 库外top1分)
     "margin_p50": float, "margin_p10": float,
     "latency_p50_ms": float, "latency_p95_ms": float,
     "verdict": {"top1_ok": bool, "top3_ok": bool, "ooc_ok": bool,
                 "nonfamous_ok": bool, "pass": bool, "chosen_threshold": float|None}}
    ```
    verdict 规则：在 sweep 里找满足 `ooc_accept_rate ≤ 0.05` 的最低阈值 t；`pass` = 全体 Top-1≥0.85 且 Top-3≥0.95 且存在这样的 t，且 `fame=nonfamous` 桶单独 Top-1≥0.85、Top-3≥0.95。
  - `render_report(results: dict, preset: str) -> str`（markdown）。
  - CLI：`python -m scripts.recognition_bench.run_eval dinov2|clip` —— 读 `data/index_{preset}.npz` + `data/testset.json`，嵌入所有测试照（计时），写 `data/report_{preset}.md` 并打印 verdict。
- Consumes: `metrics.rank/topk_hit/sweep/margins/pctl`（Task 3）、`build_index.load_index`（Task 7）、`embed.OnnxEmbedder`（Task 6）。

- [ ] **Step 1: 写失败测试**

```python
"""评测:合成向量端到端——分桶指标/阈值裁决/非名作单独达标逻辑。"""

import numpy as np

from scripts.recognition_bench.run_eval import evaluate


def _u(v):
    v = np.asarray(v, dtype=np.float32)
    return v / np.linalg.norm(v)


def test_evaluate_verdict_pass():
    index = (np.stack([_u([1, 0]), _u([0, 1])]), ["Q1", "Q2"])
    queries = [
        {"vec": _u([0.99, 0.01]), "true_qid": "Q1", "source": "real",
         "fame": "famous", "dim": "2d", "ms": 100.0},
        {"vec": _u([0.02, 0.98]), "true_qid": "Q2", "source": "synthetic",
         "fame": "nonfamous", "dim": "3d", "ms": 120.0},
        {"vec": _u([0.6, 0.6]), "true_qid": None, "source": "ooc",
         "fame": None, "dim": None, "ms": 90.0},  # 库外:top1=cos45°≈0.707
    ]
    r = evaluate(index, queries)
    assert r["buckets"]["ALL"]["top1"] == 1.0
    assert r["buckets"]["fame=nonfamous"]["top1"] == 1.0
    assert r["verdict"]["nonfamous_ok"] is True
    assert r["latency_p50_ms"] == 100.0
    # 库外 top1≈0.707 → 压住误接受的最低阈值档 = 0.75;库内分都>0.97 → pass
    assert r["verdict"]["pass"] is True and r["verdict"]["chosen_threshold"] == 0.75


def test_evaluate_fails_when_nonfamous_bucket_bad():
    index = (np.stack([_u([1, 0]), _u([0, 1])]), ["Q1", "Q2"])
    queries = [
        {"vec": _u([0.99, 0.01]), "true_qid": "Q1", "source": "real",
         "fame": "famous", "dim": "2d", "ms": 100.0},
        {"vec": _u([0.99, 0.01]), "true_qid": "Q2", "source": "synthetic",
         "fame": "nonfamous", "dim": "2d", "ms": 100.0},  # 非名作认错
    ]
    r = evaluate(index, queries)
    assert r["verdict"]["nonfamous_ok"] is False and r["verdict"]["pass"] is False
```

- [ ] **Step 2: 跑测试确认失败**

```bash
cd backend && python -m pytest tests/unit/scripts/test_bench_eval.py -v
```

预期：FAIL（模块不存在）。

- [ ] **Step 3: 实现**

```python
"""评测:测试集 → 分桶指标 + 阈值扫 + 判定(spec ⑤:非名作桶必须单独达标) + markdown 报告。"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np

from scripts.recognition_bench.metrics import margins, pctl, rank, sweep, topk_hit

DATA = Path(__file__).parent / "data"
TOP1_LINE, TOP3_LINE, OOC_LINE = 0.85, 0.95, 0.05


def _bucket_stats(rows):
    n = len(rows)
    return {
        "n": n,
        "top1": sum(r["hit1"] for r in rows) / n if n else None,
        "top3": sum(r["hit3"] for r in rows) / n if n else None,
    }


def evaluate(index, queries):
    vecs, qids = index
    in_rows, ooc_top1, ranked_all, lat = [], [], [], []
    for q in queries:
        ranked = rank(q["vec"], vecs, qids)
        lat.append(q["ms"])
        if q["true_qid"] is None:
            ooc_top1.append(ranked[0][1] if ranked else 0.0)
            continue
        ranked_all.append(ranked)
        in_rows.append(
            {**q,
             "top1_score": ranked[0][1] if ranked else 0.0,
             "hit1": topk_hit(ranked, q["true_qid"], 1),
             "hit3": topk_hit(ranked, q["true_qid"], 3)}
        )
    buckets = {"ALL": _bucket_stats(in_rows)}
    for key in ("source", "fame", "dim"):
        for val in sorted({r[key] for r in in_rows if r[key]}):
            buckets[f"{key}={val}"] = _bucket_stats(
                [r for r in in_rows if r[key] == val]
            )
    for r in in_rows:  # 组合桶(报告矩阵用)
        combo = f"{r['source']}|{r['fame']}|{r['dim']}"
        buckets.setdefault(combo, _bucket_stats(
            [x for x in in_rows if f"{x['source']}|{x['fame']}|{x['dim']}" == combo]
        ))
    correct_top1 = [r["top1_score"] for r in in_rows if r["hit1"]]
    sw = sweep(correct_top1, ooc_top1)
    chosen = next(
        (row["threshold"] for row in sw if row["ooc_accept_rate"] <= OOC_LINE), None
    )
    mg = margins(ranked_all)
    nf = buckets.get("fame=nonfamous") or {"top1": None, "top3": None}
    verdict = {
        "top1_ok": (buckets["ALL"]["top1"] or 0) >= TOP1_LINE,
        "top3_ok": (buckets["ALL"]["top3"] or 0) >= TOP3_LINE,
        "ooc_ok": chosen is not None,
        "nonfamous_ok": (nf["top1"] or 0) >= TOP1_LINE and (nf["top3"] or 0) >= TOP3_LINE,
        "chosen_threshold": chosen,
    }
    verdict["pass"] = all(
        verdict[k] for k in ("top1_ok", "top3_ok", "ooc_ok", "nonfamous_ok")
    )
    return {
        "buckets": buckets, "sweep": sw,
        "margin_p50": pctl(mg, 50) if mg else None,
        "margin_p10": pctl(mg, 10) if mg else None,
        "latency_p50_ms": pctl(lat, 50) if lat else None,
        "latency_p95_ms": pctl(lat, 95) if lat else None,
        "verdict": verdict,
    }


def render_report(results: dict, preset: str) -> str:
    v = results["verdict"]
    lines = [
        f"# recognition bench report — {preset}",
        "",
        f"**verdict: {'PASS ✅' if v['pass'] else 'FAIL ❌'}** "
        f"(top1_ok={v['top1_ok']} top3_ok={v['top3_ok']} ooc_ok={v['ooc_ok']} "
        f"nonfamous_ok={v['nonfamous_ok']} chosen_threshold={v['chosen_threshold']})",
        "",
        f"margin p50={results['margin_p50']} p10={results['margin_p10']} | "
        f"latency p50={results['latency_p50_ms']}ms p95={results['latency_p95_ms']}ms",
        "",
        "| bucket | n | top1 | top3 |", "|---|---|---|---|",
    ]
    for k, b in results["buckets"].items():
        t1 = f"{b['top1']:.3f}" if b["top1"] is not None else "-"
        t3 = f"{b['top3']:.3f}" if b["top3"] is not None else "-"
        lines.append(f"| {k} | {b['n']} | {t1} | {t3} |")
    lines += ["", "| threshold | in_accept | ooc_accept |", "|---|---|---|"]
    for row in results["sweep"]:
        lines.append(
            f"| {row['threshold']:.2f} | {row['in_accept_rate']:.3f} "
            f"| {row['ooc_accept_rate']:.3f} |"
        )
    return "\n".join(lines) + "\n"


def main():
    preset = sys.argv[1]
    from PIL import Image

    from scripts.recognition_bench.build_index import load_index
    from scripts.recognition_bench.embed import OnnxEmbedder

    onnx = {"dinov2": "dinov2_vits14.onnx", "clip": "clip_vitb32.onnx"}[preset]
    embedder = OnnxEmbedder(str(DATA / onnx), preset)
    vecs, qids, model = load_index(DATA / f"index_{preset}.npz")
    assert model == preset, f"index model {model} != {preset}"
    rows = json.loads((DATA / "testset.json").read_text())
    queries = []
    for r in rows:
        if r["path"].endswith("_ref.jpg"):
            continue  # 官方图本尊不当查询
        img = Image.open(r["path"])
        t0 = time.perf_counter()
        vec = embedder.embed(img)
        queries.append(
            {**r, "vec": vec, "ms": (time.perf_counter() - t0) * 1000}
        )
    results = evaluate((vecs, qids), queries)
    report = render_report(results, preset)
    (DATA / f"report_{preset}.md").write_text(report)
    print(report)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: 跑测试确认通过**

```bash
cd backend && python -m pytest tests/unit/scripts/test_bench_eval.py -v
```

预期：2 passed。

- [ ] **Step 5: 全量单测回归 + Commit**

```bash
cd backend && python -m pytest tests/unit/scripts/ -v
git add backend/scripts/recognition_bench/run_eval.py backend/tests/unit/scripts/test_bench_eval.py
git commit -m "feat(bench): 评测与报告(分桶指标/阈值扫/非名作单独达标裁决/markdown)"
```

---

### Task 9: 实跑 benchmark 并出结论

（本 task 全是运行与记录，无新代码；网络/耗时步骤失败按幂等设计续跑。）

**Files:**
- 产物：`backend/scripts/recognition_bench/data/report_dinov2.md`、`report_clip.md`（gitignored，结论摘录进 spec）
- Modify: `docs/superpowers/specs/2026-07-11-recognition-embedding-bench-design.md`（追加"结果与裁决"节）

- [ ] **Step 1: VPS 导出 manifest**（staging 容器内跑，只读；容器名以 VPS 上 `docker ps` 实际为准）

```bash
ssh -i ~/.ssh/deepmeeting_deploy root@38.242.207.219 \
  "docker exec \$(docker ps --format '{{.Names}}' | grep -i 'staging.*api\|api.*staging' | head -1) \
   python -m scripts.recognition_bench.export_manifest orsay" \
  > backend/scripts/recognition_bench/data/manifest.json
python3 -c "import json;m=json.load(open('backend/scripts/recognition_bench/data/manifest.json'));print(len(m['objects']),'objects')"
```

预期：objects 数上千（orsay 全目录有图件）。若 staging 容器缺该模块（代码未部署），先 `git push` 分支后在 VPS 上 `docker cp` 单文件进容器再跑——只读脚本，无风险。

- [ ] **Step 2: 构建测试集**

```bash
cd backend && poetry run python -m scripts.recognition_bench.build_testset
```

预期：`data/testset.json` 数百行；打印各件进度。Commons 拉不到照片的冷门件只有 syn_* 行——正常。

- [ ] **Step 3: 双模型建索引**

```bash
cd backend && poetry run python -m scripts.recognition_bench.build_index dinov2
poetry run python -m scripts.recognition_bench.build_index clip
```

预期：两个 npz；打印向量数/对象数（≈manifest 图总数）。

- [ ] **Step 4: 双模型评测**

```bash
cd backend && poetry run python -m scripts.recognition_bench.run_eval dinov2
poetry run python -m scripts.recognition_bench.run_eval clip
```

预期：两份 report_*.md + 终端 verdict。

- [ ] **Step 5: VPS 同级 CPU 延迟抽测**（spec 要求延迟在 VPS 级环境测；一次性容器，不装进 staging）

```bash
scp -i ~/.ssh/deepmeeting_deploy \
  backend/scripts/recognition_bench/data/dinov2_vits14.onnx \
  backend/scripts/recognition_bench/embed.py \
  root@38.242.207.219:/tmp/bench/
ssh -i ~/.ssh/deepmeeting_deploy root@38.242.207.219 \
  "docker run --rm -v /tmp/bench:/b python:3.11-slim bash -c '
   pip -q install onnxruntime pillow numpy &&
   python - <<PY
import sys, time
sys.path.insert(0, \"/b\")
from PIL import Image
from embed import OnnxEmbedder
e = OnnxEmbedder(\"/b/dinov2_vits14.onnx\", \"dinov2\")
img = Image.new(\"RGB\", (800, 600), (100, 100, 100))
ts = []
for _ in range(20):
    t0 = time.perf_counter(); e.embed(img); ts.append((time.perf_counter()-t0)*1000)
ts.sort(); print(f\"VPS p50={ts[10]:.0f}ms p95={ts[18]:.0f}ms\")
PY'"
ssh -i ~/.ssh/deepmeeting_deploy root@38.242.207.219 "rm -rf /tmp/bench"
```

预期：p50 在几百 ms 内（spec 资源账预估 50-300ms 级）。

- [ ] **Step 6: 结论回写 spec 并提交**

spec 末尾追加"## 结果与裁决（2026-07-XX 实测）"：两模型分桶指标表、选定阈值（HIGH/LOW 对应 chosen_threshold 与 margin 分布）、VPS 延迟、PASS/FAIL、失败案例主因（若 FAIL：按渐进路线列下一步）。

```bash
git add docs/superpowers/specs/2026-07-11-recognition-embedding-bench-design.md
git commit -m "docs(bench): benchmark 实测结果与裁决(DINOv2 vs CLIP,阈值校准,VPS延迟)"
```

- [ ] **Step 7: 汇报用户**

报告要点：两模型对比结论、非名作桶表现、3D 桶表现、建议阈值、是否过线进入"接引擎位"轮。**staging→prod/合并动作留给用户**（见 autonomy-preference）。
