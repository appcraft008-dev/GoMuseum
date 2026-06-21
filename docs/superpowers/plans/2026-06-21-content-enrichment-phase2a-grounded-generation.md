# 内容富化 Phase 2a — 核心 grounded 英语生成 + 落库 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans. Steps use checkbox (`- [ ]`).
> ⚠️ 改函数签名时 grep 范围含 `backend/tests/`（1b 教训）。LLM 调用一律可注入，单测离线。

**Goal:** 把"事实 + Wikipedia 素材"接地生成为**英语轴心分段 body** 并落库 `object_content_sections`——产品"藏品真正有讲解"的第一步。仅英语轴心 + 落库；翻译(2c)、质量门(2b)、Q&A/CLI(2d)后续。

**Architecture:** 新增 `enrichment/content_enricher.py`（`ContentEnricher`：组装材料 → 一次 LLM 调用产出分段 → 解析）；LLM 调用经**注入的 `complete` 可调用**（默认 OpenAI，测试用 mock）。落库扩 `content_repo.py`（`persist_generated_sections`）。读对象的 `attributes`(含 Joconde 法语事实)+ `sources`(含 Wikipedia extract，1b/1c 产出)作材料。

**Tech Stack:** Python 3.11 / pytest / 既有 openai AsyncOpenAI 模式（见 content_generation_service `_get_openai_client`）。

**分支：** 从最新 `staging` 切 `feature/content-enrichment-phase2a`。**测试：** `cd backend && poetry run pytest`（用 storage/DB 的加 `STORAGE_BACKEND=local`）。

**对应 spec：** §3 第一原则、§7 生成服务（步骤 1-3 英语轴心；4 翻译/5 Q&A 后续期）。

---

## File Structure

| 文件 | 责任 | 改动 |
|---|---|---|
| `enrichment/content_enricher.py` | 组装材料 + 接地生成英语分段（LLM 注入） | 新建 |
| `enrichment/prompts.py` | grounded system prompt（类别感知、只依据材料、缺料留空） | 新建 |
| `content_repo.py` | `persist_generated_sections`（按 obj/lang/section upsert body+status+model） | 改 |

---

## Task 1: 材料组装 `_build_material`

**Files:** Create `backend/app/services/enrichment/content_enricher.py`；Test `backend/tests/unit/services/enrichment/test_content_enricher.py`

- [ ] **Step 1: 失败测试**
```python
from app.services.enrichment.content_enricher import build_material


def test_build_material_includes_facts_and_wikipedia():
    obj = {
        "qid": "Q1", "title_en": "Bedroom in Arles", "artist_en": "Vincent van Gogh",
        "year": "1889", "category": "painting",
        "attributes": {
            "medium_fr": "huile sur toile", "dimensions": "73 × 92 cm",
            "extract_en": "Van Gogh painted his bedroom in Arles in 1888.",
        },
    }
    mat = build_material(obj)
    assert "Bedroom in Arles" in mat
    assert "Vincent van Gogh" in mat
    assert "huile sur toile" in mat
    assert "Van Gogh painted his bedroom" in mat  # Wikipedia extract 进材料


def test_build_material_empty_when_no_facts():
    mat = build_material({"qid": "Q1", "category": "painting", "attributes": {}})
    # 标题/作者/extract 全无 → 材料很薄（仅含 qid 标识），不抛
    assert isinstance(mat, str)
```

- [ ] **Step 2: 跑确认失败** — `cd backend && poetry run pytest tests/unit/services/enrichment/test_content_enricher.py -k build_material -v`。

- [ ] **Step 3: 实现 `content_enricher.py`（先只 build_material）**
```python
"""ContentEnricher：把事实 + Wikipedia 素材接地生成英语轴心分段讲解。
LLM 调用经注入的 complete 可调用，单测离线。"""

from __future__ import annotations

# 结构化事实里要喂给模型的 canonical 字段（标签 → 取值键）
_FACT_FIELDS = [
    ("Title", "title_en"),
    ("Artist", "artist_en"),
    ("Year", "year"),
    ("Category", "category"),
]
# attributes 里要喂的事实键（法语/英语描述型 + 数值型）
_ATTR_FACT_KEYS = [
    "medium_fr", "dimensions", "inventory_number", "provenance_fr",
    "exhibitions_fr", "bibliography_fr", "title_fr", "artist_fr",
]


def build_material(obj: dict) -> str:
    """组装"材料包"文本（结构化事实 + Wikipedia 正文），每条标来源，供 grounded 生成。"""
    lines = ["[FACTS]"]
    for label, key in _FACT_FIELDS:
        v = obj.get(key)
        if v:
            lines.append(f"- {label}: {v}")
    attrs = obj.get("attributes") or {}
    for key in _ATTR_FACT_KEYS:
        v = attrs.get(key)
        if v:
            lines.append(f"- {key}: {v}")
    # Wikipedia 正文摘录（各语言 extract_*）
    extracts = {k: v for k, v in attrs.items() if k.startswith("extract_") and v}
    if extracts:
        lines.append("\n[WIKIPEDIA EXTRACTS]")
        for k, v in extracts.items():
            lines.append(f"({k}) {v}")
    return "\n".join(lines)
```

