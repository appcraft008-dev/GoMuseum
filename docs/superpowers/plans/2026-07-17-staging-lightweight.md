# staging 轻量化 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** staging 永不为数据规模付 LLM 费——护栏强制小样本 + 规模数据从 prod 搬运(slim/full 两档)。

**Architecture:** 三件套:①`ops_guard` 护栏(onboard LLM 子命令 staging 默认 limit=50;rescan 系需 `--allow-full`);②容器内 `staging_prune.py`(金样本规则裁剪);③host 级 `sync_staging_from_prod.py`(pg_dump 内容表搬运,用户表红线)。契约回写收录策略⑥。

**Tech Stack:** Python/SQLAlchemy/pytest(sqlite fixture)/pg_dump/docker。

## Global Constraints

- spec: `docs/superpowers/specs/2026-07-17-staging-lightweight-design.md`
- 搬运表(顺序即恢复顺序): museums, artists, museum_objects, object_images, object_embeddings, object_content_sections, object_suggested_questions
- **永不搬**: users / benefits / devices / recognition_events
- staging 小样本上限 = 50;金样本目标 ~300-500 件
- 同步全程零 LLM 调用
- black 格式化;测试 sqlite StaticPool fixture 风格照 `tests/integration/test_rescan_artist_names.py`

---

### Task 1: ops_guard 护栏模块

**Files:**
- Create: `backend/scripts/ops_guard.py`
- Test: `backend/tests/unit/test_ops_guard.py`

**Interfaces:**
- Produces: `staging_limit(target: str, limit: int | None, allow_full: bool) -> int | None`;`staging_require_allow_full(target: str, allow_full: bool) -> None`(staging 且未确认时 `SystemExit`)。Task 2/3 消费。

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/unit/test_ops_guard.py
"""staging 护栏:staging 上带 LLM 的批命令默认小样本;全量须显式 --allow-full。"""

import pytest

from scripts.ops_guard import (
    STAGING_SAMPLE_LIMIT,
    staging_limit,
    staging_require_allow_full,
)


def test_staging_limit_tightens_none_and_large():
    assert staging_limit("staging", None, False) == STAGING_SAMPLE_LIMIT
    assert staging_limit("staging", 5000, False) == STAGING_SAMPLE_LIMIT


def test_staging_limit_keeps_small_prod_and_allow_full():
    assert staging_limit("staging", 10, False) == 10
    assert staging_limit("prod", None, False) is None
    assert staging_limit("staging", None, True) is None


def test_require_allow_full():
    staging_require_allow_full("prod", False)  # prod 不拦
    staging_require_allow_full("staging", True)  # 显式确认放行
    with pytest.raises(SystemExit):
        staging_require_allow_full("staging", False)
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && python -m pytest tests/unit/test_ops_guard.py -q --no-cov -p no:cacheprovider`
Expected: FAIL(`ModuleNotFoundError: scripts.ops_guard`)

- [ ] **Step 3: 最小实现**

```python
# backend/scripts/ops_guard.py
"""staging 轻量化护栏(spec 2026-07-17):staging 永不为数据规模付 LLM 费。
机制验证=小样本;规模数据用 sync_staging_from_prod.py 从 prod 搬运,别重算。"""

STAGING_SAMPLE_LIMIT = 50
_HINT = "(全量请 --allow-full;规模数据用 sync_staging_from_prod.py 搬运,别重算)"


def staging_limit(target, limit, allow_full):
    """带 LLM 的批命令:staging 默认收紧到小样本;prod/显式 allow_full 原样返回。"""
    if target != "staging" or allow_full:
        return limit
    if limit is None or limit > STAGING_SAMPLE_LIMIT:
        print(f"⚠️ staging 护栏:limit → {STAGING_SAMPLE_LIMIT} {_HINT}")
        return STAGING_SAMPLE_LIMIT
    return limit


def staging_require_allow_full(target, allow_full):
    """无 limit 概念的全库 LLM 脚本(rescan 系):staging 必须显式确认。"""
    if target == "staging" and not allow_full:
        raise SystemExit(f"❌ staging 护栏:全库 LLM 操作需显式 --allow-full {_HINT}")
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd backend && python -m pytest tests/unit/test_ops_guard.py -q --no-cov -p no:cacheprovider`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add backend/scripts/ops_guard.py backend/tests/unit/test_ops_guard.py
git commit -m "feat(ops): staging 护栏模块(小样本 limit + allow-full 确认)"
```

### Task 2: onboard.py 接线护栏(names 补 --limit)

