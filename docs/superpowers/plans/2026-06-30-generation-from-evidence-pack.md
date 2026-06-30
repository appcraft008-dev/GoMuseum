# 从证据包生成 + 去重（阶段2a）Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 生成改从 `evidence_pack` 取料(用上富属性→更丰富);默认讲解先生成(头条),模块单调用带 guide 互知 + 锐化 lane + "深化非复述/只会重复就返空"(去重);overview 退役。

**Architecture:** 复用现有单调用 `generate_canonical` + 三类闸 + 翻译。`build_material` 改为 pack 感知(无 pack 回退);`build_generation_prompt` +guide+锐化lane;`generate_object` 调序(guide 先)。spec `2026-06-30-generation-from-evidence-pack-design.md`。**不含** hedge(2b)、质量评估(2c)、配源(round2)。

**Tech Stack:** Python + pytest;注入式组件,离线可测。

> 命令在 `backend/` 下跑。

---

### Task 1: SECTION_ROLES 锐化 + overview 退役

**Files:**
- Modify: `backend/app/services/enrichment/category_config.py`
- Test: `backend/tests/unit/services/enrichment/test_category_config.py`、`backend/tests/unit/services/test_seed_sections.py`

参考:`SECTION_ROLES`(各 code → {role, max_chars});`SECTIONS_BY_CATEGORY`(painting=[overview,artist,background,analysis,significance,facts] 等)。

- [ ] **Step 1: 写失败测试** — 在 `test_category_config.py` 追加:

```python
def test_overview_retired_from_categories():
    from app.services.enrichment.category_config import SECTIONS_BY_CATEGORY

    for codes in SECTIONS_BY_CATEGORY.values():
        assert "overview" not in codes


def test_section_roles_are_distinct_lanes():
    from app.services.enrichment.category_config import section_role

    assert "person" in section_role("artist")["role"].lower() or "maker" in section_role("artist")["role"].lower()
    assert "influence" in section_role("significance")["role"].lower() or "legacy" in section_role("significance")["role"].lower()
    assert "event" in section_role("background")["role"].lower() or "history" in section_role("background")["role"].lower()
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && python -m pytest tests/unit/services/enrichment/test_category_config.py -q`
Expected: FAIL（overview 仍在 / role 措辞不符）

- [ ] **Step 3: 实现** —
(a) `SECTIONS_BY_CATEGORY` 每个类目列表移除 `"overview"`(painting/sculpture/photograph/decorative 及 `_FALLBACK_SECTIONS` 若含)。
(b) 锐化 `SECTION_ROLES` 中这几个 lane 的 role(英文,互斥):
```python
    "artist": {"role": "The MAKER as a person: life, character, what drove them, their place in art history. NOT this work's scandal/technique (other lanes cover those).", "max_chars": 180},
    "background": {"role": "The work's HISTORY as concrete events: when, who commissioned it, where shown, the reception as events, provenance. NOT why-it-matters (that's significance), NOT how-to-look (that's analysis).", "max_chars": 280},
    "analysis": {"role": "Guided LOOKING: composition, technique, brushwork, what to notice with your eyes. NOT history or influence.", "max_chars": 280},
    "significance": {"role": "LEGACY & influence: what it changed, who it influenced, why it matters to art history. Do NOT re-tell the scandal events (that's background).", "max_chars": 160},
    "facts": {"role": "ONE surprising anecdote/curiosity not covered by other lanes.", "max_chars": 160},
```
（其余 code 不动；`overview` 的 SECTION_ROLES 条目可保留无害,反正不再生成。）

- [ ] **Step 4: seed 测试同步** — `test_seed_sections.py` 的 `test_seed_creates_multi_category_skeleton` 若断言 painting==6 段,改为 5(去 overview);`category_sections` painting 段数同改。运行 `cd backend && python -m pytest tests/unit/services/test_seed_sections.py tests/unit/services/enrichment/test_category_config.py -q` → PASS。

- [ ] **Step 5: 提交**

