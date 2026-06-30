# 模块深度提升(按热度分档)Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 抬高深度模块字数上限 + 按热度分档(重点件 ×1.5),名作能深则深、薄件天然短;prompt 强化"深=具体细节不注水"。

**Architecture:** `SECTION_ROLES.max_chars` 改为 base 值 + 新 `section_target_chars(code, popularity)`;`build_generation_prompt` 按档套上限 + 接 popularity(经 `_row_to_obj`→`generate_canonical`)。接地闸+2a去重兜底防注水。spec `2026-06-30-module-depth-design.md`。

**Tech Stack:** Python + pytest。

> 命令在 `backend/` 下跑。

---

### Task 1: 抬高 base 上限 + section_target_chars

**Files:**
- Modify: `backend/app/services/enrichment/category_config.py`
- Test: `backend/tests/unit/services/enrichment/test_category_config.py`

参考:`SECTION_ROLES`(169 行起,各 code→{role,max_chars});`GUIDE_KEY_THRESHOLD=30`;`guide_target_chars`(分档范例)。

- [ ] **Step 1: 写失败测试**

```python
def test_section_target_chars_tiers():
    from app.services.enrichment.category_config import section_target_chars

    # 重点件(pop>=30)= base×1.5;普通件=base
    assert section_target_chars("background", 40) == int(380 * 1.5)  # 570
    assert section_target_chars("background", 10) == 380
    assert section_target_chars("background", None) == 380
    assert section_target_chars("facts", 50) == int(200 * 1.5)  # 300


def test_section_roles_base_raised():
    from app.services.enrichment.category_config import SECTION_ROLES

    assert SECTION_ROLES["background"]["max_chars"] == 380
    assert SECTION_ROLES["analysis"]["max_chars"] == 380
    assert SECTION_ROLES["artist"]["max_chars"] == 260
    assert SECTION_ROLES["significance"]["max_chars"] == 240
    assert SECTION_ROLES["facts"]["max_chars"] == 200
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && python -m pytest tests/unit/services/enrichment/test_category_config.py -q`
Expected: FAIL

- [ ] **Step 3: 实现** —
(a) `SECTION_ROLES` 改 max_chars 为 base:artist 260、background 380、analysis 380、significance 240、facts 200(role 文本不动)。其余 code(material-technique/context/maker/use/photographer)若现 <240,适度抬到 ~240(可选,保守不改也行)。
(b) `guide_target_chars` 附近加:
```python
def section_target_chars(code: str, popularity: int | None) -> int:
    """模块字数上限,按热度分档:重点件(>=阈值)base×1.5,普通件 base。"""
    base = SECTION_ROLES.get(code, _DEFAULT_ROLE)["max_chars"]
    if (popularity or 0) >= GUIDE_KEY_THRESHOLD:
        return int(base * 1.5)
    return base
```

- [ ] **Step 4: 通过 + 提交**

Run: `cd backend && python -m pytest tests/unit/services/enrichment/test_category_config.py -q`（PASS,含既有锐化 lane 用例——若既有用例断言旧 max_chars 值,同步改)
```bash
cd backend && git add app/services/enrichment/category_config.py tests/unit/services/enrichment/test_category_config.py
git commit -m "feat(depth): 抬高模块 base 上限 + section_target_chars 按热度分档"
```

---

### Task 2: build_generation_prompt 按档套上限 + 不注水指令

**Files:**
- Modify: `backend/app/services/enrichment/prompts.py`
- Test: `backend/tests/unit/services/enrichment/test_prompts.py`

参考:`build_generation_prompt(material, sections, category, guide=None)` 现各段行用 `section_role(code)['max_chars']`。

- [ ] **Step 1: 写失败测试**

```python
def test_generation_prompt_tiers_length_by_popularity():
    from app.services.enrichment.prompts import build_generation_prompt

    system, user_key = build_generation_prompt("M", ["background"], "painting", popularity=40)
    system, user_norm = build_generation_prompt("M", ["background"], "painting", popularity=5)
    assert "570" in user_key  # 重点件 background 380×1.5
    assert "380" in user_norm  # 普通件
    assert "注水" in user_key or "specific" in user_key.lower() or "fluff" in user_key.lower()


def test_generation_prompt_popularity_optional():
    from app.services.enrichment.prompts import build_generation_prompt
    system, user = build_generation_prompt("M", ["artist"], "painting")
    assert "artist" in user  # 无 popularity 不报错
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && python -m pytest tests/unit/services/enrichment/test_prompts.py::test_generation_prompt_tiers_length_by_popularity -q`
Expected: FAIL（不接受 popularity / 用旧 max_chars）

- [ ] **Step 3: 实现** — `build_generation_prompt` 签名加 `popularity=None`;各段行 aim 改用 `section_target_chars`:

