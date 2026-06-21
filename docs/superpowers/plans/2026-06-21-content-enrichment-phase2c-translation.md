# 内容富化 Phase 2c 翻译铺语言 + 译文忠实校验 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 Phase 2b 已过质量闸的英语轴心正文翻译到目标语言集（默认 en/fr/de/es/it/zh），每条译文做忠实校验，漂移/丢事实的标 `needs_review`，按语言落库（复用 `persist_gated_sections`）。

**Architecture:** 新增 `lang_config.py`（语言集配置：全局默认 + `museums.yaml` 覆盖，零硬编码语言）；`prompts.py` 加翻译与忠实校验两个 prompt；新增 `translator.py`（`ContentTranslator`，LLM 经注入式 `complete` 离线可测，与 2a/2b 同款）；输出复用 2b 的 `SectionQuality`，直接喂已有 `persist_gated_sections` 按语言落库。

**Tech Stack:** Python 3.11 · FastAPI · SQLAlchemy · pytest · OpenAI（gpt-4o-mini，经 `default_complete` 复用）。

**本期范围（按既定 2c 切分，spec §14 + §8A-5）:** 仅翻译 + 译文忠实校验 + 语言集配置。英语轴心生成（2a）、质量闸（2b）已成；批量入口/建议问答/质量报告属 Phase 2d。**标题/专名不裸翻译**（§14：保留原文或既定译名）写进翻译 prompt 约束。langdetect 形式校验留后续（同 2b 遗留）。

**前置事实（已验证，勿重查）:**
- `SectionLabels`/段落标签已支持 en/fr/de/es/it/zh 六语（`category_config.SECTION_LABELS`）。
- 2b 的 `SectionQuality(body,status,grounding_ratio,conflicts,score)` 在 `app/services/enrichment/quality.py`。
- `persist_gated_sections(db, qid, language, results, model)`（`content_repo.py`）已能按语言写 published/needs_review，返回 `(pub, nr)`。
- `_parse_json` 在 `content_enricher.py`（容错 JSON 解析）。
- `default_complete` 在 `content_enricher.py`（gpt-4o-mini）。
- `MuseumConfig`（`catalog.py`）当前无 `languages` 字段。
- 2026-06-21 staging 实测发现 LLM 判官有噪声（fact-consistency 把创作年/展出年误判冲突）；译文忠实判官同属 LLM-as-judge，**偏严不偏松**可接受，校准靠金标准（后续）。

---

## 文件结构

| 文件 | 职责 | 动作 |
|---|---|---|
| `backend/app/services/enrichment/lang_config.py` | `DEFAULT_LANGUAGES`、`LANG_NAMES`、`resolve_languages(override)` | **新建** |
| `backend/app/services/enrichment/catalog.py` | `MuseumConfig` 加 `languages` 字段 + `from_file` 解析 | 修改 |
| `backend/app/services/enrichment/prompts.py` | 加 `build_translation_prompt`、`build_faithfulness_prompt` | 修改（追加） |
| `backend/app/services/enrichment/translator.py` | `ContentTranslator`：`translate_section` / `check_faithfulness` / `translate_object` | **新建** |
| `backend/tests/unit/services/enrichment/test_lang_config.py` | 语言集配置单测 | **新建** |
| `backend/tests/unit/services/enrichment/test_prompts.py` | 追加两个 prompt 断言 | 修改 |
| `backend/tests/unit/services/enrichment/test_translator.py` | 翻译器单测 | **新建** |
| `backend/tests/integration/test_content_persist.py` | 追加"译文喂 persist 按语言落库"集成测试 | 修改 |

**关键接口（贯穿全计划，先定死）:**

```python
# lang_config.py
DEFAULT_LANGUAGES = ["en", "fr", "de", "es", "it", "zh"]
LANG_NAMES = {"en": "English", "fr": "French", "de": "German",
              "es": "Spanish", "it": "Italian", "zh": "Chinese"}
def resolve_languages(override: list[str] | None = None) -> list[str]: ...

# translator.py（输出复用 quality.SectionQuality）
class ContentTranslator:
    def __init__(self, complete): ...                                  # complete(system,user)->str
    def translate_section(self, en_body: str, target_lang: str) -> str: ...
    def check_faithfulness(self, en_body: str, translated: str, target_lang: str) -> tuple[bool, list[str]]: ...
    def translate_object(self, en_sections: dict, target_langs: list[str]) -> dict: ...
    # en_sections: {section_code: en_body}（仅已发布英语正文，调用方过滤）
    # 返回 {lang: {section_code: SectionQuality}}，lang 跳过 "en"（轴心本身不翻）
```