```bash
cd backend && git add app/services/enrichment/category_config.py tests/unit/services/enrichment/test_category_config.py tests/unit/services/test_seed_sections.py
git commit -m "feat(gen): SECTION_ROLES 锐化互斥 lane + overview 退役"
```

---

### Task 2: build_material 改 pack 感知 + _row_to_obj 带 evidence_pack

**Files:**
- Modify: `backend/app/services/enrichment/content_enricher.py`
- Modify: `backend/app/services/enrichment/pipeline.py`(`_row_to_obj`)
- Test: `backend/tests/unit/services/enrichment/test_content_enricher.py`

参考:`build_material(obj)` 现渲染 `[FACTS]`(_FACT_FIELDS + _ATTR_FACT_KEYS)+ `[WIKIPEDIA EXTRACTS]` + `[ABOUT THE ARTIST]`。`pipeline._row_to_obj(o)` 返回 dict(不含 evidence_pack)。

- [ ] **Step 1: 写失败测试** — `test_content_enricher.py` 追加:

```python
def test_build_material_renders_evidence_pack_rich_facts():
    from app.services.enrichment.content_enricher import build_material

    obj = {
        "qid": "Q1", "title_en": "X", "category": "painting",
        "attributes": {"extract_en": "narrative"},
        "evidence_pack": {
            "facts": [
                {"claim": "委托人", "value": "Khalil Bey", "source": "wikidata:P88", "topic": "background"},
                {"claim": "描绘内容", "value": "female nude", "source": "wikidata:P180", "topic": "analysis"},
                {"claim": "材质", "value": "oil paint", "source": "joconde:medium_fr", "topic": "analysis"},
            ],
            "narrative": [], "flagged": [],
        },
    }
    mat = build_material(obj)
    assert "Khalil Bey" in mat and "female nude" in mat
    assert "background" in mat.lower()  # 富属性带 topic 分组提示


def test_build_material_without_pack_unchanged():
    from app.services.enrichment.content_enricher import build_material
    mat = build_material({"qid": "Q1", "category": "painting", "attributes": {"extract_en": "x"}})
    assert isinstance(mat, str)  # 无 pack 回退,不抛
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && python -m pytest tests/unit/services/enrichment/test_content_enricher.py::test_build_material_renders_evidence_pack_rich_facts -q`
Expected: FAIL

- [ ] **Step 3: 实现** —
(a) `content_enricher.build_material`:在 `[ABOUT THE ARTIST]` 块之后(return 之前)加渲染 pack 的富属性(只 wikidata 来源,避免与 attributes 重复;按 topic 分组):
```python
    pack = obj.get("evidence_pack") or {}
    rich = [f for f in pack.get("facts", []) if f.get("source", "").startswith("wikidata:")]
    if rich:
        lines.append("\n[STRUCTURED FACTS]")
        for f in rich:
            topic = f.get("topic", "")
            lines.append(f"- ({topic}) {f.get('claim')}: {f.get('value')}")
```
(b) `pipeline._row_to_obj(o)`:返回 dict 加 `"evidence_pack": o.evidence_pack`。

- [ ] **Step 4: 通过 + 提交**

Run: `cd backend && python -m pytest tests/unit/services/enrichment/test_content_enricher.py -q`（PASS）
```bash
cd backend && git add app/services/enrichment/content_enricher.py app/services/enrichment/pipeline.py tests/unit/services/enrichment/test_content_enricher.py
git commit -m "feat(gen): build_material 渲染证据包富属性(pack感知)+ _row_to_obj 带 evidence_pack"
```

---

### Task 3: build_generation_prompt + guide 互知 + 去重指令

**Files:**
- Modify: `backend/app/services/enrichment/prompts.py`
- Test: `backend/tests/unit/services/enrichment/test_prompts.py`

参考:`build_generation_prompt(material, sections, category)` 现返回 `(_SYSTEM, user)`,user 含各段 role 行。

- [ ] **Step 1: 写失败测试** — `test_prompts.py` 追加:

```python
def test_generation_prompt_dedup_with_guide():
    from app.services.enrichment.prompts import build_generation_prompt

    system, user = build_generation_prompt(
        "MAT", ["artist", "background"], "painting", guide="这是已播的头条讲解。"
    )
    blob = (system + user).lower()
    assert "这是已播的头条讲解" in user  # 头条传入
    assert "do not repeat" in blob or "don't repeat" in blob or "不重复" in blob or "already" in blob
    assert "empty" in blob  # 只会重复就返空
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && python -m pytest tests/unit/services/enrichment/test_prompts.py::test_generation_prompt_dedup_with_guide -q`
Expected: FAIL（不接受 guide 参数）

- [ ] **Step 3: 实现** — 改 `build_generation_prompt` 签名为 `(material, sections, category, guide=None)`;在 `_SYSTEM` 追加去重原则(或在 user 拼入):
```python
def build_generation_prompt(material, sections, category, guide=None):
    from app.services.enrichment.category_config import section_role

    lines = []
    for code in sections:
        r = section_role(code)
        lines.append(f"- {code} — {r['role']} (aim ~{r['max_chars']} Chinese-char equivalent)")
    roles_block = "\n".join(lines)
    guide_block = (
        f"\nThe visitor ALREADY heard this HEADLINE guide:\n\"\"\"\n{guide}\n\"\"\"\n"
        "Each section must go DEEPER on ITS OWN lane and add NEW material the headline did "
        "NOT cover. Do NOT repeat the headline or other sections. If a section would only "
        "repeat what's already said, return an empty string for it.\n"
        if guide else ""
    )
    user = (
        f"Artwork category: {category}\n"
        f"Write these sections (return JSON keyed by these exact codes), each staying strictly "
        f"in its lane:\n{roles_block}\n{guide_block}\n"
        f"Material (facts tagged with their lane topic):\n{material}"
    )
    return _SYSTEM, user
```

- [ ] **Step 4: 通过 + 提交**

Run: `cd backend && python -m pytest tests/unit/services/enrichment/test_prompts.py -q`（PASS,含既有）
```bash
cd backend && git add app/services/enrichment/prompts.py tests/unit/services/enrichment/test_prompts.py
git commit -m "feat(gen): build_generation_prompt 加 guide 互知 + 去重/返空指令"
```

---

### Task 4: generate_canonical 透传 guide

**Files:**
- Modify: `backend/app/services/enrichment/content_enricher.py`
- Test: `backend/tests/unit/services/enrichment/test_content_enricher.py`

- [ ] **Step 1: 写失败测试** — 追加:

```python
def test_generate_canonical_passes_guide_to_prompt():
    from app.services.enrichment.content_enricher import ContentEnricher

    captured = {}

    def fake(system, user):
        captured["user"] = user
        import json as _json
        return _json.dumps({"artist": "A."})

    enr = ContentEnricher(complete=fake)
    enr.generate_canonical(
        {"qid": "Q1", "category": "painting", "attributes": {}},
        sections=["artist"], guide="头条 XYZ。",
    )
    assert "头条 XYZ" in captured["user"]
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && python -m pytest tests/unit/services/enrichment/test_content_enricher.py::test_generate_canonical_passes_guide_to_prompt -q`
Expected: FAIL（generate_canonical 不接受 guide）

- [ ] **Step 3: 实现** — `generate_canonical` 签名加 `guide=None`,传给 `build_generation_prompt`:
```python
    def generate_canonical(self, obj: dict, sections: list[str], guide: str | None = None) -> dict:
        material = build_material(obj)
        system, user = build_generation_prompt(
            material, sections, obj.get("category", "unknown"), guide=guide
        )
        ...（其余不变）
```

- [ ] **Step 4: 通过 + 提交**

Run: `cd backend && python -m pytest tests/unit/services/enrichment/test_content_enricher.py -q`（PASS）
```bash
cd backend && git add app/services/enrichment/content_enricher.py tests/unit/services/enrichment/test_content_enricher.py
git commit -m "feat(gen): generate_canonical 透传 guide"
```

---

### Task 5: pipeline 调序——guide 先,模块带 guide

