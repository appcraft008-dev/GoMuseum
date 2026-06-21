# 内容富化 Phase 2d-2a 建议问答地基（模型+迁移+落库+读侧契约）Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 给"建议问答（§12b 推荐 chips）"打地基：新表 `object_suggested_questions`（模型 + Alembic 迁移）、整组落库 `persist_suggested_questions`、并在 `get_object_content` **加法式**返回 `suggested_questions:[{question,answer}]`（先有契约面 + 存储，内容由 2d-2b 生成器填）。

**Architecture:** 沿用 `ObjectContentSection` 的列/约束风格新增 `ObjectSuggestedQuestion` 模型；迁移挂在当前 head `e1a1_add_object_sources` 之后；落库整组替换（regenerate 友好）；读侧加法补字段（老 App 容忍多余字段，符合契约前向兼容）。

**Tech Stack:** Python 3.11 · FastAPI · SQLAlchemy · Alembic · PostgreSQL · pytest。

**本期范围（2d-2 拆两半：本计划是 2d-2a 地基）:** 模型/迁移/落库/读侧契约。**Q&A 生成（prompt + 生成 + gate + 翻译 + 接入 generate_object）= 2d-2b**，独立计划，不在本期。

**前置事实（已验证，勿重查）:**
- Alembic 当前 head = `e1a1_add_object_sources`（`backend/alembic/versions/`）。迁移用 `from alembic import op`、`import sqlalchemy as sa`、`from sqlalchemy.dialects.postgresql import UUID`。
- `ObjectContentSection`（`app/models/content.py`）的列/约束风格：`id`(UUID pk)、`object_id`(FK museum_objects.id, index)、`language`(String8)、`status`(String16 default published)、`model`(String64 null)、`generated_at`(DateTime null)、`created_at`/`updated_at`(server_default now)。content.py 已 import `Column, ForeignKey, Integer, String, Text, UniqueConstraint, DateTime, func, UUID, uuid, Base`。
- `content_repo.py` 顶部已 import `datetime, timezone`、`ObjectContentSection`、`MuseumObject`。
- `get_object_content`（`app/services/museum_repo.py`）当前返回 `{qid, category, language, tabs}`；要加法补 `suggested_questions`。
- 契约（spec §15 附录 + 行 353/556）：`object_content` 加法补 `suggested_questions:[{question,answer}]`（published、按 sort 序、当前语言）。
- 集成测试可仿 `tests/integration/test_content_persist.py` 的 in-memory SQLite fixture（`upsert_museum`/`upsert_object`）。

---

## 文件结构

| 文件 | 职责 | 动作 |
|---|---|---|
| `backend/app/models/content.py` | 加 `ObjectSuggestedQuestion` 模型 | 修改 |
| `backend/alembic/versions/f2a2_add_suggested_questions.py` | 建表迁移 | **新建** |
| `backend/app/services/content_repo.py` | 加 `persist_suggested_questions`（整组替换） | 修改 |
| `backend/app/services/museum_repo.py` | `get_object_content` 加法补 `suggested_questions` | 修改 |
| `backend/tests/integration/test_suggested_questions.py` | 模型 + 落库 + 读侧集成测试 | **新建** |

**关键接口（先定死）:**

```python
# models/content.py
class ObjectSuggestedQuestion(Base):
    __tablename__ = "object_suggested_questions"
    # uq(object_id, language, sort)；列见 Task 1

# content_repo.py
def persist_suggested_questions(db, qid, language, items, model=None) -> int: ...
# items = [{"question","answer","status"?}]；整组替换该(对象,语言)；返回 published 数

# museum_repo.get_object_content 返回值加键：
#   "suggested_questions": [{"question","answer"}]  # published、按 sort
```

---

## Task 1: 模型 `ObjectSuggestedQuestion`

**Files:**
- Modify: `backend/app/models/content.py`（末尾追加类）
- Test: `backend/tests/integration/test_suggested_questions.py`

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/integration/test_suggested_questions.py
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.models.content import ObjectContentSection, ObjectSuggestedQuestion
from app.models.museum import Museum
from app.models.museum_object import MuseumObject, ObjectImage
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
            ObjectContentSection.__table__,
            ObjectSuggestedQuestion.__table__,
        ],
    )
    s = sessionmaker(bind=engine)()
    m = upsert_museum(s, {"slug": "orsay", "name_en": "Orsay"})
    upsert_object(s, m.id, {"qid": "Q1", "title_en": "A", "category": "painting"})
    s.commit()
    yield s