---

## Task 1: 语言集配置 `lang_config` + `MuseumConfig.languages`

**Files:**
- Create: `backend/app/services/enrichment/lang_config.py`
- Modify: `backend/app/services/enrichment/catalog.py`（加字段 + 解析）
- Test: `backend/tests/unit/services/enrichment/test_lang_config.py`

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/unit/services/enrichment/test_lang_config.py
from app.services.enrichment.lang_config import (
    DEFAULT_LANGUAGES,
    LANG_NAMES,
    resolve_languages,
)


def test_resolve_languages_defaults_when_no_override():
    assert resolve_languages() == DEFAULT_LANGUAGES
    assert resolve_languages(None) == DEFAULT_LANGUAGES
    assert resolve_languages([]) == DEFAULT_LANGUAGES


def test_resolve_languages_uses_override():
    assert resolve_languages(["en", "fr"]) == ["en", "fr"]


def test_default_languages_all_have_names():
    for code in DEFAULT_LANGUAGES:
        assert code in LANG_NAMES


def test_museum_config_has_languages_field_defaulting_empty():
    from app.services.enrichment.catalog import MuseumConfig

    cfg = MuseumConfig(
        slug="x", name_zh="x", name_en="x", city_zh="x", city_en="x",
        country="FR", wikidata_qid="Q1", category_filter="painting",
        fetch_limit=1, sample_size=1,
    )
    assert cfg.languages == []
```

- [ ] **Step 2: 跑确认失败**

Run: `cd backend && poetry run pytest tests/unit/services/enrichment/test_lang_config.py -v`
Expected: FAIL（`ModuleNotFoundError: lang_config`）

- [ ] **Step 3a: 创建 `backend/app/services/enrichment/lang_config.py`**

```python
"""目标翻译语言集配置：全局默认 + museums.yaml 覆盖，代码零硬编码语言。spec §14。"""

from __future__ import annotations

# 默认语言集是运营旋钮、非架构（spec §14）。主市场欧洲 + 中文（开发语言）。
DEFAULT_LANGUAGES = ["en", "fr", "de", "es", "it", "zh"]

# 语言 code → 英文名（喂翻译/校验 prompt，便于模型识别目标语言）。
LANG_NAMES = {
    "en": "English",
    "fr": "French",
    "de": "German",
    "es": "Spanish",
    "it": "Italian",
    "zh": "Chinese",
}


def resolve_languages(override: list[str] | None = None) -> list[str]:
    """解析目标语言集：有非空 override（来自 museums.yaml）用之，否则全局默认。"""
    return list(override) if override else list(DEFAULT_LANGUAGES)
```

- [ ] **Step 3b: 改 `catalog.py`** — 给 `MuseumConfig` 加字段（放在 `country_lang` 后）：

```python
    country_lang: str | None = None
    languages: list[str] = field(default_factory=list)
```

并在 `from_file` 的 `MuseumConfig(...)` 构造里加一行（在 `country_lang=...` 后）：

```python
                country_lang=m.get("country_lang"),
                languages=list(m.get("languages") or []),
