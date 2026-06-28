# 引人入胜的语音导览内容 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让富化讲解接地的同时引人入胜、可听、能记住一个重点——靠重写生成 prompt(导览导演口吻+各段角色+变长)与接地闸(逐句蕴含→三类判定),不改契约、不换模型(先 mini)。

**Architecture:** 核心改动在 **prompt 文本** + 一个 `SECTION_ROLES` 配置;消费代码(`ContentEnricher`/`QualityGate`)几乎不动。接地闸输出仍是逐句 keep/remove 布尔列表,判官内部应用三类规则——故 `quality.py` 仅调阈值/文档。

**Tech Stack:** Python + pytest;注入式 `complete`,全离线可测。spec `docs/superpowers/specs/2026-06-28-engaging-audio-guide-content-design.md`。

---

## File Structure

- **Modify** `backend/app/services/enrichment/category_config.py` — 加 `SECTION_ROLES`(各段 code → 角色描述 + 中文字数目标)+ `section_role(code)` 取值。
- **Modify** `backend/app/services/enrichment/prompts.py` — `build_generation_prompt` 重写(导览声音 + 各段角色/长度 + 三类许可);`build_entailment_prompt` 重写(三类判定);`_TRANSLATION_SYSTEM` 加保腔调。
- **Modify** `backend/app/services/enrichment/quality.py` — `check_section` 阈值/文档微调(语义=存活率)。

测试：
- **Modify** `backend/tests/unit/services/enrichment/test_quality.py`
- **Create** `backend/tests/unit/services/enrichment/test_prompts.py`
- **Modify** `backend/tests/unit/services/enrichment/test_content_enricher.py`

> 所有命令在 `backend/` 下跑。

---

### Task 1: SECTION_ROLES 配置

**Files:**
- Modify: `backend/app/services/enrichment/category_config.py`
- Test: `backend/tests/unit/services/enrichment/test_category_config.py`（若不存在则 Create）

参考既有：`category_config.py` 已有 `SECTIONS_BY_CATEGORY`(painting=[overview,artist,background,analysis,significance,facts] 等)、`SECTION_LABELS`、`section_label(code,lang)`。

- [ ] **Step 1: 写失败测试**

在 `test_category_config.py`（无则新建，含 `from app.services.enrichment.category_config import section_role`）追加：

```python
def test_section_role_has_role_and_length():
    r = section_role("overview")
    assert "role" in r and "max_chars" in r
    assert r["max_chars"] <= 120  # overview 是短钩子段
    assert section_role("background")["max_chars"] >= 200  # 长故事段


def test_section_role_unknown_falls_back():
    r = section_role("nonexistent")
    assert "role" in r and "max_chars" in r  # 有兜底，不抛
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && python -m pytest tests/unit/services/enrichment/test_category_config.py -q`
Expected: FAIL（`cannot import name 'section_role'`）

- [ ] **Step 3: 实现**

在 `category_config.py` 末尾加（角色描述喂 prompt，用英文便于模型；长度按 spec §4 各段型）：

```python
# 各段在语音导览里的角色 + 目标长度（中文字数；长度是目标非硬限，料薄可短）。spec §4。
SECTION_ROLES: dict[str, dict] = {
    "overview": {"role": "The HOOK: one vivid opening line that makes the visitor look up. Not a dry 'X is a painting by Y'.", "max_chars": 100},
    "artist": {"role": "A person with a story: one memorable thing about the maker tied to THIS work, not a CV.", "max_chars": 180},
    "background": {"role": "The story: commission, scandal, the moment it was made — narrative with momentum.", "max_chars": 280},
    "analysis": {"role": "Guided looking: 'notice the...', composition, technique, what to SEE. Sensory direction and gentle impressions belong here.", "max_chars": 280},
    "significance": {"role": "The one takeaway: why it matters / what to remember. The memory point.", "max_chars": 140},
    "facts": {"role": "One memorable anecdote or curiosity (hard facts live elsewhere).", "max_chars": 160},
    "photographer": {"role": "A person with a story: one memorable thing about the maker tied to THIS work.", "max_chars": 180},
    "maker": {"role": "A person with a story: one memorable thing about the maker tied to THIS work.", "max_chars": 180},
    "material-technique": {"role": "Guided looking at how it was made: material and craft a visitor can notice.", "max_chars": 200},
    "context": {"role": "The story and moment behind the work — narrative with momentum.", "max_chars": 280},
    "use": {"role": "What it was for and how it lived — concrete and human.", "max_chars": 200},
}

_DEFAULT_ROLE = {"role": "Engaging, grounded spoken narration for a museum visitor.", "max_chars": 180}


def section_role(code: str) -> dict:
    return SECTION_ROLES.get(code, _DEFAULT_ROLE)
```

