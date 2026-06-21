# 内容富化 Phase 2d-2b 建议问答生成器 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 给每件作品接地预生成 3–4 个"问题+答案"（英语轴心 → 答案过蕴含闸 → 翻译铺语言 → 落 `persist_suggested_questions`），并接入 `generate_object` 管线，作 §12b 详情页推荐 chips 的内容来源。**收官 Phase 2。**

**Architecture:** 新增 `build_qa_prompt`（接地 Q&A prompt）+ `QASuggester(complete, gate, translator)`（注入式、离线可测：生成英语 Q&A → 复用 2b `QualityGate.check_section` 闸答案 → 复用 2c `ContentTranslator` 翻译 + 忠实校验）；`generate_object` 加**可选** `qa_suggester=None` 参数（不破既有 pipeline 测试），有则产出 + 按语言落库。

**Tech Stack:** Python 3.11 · FastAPI · SQLAlchemy · pytest · OpenAI（gpt-4o-mini，经 `default_complete`）。

**本期范围（2d-2 后半，收官 Phase 2）:** Q&A 生成 + gate + 翻译 + 接入管线。**多轮 `/ask` 端点、答案临时音频（§12b/§13b）= 后续 Phase**，不在本期。

**前置事实（已验证，勿重查）:**
- `build_material(obj)`、`_parse_json(text)`、`default_complete` 在 `content_enricher.py`。
- `QualityGate(complete).check_section(material, facts, body) -> SectionQuality(body,status,grounding_ratio,conflicts,score)`（2b，`quality.py`）。
- `ContentTranslator(complete).translate_section(body, lang) -> str` 与 `.check_faithfulness(en, tr, lang) -> (bool, list)`（2c，`translator.py`）。
- `persist_suggested_questions(db, qid, language, items, model) -> int`，`items=[{question,answer,status?}]`（2d-2a，`content_repo.py`）。
- `generate_object(db, qid, *, enricher, gate, translator, target_langs, model, force=False)` 与 `generate_museum(...)` 在 `pipeline.py`；内部已算 `material`/`facts`/`o.category`。
- `cmd_generate`（`onboard.py`）构造 `ContentEnricher`/`QualityGate`/`ContentTranslator(default_complete)` 并调 `generate_object`/`generate_museum`。
- prompts.py 既有 `_parse_json` 由各调用方用；QASuggester 也用 `_parse_json` 解析。

---

## 文件结构

| 文件 | 职责 | 动作 |
|---|---|---|
| `backend/app/services/enrichment/prompts.py` | 加 `build_qa_prompt(material, category)` | 修改（追加） |
| `backend/app/services/enrichment/qa_suggester.py` | `QASuggester`：生成→闸→翻译 | **新建** |
| `backend/app/services/enrichment/pipeline.py` | `generate_object`/`generate_museum` 加可选 `qa_suggester` | 修改 |
| `backend/scripts/onboard.py` | `cmd_generate` 构造并传 `QASuggester` | 修改 |
| `backend/tests/unit/services/enrichment/test_prompts.py` | 追加 qa prompt 断言 | 修改 |
| `backend/tests/unit/services/enrichment/test_qa_suggester.py` | QASuggester 单测 | **新建** |
| `backend/tests/integration/test_generate_pipeline.py` | 追加 generate_object 落 Q&A 测试 | 修改 |

**关键接口（先定死）:**

```python
# prompts.py
def build_qa_prompt(material: str, category: str) -> tuple[str, str]: ...   # 返 {"qa":[{question,answer}]}

# qa_suggester.py
class QASuggester:
    def __init__(self, complete, gate, translator): ...
    def suggest(self, material: str, facts: str, category: str, target_langs: list[str]) -> dict: ...
    # 返回 {lang: [{"question","answer","status"}]}

# pipeline.generate_object 加可选关键字参数 qa_suggester=None（None→不产 Q&A）
```

---

## Task 1: `build_qa_prompt`

**Files:**
- Modify: `backend/app/services/enrichment/prompts.py`（追加）
- Test: `backend/tests/unit/services/enrichment/test_prompts.py`（追加）