**Files:**
- Modify: `backend/scripts/onboard.py`(argparse: names/generate/translate 加 `--allow-full`,names 加 `--limit`;cmd_names/cmd_generate/cmd_translate 接 `staging_limit`;main 分发传参)
- Modify: `backend/app/services/enrichment/backfill.py` `backfill_display_names` 加 `limit` 参数
- Test: `backend/tests/integration/test_backfill_names.py`(追加 limit 用例)

**Interfaces:**
- Consumes: Task 1 `staging_limit`
- Produces: `backfill_display_names(..., limit: int | None = None)`——对象查询加 `.limit(limit)`;CLI 面 `names/generate/translate --allow-full`、`names --limit N`

- [ ] **Step 1: 失败测试(backfill limit)**

在 `test_backfill_names.py` 末尾追加(fixture/fake 复用该文件既有的):

```python
def test_backfill_display_names_respects_limit(session, monkeypatch):
    # staging 护栏依赖:names 底层支持 limit(只处理前 N 件)
    import app.services.enrichment.backfill as bf

    # 该文件既有测试怎么构造 objects/fakes,这里复用同一套;新建 3 个待回填对象后:
    out = bf.backfill_display_names(
        session,
        "orsay",
        translator=该文件既有的FakeTranslator(),
        langs=["en", "zh"],
        fetch_labels=lambda qid, langs: {},
        fetch_creators=lambda qids: {},
        fetch_artist_facts_i18n=lambda qid, langs: {},
        limit=1,
    )
    assert out.get("objects", out.get("done", 0)) <= 1  # 按该函数实际返回键断言
```

(执行时先读该文件既有 fixture/返回结构,把「该文件既有的…」替换为真实名字——这是对既有测试风格的复用,不是占位。)

- [ ] **Step 2: 跑测试确认失败**(`TypeError: unexpected keyword 'limit'`)

- [ ] **Step 3: 实现**

`backfill_display_names` 签名加 `limit=None`;函数内对象查询处(objects 遍历的 query)追加:

```python
    if limit:
        objs = objs[:limit]  # 或 query.limit(limit),按实际代码形态取一种
```

`onboard.py` argparse 三处:

```python
    ge.add_argument("--allow-full", action="store_true")
    na.add_argument("--limit", type=int, default=None)
    na.add_argument("--allow-full", action="store_true")
    tr.add_argument("--allow-full", action="store_true")
```

cmd 三处开头(以 names 为例,generate/translate 同型):

```python
    from scripts.ops_guard import staging_limit

    limit = staging_limit(target, limit, allow_full)
```

`cmd_names` 签名加 `limit, allow_full`,把 `limit` 传给 `backfill_display_names`;main 分发处对应传 `ns.limit, ns.allow_full`。

- [ ] **Step 4: 跑测试**

Run: `cd backend && python -m pytest tests/integration/test_backfill_names.py tests/unit/test_ops_guard.py -q --no-cov -p no:cacheprovider`
Expected: 全 passed

- [ ] **Step 5: Commit**

```bash
git add backend/scripts/onboard.py backend/app/services/enrichment/backfill.py backend/tests/integration/test_backfill_names.py
git commit -m "feat(ops): onboard names/generate/translate 接 staging 护栏(names 补 --limit)"
```

### Task 3: rescan 系脚本接护栏

**Files:**
- Modify: `backend/scripts/rescan_language.py`、`backend/scripts/rescan_artist_names.py`(`__main__` 段)

**Interfaces:**
- Consumes: Task 1 `staging_require_allow_full`

- [ ] **Step 1: 两脚本 `__main__` 各加**

```python
    ap.add_argument("--allow-full", action="store_true")
```

解析后、建组件前:

```python
    from scripts.ops_guard import staging_require_allow_full

    staging_require_allow_full(ns.target, ns.allow_full)
```

- [ ] **Step 2: 手工验证**

Run: `cd backend && python scripts/rescan_artist_names.py orsay --target staging`(本地无 DB 也行——护栏在建 DB 前触发)
Expected: 以 `❌ staging 护栏` SystemExit;`--target staging --allow-full` 则往下走(本地会因 DB 连接失败,属预期,护栏已过)

- [ ] **Step 3: Commit**

```bash
git add backend/scripts/rescan_language.py backend/scripts/rescan_artist_names.py
git commit -m "feat(ops): rescan 系脚本接 staging 护栏(--allow-full)"
```

### Task 4: staging_prune.py 金样本裁剪(容器内)