```python
def build_generation_prompt(material, sections, category, guide=None, popularity=None):
    from app.services.enrichment.category_config import section_role, section_target_chars

    lines = []
    for code in sections:
        r = section_role(code)
        aim = section_target_chars(code, popularity)
        lines.append(f"- {code} — {r['role']} (aim ~{aim} Chinese-char equivalent)")
    roles_block = "\n".join(lines)
    # ...（guide_block 不变）...
    user = (
        f"Artwork category: {category}\n"
        f"Write these sections (return JSON keyed by these exact codes), each staying strictly "
        f"in its lane. Go DEEPER by unpacking concrete facts and details FROM THE MATERIAL — "
        f"never pad or 注水 with generic filler:\n{roles_block}\n{guide_block}\n"
        f"Material (facts tagged with their lane topic):\n{material}"
    )
    return _SYSTEM, user
```
(保留上一阶段 guide_block 逻辑不变。)

- [ ] **Step 4: 通过 + 提交**

Run: `cd backend && python -m pytest tests/unit/services/enrichment/test_prompts.py -q`（PASS,含既有 guide 去重用例）
```bash
cd backend && git add app/services/enrichment/prompts.py tests/unit/services/enrichment/test_prompts.py
git commit -m "feat(depth): build_generation_prompt 按热度分档套上限 + 不注水指令"
```

---

### Task 3: generate_canonical 取 popularity + _row_to_obj 补 popularity

**Files:**
- Modify: `backend/app/services/enrichment/content_enricher.py`
- Modify: `backend/app/services/enrichment/pipeline.py`
- Test: `backend/tests/unit/services/enrichment/test_content_enricher.py`

- [ ] **Step 1: 写失败测试**

```python
def test_generate_canonical_passes_popularity():
    from app.services.enrichment.content_enricher import ContentEnricher

    captured = {}

    def fake(system, user):
        captured["user"] = user
        import json as _json
        return _json.dumps({"background": "B."})

    enr = ContentEnricher(complete=fake)
    enr.generate_canonical(
        {"qid": "Q1", "category": "painting", "attributes": {}, "popularity": 40},
        sections=["background"],
    )
    assert "570" in captured["user"]  # 重点件 background 380×1.5
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && python -m pytest tests/unit/services/enrichment/test_content_enricher.py::test_generate_canonical_passes_popularity -q`
Expected: FAIL

- [ ] **Step 3: 实现** —
(a) `content_enricher.generate_canonical`:`build_generation_prompt(..., guide=guide, popularity=obj.get("popularity"))`。
(b) `pipeline._row_to_obj(o)`:返回 dict 加 `"popularity": getattr(o, "popularity", None)`。

- [ ] **Step 4: 通过(含既有) + 提交**

Run: `cd backend && python -m pytest tests/unit/services/enrichment/test_content_enricher.py tests/integration/test_generate_pipeline.py -q`（全 PASS）
```bash
cd backend && git add app/services/enrichment/content_enricher.py app/services/enrichment/pipeline.py tests/unit/services/enrichment/test_content_enricher.py
git commit -m "feat(depth): generate_canonical 取 obj popularity 透传 + _row_to_obj 补 popularity"
```

---

### Task 4: 全量回归 + 回写主文档

**Files:**
- Modify: `docs/architecture/museum-api-contract.md`

- [ ] **Step 1: 全量回归**

Run: `cd backend && python -m pytest tests/unit/services/enrichment/ tests/integration/test_generate_pipeline.py tests/integration/test_pack_and_content_facts.py -q`
Expected: PASS

- [ ] **Step 2: 回写主文档** — 内容体系/模块库处加一句"深度模块字数按热度分档(重点件 ×1.5),名作能深则深、薄件天然短;深=具体细节非注水";变更记录加一行。

- [ ] **Step 3: 提交**

```bash
cd /Users/hongyang/Projects/GoMuseum && git add docs/architecture/museum-api-contract.md
git commit -m "docs(api): 回写模块深度按热度分档"
```

---

## Self-Review

- **Spec 覆盖**:base 上限+section_target_chars(T1)✓ prompt 分档+不注水(T2)✓ generate_canonical/popularity 接线(T3)✓ 回写(T4)✓。
- **不注水**:上限=天花板;接地闸+2a去重兜底(spec §4)。
- **向后兼容**:无契约/迁移改动;popularity 缺省 → base 档不报错。
- **类型一致**:`section_target_chars(code, popularity)->int`(T1 定义,T2 用);`build_generation_prompt(...,popularity=None)`(T2 定义,T3 调);`_row_to_obj` popularity(T3)→ obj["popularity"](T3 generate_canonical 用)。

## 上线验证(合 staging 后)

1. 重生成名作:`generate --qid Q737062 --target staging --langs zh --force`。
2. curl content:名作 background/analysis 明显变长(更具体),且仍各守 lane、不注水。
3. 重生成一件薄件确认未被硬撑注水。