- [ ] **Step 1: 写失败测试（追加）**

```python
def test_qa_prompt_grounded_json_pairs():
    from app.services.enrichment.prompts import build_qa_prompt

    system, user = build_qa_prompt("[FACTS]\n- Title: Olympia", "painting")
    blob = (system + user).lower()
    assert "only" in blob and "material" in blob       # 接地 only
    assert "json" in blob and "qa" in blob              # JSON {"qa":[...]}
    assert "question" in blob and "answer" in blob
    assert "[FACTS]\n- Title: Olympia" in user
```

- [ ] **Step 2: 跑确认失败**

Run: `cd backend && poetry run pytest tests/unit/services/enrichment/test_prompts.py -k qa_prompt -v`
Expected: FAIL（`cannot import name build_qa_prompt`）

- [ ] **Step 3: 追加到 `prompts.py` 末尾**

```python
_QA_SYSTEM = (
    "You are a museum guide. From the provided MATERIAL about ONE artwork, write 3 to 4 "
    "engaging visitor questions and their answers. Use ONLY facts present in the material; "
    "do NOT use outside knowledge. Each answer must be fully supported by the material; if "
    "you cannot answer from the material, omit that question. Original wording, concise. "
    'Return STRICT JSON: {"qa": [{"question": "...", "answer": "..."}, ...]}. No commentary.'
)


def build_qa_prompt(material: str, category: str):
    user = f"Artwork category: {category}\n\nMATERIAL:\n{material}"
    return _QA_SYSTEM, user
```

- [ ] **Step 4: 跑确认通过**

Run: `cd backend && poetry run pytest tests/unit/services/enrichment/test_prompts.py -v`
Expected: PASS（既有 + 新 1 全 passed）

- [ ] **Step 5: 提交**

```bash
cd backend && poetry run black app/services/enrichment/prompts.py tests/unit/services/enrichment/test_prompts.py && poetry run isort app/services/enrichment/prompts.py tests/unit/services/enrichment/test_prompts.py
cd /Users/hongyang/Projects/GoMuseum && git add backend/app/services/enrichment/prompts.py backend/tests/unit/services/enrichment/test_prompts.py
git commit -m "feat(enrichment): 接地 Q&A 生成 prompt(3-4问答/只依据材料/JSON)"
```

---

## Task 2: `QASuggester`（生成 → 闸答案 → 翻译铺语言）

**Files:**
- Create: `backend/app/services/enrichment/qa_suggester.py`
- Test: `backend/tests/unit/services/enrichment/test_qa_suggester.py`

设计要点：
- `suggest(material, facts, category, target_langs)`：
  1. 一次 `complete` 生成英语 Q&A（`build_qa_prompt` + `_parse_json` 取 `qa` 列表）。
  2. 每条答案过 `gate.check_section(material, facts, answer)`：published 且有 body → `{question, answer=r.body, status="published"}`；否则 `{question, answer=原答案, status="needs_review"}`。空 question/answer 跳过。
  3. 英语进 `out["en"]`；**仅 published 英语 Q&A** 翻译到其余 `target_langs`（跳过 "en"）：`translate_section` 译问与答 + `check_faithfulness` 验答案译文 → 忠实 published / 否则 needs_review。
- 返回 `{lang: [{"question","answer","status"}]}`。

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/unit/services/enrichment/test_qa_suggester.py
import json

from app.services.enrichment.qa_suggester import QASuggester
from app.services.enrichment.quality import SectionQuality


class _Complete:
    def __call__(self, system, user):
        return json.dumps(
            {"qa": [
                {"question": "Q1?", "answer": "A1 grounded."},
                {"question": "Q2?", "answer": "A2 ungrounded."},
            ]}
        )


class _Gate:
    # A1 接地→published；A2 不接地→needs_review
    def check_section(self, material, facts, body):
        if "A1" in body:
            return SectionQuality(body=body, status="published",
                                  grounding_ratio=1.0, conflicts=[], score=1.0)
        return SectionQuality(body=None, status="needs_review",
                              grounding_ratio=0.0, conflicts=[], score=0.0)


