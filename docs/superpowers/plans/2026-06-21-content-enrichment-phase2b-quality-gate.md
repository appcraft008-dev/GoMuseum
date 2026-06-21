# 内容富化 Phase 2b 质量闸 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 给 Phase 2a 接地生成的英语段落加一道自动质量闸——逐句蕴含校验删掉材料不支持的句子、叙事与硬事实对账、聚合质量分，低分/有冲突的段标 `needs_review` 不发布。

**Architecture:** 新增 `quality.py`（纯逻辑 `QualityGate`，LLM 判定经注入式 `complete` 离线可测，与 Phase 2a `ContentEnricher` 同款注入模式）；`prompts.py` 加蕴含与事实一致性两个 prompt；`content_repo.py` 抽 `_upsert_section` 复用、加 `persist_gated_sections`（按段写 published/needs_review，跳过 absent）。生成→闸→落库三段解耦，闸不依赖 DB、不依赖网络。

**Tech Stack:** Python 3.11 · FastAPI · SQLAlchemy · pytest · OpenAI（gpt-4o-mini，经 `default_complete` 复用）。

**动机（真实数据驱动）:** 2026-06-21 在 staging 容器对《奥林匹亚》(Q737062) 跑 Phase 2a `generate_canonical`，喂真实 Wikipedia 材料：overview/background 完全接地、analysis/facts 薄料正确留空，**但 `artist` 段冒出"现实主义到印象派转型"——材料里只有作者名，这句是模型自带知识泄漏**。证明光靠 prompt 约束挡不住名作的知识泄漏，必须有自动蕴含闸删/标不被材料支持的句子。这正是 spec §8A-1/§8A-2 要解决的。

**本期范围（按既定 2b/2c/2d 切分）:** 仅 §8A 的 (1) 接地/蕴含分、(2) 事实一致性、聚合**质量分 → status**。译文忠实（§8A-5）属 Phase 2c；格式/语言（§8A-4，langdetect）、安全 moderation（§8A-6）、质量报告（§8B）、金标准回归（§8D）暂不在本期，留 TODO 注记，不写代码（YAGNI）。

---

## 文件结构

| 文件 | 职责 | 本期动作 |
|---|---|---|
| `backend/app/services/enrichment/quality.py` | `QualityGate`：句子切分 + 逐句蕴含删句 + 事实对账 + 质量分 + status 判定；`SectionQuality` 数据类 | **新建** |
| `backend/app/services/enrichment/prompts.py` | 加 `build_entailment_prompt`、`build_fact_consistency_prompt` | 修改（追加，不动 `build_generation_prompt`） |
| `backend/app/services/content_repo.py` | 抽 `_upsert_section` 复用；加 `persist_gated_sections` | 修改 |
| `backend/tests/unit/services/enrichment/test_quality.py` | quality 单测 | **新建** |
| `backend/tests/unit/services/enrichment/test_prompts.py` | 追加两个 prompt 的断言 | 修改 |
| `backend/tests/integration/test_content_persist.py` | 追加 `persist_gated_sections` 测试 | 修改 |

**关键接口（贯穿全计划，先定死避免漂移）:**

```python
# quality.py
@dataclass
class SectionQuality:
    body: str | None          # 删掉不支持句后的正文（可能比原文短）；全删→None
    status: str               # "published" | "needs_review"
    grounding_ratio: float    # 被材料支持的句子占比（0.0–1.0）
    conflicts: list[str]      # 与硬事实矛盾点；空=无冲突
    score: float              # 聚合质量分 0.0–1.0

GROUNDING_THRESHOLD = 0.6     # 接地率低于此 → needs_review

class QualityGate:
    def __init__(self, complete):   # complete(system, user) -> str，与 ContentEnricher 同款注入
        ...
    def check_section(self, material: str, facts: str, body: str) -> SectionQuality: ...
    def gate(self, material: str, facts: str, sections: dict) -> dict: ...
    # gate 返回 {section_code: SectionQuality}；输入 sections 里 body 为 None/空的段直接跳过（absent，不进结果）
```

---

## Task 1: 句子切分 `_split_sentences`