```

- [ ] **Step 4: 跑确认通过**

Run: `cd backend && poetry run pytest tests/unit/services/enrichment/test_lang_config.py -v`
Expected: PASS（4 passed）

- [ ] **Step 5: 提交**

```bash
cd backend && poetry run black app/services/enrichment/lang_config.py app/services/enrichment/catalog.py tests/unit/services/enrichment/test_lang_config.py && poetry run isort app/services/enrichment/lang_config.py app/services/enrichment/catalog.py tests/unit/services/enrichment/test_lang_config.py
cd /Users/hongyang/Projects/GoMuseum && git add backend/app/services/enrichment/lang_config.py backend/app/services/enrichment/catalog.py backend/tests/unit/services/enrichment/test_lang_config.py
git commit -m "feat(enrichment): 语言集配置 lang_config + MuseumConfig.languages 覆盖"
```

---

## Task 2: 翻译 + 译文忠实 prompt

**Files:**
- Modify: `backend/app/services/enrichment/prompts.py`（追加，不动既有函数）
- Test: `backend/tests/unit/services/enrichment/test_prompts.py`（追加）

设计要点：
- 翻译 prompt：忠实翻译、不增不减事实、**标题/专名保留原文或既定译名不硬翻**（§14）、返回纯文本（非 JSON）。
- 忠实 prompt：判译文与英语轴心是否同义不漂移，返 STRICT JSON `{"faithful": bool, "issues": [...]}`。

- [ ] **Step 1: 写失败测试（追加）**

```python
def test_translation_prompt_demands_faithful_and_keeps_proper_names():
    from app.services.enrichment.prompts import build_translation_prompt

    system, user = build_translation_prompt("Olympia is an 1863 painting.", "fr")
    blob = (system + user).lower()
    assert "french" in blob            # 目标语言名
    assert "faithful" in blob or "do not add" in blob
    assert "proper" in blob or "title" in blob   # 标题/专名不硬翻
    assert "Olympia is an 1863 painting." in user


def test_faithfulness_prompt_returns_json_verdict():
    from app.services.enrichment.prompts import build_faithfulness_prompt

    system, user = build_faithfulness_prompt(
        "Olympia is an 1863 painting.", "Olympia est un tableau de 1863.", "fr"
    )
    blob = (system + user).lower()
    assert "faithful" in blob
    assert "json" in blob
    assert "issues" in blob
    assert "Olympia est un tableau de 1863." in user
```

- [ ] **Step 2: 跑确认失败**

Run: `cd backend && poetry run pytest tests/unit/services/enrichment/test_prompts.py -k "translation or faithfulness" -v`
Expected: FAIL（`cannot import name build_translation_prompt`）

- [ ] **Step 3: 追加到 `prompts.py` 末尾**

```python
from app.services.enrichment.lang_config import LANG_NAMES

_TRANSLATION_SYSTEM = (
    "You are a professional art translator. Translate the given English artwork explanation "
    "into {lang}. Rules: (1) Be FAITHFUL — do NOT add, remove, or alter any fact. "
    "(2) Keep proper names, artist names, and work TITLES in their original form or the "
    "established exonym in the target language; do NOT literally translate titles. "
    "(3) Natural, fluent {lang}. Return ONLY the translated text, no commentary, no quotes."
)


def build_translation_prompt(en_body: str, target_lang: str):
    lang = LANG_NAMES.get(target_lang, target_lang)
    system = _TRANSLATION_SYSTEM.format(lang=lang)
    user = f"English:\n{en_body}"
    return system, user


_FAITHFULNESS_SYSTEM = (
    "You are a translation quality judge. You are given an English SOURCE and its {lang} "
    "TRANSLATION. Decide whether the translation is faithful: it must convey exactly the "
    "same facts with nothing added and nothing omitted (wording/fluency differences are "
    "fine). Return STRICT JSON: {{\"faithful\": true|false, \"issues\": [\"...\"]}} "
    "(issues empty if faithful). No commentary."
)


def build_faithfulness_prompt(en_body: str, translated: str, target_lang: str):
    lang = LANG_NAMES.get(target_lang, target_lang)
    system = _FAITHFULNESS_SYSTEM.format(lang=lang)
    user = f"SOURCE (English):\n{en_body}\n\nTRANSLATION ({lang}):\n{translated}"
    return system, user