class _Translator:
    def translate_section(self, body, lang):
        return f"[{lang}] {body}"

    def check_faithfulness(self, en, tr, lang):
        return True, []


def test_suggest_en_gates_answers_and_translates_published():
    s = QASuggester(_Complete(), _Gate(), _Translator())
    out = s.suggest("material", "facts", "painting", ["en", "fr"])

    # 英语：A1 published、A2 needs_review
    en = out["en"]
    assert {i["status"] for i in en} == {"published", "needs_review"}
    a1 = next(i for i in en if i["question"] == "Q1?")
    assert a1["status"] == "published" and a1["answer"] == "A1 grounded."

    # 法语：仅已发布 A1 被翻译
    fr = out["fr"]
    assert len(fr) == 1
    assert fr[0]["question"] == "[fr] Q1?"
    assert fr[0]["answer"] == "[fr] A1 grounded."
    assert fr[0]["status"] == "published"


def test_suggest_skips_empty_pairs():
    class _C:
        def __call__(self, system, user):
            return json.dumps({"qa": [{"question": "", "answer": "x"},
                                      {"question": "Q?", "answer": ""}]})

    s = QASuggester(_C(), _Gate(), _Translator())
    out = s.suggest("m", "f", "painting", ["en"])
    assert out["en"] == []
```

- [ ] **Step 2: 跑确认失败**

Run: `cd backend && poetry run pytest tests/unit/services/enrichment/test_qa_suggester.py -v`
Expected: FAIL（`ModuleNotFoundError: qa_suggester`）

- [ ] **Step 3: 创建 `backend/app/services/enrichment/qa_suggester.py`**

```python
"""QASuggester：每件接地预生成 3-4 个"问题+答案"（英语轴心→答案过闸→翻译铺语言）。
组件注入（complete/gate/translator），离线可测。spec §12b 推荐 chips。"""

from __future__ import annotations

from app.services.enrichment.prompts import build_qa_prompt


def _parse():
    from app.services.enrichment.content_enricher import _parse_json

    return _parse_json


class QASuggester:
    def __init__(self, complete, gate, translator):
        self._complete = complete
        self._gate = gate
        self._translator = translator

    def _generate_en(self, material: str, facts: str, category: str) -> list:
        raw = self._complete(*build_qa_prompt(material, category))
        pairs = _parse()(raw).get("qa") or []
        items = []
        for p in pairs:
            q = (p.get("question") or "").strip()
            a = (p.get("answer") or "").strip()
            if not q or not a:
                continue
            r = self._gate.check_section(material, facts, a)
            if r.status == "published" and r.body:
                items.append({"question": q, "answer": r.body, "status": "published"})
            else:
                items.append({"question": q, "answer": a, "status": "needs_review"})
        return items

    def suggest(self, material: str, facts: str, category: str, target_langs: list) -> dict:
        en_items = self._generate_en(material, facts, category)
        out = {"en": en_items}
        published = [it for it in en_items if it["status"] == "published"]
        for lang in target_langs:
            if lang == "en":
                continue
            litems = []
            for it in published:
                tq = self._translator.translate_section(it["question"], lang)
                ta = self._translator.translate_section(it["answer"], lang)
                ok, _ = self._translator.check_faithfulness(it["answer"], ta, lang)
                litems.append(
                    {
                        "question": tq,
                        "answer": ta,
                        "status": "published" if ok else "needs_review",
                    }
                )
            out[lang] = litems
        return out