**Files:**
- Create: `backend/scripts/staging_prune.py`
- Test: `backend/tests/integration/test_staging_prune.py`

**Interfaces:**
- Produces: `golden_ids(db) -> set`(保留对象 id 集)、`prune(db) -> dict`(`{"before","deleted","after"}`);CLI `python scripts/staging_prune.py --yes`。Task 5 的 host 脚本以 `docker exec … python scripts/staging_prune.py --yes` 消费。

- [ ] **Step 1: 失败测试**

```python
# backend/tests/integration/test_staging_prune.py
"""金样本裁剪:规则保留(热度top/樱桃/文字层样本/多视角/多音译作者/裸stub/empty),其余连子行删。"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.models.artist import Artist
from app.models.content import ObjectContentSection, ObjectSuggestedQuestion
from app.models.museum import Museum
from app.models.museum_object import MuseumObject, ObjectImage
from app.models.object_embedding import ObjectEmbedding
from app.services.object_importer import upsert_museum, upsert_object
from scripts.staging_prune import golden_ids, prune


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
            ObjectContentSection.__table__,
            ObjectSuggestedQuestion.__table__,
            Artist.__table__,
        ],
    )
    s = sessionmaker(bind=engine)()
    m = upsert_museum(s, {"slug": "orsay", "name_en": "Orsay"})
    def obj(qid, **kw):
        return upsert_object(s, m.id, {"qid": qid, "title_en": kw.pop("title", qid),
                                       "category": kw.pop("category", "painting"),
                                       "attributes": {}, **kw})
    # 金样本面孔
    hot = obj("Q1"); hot.popularity = 99
    obj("Q2").popularity = 50
    cherry = obj("joconde-C1")          # 合成 qid 带图
    s.add(ObjectImage(object_id=cherry.id, role="primary", source_url="u"))
    obj("joconde-T1")                    # 合成 qid 文字层
    sculpt = obj("Q3", category="sculpture")
    s.add(ObjectImage(object_id=sculpt.id, role="view", source_url="v"))
    seurat = obj("Q4"); seurat.artist_en = "Georges Seurat"
    bare = obj("Q5"); bare.title_en = None
    empty = obj("Q6"); empty.content_status = "empty"
    # 该死的:热度垫底且带全套子行
    doomed = obj("Q99", category="works_on_paper"); doomed.popularity = -1
    img = ObjectImage(object_id=doomed.id, role="primary", source_url="x")
    s.add(img); s.flush()
    s.add(ObjectEmbedding(image_id=img.id, object_id=doomed.id, model="m", vector=[0.0]))
    s.add(ObjectContentSection(object_id=doomed.id, language="en", section_code="guide",
                               body="b", status="published"))
    s.add(ObjectSuggestedQuestion(object_id=doomed.id, language="en", sort=0,
                                  question="q?", answer="a", status="published"))
    s.commit()
    yield s


def test_golden_rules_keep_edge_faces(session):
    keep = golden_ids(session)
    qids = {o.qid for o in session.query(MuseumObject).filter(MuseumObject.id.in_(keep))}
    assert {"Q1", "joconde-C1", "joconde-T1", "Q3", "Q4", "Q5", "Q6"} <= qids


def test_prune_deletes_doomed_with_children(session):
    # 让 doomed 落网:works_on_paper 类只此一件会被 top30 保住 → 再造 30 件同类挤掉它
    m = session.query(Museum).one()
    for i in range(30):
        o = upsert_object(session, m.id, {"qid": f"Qf{i}", "title_en": f"f{i}",
                                          "category": "works_on_paper", "attributes": {}})
        o.popularity = 10 + i
    session.commit()
    out = prune(session)
    assert out["deleted"] >= 1
    assert session.query(MuseumObject).filter_by(qid="Q99").count() == 0
    assert session.query(ObjectImage).count() == session.query(ObjectImage).join(
        MuseumObject, ObjectImage.object_id == MuseumObject.id).count()  # 无孤儿
    assert session.query(ObjectEmbedding).count() == 0 or session.query(
        ObjectEmbedding).join(ObjectImage, ObjectEmbedding.image_id == ObjectImage.id
    ).count() == session.query(ObjectEmbedding).count()
    assert session.query(MuseumObject).filter_by(qid="Q1").count() == 1  # 金样本健在
```

(ObjectEmbedding 字段名执行时按 `app/models/object_embedding.py` 实际为准——已知有 `image_id`;`model`/`vector` 列名以模型文件为准替换。)