```

> 注意 `_FAITHFULNESS_SYSTEM` 用了 `.format`，JSON 大括号必须双写 `{{ }}` 转义（如上）。

- [ ] **Step 4: 跑确认通过**

Run: `cd backend && poetry run pytest tests/unit/services/enrichment/test_prompts.py -v`
Expected: PASS（既有 3 + 新 2 = 5 passed）

- [ ] **Step 5: 提交**

```bash
cd backend && poetry run black app/services/enrichment/prompts.py tests/unit/services/enrichment/test_prompts.py && poetry run isort app/services/enrichment/prompts.py tests/unit/services/enrichment/test_prompts.py
cd /Users/hongyang/Projects/GoMuseum && git add backend/app/services/enrichment/prompts.py backend/tests/unit/services/enrichment/test_prompts.py
git commit -m "feat(enrichment): 翻译+译文忠实 prompt(忠实/标题不硬翻/JSON判定)"
```

---

## Task 3: `ContentTranslator.translate_section` + `check_faithfulness`

**Files:**
- Create: `backend/app/services/enrichment/translator.py`
- Test: `backend/tests/unit/services/enrichment/test_translator.py`

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/unit/services/enrichment/test_translator.py
import json

from app.services.enrichment.translator import ContentTranslator


def test_translate_section_returns_stripped_text():
    def fake_complete(system, user):
        return "  Olympia est un tableau de 1863.  "

    t = ContentTranslator(fake_complete)
    out = t.translate_section("Olympia is an 1863 painting.", "fr")
    assert out == "Olympia est un tableau de 1863."


def test_check_faithfulness_true_no_issues():
    def fake_complete(system, user):
        return json.dumps({"faithful": True, "issues": []})

    t = ContentTranslator(fake_complete)
    ok, issues = t.check_faithfulness("en body", "fr body", "fr")
    assert ok is True
    assert issues == []


def test_check_faithfulness_false_with_issues():
    def fake_complete(system, user):
        return json.dumps({"faithful": False, "issues": ["dropped the year"]})

    t = ContentTranslator(fake_complete)
    ok, issues = t.check_faithfulness("en body", "fr body", "fr")
    assert ok is False
    assert issues == ["dropped the year"]
```

- [ ] **Step 2: 跑确认失败**

Run: `cd backend && poetry run pytest tests/unit/services/enrichment/test_translator.py -k "translate_section or faithfulness" -v`
Expected: FAIL（`ModuleNotFoundError: translator`）

- [ ] **Step 3: 创建 `backend/app/services/enrichment/translator.py`**

```python
"""ContentTranslator：把英语轴心正文翻译到目标语言 + 译文忠实校验。
LLM 经注入式 complete，单测离线。spec §14 / §8A-5。"""

from __future__ import annotations

from app.services.enrichment.prompts import (
    build_faithfulness_prompt,
    build_translation_prompt,
)
from app.services.enrichment.quality import SectionQuality


def _parse():
    from app.services.enrichment.content_enricher import _parse_json

    return _parse_json


class ContentTranslator:
    def __init__(self, complete):
        self._complete = complete  # complete(system, user) -> str

    def translate_section(self, en_body: str, target_lang: str) -> str:
        system, user = build_translation_prompt(en_body, target_lang)
        return (self._complete(system, user) or "").strip()

    def check_faithfulness(self, en_body: str, translated: str, target_lang: str):
        system, user = build_faithfulness_prompt(en_body, translated, target_lang)
        data = _parse()(self._complete(system, user))
        return bool(data.get("faithful")), (data.get("issues") or [])
```

- [ ] **Step 4: 跑确认通过**

Run: `cd backend && poetry run pytest tests/unit/services/enrichment/test_translator.py -k "translate_section or faithfulness" -v`
Expected: PASS（3 passed）

- [ ] **Step 5: 提交**

```bash
cd backend && poetry run black app/services/enrichment/translator.py tests/unit/services/enrichment/test_translator.py && poetry run isort app/services/enrichment/translator.py tests/unit/services/enrichment/test_translator.py
cd /Users/hongyang/Projects/GoMuseum && git add backend/app/services/enrichment/translator.py backend/tests/unit/services/enrichment/test_translator.py
git commit -m "feat(enrichment): ContentTranslator 翻译段落+译文忠实校验"
```

---

## Task 4: `ContentTranslator.translate_object`（按语言铺，忠实→status）

**Files:**
- Modify: `backend/app/services/enrichment/translator.py`
- Test: `backend/tests/unit/services/enrichment/test_translator.py`（追加）