**Files:**
- Modify: `backend/app/services/enrichment/pipeline.py`
- Test: `backend/tests/integration/test_generate_pipeline.py`

参考:`generate_object` 现顺序:evidence_pack → `draft = enricher.generate_canonical(obj, sections)` → gate → 落英语 → guide(`enricher.generate_default_guide(...)`)→ 并入 en_published → 翻译。**需把 guide 生成提到 generate_canonical 之前,并把 guide_text 传给 generate_canonical。**

- [ ] **Step 1: 写失败测试** — 复用 `_GuideEnricher`(有 generate_default_guide)。断言 generate_canonical 收到 guide:

```python
def test_generate_object_passes_guide_into_canonical(session):
    from app.services.enrichment.pipeline import generate_object
    from app.services.enrichment.quality import SectionQuality

    seen = {}

    class _Enr(_FakeEnricher):
        def generate_default_guide(self, obj, facts, target_chars):
            return "HEADLINE."

        def generate_canonical(self, obj, sections, guide=None):
            seen["guide"] = guide
            return {"artist": "A."}

    class _G(_FakeGate):
        def check_section(self, m, f, b):
            return SectionQuality(body=b, status="published", grounding_ratio=1.0, conflicts=[], score=1.0)

    generate_object(session, "Q1", enricher=_Enr(), gate=_G(),
                    translator=_FakeTranslator(), target_langs=["en"], model="m")
    assert seen["guide"] == "HEADLINE."  # 模块拿到了头条
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && python -m pytest tests/integration/test_generate_pipeline.py::test_generate_object_passes_guide_into_canonical -q`
Expected: FAIL（当前 guide 在 canonical 之后、且未传入）

- [ ] **Step 3: 实现** — 在 `generate_object` 里**重排**:把默认讲解生成(`guide_text = enricher.generate_default_guide(obj, facts, guide_target_chars(o.popularity)) if hasattr(...) else None`)移到 `draft = enricher.generate_canonical(...)` **之前**;`generate_canonical` 调用改为 `enricher.generate_canonical(obj, sections, guide=guide_text)`;guide 段的落库/并入 en_published 逻辑保持(在 canonical 之后落 guide 段那段仍可,但 guide_text 已先算)。确保 guide 段仍 `persist_gated_sections` + 并入 `en_published` 翻译(逻辑不丢)。

> 注:仔细保持既有 guide 段落库 + content_status 流转 + 翻译并入不变,只是**计算 guide_text 的时机提前**并**传入 canonical**。

- [ ] **Step 4: 通过(含原有用例) + 提交**

Run: `cd backend && python -m pytest tests/integration/test_generate_pipeline.py -q`（全 PASS）
```bash
cd backend && git add app/services/enrichment/pipeline.py tests/integration/test_generate_pipeline.py
git commit -m "feat(gen): generate_object 先生成头条→模块带 guide 互知去重"
```

---

### Task 6: overview 退役迁移

**Files:**
- Create: `backend/alembic/versions/i1f5_retire_overview_tab.py`
- Test: `backend/tests/integration/test_pack_and_content_facts.py`

alembic head = `h1e4_add_evidence_pack`。

- [ ] **Step 1: 写失败测试** — `test_pack_and_content_facts.py` 追加(fixture 已建 painting 对象;手插一个 overview category_section 模拟旧数据,验证 tabs 不含 overview——但更直接:断言迁移后 category_sections 无 overview。改为验 get_object_content tabs 不含 overview):

```python
def test_tabs_exclude_overview(session):
    # 即便 DB 残留 overview 段,tabs 也不应含 overview(category_sections 已无 overview 映射)
    from app.services.museum_repo import get_object_content
    d = get_object_content(session, "orsay", "Q1", "zh")
    assert all(t["section_code"] != "overview" for t in d["tabs"])
```

> 注:tabs 来自 category_sections 映射。测试 fixture 不 seed overview 映射即天然不含——本用例守护"不回归"。迁移负责清 prod/staging 既有 overview 映射行。

- [ ] **Step 2: 运行确认**