**Files:**
- Create: `backend/app/services/enrichment/quality.py`
- Test: `backend/tests/unit/services/enrichment/test_quality.py`

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/unit/services/enrichment/test_quality.py
from app.services.enrichment.quality import _split_sentences


def test_split_sentences_basic():
    text = "Olympia is a painting. It caused a scandal. Monet led a subscription."
    assert _split_sentences(text) == [
        "Olympia is a painting.",
        "It caused a scandal.",
        "Monet led a subscription.",
    ]


def test_split_sentences_strips_empty_and_whitespace():
    assert _split_sentences("  One sentence only.  ") == ["One sentence only."]
    assert _split_sentences("") == []
    assert _split_sentences(None) == []
```

- [ ] **Step 2: 跑确认失败**

Run: `cd backend && poetry run pytest tests/unit/services/enrichment/test_quality.py -k split -v`
Expected: FAIL（`ModuleNotFoundError` / `cannot import name _split_sentences`）

- [ ] **Step 3: 实现**

```python
# backend/app/services/enrichment/quality.py
"""质量闸 QualityGate：逐句蕴含校验删不支持句 + 叙事/硬事实对账 + 质量分 → status。
LLM 判定经注入式 complete，单测离线。spec §8A-1/§8A-2。"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

from app.services.enrichment.prompts import (
    build_entailment_prompt,
    build_fact_consistency_prompt,
)

GROUNDING_THRESHOLD = 0.6

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")


def _split_sentences(text: str | None) -> list[str]:
    """把正文切成句子列表（按 . ! ? 后接空白）。空/None → []。"""
    if not text or not text.strip():
        return []
    parts = _SENTENCE_SPLIT.split(text.strip())
    return [p.strip() for p in parts if p.strip()]
```

- [ ] **Step 4: 跑确认通过**

Run: `cd backend && poetry run pytest tests/unit/services/enrichment/test_quality.py -k split -v`
Expected: PASS（2 passed）

- [ ] **Step 5: 提交**

```bash
cd backend && poetry run black app/services/enrichment/quality.py tests/unit/services/enrichment/test_quality.py && poetry run isort app/services/enrichment/quality.py tests/unit/services/enrichment/test_quality.py
cd /Users/hongyang/Projects/GoMuseum && git add backend/app/services/enrichment/quality.py backend/tests/unit/services/enrichment/test_quality.py
git commit -m "feat(enrichment): 质量闸句子切分 _split_sentences"
```

---

## Task 2: 蕴含 + 事实一致性 prompt

**Files:**
- Modify: `backend/app/services/enrichment/prompts.py`（追加两个函数，不动既有 `build_generation_prompt`/`_SYSTEM`）
- Test: `backend/tests/unit/services/enrichment/test_prompts.py`（追加）

- [ ] **Step 1: 写失败测试（追加到现有文件）**

```python
def test_entailment_prompt_demands_per_sentence_json_verdicts():
    from app.services.enrichment.prompts import build_entailment_prompt

    system, user = build_entailment_prompt("[FACTS]\n- Title: Olympia", ["S1.", "S2."])
    blob = (system + user).lower()
    # 只依据材料判定、逐句、严格 JSON 布尔数组
    assert "only" in blob and "material" in blob
    assert "json" in blob
    assert "verdicts" in blob
    # 句子按序编号进 user
    assert "S1." in user and "S2." in user


def test_fact_consistency_prompt_lists_conflicts_json():
    from app.services.enrichment.prompts import build_fact_consistency_prompt

    system, user = build_fact_consistency_prompt(
        "- Year: 1863", "Painted in 1900 by Manet."
    )
    blob = (system + user).lower()
    assert "contradict" in blob or "conflict" in blob
    assert "json" in blob
    assert "conflicts" in blob
    assert "1863" in user and "1900" in user
```

- [ ] **Step 2: 跑确认失败**

Run: `cd backend && poetry run pytest tests/unit/services/enrichment/test_prompts.py -k "entailment or fact_consistency" -v`
Expected: FAIL（`cannot import name build_entailment_prompt`）

- [ ] **Step 3: 实现（追加到 prompts.py 末尾）**

```python
_ENTAILMENT_SYSTEM = (
    "You are a fact-checking judge. You are given source MATERIAL and a numbered list of "
    "SENTENCES taken from an artwork explanation. For EACH sentence decide whether it is "
    "entailed (fully supported) by the material. Judge USING ONLY the material; a sentence "
    "that adds any fact not present in the material is NOT supported, even if it is true in "
    "the real world. Return STRICT JSON: {\"verdicts\": [true, false, ...]} with one boolean "
    "per sentence in the SAME order. No commentary."
)


def build_entailment_prompt(material: str, sentences: list[str]):
    numbered = "\n".join(f"{i + 1}. {s}" for i, s in enumerate(sentences))
    user = f"MATERIAL:\n{material}\n\nSENTENCES:\n{numbered}"
    return _ENTAILMENT_SYSTEM, user


_FACT_CONSISTENCY_SYSTEM = (
    "You are a fact-checking judge. You are given structured FACTS about an artwork and a "
    "narrative BODY. List every statement in the body that CONTRADICTS the facts (e.g. wrong "
    "year, wrong artist, wrong dimensions). Ignore extra detail that does not contradict. "
    "Return STRICT JSON: {\"conflicts\": [\"...\", ...]} (empty list if none). No commentary."
)


def build_fact_consistency_prompt(facts: str, body: str):
    user = f"FACTS:\n{facts}\n\nBODY:\n{body}"
    return _FACT_CONSISTENCY_SYSTEM, user
```

- [ ] **Step 4: 跑确认通过**

Run: `cd backend && poetry run pytest tests/unit/services/enrichment/test_prompts.py -v`
Expected: PASS（既有 1 + 新 2 = 3 passed）

- [ ] **Step 5: 提交**

```bash
cd backend && poetry run black app/services/enrichment/prompts.py tests/unit/services/enrichment/test_prompts.py && poetry run isort app/services/enrichment/prompts.py tests/unit/services/enrichment/test_prompts.py
cd /Users/hongyang/Projects/GoMuseum && git add backend/app/services/enrichment/prompts.py backend/tests/unit/services/enrichment/test_prompts.py
git commit -m "feat(enrichment): 蕴含+事实一致性 prompt(逐句判定/列冲突,严格JSON)"
```

---

## Task 3: `QualityGate.check_section`（删句 + 对账 + 质量分 + status）

**Files:**
- Modify: `backend/app/services/enrichment/quality.py`
- Test: `backend/tests/unit/services/enrichment/test_quality.py`（追加）

设计要点：
- `check_section` 用注入的 `complete` 两次调用：蕴含（删不支持句）+ 事实一致性（列冲突）。
- 蕴含解析出每句 verdict，保留 `True` 的句子拼回 `body`；`grounding_ratio = kept/total`。
- 全删（kept 为空）→ `body=None, status="needs_review", grounding_ratio=0.0`。
- `score = grounding_ratio`，**有冲突再扣 0.5**（下限 0）。
- `status = "published"` 当 `score >= GROUNDING_THRESHOLD 且 无 conflicts 且 body 非空`，否则 `"needs_review"`。
- 复用 Phase 2a 的容错 JSON 解析：从 `content_enricher` import `_parse_json`（已实现：去代码围栏 + fallback 取首个 `{...}`）。

- [ ] **Step 1: 写失败测试（追加）**

```python
from app.services.enrichment.quality import QualityGate, SectionQuality


class _FakeComplete:
    """按 system 内容路由：蕴含 prompt 返 verdicts，事实 prompt 返 conflicts。"""

    def __init__(self, verdicts, conflicts):
        self._verdicts = verdicts
        self._conflicts = conflicts

    def __call__(self, system, user):
        import json as _json

        if "entail" in system.lower():
            return _json.dumps({"verdicts": self._verdicts})
        return _json.dumps({"conflicts": self._conflicts})


def test_check_section_drops_unsupported_sentence():
    body = "Olympia is an 1863 painting. Manet pioneered Impressionism."
    gate = QualityGate(_FakeComplete(verdicts=[True, False], conflicts=[]))
    r = gate.check_section("[FACTS]\n- Year: 1863", "- Year: 1863", body)
    assert r.body == "Olympia is an 1863 painting."   # 第二句不被支持 → 删
    assert r.grounding_ratio == 0.5
    assert r.conflicts == []
    # 接地率 0.5 < 0.6 阈值 → needs_review
    assert r.status == "needs_review"


def test_check_section_all_supported_no_conflict_publishes():
    body = "Olympia is an 1863 painting. It now hangs in the Musee d'Orsay."
    gate = QualityGate(_FakeComplete(verdicts=[True, True], conflicts=[]))
    r = gate.check_section("material", "facts", body)
    assert r.grounding_ratio == 1.0
    assert r.status == "published"
    assert r.score == 1.0


def test_check_section_fact_conflict_forces_review():
    body = "Olympia was painted in 1900."
    gate = QualityGate(_FakeComplete(verdicts=[True], conflicts=["body says 1900, facts say 1863"]))
    r = gate.check_section("material", "- Year: 1863", body)
    assert r.conflicts == ["body says 1900, facts say 1863"]
    assert r.status == "needs_review"
    assert r.score == 0.5   # grounding 1.0 - 冲突罚 0.5


def test_check_section_all_dropped_returns_none_body():
    body = "Totally made up sentence."
    gate = QualityGate(_FakeComplete(verdicts=[False], conflicts=[]))
    r = gate.check_section("material", "facts", body)
    assert r.body is None
    assert r.grounding_ratio == 0.0
    assert r.status == "needs_review"
```

- [ ] **Step 2: 跑确认失败**

Run: `cd backend && poetry run pytest tests/unit/services/enrichment/test_quality.py -k check_section -v`
Expected: FAIL（`cannot import name QualityGate`）

- [ ] **Step 3: 实现（在 quality.py 追加）**

```python
@dataclass
class SectionQuality:
    body: str | None
    status: str
    grounding_ratio: float
    conflicts: list[str] = field(default_factory=list)
    score: float = 0.0


def _parse():
    # 复用 Phase 2a 的容错解析，避免重复实现
    from app.services.enrichment.content_enricher import _parse_json

    return _parse_json


class QualityGate:
    def __init__(self, complete):
        self._complete = complete  # complete(system, user) -> str

    def check_section(self, material: str, facts: str, body: str) -> SectionQuality:
        parse = _parse()
        sentences = _split_sentences(body)
        if not sentences:
            return SectionQuality(
                body=None, status="needs_review", grounding_ratio=0.0
            )

        # 1) 逐句蕴含
        e_sys, e_user = build_entailment_prompt(material, sentences)
        verdicts = parse(self._complete(e_sys, e_user)).get("verdicts") or []
        kept = [
            s for s, ok in zip(sentences, verdicts) if ok is True
        ]
        grounding_ratio = len(kept) / len(sentences)
        kept_body = " ".join(kept) if kept else None

        # 2) 事实一致性（仅当还有留存正文才查）
        conflicts: list[str] = []
        if kept_body:
            f_sys, f_user = build_fact_consistency_prompt(facts, kept_body)
            conflicts = parse(self._complete(f_sys, f_user)).get("conflicts") or []

        # 3) 质量分 + status
        score = grounding_ratio - (0.5 if conflicts else 0.0)
        score = max(0.0, score)
        published = (
            kept_body is not None
            and grounding_ratio >= GROUNDING_THRESHOLD
            and not conflicts
        )
        return SectionQuality(
            body=kept_body,
            status="published" if published else "needs_review",
            grounding_ratio=grounding_ratio,
            conflicts=conflicts,
            score=score,
        )
```

- [ ] **Step 4: 跑确认通过**

Run: `cd backend && poetry run pytest tests/unit/services/enrichment/test_quality.py -k check_section -v`
Expected: PASS（4 passed）

- [ ] **Step 5: 提交**

```bash
cd backend && poetry run black app/services/enrichment/quality.py tests/unit/services/enrichment/test_quality.py && poetry run isort app/services/enrichment/quality.py tests/unit/services/enrichment/test_quality.py
cd /Users/hongyang/Projects/GoMuseum && git add backend/app/services/enrichment/quality.py backend/tests/unit/services/enrichment/test_quality.py
git commit -m "feat(enrichment): QualityGate.check_section 删不支持句+事实对账+质量分→status"
```

---

## Task 4: `QualityGate.gate`（整件逐段过闸，跳过 absent 段）

**Files:**
- Modify: `backend/app/services/enrichment/quality.py`
- Test: `backend/tests/unit/services/enrichment/test_quality.py`（追加）

- [ ] **Step 1: 写失败测试（追加）**

```python
def test_gate_runs_each_section_and_skips_absent():
    # overview 全支持→published；artist 全删→needs_review；analysis 输入为 None→跳过不进结果
    class _Router:
        def __call__(self, system, user):
            import json as _json
            if "entail" in system.lower():
                # overview 1 句支持；artist 1 句不支持
                return _json.dumps({"verdicts": [True]}) if "Overview sentence." in user \
                    else _json.dumps({"verdicts": [False]})
            return _json.dumps({"conflicts": []})

    gate = QualityGate(_Router())
    sections = {
        "overview": "Overview sentence.",
        "artist": "Fabricated artist sentence.",
        "analysis": None,
    }
    out = gate.gate("material", "facts", sections)
    assert set(out.keys()) == {"overview", "artist"}        # analysis(None) 被跳过
    assert out["overview"].status == "published"
    assert out["artist"].status == "needs_review"
    assert out["artist"].body is None
```

- [ ] **Step 2: 跑确认失败**

Run: `cd backend && poetry run pytest tests/unit/services/enrichment/test_quality.py -k gate -v`
Expected: FAIL（`'QualityGate' object has no attribute 'gate'`）

- [ ] **Step 3: 实现（在 QualityGate 类内追加方法）**

```python
    def gate(self, material: str, facts: str, sections: dict) -> dict:
        """逐段过闸。sections 里 body 为 None/空的段视为 absent，跳过不进结果。
        返回 {section_code: SectionQuality}。"""
        results = {}
        for code, body in sections.items():
            if not body:
                continue
            results[code] = self.check_section(material, facts, body)
        return results
```

- [ ] **Step 4: 跑确认通过**

Run: `cd backend && poetry run pytest tests/unit/services/enrichment/test_quality.py -v`
Expected: PASS（Task1 的 2 + Task3 的 4 + 本 1 = 7 passed）

- [ ] **Step 5: 提交**

```bash
cd backend && poetry run black app/services/enrichment/quality.py tests/unit/services/enrichment/test_quality.py && poetry run isort app/services/enrichment/quality.py tests/unit/services/enrichment/test_quality.py
cd /Users/hongyang/Projects/GoMuseum && git add backend/app/services/enrichment/quality.py backend/tests/unit/services/enrichment/test_quality.py
git commit -m "feat(enrichment): QualityGate.gate 整件逐段过闸+跳过absent"
```

---

## Task 5: 落库 `persist_gated_sections`（按段写 published/needs_review）

**Files:**
- Modify: `backend/app/services/content_repo.py`（抽 `_upsert_section` 复用 + 加 `persist_gated_sections`）
- Test: `backend/tests/integration/test_content_persist.py`（追加）

设计要点：
- 把现有 `persist_generated_sections` 内重复的"查/建行 + 赋值"抽成模块级 `_upsert_section(db, obj, language, code, body, status, model)`，两个 persist 函数共用（DRY）。`persist_generated_sections` 行为不变（仍只发布、仍跳空、仍返发布数）。
- `persist_gated_sections(db, qid, language, results, model)`：`results` 是 `{code: SectionQuality}`；逐段写 `body`/`status`（published 或 needs_review）；`SectionQuality.body` 为 None 的段也建行（status 必为 needs_review，body=None → 前端显"待完善"）。返回 `(published_count, needs_review_count)`。未知 qid → `(0, 0)`。

- [ ] **Step 1: 写失败测试（追加，复用既有 `session` fixture，已 seed orsay+Q1）**

```python
def test_persist_gated_sections_writes_published_and_needs_review(session):
    from app.services.content_repo import persist_gated_sections
    from app.services.enrichment.quality import SectionQuality
    from app.models.content import ObjectContentSection

    results = {
        "overview": SectionQuality(body="Good grounded text.", status="published",
                                   grounding_ratio=1.0, conflicts=[], score=1.0),
        "artist": SectionQuality(body=None, status="needs_review",
                                 grounding_ratio=0.0, conflicts=[], score=0.0),
    }
    pub, nr = persist_gated_sections(session, "Q1", "en", results, model="gpt-4o-mini")
    assert (pub, nr) == (1, 1)
    rows = {r.section_code: r for r in
            session.query(ObjectContentSection).filter_by(language="en").all()}
    assert rows["overview"].status == "published"
    assert rows["overview"].body == "Good grounded text."
    assert rows["overview"].source == "ai_generated"
    assert rows["artist"].status == "needs_review"   # needs_review 段也建行
    assert rows["artist"].body is None


def test_persist_gated_unknown_qid_returns_zeros(session):
    from app.services.content_repo import persist_gated_sections
    from app.services.enrichment.quality import SectionQuality
    r = {"overview": SectionQuality(body="x", status="published",
                                    grounding_ratio=1.0, conflicts=[], score=1.0)}
    assert persist_gated_sections(session, "Q404", "en", r, model="m") == (0, 0)


def test_persist_generated_sections_still_works(session):
    # 回归：抽 _upsert_section 后旧函数行为不变
    from app.services.content_repo import persist_generated_sections
    n = persist_generated_sections(session, "Q1", "en",
                                   {"overview": "Body.", "artist": None}, model="m")
    assert n == 1
```

- [ ] **Step 2: 跑确认失败**

Run: `cd backend && poetry run pytest tests/integration/test_content_persist.py -k "gated or still_works" -v`
Expected: FAIL（`cannot import name persist_gated_sections`）

- [ ] **Step 3: 实现**

先在 `content_repo.py` 加模块级辅助（放在 `persist_generated_sections` 定义之前）：

```python
def _upsert_section(db, obj, language, code, body, status, model):
    """查/建 (obj,lang,section) 行并赋值。供 persist_generated_sections / persist_gated_sections 复用。"""
    row = (
        db.query(ObjectContentSection)
        .filter_by(object_id=obj.id, language=language, section_code=code)
        .one_or_none()
    ) or ObjectContentSection(
        object_id=obj.id, language=language, section_code=code
    )
    row.body = body
    row.status = status
    row.source = "ai_generated"
    row.model = model
    row.generated_at = datetime.now(timezone.utc)
    db.add(row)
```

把 `persist_generated_sections` 循环体改为复用（行为不变）：

```python
    n = 0
    for code, body in sections.items():
        if not body:
            continue
        _upsert_section(db, obj, language, code, body, "published", model)
        n += 1
    db.commit()
    return n
```

再加新函数：

```python
def persist_gated_sections(db, qid: str, language: str, results: dict, model: str | None = None):
    """把质量闸结果落库（按 obj/lang/section upsert）。published 与 needs_review 段都建行，
    body 可为 None（needs_review 占位）。返回 (published_count, needs_review_count)。未知 qid → (0,0)。"""
    obj = db.query(MuseumObject).filter_by(qid=qid).one_or_none()
    if not obj:
        return (0, 0)
    pub = nr = 0
    for code, r in results.items():
        _upsert_section(db, obj, language, code, r.body, r.status, model)
        if r.status == "published":
            pub += 1
        else:
            nr += 1
    db.commit()
    return (pub, nr)
```

- [ ] **Step 4: 跑确认通过**

Run: `cd backend && poetry run pytest tests/integration/test_content_persist.py -v`
Expected: PASS（既有 + 新 3 全 passed）

- [ ] **Step 5: 提交**

```bash
cd backend && poetry run black app/services/content_repo.py tests/integration/test_content_persist.py && poetry run isort app/services/content_repo.py tests/integration/test_content_persist.py
cd /Users/hongyang/Projects/GoMuseum && git add backend/app/services/content_repo.py backend/tests/integration/test_content_persist.py
git commit -m "feat(content): persist_gated_sections 按段写published/needs_review(抽_upsert_section复用)"
```

---

## Task 6: 默认 LLM 判定接线（无新代码，仅验证可构造）

**Files:**
- Test: `backend/tests/unit/services/enrichment/test_quality.py`（追加 1 个构造冒烟）

`QualityGate` 与 `ContentEnricher` 同款注入 `complete`，真实运行复用 Phase 2a 已有的 `default_complete`（gpt-4o-mini），**无需新增默认实现**。本任务仅加一条"能用 default_complete 构造 QualityGate"的离线断言，锁死接口契约。

- [ ] **Step 1: 写失败测试（追加）**

```python
def test_quality_gate_constructible_with_default_complete():
    from app.services.enrichment.content_enricher import default_complete
    from app.services.enrichment.quality import QualityGate

    gate = QualityGate(default_complete)   # 不调用，只验证可构造、签名兼容
    assert callable(gate._complete)
```

- [ ] **Step 2: 跑确认失败/通过**

Run: `cd backend && poetry run pytest tests/unit/services/enrichment/test_quality.py -k constructible -v`
Expected: PASS（`default_complete` 与 `QualityGate` 都已存在 → 直接 PASS；若 import 错则 FAIL）

- [ ] **Step 3: 提交**

```bash
cd /Users/hongyang/Projects/GoMuseum && git add backend/tests/unit/services/enrichment/test_quality.py
git commit -m "test(enrichment): QualityGate 可用 default_complete 构造(锁接口)"
```

---

## 收尾

- [ ] **全套相关单测**：
```bash
cd backend && STORAGE_BACKEND=local poetry run pytest \
  tests/unit/services/enrichment/test_quality.py \
  tests/unit/services/enrichment/test_prompts.py \
  tests/integration/test_content_persist.py \
  -W "ignore::PendingDeprecationWarning" -v
```
Expected: 全 passed。

- [ ] **提 PR**：`feature/content-enrichment-phase2b → staging`（用 `/pr`）。无 DB 迁移。CI 绿后 squash 合并、删分支。
- [ ]（可选）合并后在 staging 容器重跑《奥林匹亚》验证：先 `generate_canonical` 拿草稿 → `QualityGate(default_complete).gate(material, facts, draft)` → 看 `artist` 段那句"印象派转型"是否被蕴含闸删掉/标 needs_review（对照本计划动机）。

---

## Self-Review（计划对照 spec §8）

- **§8A-1 接地/蕴含分**：`build_entailment_prompt`（Task 2）+ `check_section` 逐句删不支持句、`grounding_ratio`（Task 3）✓。
- **§8A-2 事实一致性**：`build_fact_consistency_prompt`（Task 2）+ `check_section` 冲突扣分/标审（Task 3）✓。
- **§8A 质量分→needs_review**：`score` 聚合 + `GROUNDING_THRESHOLD` + status 判定（Task 3），整件 `gate`（Task 4），落库 published/needs_review（Task 5）✓。
- **§8A-3 完整性（空段）**：absent 段在 `gate` 跳过、全删段 → needs_review（Task 3/4）✓。
- **§8A-4 格式/语言（langdetect）、§8A-5 译文忠实、§8A-6 安全 moderation、§8B 质量报告、§8D 金标准**：本期**显式不做**（langdetect/译文属 2c、moderation/报告/金标准留后续），已在范围说明标注 — 非遗漏。
- **注入式离线可测**：`QualityGate(complete)` 与 Phase 2a `ContentEnricher` 同款，单测全 mock（Task 3/4/6）✓。
- **类型一致性**：`SectionQuality(body,status,grounding_ratio,conflicts,score)` 跨 Task 3/4/5/6 一致；`gate` 返回 `{code: SectionQuality}`、`persist_gated_sections` 消费同型并返 `(pub,nr)` 元组，全计划一致 ✓。
- **DRY**：`_parse_json` 复用 Phase 2a、`_upsert_section` 抽出复用 ✓。