```

- [ ] **Step 4: 跑确认通过**

Run: `cd backend && poetry run pytest tests/unit/services/enrichment/test_qa_suggester.py -v`
Expected: PASS（2 passed）

- [ ] **Step 5: 提交**

```bash
cd backend && poetry run black app/services/enrichment/qa_suggester.py tests/unit/services/enrichment/test_qa_suggester.py && poetry run isort app/services/enrichment/qa_suggester.py tests/unit/services/enrichment/test_qa_suggester.py
cd /Users/hongyang/Projects/GoMuseum && git add backend/app/services/enrichment/qa_suggester.py backend/tests/unit/services/enrichment/test_qa_suggester.py
git commit -m "feat(enrichment): QASuggester 生成Q&A+闸答案+翻译铺语言"
```

---

## Task 3: 接入 `generate_object` / `generate_museum` + CLI

**Files:**
- Modify: `backend/app/services/enrichment/pipeline.py`（`generate_object`/`generate_museum` 加可选 `qa_suggester`）
- Modify: `backend/scripts/onboard.py`（`cmd_generate` 构造并传 `QASuggester`）
- Test: `backend/tests/integration/test_generate_pipeline.py`（追加）

设计要点：
- `generate_object(..., qa_suggester=None)`：产出分段后，若 `qa_suggester` 非 None → `qa_suggester.suggest(material, facts, o.category, target_langs)` → 逐语言 `persist_suggested_questions` → 返回 dict 加 `"qa": {lang: count}`。**`qa_suggester=None` 时行为完全不变**（既有测试不破）。
- `generate_museum(..., qa_suggester=None)`：透传给 `generate_object`。
- `cmd_generate`：构造 `QASuggester(default_complete, gate, translator)` 并传入。

- [ ] **Step 1: 写失败测试（追加到 `test_generate_pipeline.py`）**

```python
class _FakeQA:
    def suggest(self, material, facts, category, target_langs):
        from app.services.enrichment.quality import SectionQuality  # noqa: F401

        return {
            "en": [{"question": "Q?", "answer": "A.", "status": "published"}],
            "fr": [{"question": "Q-fr?", "answer": "A-fr.", "status": "published"}],
        }


def test_generate_object_persists_suggested_questions(session):
    from app.services.enrichment.pipeline import generate_object
    from app.models.content import ObjectSuggestedQuestion

    out = generate_object(
        session, "Q1",
        enricher=_FakeEnricher(), gate=_FakeGate(), translator=_FakeTranslator(),
        target_langs=["en", "fr"], model="gpt-4o-mini", qa_suggester=_FakeQA(),
    )
    assert out["qa"] == {"en": 1, "fr": 1}
    rows = session.query(ObjectSuggestedQuestion).all()
    langs = {r.language for r in rows}
    assert langs == {"en", "fr"}
    en = next(r for r in rows if r.language == "en")
    assert en.question == "Q?" and en.answer == "A." and en.status == "published"


def test_generate_object_without_qa_suggester_unchanged(session):
    # qa_suggester 缺省 None → 不产 Q&A、无 "qa" 键（既有行为不破）
    from app.services.enrichment.pipeline import generate_object
    from app.models.content import ObjectSuggestedQuestion

    out = generate_object(
        session, "Q1",
        enricher=_FakeEnricher(), gate=_FakeGate(), translator=_FakeTranslator(),
        target_langs=["en", "fr"], model="m",
    )
    assert "qa" not in out
    assert session.query(ObjectSuggestedQuestion).count() == 0
```

> 本测试需 `ObjectSuggestedQuestion` 表。**在 `test_generate_pipeline.py` 的 `session` fixture 的 `create_all` tables 列表里补 `ObjectSuggestedQuestion.__table__`，并在文件顶部 import `from app.models.content import ObjectSuggestedQuestion`**（与既有 `ObjectContentSection` import 并列）。

- [ ] **Step 2: 跑确认失败**

Run: `cd backend && poetry run pytest tests/integration/test_generate_pipeline.py -k "suggested or qa" -v`
Expected: FAIL（`generate_object` 无 `qa_suggester` 参数 / 无 `qa` 键）

- [ ] **Step 3a: 改 `pipeline.py`**

顶部 import 加 `from app.services.content_repo import persist_suggested_questions`（与既有 `from app.services.content_repo import persist_gated_sections` 并列，可合一行）。

`generate_object` 签名加 `qa_suggester=None`，在 `return` 前插入：

```python
    result = {"qid": qid, "counts": counts}
    if qa_suggester is not None:
        qa_by_lang = qa_suggester.suggest(material, facts, o.category, target_langs)
        qa_counts = {}
        for lang, items in qa_by_lang.items():
            qa_counts[lang] = persist_suggested_questions(db, qid, lang, items, model)
        result["qa"] = qa_counts
    return result