- [ ] **Step 4: 运行确认通过**

Run: `cd backend && python -m pytest tests/unit/services/enrichment/test_category_config.py -q`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
cd backend && git add app/services/enrichment/category_config.py tests/unit/services/enrichment/test_category_config.py
git commit -m "feat(enrichment): SECTION_ROLES 各段导览角色+长度配置"
```

---

### Task 2: 生成 prompt 重写为"导览导演"

**Files:**
- Modify: `backend/app/services/enrichment/prompts.py`
- Test: `backend/tests/unit/services/enrichment/test_prompts.py`（新建）

参考既有：`build_generation_prompt(material, sections, category)` 现返回 `(_SYSTEM, user)`；签名不变（内部读 `section_role`）。

- [ ] **Step 1: 写失败测试**

Create `test_prompts.py`：

```python
from app.services.enrichment.prompts import build_generation_prompt


def test_generation_prompt_is_audio_guide_voice_with_roles():
    system, user = build_generation_prompt("MAT", ["overview", "background"], "painting")
    blob = (system + user).lower()
    # 导览声音
    assert "audio" in blob or "spoken" in blob
    assert "you" in blob  # 第二人称
    # 三类许可 + 接地铁律
    assert "framing" in blob or "guide" in blob or "second person" in blob
    assert "do not invent" in blob or "not in the material" in blob
    # 各段角色注入
    assert "hook" in blob  # overview 的角色词
    assert "story" in blob  # background 的角色词
    # 仍 JSON、键是 section code
    assert "json" in blob
    assert "overview" in user and "background" in user
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && python -m pytest tests/unit/services/enrichment/test_prompts.py -q`
Expected: FAIL（现 prompt 无 audio/hook/story 等）

- [ ] **Step 3: 实现**

在 `prompts.py`：把 `_SYSTEM` 与 `build_generation_prompt` 替换为：

```python
_SYSTEM = (
    "You are writing AUDIO-GUIDE narration for a museum visitor standing in front of the "
    "artwork — spoken, not an encyclopedia entry. Voice: vivid storytelling that makes dry "
    "facts come alive WITHOUT inventing anything (think a great popular-history narrator). "
    "Be colloquial and direct, speak to 'you', write people (artists, patrons) as real "
    "humans with motives, use a hook and gentle suspense, vary the rhythm. Each section has "
    "a ROLE and a target length given below; pick the single most engaging angle the "
    "material supports rather than summarizing everything; give one thing worth remembering.\n"
    "What you MAY write freely (these are NOT facts to be checked): framing and second-person "
    "guidance ('notice the red in the corner'), rhetorical questions, transitions, and GENTLE "
    "subjective impressions clearly phrased as impression ('the brushwork feels restless').\n"
    "What you MUST NOT do: invent any verifiable fact (names, dates, events, attributions, "
    "medium, what is depicted) that is not in the material. If the material is too thin for a "
    "section, return a SHORT honest text or an empty string — never pad with fabrication.\n"
    "Write in English. Return STRICT JSON mapping each requested section_code to its text "
    '(or "" if insufficient). No extra keys, no commentary.'
)


def build_generation_prompt(material: str, sections: list[str], category: str):
    from app.services.enrichment.category_config import section_role

    lines = []
    for code in sections:
        r = section_role(code)
        lines.append(f"- {code} — {r['role']} (aim ~{r['max_chars']} Chinese-char equivalent)")
    roles_block = "\n".join(lines)
    user = (
        f"Artwork category: {category}\n"
        f"Write these sections (return JSON keyed by these exact codes):\n{roles_block}\n\n"
        f"Material:\n{material}"
    )
    return _SYSTEM, user