设计要点：
- `translate_object(en_sections, target_langs)`：对每个 `target_lang`（跳过 `"en"`，轴心本身不翻），对每个英语段落 `translate_section` → `check_faithfulness`；忠实 → `SectionQuality(body=译文, status="published", score=1.0)`，不忠实 → `SectionQuality(body=译文, status="needs_review", conflicts=issues, score=0.0)`。
- 返回 `{lang: {code: SectionQuality}}`。`en_sections` 里空 body 的段跳过。

- [ ] **Step 1: 写失败测试（追加）**

```python
from app.services.enrichment.quality import SectionQuality


def test_translate_object_skips_en_and_marks_unfaithful():
    # fr 忠实→published；de 不忠实→needs_review
    def router(system, user):
        s = system.lower()
        if "translate" in s:                       # 翻译调用
            return "translated body"
        # 忠实判定：fr 忠实、de 不忠实（按 system 里的语言名区分）
        if "german" in s:
            return json.dumps({"faithful": False, "issues": ["added a claim"]})
        return json.dumps({"faithful": True, "issues": []})

    t = ContentTranslator(router)
    out = t.translate_object({"overview": "English overview."}, ["en", "fr", "de"])

    assert set(out.keys()) == {"fr", "de"}          # en 被跳过
    assert out["fr"]["overview"].status == "published"
    assert out["fr"]["overview"].body == "translated body"
    assert out["de"]["overview"].status == "needs_review"
    assert out["de"]["overview"].conflicts == ["added a claim"]


def test_translate_object_skips_empty_section_bodies():
    def router(system, user):
        if "translate" in system.lower():
            return "x"
        return json.dumps({"faithful": True, "issues": []})

    t = ContentTranslator(router)
    out = t.translate_object({"overview": "ok", "artist": None}, ["fr"])
    assert set(out["fr"].keys()) == {"overview"}    # artist(None) 不翻
```

- [ ] **Step 2: 跑确认失败**

Run: `cd backend && poetry run pytest tests/unit/services/enrichment/test_translator.py -k translate_object -v`
Expected: FAIL（`'ContentTranslator' object has no attribute 'translate_object'`）

- [ ] **Step 3: 实现（在 `ContentTranslator` 类内追加）**

```python
    def translate_object(self, en_sections: dict, target_langs: list[str]) -> dict:
        """把英语段落铺到目标语言。跳过 'en'（轴心不翻）与空 body 段。
        返回 {lang: {section_code: SectionQuality}}。"""
        out: dict = {}
        for lang in target_langs:
            if lang == "en":
                continue
            lang_result: dict = {}
            for code, en_body in en_sections.items():
                if not en_body:
                    continue
                translated = self.translate_section(en_body, lang)
                ok, issues = self.check_faithfulness(en_body, translated, lang)
                lang_result[code] = SectionQuality(
                    body=translated,
                    status="published" if ok else "needs_review",
                    grounding_ratio=1.0 if ok else 0.0,
                    conflicts=issues,
                    score=1.0 if ok else 0.0,
                )
            out[lang] = lang_result
        return out
```

- [ ] **Step 4: 跑确认通过（全文件）**

Run: `cd backend && poetry run pytest tests/unit/services/enrichment/test_translator.py -v`
Expected: PASS（3 + 2 = 5 passed）

- [ ] **Step 5: 提交**

```bash
cd backend && poetry run black app/services/enrichment/translator.py tests/unit/services/enrichment/test_translator.py && poetry run isort app/services/enrichment/translator.py tests/unit/services/enrichment/test_translator.py
cd /Users/hongyang/Projects/GoMuseum && git add backend/app/services/enrichment/translator.py backend/tests/unit/services/enrichment/test_translator.py
git commit -m "feat(enrichment): translate_object 按语言铺+忠实→status(跳过en/空段)"
```

---

## Task 5: 集成 — 译文按语言落库（复用 `persist_gated_sections`）

**Files:**
- Test: `backend/tests/integration/test_content_persist.py`（追加，无新生产代码——验证 `translate_object` 输出能直接喂 `persist_gated_sections`）

- [ ] **Step 1: 写测试（追加，复用既有 `session` fixture：已 seed orsay + Q1）**