Run: `cd backend && python -m pytest tests/integration/test_pack_and_content_facts.py::test_tabs_exclude_overview -q`（fixture 未 seed overview → 多半已 PASS;作为回归守护)

- [ ] **Step 3: 写迁移** — `backend/alembic/versions/i1f5_retire_overview_tab.py`(幂等删 overview 映射行):

```python
"""retire overview tab: 删 category_sections 里 section_code='overview' 的映射行

默认讲解(default_guide)已取代 overview 作开场;overview 与头条重复,退役为非 tab。
section_types 的 overview 行保留(无害)。幂等。
"""
import sqlalchemy as sa

from alembic import op

revision = "i1f5_retire_overview_tab"
down_revision = "h1e4_add_evidence_pack"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.get_bind().execute(
        sa.text("DELETE FROM category_sections WHERE section_code = 'overview'")
    )


def downgrade() -> None:
    pass  # 不恢复(overview 退役为产品决定;需要时重 seed)
```

- [ ] **Step 4: 单 head 校验 + 通过** —
Run: `cd backend && python -c "from alembic.config import Config; from alembic.script import ScriptDirectory; print(ScriptDirectory.from_config(Config('alembic.ini')).get_heads())"`（应 `['i1f5_retire_overview_tab']`）
Run: `cd backend && python -m pytest tests/integration/test_pack_and_content_facts.py -q`（PASS）

- [ ] **Step 5: 提交**

```bash
cd backend && git add alembic/versions/i1f5_retire_overview_tab.py tests/integration/test_pack_and_content_facts.py
git commit -m "feat(gen): overview 退役迁移(删 category_sections 映射行)"
```

---

### Task 7: 全量回归 + 契约文档回写

**Files:**
- Modify: `docs/architecture/museum-api-contract.md`

- [ ] **Step 1: 全量回归**

Run: `cd backend && python -m pytest tests/unit/services/enrichment/ tests/integration/test_generate_pipeline.py tests/integration/test_pack_and_content_facts.py tests/unit/services/test_seed_sections.py -q`
Expected: PASS（无回归）

- [ ] **Step 2: 回写主文档** — `museum-api-contract.md`:① §内容体系标注"已落地(阶段2a):生成从证据包出 + guide 互知去重 + overview 退役";② 端点4 `tabs` 说明加"overview 已退役(默认讲解取代);各模块各守互斥 lane、不复述头条";③ 变更记录加一行。

- [ ] **Step 3: 提交**

```bash
cd /Users/hongyang/Projects/GoMuseum && git add docs/architecture/museum-api-contract.md
git commit -m "docs(api): 回写阶段2a(从证据包生成+去重+overview退役)"
```

---

## Self-Review

- **Spec 覆盖**:SECTION_ROLES 锐化+overview 退役(T1)✓ build_material pack 感知(T2)✓ guide 互知去重 prompt(T3)✓ generate_canonical 透传 guide(T4)✓ pipeline 调序 guide 先(T5)✓ overview 迁移(T6)✓ 回写(T7)✓。
- **机制一致**:guide 先 → 模块单调用带 guide+锐化lane+返空(spec §2)。
- **丰富**:build_material 渲染证据包富属性(P88/P180…)(T2)。
- **向后兼容**:无 pack 回退 build_material 旧渲染;tabs/facts 契约形状不变;overview 退役是数据层(迁移)。
- **类型一致**:`build_generation_prompt(material,sections,category,guide=None)`(T3 定义,T4 调);`generate_canonical(obj,sections,guide=None)`(T4 定义,T5 调)。

## 上线验证(合 staging 后)

1. staging 重生成几件:`generate --qid <q> --target staging --langs zh --force`(force 重建证据包+重生成)。
2. curl content:① 各模块**不再复述头条**、各守 lane(artist 只讲人、background 只讲事件链、significance 只讲影响)② 用上富属性(委托人/描绘)③ overview 不在 tabs ④ 只会重复的模块返空(前端隐)。
3. staging APK 看"更多内容"是否一层比一层深、不重复。满意 → 评估是否进 2b(hedge)/配源 round2,再统一上 prod 生成一次。