```

- [ ] **Step 4: 运行确认通过**

Run: `cd backend && python -m pytest tests/unit/services/enrichment/test_prompts.py -q`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
cd backend && git add app/services/enrichment/prompts.py tests/unit/services/enrichment/test_prompts.py
git commit -m "feat(enrichment): 生成 prompt 重写为导览导演口吻(角色+变长+三类许可)"
```

---

### Task 3: 接地闸改三类判定

**Files:**
- Modify: `backend/app/services/enrichment/prompts.py`
- Test: `backend/tests/unit/services/enrichment/test_prompts.py`

参考既有：`build_entailment_prompt(material, sentences)` 返回 `(_ENTAILMENT_SYSTEM, user)`，输出契约是 `{"verdicts": [bool,...]}`（`quality.py` 依赖此，**不可改输出形状**）。

- [ ] **Step 1: 写失败测试**

在 `test_prompts.py` 追加：

```python
from app.services.enrichment.prompts import build_entailment_prompt


def test_grounding_prompt_is_three_class():
    system, user = build_entailment_prompt("MAT", ["s1", "s2"])
    blob = (system + user).lower()
    # 三类规则
    assert "factual claim" in blob or "factual" in blob
    assert "framing" in blob or "guidance" in blob or "second person" in blob
    assert "impression" in blob
    # 存疑偏保守
    assert "when in doubt" in blob or "if unsure" in blob
    # 输出契约不变：verdicts 布尔列表（true=keep）
    assert "verdicts" in blob and "true" in blob
    assert "1. s1" in user and "2. s2" in user
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && python -m pytest tests/unit/services/enrichment/test_prompts.py::test_grounding_prompt_is_three_class -q`
Expected: FAIL

- [ ] **Step 3: 实现**

把 `prompts.py` 的 `_ENTAILMENT_SYSTEM` 替换为（**输出仍是 verdicts 布尔列表，true=keep**）：

```python
_ENTAILMENT_SYSTEM = (
    "You are a grounding judge for audio-guide narration. Given source MATERIAL and a "
    "numbered list of SENTENCES, decide for EACH sentence whether to KEEP it (true) or "
    "REMOVE it (false), by its type:\n"
    "- FACTUAL CLAIM (a checkable fact about the work/artist/history: a name, date, medium, "
    "event, attribution, or what is depicted) → KEEP only if fully supported by the "
    "material; otherwise REMOVE. A claim true in the real world but absent from the material "
    "is still REMOVE.\n"
    "- FRAMING / GUIDANCE (second-person direction like 'notice the corner', rhetorical "
    "questions, transitions, sensory pointers) → KEEP. These make no factual claim.\n"
    "- IMPRESSION (a gentle subjective reading like 'the brushwork feels restless') → KEEP, "
    "UNLESS it asserts or implies a specific fact not in the material, or contradicts the "
    "material → then REMOVE.\n"
    "When in doubt whether something is a factual claim, treat it AS a factual claim and "
    "require support (bias toward grounding).\n"
    'Return STRICT JSON: {"verdicts": [true, false, ...]} with one boolean per sentence in '
    "the SAME order (true = keep). No commentary."
)
```

- [ ] **Step 4: 运行确认通过**

Run: `cd backend && python -m pytest tests/unit/services/enrichment/test_prompts.py -q`
Expected: PASS（含 Task 2 用例）

- [ ] **Step 5: 提交**

```bash
cd backend && git add app/services/enrichment/prompts.py tests/unit/services/enrichment/test_prompts.py
git commit -m "feat(enrichment): 接地闸改三类判定(事实硬接地/引导留/解读留)"
```

---

### Task 4: quality.py 阈值与语义对齐

**Files:**
- Modify: `backend/app/services/enrichment/quality.py`
- Test: `backend/tests/unit/services/enrichment/test_quality.py`