```python
def test_translate_object_output_persists_per_language(session):
    import json as _json
    from app.services.content_repo import persist_gated_sections
    from app.services.enrichment.translator import ContentTranslator
    from app.models.content import ObjectContentSection

    def router(system, user):
        if "translate" in system.lower():
            return "Texte traduit."
        return _json.dumps({"faithful": True, "issues": []})

    by_lang = ContentTranslator(router).translate_object(
        {"overview": "English overview."}, ["en", "fr"]
    )
    # 按语言落库
    for lang, results in by_lang.items():
        persist_gated_sections(session, "Q1", lang, results, model="gpt-4o-mini")

    rows = {
        (r.language, r.section_code): r
        for r in session.query(ObjectContentSection).all()
    }
    assert ("fr", "overview") in rows
    assert rows[("fr", "overview")].body == "Texte traduit."
    assert rows[("fr", "overview")].status == "published"
    assert ("en", "overview") not in rows          # en 不翻、不落
```

- [ ] **Step 2: 跑确认通过（本测试无需新代码，直接跑）**

Run: `cd backend && poetry run pytest tests/integration/test_content_persist.py -k per_language -v`
Expected: PASS（1 passed）

> 若失败，检查 `translate_object` 返回结构 `{lang: {code: SectionQuality}}` 与 `persist_gated_sections(db, qid, language, results, model)` 签名是否一致（Task 4 / 2b）。

- [ ] **Step 3: 提交**

```bash
cd backend && poetry run black tests/integration/test_content_persist.py && poetry run isort tests/integration/test_content_persist.py
cd /Users/hongyang/Projects/GoMuseum && git add backend/tests/integration/test_content_persist.py
git commit -m "test(content): 译文 translate_object 输出按语言落库集成验证"
```

---

## 收尾

- [ ] **全套相关单测**：
```bash
cd backend && STORAGE_BACKEND=local poetry run pytest \
  tests/unit/services/enrichment/test_lang_config.py \
  tests/unit/services/enrichment/test_prompts.py \
  tests/unit/services/enrichment/test_translator.py \
  tests/integration/test_content_persist.py \
  -W "ignore::PendingDeprecationWarning" -v
```
Expected: 全 passed。

- [ ] **提 PR**：`feature/content-enrichment-phase2c → staging`（用 `/pr`）。无 DB 迁移。CI 绿后 squash 合并、删分支。
- [ ]（可选）合并后 staging 容器对《奥林匹亚》英语已发布段跑 `ContentTranslator(default_complete).translate_object(en_published, ["fr","de"])`，肉眼看法/德译文忠实、标题未硬翻。

---

## Self-Review（计划对照 spec §14 / §8A-5）

- **§14 英语轴心 + 翻译铺语言**：`translate_object` 跳过 en、按 `target_langs` 铺（Task 4）✓。
- **§14 语言全参数化 + 配置驱动（全局默认 + museums.yaml 覆盖、零硬编码）**：`lang_config.DEFAULT_LANGUAGES` + `MuseumConfig.languages` + `resolve_languages`（Task 1）✓。
- **§14 标题/专名不裸翻译**：`build_translation_prompt` 明示保留原文/既定译名（Task 2）✓。
- **§8A-5 译文忠实校验（译文 vs 英语轴心，防漂移/丢事实）**：`build_faithfulness_prompt` + `check_faithfulness` + 不忠实→needs_review（Task 2/3/4）✓。
- **按语言落库**：复用 `persist_gated_sections` 按语言写 published/needs_review（Task 5 集成验证）✓。
- **注入式离线可测**：`ContentTranslator(complete)` 与 2a/2b 同款，单测全 mock ✓。
- **类型一致性**：`translate_object` 返回 `{lang: {code: SectionQuality}}`，`SectionQuality` 复用 2b 同型，喂 `persist_gated_sections` 一致（Task 4/5）✓。`check_faithfulness` 返 `(bool, list)` 跨 Task 3/4 一致 ✓。
- **DRY**：复用 2b `SectionQuality` / `persist_gated_sections`、2a `_parse_json`、`LANG_NAMES` 单一真相源 ✓。
- **本期不做（显式）**：批量入口/建议问答/质量报告（2d）、langdetect 形式校验（后续）、判官校准（金标准，后续）——非遗漏。