def test_suggested_question_roundtrip(session):
    o = session.query(MuseumObject).filter_by(qid="Q1").one()
    row = ObjectSuggestedQuestion(
        object_id=o.id, language="en", sort=0,
        question="Why the direct gaze?", answer="Because ...",
        status="published",
    )
    session.add(row)
    session.commit()
    got = session.query(ObjectSuggestedQuestion).filter_by(object_id=o.id).one()
    assert got.question == "Why the direct gaze?"
    assert got.answer == "Because ..."
    assert got.language == "en" and got.sort == 0
    assert got.status == "published"
```

- [ ] **Step 2: 跑确认失败**

Run: `cd backend && poetry run pytest tests/integration/test_suggested_questions.py -v`
Expected: FAIL（`cannot import name ObjectSuggestedQuestion`）

- [ ] **Step 3: 在 `content.py` 末尾追加**

```python
class ObjectSuggestedQuestion(Base):
    __tablename__ = "object_suggested_questions"
    __table_args__ = (
        UniqueConstraint(
            "object_id", "language", "sort", name="uq_sq_obj_lang_sort"
        ),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    object_id = Column(
        UUID(as_uuid=True), ForeignKey("museum_objects.id"), nullable=False, index=True
    )
    language = Column(String(8), nullable=False)
    sort = Column(Integer, nullable=False, default=0)
    question = Column(Text, nullable=False)
    answer = Column(Text, nullable=False)
    status = Column(String(16), default="published")  # published | needs_review
    model = Column(String(64), nullable=True)
    generated_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )

    def __repr__(self) -> str:
        return (
            f"<ObjectSuggestedQuestion(object_id={self.object_id}, "
            f"language={self.language}, sort={self.sort})>"
        )
```

- [ ] **Step 4: 跑确认通过**

Run: `cd backend && poetry run pytest tests/integration/test_suggested_questions.py -v`
Expected: PASS（1 passed）（单文件触发覆盖率门时加 `--no-cov`）

- [ ] **Step 5: 提交**

```bash
cd backend && poetry run black app/models/content.py tests/integration/test_suggested_questions.py && poetry run isort app/models/content.py tests/integration/test_suggested_questions.py
cd /Users/hongyang/Projects/GoMuseum && git add backend/app/models/content.py backend/tests/integration/test_suggested_questions.py
git commit -m "feat(content): ObjectSuggestedQuestion 模型(推荐问答地基)"
```

---

## Task 2: Alembic 迁移 `object_suggested_questions`

**Files:**
- Create: `backend/alembic/versions/f2a2_add_suggested_questions.py`

- [ ] **Step 1: 创建迁移文件**

```python
"""add object_suggested_questions table

Revision ID: f2a2_add_suggested_questions
Revises: e1a1_add_object_sources
Create Date: 2026-06-21
"""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

from alembic import op