参考既有：`check_section` 切句→`build_entailment_prompt`→`parse(...).get("verdicts")`→keep where true→`grounding_ratio = kept/total`→`published if kept_body and ratio>=GROUNDING_THRESHOLD`。`GROUNDING_THRESHOLD=0.6`。**三类闸下 keep 含引导/解读句,存活率自然高;低存活率=大量无据事实被删=料薄/脑补。** 逻辑不变,仅下调阈值 + 更新文档。

- [ ] **Step 1: 写失败测试**

在 `test_quality.py` 追加（验证新语义：引导句被 keep、无据事实句被删、混合段按存活率发布）：

```python
def test_gate_keeps_guidance_and_drops_unsupported_claim():
    # 判官返回：句1(引导)keep, 句2(无据事实)remove, 句3(解读)keep
    import json as _json

    def fake(system, user):
        return _json.dumps({"verdicts": [True, False, True]})

    from app.services.enrichment.quality import QualityGate

    g = QualityGate(fake)
    body = "Notice the red in the corner. It was painted in 1505. The mood feels uneasy."
    r = g.check_section("MAT", "FACTS", body)
    assert "Notice the red" in r.body and "mood feels uneasy" in r.body
    assert "1505" not in r.body  # 无据事实被删
    assert r.status == "published"  # 存活 2/3 ≥ 阈值


def test_gate_needs_review_when_mostly_unsupported():
    import json as _json

    def fake(system, user):
        return _json.dumps({"verdicts": [False, False, True]})

    from app.services.enrichment.quality import QualityGate

    r = QualityGate(fake).check_section("MAT", "F", "A. B. C.")
    assert r.status == "needs_review"  # 存活 1/3 < 阈值
```

> 注：阈值取值需与断言一致。若现 0.6 让 2/3(0.67)published、1/3(0.33)needs_review，则保持 0.6 即可使两用例通过；本任务确认阈值并更新 docstring 反映"存活率"语义。先跑确认现阈值是否已让两用例过；不过再调。

- [ ] **Step 2: 运行确认（看是否已过 / 需调阈值）**

Run: `cd backend && python -m pytest tests/unit/services/enrichment/test_quality.py -q`
Expected: 若两新用例 PASS 则阈值无需改；若 needs_review 用例失败则按下步调阈值。

- [ ] **Step 3: 更新阈值语义 + 文档**

在 `quality.py`：把 `GROUNDING_THRESHOLD` 的行内注释/`check_section` docstring 更新为反映"存活率(survival rate)"语义——keep 含引导/解读句,低存活率=大量无据事实被删→needs_review。保持 `GROUNDING_THRESHOLD = 0.6`（0.67 publish / 0.33 needs_review 符合 Step 1 断言）。**若现有其它 test_quality 用例因新语义失效，同步修正其期望。**

- [ ] **Step 4: 运行确认通过**

Run: `cd backend && python -m pytest tests/unit/services/enrichment/test_quality.py -q`
Expected: PASS（含既有用例）

- [ ] **Step 5: 提交**

```bash
cd backend && git add app/services/enrichment/quality.py tests/unit/services/enrichment/test_quality.py
git commit -m "test(enrichment): 接地闸存活率语义对齐(引导/解读留、无据事实删)"
```

---

### Task 5: 翻译保腔调

**Files:**
- Modify: `backend/app/services/enrichment/prompts.py`
- Test: `backend/tests/unit/services/enrichment/test_prompts.py`

参考既有：`_TRANSLATION_SYSTEM`（faithful + 不直译标题）。加一条保腔调规则。

- [ ] **Step 1: 写失败测试**

在 `test_prompts.py` 追加：

```python
from app.services.enrichment.prompts import build_translation_prompt


def test_translation_prompt_preserves_tone():
    system, _ = build_translation_prompt("Hello.", "zh")
    blob = system.lower()
    assert "tone" in blob or "voice" in blob or "engaging" in blob  # 保腔调
    assert "faithful" in blob  # 仍忠实
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && python -m pytest tests/unit/services/enrichment/test_prompts.py::test_translation_prompt_preserves_tone -q`
Expected: FAIL

- [ ] **Step 3: 实现**