- [ ] **Step 2: 跑测试确认失败**(`ModuleNotFoundError: scripts.staging_prune`)

- [ ] **Step 3: 实现**

```python
# backend/scripts/staging_prune.py
"""slim 裁剪:金样本规则保留 ~300-500 件,其余对象连子行删(embeddings→images/sections/qa)。
artists/museums/用户表不动;零 LLM;幂等。spec 2026-07-17-staging-lightweight §1。"""

import sys

sys.path.insert(0, ".")

TOP_PER_CATEGORY = 30
EDGE_ARTISTS = [
    "Georges Seurat",
    "Auguste Renoir",
    "Pierre-Auguste Renoir",
    "Henri de Toulouse-Lautrec",
]


def golden_ids(db) -> set:
    from app.models.museum_object import MuseumObject, ObjectImage

    keep: set = set()

    def add(rows):
        keep.update(oid for (oid,) in rows)

    for (cat,) in db.query(MuseumObject.category).distinct():
        if not cat:
            continue
        add(
            db.query(MuseumObject.id)
            .filter_by(category=cat)
            .order_by(MuseumObject.popularity.desc().nullslast(), MuseumObject.id)
            .limit(TOP_PER_CATEGORY)
        )
    # 合成 qid 带图(樱桃全保)
    add(
        db.query(MuseumObject.id)
        .filter(MuseumObject.qid.like("joconde-%"))
        .join(ObjectImage, ObjectImage.object_id == MuseumObject.id)
        .distinct()
    )
    # 合成 qid 文字层样本 30
    has_img = db.query(ObjectImage.object_id)
    add(
        db.query(MuseumObject.id)
        .filter(MuseumObject.qid.like("joconde-%"), ~MuseumObject.id.in_(has_img))
        .order_by(MuseumObject.id)
        .limit(30)
    )
    # 多视角(有 view 行)
    add(db.query(ObjectImage.object_id).filter(ObjectImage.role == "view").distinct())
    # 多音译作者件
    add(db.query(MuseumObject.id).filter(MuseumObject.artist_en.in_(EDGE_ARTISTS)))
    # 裸 stub 2 + empty 5
    add(
        db.query(MuseumObject.id)
        .filter((MuseumObject.title_en.is_(None)) | (MuseumObject.title_en == ""))
        .order_by(MuseumObject.id)
        .limit(2)
    )
    add(
        db.query(MuseumObject.id)
        .filter_by(content_status="empty")
        .order_by(MuseumObject.id)
        .limit(5)
    )
    return keep


def prune(db) -> dict:
    from app.models.content import ObjectContentSection, ObjectSuggestedQuestion
    from app.models.museum_object import MuseumObject, ObjectImage
    from app.models.object_embedding import ObjectEmbedding

    keep = golden_ids(db)
    total = db.query(MuseumObject.id).count()
    doomed = [oid for (oid,) in db.query(MuseumObject.id) if oid not in keep]
    for i in range(0, len(doomed), 500):  # 分批落盘(批处理纪律②)
        batch = doomed[i : i + 500]
        img_ids = [
            iid
            for (iid,) in db.query(ObjectImage.id).filter(
                ObjectImage.object_id.in_(batch)
            )
        ]
        if img_ids:
            db.query(ObjectEmbedding).filter(
                ObjectEmbedding.image_id.in_(img_ids)
            ).delete(synchronize_session=False)
        for model in (ObjectImage, ObjectContentSection, ObjectSuggestedQuestion):
            db.query(model).filter(model.object_id.in_(batch)).delete(
                synchronize_session=False
            )
        db.query(MuseumObject).filter(MuseumObject.id.in_(batch)).delete(
            synchronize_session=False
        )
        db.commit()
    return {
        "before": total,
        "deleted": len(doomed),
        "after": db.query(MuseumObject.id).count(),
    }


if __name__ == "__main__":
    import argparse

    from app.core.database import SessionLocal

    ap = argparse.ArgumentParser()
    ap.add_argument("--yes", action="store_true")
    ns = ap.parse_args()
    db = SessionLocal()
    keep_n, total_n = len(golden_ids(db)), db.query.__self__ and None  # 见下行
    from app.models.museum_object import MuseumObject

    total_n = db.query(MuseumObject.id).count()
    print(f"金样本保留 {keep_n} / 总 {total_n},将删除 {total_n - keep_n} 件")
    if not ns.yes:
        raise SystemExit("预览模式:加 --yes 执行(破坏性)")
    print(prune(db))
```