revision = "f2a2_add_suggested_questions"
down_revision = "e1a1_add_object_sources"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "object_suggested_questions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "object_id",
            UUID(as_uuid=True),
            sa.ForeignKey("museum_objects.id"),
            nullable=False,
        ),
        sa.Column("language", sa.String(length=8), nullable=False),
        sa.Column("sort", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("answer", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=16), server_default="published"),
        sa.Column("model", sa.String(length=64), nullable=True),
        sa.Column("generated_at", sa.DateTime(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint(
            "object_id", "language", "sort", name="uq_sq_obj_lang_sort"
        ),
    )
    op.create_index(
        "ix_object_suggested_questions_object_id",
        "object_suggested_questions",
        ["object_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_object_suggested_questions_object_id",
        table_name="object_suggested_questions",
    )
    op.drop_table("object_suggested_questions")
```

- [ ] **Step 2: 验证迁移链（离线，读文件即可）**

Run: `cd backend && poetry run alembic history | head -3`
Expected: 顶部出现 `e1a1_add_object_sources -> f2a2_add_suggested_questions (head)`（新迁移成为唯一 head；若 `alembic` 因缺依赖跑不起来，改用 `/Users/hongyang/.pyenv/versions/3.11.7/bin/python3.11 -m alembic history`）。

> 不在此跑 `upgrade`（需真实 PG）；真正 apply 在合并部署后于 staging 容器执行（见收尾）。

- [ ] **Step 3: 提交**

```bash
cd /Users/hongyang/Projects/GoMuseum && git add backend/alembic/versions/f2a2_add_suggested_questions.py
git commit -m "feat(db): 迁移建表 object_suggested_questions"
```

---

## Task 3: 落库 `persist_suggested_questions`（整组替换）

**Files:**
- Modify: `backend/app/services/content_repo.py`
- Test: `backend/tests/integration/test_suggested_questions.py`（追加）

设计要点：
- 整组替换：先删该 (对象,语言) 所有问答，再按列表序写入（`sort=i`）。regenerate 友好、无残留。
- `items=[{"question","answer","status"?}]`，`status` 缺省 `"published"`。返回 published 数。未知 qid → 0。

- [ ] **Step 1: 写失败测试（追加）**

```python
def test_persist_suggested_questions_replaces_group(session):
    from app.services.content_repo import persist_suggested_questions
    from app.models.content import ObjectSuggestedQuestion

    n = persist_suggested_questions(
        session, "Q1", "en",
        [
            {"question": "Q-a", "answer": "A-a"},
            {"question": "Q-b", "answer": "A-b", "status": "needs_review"},
        ],
        model="gpt-4o-mini",
    )
    assert n == 1  # 仅 published 计数
    rows = (
        session.query(ObjectSuggestedQuestion)
        .filter_by(language="en")
        .order_by(ObjectSuggestedQuestion.sort)
        .all()
    )
    assert [r.sort for r in rows] == [0, 1]
    assert rows[0].question == "Q-a" and rows[0].status == "published"
    assert rows[1].status == "needs_review"
    assert rows[0].model == "gpt-4o-mini"

    # 再写一组更短的 → 整组替换、无残留
    persist_suggested_questions(session, "Q1", "en", [{"question": "Q-x", "answer": "A-x"}])
    rows2 = session.query(ObjectSuggestedQuestion).filter_by(language="en").all()
    assert len(rows2) == 1 and rows2[0].question == "Q-x"


def test_persist_suggested_questions_unknown_qid(session):
    from app.services.content_repo import persist_suggested_questions

    assert persist_suggested_questions(session, "Q404", "en", [{"question": "a", "answer": "b"}]) == 0
```

- [ ] **Step 2: 跑确认失败**

Run: `cd backend && poetry run pytest tests/integration/test_suggested_questions.py -k persist -v`
Expected: FAIL（`cannot import name persist_suggested_questions`）

- [ ] **Step 3: 在 `content_repo.py` 实现**

顶部 import 加：`from app.models.content import ObjectSuggestedQuestion`（与现有 `from app.models.content import ObjectContentSection` 并列）。追加：

```python
def persist_suggested_questions(db, qid: str, language: str, items: list, model: str | None = None) -> int:
    """整组替换某 (对象,语言) 的推荐问答。items=[{question,answer,status?}]。返回 published 数。未知 qid→0。"""
    obj = db.query(MuseumObject).filter_by(qid=qid).one_or_none()
    if not obj:
        return 0
    db.query(ObjectSuggestedQuestion).filter_by(
        object_id=obj.id, language=language
    ).delete()
    n = 0
    for i, it in enumerate(items):
        status = it.get("status", "published")
        db.add(
            ObjectSuggestedQuestion(
                object_id=obj.id,
                language=language,
                sort=i,
                question=it["question"],
                answer=it["answer"],
                status=status,
                model=model,
                generated_at=datetime.now(timezone.utc),
            )
        )
        if status == "published":
            n += 1
    db.commit()
    return n
```

- [ ] **Step 4: 跑确认通过**

Run: `cd backend && poetry run pytest tests/integration/test_suggested_questions.py -v`
Expected: PASS（既有 1 + 新 2 = 3 passed）

- [ ] **Step 5: 提交**

```bash
cd backend && poetry run black app/services/content_repo.py tests/integration/test_suggested_questions.py && poetry run isort app/services/content_repo.py tests/integration/test_suggested_questions.py
cd /Users/hongyang/Projects/GoMuseum && git add backend/app/services/content_repo.py backend/tests/integration/test_suggested_questions.py
git commit -m "feat(content): persist_suggested_questions 整组替换落库"
```

---

## Task 4: `get_object_content` 加法补 `suggested_questions`

**Files:**
- Modify: `backend/app/services/museum_repo.py`
- Test: `backend/tests/integration/test_suggested_questions.py`（追加）

设计要点：
- 在 `get_object_content` 返回 dict 里**加法补** `suggested_questions`：查该 (对象,语言) `status="published"` 的问答、按 `sort` 序 → `[{"question","answer"}]`。其余字段不变（前向兼容）。

- [ ] **Step 1: 写失败测试（追加）**

```python
def test_get_object_content_includes_suggested_questions(session):
    from app.services.content_repo import persist_suggested_questions
    from app.services.museum_repo import get_object_content

    persist_suggested_questions(
        session, "Q1", "en",
        [
            {"question": "Q-pub", "answer": "A-pub"},
            {"question": "Q-nr", "answer": "A-nr", "status": "needs_review"},
        ],
    )
    content = get_object_content(session, "orsay", "Q1", "en")
    assert "suggested_questions" in content
    sq = content["suggested_questions"]
    assert sq == [{"question": "Q-pub", "answer": "A-pub"}]  # 仅 published、按 sort


def test_get_object_content_suggested_questions_empty_when_none(session):
    from app.services.museum_repo import get_object_content

    content = get_object_content(session, "orsay", "Q1", "fr")
    assert content["suggested_questions"] == []
```

> 该测试的 `session` fixture（本文件顶部）只建了 `Museum/MuseumObject/ObjectImage/ObjectContentSection/ObjectSuggestedQuestion` 表；`get_object_content` 会查 `CategorySection/SectionType`（tabs 用）——这两张表未建会报错。**故在本文件 fixture 的 `create_all` tables 列表里补上 `SectionType.__table__, CategorySection.__table__`**，并在文件顶部 import：`from app.models.content import CategorySection, SectionType`。无 seed 数据时 tabs 为空列表，不影响本测试断言。

- [ ] **Step 2: 跑确认失败**

Run: `cd backend && poetry run pytest tests/integration/test_suggested_questions.py -k suggested_questions -v`
Expected: FAIL（返回 dict 无 `suggested_questions` 键）

- [ ] **Step 3: 改 `museum_repo.py`**

顶部 import 补 `ObjectSuggestedQuestion`（与现有 `from app.models.content import ...` 并列）。在 `get_object_content` 的 `return` 前加查询、并把字段加进返回 dict：

```python
    suggested = [
        {"question": q.question, "answer": q.answer}
        for q in db.query(ObjectSuggestedQuestion)
        .filter_by(object_id=obj.id, language=language, status="published")
        .order_by(ObjectSuggestedQuestion.sort)
        .all()
    ]
    return {
        "qid": qid,
        "category": obj.category,
        "language": language,
        "tabs": tabs,
        "suggested_questions": suggested,
    }
```

- [ ] **Step 4: 跑确认通过**

Run: `cd backend && poetry run pytest tests/integration/test_suggested_questions.py -v`
Expected: PASS（全 passed）

- [ ] **Step 5: 提交**

```bash
cd backend && poetry run black app/services/museum_repo.py tests/integration/test_suggested_questions.py && poetry run isort app/services/museum_repo.py tests/integration/test_suggested_questions.py
cd /Users/hongyang/Projects/GoMuseum && git add backend/app/services/museum_repo.py backend/tests/integration/test_suggested_questions.py
git commit -m "feat(content): get_object_content 加法补 suggested_questions(前向兼容)"
```

---

## 收尾

- [ ] **全套相关测试**：
```bash
cd backend && STORAGE_BACKEND=local poetry run pytest tests/integration/test_suggested_questions.py -W "ignore::PendingDeprecationWarning" -v
```
Expected: 全 passed。

- [ ] **提 PR**：`feature/content-enrichment-phase2d2a → staging`（用 `/pr`）。**有 DB 迁移**——PR 描述注明需在部署后跑 `alembic upgrade head`。CI 绿后 squash 合并、删分支。
- [ ]（部署后·必须）合并 + staging 自动部署后，在容器内 apply 迁移并自检：
  `docker exec gomuseum_staging_backend alembic upgrade head`，再
  `docker exec gomuseum_staging_backend python -c "from app.core.database import SessionLocal; from app.services.museum_repo import get_object_content; print(get_object_content(SessionLocal(),'orsay','Q737062','en')['suggested_questions'])"`
  期望返回 `[]`（表已建、字段加法生效、暂无数据）。
  > ⚠️ 确认部署流程是否自动跑 `alembic upgrade head`；若不自动则手动执行（仅 staging；prod 待 staging→main 后另行）。

---

## Self-Review（计划对照 spec §12b / 契约）

- **§12b 推荐问答落库地基**：`ObjectSuggestedQuestion` 模型 + 迁移（Task 1/2）✓。
- **整组预生成可重跑**：`persist_suggested_questions` 整组替换（Task 3）✓。
- **契约加法补 `suggested_questions:[{question,answer}]`**：`get_object_content` 加字段、published 按 sort（Task 4）✓，老 App 容忍多余字段（前向兼容、不破已装）。
- **本期不做（显式）**：Q&A 生成（prompt/生成/gate/翻译/接 generate_object）= 2d-2b；多轮 `/ask` 端点 = 后续；答案音频临时（§13b）= 后续 ✓。
- **类型一致性**：`persist_suggested_questions(db,qid,language,items,model)` 的 `items=[{question,answer,status?}]` 与 Task 3/4 测试一致；`get_object_content` 加键 `suggested_questions=[{question,answer}]` 与契约一致 ✓。
- **DRY/风格**：模型沿用 `ObjectContentSection` 列风格、迁移挂当前 head、复用现有 import ✓。