- [ ] **Step 4: 跑确认通过 + 提交** — 预期 2 passed。
```bash
cd backend && poetry run black app/services/enrichment/content_enricher.py tests/unit/services/enrichment/test_content_enricher.py && poetry run isort app/services/enrichment/content_enricher.py tests/unit/services/enrichment/test_content_enricher.py
cd /Users/hongyang/Projects/GoMuseum && git add backend/app/services/enrichment/content_enricher.py backend/tests/unit/services/enrichment/test_content_enricher.py
git commit -m "feat(enrichment): ContentEnricher.build_material 组装接地材料(事实+Wikipedia)"
```

---

## Task 2: grounded system prompt

**Files:** Create `backend/app/services/enrichment/prompts.py`；Test `backend/tests/unit/services/enrichment/test_prompts.py`

- [ ] **Step 1: 失败测试**
```python
from app.services.enrichment.prompts import build_generation_prompt


def test_prompt_lists_requested_sections_and_grounding_rules():
    system, user = build_generation_prompt(
        material="[FACTS]\n- Title: X",
        sections=["overview", "artist"],
        category="painting",
    )
    assert "only" in system.lower() or "only the" in system.lower() or "仅" in system
    assert "overview" in user and "artist" in user
    assert "painting" in user
    assert "[FACTS]" in user  # 材料进 user 消息
```

- [ ] **Step 2: 跑确认失败**。

- [ ] **Step 3: 实现 `prompts.py`**
```python
"""grounded 生成 prompt：只依据材料、类别感知、原创表达、缺料留空。"""

from __future__ import annotations

_SYSTEM = (
    "You are a museum content writer. Write section-by-section explanations of an artwork "
    "USING ONLY the provided material (facts + encyclopedia extracts). "
    "Rules: (1) Use only information present in the material; do NOT add facts from your own "
    "knowledge. (2) Write in your own original wording; do NOT copy source sentences. "
    "(3) If the material lacks enough for a section, return an empty string for that section "
    "(better empty than fabricated). (4) Be accurate, concise, engaging. "
    'Return STRICT JSON: an object mapping each requested section_code to its English text '
    '(or "" if insufficient). No extra keys, no commentary.'
)


def build_generation_prompt(material: str, sections: list[str], category: str):
    user = (
        f"Artwork category: {category}\n"
        f"Write these sections (return JSON keyed by these exact codes): {sections}\n\n"
        f"Material:\n{material}"
    )
    return _SYSTEM, user
```

- [ ] **Step 4: 跑确认通过 + 提交** — 预期 passed。
```bash
cd backend && poetry run black app/services/enrichment/prompts.py tests/unit/services/enrichment/test_prompts.py && poetry run isort app/services/enrichment/prompts.py tests/unit/services/enrichment/test_prompts.py
cd /Users/hongyang/Projects/GoMuseum && git add backend/app/services/enrichment/prompts.py backend/tests/unit/services/enrichment/test_prompts.py
git commit -m "feat(enrichment): grounded 生成 prompt(只依据材料/原创/缺料留空)"
```

---

## Task 3: `ContentEnricher.generate_canonical`（LLM 注入 + 解析）

**Files:** Modify `backend/app/services/enrichment/content_enricher.py`；Test `test_content_enricher.py`（追加）

- [ ] **Step 1: 失败测试（追加）**
```python
import json
from app.services.enrichment.content_enricher import ContentEnricher


def test_generate_canonical_parses_sections_and_drops_empty():
    obj = {"qid": "Q1", "title_en": "X", "category": "painting", "attributes": {"extract_en": "Foo."}}

    def fake_complete(system, user):
        # 模型返回严格 JSON：overview 有内容，artist 空（材料不足）
        return json.dumps({"overview": "An original overview.", "artist": ""})

    enr = ContentEnricher(complete=fake_complete)
    out = enr.generate_canonical(obj, sections=["overview", "artist"])
    assert out["overview"] == "An original overview."
    assert out["artist"] is None     # 空串 → None（不发布）


def test_generate_canonical_tolerates_unkeyed_or_extra(monkeypatch):
    obj = {"qid": "Q1", "category": "painting", "attributes": {}}

    def fake_complete(system, user):
        return '```json\n{"overview": "Hi", "extra": "ignored"}\n```'  # 带代码围栏 + 多键

    enr = ContentEnricher(complete=fake_complete)
    out = enr.generate_canonical(obj, sections=["overview", "artist"])
    assert out["overview"] == "Hi"
    assert out["artist"] is None     # 未返回的段 → None
```

