# 问答去重 + analysis lane 收重叠 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** ① 问答生成拿到"已讲内容"(解说+模块)→ 只问没讲过的(去重);② analysis lane 收到"怎么画的(技法)"、不复述解说已点符号;③ 作者卡固定展示顺序(前端交接)。

**Architecture:** `build_qa_prompt` 加 `covered`;`QASuggester`/`pipeline` 透传 `en_published` 拼接;`analysis` role 改技法聚焦。无契约/迁移。spec `2026-07-01-qa-dedup-analysis-lane-design.md`。

**Tech Stack:** Python + pytest。

> 命令在 `backend/` 下跑。

---

### Task 1: build_qa_prompt 加 covered + 去重指令

**Files:**
- Modify: `backend/app/services/enrichment/prompts.py`
- Test: `backend/tests/unit/services/enrichment/test_prompts.py`

参考:`build_qa_prompt(material, category)`(160 行)现 `user = f"Artwork category: {category}\n\nMATERIAL:\n{material}"`,返回 `(_QA_SYSTEM, user)`。

- [ ] **Step 1: 写失败测试**

```python
def test_qa_prompt_includes_covered_dedup():
    from app.services.enrichment.prompts import build_qa_prompt

    _, user = build_qa_prompt("MAT", "painting", covered="解说已讲了猫和花的象征。")
    assert "解说已讲了猫和花" in user
    assert "already" in user.lower() or "已" in user or "not" in user.lower()


def test_qa_prompt_covered_optional():
    from app.services.enrichment.prompts import build_qa_prompt
    _, user = build_qa_prompt("MAT", "painting")
    assert "MAT" in user  # 无 covered 不报错
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && python -m pytest tests/unit/services/enrichment/test_prompts.py::test_qa_prompt_includes_covered_dedup -q`
Expected: FAIL

- [ ] **Step 3: 实现** — 改 `build_qa_prompt`:

```python
def build_qa_prompt(material: str, category: str, covered: str | None = None):
    covered_block = (
        "\n\nALREADY TOLD to the visitor (in the guide and modules) — do NOT ask questions "
        "whose answer is already covered here; ask only what extends BEYOND it:\n"
        f"\"\"\"\n{covered}\n\"\"\""
        if covered
        else ""
    )
    user = f"Artwork category: {category}{covered_block}\n\nMATERIAL:\n{material}"
    return _QA_SYSTEM, user
```

- [ ] **Step 4: 通过 + 提交**

Run: `cd backend && python -m pytest tests/unit/services/enrichment/test_prompts.py -q`（PASS,含既有）
```bash
cd backend && git add app/services/enrichment/prompts.py tests/unit/services/enrichment/test_prompts.py
git commit -m "feat(qa): build_qa_prompt 加 covered + 只问没讲过指令"
```

---

### Task 2: QASuggester 透传 covered

**Files:**
- Modify: `backend/app/services/enrichment/qa_suggester.py`
- Test: `backend/tests/unit/services/enrichment/test_qa_suggester.py`

参考:`QASuggester._generate_en(self, material, facts, category)` 调 `build_qa_prompt(material, category)`;`.suggest(self, material, facts, category, target_langs)` 调 `_generate_en`。

- [ ] **Step 1: 写失败测试** — 在 `test_qa_suggester.py` 追加(注入 fake complete 捕获 user):

```python
def test_suggest_passes_covered_to_prompt():
    from app.services.enrichment.qa_suggester import QASuggester

    captured = {}

    def fake_complete(system, user):
        captured["user"] = user
        import json as _json
        return _json.dumps({"qa": []})

    class _G:
        def check_section(self, m, f, b):
            from app.services.enrichment.quality import SectionQuality
            return SectionQuality(body=b, status="published", grounding_ratio=1.0, conflicts=[], score=1.0)

    class _T:
        pass

    s = QASuggester(complete=fake_complete, gate=_G(), translator=_T())
    s.suggest("MAT", "facts", "painting", ["en"], covered="解说讲过猫和花。")
    assert "解说讲过猫和花" in captured["user"]
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && python -m pytest tests/unit/services/enrichment/test_qa_suggester.py::test_suggest_passes_covered_to_prompt -q`
Expected: FAIL（suggest 不接受 covered）

- [ ] **Step 3: 实现** —
- `_generate_en(self, material, facts, category, covered=None)`:`raw = self._complete(*build_qa_prompt(material, category, covered))`。
- `suggest(self, material, facts, category, target_langs, covered=None)`:`en_items = self._generate_en(material, facts, category, covered)`。

- [ ] **Step 4: 通过(含既有) + 提交**

Run: `cd backend && python -m pytest tests/unit/services/enrichment/test_qa_suggester.py -q`（PASS）
```bash
cd backend && git add app/services/enrichment/qa_suggester.py tests/unit/services/enrichment/test_qa_suggester.py
git commit -m "feat(qa): QASuggester suggest/_generate_en 透传 covered"
```

---

### Task 3: pipeline 把 en_published 作为 covered 传给 QA

**Files:**
- Modify: `backend/app/services/enrichment/pipeline.py`
- Test: `backend/tests/integration/test_generate_pipeline.py`

参考:`generate_object` 现 `qa_by_lang = qa_suggester.suggest(material, facts, o.category, target_langs)`(约 165 行);此处 `en_published`(dict code→body,含 guide+模块)已构建完。

- [ ] **Step 1: 写失败测试** — 追加(自定义 qa_suggester 捕获 covered):