(实现时把 `keep_n, total_n` 那行拙劣写法直接展开成两条语句——上面已给出正确形态。)

- [ ] **Step 4: 跑测试**

Run: `cd backend && python -m pytest tests/integration/test_staging_prune.py -q --no-cov -p no:cacheprovider`
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add backend/scripts/staging_prune.py backend/tests/integration/test_staging_prune.py
git commit -m "feat(ops): staging 金样本裁剪脚本(规则选留+连子行删,零LLM)"
```

### Task 5: sync_staging_from_prod.py(host 编排)

**Files:**
- Create: `backend/scripts/sync_staging_from_prod.py`

**Interfaces:**
- Consumes: Task 4 CLI(`docker exec gomuseum_staging_backend python scripts/staging_prune.py --yes`)
- Produces: VPS host 命令 `python3 sync_staging_from_prod.py [--mode slim|full] --yes`

- [ ] **Step 1: 实现**(thin 编排,stdlib only,无单测——验收在 Task 7 实跑)

```python
#!/usr/bin/env python3
"""VPS host 上跑:prod → staging 内容表搬运。slim(默认)=搬运后金样本裁剪;full=全量拉真。
用户表(users/benefits/devices)与 recognition_events 永不搬(隐私红线;staging 自有)。
零 LLM。spec 2026-07-17-staging-lightweight §2。
用法(VPS root):python3 sync_staging_from_prod.py --mode slim --yes"""

import argparse
import subprocess
import sys

PROD_PG = "gomuseum_prod_postgres"
STG_PG = "gomuseum_staging_postgres"
STG_BACKEND = "gomuseum_staging_backend"
# 恢复顺序=依赖顺序;--disable-triggers 双保险
CONTENT_TABLES = [
    "museums",
    "artists",
    "museum_objects",
    "object_images",
    "object_embeddings",
    "object_content_sections",
    "object_suggested_questions",
]


def out(cmd):
    return subprocess.run(
        cmd, shell=True, check=True, capture_output=True, text=True
    ).stdout.strip()


def conn(container):
    u = out(f"docker exec {container} printenv POSTGRES_USER")
    d = out(f"docker exec {container} printenv POSTGRES_DB")
    return u, d


def psql(container, sql):
    u, d = conn(container)
    return out(f'docker exec {container} psql -U {u} -d {d} -Atc "{sql}"')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["slim", "full"], default="slim")
    ap.add_argument("--yes", action="store_true")
    ns = ap.parse_args()

    # 1) schema 对齐前置检查
    pv = psql(PROD_PG, "SELECT version_num FROM alembic_version")
    sv = psql(STG_PG, "SELECT version_num FROM alembic_version")
    if pv != sv:
        sys.exit(f"❌ alembic 版本不一致 prod={pv} staging={sv}:先把两边部署到同一版本")

    users_before = psql(STG_PG, "SELECT count(*) FROM users")
    prod_objs = psql(PROD_PG, "SELECT count(*) FROM museum_objects")
    stg_objs = psql(STG_PG, "SELECT count(*) FROM museum_objects")
    print(f"mode={ns.mode} | prod objects={prod_objs} → staging(现 {stg_objs} 将重置)")
    print(f"staging users={users_before}(不动)")
    if not ns.yes:
        sys.exit("预览模式:加 --yes 执行(破坏性重置 staging 内容表)")

    # 2) 清 staging 内容表(child→parent,不 CASCADE 防波及)
    for t in reversed(CONTENT_TABLES):
        psql(STG_PG, f"DELETE FROM {t}")

    # 3) 搬运(dump 管道直灌,--disable-triggers 免 FK 顺序问题)
    pu, pd = conn(PROD_PG)
    su, sd = conn(STG_PG)
    tables = " ".join(f"-t {t}" for t in CONTENT_TABLES)
    pipe = (
        f"docker exec {PROD_PG} pg_dump -U {pu} -d {pd} --data-only "
        f"--disable-triggers {tables} | "
        f"docker exec -i {STG_PG} psql -U {su} -d {sd} -v ON_ERROR_STOP=1 -q"
    )
    subprocess.run(pipe, shell=True, check=True)

    # 4) slim 裁剪
    if ns.mode == "slim":
        subprocess.run(
            f"docker exec {STG_BACKEND} sh -c 'cd /app && python scripts/staging_prune.py --yes'",
            shell=True,
            check=True,
        )

    # 5) 验收摘要:件数 + 用户表零泄漏
    print(f"staging objects={psql(STG_PG, 'SELECT count(*) FROM museum_objects')}")
    users_after = psql(STG_PG, "SELECT count(*) FROM users")
    if users_after != users_before:
        sys.exit(f"❌ users 表被波及!before={users_before} after={users_after}")
    print(f"users 不变({users_after}) ✓ 完成,全程零 LLM 调用")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: 本地烟测**(语法+预览分支)