```

（即把原 `return {"qid": qid, "counts": counts}` 替换为上面这段。）

`generate_museum` 签名加 `qa_suggester=None`，并在调 `generate_object(...)` 时传 `qa_suggester=qa_suggester`。

- [ ] **Step 3b: 改 `onboard.py` 的 `cmd_generate`**

import 区（函数内已有 `from ... import ContentEnricher, default_complete` 等）加 `from app.services.enrichment.qa_suggester import QASuggester`；构造组件处加：

```python
    qa_suggester = QASuggester(default_complete, gate, translator)
```

并把 `generate_object(...)` 与 `generate_museum(...)` 两处调用都加上 `qa_suggester=qa_suggester`。

- [ ] **Step 4: 跑确认通过**

Run: `cd backend && poetry run pytest tests/integration/test_generate_pipeline.py tests/unit/services/enrichment/test_onboard_cli.py -v`
Expected: PASS（既有全绿 + 新 2）。

- [ ] **Step 5: 提交**

```bash
cd backend && poetry run black app/services/enrichment/pipeline.py scripts/onboard.py tests/integration/test_generate_pipeline.py && poetry run isort app/services/enrichment/pipeline.py scripts/onboard.py tests/integration/test_generate_pipeline.py
cd /Users/hongyang/Projects/GoMuseum && git add backend/app/services/enrichment/pipeline.py backend/scripts/onboard.py backend/tests/integration/test_generate_pipeline.py
git commit -m "feat(enrichment): generate_object 接入 QASuggester(可选,落 suggested_questions)"
```

---

## 收尾

- [ ] **全套相关测试**：
```bash
cd backend && STORAGE_BACKEND=local poetry run pytest \
  tests/unit/services/enrichment/test_prompts.py \
  tests/unit/services/enrichment/test_qa_suggester.py \
  tests/unit/services/enrichment/test_onboard_cli.py \
  tests/integration/test_generate_pipeline.py \
  tests/integration/test_suggested_questions.py \
  -W "ignore::PendingDeprecationWarning" -v
```
Expected: 全 passed。

- [ ] **提 PR**：`feature/content-enrichment-phase2d2b → staging`（用 `/pr`）。无 DB 迁移（表已在 2d-2a）。CI 绿后 squash 合并、删分支。
- [ ]（合并部署后·端到端收官验证）staging 容器对 Q737062 重跑 `onboard generate --qid Q737062 --langs en,fr --force`，再
  `get_object_content(...,'Q737062','en')['suggested_questions']` 应返回若干 `{question,answer}`；肉眼看问答接地不脑补。

---

## Self-Review（计划对照 spec §12b）

- **§12b 预生成 3–4 个"问题+预回答"**：`build_qa_prompt`（Task 1）+ `QASuggester._generate_en`（Task 2）✓。
- **§12b grounded + 蕴含校验**：prompt 强约束 + 答案过 `QualityGate.check_section`（Task 2）✓。
- **§12b 多语言**：`suggest` 翻译已发布英语 Q&A + 译文忠实校验（Task 2）✓。
- **§12b 落库供 chips**：`generate_object` 接入 + `persist_suggested_questions`（Task 3，落库由 2d-2a 提供；读出 `suggested_questions` 由 2d-2a `get_object_content`）✓。
- **不破既有 pipeline**：`qa_suggester=None` 缺省、行为不变（Task 3 第二测试守这条）✓。
- **本期不做（显式）**：多轮 `/ask` 端点、答案临时音频（§12b/§13b）= 后续 Phase ✓。
- **类型一致性**：`suggest(...) -> {lang: [{question,answer,status}]}`，喂 `persist_suggested_questions(items=[{question,answer,status?}])` 一致（Task 2/3）；`generate_object` 加 `"qa": {lang:count}` 加法键 ✓。
- **DRY**：复用 2b `QualityGate.check_section`、2c `translate_section`/`check_faithfulness`、`_parse_json`、`build_material`/`_facts_text` ✓。