- [ ] **Step 2: 跑确认失败**。

- [ ] **Step 3: 在 content_enricher.py 加 `ContentEnricher`**
```python
import json
import re

from app.services.enrichment.prompts import build_generation_prompt


def _parse_json(text: str) -> dict:
    """容错解析模型返回的 JSON（去代码围栏 / 取首个 {...}）。"""
    t = text.strip()
    t = re.sub(r"^```(?:json)?|```$", "", t, flags=re.MULTILINE).strip()
    try:
        return json.loads(t)
    except Exception:
        m = re.search(r"\{.*\}", t, re.DOTALL)
        return json.loads(m.group(0)) if m else {}


class ContentEnricher:
    def __init__(self, complete):
        # complete(system: str, user: str) -> str（注入；默认见 default_complete）
        self._complete = complete

    def generate_canonical(self, obj: dict, sections: list[str]) -> dict:
        """英语轴心：一次 LLM 调用产出请求段落。空串/未返回 → None（不发布）。"""
        material = build_material(obj)
        system, user = build_generation_prompt(material, sections, obj.get("category", "unknown"))
        raw = self._complete(system, user)
        parsed = _parse_json(raw)
        out = {}
        for code in sections:
            v = parsed.get(code)
            out[code] = v.strip() if isinstance(v, str) and v.strip() else None
        return out
```

- [ ] **Step 4: 跑确认通过 + 提交** — 预期 passed。
```bash
cd backend && poetry run black app/services/enrichment/content_enricher.py tests/unit/services/enrichment/test_content_enricher.py && poetry run isort app/services/enrichment/content_enricher.py tests/unit/services/enrichment/test_content_enricher.py
cd /Users/hongyang/Projects/GoMuseum && git add backend/app/services/enrichment/content_enricher.py backend/tests/unit/services/enrichment/test_content_enricher.py
git commit -m "feat(enrichment): ContentEnricher.generate_canonical(LLM注入+容错解析+空段None)"
```

---

## Task 4: 落库 `content_repo.persist_generated_sections`

**Files:** Modify `backend/app/services/content_repo.py`；Test `backend/tests/integration/test_content_persist.py`（追加）

- [ ] **Step 1: 失败测试（追加，复用既有 session fixture）**
```python
def test_persist_generated_sections_upsert(session):
    from app.services.content_repo import persist_generated_sections
    from app.models.content import ObjectContentSection

    n = persist_generated_sections(
        session, "Q1", "en",
        {"overview": "An overview.", "artist": None},  # artist None → 标 needs_review/不建
        model="gpt-4o-mini",
    )
    assert n == 1  # 只发布有内容的 overview
    rows = {r.section_code: r for r in session.query(ObjectContentSection).filter_by(language="en").all()}
    assert rows["overview"].body == "An overview."
    assert rows["overview"].status == "published"
    assert rows["overview"].model == "gpt-4o-mini"
    assert rows["overview"].source == "ai_generated"
    assert "artist" not in rows  # 空段不建行


def test_persist_generated_unknown_qid_returns_zero(session):
    from app.services.content_repo import persist_generated_sections
    assert persist_generated_sections(session, "Q404", "en", {"overview": "x"}, model="m") == 0
```
> 既有 `test_content_persist.py` 的 `session` fixture 已 seed orsay + Q1（见文件顶部）。

- [ ] **Step 2: 跑确认失败** — `cd backend && poetry run pytest tests/integration/test_content_persist.py -k generated -v`。

- [ ] **Step 3: 在 `content_repo.py` 加**
```python
def persist_generated_sections(
    db, qid: str, language: str, sections: dict, model: str | None = None
) -> int:
    """把生成的分段 body 落库（按 obj/lang/section upsert）。body 为 None/空的段不发布。返回发布数。"""
    from datetime import datetime, timezone

    obj = db.query(MuseumObject).filter_by(qid=qid).one_or_none()
    if not obj:
        return 0
    n = 0
    for code, body in sections.items():
        if not body:
            continue
        row = db.query(ObjectContentSection).filter_by(
            object_id=obj.id, language=language, section_code=code
        ).one_or_none() or ObjectContentSection(
            object_id=obj.id, language=language, section_code=code
        )
        row.body = body
        row.status = "published"
        row.source = "ai_generated"
        row.model = model
        row.generated_at = datetime.now(timezone.utc)
        db.add(row)
        n += 1
    db.commit()
    return n
```
(`MuseumObject`/`ObjectContentSection` 已在 content_repo.py 顶部 import。)