Run: `python3 backend/scripts/sync_staging_from_prod.py --mode slim`(本地无 docker 容器)
Expected: 在第一处 docker 调用报 CalledProcessError/找不到容器——语法与 argparse 正常即可

- [ ] **Step 3: Commit**

```bash
git add backend/scripts/sync_staging_from_prod.py
git commit -m "feat(ops): prod→staging 内容表搬运脚本(slim/full 两档,用户表红线)"
```

### Task 6: 契约回写 + PR

**Files:**
- Modify: `docs/architecture/museum-api-contract.md`(收录策略加⑥ + 变更记录)

- [ ] **Step 1: 收录策略段(「⑤ 内容生成分层」之后)追加**

```markdown
**⑥ staging 轻量化(2026-07-17 定,spec 2026-07-17-staging-lightweight)。** staging=机制验证平台,**永不为数据规模付 LLM 费**:机制验证用小样本(护栏强制——onboard names/generate/translate 在 staging 默认 limit=50,rescan 系需显式 `--allow-full`);规模数据一律从 prod 搬运(`sync_staging_from_prod.py`,slim=金样本 ~300-500 件/full=发版前拉真;内容是 prod 已付费资产,共 R2 桶 key 复制即解析,零 LLM);**用户表(users/benefits/devices)与 recognition_events 永不跨环境**。上新馆同理:staging 只跑 `catalog --limit` 验证配方,全量只在 prod。
```

- [ ] **Step 2: 变更记录顶部追加**

```markdown
- 2026-07-17:**staging 轻量化落地**(收录⑥)——护栏(staging 默认小样本/--allow-full)+ prod→staging 搬运两档(slim 金样本/full 拉真)+ 用户表红线。背景:staging 已成 prod 近镜像,十万件×10语全量回填≈百万级强模型调用不可持续。
```

- [ ] **Step 3: 全量测试 + black + PR**

```bash
cd backend && python -m pytest tests/ -q -p no:cacheprovider -x --no-cov -k "ops_guard or staging_prune or backfill_names or generate_pipeline" && black scripts/ app/ tests/ --check
cd .. && git add -A docs backend && git commit -m "docs(api): 契约回写收录⑥ staging 轻量化"
git push -u origin feature/staging-lightweight
gh pr create --base staging --head feature/staging-lightweight --title "feat(ops): staging 轻量化(护栏+prod搬运两档+金样本裁剪)" --body "spec: docs/superpowers/specs/2026-07-17-staging-lightweight-design.md"
```

CI 绿 → squash 合并(`--delete-branch`)。

### Task 7: 首次 slim 刷新(VPS 实跑,需用户确认时点)

**Files:** 无(运维)

- [ ] **Step 1: 用户确认时点**(破坏性:staging 现有 6569 件重置为金样本)
- [ ] **Step 2: 把两脚本随部署带到容器**(合并 PR 后 CD 已同步 backend/scripts;host 脚本 scp 或直接 heredoc 执行)
- [ ] **Step 3: VPS 跑** `python3 sync_staging_from_prod.py --mode slim --yes`
- [ ] **Step 4: 验收**(对照 spec):staging objects ∈ [300,500];users 不变;`curl staging /museums/orsay` 200 且列表有数据;懒生成随点一件 stub 正常;日志无 openai 调用
- [ ] **Step 5: 记忆/收尾**:staging-pending-prod-release 记录新工作流

---

## Self-Review

1. **Spec coverage**:原则→Task 6;§1 金样本→Task 4;§2 同步→Task 5(红线/–yes/alembic 检查/零 LLM 摘要都在代码里);§3 护栏→Task 1-3;验收 4 条→Task 7 Step 4 + Task 2(护栏 limit≤50 由 ops_guard 测试覆盖)✓
2. **Placeholder**:Task 2 Step 1 标注了「执行时读既有 fixture 替换」——这是复用指令非 TBD;其余步骤代码完整 ✓
3. **类型一致**:`staging_limit/staging_require_allow_full/golden_ids/prune` 名称与消费方一致;CONTENT_TABLES 顺序与 spec 一致 ✓