```python
def test_generate_object_passes_covered_to_qa(session):
    from app.services.enrichment.pipeline import generate_object
    from app.services.enrichment.quality import SectionQuality

    seen = {}

    class _QA:
        def suggest(self, material, facts, category, target_langs, covered=None):
            seen["covered"] = covered
            return {"en": []}

    class _Enr(_FakeEnricher):
        def generate_canonical(self, obj, sections, guide=None):
            return {"background": "深度背景正文。"}

    class _G(_FakeGate):
        def check_section(self, m, f, b):
            return SectionQuality(body=b, status="published", grounding_ratio=1.0, conflicts=[], score=1.0)

    generate_object(session, "Q1", enricher=_Enr(), gate=_G(),
                    translator=_FakeTranslator(), target_langs=["en"], model="m",
                    qa_suggester=_QA())
    assert seen["covered"] and "深度背景正文" in seen["covered"]  # 模块正文进了 covered
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && python -m pytest tests/integration/test_generate_pipeline.py::test_generate_object_passes_covered_to_qa -q`
Expected: FAIL

- [ ] **Step 3: 实现** — 改 QA 调用:

```python
    if qa_suggester is not None:
        covered = "\n\n".join(v for v in en_published.values() if v)
        qa_by_lang = qa_suggester.suggest(
            material, facts, o.category, target_langs, covered=covered
        )
```

- [ ] **Step 4: 通过(含既有) + 提交**

Run: `cd backend && python -m pytest tests/integration/test_generate_pipeline.py -q`（全 PASS）
```bash
cd backend && git add app/services/enrichment/pipeline.py tests/integration/test_generate_pipeline.py
git commit -m "feat(qa): pipeline 把 en_published(解说+模块)作 covered 传给问答去重"
```

---

### Task 4: analysis lane 收技法

**Files:**
- Modify: `backend/app/services/enrichment/category_config.py`
- Test: `backend/tests/unit/services/enrichment/test_category_config.py`

参考:`SECTION_ROLES["analysis"]["role"]` 现 = "Guided LOOKING: composition, technique, brushwork, what to notice with your eyes. NOT history or influence."

- [ ] **Step 1: 写失败测试**

```python
def test_analysis_lane_focuses_craft_not_symbols():
    from app.services.enrichment.category_config import section_role

    role = section_role("analysis")["role"].lower()
    assert "craft" in role or "brushwork" in role
    assert "do not re-list" in role or "go beyond" in role or "headline" in role
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && python -m pytest tests/unit/services/enrichment/test_category_config.py::test_analysis_lane_focuses_craft_not_symbols -q`
Expected: FAIL

- [ ] **Step 3: 实现** — `SECTION_ROLES["analysis"]["role"]` 改为:

```python
        "role": "HOW it's painted — the craft: brushwork, paint handling, light & colour, composition structure, scale. Explain technique and the choices behind the effect. Do NOT re-list the symbols/subjects the headline guide already pointed out; go beyond naming them to how the painting achieves its impact.",
```
(`max_chars` 不动。)

- [ ] **Step 4: 通过(含既有 lane 用例) + 提交**

Run: `cd backend && python -m pytest tests/unit/services/enrichment/test_category_config.py -q`（PASS;既有 `test_section_roles_are_distinct_lanes` 若断言 analysis 旧措辞需同步)
```bash
cd backend && git add app/services/enrichment/category_config.py tests/unit/services/enrichment/test_category_config.py
git commit -m "feat(gen): analysis lane 收到技法(怎么画的)、不复述解说符号"
```

---

### Task 5: 全量回归 + 前端交接 + 契约回写

**Files:**
- Create: `docs/handoff/2026-07-01-artist-card-order-frontend.md`
- Modify: `docs/architecture/museum-api-contract.md`

- [ ] **Step 1: 全量回归**

Run: `cd backend && python -m pytest tests/unit/services/enrichment/ tests/integration/test_generate_pipeline.py tests/integration/test_pack_and_content_facts.py -q`
Expected: PASS

- [ ] **Step 2: 前端交接** — `docs/handoff/2026-07-01-artist-card-order-frontend.md`:作者卡 `GuideArtistCard` 按**固定顺序**展示:姓名 → 生卒年(birth–death)→ 国籍/籍贯(nationality)→ 主要作品(notable_works)→ 生平(bio);结构化字段在前、bio 在后;缺字段不显(name 一定有)。

- [ ] **Step 3: 回写主文档** — 内容体系:① 问答"补头条/模块没答的"已落地(QA 收到 covered 去重)② analysis lane 改为"怎么画的(技法)"、guide=看什么/含义;变更记录加一行。

- [ ] **Step 4: 提交**

```bash
cd /Users/hongyang/Projects/GoMuseum && git add docs/handoff/2026-07-01-artist-card-order-frontend.md docs/architecture/museum-api-contract.md
git commit -m "docs: 作者卡展示顺序交接 + 回写问答去重/analysis技法"
```

---

## Self-Review

- **Spec 覆盖**:QA covered prompt(T1)✓ QASuggester 透传(T2)✓ pipeline 传 en_published(T3)✓ analysis 收技法(T4)✓ 交接+回写(T5)✓。
- **向后兼容**:covered/参数均可选缺省;无契约/迁移。
- **类型一致**:`build_qa_prompt(material, category, covered=None)`(T1)→ `_generate_en(...,covered)`/`suggest(...,covered=None)`(T2)→ pipeline 传 `covered=`(T3)。
- **#2 是前端**:后端数据已就绪,仅交接(T5)。

## 上线验证(合 staging 后)

1. 重生成奥林匹亚:`generate --qid Q737062 --target staging --langs zh --force`。
2. curl content:① 4 条问答**不再复述**解说/模块(问别的角度)② analysis 讲**技法**(笔触/光色/构图)而非复述猫和花。
3. 前端接作者卡顺序后 APK 看固定结构。