- [ ] **Step 4: 跑确认通过 + 提交** — `cd backend && poetry run pytest tests/integration/test_content_persist.py -v` 全 passed。
```bash
cd backend && poetry run black app/services/content_repo.py tests/integration/test_content_persist.py && poetry run isort app/services/content_repo.py tests/integration/test_content_persist.py
cd /Users/hongyang/Projects/GoMuseum && git add backend/app/services/content_repo.py backend/tests/integration/test_content_persist.py
git commit -m "feat(content): persist_generated_sections 接地生成分段落库(空段不发布)"
```

---

## Task 5: 默认 LLM `complete`（OpenAI 包装，便宜模型）

**Files:** Modify `backend/app/services/enrichment/content_enricher.py`

- [ ] **Step 1: 加 `default_complete`（同步包装异步 OpenAI；便宜模型；不单测，真实联网用）**
在 content_enricher.py 加：
```python
def default_complete(system: str, user: str, model: str = "gpt-4o-mini") -> str:
    """默认 LLM 调用（OpenAI，便宜模型）。grounded 生成是受约束改写，不需顶配。"""
    import asyncio

    from app.services.content_generation_service import _get_openai_client

    client = _get_openai_client()
    if client is None:
        raise RuntimeError("OpenAI client 不可用")

    async def _run():
        resp = await client.chat.completions.create(
            model=model,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
            temperature=0.3,
            response_format={"type": "json_object"},
        )
        return resp.choices[0].message.content

    return asyncio.run(_run())
```

- [ ] **Step 2: import 自检** — `cd backend && poetry run python -c "from app.services.enrichment.content_enricher import ContentEnricher, default_complete, build_material; print('ok')"`（用 pyenv 解释器；若 poetry venv 缺依赖见 1b 报告，用 `/Users/hongyang/.pyenv/versions/3.11.7/bin/python3.11`）。

- [ ] **Step 3: 提交**
```bash
cd backend && poetry run black app/services/enrichment/content_enricher.py && poetry run isort app/services/enrichment/content_enricher.py
cd /Users/hongyang/Projects/GoMuseum && git add backend/app/services/enrichment/content_enricher.py
git commit -m "feat(enrichment): ContentEnricher 默认 OpenAI complete(便宜模型,JSON模式)"
```

---

## 收尾

- [ ] **全套相关单测**：`cd backend && STORAGE_BACKEND=local poetry run pytest tests/unit/services/enrichment/test_content_enricher.py tests/unit/services/enrichment/test_prompts.py tests/integration/test_content_persist.py -W "ignore::PendingDeprecationWarning" -v` 全 passed。
- [ ] **提 PR**：`feature/content-enrichment-phase2a → staging`。无 DB 迁移。CI 绿后 squash 合并。
- [ ]（可选）合并后 staging 容器抽一件真实生成验证：`docker exec gomuseum_staging_backend python -c "..."` 用 default_complete 对 Q334138 生成英语 overview，看接地不脑补。

---

## Self-Review（计划对照 spec §7）

- **§7-1 组装材料**：`build_material`（Task 1，事实 + Wikipedia extract，标来源）✓。
- **§7-2 英语轴心生成**：`generate_canonical`（Task 3，一次 LLM、类别感知 prompt、缺料留空）✓。prompt（Task 2）含"只依据材料/原创/缺料空"。
- **§3 原创不照搬/宁缺毋滥**：prompt 明示 + 空段→None 不发布（Task 3/4）✓。
- **落库**：`persist_generated_sections`（Task 4，按 obj/lang/section upsert，空段不建行）✓。
- **便宜模型**：default_complete 默认 gpt-4o-mini（Task 5）✓。
- **不在本期**：蕴含校验 + 事实一致性 + 质量分（=2b）；翻译铺语言 + 译文忠实（=2c）；Q&A 预生成 + CLI generate + 金丝雀报告（=2d）；content_version 列（迁移，后续）。
- **类型一致**：`build_material(obj)->str`、`build_generation_prompt(material,sections,category)->(str,str)`、`ContentEnricher(complete).generate_canonical(obj,sections)->dict`、`persist_generated_sections(db,qid,language,sections,model)->int`、`default_complete(system,user,model)->str` 跨任务一致 ✓。