在 `_TRANSLATION_SYSTEM` 的 Rules 里加一条（在 (3) 之后）：

```python
_TRANSLATION_SYSTEM = (
    "You are a professional art translator. Translate the given English artwork explanation "
    "into {lang}. Rules: (1) Be FAITHFUL — do NOT add, remove, or alter any fact. "
    "(2) Keep proper names, artist names, and work TITLES in their original form or the "
    "established exonym in the target language; do NOT literally translate titles. "
    "(3) Natural, fluent {lang}. (4) PRESERVE THE TONE — keep the engaging, spoken, "
    "second-person audio-guide voice, hooks and gentle wit; convey them idiomatically in "
    "{lang} rather than translating jokes literally. "
    "Return ONLY the translated text, no commentary, no quotes."
)
```

- [ ] **Step 4: 运行确认通过**

Run: `cd backend && python -m pytest tests/unit/services/enrichment/test_prompts.py -q`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
cd backend && git add app/services/enrichment/prompts.py tests/unit/services/enrichment/test_prompts.py
git commit -m "feat(enrichment): 翻译 prompt 加保腔调(导览口吻不直译段子)"
```

---

### Task 6: 端到端集成回归

**Files:**
- Modify: `backend/tests/unit/services/enrichment/test_content_enricher.py`

确认生成器吃新 prompt 仍产 section JSON（注入式 complete，离线）。

- [ ] **Step 1: 加集成测试**

在 `test_content_enricher.py` 追加：

```python
def test_generate_canonical_uses_role_prompt_and_parses():
    from app.services.enrichment.content_enricher import ContentEnricher

    captured = {}

    def fake_complete(system, user):
        captured["user"] = user
        import json as _json
        return _json.dumps({"overview": "A grounded hook.", "background": "The story."})

    enr = ContentEnricher(complete=fake_complete)
    out = enr.generate_canonical(
        {"qid": "Q1", "title_en": "X", "category": "painting", "attributes": {"extract_en": "Foo."}},
        sections=["overview", "background"],
    )
    assert out["overview"] == "A grounded hook." and out["background"] == "The story."
    # 角色注入到了 prompt
    assert "hook" in captured["user"].lower() and "story" in captured["user"].lower()
```

- [ ] **Step 2: 运行确认通过**

Run: `cd backend && python -m pytest tests/unit/services/enrichment/test_content_enricher.py -q`
Expected: PASS

- [ ] **Step 3: 全量 enrichment 回归 + 提交**

Run: `cd backend && python -m pytest tests/unit/services/enrichment/ tests/integration/test_generate_pipeline.py -q`
Expected: PASS（无回归）

```bash
cd backend && git add tests/unit/services/enrichment/test_content_enricher.py
git commit -m "test(enrichment): generate_canonical 角色 prompt 集成回归"
```

---

## Self-Review

- **Spec 覆盖**:§3 声音(Task 2)✓ §4 各段角色/长度(Task 1+2)✓ §2/§5B 三类闸(Task 3)✓ §5D 翻译保腔调(Task 5)✓ §5C 先 mini(无改动,`model` 参数已贯通)✓ §7 无契约/迁移 ✓。
- **输出契约不变**:闸仍 `{"verdicts":[bool]}`,`quality.py` 消费不变(Task 3 测试锁这点);生成仍 section→text JSON(Task 6 锁)。
- **接地铁律保留**:三类闸"存疑偏保守"+ 生成 prompt"禁编造可证伪事实"(Task 2/3)。
- **类型一致**:`section_role(code)->{role,max_chars}`(Task 1 定义,Task 2 消费)。
- **YAGNI**:不加评审重写环、不动 section 结构、不换模型——均 spec §6 非目标。

## 上线验证(合 staging 后人工)

1. staging 重生成几件(`generate --qid <q> --target staging --langs en,fr,zh --force`,先重置 stub 或直接 force)。
2. 肉眼三标准:愿意听/看懂/记住一个重点 + 长度到位 + **无据事实没溜进来**(抽查事实句对材料)。
3. 满意 → prod 重生成 14 件 → 你验收 → 再定上 gpt-4o / 扩 TOP-N。
